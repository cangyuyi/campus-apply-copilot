# 平台识别速查表

打开一个网申页面，先认出它是哪套系统 —— 这决定了你该用哪套填法。

## 一秒识别

| 看什么 | 北森 Beisen | Moka | 飞书 ATS | Element UI 系 | 企业自建 |
|---|---|---|---|---|---|
| **URL** | `*.zhiye.com`<br>`*.hotjob.cn` | `app.mokahr.com` | `*.jobs.feishu.cn` | 各家域名 | 各家域名 |
| **CSS 前缀** | `phoenix-*`（新版）<br>`cmp_*` / `apply-field`（老版） | `sd-*`<br>`apply-field-*` | `atsx-*` | `el-*` | 自研类名 |
| **页面特征** | 左侧/顶部锚点导航，区块可折叠 | 顶部 tab + 左侧锚点，右上角"暂存" | 底部黄色"提交简历"按钮 | `el-input` / `el-select` / `el-upload` | 五花八门 |
| **典型公司** | 大量国企/制造业/银行 | 互联网公司、独角兽 | 字节系、部分新消费 | 老版门户、部分自建站 | 各行业龙头 |

## DOM 探针（贴进 Console 秒判）

```js
(() => {
  const s = document.documentElement.outerHTML;
  const hit = (re) => (s.match(re) || []).length;
  const score = {
    '北森-新版 phoenix': hit(/phoenix-/g),
    '北森-老版 cmp':     hit(/cmp_name|cmp_type/g),
    'Moka sd-':          hit(/sd-Input-|sd-Select-|apply-field-/g),
    '飞书 ATS atsx':     hit(/atsx-/g),
    'Element UI':        hit(/el-input|el-select|el-upload/g),
  };
  return Object.entries(score).sort((a,b) => b[1]-a[1]);
})()
```

得分最高的那套就是当前平台。

## 各平台的核心难点

| 平台 | 最大的坑 | 解法 |
|---|---|---|
| **北森** | 穿梭面板点"确定"不写入；日期控件拒绝程序化写入 | `cmp onChange 直调法` → [beisen.md](beisen.md) |
| **北森（新版）** | 选项编码要钻进 React fiber 取 `itemData`；凭经验传值会"显示对、存储错" | 从 `itemData` 里读 `code` → [beisen.md](beisen.md) |
| **Moka** | 用 `_set_`/`onChange` 直调下拉会污染内部 store，**用户提交时报错页** | 一律真实 UI 点击 → [moka.md](moka.md) |
| **飞书 ATS** | 长表单滚动时区块 DOM 卸载、React state 重置 | 填完立即提交，不做多余滚动 → [feishu.md](feishu.md) |
| **Element UI** | `el-upload` 的 `input[type=file]` 是 `display:none`，且会重置 | 见 [element-ui.md](element-ui.md) |
| **企业自建** | 组件行为不可预测，同一平台不同公司实现不同 | 见 [custom-sites.md](custom-sites.md) |

## 通用降级链路

不管哪套系统，填不进去时按这个顺序降级：

```
1. Playwright 定位器（getByRole / getByPlaceholder / getByText）
   ↓ 超时/不可交互
2. domSnapshot 重新定位 → 重建 locator
   ↓ 仍不行
3. 页面内原生 click()（合成事件）
   ↓ 仍不行
4. 鼠标事件序列（pointerdown→mousedown→pointerup→mouseup→click）
   ↓ 仍不行
5. cua 真实鼠标点击（需要坐标）
   ↓ 仍不行
6. React fiber 直调 props.onChange / onClick
   ↓ 仍不行（或属于 Moka 的下拉）
7. 【止损】转人工，输出字段名 + 应填值
```

**注意第 6 步的位置**：React 直调是"核武器"，能解决很多顽疾，但对某些框架（尤其 Moka 的 SD-Select）会造成 store 污染，导致用户提交时炸掉。所以它排在真实 UI 交互之后，不是之前。
