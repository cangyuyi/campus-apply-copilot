#!/usr/bin/env python3
"""
生成 README 与文档用示意图。

设计取舍：不用真实招聘站点的截图 —— 截图会带第三方品牌 UI 和潜在个人信息，
且无法标注关键结构。示意图可以把「容器 vs 单字段」「显示层 vs 真实值」这类
dom 细节直接画出来，教学价值更高，且完全原创、可版本控制。

输出：assets/*.png（2x 分辨率）

    python3 scripts/make-diagrams.py
"""

import os
import fitz

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FN = "cjk"
F = fitz.Font(fontfile=FONT)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# ── 调色板 ──────────────────────────────────────────────────
INK = (0.11, 0.13, 0.17)
MUTED = (0.45, 0.48, 0.53)
FAINT = (0.82, 0.85, 0.88)
BG = (0.97, 0.98, 0.99)

BLUE = (0.15, 0.35, 0.68)
BLUE_BG = (0.90, 0.94, 0.99)
GREEN = (0.13, 0.52, 0.36)
GREEN_BG = (0.90, 0.96, 0.92)
AMBER = (0.72, 0.48, 0.06)
AMBER_BG = (0.99, 0.95, 0.87)
RED = (0.72, 0.20, 0.18)
RED_BG = (0.99, 0.91, 0.90)
PURPLE = (0.42, 0.25, 0.62)
PURPLE_BG = (0.95, 0.92, 0.99)

CJK_RANGES = [
    (0x2E80, 0x303F), (0x3040, 0x33FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x20000, 0x2FA1F),
]
CLOSE = "、。，；：！？）》」』】”’%,.;:!?)]}"


def _cjk(ch):
    o = ord(ch)
    return any(a <= o <= b for a, b in CJK_RANGES)


def wrap(text, size, width):
    out = []
    for para in str(text).split("\n"):
        cur, i, n = "", 0, len(para)
        while i < n:
            ch = para[i]
            if ch == " ":
                tok, i = " ", i + 1
            elif _cjk(ch):
                tok, i = ch, i + 1
            else:
                j = i
                while j < n and not _cjk(para[j]) and para[j] != " ":
                    j += 1
                tok, i = para[i:j], j
            if not cur or F.text_length(cur + tok, size) <= width or tok in CLOSE:
                cur += tok
            else:
                out.append(cur.rstrip())
                cur = tok if tok != " " else ""
        out.append(cur.rstrip())
    return out


# ── 绘图原语 ────────────────────────────────────────────────
class Canvas:
    def __init__(self, w, h, bg=(1, 1, 1)):
        self.doc = fitz.open()
        self.p = self.doc.new_page(width=w, height=h)
        self.p.insert_font(fontname=FN, fontfile=FONT)
        self.W, self.H = w, h
        self.p.draw_rect(fitz.Rect(0, 0, w, h), color=bg, fill=bg)

    def text(self, x, y, s, size=10, color=INK, align="left", width=None, leading=1.5):
        """align: left | center | right；width 给定时用于对齐计算和自动换行"""
        lines = wrap(s, size, width) if width else [str(s)]
        for ln in lines:
            w = F.text_length(ln, size)
            dx = 0
            if align == "center" and width:
                dx = (width - w) / 2
            elif align == "right" and width:
                dx = width - w
            self.p.insert_text(fitz.Point(x + dx, y + size * 0.86), ln,
                               fontname=FN, fontsize=size, color=color)
            y += size * leading
        return y

    def box(self, x, y, w, h, fill=None, stroke=None, radius=0, lw=0.8, dash=None):
        r = fitz.Rect(x, y, x + w, y + h)
        if radius:
            shape = self.p.new_shape()
            shape.draw_rect(r) if not radius else None
            if radius:
                # 用圆角矩形：fitz 支持 draw_rect 带 radius（通过 Shape）
                shape = self.p.new_shape()
                shape.draw_rect(r)
            shape.finish(color=stroke, fill=fill, width=lw, dashes=dash)
            shape.commit()
        else:
            self.p.draw_rect(r, color=stroke, fill=fill, width=lw, dashes=dash)
        return r

    def round_rect(self, x, y, w, h, fill=None, stroke=None, lw=0.8, dash=None):
        """draw_rect 支持圆角（通过 radius 参数在 Shape 上不可用，这里手动画）"""
        s = self.p.new_shape()
        s.draw_rect(fitz.Rect(x, y, x + w, y + h))
        s.finish(color=stroke, fill=fill, width=lw, dashes=dash)
        s.commit()

    def arrow(self, x1, y1, x2, y2, color=MUTED, lw=1.0, head=5):
        self.p.draw_line(fitz.Point(x1, y1), fitz.Point(x2, y2), color=color, width=lw)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        for da in (2.6, -2.6):
            self.p.draw_line(
                fitz.Point(x2, y2),
                fitz.Point(x2 + head * math.cos(ang + da), y2 + head * math.sin(ang + da)),
                color=color, width=lw)

    def save(self, name, scale=2):
        path = os.path.join(OUT_DIR, name)
        mat = fitz.Matrix(scale, scale)
        pix = self.p.get_pixmap(matrix=mat)
        pix.save(path)
        print(f"  ✓ {name}  ({self.W:.0f}×{self.H:.0f} @{scale}x, "
              f"{os.path.getsize(path)/1024:.0f} KB)")
        return path


