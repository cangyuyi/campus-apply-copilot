# 北森 Beisen 网申表单

> 北森是中国大陆校招占有率最高的 ATS，覆盖大量国企、制造业、银行、半导体公司。
> 它有两套前端：**老版（`cmp_*`）** 和 **新版 phoenix（`phoenix-*`）**，填法不同但原理相通。

## 目录

- [一、快速识别](#一快速识别)
- [二、老版：cmp onChange 直调法](#二老版cmp-onchange-直调法)
- [三、新版 phoenix：从 React fiber 取选项](#三新版-phoenix从-react-fiber-取选项)
- [四、字段类型 → 控件行为对照表](#四字段类型--控件行为对照表)
- [五、BC_PopArea：籍贯 / 现居住地](#五bc_poparea籍贯--现居住地)
- [六、隐藏的"立即投递"按钮](#六隐藏的立即投递按钮)
- [七、登录页与岗位 ID](#七登录页与岗位-id)
- [八、踩坑实录](#八踩坑实录)

---

## 一、快速识别

```js
// 老版
document.querySelectorAll('[cmp_name]').length        // > 0 → 老版
// 新版
document.querySelectorAll('.form-item__control').length // > 0 → 新版 phoenix
// 招聘门户（hotjob.cn 等）
document.querySelectorAll('.positionItem').length
```

三种形态：

| 形态 | URL 特征 | 页面结构 |
|---|---|---|
| **老版校招** | `*.zhiye.com/campus/jobs` | 左侧锚点 + `cmp_` 组件 |
| **新版 phoenix** | `*.zhiye.com/campus/jobs` | `form-item` + `phoenix-*` 组件 |
| **招聘门户** | `*.hotjob.cn`、`*.zhiye.com/school` | 职位列表 + 独立表单页 |

---

## 二、老版：cmp onChange 直调法

**这是北森最强的解法**，能绕过两大顽疾：

- 穿梭面板/级联选择器点了"确定"但值不写入
- 日期控件拒绝一切程序化写入（React onChange / 原生 setter / 真实键入）

### 原理

北森老版的表单控件在 React fiber 上挂了 `cmp_name`、`onChange`、`cmp_data` 等 props。
**直接调用 `props.onChange({value, text})` 就等于完成了选择**，跳过所有 UI 交互。

### 通用取 props 函数

```js
function getCmpProps(cmpName) {
  // 方式一：元素上直接带 cmp_name 属性
  let el = document.querySelector(`[cmp_name="${cmpName}"]`);
  if (el) {
    const key = Object.keys(el).find(k => k.startsWith('__react'));
    let n = el[key], d = 0;
    while (n && d < 30) {
      if (n.memoizedProps?.cmp_name === cmpName) return n.memoizedProps;
      n = n.return; d++;
    }
  }
  // 方式二：新版——按 label 找 .form-item，从 .form-item__control 往上爬
  return null;
}

// 新版 phoenix
function getPhoenixProps(label) {
  const T = e => (typeof e.innerText === 'string' ? e.innerText.trim() : '');
  const f = [...document.querySelectorAll('.form-item')].find(x => {
    const t = x.querySelector('.form-item__title');
    return t && T(t).replace(/\n/g, '') === label;
  });
  if (!f) return null;
  const el = f.querySelector('.form-item__control');
  const key = Object.keys(el).find(k => k.startsWith('__react'));
  let n = el[key], d = 0;
  while (n && d < 30) {
    if (n.memoizedProps?.cmp_name) return n.memoizedProps;
    n = n.return; d++;
  }
  return null;
}
```

### 已验证的 cmp_name 速查表

| 字段 | cmp_name | 正确取值示例 |
|---|---|---|
| 民族 | `RecruitmentPersonProfile_Nation` | `{value:'1', text:'汉族'}` |
| 籍贯 | `RecruitmentPersonProfile_NativeArea` | `{value:'330199', text:'浙江省杭州市XX区'}` |
| 现居住地 | `RecruitmentPersonProfile_LivingArea` | 同上格式（省市县全路径） |
| 政治面貌 | `RecruitmentPersonProfile_Polity` | `{value:'3', text:'共青团员'}` |
| 婚否 | `RecruitmentPersonProfile_WedState` | `{value:'1', text:'未婚'}` |
| 学历 | `RecruitmentApplicantEducation_EducationLevel` | `{value:'1', text:'本科'}` |
| 成绩排名 | `RecruitmentApplicantEducation_MajorRank` | `{value:'2', text:'前10%'}` |
| 英语等级 | `RecruitmentPersonProfile_ExamCategory` | `{value:'1', text:'四级'}` |
| 意向工作地点 | `DeliveryIntentionCustom_WorkPlace` | `{value:'3301', text:'浙江省/杭州市'}` |
| 自定义日期 | `RecruitmentPersonProfile_extxxx_...`（`cmp_type=BC_DateTime`） | `{value:'2026-11-01', text:'2026-11-01'}` |

> ⚠️ 上表的 value 是**实战验证过的值**，但**不同公司配置的码表可能不同**。永远回读 `biz_data` 核对，不要盲信。

### 调用示例

```js
const props = getCmpProps('RecruitmentPersonProfile_Nation');
props.onChange({ value: '1', text: '汉族' });
```

### 调用后必须回读核对

```js
const bd = props.biz_data;
const obj = typeof bd === 'string' ? JSON.parse(bd) : bd;
console.log(obj.Nation);   // { text: '汉族', value: '1' }  ← 必须是这个
```

**为什么必须回读**：新一代 phoenix 表单里，`onChange({value:'01', text:'汉族'})` 会让字段**显示成"汉族"、校验也通过**，但 `biz_data` 里存的是 `"01"` —— 而正确值是 `"1"`。**显示层会用你传的 text 渲染，所以"显示对了"完全不代表"存储对了"。**

---

## 三、新版 phoenix：从 React fiber 取选项

新版 phoenix 表单的选项**不在 `cmp_data` 里**：

| props | 实际内容 | 能不能用来取选项 |
|---|---|---|
| `cmp_data` | **字段元数据**，如 `["民族","Nation",false]` | ❌ |
| `biz_data` | **表单当前值** | ❌ |
| `itemData` | **真正的选项表**（在虚拟列表的 fiber 上） | ✅ |

### 取选项的完整流程

```js
// 1) 先点开下拉（让其渲染出虚拟列表）
const sel = document.querySelector('.form-item .phoenix-select');
sel.click();
await new Promise(r => setTimeout(r, 1500));

// 2) 遍历虚拟列表项，往上爬 fiber 找 memoizedProps.itemData
let flat = null;
for (const it of document.querySelectorAll('.list-item-container')) {
  const k = Object.keys(it).find(x => x.startsWith('__react'));
  if (!k) continue;
  let n = it[k], d = 0;
  while (n && d < 15) {
    if (n.memoizedProps?.itemData) {
      const arr = n.memoizedProps.itemData;
      const list = Array.isArray(arr[0]) ? arr[0] : arr;   // 注意可能多包一层
      if (list?.[0]?.name) { flat = list; break; }
    }
    n = n.return; d++;
  }
  if (flat) break;
}
// flat = [{code:"1", name:"汉族", fullPathCode:"1", fullPathName:"汉族", children:[]}, ...]

// 3) 找到目标项，取 code
const hit = flat.find(o => o.name === '汉族');
// 4) 直调 onChange
getPhoenixProps('民族').onChange({ value: hit.code, text: hit.name });
```

### 选项数据结构

```json
{
  "code": "1",
  "name": "汉族",
  "fullPathCode": "1",
  "fullPathName": "汉族",
  "children": []
}
```

**用 `code` 传 value，用 `name` 传 text。**

### 实测的选项枚举

**民族**（33 项，顺序非字母序）：
`汉族=1, 回族=2, 畲族=3, 塔塔尔族, 阿昌族, 哈萨克族, 土家族, 景颇族, 哈尼族, 土族, 白族, 维吾尔族, 保安族, 赫哲族, 乌孜别克族, 基诺族, 布依族, 拉祜族, 锡伯族, 黎族, 东乡族, 蒙古族, 仫佬族, 达斡尔族, 藏族, 毛南族, 裕固族, 俄罗斯族, 德昂族, 傈僳族, 瑶族, 朝鲜族, 布朗族`

**成绩排名**：`前10% / 前30% / 前50% / 前70% / 其他`

**获奖类型**：`国家级 / 省部级 / 市级 / 区县级 / 国际性奖项 / 其他奖项（行业、协会等）`

**学历类型**：`海外及港澳台 / 统招全日制 / 统招非全日制 / 自考 / 其他`

**语言水平**：`母语/双语 / 无障碍商务沟通 / 日常会话 / 入门`

**是否接受调剂 / 是否有亲属任职 等 YN 类**：`是 / 否`

> 📌 **注意**：某些枚举**缺少常见值**。例如「获奖类型」没有「校级」这一档 —— 校级奖学金只能选「其他奖项（行业、协会等）」，或留空（选填时）。遇到这种情况如实选兜底项，**不要虚报成市级/省部级**。

---

## 四、字段类型 → 控件行为对照表

| `cmp_type` | 控件 | 交互方式 | 备注 |
|---|---|---|---|
| `BC_PopConstant` | 带搜索框的下拉 | 直调 onChange | 平铺常量表（如民族） |
| `BC_DropDownList` | 带搜索框的下拉 | 直调 onChange | 政治面貌/学历/语言类型/成绩排名 |
| `BC_RadioList` | `div.phoenix-radio-group`，**无 `input[type=radio]`** | 鼠标事件序列 | 婚否；**默认选中第一项**，要改必须点 `.phoenix-radio` |
| `BC_PopArea` | 省市县弹窗 | 见第五节 | 左勾选 + 右下钻 + 确定 |
| `BC_DateTime` | 年月/日期选择器 | 直调 onChange（`{value:'2026-11-01'}`） | 老版可用；新版走 phoenix 日期控件 |
| `BC_FileUploader` | 上传控件 | 见 `03-browser-automation.md` | 部分公司设成必填（如「本硕成绩单」） |

### Radio 组的特殊处理

**性别默认就是第一项（通常是"男"），一般不用动。**

要修改时，`input[type=radio]` 不存在，只有 `div.phoenix-radio`：

```js
const target = [...document.querySelectorAll('.phoenix-radio')]
  .find(r => r.innerText.trim() === '女');
const rect = target.getBoundingClientRect();
const o = { bubbles: true, cancelable: true,
            clientX: rect.x + rect.width / 2, clientY: rect.y + rect.height / 2, button: 0 };
['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']
  .forEach(t => target.dispatchEvent(new MouseEvent(t, o)));
```

---

## 五、BC_PopArea：籍贯 / 现居住地

**弹窗结构**：

```
┌──────────────────────────────────────┐
│  [🔍 搜索框]                          │
├────────────────┬─────────────────────┤
│ 搜索结果  1个   │                     │
│  ○ 全国        │   请在左侧选择地区    │
│  ○ 浙江省      │                     │
│                │                     │
│  已选地区 0/1   │       清空已选       │
├────────────────┴─────────────────────┤
│                      取消   确定      │
└──────────────────────────────────────┘
```

**操作步骤**：

1. 在搜索框输入省份简称（如「浙江」）
2. **点中"浙江省"前面的 radio 圆圈本身** —— 点文字不生效！
3. 点对了的标志：`已选地区` 从 `0/1` 变成 `1/1`
4. 点「确定」

```js
// 点 radio 圆圈（不是文字）
const textNode = [...document.querySelectorAll('*')]
  .find(e => e.children.length === 0 && e.innerText.trim() === '浙江省');
const radio = textNode.closest('label')?.querySelector('input[type=radio]')
           || textNode.previousElementSibling
           || textNode.parentElement.querySelector('input');
radio.click();
```

### 只允许选一级的情况

**有些公司把这个控件配置成只能选一级**（`已选地区` 显示 `1/1`，右侧不再出下级）。
这时选到省份即可，**不要硬填到区县**。

### 三级下钻的完整流程（允许选三级时）

```js
async function pickArea(province, city, district) {
  // 省份
  await clickRadio(province);
  await sleep(1500);
  // 城市（右侧面板出现）
  await clickRadio(city);
  await sleep(1500);
  // 区县
  await clickRadio(district);
  await sleep(1000);
  // 确定
  await clickText('确定');
}
```

---

## 六、隐藏的"立即投递"按钮

北森职位列表里，某些"立即投递"按钮带 `visibility: hidden`，鼠标悬停也点不到。

**解法：React `onClick` 直调**

```js
const btn = [...document.querySelectorAll('button')]
  .find(b => b.innerText.trim() === '立即投递');
if (btn) {
  const key = Object.keys(btn).find(k => k.startsWith('__react'));
  let n = btn[key], d = 0;
  while (n && d < 20) {
    const p = n.memoizedProps;
    if (p && typeof p.onClick === 'function') { p.onClick({ preventDefault(){}, stopPropagation(){} }); break; }
    n = n.return; d++;
  }
}
```

---

## 七、登录页与岗位 ID

### 登录页

北森门户多为**微信扫码登录**：先勾隐私协议再交给用户。

```js
await page.getByRole('checkbox').first().check();   // 勾隐私协议
// 然后把页面交给用户扫码
```

### 从职位列表提取岗位 ID

```js
// 老版列表
[...document.querySelectorAll('[class*="jobItem"], li')].map(el => ({
  title: el.innerText.split('\n')[0],
  id: el.querySelector('[data-id]')?.getAttribute('data-id'),
}))

// 新版（React props 上）
props.data.JobAdId
```

---

## 八、踩坑实录

### 坑 1：显示对了 ≠ 存储对了

**场景**：给「民族」传 `{value:'01', text:'汉族'}`，字段显示"汉族"，校验通过，`biz_data` 里存的是 `"01"`。

**正确值**：`"1"`（不带前导零）。

**教训**：直调 onChange 后**必须回读 `biz_data`**。显示层用你传的 text 渲染，它不会告诉你 value 是错的。

```js
// 回读模板
const ok = (() => {
  const bd = props.biz_data;
  const obj = typeof bd === 'string' ? JSON.parse(bd) : bd;
  return obj.Nation?.value === '1';
})();
```

### 坑 2：文本输入框不参与 innerText

**场景**：用 `form-item__control` 的 `innerText` 判断字段是否已填，结果**所有文本框都报"空"**。

**原因**：`<input>` 的 value 不进入 `innerText`。

**解法**：读 `input.value`，不要读 innerText。

```js
// ❌ 错
const filled = control.innerText.trim() !== '';
// ✅ 对
const input = control.querySelector('input');
const filled = input ? input.value !== '' : control.innerText.trim() !== '';
```

### 坑 3：必填判空要排除占位符

下拉框的"未填"状态显示的是占位文字（`请选择`），不是空字符串。

```js
const isEmpty = !input?.value && /^请选择|^请输入|^$/.test(control.innerText.replace(/\n/g, '').trim());
```

### 坑 4：解析器漏字段

北森自带的简历解析**经常漏**这些字段：

| 字段 | 漏的概率 | 说明 |
|---|---|---|
| 教育经历 → **专业名称** | 高 | 学校/学历/时间都带出来了，专业是空的 |
| 实习经历 → **所在部门** | 高 | 每条实习各漏一个 |
| 实习经历 → **工作职位** | 中 | 部分条目漏 |
| 项目经历 → **项目中职责** | 高 | 只填了"项目描述"，"项目中职责"空着 |
| **是否有工作/实习经历** | 中 | 每条记录各一个下拉，默认"请选择"，不设成"是"该条不生效 |
| **是否有项目经历** | 高 | 不设成"是"，「添加项目经历」按钮不出现 |

**核对清单**（填完必查）：

```js
[...document.querySelectorAll('.form-item')].forEach(f => {
  const t = f.querySelector('.form-item__title');
  const lab = t?.innerText.replace(/\n/g, '');
  const req = !!f.querySelector('.form-item__required');
  if (!req || !lab) return;
  const inp = f.querySelector('input'), ta = f.querySelector('textarea');
  const ctrl = f.querySelector('.form-item__control');
  const filled = ta ? ta.value.length > 0
               : (inp?.value ? true
               : (ctrl ? ctrl.innerText.replace(/\n/g,'').length > 0
                         && !/^请选择/.test(ctrl.innerText.replace(/\n/g,'')) : false));
  if (!filled) console.warn('缺:', lab);
});
```

### 坑 5：项目经历不在"工作经历"里

简历解析常把**创业项目**塞进「工作经历」区块，然后「没有工作经历」被勾上，导致项目两头不落。

**处理顺序**：
1. 先看「工作经历」是否被误勾"没有工作经历"
2. 把创业项目移到「项目经历」区块（重新添加）
3. 实习经历归「实习经历」

### 坑 6：file input 的 files 赋值后读回是空

某些北森上传控件会**立即消费掉** `input.files`。判断上传是否成功要看**页面上有没有出现文件名**，不要读 `input.files.length`。

```js
// ✅ 正确的成功判据
const uploaded = /\.pdf|\.docx?/i.test(document.body.innerText);
```
