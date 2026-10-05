# 浏览器自动化工程技巧

> 这一篇是工程实现层面的经验：内置浏览器（IAB）的调用模型、定位策略、上传方案、以及那些"看起来该行但就是不行"的场景怎么排查。

## 目录

- [一、运行模型：每次调用都是新内核](#一运行模型每次调用都是新内核)
- [二、标签页管理协议](#二标签页管理协议)
- [三、观察策略：snapshot 优先，截图按需](#三观察策略snapshot-优先截图按需)
- [四、定位的七层降级](#四定位的七层降级)
- [五、⛔ 文件上传的完整方案](#五-文件上传的完整方案)
- [六、坐标失效与滚动](#六坐标失效与滚动)
- [七、排查手册：点击没反应怎么办](#七排查手册点击没反应怎么办)
- [八、性能与稳定性](#八性能与稳定性)

---

## 一、运行模型：每次调用都是新内核

内置浏览器的 JS 沙箱**每次调用都是全新的内核**：

- 变量不保留
- 模块缓存不保留
- `browser` / `tab` 绑定不保留

**唯一持久的是浏览器本身的标签页。**

### 因此每次调用都要重新 bootstrap

```js
// 每次调用开头必须重新初始化
const { join } = await import('node:path');
const { pathToFileURL } = await import('node:url');
const clientUrl = pathToFileURL(join(PLUGIN_ROOT, 'scripts', 'browser-client.mjs')).href;
const { setupBrowserRuntime } = await import(clientUrl);
await setupBrowserRuntime({ globals: globalThis });

const browser = await agent.browsers.getDefault();
const tab = await browser.tabs.get('<tab-id>');   // 每次都要重新取
```

### tab id 不能凭记忆复用

**每次新逻辑批次开始前，先完整列出标签页**，确认 id/url/title 后再 `tabs.get(id)`。

```js
// 第一步：列出来，把结果返回给模型看
const tabs = await browser.tabs.list();
return tabs.map(t => ({ id: t.id, url: t.url, title: t.title }));

// 第二步（新的调用）：按 url 匹配，再 get
const target = (await browser.tabs.list()).find(t => t.url.includes('/apply'));
const tab = await browser.tabs.get(target.id);
```

**不要**用 `tabs[0]`、`tabs.at(-1)` 或记忆中的 id。

---

## 二、标签页管理协议

### 优先复用同站标签

```js
// 会用现有同源标签，没有才新建
const tab = await agent.browsers.open(url);
```

### 需要并行独立标签时才显式新建

```js
const tab = await browser.tabs.new();
await tab.goto(url);
await tab.playwright.waitForLoadState({ state: 'domcontentloaded' });
```

### 导航后必须确认加载状态

```js
await tab.goto(url);
await tab.playwright.waitForLoadState({ state: 'domcontentloaded' });   // 必须显式调用
```

**不要**用 `networkidle`（在 IAB 后端不被支持），也不要固定 sleep 代替。

### 动作可能开新标签时，一次性读两个列表

```js
const [controlledTabs, userTabs] = await Promise.all([
  browser.tabs.list(),
  browser.user.openTabs(),
]);
```

### 用户已有但未接管的标签

```js
const userTabs = await browser.user.openTabs();
const tab = await browser.user.claimTab(userTabs[0]);   // 接管
```

**登录场景常用**：用户在自己的标签里登录后，用 `claimTab` 接管继续操作。

---

## 三、观察策略：snapshot 优先，截图按需

### 默认用 domSnapshot 读页面

返回的是 AI/ARIA 树，含 role、accessible name、状态，**比截图更精确也更省**。

```js
const snap = await tab.playwright.domSnapshot();
// 用返回的 role/name 构造稳定的 locator
await tab.playwright.getByRole('button', { name: '搜索职位' }).click();
```

### 什么时候才该截图

只有三种情况：

1. **需要确认视觉布局**（对齐、溢出、遮挡）
2. **用户明确要求截图**或要做视觉验证
3. **目标不在 snapshot 里**（canvas、自定义绘制组件、非 DOM 控件）→ 需要坐标瞄准

**不要在同一个调用里同时 snapshot 和 screenshot。**

### 截图必须用 emitImage 输出

```js
nodeRepl.emitImage(await tab.screenshot());
```

**不要**把 `tab.screenshot()` 作为最后一个表达式，也不要直接返回它的字节。

---

## 四、定位的七层降级

```
① Playwright 语义定位器
   getByRole / getByText / getByPlaceholder / getByLabel
   ↓ 超时 / strict 冲突
② 重新 domSnapshot，从 snapshot 事实重建 locator
   ↓ 仍不行
③ 页面内原生 click()（合成事件）
   element.click()
   ↓ 仍不行
④ 鼠标事件序列
   ['pointerdown','mousedown','pointerup','mouseup','click']
   ↓ 仍不行
⑤ cua 真实鼠标点击（需要坐标）
   await tab.cua.click({ x, y })
   ↓ 仍不行
⑥ 【最后手段】React fiber 直调
   props.onChange(...) / props.onClick(...)
   ↓ 仍不行
⑦ 【止损】转人工
```

### 关键纪律

**同一个 locator 失败后不要原样重试。**

超时/strict 冲突/选择器解析失败之后：

1. 立刻 `domSnapshot()`
2. 从 snapshot 里找**真实存在**的元素
3. 重建 locator（或换降级层）

**React 直调为什么排在后面**：它能解决很多顽疾（隐藏按钮、拒绝写入的控件），但对某些框架（尤其 Moka 的 `sd-Select`）会造成 store 污染，导致**用户提交时炸掉**。所以它是核武器，不是首选。

---

## 五、⛔ 文件上传的完整方案

内置浏览器**不支持文件选择器**（没有 `setFiles`），所以要用下面这个方案。

### 步骤 1：起一个带 CORS 头的本地静态服务

```python
# corssrv.py
import http.server, functools

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')      # ← 关键
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    def log_message(self, *a):
        pass

http.server.ThreadingHTTPServer(('127.0.0.1', 8731),
                                functools.partial(H, directory='/tmp')).serve_forever()
```

```bash
python3 corssrv.py &
curl -sI http://127.0.0.1:8731/resume.pdf | grep -i -E "HTTP|access-control|content-length"
```

> ⚠️ **`Access-Control-Allow-Origin: *` 是必须的。**
> HTTPS 页面 fetch `http://127.0.0.1` 时：
> - 混合内容（HTTPS → HTTP localhost）Chrome **允许**（127.0.0.1 属于 potentially trustworthy origin）
> - 但 **CORS 仍然强制** —— 没有 ACAO 头会直接抛 `TypeError: Failed to fetch`
>
> 这个坑很隐蔽：浏览器 Console 只显示 `Failed to fetch`，不会告诉你是 CORS。

### 步骤 2：页面内构造 File 并注入

```js
const res  = await fetch('http://127.0.0.1:8731/resume.pdf');
if (!res.ok) return { err: 'http ' + res.status };
const buf  = await res.arrayBuffer();
const file = new File([buf], 'resume.pdf', { type: 'application/pdf' });

const input = document.querySelectorAll('input[type=file]')[0];
const dt = new DataTransfer();
dt.items.add(file);
input.files = dt.files;

input.dispatchEvent(new Event('change', { bubbles: true }));
input.dispatchEvent(new Event('input',  { bubbles: true }));
```

### 步骤 3：判断是否成功

**不要读 `input.files.length`。** 很多组件会立即消费掉 files。

```js
// ✅ 正确判据：页面上出现了文件名
const ok = /\.(pdf|docx?|jpe?g|png)/i.test(document.body.innerText);

// ✅ 或者：等待解析完成的标志（如"删除""重新上传"按钮出现）
const uploaded = !!document.querySelector('[class*="delete"], [class*="重新上传"]');
```

### 步骤 4：如果失败

**赋值后 `files.length === 0` → 该控件校验了文件来源，停止尝试。**

```
【需你手填】个人照片上传
- 文件：<绝对路径>
- 位置：表单"个人形象"区块
- 说明：该控件会校验文件是否来自真实用户选择，程序化注入被拒
```

### 清理

```bash
pkill -f corssrv.py
rm -f /tmp/resume.pdf
```

**每次用完必须关掉本地服务** —— 别让一个开放的本地 HTTP 服务一直挂着。

---

## 六、坐标失效与滚动

### 问题

`scrollIntoView` 之后取的坐标，**在下一次工具调用时可能已经失效**（页面重排、滚动回弹）。

### 解法：同一调用内完成「定位 → 取坐标 → 行动」

```js
// ✅ 一次调用内完成
const pos = await tab.playwright.evaluate(async () => {
  const el = document.querySelector('[data-cy="xxx"]');
  el.scrollIntoView({ block: 'center' });
  await new Promise(r => setTimeout(r, 600));      // 等滚动稳定
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
});
await tab.cua.click({ x: pos.x, y: pos.y });       // 立刻用
```

### 批量操作时

循环内**每次重新取坐标**：

```js
for (const [label, value] of FIELDS) {
  const pos = await evaluate(/* 定位 + 取坐标 */);
  await cua.click(pos);
  await cua.type({ text: value });
}
```

### 元素在视口外时的坐标

`getBoundingClientRect()` 返回的 y 可能是负数（元素在视口上方）。

**cua 点击需要视口内坐标。** 所以必须先 `scrollIntoView`。

### 块级滚动容器

不是所有可滚动区域都是 window。很多 SPA 用 `div { overflow: scroll }`。

```js
// 找可滚动祖先
let p = el, scroller = null;
for (let k = 0; k < 8 && p; k++) {
  p = p.parentElement;
  if (p && p.scrollHeight > p.clientHeight + 5) { scroller = p; break; }
}
if (scroller) scroller.scrollTop = scroller.scrollHeight;

// 或者用 cua.scroll（需要面板内坐标）
await tab.cua.scroll({ x: colX, y: panelMidY, scrollX: 0, scrollY: 400 });
```

---

## 七、排查手册：点击没反应怎么办

按顺序排查：

### ① 元素是否真的可见

```js
const r = el.getBoundingClientRect();
console.log(r.width, r.height, r.y, r.x, getComputedStyle(el).visibility, getComputedStyle(el).display);
```

`height === 0` → 元素被隐藏（`display:none` / 折叠面板未展开）

### ② 是否被遮挡

```js
const r = el.getBoundingClientRect();
const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
console.log('实际命中的元素:', top?.className);
```

`top` 不是目标元素就是被遮挡了。

### ③ 是否有未关闭的弹窗/遮罩

```js
[...document.querySelectorAll('[class*="modal"],[class*="dialog"],[class*="mask"],[class*="overlay"]')]
  .filter(e => e.getBoundingClientRect().height > 0)
  .forEach(e => console.log(e.className, e.innerText.slice(0, 40)));
```

### ④ 元素是否 disabled

```js
console.log(el.disabled, el.getAttribute('aria-disabled'), el.className);
```

**`disabled === true` 的元素不会触发任何处理器** —— 这时候点多少次都没用，要找**为什么它是 disabled**（通常是某个前置条件没满足）。

### ⑤ 是不是需要先失焦上一个控件

```js
await tab.cua.keypress({ keys: ['Escape'] });   // 关掉可能开着的面板
await tab.cua.click({ x: 100, y: 100 });        // 点空白
```

### ⑥ 换降级层

按第四节的七层降级往下走。

### ⑦ 止损

试到第 4 层仍不行 → 转人工，输出字段清单。

---

## 八、性能与稳定性

### 等待策略

| 场景 | 用什么 |
|---|---|
| 导航后 | `waitForLoadState({state:'domcontentloaded'})` |
| 等元素出现 | `locator.waitFor({state:'visible'})` |
| 等下拉展开 | 等面板元素 `height > 0` |
| 等异步数据 | 轮询目标元素，而不是固定 sleep |
| 真的没别的办法 | `waitForTimeout(ms)` （最后手段） |

### 轮询代替死等

```js
async function waitFor(fn, timeout = 5000, interval = 300) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const r = await evaluate(fn);
    if (r) return r;
    await tab.playwright.waitForTimeout(interval);
  }
  return null;
}

// 用法：等简历解析完成
const done = await waitFor(() => document.body.innerText.includes('删除'));
```

### 长表单的操作节奏

**不要一口气跑完 50 个字段。** 分批次：

1. 填 5-8 个字段
2. 回读验证
3. 继续下一批

原因：中途出问题时，你能精确知道是从哪一步开始错的。

### 关键节点后必须回读

| 节点 | 回读什么 |
|---|---|
| 上传简历后 | 解析出来的字段值（逐条核对） |
| 每个下拉选完后 | 字段的显示值 / `input.value` |
| 每个日期设完后 | 日期控件的文本 |
| 触发校验后 | 缺项红字清单 |
| 提交前 | 完整字段快照 |

### 页面卡住时的处置

如果 `playwright.evaluate` 抛出 `Inspected target navigated or closed`，说明**上一次操作触发了导航**。

**这不是错误，是信号**：重新读标签页列表，确认当前 URL，继续。

```js
const tabs = await browser.tabs.list();
// 按新 URL 找到标签，继续操作
```