# ════════════════════════════════════════════════════════════
# 图 1：端到端工作流（人机分工）
# ════════════════════════════════════════════════════════════
def diagram_workflow():
    W, H = 980, 720
    c = Canvas(W, H)

    c.text(40, 34, "校招网申工作流：人机分工", size=19, color=INK)
    c.text(40, 62, "Agent 做确定性劳动，人只做两件事 —— 登录，以及按下最终提交", size=10.5, color=MUTED)

    # 表头：三条泳道
    lanes = [
        ("A", "Agent", BLUE, BLUE_BG, "筛选 · 填表 · 校验 · 记账"),
        ("人", "人", AMBER, AMBER_BG, "登录 · 最终提交 · 手填兜底"),
        ("协", "协作", PURPLE, PURPLE_BG, "定方向 · 答开放题 · 核对关键字段"),
    ]
    lx, lw = 40, 250
    for i, (icon, name, col, bg, desc) in enumerate(lanes):
        y = 92 + i * 58
        c.round_rect(lx, y, lw, 48, fill=bg, stroke=col)
        c.round_rect(lx + 14, y + 13, 22, 22, fill=col)
        c.text(lx + 14, y + 17, icon, size=11, color=(1, 1, 1), align="center", width=22)
        c.text(lx + 46, y + 16, name, size=12, color=col)
        c.text(lx + 46, y + 34, desc, size=8.5, color=MUTED)

    # 阶段流程
    steps = [
        ("0", "一次性准备", "档案 / 简历 / 台账 / 素材库", "协", PURPLE),
        ("1", "筛岗", "站点核实城市 + 岗位原文 + 硬性否决", "A", BLUE),
        ("2", "进入投递流程", "识别 ATS 平台", "A", BLUE),
        ("!", "登录", "预填手机号 / 证件号 / 勾协议", "人", AMBER),
        ("3", "填表", "传简历 → 核对解析 → 补字段 → 长文本", "A", BLUE),
        ("4", "校验与修复", "触发校验 → 收红字 → 修复 → 失焦复查", "A", BLUE),
        ("5", "交接提交", "输出确认清单 → 按下提交", "人", AMBER),
        ("6", "记账", "追加记录 → 更新统计 → 校验序号", "A", BLUE),
        ("7", "定期跟进", "每周重建 → 分桶 → 催 ≥21 天", "A", BLUE),
    ]

    sx, sw = 330, 610
    y = 92
    step_h = 54
    for num, title, desc, who, col in steps:
        c.round_rect(sx, y, sw, step_h, fill=(1, 1, 1), stroke=FAINT)
        # 左侧色条
        c.round_rect(sx, y, 4, step_h, fill=col)
        # 序号圆
        c.round_rect(sx + 18, y + 15, 24, 24, fill=col)
        c.text(sx + 18, y + 20, num, size=11, color=(1, 1, 1), align="center", width=24)
        # 标题与说明
        c.text(sx + 56, y + 14, title, size=11.5, color=INK)
        c.text(sx + 56, y + 33, desc, size=8.8, color=MUTED)
        # 执行者徽章
        label = {"A": "Agent", "人": "人", "协": "协作"}[who]
        bw = F.text_length(label, 9) + 30
        bx = sx + sw - bw - 14
        c.round_rect(bx, y + 16, bw, 22, fill=(1, 1, 1), stroke=col)
        c.round_rect(bx + 4, y + 20, 14, 14, fill=col)
        c.text(bx + 4, y + 21, who, size=8.5, color=(1, 1, 1), align="center", width=14)
        c.text(bx + 22, y + 21, label, size=9, color=col)
        # 连接线
        if num != "7":
            c.arrow(sx + 30, y + step_h, sx + 30, y + step_h + 12, color=FAINT)
        y += step_h + 12

    c.save("workflow.png")


