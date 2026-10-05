#!/usr/bin/env python3
"""
CJK PDF 排版引擎 —— 绕过 PyMuPDF 排中文的三个静默失败。

三个坑（都不报错，只是内容凭空消失）：
  1. insert_textbox 的矩形高度 < 字号 × 1.5 → 整块不渲染
  2. insert_textbox 按空格断行，无空格的中文长串会被整段换行 → 首行截断
  3. 同一字体注册两个 fontname → 第二个渲染的内容消失

本模块的解法：
  - 不用 insert_textbox 排中文，改用自研断行引擎 + insert_text() 逐行绘制
  - 中文逐字断行、拉丁词整体、行首禁则（闭合标点不落行首）
  - 全篇统一一个 fontname，靠字号与颜色做层级
  - 收尾必做 doc.subset_fonts()（14.5MB → 0.3MB）

依赖：pip install pymupdf

跑 demo：
    python3 cjk_pdf.py            # 生成 demo.pdf
"""

import fitz

# ── 字体（按系统自动挑一个可用的）────────────────────────────
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",          # macOS
    "/System/Library/Fonts/PingFang.ttc",                            # macOS 备选
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",                  # Linux
    "C:/Windows/Fonts/msyh.ttc",                                     # Windows
]


def pick_font():
    import os
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "找不到中文字体，请修改 FONT_CANDIDATES 或手动传入 fontfile"
    )


FONT = pick_font()
FN = "cjk"                    # ★ 全篇唯一的 fontname
F = fitz.Font(fontfile=FONT)  # 用于测量字符串宽度

# ── 版式常量 ────────────────────────────────────────────────
A4 = fitz.paper_rect("a4")
W, H = A4.width, A4.height
ML, MR, MT = 52, 52, 54       # 左 / 右 / 上边距

BLUE = (0.16, 0.35, 0.65)
DARK = (0.13, 0.15, 0.18)
GREY = (0.42, 0.45, 0.50)
LINE = (0.80, 0.83, 0.87)

# ── CJK 断行引擎 ────────────────────────────────────────────
CJK_RANGES = [
    (0x2E80, 0x303F),    # CJK 符号与标点
    (0x3040, 0x33FF),    # 假名、注音、兼容
    (0x3400, 0x4DBF),    # 扩展 A
    (0x4E00, 0x9FFF),    # 基本汉字
    (0xF900, 0xFAFF),    # 兼容汉字
    (0xFE30, 0xFE4F),    # 兼容形式
    (0xFF00, 0xFFEF),    # 全角
    (0x20000, 0x2FA1F),  # 扩展 B 及以上
]

# 行首禁则：这些标点不能出现在行首，必要时允许轻微溢出
CLOSE_PUNCT = "、。，；：！？）》」』】”’%,.;:!?)]}"


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return any(a <= o <= b for a, b in CJK_RANGES)


def wrap(text: str, size: float, width: float) -> list:
    """把文本按像素宽度断行。

    规则：
      - CJK 逐字断行（任意位置可断）
      - 拉丁字母/数字整体不拆（Prompt、RAG、2026 不拆开）
      - 行首禁则：闭合标点不落行首，允许轻微溢出
    """
    out = []
    for para in text.split("\n"):
        cur, i, n = "", 0, len(para)
        while i < n:
            ch = para[i]
            if ch == " ":
                tok, i = " ", i + 1
            elif _is_cjk(ch):
                tok, i = ch, i + 1
            else:
                j = i
                while j < n and not _is_cjk(para[j]) and para[j] != " ":
                    j += 1
                tok, i = para[i:j], j

            if not cur or F.text_length(cur + tok, size) <= width or tok in CLOSE_PUNCT:
                cur += tok
            else:
                out.append(cur.rstrip())
                cur = tok if tok != " " else ""
        out.append(cur.rstrip())
    return out


# ── 绘制原语 ────────────────────────────────────────────────
def newpage(doc):
    """新建一页，注册字体"""
    p = doc.new_page(width=W, height=H)
    p.insert_font(fontname=FN, fontfile=FONT)
    return p, MT


