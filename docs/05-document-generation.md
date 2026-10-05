# 简历 / 作品集 PDF 生成

> 用 Python 生成中文 PDF（简历、作品集、材料汇编）时，PyMuPDF 有三个**不报错、内容凭空消失**的坑。
> 这一篇给出根因和可直接复用的解法。

## 目录

- [一、环境与基础用法](#一环境与基础用法)
- [二、⛔ 坑一：文本框高度不足 → 整块不渲染](#二-坑一文本框高度不足--整块不渲染)
- [三、⛔ 坑二：中文长串被整段换行 → 首行截断](#三-坑二中文长串被整段换行--首行截断)
- [四、⛔ 坑三：同一字体注册两个 fontname](#四-坑三同一字体注册两个-fontname)
- [五、完整可用的排版引擎](#五完整可用的排版引擎)
- [六、字体子集化：14.5MB → 0.3MB](#六字体子集化145mb--03mb)
- [七、验收检查（必做）](#七验收检查必做)
- [八、网页转 PDF 的替代路线](#八网页转-pdf-的替代路线)

---

## 一、环境与基础用法

```bash
pip install pymupdf
```

```python
import fitz   # PyMuPDF

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"   # macOS 中文友好
doc = fitz.open()
page = doc.new_page(width=fitz.paper_rect("a4").width,
                    height=fitz.paper_rect("a4").height)

# 注册字体（同一页只需注册一次）
page.insert_font(fontname="cjk", fontfile=FONT)

# 写文本
page.insert_text(fitz.Point(72, 100), "你好", fontname="cjk", fontsize=12)

doc.save("out.pdf")
```

**字体选择**：

| 系统 | 路径 |
|---|---|
| macOS | `/System/Library/Fonts/Supplemental/Arial Unicode.ttf` |
| macOS（备选） | `/System/Library/Fonts/PingFang.ttc` |
| Linux | `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc` |
| Windows | `C:/Windows/Fonts/msyh.ttc` |

---

## 二、⛔ 坑一：文本框高度不足 → 整块不渲染

### 现象

用 `insert_textbox` 写入文字，**什么都没有**。不报错、不抛异常、返回负值。

### 根因

`insert_textbox` 按**字体的 ascender/descender** 计算行高。
对 Arial Unicode 这类字体，**单行需要的高度约为 `fontsize × 1.5`**。

如果给的矩形高度不够 → 返回负值 → **直接不绘制任何内容**。

### 典型翻车

```python
# ❌ 高 14pt 的框塞 9.8pt 的字（需要 14.7pt）→ 整行消失
page.insert_textbox(fitz.Rect(x, y, x + w, y + 14), "标题",
                    fontname="cjk", fontfile=FONT, fontsize=9.8)

# ❌ 高 42pt 的框塞 27pt 的字（需要 40.5pt，边界危险）→ 时灵时不灵
page.insert_textbox(fitz.Rect(52, 42, 543, 84), "张三",
                    fontname="cjk", fontfile=FONT, fontsize=27)
```

### 解法

**单行文本框的高度，一律给 `fontsize × 2`。**

```python
# ✅
h = fontsize * 2.0
page.insert_textbox(fitz.Rect(x, y, x + w, y + h), text, ...)
```

**不要用 `y+13`、`y+14` 这种手写常量。** 它们是 bug 的温床。

---

## 三、⛔ 坑二：中文长串被整段换行 → 首行截断

### 现象

一段中英混排的文字，渲染出来**第一行只有最前面几个字**，剩下的从第二行开始。

```
单次 Prompt
交付存在四类问题：商品事实幻觉（有审核风险…）、卖点遗漏（…）
```

看起来像"文字被截断丢失"，其实是**换行位置错了**。

### 根因

`insert_textbox` **按空格断行**。

遇到 `"单次 Prompt 交付存在四类问题：商品事实幻觉（…）、卖点遗漏（…）"` 这种结构：

1. 第一行放入 `"单次 Prompt "`（约 57pt）
2. 下一个 token 是一大段**不含空格的中文**（约 800pt），塞不进剩余宽度
3. 因为不能从中间断开 → **整段推到下一行**
4. 第一行只剩下 `"单次 Prompt"`

中文天然没有空格，所以只要段落里有一段长中文，就会触发这个问题。

### 解法

**不要用 `insert_textbox` 排中文。** 自研断行引擎 + `insert_text()` 逐行绘制：

```python
F = fitz.Font(fontfile=FONT)          # 用于测量字符串宽度

CJK_RANGES = [
    (0x2E80, 0x303F),   # CJK 符号
    (0x3040, 0x33FF),   # 假名、注音
    (0x3400, 0x4DBF),   # 扩展 A
    (0x4E00, 0x9FFF),   # 基本汉字
    (0xF900, 0xFAFF),   # 兼容汉字
    (0xFE30, 0xFE4F),   # 兼容形式
    (0xFF00, 0xFFEF),   # 全角
    (0x20000, 0x2FA1F), # 扩展 B+
]
CLOSE = "、。，；：！？）》」』】”’%,.;:!?)]}"   # 行首禁则：这些标点不能出现在行首

def _is_cjk(ch):
    o = ord(ch)
    return any(a <= o <= b for a, b in CJK_RANGES)

def wrap(text, size, width):
    """CJK 逐字断行；拉丁词整体不拆；避免行首标点"""
    out = []
    for para in text.split("\n"):
        cur, i, n = "", 0, len(para)
        while i < n:
            ch = para[i]
            if ch == " ":
                tok, i = " ", i + 1
            elif _is_cjk(ch):
                tok, i = ch, i + 1            # 中文逐字
            else:
                j = i
                while j < n and not _is_cjk(para[j]) and para[j] != " ":
                    j += 1
                tok, i = para[i:j], j          # 拉丁词整体
            if not cur or F.text_length(cur + tok, size) <= width or tok in CLOSE:
                cur += tok                     # 行首禁则：闭合标点允许轻微溢出
            else:
                out.append(cur.rstrip())
                cur = tok if tok != " " else ""
        out.append(cur.rstrip())
    return out

def draw_text(page, x, y, width, text, size=9.5, color=(0,0,0), leading=1.55):
    for ln in wrap(text, size, width):
        page.insert_text(fitz.Point(x, y + size * 0.86), ln,   # 0.86 ≈ ascent
                         fontname="cjk", fontsize=size, color=color)
        y += size * leading
    return y - size * leading + size * 1.5     # 末行之后再留 1.5 倍字号
```

### 关键点

| 点 | 说明 |
|---|---|
| **中文逐字断行** | CJK 字符可以任意位置断开 |
| **拉丁词整体** | `Prompt`、`RAG` 这类不能拆开 |
| **行首禁则** | `、。），` 等不能出现在行首，允许轻微溢出 |
| **`F.text_length()`** | 用真实字体度量，不要估算 |
| **baseline = `y + size * 0.86`** | `insert_text` 的点是**基线**，不是左上角 |

---

## 四、⛔ 坑三：同一字体注册两个 fontname

### 现象

```python
# ❌
page.insert_textbox(rect1, "正文", fontname="cjk",  fontfile=FONT)
page.insert_textbox(rect2, "标题", fontname="cjkb", fontfile=FONT)   # 标题不见了
```

**第二个 fontname 指向同一个字体文件时，它渲染的内容会静默消失。**

### 根因

PyMuPDF 内部按 fontname 索引字体资源。两个名字指向同一个文件时，第二个的注册没有生效，绘制调用被静默忽略。

### 解法

**全篇统一一个 fontname，靠字号和颜色做层级。**

```python
FN = "cjk"

# 封面姓名
page.insert_textbox(rect, "张三", fontname=FN, fontsize=27, color=(1,1,1))
# 章节标题
page.insert_textbox(rect, "01. 项目经历", fontname=FN, fontsize=13, color=BLUE)
# 正文
page.insert_textbox(rect, "...", fontname=FN, fontsize=9.5, color=DARK)
```

### 中文字号的层级建议

| 层级 | 字号 |
|---|---|
| 封面姓名 | 27 |
| 章节标题 | 13 |
| 小标题 | 12.5 |
| 正文 | 9.3 – 10 |
| 注释 | 8.3 |
| 页脚 | 7.5 |

---

## 五、完整可用的排版引擎

把上面三个坑的解法合起来，得到一份可以贴进任何项目的排版模块：

```python
import fitz

FN = "cjk"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
F = fitz.Font(fontfile=FONT)

A4 = fitz.paper_rect("a4")
W, H = A4.width, A4.height
ML, MR, MT = 52, 52, 54        # 边距

BLUE  = (0.16, 0.35, 0.65)
DARK  = (0.13, 0.15, 0.18)
GREY  = (0.42, 0.45, 0.50)
LINE  = (0.80, 0.83, 0.87)


def newpage(doc):
    p = doc.new_page(width=W, height=H)
    p.insert_font(fontname=FN, fontfile=FONT)
    return p, MT


def line(p, x, y, w, text, size=9.5, color=DARK, leading=1.55):
    """单行/多行文本；高度自动累积"""
    for ln in wrap(text, size, w):
        p.insert_text(fitz.Point(x, y + size * 0.86), ln,
                      fontname=FN, fontsize=size, color=color)
        y += size * leading
    return y - size * leading + size * 1.5


def draw(p, y, text, size=9.3, color=DARK, indent=0, leading=1.55):
    return line(p, ML + indent, y, W - MR - ML - indent, text, size, color, leading)


def header(p, y, num, title, sub=""):
    p.draw_rect(fitz.Rect(ML, y + 2, ML + 3.5, y + 17), color=BLUE, fill=BLUE)
    line(p, ML + 12, y, W - MR - ML - 12, f"{num}. {title}", size=13, color=BLUE)
    y += 24
    if sub:
        line(p, ML + 12, y, W - MR - ML - 12, sub, size=8.5, color=GREY)
        y += 13
    p.draw_line(fitz.Point(ML, y + 4), fitz.Point(W - MR, y + 4), color=LINE, width=0.7)
    return y + 15


def footer(p, text):
    line(p, ML, H - 46, W - MR - ML, text, size=7.5, color=GREY)
```

用法：

```python
doc = fitz.open()
p, y = newpage(doc)
y = header(p, y, "01", "项目名称", "github.com/you/repo")
y = draw(p, y, "这里是正文，会自动断行排版。", size=9.8)
footer(p, "简历 · 1/3")

doc.subset_fonts()          # ← 必做，见下一节
doc.save("out.pdf", deflate=True, garbage=4)
```

---

## 六、字体子集化：14.5MB → 0.3MB

**必须调用 `doc.subset_fonts()`。**

| 操作 | 文件大小（8 页 A4，嵌 Arial Unicode） |
|---|---|
| 不做子集化 | **14.5 MB** |
| `subset_fonts()` | **0.3 MB** |

```python
doc.subset_fonts()
doc.save(OUT, deflate=True, garbage=4)
```

原因：Arial Unicode 全量约 23MB，8 页文档只用到几百个字符。子集化后只嵌入实际用到的字形。

**这一条很实际**：很多平台对附件有大小限制（20MB / 10MB / 1MB 不等）。不做子集化，一份 8 页作品集就顶到 14.5MB，很容易超限。

---

## 七、验收检查（必做）

### ⛔ 文本提取能查到字，但页面可能是坏的

`page.get_text()` 会返回**绘制调用里的文本**，即使它没被正确渲染。

所以：

| 检查方式 | 能发现"标签整块没渲染" | 能发现"首行被截断" |
|---|---|---|
| `page.get_text()` | ❌ | ❌ |
| **渲染成 PNG 逐页看图** | ✅ | ✅ |

### 必做的两步

**第一步：渲染成图片，逐页看**

```python
for i, page in enumerate(doc):
    page.get_pixmap(dpi=105).save(f"page_{i+1}.png")
```

**第二步：程序化检查溢出**

```python
for i, page in enumerate(doc):
    body = [b[3] for b in page.get_text("blocks") if b[3] < H - 52]
    assert max(body) < H - 52, f"第 {i+1} 页正文压到页脚"
```

### 单页检查清单

| 检查项 | 怎么看 |
|---|---|
| 标签/标题是否都渲染了 | 目视 |
| 首行是否被截断 | 目视（对比源码里的段落） |
| 正文是否压到页脚 | 程序化 |
| 中文有无乱码/方框 | 目视 |
| 数字/英文有无溢出 | 目视 |

---

## 八、网页转 PDF 的替代路线

如果文档是从 HTML 生成的，有更省心的路线：

### 路线 A：Playwright 打印

```python
page.pdf(path="out.pdf", format="A4",
         margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
         print_background=True)
```

**优点**：CSS 排版能力完整（flex/grid/分页控制），中文字体用系统字体即可。

**分页控制**：

```css
@media print {
  .page { page-break-after: always; }
  .no-break { break-inside: avoid; }
}
```

### 路线 B：先 HTML → 截图 → 合成 PDF

适合需要精确控制视觉、但不需要可选文本的场景。

### 选择建议

| 场景 | 推荐 |
|---|---|
| 简历、作品集（需可选文本、ATS 解析） | **PyMuPDF 原生绘制** |
| 复杂排版、图表、CSS 效果 | **Playwright 打印** |
| 已有 HTML 模板 | **Playwright 打印** |
| 需要精确到点的控制 | **PyMuPDF 原生绘制** |

> 💡 **注意 ATS 兼容性**：如果是投递用的简历，**必须保证 PDF 里有可选文本层**。
> 纯图片 PDF（截图层成的）无法被 ATS 解析，会直接被判为"简历不可读"。