# ════════════════════════════════════════════════════════════
# 图 2：七层降级链路
# ════════════════════════════════════════════════════════════
def diagram_degradation():
    W, H = 900, 640
    c = Canvas(W, H)

    c.text(40, 36, "定位的七层降级", size=19, color=INK)
    c.text(40, 64, "从最自然的方法开始，逐层降级；试到第 4 层仍不行就转人工", size=10.5, color=MUTED)

    layers = [
        ("1", "Playwright 语义定位器", "getByRole / getByText / getByPlaceholder", GREEN, GREEN_BG, "首选"),
        ("2", "domSnapshot 重建 locator", "超时或 strict 冲突后，从 snapshot 事实重建", GREEN, GREEN_BG, ""),
        ("3", "页面内原生 click()", "合成事件", BLUE, BLUE_BG, ""),
        ("4", "鼠标事件序列", "pointerdown → mousedown → pointerup → mouseup → click", BLUE, BLUE_BG, "临界点"),
        ("5", "cua 真实鼠标点击", "需要视口内坐标", AMBER, AMBER_BG, ""),
        ("6", "React fiber 直调", "props.onChange / onClick", RED, RED_BG, "慎用"),
        ("7", "止损：转人工", "输出「字段名 + 应填值 + 位置」清单", RED, RED_BG, "明确边界"),
    ]

    x, w = 40, 820
    y = 96
    h = 62
    for num, title, desc, col, bg, tag in layers:
        c.round_rect(x, y, w, h, fill=bg, stroke=col)
        c.round_rect(x, y, 5, h, fill=col)
        c.text(x + 22, y + 16, num, size=17, color=col)
        c.text(x + 60, y + 16, title, size=12.5, color=INK)
        c.text(x + 60, y + 37, desc, size=9, color=MUTED)
        if tag:
            tw = F.text_length(tag, 9) + 18
            c.round_rect(x + w - tw - 14, y + 20, tw, 22, fill=(1, 1, 1), stroke=col)
            c.text(x + w - tw - 14, y + 25, tag, size=9, color=col, align="center", width=tw)
        if num != "7":
            c.arrow(x + 30, y + h, x + 30, y + h + 10, color=FAINT)
        y += h + 10

    # 说明
    c.text(x, y + 8,
           "为什么 React 直调排在最后：它能解决很多顽疾（隐藏按钮、拒绝写入的控件），"
           "但对某些框架会造成 store 污染 —— 显示对了、提交时炸掉。",
           size=9, color=MUTED, width=w)

    c.save("degradation.png")