def line(page, x, y, w, text, size=9.5, color=DARK, leading=1.55):
    """绘制一段文本，返回下一段的 y。

    ⚠️ insert_text 的点是【基线】，不是左上角 —— 这里用 size * 0.86 近似 ascent。
    """
    for ln in wrap(text, size, w):
        page.insert_text(fitz.Point(x, y + size * 0.86), ln,
                         fontname=FN, fontsize=size, color=color)
        y += size * leading
    return y - size * leading + size * 1.5   # 末行之后再留 1.5 倍字号


def draw(page, y, text, size=9.3, color=DARK, indent=0, leading=1.55):
    """按正文宽度绘制（自动左右边距）"""
    return line(page, ML + indent, y, W - MR - ML - indent, text, size, color, leading)


def field(page, y, label, text, size=9.3, label_w=76):
    """左标签 + 右正文的两栏行"""
    line(page, ML, y, label_w, label, size=size, color=BLUE)
    return line(page, ML + label_w + 6, y, W - MR - ML - label_w - 6,
                text, size=size, color=DARK)


def header(page, y, num, title, sub=""):
    """章节标题：左侧色块 + 标题 + 可选副标题 + 分隔线"""
    page.draw_rect(fitz.Rect(ML, y + 2, ML + 3.5, y + 17), color=BLUE, fill=BLUE)
    line(page, ML + 12, y, W - MR - ML - 12, f"{num}. {title}", size=13, color=BLUE)
    y += 24
    if sub:
        line(page, ML + 12, y, W - MR - ML - 12, sub, size=8.5, color=GREY)
        y += 13
    page.draw_line(fitz.Point(ML, y + 4), fitz.Point(W - MR, y + 4), color=LINE, width=0.7)
    return y + 15


def hr(page, y, gap=0):
    """分隔线"""
    page.draw_line(fitz.Point(ML, y), fitz.Point(W - MR, y), color=LINE, width=0.8)
    return y + gap


def footer(page, text):
    line(page, ML, H - 46, W - MR - ML, text, size=7.5, color=GREY)


def save(doc, out):
    """★ 收尾：子集化 + 压缩。不做子集化，8 页文档会到 14.5MB。"""
    doc.subset_fonts()
    doc.save(out, deflate=True, garbage=4)


# ── 验收检查 ────────────────────────────────────────────────
def verify(path, verbose=True):
    """程序化溢出检查（★ 必做）

    ⚠️ page.get_text() 不能发现"整块没渲染"和"首行被截断"，
       必须另外渲染成 PNG 逐页目视。
    """
    doc = fitz.open(path)
    issues = []
    for i, page in enumerate(doc):
        ys = sorted(b[3] for b in page.get_text("blocks"))
        body = [y for y in ys if y < H - 52]
        if body and max(body) > H - 52:
            issues.append(f"第 {i+1} 页正文压到页脚（max y = {max(body):.0f}）")
        if verbose:
            print(f"  p{i+1}  正文最低 y={max(body) if body else 0:.0f}  "
                  f"距页脚 {H - 52 - (max(body) if body else 0):.0f}pt")
    return issues


# ── Demo ────────────────────────────────────────────────────
def demo():
    doc = fitz.open()
    p, y = newpage(doc)
    y = header(p, y, "01", "示例章节", "github.com/you/repo")

    # ⚠️ 下面这段同时踩了坑一和坑二，用本模块绘制则正常
    y = field(p, y, "项目定位", "把商品事实、品牌规则与营销目标，转化为可核验的电商营销内容。")
    y = field(p, y, "要解决的问题",
              "单次 Prompt 交付存在四类问题：商品事实幻觉（有审核风险，严重时无法发布）、"
              "卖点遗漏（文案流畅但没完成营销任务）、品牌与合规规则不稳定（每次输出都要人工复检）、"
              "版本之间无法比较（只能说感觉更好，无法验收）。")
    y += 6
    y = hr(p, y, 14)
    y = draw(p, y, "这一行演示的是：中文长句会在任意位置正确断行，"
                   "而 Prompt / RAG / Bad Case 这类拉丁词不会被拆开。", size=9.8)
    footer(p, "示例文档 · 1/1")

    out = "demo.pdf"
    save(doc, out)
    import os
    print(f"已生成 {out}（{os.path.getsize(out)/1024:.1f} KB）")
    print("溢出检查：")
    issues = verify(out)
    print("✓ 无溢出" if not issues else "✗ " + "; ".join(issues))


if __name__ == "__main__":
    demo()
