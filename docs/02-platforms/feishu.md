# 飞书招聘 ATS

> 飞书招聘（`atsx-*` 类名）被大量新消费、出海公司、部分大厂采用。
> 最大的特点：**长表单 + 区块虚拟化**，滚动时 DOM 会卸载，导致已填的值"消失"。

## 目录

- [一、识别](#一识别)
- [二、区间日期选择器（period picker）](#二区间日期选择器period-picker)
- [三、虚拟列表陷阱：填完立即提交](#三虚拟列表陷阱填完立即提交)
- [四、atsx 组件对照表](#四atsx-组件对照表)
- [五、学校/专业联想输入](#五学校专业联想输入)
- [六、非 feishu.cn 域名的飞书 ATS](#六非-feishucn-域名的飞书-ats)
- [七、踩坑实录](#七踩坑实录)

---

## 一、识别

```js
document.querySelectorAll('[class*="atsx-"]').length > 0
```

URL 特征（两种）：

| 形态 | URL |
|---|---|
| 官方域名 | `*.jobs.feishu.cn/<project>/position/list` |
| 企业自有域名 | `careers.<company>.com`、`jobs.<company>.com`（底层仍是 atsx） |

页面特征：
- 顶部导航 + 左右分栏（左筛选 / 右列表）
- 职位详情页底部**黄色「提交简历」**按钮
- 表单页通常有「投递信息 / 完善简历 / 开放性问题 / 完成投递」四步

---

## 二、区间日期选择器（period picker）

飞书 ATS 的「起止时间」是一个**组合控件**，不是两个输入框：

```html
<div class="atsx-date-picker atsx-date-picker-period-month">
  <div class="atsx-date-picker-period-month-label" data-cy="education[0].periodInputBegin">
    <span class="atsx-date-picker-period-month-label-year" data-cy="year">2023</span>
    <span class="atsx-date-picker-period-mont" ...>09</span>
  </div>
</div>
```

### DOM 结构特征

- 每段经历都有 `data-cy="<section>[N].period"` 这样的稳定标识
- `section` 取值：`education`、`internship`、`work`、`project`
- **索引从 1 开始**（`internship[1]` 是第一段，不是 `[0]`）

```js
// 列出所有区间控件
[...document.querySelectorAll('[data-cy$="period"]')].map(e => ({
  cy: e.getAttribute('data-cy'),
  value: e.innerText.replace(/\n/g, '|'),
}));
// → [{ cy:'education[1].period', value:'起止时间|2023-09|2027-06' }, ...]
```

### 操作流程

```js
async function setPeriod(cy, year, month) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 1) 点开面板
  const el = document.querySelector(`[data-cy="${cy}"]`);
  el.scrollIntoView({ block: 'center' });
  await sleep(600);
  await cua.click(centerOf(el));
  await sleep(1800);   // 面板渲染需要时间

  // 2) 面板出现「年列 + 月列」
  //    年份列默认可能停在很远的未来，需要滚动
  let yearEl = findText(String(year));
  if (!yearEl) {
    await cua.scroll({ x: YEAR_COL_X, y: PANEL_MID_Y, scrollX: 0, scrollY: 400 });
    await sleep(1200);
    yearEl = findText(String(year));
  }
  if (!yearEl) return { err: 'year not found' };

  await cua.click(centerOf(yearEl));
  await sleep(1000);

  // 3) 点月份
  const monthEl = findText(month);
  if (!monthEl) return { err: 'month not found' };
  await cua.click(centerOf(monthEl));
  await sleep(1200);

  // 4) 回读验证
  return { value: document.querySelector(`[data-cy="${cy}"]`).innerText };
}
```

### 关键点

1. **面板里数字可能重复**（年列有 `2026`，正文里也有 `2026`）→ 用 `getBoundingClientRect().y > 100` 之类的条件限定在面板内
2. **年份列滚动方向**：`cua.scroll` 的 `scrollY` 为**负值**时显示**更近年份**，正值显示更老年份
3. **面板会因重渲染自动关闭** → 点开年份后如果月份列找不到，说明面板关了，要重新走一遍
4. **改完必须回读** `data-cy="...period"` 的文本确认

### 另一种形态：`atsx-select` 年月下拉

部分飞书表单把年月做成两个标准下拉：

```js
// 年
await pickAtsxSelect('开始时间-年', '2026');
// 月
await pickAtsxSelect('开始时间-月', '03');
```

---

## 三、虚拟列表陷阱：填完立即提交

### 现象

飞书 ATS 的长表单（实习经历、项目经历列表）在滚动时**会卸载当前不可见的区块 DOM**，React state 也随之重置。

表现：
- 教育经历填好了 → 往下滚到实习经历 → 再滚回去 → **教育经历的值没了**
- 区块校验报红字，但红字来自**已卸载区块的残影**

### 解法

1. **填完立即提交，不做多余滚动**
2. 如果必须滚动，**每填完一个区块立刻回读校验**

```js
// 每填完一个区块就回读
const check = () => {
  const vals = [...document.querySelectorAll('input,textarea')]
    .filter(e => e.offsetHeight > 0 && e.value)
    .map(e => e.placeholder + '=' + e.value.slice(0, 20));
  return vals;
};
```

3. **判断字段是否真的为空，以 DOM 实际值为准，不要信红字**

### 提交按钮无反应

实战中遇到过：`cua.click` 和 React `onClick` 直调都不触发提交请求（无网络请求、无 modal）。

**这是止损信号** —— 让用户手动点击提交按钮。

---

## 四、atsx 组件对照表

| 类名 | 类型 | 填法 |
|---|---|---|
| `atsx-input.atsx-input-lg` | 文本输入 | React 原生 setter |
| `atsx-select` | 单选下拉 | 真实 UI 点击 → 输入过滤 → 点选项 |
| `atsx-select-dropdown` | 下拉面板 | portal，在 document 级 |
| `atsx-date-picker-period-month` | 区间日期 | 见第二节 |
| `atsx-textarea` | 多行文本 | React 原生 setter |
| `atsx-checkbox` | 复选 | 鼠标事件序列 |
| `atsx-upload` | 上传 | 见 `03-browser-automation.md` |

### 文本输入的正确写法

```js
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(input, value);
input.dispatchEvent(new Event('input', { bubbles: true }));
input.dispatchEvent(new Event('change', { bubbles: true }));
```

**文本框不参与 `innerText`** —— 校验时要读 `input.value`：

```js
// 逐字段的值
[...document.querySelectorAll('input,textarea')]
  .filter(i => i.offsetHeight > 0)
  .map(i => (i.placeholder || i.type) + '=' + i.value.slice(0, 24))
```

### 下拉的坐标不稳定问题

`atsx-select` 的下拉面板是 **portal**，位置由 JS 计算。
点击字段和点击选项之间如果有任何重排（例如滚动），**面板位置会变**。

**解法**：点开字段后**立刻**取选项坐标并点击，中间不要插入其他操作。

---

## 五、学校/专业联想输入

飞书 ATS 的「学校名称」「专业」是**联想型输入框**：

- 输入后弹出候选列表
- 从列表选择才会写入内部值
- 直接输入完整名称 + 失焦，部分表单能接受，部分会清空

### 标准流程

```js
// 1) 点击输入框
await cua.click(centerOf(schoolInput));
await sleep(400);

// 2) 输入关键词
await cua.type({ text: '浙江大学' });
await sleep(1800);   // 等联想列表

// 3) 在候选列表里点选
const option = [...document.querySelectorAll('[class*="dropdown"] [class*="item"],
                                            [class*="option"]')]
  .find(o => o.innerText.includes('浙江大学') && o.getBoundingClientRect().height > 0);
if (option) {
  await cua.click(centerOf(option));
} else {
  // 无候选时的降级：失焦保留手输值
  await cua.keypress({ keys: ['Escape'] });
  await cua.click({ x: 100, y: 100 });   // 点空白失焦
}
```

### 联想库没有主条目的情况

**实测遇到**：联想库里只有「XX大学继续教育学院」，没有「XX大学」主条目。

**处理**：手输全名 → `Escape` 关联想 → 点空白 blur → 值保留 → 提交校验能通过。

### `cua.type` 叠加字符

联想输入框在联想未就绪时连续 type 会**叠加字符**（如输入「XX专业」变成「XXXX专业」）。

**规则**：文本字段一律用 React setter，或用「点击后单次 type + 长等待」。

---

## 六、非 feishu.cn 域名的飞书 ATS

部分公司（尤其新消费品牌）用自有域名承载飞书 ATS，特征一致但 URL 不同。

**识别方法**：看 CSS 前缀，不看域名。

```js
document.querySelectorAll('[class*="atsx-"]').length
```

实战案例：某美妆品牌用 `jobs.<brand>.com` 承载，`atsx-` 类名完全一致，填法通用。

### 该场景的两个额外坑

1. **多个同名字段**：表单里出现多个都叫「描述」的 textarea（分别是实习描述、项目描述、自我评价）
   → 必须**按字段容器定位**，不能按 placeholder

```js
// 按 label 精确定位
const label = [...document.querySelectorAll('*')]
  .find(e => e.children.length === 0 && e.innerText.trim() === '项目描述');
let box = label;
for (let i = 0; i < 5; i++) { box = box.parentElement; if (box?.querySelector('textarea')) break; }
const textarea = box.querySelector('textarea');
```

2. **块级滚动容器**：SECTION 元素自带 `overflow: scroll`，`window.scrollTo` 无效
   → 要滚动**块级容器**本身，不是 window

```js
// 找到可滚动祖先
let p = el, scroller = null;
for (let k = 0; k < 8 && p; k++) {
  p = p.parentElement;
  if (p && p.scrollHeight > p.clientHeight + 5) { scroller = p; break; }
}
if (scroller) scroller.scrollTop = scroller.scrollHeight;
```

---

## 七、踩坑实录

### 坑 1：`innerText` 检查字段值全是空

文本框的 value 不进 `innerText`。校验必填时要读 `input.value`。

### 坑 2：上传成功后读 `input.files` 是空

飞书 ATS 的文件控件会**立即消费** `input.files`。判断成功的正确方式：

```js
// ✅ 看页面上有没有文件名
const ok = /\.(pdf|docx?|jpe?g|png)/i.test(document.body.innerText);
```

### 坑 3：表单四步流程的跳转

飞书 ATS 常见流程：

```
投递信息 → 完善简历 → 开放性问题 → 完成投递
```

- **投递信息**（第一步）经常出现「下一步」按钮**一直灰着**，即使所有必填项都填了
- 排查过：重新选下拉、点暂存触发校验、检查所有 radio 都选中 —— 都没解开
- **这是平台前端的状态判断问题**，止损让用户手动点

**经验**：飞书 ATS 的「下一步」按钮灰着时，**先让用户刷新页面重进**（草稿会保留），往往就好了。

### 坑 4：开放性问题没有字数提示

`maxlength` 常是 2000，但页面上不一定显示。先探测再决定填多长：

```js
const ta = document.querySelector('textarea');
console.log(ta.maxLength);   // 2000 或 -1
```

### 坑 5：period picker 改一条要重开一次面板

因为面板会在选择后自动关闭，**批量改 N 条经历的时间 = N 次完整的「点开 → 选年 → 选月」**。

建议**把时间字段放在最后处理**，或者直接交给用户手填（用户点两下就完了）。