# ════════════════════════════════════════════════════════════
# 图 3：DOM 解剖 —— 为什么 setter 会污染 store
# ════════════════════════════════════════════════════════════
def diagram_dom_anatomy():
    W, H = 1000, 700
    c = Canvas(W, H)

    c.text(40, 36, "DOM 解剖：为什么直调 setter 会炸", size=19, color=INK)
    c.text(40, 64, "以某 ATS 的 SD-Select 为例 —— 显示层和真实值是两个地方", size=10.5, color=MUTED)

    # ── 左：两个容器的区别 ──
    lx, lw = 40, 440
    c.text(lx, 100, "① 容器类名：复数 vs 单数", size=12, color=BLUE)

    c.round_rect(lx, 116, lw, 96, fill=RED_BG, stroke=RED)
    c.text(lx + 12, 130, '<div class="apply-fields-XXXX">', size=9.5, color=RED)
    c.text(lx + 26, 148, '<div class="apply-field-XXXX">   ← 字段①', size=9, color=INK)
    c.text(lx + 26, 166, '<div class="apply-field-XXXX">   ← 字段②', size=9, color=INK)
    c.text(lx + 12, 188, '</div>', size=9.5, color=RED)
    c.text(lx + 12, 204, '✗ [class*="apply-field"] 会匹配到这个容器', size=9, color=RED)

    c.round_rect(lx, 226, lw, 76, fill=GREEN_BG, stroke=GREEN)
    c.text(lx + 12, 240, '<div class="apply-field-XXXX">   ← 只匹配单个字段', size=9, color=INK)
    c.text(lx + 12, 260, '  <input />', size=9, color=INK)
    c.text(lx + 12, 280, '✓ [class*="apply-field-"] 带尾横线才对', size=9, color=GREEN)

    c.text(lx, 326,
           "写错选择器的后果：querySelector('input') 拿到隔壁字段的控件，\n"
           "「期望薪资」里会被填进「岗位内容」的一整段文本。",
           size=9, color=MUTED, width=lw)

    # ── 右：显示层 vs 真实值 ──
    rx, rw = 520, 440
    c.text(rx, 100, "② 显示层 vs 真实值", size=12, color=BLUE)

    c.round_rect(rx, 116, rw, 226, fill=(1, 1, 1), stroke=FAINT)
    c.text(rx + 12, 132, '<label class="sd-Select-container">', size=9, color=MUTED)
    c.round_rect(rx + 24, 144, rw - 48, 64, fill=AMBER_BG, stroke=AMBER)
    c.text(rx + 36, 158, '<span class="sd-Input-display-value">', size=8.8, color=AMBER)
    c.text(rx + 48, 176, '<span class="sd-Select-ghost">汉族</span>', size=8.8, color=AMBER)
    c.text(rx + 36, 194, '</span>   ← 显示层', size=8.8, color=AMBER)
    c.round_rect(rx + 24, 218, rw - 48, 48, fill=GREEN_BG, stroke=GREEN)
    c.text(rx + 36, 232, '<input value="1" />', size=8.8, color=GREEN)
    c.text(rx + 36, 252, '↑ 真实值，提交时读这里', size=8.8, color=GREEN)
    c.text(rx + 12, 282, '<div class="sd-Input-message">必填项未填写</div>', size=8.5, color=RED)
    c.text(rx + 12, 300, '↑ 内部 store 没更新时的报错', size=8.5, color=RED)
    c.text(rx + 12, 324, '</label>', size=9, color=MUTED)

    # ── 对比结论 ──
    c.text(40, 420, "③ 两条路径的结果对比", size=12, color=BLUE)

    cols = [
        (40, 460, "直调 React setter", RED, RED_BG,
         ["显示层 → 更新（看起来对了）",
          "内部 store → 没同步",
          "表单校验 → 通过",
          "用户提交 → 页面加载失败错误页"]),
        (520, 460, "真实 UI 点击", GREEN, GREEN_BG,
         ["显示层 → 更新",
          "内部 store → 同步更新",
          "表单校验 → 通过",
          "用户提交 → 正常提交"]),
    ]
    for x, w, title, col, bg, items in cols:
        c.round_rect(x, 436, w, 168, fill=bg, stroke=col)
        c.text(x + 14, 452, title, size=11.5, color=col)
        yy = 476
        for it in items:
            c.text(x + 14, yy, "·", size=11, color=col)
            c.text(x + 28, yy, it, size=9.3, color=INK, width=w - 44)
            yy += 26

    c.text(40, 636,
           "结论：对这类组件，「显示对了」完全不代表「存储对了」。"
           "Moka 的 sd-Select 属于此类，所以它的下拉只能真实点击，禁止任何形式的直调。",
           size=9.5, color=MUTED, width=920)

    c.save("dom-anatomy.png")


