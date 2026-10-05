#!/usr/bin/env python3
"""
投递台账读写与校验。

解决的核心问题：用固定行号写入导致的数据覆盖事故。
本模块的做法：
  1. 动态计算目标行号（只认"序号为整数"的行，避开统计区）
  2. 统计区按前缀查找更新，不写死行号
  3. ★ 每次写完断言序号连续性
  4. 进度跟踪表从主表重建，而不是增量维护

依赖：pip install openpyxl

用法：
    python3 tracking.py init   ~/applications.xlsx
    python3 tracking.py append ~/applications.xlsx            # 交互式录入
    python3 tracking.py verify ~/applications.xlsx
    python3 tracking.py rebuild ~/applications.xlsx ~/tracking.xlsx
"""

import sys
from copy import copy
from datetime import date

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
except ImportError:
    sys.exit("需要 openpyxl：pip install openpyxl")


SHEET_MAIN = "投递记录汇总"
HEADERS = ["序号", "公司名称", "行业", "投递岗位", "方向", "投递日期", "简历版本", "投递系统/渠道"]

# 跟进分桶阈值（天）
BUCKETS = [
    (21, "🔴", "建议跟进"),
    (14, "🟡", "重点关注"),
    (7,  "🟢", "正常等待"),
    (0,  "⚪", "刚投递"),
]


# ── 内部工具 ────────────────────────────────────────────────
def _last_data_row(ws, start=3):
    """★ 只认序号为整数的行，避开末尾统计区"""
    rows = [r for r in range(start, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)]
    return max(rows) if rows else start - 1


def _serial_numbers(ws, start=3):
    return [ws.cell(r, 1).value for r in range(start, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)]


def _bucket(days):
    for threshold, icon, label in BUCKETS:
        if days >= threshold:
            return icon, label
    return "⚪", "刚投递"


