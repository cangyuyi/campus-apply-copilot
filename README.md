# Campus Apply Copilot

> 让 AI Agent 替你完成校招网申的重复劳动 —— 一套经过 **60+ 家真实投递** 验证的人机协作 SOP

中国大陆的秋招网申是一件高度重复、平台极其碎片化的事：一家公司一套系统，同一份简历要在十几个不同框架的表单里重填一遍。一个求职者投 60 家，可能要填 2000+ 个字段。

这个项目把我用 AI Agent 完成 60+ 家投递的全过程**沉淀成一套可复用的方法论 + 平台知识库 + 工程技巧**。它不是"自动投递脚本"，而是一套**人机分工协议**：Agent 负责所有确定性劳动（找岗、核岗、填表、校验、记账），人只做两件机器做不了的事 —— **登录**和**按下最终提交**。

---

## 核心设计：为什么是"人机协作"而不是"全自动"

做这个项目之前，先想清楚三件事：

**第一，登录墙是设计约束，不是待解决的 bug。**
绝大多数招聘平台用短信验证码、微信扫码、图形验证码来确认"屏幕前是一个真人"。绕过它们既违反服务条款，也会让账号承担风险。**正确的做法是把登录作为显式的交接点**：Agent 把页面准备好、把手机号预填好、把协议勾好，然后把控制权交出去，等用户登录完成再继续。

**第二，最终提交必须由人按下。**
投递是不可逆的对外行为。Agent 可以在提交前做完所有校验、把预览页准备好，但"确认提交"这一下必须由本人执行 —— 这是对求职者本人的保护。

**第三，Agent 的价值在"确定性劳动"，不在"代替决策"。**
筛选规则、字段映射、平台适配、异常止损 —— 这些是确定性的，可以自动化。但"这家公司值不值得投""这个岗位是不是真的合适"仍然是人的判断。所以这套 SOP 里，Agent 输出的永远是可核查的**证据**（岗位原文、城市、学历要求、当前进度），而不是替用户做的结论。

---

## 它能做什么

| 环节 | Agent 负责 | 人负责 |
|---|---|---|
| **筛岗** | 按硬性规则过滤（学历、城市、岗位方向），逐家到站点核实 | 定方向偏好 |
| **登录** | 预填手机号/证件号、勾选协议、把页面准备好 | **输入验证码 / 扫码** |
| **填表** | 上传简历触发解析、补齐缺项、处理各类组件、长文本用原文 | 抽查关键字段 |
| **校验** | 触发表单校验、收集缺项清单、逐项修复 | — |
| **记账** | 写入投递台账、更新进度、生成跟进分桶 | — |
| **提交** | 完成预览、确认无缺项 | **按下提交** |

## 覆盖的平台

| 平台 | 识别特征 | 文档 |
|---|---|---|
| **北森 Beisen** | `*.zhiye.com`、`phoenix-*` / `cmp_*` 类名、`apply-field` | [docs](docs/02-platforms/beisen.md) |
| **Moka** | `app.mokahr.com`、`sd-*` 类名 | [docs](docs/02-platforms/moka.md) |
| **飞书招聘 ATS** | `*.jobs.feishu.cn`、`atsx-*` 类名 | [docs](docs/02-platforms/feishu.md) |
| **Element UI 系** | `el-*` 类名（多数自建站与老版门户） | [docs](docs/02-platforms/element-ui.md) |
| **招聘门户（51job/hotjob/智联等）** | `hotjob.cn`、`51job.com`、`zhaopin.com` | [docs](docs/02-platforms/custom-sites.md) |
| **企业自建站** | 各家自研，组件风格各异 | [docs](docs/02-platforms/custom-sites.md) |

## 快速开始

```bash
git clone https://github.com/cangyuyi/campus-apply-copilot.git
cd campus-apply-copilot
cp templates/candidate-profile.example.json ~/candidate-profile.json
# 编辑 ~/candidate-profile.json，填入你的信息与简历路径
```

然后阅读 [`docs/00-workflow.md`](docs/00-workflow.md)，按 Runbook 逐阶段执行。

### 可直接运行的工具

`scripts/` 里是文档中反复用到的三段代码，做成了开箱即用：

```bash
# ① 上传用的本地服务（解决内置浏览器不支持文件选择器）
python3 scripts/cors-upload-server.py --dir ~/resumes
# → serving ... at http://127.0.0.1:8731/

# ② 中文 PDF 排版引擎（绕过 PyMuPDF 的三个静默失败）
python3 scripts/cjk_pdf.py          # 生成 demo.pdf 并自动做溢出检查

# ③ 投递台账读写与校验（含序号连续性断言）
python3 scripts/tracking.py init    ~/applications.xlsx
python3 scripts/tracking.py append  ~/applications.xlsx
python3 scripts/tracking.py verify  ~/applications.xlsx
python3 scripts/tracking.py rebuild ~/applications.xlsx ~/tracking.xlsx
```

**提交前必跑**脱敏检查：

```bash
bash scripts/check-desensitize.sh .
```

它会扫手机号、身份证、邮箱、本地路径和未替换的占位符，有命中就返回非零退出码。

## 目录结构