# ════════════════════════════════════════════════════════════
# 图 4：平台识别决策树
# ════════════════════════════════════════════════════════════
def diagram_platform_map():
    W, H = 1000, 660
    c = Canvas(W, H)

    c.text(40, 36, "平台识别决策树", size=19, color=INK)
    c.text(40, 64, "打开网申页面后，按类名前缀一秒判断是哪套 ATS", size=10.5, color=MUTED)

    # 起点
    c.round_rect(400, 92, 200, 44, fill=INK)
    c.text(400, 106, "网申页面已打开", size=11.5, color=(1, 1, 1), align="center", width=200)

    branches = [
        ("phoenix-*  或  cmp_name", "北森 Beisen", BLUE, BLUE_BG,
         "cmp onChange 直调法 / 新版从 fiber 取 itemData"),
        ("sd-*  且 URL 含 mokahr.com", "Moka", RED, RED_BG,
         "下拉禁止直调（会污染 store）；选择器带尾横线"),
        ("atsx-*", "飞书招聘 ATS", GREEN, GREEN_BG,
         "period picker；长表单虚拟列表会卸载区块"),
        ("el-*", "Element UI 系", AMBER, AMBER_BG,
         "el-upload 可能拒绝程序化注入"),
    ]

    y = 176
    for i, (sig, name, col, bg, note) in enumerate(branches):
        # 连接线
        c.p.draw_line(fitz.Point(500, 136), fitz.Point(500, 152), color=FAINT, width=0.8)
        c.p.draw_line(fitz.Point(500, 152), fitz.Point(160, 152), color=FAINT, width=0.8)
        c.p.draw_line(fitz.Point(160, 152), fitz.Point(160, y + 26), color=FAINT, width=0.8)
        c.arrow(160, y + 26 - 10, 160, y + 26, color=FAINT, head=4)

        # 判定条件
        c.round_rect(40, y, 240, 52, fill=(1, 1, 1), stroke=FAINT)
        c.text(54, y + 12, f"检测到  {sig}", size=9.5, color=MUTED)
        c.text(54, y + 30, f"document.querySelectorAll(...)", size=8, color=(0.6, 0.63, 0.67))

        c.arrow(280, y + 26, 316, y + 26, color=FAINT, head=4)

        # 结论
        c.round_rect(320, y, 640, 52, fill=bg, stroke=col)
        c.round_rect(320, y, 4, 52, fill=col)
        c.text(338, y + 12, name, size=12, color=col)
        c.text(338, y + 31, note, size=9, color=INK)

        y += 68

    # 兜底
    c.p.draw_line(fitz.Point(500, 136), fitz.Point(500, 152), color=FAINT, width=0.8)
    c.p.draw_line(fitz.Point(500, 152), fitz.Point(960, 152), color=FAINT, width=0.8)
    c.p.draw_line(fitz.Point(960, 152), fitz.Point(960, y + 26), color=FAINT, width=0.8)
    c.arrow(960, y + 16, 960, y + 26, color=FAINT, head=4)

    c.round_rect(320, y, 640, 52, fill=PURPLE_BG, stroke=PURPLE)
    c.round_rect(320, y, 4, 52, fill=PURPLE)
    c.text(338, y + 12, "都不匹配 → 企业自建站", size=12, color=PURPLE)
    c.text(338, y + 31, "先 dump 页面结构，不要先写选择器", size=9, color=INK)

    # 探针代码
    c.round_rect(40, y + 76, 920, 92, fill=BG, stroke=FAINT)
    c.text(56, y + 90, "DOM 探针（贴进 Console 秒判）", size=10, color=BLUE)
    code = ("(() => { const s = document.documentElement.outerHTML; const hit = re => (s.match(re)||[]).length;\n"
            "  return { '北森': hit(/phoenix-|cmp_name/g), 'Moka': hit(/sd-Input-|apply-field-/g),\n"
            "           '飞书': hit(/atsx-/g), 'Element': hit(/el-input|el-select/g) }; })()")
    yy = y + 110
    for ln in code.split("\n"):
        c.text(56, yy, ln, size=8.2, color=INK)
        yy += 14

    c.save("platform-map.png")


# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print("生成示意图 →", OUT_DIR)
    diagram_workflow()
    diagram_degradation()
    diagram_dom_anatomy()
    diagram_platform_map()
    print("完成")