# ── 初始化 ──────────────────────────────────────────────────
def init(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET_MAIN

    ws.cell(1, 1, "投递记录汇总").font = Font(size=14, bold=True)
    ws.cell(2, 1, "数据由 tracking.py 维护 ｜ 序号必须连续").font = Font(size=9, color="666666")

    head_fill = PatternFill("solid", fgColor="1F3864")
    for c, h in enumerate(HEADERS, start=1):
        cell = ws.cell(3, c, h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center")

    # 列宽
    for c, w in enumerate([6, 22, 26, 40, 14, 13, 20, 44], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w

    # ★ 统计区独立成 sheet，避免被数据行吃掉
    st = wb.create_sheet("统计汇总")
    st.cell(1, 1, "总投递数").value = "总投递数"
    st.cell(2, 1, "AI产品经理方向").value = "AI产品经理方向"
    st.cell(3, 1, "大客户销售方向").value = "大客户销售方向"
    st.cell(1, 2, 0); st.cell(2, 2, 0); st.cell(3, 2, 0)
    st.column_dimensions["A"].width = 22
    st.column_dimensions["B"].width = 10

    wb.save(path)
    print(f"✓ 已初始化 {path}")
    print("  统计区放在独立的「统计汇总」sheet —— 这是避免数据覆盖的根本解法")


# ── 追加一条 ────────────────────────────────────────────────
def append(path, record):
    """record = dict(company, industry, position, direction, date, resume, channel)"""
    wb = openpyxl.load_workbook(path)
    ws = wb[SHEET_MAIN]

    last = _last_data_row(ws)
    row = last + 1
    new_no = (ws.cell(last, 1).value or 0) + 1 if last >= 3 else 1

    values = [new_no,
              record["company"], record.get("industry", ""), record["position"],
              record.get("direction", ""), record["date"],
              record.get("resume", ""), record.get("channel", "")]

    for c, v in enumerate(values, start=1):
        ws.cell(row, c, v)
        if last >= 3:
            ws.cell(row, c)._style = copy(ws.cell(last, c)._style)

    # 统计区按字段名查找更新（在独立 sheet 里）
    _refresh_stats(wb)

    wb.save(path)

    # ★ 写完立刻校验序号连续性
    issues = verify(path, quiet=True)
    if issues:
        print("⚠️  写入后校验失败：")
        for i in issues:
            print("   ", i)
        print("   请检查是否发生了行覆盖。")
        return new_no

    print(f"✓ 已追加 序号 {new_no}：{record['company']} · {record['position']}")
    return new_no


def _refresh_stats(wb):
    if "统计汇总" not in wb.sheetnames:
        return
    ws = wb[SHEET_MAIN]
    st = wb["统计汇总"]

    rows = [(ws.cell(r, 1).value, ws.cell(r, 5).value)
            for r in range(3, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)]

    counts = {}
    for _, direction in rows:
        counts[direction] = counts.get(direction, 0) + 1

    for r in range(1, st.max_row + 1):
        label = str(st.cell(r, 1).value or "")
        if label == "总投递数":
            st.cell(r, 2, len(rows))
        elif label.endswith("方向"):
            key = label.replace("方向", "")
            st.cell(r, 2, counts.get(key, 0))


# ── 校验 ────────────────────────────────────────────────────
def verify(path, quiet=False):
    """检查序号连续性 —— 这一步能立刻发现覆盖事故"""
    wb = openpyxl.load_workbook(path)
    ws = wb[SHEET_MAIN]
    nums = _serial_numbers(ws)

    issues = []
    if nums != list(range(1, len(nums) + 1)):
        expected = set(range(1, len(nums) + 1))
        missing = sorted(expected - set(nums))
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        if missing:
            issues.append(f"序号缺失：{missing}")
        if dupes:
            issues.append(f"序号重复：{dupes}")
        if not missing and not dupes:
            issues.append(f"序号非连续或非递增：{nums}")

    if not quiet:
        if not nums:
            print("（暂无记录）")
        else:
            print(f"共 {len(nums)} 条记录")
        if issues:
            for i in issues:
                print("✗", i)
        elif nums:
            print("✓ 序号 1..%d 连续，无缺口、无重复" % len(nums))
    return issues


# ── 重建进度跟踪表 ──────────────────────────────────────────
def rebuild(src, dst):
    """从主表重建进度跟踪表（不从旧表增量维护，避免两表不一致）"""
    wb = openpyxl.load_workbook(src)
    ws = wb[SHEET_MAIN]

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
            y, m, dd = map(int, str(d).split("-")[:3])
            waited = (today - date(y, m, dd)).days
        except Exception:
            continue

        icon, label = _bucket(waited)
        rows.append([no, ws.cell(r, 2).value, ws.cell(r, 4).value, ws.cell(r, 5).value,
                     d, waited, ws.cell(r, 8).value, "已投递·待回音",
                     f"{icon} {label}", ws.cell(r, 8).value])

    rows.sort(key=lambda x: -x[5])

    wb2 = openpyxl.Workbook()
    t = wb2.active
    t.title = "投递进度跟踪"
    head = ["序号", "公司名称", "投递岗位", "方向", "投递日期",
            "已等待(天)", "投递渠道/平台", "当前状态", "跟进建议", "备注"]
    for c, h in enumerate(head, start=1):
        t.cell(1, c, h).font = Font(bold=True)
    for i, row in enumerate(rows):
        for c, v in enumerate(row, start=1):
            t.cell(2 + i, c, v)

    # 分桶统计
    t2 = wb2.create_sheet("本周跟进清单")
    t2.cell(1, 1, "本周该盯谁（按等待天数排序）").font = Font(bold=True, size=13)
    t2.cell(2, 1, f"数据截止 {today.isoformat()} ｜ 共 {len(rows)} 家").font = Font(size=9, color="666666")

    rr = 4
    for threshold, icon, label in BUCKETS:
        group = [x for x in rows if _bucket(x[5]) == (icon, label)]
        if not group:
            continue
        t2.cell(rr, 1, f"—— {icon} {label}（{len(group)} 家）——").font = Font(bold=True)
        rr += 1
        for g in group:
            t2.cell(rr, 1, g[1]); t2.cell(rr, 2, g[2]); t2.cell(rr, 3, g[3])
            t2.cell(rr, 4, g[4]); t2.cell(rr, 5, g[5]); t2.cell(rr, 6, g[8])
            rr += 1
        rr += 1

    wb2.save(dst)
    print(f"✓ 已重建 {dst}（{len(rows)} 条）")
    for threshold, icon, label in BUCKETS:
        n = len([x for x in rows if _bucket(x[5]) == (icon, label)])
        if n:
            print(f"   {icon} {label}: {n} 家")


# ── CLI ─────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd, path = sys.argv[1], sys.argv[2]

    if cmd == "init":
        init(path)
    elif cmd == "verify":
        sys.exit(1 if verify(path) else 0)
    elif cmd == "append":
        rec = {
            "company":  input("公司名称: ").strip(),
            "industry": input("行业（可空）: ").strip(),
            "position": input("投递岗位（含地点）: ").strip(),
            "direction": input("方向（如 AI产品经理）: ").strip(),
            "date":     input(f"投递日期 [{date.today().isoformat()}]: ").strip() or date.today().isoformat(),
            "resume":   input("简历版本: ").strip(),
            "channel":  input("投递系统/渠道（含 candidateId）: ").strip(),
        }
        append(path, rec)
    elif cmd == "rebuild":
        if len(sys.argv) < 4:
            sys.exit("用法: tracking.py rebuild <主表> <输出表>")
        rebuild(path, sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
