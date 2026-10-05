# Element UI 系表单

> 大量企业自建站和老版招聘门户用 Element UI（`el-*` 类名）。
> 组件行为相对标准，但**文件上传（`el-upload`）是个硬骨头**。

## 目录

- [一、识别](#一识别)
- [二、文本与选择器](#二文本与选择器)
- [三、⛔ el-upload：为什么传不上去](#三-el-upload为什么传不上去)
- [四、通用降级方案](#四通用降级方案)
- [五、踩坑实录](#五踩坑实录)

---

## 一、识别

```js
document.querySelectorAll('[class*="el-input"], [class*="el-select"]').length > 0
document.querySelectorAll('[class*="el-upload"]').length > 0
```

页面特征：
- `el-input__inner` / `el-select__caret` / `el-dialog__wrapper`
- 下拉面板 `.el-select-dropdown`（portal 挂到 body）
- 日期选择器 `.el-date-picker`

---

## 二、文本与选择器

### 文本输入

Element UI 的 `el-input` 是受控组件，React 原生 setter 通常可用：

```js
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(input, value);
input.dispatchEvent(new Event('input', { bubbles: true }));
input.dispatchEvent(new Event('change', { bubbles: true }));
```

**注意**：Vue 实现的 Element UI 监听的是 `input` 事件（不是 React 的 `onChange`），
所以 **`input` 事件是必须的**，`change` 可以带上但不要只发 `change`。

### 下拉选择

```js
async function pickElSelect(labelText, optionText) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 1) 点击触发下拉
  const input = findInputByLabel(labelText);
  input.scrollIntoView({ block: 'center' });
  await sleep(500);
  await cua.click(centerOf(input));
  await sleep(1000);

  // 2) 面板挂在 body 上
  const panel = [...document.querySelectorAll('.el-select-dropdown')]
    .find(p => p.getBoundingClientRect().height > 0);
  if (!panel) return { err: 'panel not open' };

  // 3) 找到目标项
  const option = [...panel.querySelectorAll('.el-select-dropdown__item')]
    .find(o => o.innerText.trim() === optionText);
  if (!option) return { err: 'option not found' };

  // 4) 真实点击
  await cua.click(centerOf(option));
  await sleep(800);
  return { ok: true };
}
```

### 日期选择

`el-date-picker` 的输入框是**只读**的，必须点开面板选：

```js
await cua.click(centerOf(dateInput));
await sleep(1000);
// 面板：.el-picker-panel
// 年份：点 .el-date-picker__header-label 切换年视图
// 月份：点 .el-month-table td
// 日期：点 .el-date-table td.available
```

**年份跨度大时**，点表头切到年视图比翻月视图快得多。

---

## 三、⛔ el-upload：为什么传不上去

### 现象

`input[type=file]` 存在，但：

| 尝试 | 结果 |
|---|---|
| 原生 `change` 事件 | ❌ 无效 |
| React `onChange` 直调 | ❌ 无效 |
| 取消 `display:none` 父节点 | ❌ 无效 |
| 加 `aria-label` | ❌ 无效 |
| `new DataTransfer()` + `input.files = dt.files` | ❌ **files 立刻被重置为 0** |

**对照组**：同一个站点上，**简历附件的上传口用同样方法可以成功**。

### 为什么

`el-upload` 内部维护了自己的 fileList 状态。
当 `input.files` 被程序化赋值时，Element UI 的 `onChange` 处理器会**校验文件是否来自真实的用户选择**，
不是则清空 —— 所以 `files.length` 立刻变 0。

### 触发条件

**只在部分场景触发**：

- ✅ 有的 `el-upload` 接受程序化赋值（简单配置，无 `beforeUpload` 校验）
- ❌ 有的会拒绝（带图片尺寸校验、带 `http-request` 自定义上传、`list-type="picture-card"`）

同站点的两个上传口行为不同，说明**取决于组件的 props 配置**，不是全局行为。

### 判断方法

```js
// 试探：赋值后立刻回读
const input = document.querySelectorAll('input[type=file]')[0];
const dt = new DataTransfer();
dt.items.add(file);
input.files = dt.files;
await new Promise(r => setTimeout(r, 500));
console.log(input.files.length);   // 0 → 组件拒绝了，止损
```

**`files.length === 0` → 立刻止损转人工，不要继续试。**

---

## 四、通用降级方案

### 方案 A：本地 CORS 服务 + fetch 构造 File

这是**最通用**的方案，适用于大多数接受程序化赋值的上传控件：

```js
// 1) 本地起服务（静态文件 + CORS 头）
//    python3 -c "..." 见 03-browser-automation.md
// 2) 页面内构造 File
const res  = await fetch('http://127.0.0.1:8731/file.pdf');
const buf  = await res.arrayBuffer();
const file = new File([buf], 'file.pdf', { type: 'application/pdf' });
const dt = new DataTransfer();
dt.items.add(file);
const input = document.querySelector('input[type=file]');
input.files = dt.files;
input.dispatchEvent(new Event('change', { bubbles: true }));
input.dispatchEvent(new Event('input',  { bubbles: true }));
```

> ⚠️ **必须给服务加 `Access-Control-Allow-Origin: *`**。
> HTTPS 页面 fetch `http://127.0.0.1` 时，没有 CORS 头会直接 `Failed to fetch`。
> 混合内容（HTTPS → HTTP localhost）在 Chrome 里是允许的，但 CORS 仍然强制。

### 方案 B：原生 `change` 事件（简单控件）

```js
// 某些实现直接监听 input 的 change
input.files = dt.files;
input.dispatchEvent(new Event('change', { bubbles: true }));
```

### 方案 C：交给人工

前两种都不行时，**不要恋战**：

```
【需你手填】个人照片上传
- 文件：<绝对路径>
- 位置：表单"个人形象"区块 → 点击上传
- 说明：该控件会校验文件是否来自真实用户选择，程序化注入被拒
```

---

## 五、踩坑实录

### 坑 1：`display:none` 的 file input

Element UI 的 file input 是 `display: none`，但**这不影响程序化赋值**。

真正的问题是组件内部的校验，不是可见性。所以：

- ❌ 花时间取消 `display:none`、改 `opacity`、加 `aria-label` —— 都是无用功
- ✅ 直接赋值 → 回读 `files.length` → 判断组件是否接受

### 坑 2：文件大小限制

**先看限制再传。**

实测：

| 场景 | 限制 | 结果 |
|---|---|---|
| 某招聘门户照片上传 | **1 MB** | 原图 1.44 MB 被拒 |
| 简历附件 | 20 MB | 正常 |
| 其他附件 | 100 MB | 正常 |

**处理**：超限时先压缩再传。

```python
# Python 压缩证件照到 1MB 以内
from PIL import Image
im = Image.open(src)
im.thumbnail((600, 856), Image.Resampling.LANCZOS)
im.save(dst, "JPEG", quality=88, optimize=True)
# 1050×1498 / 1.44MB → 600×856 / 67KB
```

### 坑 3：单页多文件输入框

页面可能有 2-3 个 `input[type=file]`（简历、附件、照片）。

**必须按 accept 属性区分**：

```js
const inputs = [...document.querySelectorAll('input[type=file]')];
inputs.forEach((f, i) => console.log(i, f.accept?.slice(0, 60)));
// 0: application/pdf,application/msword,...      ← 简历
// 1: video/x-ms-asf,audio/mpeg,image/jpeg,...     ← 附件（类目很杂）
// 2: image/jpg,image/jpeg,image/png,image/bmp     ← 照片
```

### 坑 4：`el-dialog` 遮挡

Element UI 的弹窗挂在 `body` 上，`z-index` 很高。

**排查**：如果点击没反应，先检查有没有未关闭的 dialog：

```js
document.querySelectorAll('.el-dialog__wrapper').forEach(d => {
  console.log(getComputedStyle(d).display, d.innerText.slice(0, 40));
});
```

关闭方式：点 `.el-dialog__headerbtn`（右上角 ×），或调用组件的 `close()`。
