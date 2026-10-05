# 投递台账设计

> 投到 30 家以上之后，"我投了哪些、投了多久、该催谁"就变成了一个数据处理问题。
> 这一篇是台账结构设计，以及**真实踩过的数据事故**。

## 目录

- [一、为什么需要台账](#一为什么需要台账)
- [二、三张表的结构](#二三张表的结构)
- [三、⛔ 行号冲突：一次真实的数据覆盖事故](#三-行号冲突一次真实的数据覆盖事故)
- [四、写入纪律](#四写入纪律)
- [五、进度分桶与跟进节奏](#五进度分桶与跟进节奏)
- [六、完整实现代码](#六完整实现代码)

---

## 一、为什么需要台账

校招的反馈周期是 **2–4 周**，投到几十家之后：

- 记不清哪家投过、投的哪个岗位
- 不知道哪家已经等太久该催
- 笔试/面试邀请来了，对不上是哪家的
- 同一家公司可能投过多个岗位，混在一起

**台账不是"记录"，是"决策依据"。** 它的价值在于回答三个问题：

1. 我投了多少家？方向分布对不对？
2. 哪几家该催了？
3. 下一步该盯谁？

---

## 二、三张表的结构

### 表 1：投递记录汇总（主表）

一行一家公司，投递动作发生时追加。

| 列 | 字段 | 说明 |
|---|---|---|
| 1 | 序号 | **连续整数，1..N**，用于交叉引用 |
| 2 | 公司名称 | |
| 3 | 行业 | 用于分析方向分布 |
| 4 | 投递岗位 | **完整岗位名 + 地点标注** |
| 5 | 方向 | 归一化标签（如 `AI产品经理` / `大客户销售`） |
| 6 | 投递日期 | `YYYY-MM-DD` |
| 7 | 简历版本 | 用了哪份简历 |
| 8 | 投递系统/渠道 | ATS 平台 + 登录方式 + candidateId |

**末尾附统计区**：

```
统计汇总
总投递数：NN 家
AI产品经理方向：NN 家
大客户销售方向：NN 家
```

### 表 2：投递进度跟踪（按等待天数排序）

从主表派生，按 `已等待天数` 降序。

| 列 | 字段 |
|---|---|
| 1 | 序号 |
| 2 | 公司名称 |
| 3 | 投递岗位 |
| 4 | 方向 |
| 5 | 投递日期 |
| 6 | 已等待(天) |
| 7 | 投递渠道/平台 |
| 8 | 当前状态 |
| 9 | 跟进建议 |
| 10 | 备注 |

### 表 3：本周跟进清单（分桶）

从表 2 派生，按等待天数分四档：

| 分桶 | 等待天数 | 建议动作 |
|---|---|---|
| 🔴 | ≥ 21 天 | **建议跟进** |
| 🟡 | 14–20 天 | 重点关注 |
| 🟢 | 7–13 天 | 正常等待 |
| ⚪ | < 7 天 | 刚投递 |

每个桶带家数标注（如 `—— 🟡 14-20天：重点关注（13 家）——`），方便一眼看出压力分布。

### 表 4：总表（候选池）

如果有一张包含几百家公司的候选清单，加一列 **投递进度**，把每家公司的处理结论写进去。

**这一列是台账里信息密度最高的地方**，因为它记录了"为什么没投"：

```
已投递 2026-10-02｜岗位：AI产品经理-导购方向(杭州)｜简历：AI产品经理简历｜当前状态：流程中
已站点实查 2026-10-02｜杭州+产品=0，其AI产品经理仅北京 → 跳过
未核查·学历不符｜公告要求硕士/博士，本科不可投 → 跳过（文本判定）
未核查·用户指定｜用户明确「该系先不投」→ 跳过（用户决策）
未核查·入口缺失｜仅有微信公众号公告，无公开网申入口 → 需人工确认
```

**给每家公司一个明确结论，不留空。** 空格意味着"没处理"，而"没处理"和"已排除"是完全不同的状态。

---

## 三、⛔ 行号冲突：一次真实的数据覆盖事故

### 事故经过

**背景**：主表有 52 行数据（序号 1–52），末尾 3 行是统计区。

```
行 3..54   序号 1..52
行 55       （空）
行 56..59   统计汇总 / 总投递数 / AI方向 / 销售方向
```

**第一次写入**：新增序号 53，写在第 55 行。

**第二次写入**：新增序号 54。此时"最后一个数据行"的查找逻辑有问题，**又算了 55**，于是：

```
行 55 ← 序号 54（覆盖了序号 53 的数据）
行 56 ← 序号 55
行 57 ← 序号 56（覆盖了统计区第一行）
```

**结果**：

- 序号 53 的记录**永久丢失**
- 统计区被顶掉一行
- 序号序列出现缺口

### 根因

两个错误叠加：

1. **用固定行号写入**（`row = 55`），而不是"当前最后一行 + 1"
2. **统计区在数据区下方**，数据行增长会吃掉统计区

### 正确的写法

```python
# ✅ 动态找最后一个数据行（只认序号是整数的行）
last = max(r for r in range(3, ws.max_row + 1)
           if isinstance(ws.cell(r, 1).value, int))
row = last + 1
```

### 更安全的写法：数据区与统计区分离

**根本解法**：不要把统计区放在同一张 sheet 的下方。

| 方案 | 做法 |
|---|---|
| A | 统计区放到**独立的 sheet** |
| B | 统计区与数据区之间**留 5 行缓冲**，写入前检测 |
| C | 用 Excel **表格对象**（ListObject），统计写在表格外 |

### 每次写完必须校验

```python
nums = [ws.cell(r, 1).value for r in range(3, ws.max_row + 1)
        if isinstance(ws.cell(r, 1).value, int)]
assert nums == list(range(1, len(nums) + 1)), f'序号不连续: {nums}'
```

**这一步能立刻发现覆盖事故**，而不是等十几家之后才发现。

### 事故的教训

> **写数据前先算行号，写完立即校验序号连续性。**

另外：**每次写表前先备份。**

```bash
cp "总表.xlsx" "/tmp/bak_$(date +%s)_总表.xlsx"
```

出事故时能回滚，比事后修复便宜得多。

---

## 四、写入纪律

### 1. 一家投完立即记，不要批量补记

批量补记的问题：

- 会漏（记不清哪家投了什么岗位）
- 会记错（candidateId、岗位全名容易张冠李戴）
- 补记时段的心里负担高，容易拖延

**"投完一家 → 记一家"** 是最省心的节奏。

### 2. 记录必须带可复核的标识

```python
{
  "公司": "某公司",
  "岗位": "AI产品经理（杭州）",
  "日期": "2026-10-02",
  "渠道": "自建网申 campus.example.com（candidateId=810686285）",
  "备注": "岗位要求「Prompt/Agent/RAG + 手搓 demo 经验」，与项目经历高度对口"
}
```

**candidateId / jobId 一定要记** —— 三个月后要查进度，没有这个就找不回来了。

### 3. 备注写"为什么"，不写"是什么"

| 写法 | 评价 |
|---|---|
| ❌ `已投递` | 系统里有的是，不用你记 |
| ❌ `AI产品经理` | 岗位栏已经有了 |
| ✅ `岗位要求「能独立搭建 Agent/智能工作流」，与我的外呼 Agent 经历对口` | 面试准备时这就是弹药 |
| ✅ `该项目仅可投 1 个职位，已锁定` | 避免重复尝试 |

### 4. 跳过也要记原因

```
已核查 2026-10-02｜杭州+产品=0，其AI产品经理仅北京 → 跳过
未核查·学历不符｜公告要求硕士，本科不可投 → 跳过（文本判定）
未核查·用户指定｜用户明确不投 → 跳过（用户决策）
```

**"跳过原因"是可复用的资产**：下次再看到这家公司，不用重新查一遍。

---

## 五、进度分桶与跟进节奏

### 校招的反馈周期

| 阶段 | 典型时长 |
|---|---|
| 简历筛选 | 3–14 天 |
| 笔试通知 | 1–3 周 |
| 面试通知 | 2–4 周 |
| 全程 | 1–2 个月 |

### 分桶阈值

```
🔴 ≥ 21 天   建议跟进
🟡 14–20 天  重点关注
🟢 7–13 天   正常等待
⚪ < 7 天    刚投递
```

**为什么是 21 天**：超过三周没有回音，要么是流程慢了，要么是简历被漏看了。这时候主动跟进（邮件/招聘平台留言/找内推）的边际收益最高。

### 跟进不等于催

| 好的跟进 | 差的跟进 |
|---|---|
| 补充新信息（新项目、新成绩） | "请问我的简历看了吗" |
| 表达持续的兴趣 + 具体理由 | 群发模板 |
| 通过内推人/HR 渠道 | 反复轰炸同一渠道 |

### 台账里要留"跟进记录"

在备注列追加，不要新开一列：

```
2026-10-02 已投递｜岗位：AI产品经理
2026-10-20 已邮件跟进一次（附作品集链接）
```

---

## 六、完整实现代码

```python
import openpyxl
from copy import copy
from datetime import date

def append_application(workbook_path, record):
    """
    record = {
      'company': str, 'industry': str, 'position': str, 'direction': str,
      'date': str, 'resume': str, 'channel': str,
    }
    """
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb['投递记录汇总']

    # 1) 动态找最后一个数据行（只认序号为整数的行）
    last = max(r for r in range(3, ws.max_row + 1)
               if isinstance(ws.cell(r, 1).value, int))
    row = last + 1

    # 2) 序号 = 上一行序号 + 1
    new_no = ws.cell(last, 1).value + 1

    # 3) 写入，并复制上一行的样式
    values = [new_no, record['company'], record['industry'], record['position'],
              record['direction'], record['date'], record['resume'], record['channel']]
    for c, v in enumerate(values, start=1):
        ws.cell(row, c, v)
        ws.cell(row, c)._style = copy(ws.cell(last, c)._style)

    # 4) 更新统计区（按前缀查找，不写死行号）
    for r in range(1, ws.max_row + 1):
        v = str(ws.cell(r, 1).value or '')
        if v.startswith('总投递数'):
            ws.cell(r, 1, f'总投递数：{new_no} 家')
        elif v.startswith('AI产品经理方向'):
            n = sum(1 for rr in range(3, row + 1)
                    if ws.cell(rr, 5).value == 'AI产品经理')
            ws.cell(r, 1, f'AI产品经理方向：{n} 家')

    wb.save(workbook_path)

    # 5) ★ 校验序号连续性（必须）
    wb2 = openpyxl.load_workbook(workbook_path)
    w2 = wb2['投递记录汇总']
    nums = [w2.cell(r, 1).value for r in range(3, w2.max_row + 1)
            if isinstance(w2.cell(r, 1).value, int)]
    assert nums == list(range(1, len(nums) + 1)), f'序号不连续: {nums}'

    return new_no


def rebuild_tracking(workbook_path, tracking_path):
    """从主表重建进度跟踪表"""
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb['投递记录汇总']

    today = date.today()
    rows = []
    for r in range(3, ws.max_row + 1):
        no = ws.cell(r, 1).value
        if not isinstance(no, int):
            continue
        d = ws.cell(r, 6).value
        if not d:
            continue
        try:
            y, m, dd = map(int, str(d).split('-'))
            waited = (today - date(y, m, dd)).days
        except Exception:
            continue
        if waited >= 21:   bucket, advice = '🔴', '建议跟进'
        elif waited >= 14: bucket, advice = '🟡', '重点关注'
        elif waited >= 7:  bucket, advice = '🟢', '正常等待'
        else:              bucket, advice = '⚪', '刚投递'
        rows.append([no, ws.cell(r, 2).value, ws.cell(r, 4).value, ws.cell(r, 5).value,
                     d, waited, ws.cell(r, 8).value, '已投递·待回音',
                     f'{bucket} {advice}', ws.cell(r, 8).value])

    rows.sort(key=lambda x: -x[5])

    wb2 = openpyxl.load_workbook(tracking_path)
    t = wb2['投递进度跟踪']
    # 清空数据区
    for r in range(t.max_row, 3, -1):
        t.delete_rows(r)
    for i, row in enumerate(rows):
        for c, v in enumerate(row, start=1):
            t.cell(4 + i, c, v)
    wb2.save(tracking_path)
    return len(rows)
```

**关键点**：

1. `max(r for r in ... if isinstance(ws.cell(r,1).value, int))` —— 只认序号是整数的行，避开统计区
2. 统计区按**前缀查找**更新，不写死行号
3. 写完**断言序号连续性**
4. 进度跟踪表**从主表重建**，而不是增量维护（避免两表不一致）