```
.
├── README.md
├── CONTRIBUTING.md                # 贡献规范 + 脱敏要求
├── LICENSE                        # MIT
├── .github/ISSUE_TEMPLATE/        # 平台问题 / 数据事故 两个模板
├── scripts/                       # 可直接运行的工具
│   ├── cors-upload-server.py      # 上传用的本地 CORS 文件服务
│   ├── cjk_pdf.py                 # 中文 PDF 排版引擎（含 demo 与验收检查）
│   ├── tracking.py                # 投递台账读写 / 校验 / 重建
│   └── check-desensitize.sh       # 提交前的脱敏扫描
├── docs/
│   ├── 00-workflow.md             # 端到端 Runbook（阶段 0-7，标注 🤖/👤）
│   ├── 01-methodology.md          # 核心方法论：筛岗纪律、校验驱动、止损红线
│   ├── 02-platforms/              # 平台知识库（按 ATS 家族分类）
│   │   ├── README.md              # 平台识别速查表 + 七层降级链路
│   │   ├── beisen.md              # 北森：cmp 直调法 / 新版 fiber 取选项
│   │   ├── moka.md                # Moka：禁止 setter 污染 store
│   │   ├── feishu.md              # 飞书 ATS：period picker / 虚拟列表陷阱
│   │   ├── element-ui.md          # Element UI：el-upload 等
│   │   └── custom-sites.md        # 企业自建站（6 个实测案例）
│   ├── 03-browser-automation.md   # 浏览器自动化工程技巧（含文件上传方案）
│   ├── 04-data-management.md      # 投递台账设计（含真实踩过的数据事故）
│   └── 05-document-generation.md  # 简历/作品集 PDF 生成的静默失败
└── templates/
    ├── candidate-profile.example.json
    ├── application-log.example.csv
    └── open-ended-questions.md    # 开放性问题素材库（六类题型拆解）
```

## 三条最有价值的经验

如果只读三段，读这三段：

### 1. 校验驱动法：不要猜缺什么，让表单告诉你

填完一版后，直接点「预览并提交」（**不要点最终的"确认提交"**）。真实校验会跑出所有红字，得到一份精确的缺项清单。这比自己对着 DOM 猜快一个数量级，而且不会漏。

```js
// 触发校验后收集全部红字
[...document.querySelectorAll('*')]
  .filter(e => e.innerText?.trim() === '必填项未填写')
  .map(e => { /* 向上找最近的字段容器，取标题 */ })
```

### 2. 止损红线：单个字段试 4 次就转人工

网申里总有几个字段是程序化填不进去的（日期穿梭框、级联选择器、只读输入）。**试到第 4 种方法就停下**，把「字段名 + 应该填什么」整理成清单交给用户手填。继续死磕的期望收益是负的 —— 你在一个字段上花 10 分钟，用户 10 秒就填完了。

### 3. 文件上传的可行方案

内置浏览器通常不支持文件选择器。可行做法是在本地起一个带 CORS 头的静态服务，然后在页面里构造 `File` 对象注入：

```js
// 本地服务（必须返回 Access-Control-Allow-Origin: *，否则 HTTPS 页面 fetch 会 Failed to fetch）
const res  = await fetch('http://127.0.0.1:8731/resume.pdf');
const buf  = await res.arrayBuffer();
const file = new File([buf], 'resume.pdf', { type: 'application/pdf' });

const dt = new DataTransfer();
dt.items.add(file);
const input = document.querySelector('input[type=file]');
input.files = dt.files;
input.dispatchEvent(new Event('change', { bubbles: true }));
```

大多数平台的简历解析器会自动跑起来，把教育经历、实习经历、项目经历一次性填好 —— 这是整个流程里性价比最高的一步。

> ⚠️ 传完务必逐字段核对解析结果。解析器最常见的错误是：**专业识别错**、**创业项目塞进"工作经历"**、**职位名混进部门名**、**实习时间段串行**。

## 适用边界

- ✅ 适用于：中国大陆校招/社招网申，主流 ATS 平台
- ✅ 适用于：批量投递时的重复劳动消除
- ❌ 不适用于：绕过验证码、模拟登录、批量海投（本项目**明确不做**，见下）
- ❌ 不适用于：需要人工判断的岗位匹配决策

### 明确不做的事

- **不绕过任何验证码或登录验证** —— 登录是显式的人工交接点
- **不代按最终提交键** —— 投递不可逆，必须本人确认
- **不批量海投** —— 定位是"把该投的投好"，不是"投得多"
- **不伪造任何信息** —— 所有字段严格来自用户提供的资料与简历原文

## 数据安全

`candidate-profile.json` 包含身份证号、手机号等敏感字段，**已在 `.gitignore` 中排除**，请勿提交。仓库内的所有示例数据均为脱敏占位符。

## License

[MIT](LICENSE)

---

**这个项目是怎么来的**：用 AI Agent 完成 60+ 家校招投递的过程中，把每一步踩过的坑、每个平台的组件解法、每次翻车的事后复盘，都写回了一套持续迭代的知识库里。现在把它整理成公开版本，希望能帮到同样在秋招里刷表单的人。
