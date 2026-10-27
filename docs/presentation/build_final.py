# -*- coding: utf-8 -*-
"""SafeGuard 결선 개발완료보고서 덱 생성 — python-pptx (build_deck.py 도우미 재사용)."""
import sys, os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "SafeGuard_final_report.pptx"
IMG = "img"
FONT = "Malgun Gothic"

# ---------------- 팔레트 ----------------
NAVY = RGBColor(0x1F, 0x1F, 0x1F)
NAVY2 = RGBColor(0x4E, 0x7A, 0x27)
INK = RGBColor(0x22, 0x22, 0x22)
OLIVE = RGBColor(0x5E, 0x93, 0x35)
LIME = RGBColor(0xB5, 0xC9, 0x2B)
MUTED = RGBColor(0x5B, 0x6B, 0x7F)
AMBER = RGBColor(0x8D, 0xB0, 0x2E)
AMBER_D = RGBColor(0xD3, 0x54, 0x00)
AMBER_L = RGBColor(0xFD, 0xF3, 0xE0)
LIGHT = RGBColor(0xF4, 0xF7, 0xEE)
LINE = RGBColor(0xD5, 0xDB, 0xE1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2E, 0x8B, 0x57)
GREEN_L = RGBColor(0xEE, 0xF5, 0xE6)
RED = RGBColor(0xC0, 0x39, 0x2B)
RED_L = RGBColor(0xFB, 0xE9, 0xE7)
BLUE = RGBColor(0x2E, 0x6F, 0xA7)
BLUE_L = RGBColor(0xE8, 0xF1, 0xF9)
GRAY_T = RGBColor(0x8A, 0x94, 0x9E)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5

# ---------------- 도우미 ----------------
def rgb(shape_fill, color):
    shape_fill.solid(); shape_fill.fore_color.rgb = color

def rect(slide, x, y, w, h, fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, shadow=False):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None: s.fill.background()
    else: rgb(s.fill, fill)
    if line is None: s.line.fill.background()
    else: s.line.color.rgb = line; s.line.width = Pt(0.75)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    if not shadow:
        s.shadow.inherit = False
    s.text_frame.text = ""
    return s

def text(slide, x, y, w, h, content, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         font=FONT, line_spacing=1.15, margin=0.05, italic=False):
    """content: str | list of paragraphs; paragraph = str | list of runs (text, {opts})"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin); tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = anchor
    paras = content if isinstance(content, list) else [content]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align; para.line_spacing = line_spacing
        runs = p if isinstance(p, list) else [(p, {})]
        for rt, opt in runs:
            r = para.add_run(); r.text = rt
            f = r.font; f.name = font; f.size = Pt(opt.get("size", size)); f.bold = opt.get("bold", bold)
            f.italic = opt.get("italic", italic); f.color.rgb = opt.get("color", color)
            if opt.get("underline"): f.underline = True
        if isinstance(p, list) and p and isinstance(p[-1], dict):
            pass
    return tb

def bullets(slide, x, y, w, h, items, size=13, color=INK, gap=4, bullet="✓", bold_lead=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, it in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(gap); para.line_spacing = 1.12
        lead, body = (it if isinstance(it, tuple) else (None, it))
        r = para.add_run(); r.text = bullet + "  "; r.font.name = FONT; r.font.size = Pt(size); r.font.color.rgb = INK; r.font.bold = True
        if lead:
            r = para.add_run(); r.text = lead + " "; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = color
        r = para.add_run(); r.text = body; r.font.name = FONT; r.font.size = Pt(size); r.font.color.rgb = color
    return tb

def picture(slide, path, x, y, w, h, align="center"):
    """box (x,y,w,h)에 비율 유지로 맞춤."""
    im = Image.open(path); iw, ih = im.size; ar = iw / ih
    if w / h > ar: nh = h; nw = h * ar
    else: nw = w; nh = w / ar
    if align == "center": px = x + (w - nw) / 2; py = y + (h - nh) / 2
    elif align == "top": px = x + (w - nw) / 2; py = y
    else: px, py = x, y
    return slide.shapes.add_picture(path, Inches(px), Inches(py), Inches(nw), Inches(nh))

FIG = [0]


def framed_picture(slide, path, x, y, w, h, caption=None, cap_size=9, fill=WHITE, line=LINE):
    """테두리 없는 그림 + '그림 N.' 번호 캡션 (레퍼런스 학회 발표 양식)."""
    ch = 0.3 if caption else 0
    picture(slide, path, x + 0.05, y + 0.04, w - 0.1, h - 0.08 - ch)
    if caption:
        FIG[0] += 1
        text(slide, x - 0.1, y + h - ch - 0.02, w + 0.2, ch, f"그림 {FIG[0]}. {caption}", size=max(cap_size, 9), bold=True,
             color=INK, align=PP_ALIGN.CENTER)

def header(slide, num, title, sub=None, dark=False):
    bg = NAVY if dark else WHITE
    b = slide.background; b.fill.solid(); b.fill.fore_color.rgb = bg
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.6), Inches(0.42), Inches(0.5), Inches(0.5))
    rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = 0; tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(num)
    r.font.name = FONT; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = WHITE
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    text(slide, 1.25, 0.32, 10.5, 0.7, title, size=26, bold=True, color=WHITE if dark else NAVY, anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        text(slide, 1.27, 0.95, 11.5, 0.4, sub, size=12, color=RGBColor(0xC9, 0xD3, 0xDE) if dark else MUTED)
    # footer
    text(slide, 0.6, 7.08, 8, 0.3, "SafeGuard 중간 발표 · 두고내리지말아조", size=9, color=GRAY_T)
    text(slide, 11.7, 7.08, 1.0, 0.3, str(num), size=9, color=GRAY_T, align=PP_ALIGN.RIGHT)

def tag(slide, x, y, w, label, fill=AMBER, color=WHITE, size=10, h=0.3):
    s = rect(slide, x, y, w, h, fill=fill, radius=0.5)
    tf = s.text_frame; tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = label
    r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = color
    return s

def chevron_flow(slide, x, y, w, h, steps, fill=NAVY2, color=WHITE, size=11, gap=0.08, first_fill=None, last_fill=None, adj=0.28):
    n = len(steps); cw = (w - gap * (n - 1)) / n
    for i, st in enumerate(steps):
        f = fill
        if i == 0 and first_fill: f = first_fill
        if i == n - 1 and last_fill: f = last_fill
        s = slide.shapes.add_shape(MSO_SHAPE.CHEVRON if i > 0 else MSO_SHAPE.PENTAGON, Inches(x + i * (cw + gap)), Inches(y), Inches(cw), Inches(h))
        rgb(s.fill, f); s.line.fill.background(); s.shadow.inherit = False
        s.adjustments[0] = adj
        tf = s.text_frame; tf.margin_left = Inches(0.06); tf.margin_right = Inches(0.03); tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        tf.word_wrap = True
        lines = st.split("\n")
        for j, ln in enumerate(lines):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = ln; r.font.name = FONT; r.font.size = Pt(size if j == 0 else size - 2); r.font.bold = (j == 0); r.font.color.rgb = color

def arrow(slide, x1, y1, x2, y2, color=MUTED, width=1.5):
    c = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color; c.line.width = Pt(width)
    # arrow head
    ln = c.line._get_or_add_ln()
    from pptx.oxml.ns import qn
    from lxml import etree
    tail = etree.SubElement(ln, qn("a:tailEnd")); tail.set("type", "triangle"); tail.set("w", "med"); tail.set("len", "med")
    return c

def table(slide, x, y, w, h, header_row, rows, col_w=None, size=10.5, head_fill=OLIVE, head_color=WHITE, zebra=True, first_bold=False, row_h=None):
    nr, nc = len(rows) + 1, len(header_row)
    gt = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(h))
    t = gt.table
    tbl = gt._element.graphic.graphicData.tbl
    # remove style banding
    tblPr = tbl.tblPr; tblPr.set("firstRow", "0"); tblPr.set("bandRow", "0")
    if col_w:
        tot = sum(col_w)
        for i, cw in enumerate(col_w): t.columns[i].width = Inches(w * cw / tot)
    if row_h:
        for i in range(nr): t.rows[i].height = Inches(row_h)
    def setcell(cell, txt, bold, color, fill, sz, align=PP_ALIGN.LEFT):
        cell.fill.solid(); cell.fill.fore_color.rgb = fill
        cell.margin_left = cell.margin_right = Inches(0.06); cell.margin_top = cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = cell.text_frame; tf.word_wrap = True
        lines = txt.split("\n") if isinstance(txt, str) else [txt]
        for j, ln in enumerate(lines):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph(); p.alignment = align
            r = p.add_run(); r.text = ln; r.font.name = FONT; r.font.size = Pt(sz); r.font.bold = bold; r.font.color.rgb = color
    for j, htxt in enumerate(header_row):
        setcell(t.cell(0, j), htxt, True, head_color, head_fill, size)
    for i, row in enumerate(rows, 1):
        fill = LIGHT if (zebra and i % 2 == 0) else WHITE
        for j, ctxt in enumerate(row):
            if isinstance(ctxt, tuple):  # (text, fill, color, bold)
                tx, cf, cc, cb = (list(ctxt) + [None, None, None])[:4]
                setcell(t.cell(i, j), tx, cb if cb is not None else False, cc or INK, cf or fill, size)
            else:
                setcell(t.cell(i, j), ctxt, first_bold and j == 0, INK, fill, size)
    return t

def card(slide, x, y, w, h, title, body_items, num=None, title_color=NAVY, fill=LIGHT, size=11.5, title_size=13, accent=AMBER):
    text(slide, x, y, w, 0.45, "❖  " + title, size=title_size + 1, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    if body_items:
        bullets(slide, x + 0.28, y + 0.5, w - 0.3, h - 0.55, body_items, size=size)

def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt

def P(name): return os.path.join(IMG, name)

# =====================================================================
# 결선 보고서 전용
# =====================================================================
FOOT = "제24회 임베디드SW경진대회 | 자동차/모빌리티 | 두고내리지말아조 | SafeGuard"
GITHUB = "github.com/SafeGuard-EWHA/2026ESWContest_mobility_DugoNaerijiMarajo"
YOUTUBE = "youtu.be/[시연 영상 업로드 후 주소 입력]"
PAGE = [0]
F = lambda n: os.path.join(IMG, "final", n)
BZ = lambda n: os.path.join(IMG, "benz", n)
PF = lambda n: os.path.join(IMG, "..", "..", "figures", "paper", n)

def new_slide():
    return prs.slides.add_slide(BLANK)

def top_bars(s):
    rect(s, 0, 0, SW, 0.08, fill=RGBColor(0, 0, 0), shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, 0.08, SW, 0.09, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
    text(s, 0.08, -0.02, 6, 0.12, "SafeGuard | 두고내리지말아조", size=6, color=WHITE)


def page(sec, title, sub=None):
    """레퍼런스 양식: 큰 섹션 제목 + 연두 밑줄 + 초록 탭 + 아래 빨간 화살표 결론.
    sub = "N. 섹션 | 탭 (보충)" / title = 이 쪽의 결론 문장."""
    PAGE[0] += 1
    s = new_slide()
    b = s.background; b.fill.solid(); b.fill.fore_color.rgb = WHITE
    top_bars(s)
    sec_name, tab_label, note = "", "", ""
    if sub:
        sec_name, _, rest = sub.partition(" | ")
        tab_label, _, note = rest.partition(" (")
        note = note[:-1] if note.endswith(")") else note
    text(s, 0.3, 0.24, 11, 0.65, sec_name, size=26, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    rect(s, 0.3, 0.9, SW - 0.6, 0.025, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
    if tab_label:
        tw = 0.6 + 0.2 * len(tab_label)
        t = rect(s, 0.3, 0.99, tw, 0.37, fill=OLIVE, radius=0.12, shadow=True)
        tf = t.text_frame; tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        pp = tf.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER; r = pp.add_run(); r.text = tab_label
        r.font.name = FONT; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE
        if note:
            text(s, 0.3 + tw + 0.15, 0.99, 9, 0.37, note, size=10.5, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
    # 아래: 빨간 화살표 + 이 쪽의 결론
    ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(0.35), Inches(7.04), Inches(0.5), Inches(0.28))
    rgb(ar.fill, RGBColor(0xC0, 0x10, 0x10)); ar.line.fill.background(); ar.shadow.inherit = False
    text(s, 0.95, 6.98, 11.3, 0.4, [[("핵심:  ", {"bold": True, "color": INK, "size": 13.5}),
                                    (title, {"bold": True, "color": RGBColor(0xC0, 0x10, 0x10), "size": 13.5, "underline": True})]],
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, 12.3, 7.1, 0.7, 0.3, str(PAGE[0]), size=9, color=GRAY_T, align=PP_ALIGN.RIGHT)
    return s

def todo(slide, x, y, w, label):
    """팀 확인이 필요한 자리 표시 (제출 전 반드시 채우거나 지울 것)."""
    return tag(slide, x, y, w, label, fill=RED_L, color=RED, size=10, h=0.32)

def stat(slide, x, y, w, h, big, label, color=NAVY, fill=LIGHT, big_size=30):
    rect(slide, x, y, w, h, fill=fill, radius=0.06)
    text(slide, x + 0.1, y + 0.1, w - 0.2, h * 0.55, big, size=big_size, bold=True, color=color, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, x + 0.1, y + h * 0.58, w - 0.2, h * 0.4, label, size=11, color=MUTED, align=PP_ALIGN.CENTER)

# ---------------- 표지 (분량 제외) ----------------
s = new_slide()
b = s.background; b.fill.solid(); b.fill.fore_color.rgb = WHITE
rect(s, 0, 0, SW, 0.62, fill=RGBColor(0, 0, 0), shape=MSO_SHAPE.RECTANGLE)
rect(s, 0, 0.62, SW, 0.16, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.45, 0.08, 8, 0.3, "제24회 임베디드SW경진대회", size=13, bold=True, color=WHITE)
text(s, 0.45, 0.34, 8, 0.25, "자동차/모빌리티 부문  |  개발완료보고서", size=9.5, italic=True, color=WHITE)
rect(s, 0, 1.95, 0.9, 0.03, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
rect(s, 12.43, 1.95, 0.9, 0.03, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
text(s, 1.2, 1.1, 10.9, 1.4, ["UWB와 mmWave를 융합한 Cascading Wake-up 기반", "차량 내 잔류 탑승자 선제 보호 시스템, SafeGuard"],
     size=26, bold=True, color=INK, align=PP_ALIGN.CENTER, line_spacing=1.05)
text(s, 1.2, 2.55, 10.9, 0.8, ["SafeGuard: Event-driven Cascading Wake-up System", "for In-vehicle Occupant Protection"],
     size=14, bold=True, color=RGBColor(0xC8, 0xCC, 0xD0), align=PP_ALIGN.CENTER, line_spacing=1.0)
picture(s, BZ("car_side_teddy.jpg"), 0.6, 3.55, 5.9, 3.35)
text(s, 6.9, 4.45, 6.0, 0.4, "[팀번호]_두고내리지말아조:  윤현서, 최서현, 윤홍은", size=14, bold=True, color=INK)
bullets(s, 6.9, 4.95, 6.0, 1.5, ["이화여자대학교", "소스코드  " + GITHUB, "시연 영상  " + YOUTUBE], size=10.5, bullet="▪", gap=2)
text(s, 6.9, 6.55, 6.0, 0.3, "시연 시제품: 유아용 전동차 + 인형(잔류 탑승자 역할), 2026.10.28", size=9.5, color=MUTED)
text(s, 0.45, 7.0, 3, 0.3, "2026. 10. 28", size=10, color=GRAY_T)

# =====================================================================
# 1. 개발 개요 (3p)
# =====================================================================
s = page(1, "온도가 오른 뒤에 알리면 이미 늦다", "1. 개발 개요 | 배경과 필요성")
stat(s, 0.6, 1.55, 2.9, 1.5, "2~3배", "직사광선 아래 차량 실내 온도\n(외기 대비 상승 배율)", color=RED)
stat(s, 3.7, 1.55, 2.9, 1.5, "1,000명+", "1998년 이후 미국 고온 차량\n아동 사망 (NHTSA)", color=RED)
stat(s, 6.8, 1.55, 2.9, 1.5, "2026", "Euro NCAP 어린이 잔류 감지\n(CPD) 평가 항목 포함", color=NAVY)
stat(s, 9.9, 1.55, 2.83, 1.5, "2019", "국내 어린이 통학차량\n하차 확인 장치 의무화", color=NAVY)
card(s, 0.6, 3.35, 6.0, 3.55, "기존 방식의 한계", [
    ("단일 센서 의존", "PIR은 정지한 아이를, 카메라는 어둠, 가림을 놓친다"),
    ("상시 구동", "모든 센서를 계속 켜 두면 주차 중 배터리 부담이 크다"),
    ("사후 대응", "‘현재 온도 > 기준’이면 이미 위험 구간에 들어선 뒤다"),
    ("단순 알림", "알림만 보내고 실내 환경을 직접 바꾸지 못한다"),
], size=14)
card(s, 6.8, 3.35, 5.93, 3.55, "개발 동기와 필요성", [
    ("동기", "‘잠깐이면 괜찮겠지’ 하는 순간의 사고를 막으려면, 보호자가 차를 떠나는 시점부터 자동으로 확인하는 장치가 필요하다고 판단"),
    ("필요성", "CPD 규제, 평가가 본격화되어, 기존 차량에도 붙일 수 있는 저가, 저전력 잔류 감지 모듈의 수요가 생긴다"),
], size=14, accent=NAVY)
text(s, 6.8, 6.92, 5.93, 0.25, "출처: 도로교통공단 차량 실내 온도 실험, NHTSA Heatstroke, Euro NCAP 2026 CPD 프로토콜, 도로교통법 어린이통학버스 규정", size=7.5, color=GRAY_T)

s = page(1, "보호자가 떠난 순간부터 필요한 센서만 차례로 깨운다", "1. 개발 개요 | 목표와 작품 개념 (Cascading Wake-up + 35°C 도달 전 선제 보호)")
framed_picture(s, os.path.join(IMG, "..", "..", "..", "회로도.jpg"), 0.6, 1.45, 7.9, 4.75, caption="동작 개념도 (7월 1차 설계 그림. 결선에서는 레이더 IWR6843, 온습도 SHT31, 구동 ESP32로 교체)")
goals = [
    ("1", "놓치지 않는다", "평소엔 PIR 또는 카메라 하나만 반응해도 레이더로 확인. 레이더가 고장 나면 PIR과 카메라가 둘 다 반응할 때 ‘의심’으로 보호.", AMBER),
    ("2", "필요할 때만 켠다", "Pi 5만 상시 ON. 다음 센서와 연산은 앞 단계 이벤트가 있을 때만 활성화.", NAVY),
    ("3", "뜨거워지기 전에 움직인다", "현재 온도가 아니라 35°C 도달까지 남은 시간으로 판단해 팬, 부저를 먼저 켠다.", AMBER_D),
]
for k, (n, head_t, body_t, col) in enumerate(goals):
    y = 1.45 + k * 1.62
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.75), Inches(y + 0.05), Inches(0.55), Inches(0.55))
    rgb(c.fill, col); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    pp = tf.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER; r = pp.add_run(); r.text = n
    r.font.name = FONT; r.font.size = Pt(16); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 9.45, y, 3.3, 0.5, head_t, size=17, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 9.45, y + 0.5, 3.3, 1.05, body_t, size=12, color=INK)
framed_picture(s, P("docx/image12.png"), 0.6, 6.3, 0.9, 0.62, caption=None)
text(s, 1.6, 6.3, 11.1, 0.62, "7월 1차 시제품(Pi 4B, 릴레이, LCD)으로 이 흐름을 먼저 검증한 뒤, 결선 장비(Pi 5, IWR6843 레이더, DWM1001 UWB, ESP32)로 다시 만들었다.",
     size=12, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)

s = page(1, "유아용 전동차 안의 인형을 레이더가 찾고, 위험하면 팬과 부저가 켜진다", "1. 개발 개요 | 작품 요약, 소스코드, 시연 영상")
framed_picture(s, BZ("car_top_full.jpg"), 0.6, 1.4, 4.0, 5.55, caption="시연 시제품 전체 (2026.10.28)")
framed_picture(s, BZ("radar_on_dashboard.jpg"), 4.75, 1.4, 2.2, 5.55, caption="운전대 앞 레이더", cap_size=9)
table(s, 7.15, 1.4, 5.58, 3.1, ["항목", "내용"], [
    ["작품명", "SafeGuard"],
    ["부문 / 주제", "자동차/모빌리티 (차량 내부 및 외부 정보 활용)"],
    ["핵심 하드웨어", "Raspberry Pi 5, ESP32, TI IWR6843ISK-ODS, DWM1001-DEV ×2, Camera Module 3, PIR, SHT31, 12V 팬, 부저, 서보"],
    ["핵심 소프트웨어", "C++ 상태기계와 열 관측기, Python 센서 허브, 레이더 TLV 해석, 프레임 차분, 보호자 대시보드"],
    ["시연 플랫폼", "유아용 전동차 + 인형 (잔류 탑승자 역할)"],
], col_w=[1.4, 4.2], size=10.5)
rect(s, 7.15, 4.7, 5.58, 1.75, fill=AMBER_L, radius=0.05)
text(s, 7.35, 4.8, 5.3, 0.4, "소스코드 (GitHub)", size=13, bold=True, color=AMBER_D)
text(s, 7.35, 5.15, 5.3, 0.4, GITHUB, size=10.5, color=INK)
text(s, 7.35, 5.6, 5.3, 0.4, "시연 동영상 (YouTube, 3분 이내)", size=13, bold=True, color=AMBER_D)
text(s, 7.35, 5.95, 5.3, 0.4, YOUTUBE, size=11, color=INK)

# =====================================================================
# 2. 개발 환경 설명 (HW, SW, 기능 설계도)
# =====================================================================
s = page(2, "3개 블록으로 나눠 각자 검증한 뒤 Pi 5에서 합쳤다", "2. 개발 환경 | 하드웨어 구성")
table(s, 0.6, 1.45, 7.4, 5.4, ["블록", "부품", "역할, 연결"], [
    ["B: 판단", "Raspberry Pi 5 (16 GB)", "FSM, 온도 예측, 로그, 보호자 알림, 상시 ON"],
    ["B: 감지", "TI IWR6843ISK-ODS (60 GHz)", "존재 검증. USB(CP2105) CLI 115200 / 데이터 921600"],
    ["B: 감지", "Camera Module 3 (imx708)", "프레임 차분 움직임 검출 (1차 감지)"],
    ["A: 노드", "ESP32 #1", "PIR, SHT31 수집, 팬, 부저, 서보 구동, 시리얼 JSON"],
    ["A: 감지", "PIR EKMC4607112K", "1차 감지 (GPIO27, 풀다운)"],
    ["A: 감지", "SHT31 온습도", "실내 온도 → RC 예측 입력 (I2C 0x45)"],
    ["A: 구동", "IRLZ44N MOSFET ×2, 12V 팬, 부저, DS3218 서보", "능동 대응. 퓨즈 → 비상정지(NC) → 부하"],
    ["C: 이탈", "DWM1001-DEV ×2 (UWB)", "차량측 TAG(Pi USB) ↔ 보호자측 ANCHOR(보조배터리)"],
], col_w=[1.1, 2.6, 3.7], size=10.5)
framed_picture(s, BZ("uwb_pi_camera.jpg"), 8.2, 1.45, 2.22, 5.45, caption="UWB, 카메라, Pi 5", cap_size=9)
framed_picture(s, BZ("esp32_pir_sht31.jpg"), 10.51, 1.45, 2.22, 5.45, caption="ESP32, PIR, 온습도", cap_size=9)

s = page(2, "12V 구동부는 비상정지 스위치가 직접 끊는다", "2. 개발 환경 | 전원과 배선 (12V 구동부와 3.3V/5V 로직부 분리)")
framed_picture(s, P("hw/wiring_A.png"), 0.6, 1.45, 6.0, 3.6, caption="블록 A 배선: 12V → 퓨즈 → 비상정지(NC) → MOSFET → 팬, 부저 (빨강 12V, 파랑 신호)")
framed_picture(s, F("blockA_board.jpg"), 6.8, 1.45, 1.95, 3.6, caption="ESP32 노드 (10.28)", cap_size=8.5)
framed_picture(s, F("sht31.jpg"), 8.85, 1.45, 1.9, 3.6, caption="SHT31", cap_size=8.5)
framed_picture(s, F("power_conv.jpg"), 10.85, 1.45, 1.88, 3.6, caption="12V 컨버터", cap_size=8.5)
table(s, 0.6, 5.25, 12.13, 1.6, ["ESP32 핀", "PIR", "SHT31 SDA/SCL", "팬 MOSFET", "부저 MOSFET", "서보", "Pi ↔ ESP32"], [
    ["GPIO", "27 (INPUT_PULLDOWN)", "32 / 33 (I2C 0x45)", "25", "26", "18 / 19", "USB 시리얼 JSON 115200"],
    ["메시지 예", "{\"pir\":1}", "{\"temp\":31.2,\"hum\":48}", "FAN 1", "BUZ 1", "SRV1 90", "명령 → ACK 회신"],
], size=10.5, col_w=[1.2, 1.9, 2.2, 1.3, 1.4, 1.2, 2.6])

s = page(2, "판단은 Pi 5, 실시간 입출력은 ESP32가 맡는다", "2. 개발 환경 | 시스템 구성도 (실선 = 유선, 점선 = 무선)")
ICON = lambda n: os.path.join(IMG, "final", "icons", n + ".png")
from pptx.enum.dml import MSO_LINE


def zone(x, y, w, h, label, col):
    z = rect(s, x, y, w, h, fill=None, line=col, radius=0.03)
    z.line.dash_style = MSO_LINE.DASH; z.line.width = Pt(1.25)
    text(s, x + 0.12, y + 0.04, 3.0, 0.3, label, size=11, bold=True, color=col)


def node(x, y, w, h, icons, title, sub, fill=WHITE, tcol=NAVY, scol=MUTED, icon_w=0.8):
    rect(s, x, y, w, h, fill=fill, line=LINE, radius=0.08)
    ix = x + 0.12
    for ic in icons:
        picture(s, ICON(ic), ix, y + 0.14, icon_w, h - 0.28)
        ix += icon_w + 0.06
    text(s, ix + 0.02, y + 0.12, x + w - ix - 0.1, 0.42, title, size=12.5, bold=True, color=tcol)
    text(s, ix + 0.02, y + 0.5, x + w - ix - 0.1, h - 0.58, sub, size=10, color=scol)


def link(x1, y1, x2, y2, label, dashed=False, lx=None, ly=None, col=NAVY2, lw=1.6):
    c = arrow(s, x1, y1, x2, y2, color=col, width=2)
    if dashed:
        c.line.dash_style = MSO_LINE.DASH
    if label:
        text(s, lx if lx is not None else min(x1, x2) - 0.2, ly if ly is not None else min(y1, y2) - 0.33,
             abs(x2 - x1) + 0.4 if lx is None else lw, 0.3, label, size=9.5, bold=True, color=AMBER_D,
             align=PP_ALIGN.CENTER if lx is None else PP_ALIGN.LEFT)


R1, R2, R3, NH = 1.75, 3.35, 4.95, 1.2
zone(0.6, 1.4, 9.4, 5.0, "차량 내부", NAVY2)
zone(10.2, 1.4, 2.53, 5.0, "보호자", GREEN)
# 왼쪽: 감지 입력
node(0.8, R1, 2.45, NH, ["camera"], "카메라", "Camera Module 3\n움직임 1차 감지")
node(0.8, R2, 2.45, NH, ["mmwave"], "60 GHz 레이더", "IWR6843ISK-ODS\n존재 검증")
node(0.8, R3, 2.45, NH, ["pir", "sht31"], "PIR, 온습도", "1차 감지\nSHT31", icon_w=0.55)
# 가운데: Pi 5 + ESP32
rect(s, 4.2, R1, 2.95, R2 + NH - R1, fill=OLIVE, radius=0.06)
rect(s, 4.4, R1 + 0.18, 2.55, 1.15, fill=WHITE, radius=0.08)
picture(s, ICON("pi"), 4.5, R1 + 0.25, 2.35, 1.0)
text(s, 4.3, R1 + 1.42, 2.75, 0.45, "Raspberry Pi 5", size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
text(s, 4.3, R1 + 1.88, 2.75, 0.85, ["상태기계(FSM), 35°C 도달 예측", "레이더 TLV 해석, 로그"], size=11, color=WHITE, align=PP_ALIGN.CENTER)
rect(s, 4.2, R3, 2.95, NH, fill=AMBER_L, line=AMBER, radius=0.08)
picture(s, ICON("esp32"), 4.32, R3 + 0.15, 1.15, NH - 0.3)
text(s, 5.55, R3 + 0.12, 1.55, 0.42, "ESP32 노드", size=13, bold=True, color=AMBER_D)
text(s, 5.55, R3 + 0.52, 1.55, 0.6, "센서 읽기\n12V 구동 제어", size=10.5, color=INK)
# 오른쪽(차량): UWB 차량측, 구동부
node(7.6, R1, 2.25, NH, ["uwb"], "UWB 차량측", "DWM1001 TAG\n거리 측정", icon_w=0.75)
node(7.6, R3, 2.25, NH, ["fan", "buzzer"], "팬, 부저", "MOSFET\n비상정지", icon_w=0.5)
# 보호자
node(10.35, R1, 2.25, NH, ["uwb"], "UWB 보호자", "ANCHOR\n보조배터리", fill=GREEN_L, tcol=GREEN, icon_w=0.75)
rect(s, 10.35, R2, 2.25, NH + 0.35, fill=GREEN_L, line=LINE, radius=0.08)
picture(s, P("docx/image23.png"), 10.45, R2 + 0.1, 2.05, 0.95)
text(s, 10.35, R2 + 1.07, 2.25, 0.45, "보호자 알림 화면", size=12, bold=True, color=GREEN, align=PP_ALIGN.CENTER)
# 연결
link(3.25, R1 + 0.6, 4.2, R1 + 0.6, "CSI")
link(3.25, R2 + 0.6, 4.2, R2 + 0.6, "USB 921600")
link(3.25, R3 + 0.6, 4.2, R3 + 0.6, "GPIO, I2C")
link(7.6, R1 + 0.6, 7.15, R1 + 0.6, "USB", lx=7.13, ly=R1 + 0.25)
link(10.35, R1 + 0.6, 9.85, R1 + 0.6, "UWB 거리", dashed=True, lx=9.3, ly=R1 - 0.33, col=GREEN, lw=1.2)
link(7.15, R2 + 0.75, 10.35, R2 + 0.75, "Wi-Fi 알림: 위험 단계, 온도, 예상 시간", dashed=True, col=GREEN, lx=7.3, ly=R2 + 0.38, lw=3.0)
link(5.4, R2 + NH, 5.4, R3, "USB 시리얼 JSON", lx=6.05, ly=R2 + NH + 0.06)
link(5.95, R3, 5.95, R2 + NH, None)
link(7.15, R3 + 0.6, 7.6, R3 + 0.6, None)
text(s, 0.6, 6.5, 12.13, 0.5, [[("개발 환경  ", {"bold": True, "color": NAVY}),
                                 ("Raspberry Pi OS 64-bit, Python 3.11 (pyserial, picamera2, numpy, pandas)  |  ESP32 Arduino C++  |  "
                                  "TI mmWave SDK 3.6.2, Radar Toolbox 4.00, UniFlash 9.7  |  Streamlit, pytest  |  GitHub", {})]], size=10.5, color=INK)

# =====================================================================
# 3. 개발 프로그램 설명
# =====================================================================
s = page(3, "상태기계 하나가 이탈 확인부터 팬 구동까지 잇는다", "3. 프로그램 설명 | 상태기계 흐름도 (C++ core.cpp, 상태 10개)")
chevron_flow(s, 0.6, 1.55, 12.13, 0.95, ["STANDBY", "DEPARTURE\n_CHECK", "PRIMARY", "MMWAVE", "THERMAL", "PROTECTION"], size=12, first_fill=NAVY, last_fill=AMBER_D)
table(s, 0.6, 2.75, 7.6, 3.85, ["전이", "조건 (configs/real.json)"], [
    ["STANDBY → DEPARTURE_CHECK", "UWB 거리 > 5.0 m (7점 이동평균)"],
    ["→ PRIMARY", "5.0 m 초과가 10 s 유지 (4.0 m 안으로 3 s 돌아오면 복귀)"],
    ["→ MMWAVE", "PIR OR 카메라 움직임 (2 s 융합 창)"],
    ["→ THERMAL", "레이더 추적 > 0 또는 presence = 1"],
    ["→ PROTECTION", "실측 ≥ 35°C 또는 예측상 60 s 안에 35°C 도달"],
    ["→ FAIL_SAFE", "레이더, 센서 2 s 무응답, UART 오류, USB 소실"],
    ["어느 상태든 → ESTOP", "비상정지: 모든 출력 정지 (최우선)"],
], col_w=[2.9, 4.7], size=10.5)
table(s, 8.4, 2.75, 4.33, 2.6, ["PIR", "Cam", "정상 경로", "레이더 장애"], [
    ["0", "0", "재평가", "UNKNOWN"],
    ["1", "0", "mmWave 진입", "UNKNOWN"],
    ["0", "1", "mmWave 진입", "UNKNOWN"],
    ["1", "1", "mmWave 진입", "SUSPECTED"],
], col_w=[0.6, 0.6, 1.5, 1.6], size=10.5)
text(s, 8.4, 5.45, 4.33, 1.2, ["정상 = OR (미검출 최소화) → CONFIRMED", "레이더 장애 = AND (보수적) → SUSPECTED", "임계값은 현장 보정 전 초기값"], size=11, color=INK)

s = page(3, "센서 입력부터 대시보드까지 C++와 Python으로 직접 작성했다", "3. 프로그램 설명 | 파일 구성과 주요 함수")
table(s, 0.6, 1.4, 12.13, 5.5, ["파일", "주요 함수 / 클래스", "기능"], [
    ["prototype/SafeGuard_Main/src/core.cpp, core.hpp", "State, Core 전이", "상태 10개(INIT~ESTOP), 정상 OR / 장애 AND 판정, 출력 요청"],
    ["prototype/SafeGuard_Main/src/main.cpp", "메인 루프", "센서 허브 입력 → Core → 팬, 부저, 서보 명령, JSON 로그"],
    ["prototype/SafeGuard_Main/src/thermal_observer.hpp", "열 관측기", "최근 10분 온도 기울기 + 적응형 RC로 35°C 도달 예측"],
    ["prototype/SafeGuard_Main/scripts/sensor_hub.py", "센서 허브", "ESP32, 카메라, 레이더, UWB 입력을 묶어 C++ 코어로 전달"],
    ["prototype/SafeGuard_Main/scripts/safeguard_uwb_reader.py", "DistanceState", "UWB 거리 해석, 7점 이동평균, 2 s 만료"],
    ["prototype/SafeGuard_Main/scripts/dashboard.py", "보호자 대시보드", "상태, 온도, 예측을 Pi 8080 포트로 표시"],
    ["prototype/SafeGuard_Main/firmware/esp32_reference.ino", "명령 파서", "PIR, SHT31 JSON 송신, FAN/BUZ/SRV 명령과 ACK"],
    ["hardware/mmwave/mmwave_reader.py", "FrameReader, parse_frame", "TLV 1010/1020/1021 해석, 원본 바이트(--raw) 저장"],
    ["hardware/camera/camera_motion.py", "MotionState", "프레임 차분, 3프레임 연속 규칙, 조명 변화 1초 무시"],
    ["docs/figures/paper/build_paper_figures.py", "fig1 ~ fig7", "실측 원본으로 보고서 그림 재현"],
], col_w=[4.3, 2.4, 5.4], size=10)

s = page(3, "Pi에서 레이더 8,363프레임을 누락 0으로 받아 직접 해석했다", "3. 프로그램 설명 | mmWave 처리와 공석 판정 (TI 3D People Tracking 출력)")
chevron_flow(s, 0.6, 1.5, 12.13, 0.8, ["cfg 전송\nCLI 115200", "바이트 수신\n데이터 921600", "프레임 분리\n매직워드, 길이 검사", "TLV 해석\n점, 추적, presence", "재실 판단\n5초 규칙"], size=12)
framed_picture(s, F("dash_test3.png"), 0.4, 2.45, 8.4, 4.5, caption="원본 바이트로 다시 그린 TI 데모 형식 화면 (시험 3, 2026.10.27): X-Y, Doppler-Range, 좌석 영역 점 개수")
framed_picture(s, BZ("radar_close.jpg"), 9.0, 2.45, 3.73, 3.2, caption="IWR6843ISK-ODS", cap_size=9)
text(s, 9.0, 5.75, 3.73, 1.2, "공석 판정: 추적 1개 이상 또는 presence = 1이면 재실, 5초 연속 둘 다 없을 때만 공석", size=11, bold=True, color=NAVY)

s = page(3, "카메라는 움직일 때만 반응하고 조명 변화는 걸러낸다", "3. 프로그램 설명 | 카메라 움직임 규칙 (Camera Module 3, 10 fps)")
framed_picture(s, F("rpt_fig3.png"), 0.4, 1.4, 12.53, 4.15, caption="조건별 프레임 차분 비율과 판정 결과 (2026.10.27 시험 3, 조명 시험)")
framed_picture(s, F("cam_diff_0.jpg"), 0.6, 5.6, 2.0, 1.4, caption=None)
framed_picture(s, F("cam_diff_1.jpg"), 2.7, 5.6, 2.0, 1.4, caption=None)
text(s, 4.9, 5.6, 7.83, 1.4, [[("규칙  ", {"bold": True, "color": AMBER_D}), ("화소 밝기 차 25 초과 비율이 1%를 3프레임 연속 넘으면 움직임. 60% 넘게 바뀌면 조명 변화로 보고 1초 쉼.", {})],
                             [("결과  ", {"bold": True, "color": AMBER_D}), ("움직이는 사람 54.7%, 가만히 앉음 7.4%, 조명 변화 0%. 정지한 탑승자는 레이더가 맡는다.", {})]], size=11.5)

s = page(3, "UWB 거리 잡음 3.5 cm, 7점 평균으로 절반 줄이고 지연은 1.6초", "3. 프로그램 설명 | UWB 보호자 이탈 판정 (DWM1001 2대, 2026.10.16)")
framed_picture(s, F("rpt_fig1.png"), 0.4, 1.4, 7.7, 5.55, caption="UWB 거리 기록, 정지 구간 잡음, 평균 창 크기와 잡음, 계단 응답")
card(s, 8.3, 1.4, 4.43, 1.9, "측정 조건", [
    "차량측 TAG(Pi USB) ↔ 보호자측 ANCHOR",
    "세션 1: 602 s, 1,106개 / 세션 2: 57 s, 112개, 약 1.9 Hz",
], size=11)
card(s, 8.3, 3.4, 4.43, 2.05, "결과", [
    "정지 구간 잡음 σ 3.5 cm, 6.7 cm",
    "7점 이동평균: σ 1.7, 3.4 cm, 지연 약 1.6 s",
    "5 m + 10 s 유지 판정에 비해 지연이 작다",
], size=11, accent=GREEN)
card(s, 8.3, 5.55, 4.43, 1.4, "한계", [
    "정답 거리가 없어 정밀도만 보고. 5 m 이탈 오차는 줄자 시험으로 측정 예정",
], size=11, accent=RED)

s = page(4, "부딪힌 문제 7개, 원인을 찾아 수치로 확인했다", "4. 장애요인과 해결 | 연결, 수신, 센서")
table(s, 0.6, 1.45, 12.13, 5.45, ["장애 요인", "원인", "해결", "결과"], [
    ["레이더 펌웨어 굽기 반복 실패", "S1 스위치 5번 ON (Rev C 보드 표와 다름)", "TI SWRU546E 표 3-3대로 5번 OFF, 전원 후 RST", "굽기 성공, 펌웨어 3종 교체"],
    ["Visualizer가 cfg를 못 읽음", "검색창 실행 시 작업 폴더 쓰기 금지", "exe 폴더에서 직접 실행", "추적 화면 18 fps"],
    ["노트북 수신 프레임 7~8% 깨짐", "점 수, 버퍼와 무관 → 노트북 USB 쪽", "같은 시험을 Pi에서 반복", "Pi 8분 8,681프레임 누락 0"],
    ["Visualizer 약 6분 뒤 보드 무응답", "도구 쪽 수신 처리로 추정", "수신 리더 mmwave_reader.py 직접 작성", "15분 연속 정지 없음"],
    ["PIR 출력이 흔들림", "출력이 떠 있음, 감지 중 0.3~1초 펄스", "INPUT_PULLDOWN + FSM 유지 시간", "평소 0, 감지 시 1로 안정"],
    ["SHT31 ‘no device’", "4선 하우징이 5핀 헤더에 한 칸 밀려 VCC 빠짐", "하우징 이동, 주소 0x45, SDA 32 / SCL 33", "온습도 정상 수신"],
    ["Vital Signs 호흡수 −40~47%", "측정 거리칸 1.26 m ≠ 실제 가슴 0.95 m", "거리칸 고정 cfg", "오차 0.4~1.4회/분 (2회). 정확도는 주장 안 함"],
], col_w=[2.7, 3.4, 3.4, 2.6], size=10.5)

s = page(4, "영역을 차 크기로 줄이자 정지 1인 판정이 0%에서 95.7%로", "4. 장애요인과 해결 | 유령 추적 (2026.10.24 정지 착석 시험, 5분, 센서 높이 1.2 m)")
framed_picture(s, F("fig_still_tests.png"), 0.6, 1.45, 8.1, 5.45, caption="추적 수 원본 CSV (18.2 fps, 5,455프레임씩). 빨간 상자 = 차량용 cfg로 1명을 계속 1명으로 본 구간")
stat(s, 8.9, 1.45, 1.85, 1.65, "95.7%", "정지 1인\n정확 판정", color=GREEN, fill=GREEN_L, big_size=24)
stat(s, 10.88, 1.45, 1.85, 1.65, "6초", "퇴장 후\n공석 판정", color=GREEN, fill=GREEN_L, big_size=24)
text(s, 8.9, 3.3, 3.83, 3.6, [[("원인  ", {"bold": True, "color": RED}), ("TI 원본 cfg는 6 m 방 기준이라, 4 m 벽의 다중 반사가 영역 안에서 사람처럼 추적됐다 (C: 1명에 유령 2~5개).", {})],
                              [("해결  ", {"bold": True, "color": GREEN}), ("추적, 정지 영역(boundaryBox)을 세단 실내 치수로 줄인 ODS_sedan_est.cfg 작성.", {})],
                              [("남은 점  ", {"bold": True, "color": AMBER_D}), ("120~138초 간헐 끊김은 정지 영역 높이 1.2 m(아이 기준) 때문으로 추정.", {})]], size=12)

s = page(4, "하차 후 추적이 87초 남은 원인은 static2free 설정", "4. 장애요인과 해결 | 하차 후 잔존 (2026.10.27 시험 3, 레이더 높이 1.05 m)")
framed_picture(s, F("fig_pointcloud.png"), 0.6, 1.45, 12.13, 4.25, caption="시험 3 레이더 원본 바이트로 다시 그린 점 구름과 추적 위치 (위에서 본 모습, 2026.10.27)")
table(s, 0.6, 5.75, 7.2, 1.15, ["stateParam static2free", "프레임", "시간", "결과"], [
    ["차량용 cfg (현재)", "3000", "약 165초", "퇴장 후 87초+ 잔존"],
    ["TI 원본 cfg", "500", "약 27.5초", "시험 C: 33초 뒤 소거"],
    ["후보 cfg 3종", "500 / 200 / 100", "27.5 / 11 / 5.5초", "결선 전 비교 시험"],
], col_w=[2.2, 1.4, 1.6, 2.0], size=9.5)
text(s, 8.0, 5.75, 4.73, 1.15, [[("분석  ", {"bold": True, "color": RED}), ("남은 추적 반경 0.5 m 안 점 0개 → 정지 추적 소거 시간(static2free)이 지배. 앉아 있을 때 점이 끊긴 최장은 1.93초라 줄여도 여유 있음.", {})]], size=10.5)

# =====================================================================
# 5. 차별성, 6. 파급력
# =====================================================================
s = page(5, "기존 방식이 못 하는 세 가지: 이탈 시점, 정지한 아이, 센서 고장", "5. 개발 결과물의 차별성 | 기존 방식과 비교")
table(s, 0.6, 1.45, 12.13, 4.5, ["비교 항목", "후석 알림 (문 개폐 기록)", "단일 레이더 CPD", "SafeGuard"], [
    ["감지 시작 시점", "시동 OFF", "상시 또는 시동 OFF", "보호자 실제 이탈 (UWB 5 m)"],
    ["정지한 아이", "판단 불가", "가능", "가능 (레이더 검증)"],
    ["센서 고장 시", "-", "판단 불가", "PIR AND 카메라로 SUSPECTED"],
    ["전력", "낮음", "레이더 상시 구동", "앞 단계 이벤트가 있을 때만 활성화"],
    ["온도 대응", "없음", "알림 위주", "35°C 도달 전 팬, 부저 선제 구동"],
    ["설치", "신차 내장", "신차 내장", "기존 차량에 모듈로 추가"],
], col_w=[2.0, 3.0, 3.0, 4.1], size=11.5)
bullets(s, 0.6, 6.15, 12.1, 0.8, [
    ("핵심", "‘언제 감지를 시작하나(UWB 이탈)’, ‘무엇을 순서대로 켜나(Cascading)’, ‘언제 행동하나(도달 예측)’를 한 상태기계로 묶은 점"),
], size=13)

s = page(5, "카메라와 레이더를 합치고 점 근거를 확인하면 퇴장 뒤 오판이 사라진다", "5. 개발 결과물의 차별성 | 센서 상호보완과 측정 결과 요약")
framed_picture(s, F("rpt_fig4.png"), 0.4, 1.4, 7.4, 3.9, caption="시험 3 초 단위 재실 판정 (한 사람, 한 번 시험). 점 근거 확인은 사후 분석")
text(s, 0.6, 5.45, 7.2, 1.5, [[("해석  ", {"bold": True, "color": AMBER_D}), ("카메라만으로는 정지 착석을 12%만 잡고, 레이더는 100%지만 퇴장 뒤에도 100%다. "
                                "추적 주변 0.45 m 안에 0.5 s 동안 점 3개 이상일 때만 인정하면 퇴장 뒤 0%, 착석 100% (메인 코드 반영 전 해결 후보).", {})]], size=11)
table(s, 8.0, 1.4, 4.73, 5.55, ["지표", "결과"], [
    ["이탈 판정 (UWB)", "잡음 σ 3.5 cm, 정답 거리 시험 예정"],
    ["검출률 (레이더)", "정지 1인 95.7% (차량 cfg)"],
    ["퇴장 뒤 오판", "유령 추적 발견 → 점 근거 확인 시 0% (사후)"],
    ["카메라", "움직임 54.7%, 조명 변화 0%"],
    ["수신 주기", "레이더 55 ms 누락 0, 카메라 100 ms, UWB 531 ms"],
    ["온도 예측", "문헌 곡선 5분 앞 RMSE 0.81°C"],
    ["전환 시간, Fail-Safe, 전력", "결선 전 측정 (측정 계획 작성)"],
], col_w=[1.8, 2.9], size=10)

s = page(5, "온도가 오르는 추세로 35°C 도달을 미리 계산해 60초 전에 보호한다", "5. 개발 결과물의 차별성 | 선제 보호 열 예측 (문헌 곡선 보정) + 예외 검증")
framed_picture(s, F("rpt_fig7.png"), 0.4, 1.4, 8.3, 3.95, caption="McLaren et al. (Pediatrics 2005) 그래프 읽기 값에 맞춘 열 모델 (우리 측정 아님)")
table(s, 8.9, 1.4, 3.83, 3.95, ["시나리오 (TwinLab)", "결과"], [
    ["Normal Risk", "t = 35 s 보호 진입"],
    ["No Occupant", "카메라 오검출을 레이더가 걸러냄"],
    ["mmWave Timeout", "6 s 무응답 → FAIL_SAFE"],
], col_w=[1.7, 2.1], size=10)
card(s, 0.6, 5.5, 6.0, 1.45, "구현 (메인 코드)", [
    "최근 10분 기울기 + 적응형 RC, 예측 60 s 안 35°C면 PROTECTION",
    "합성 이력 시험: 34.5°C, 51 s 뒤 도달 예측 → 팬, 부저 요청 확인",
], size=10.5)
card(s, 6.8, 5.5, 5.93, 1.45, "한계", [
    "한 연구의 그래프 값 보정이며 실차 검증 아님",
    "실장치 선제 출력 시험은 결선 전 수행. 현장 시연은 DEMO 온도 사용",
], size=10.5, accent=RED)

s = page(6, "기존 차량에 붙이는 모듈로, 남은 과제는 실차 측정과 전력 실측", "6. 파급력과 기대효과 | 시장성, 발전 가능성, 한계")
card(s, 0.6, 1.45, 3.9, 3.3, "시장과 적용", [
    "Euro NCAP 2026 CPD 평가, 국내 통학차량 하차 확인 의무",
    "통학차량, 가족용 승용차, 렌터카, 카셰어링, 반려동물 동승",
    "범용 보드와 공개 펌웨어, 양산 시 레이더 1칩 + MCU",
], num=1, size=13.5)
card(s, 4.72, 1.45, 3.9, 3.3, "발전 가능성", [
    "CAN으로 창문, 공조, 비상등 직접 제어 (지금은 서보 모형 창문)",
    "보호자 앱 푸시, 미응답 시 단계적 연락",
    "거리 고정 레이더로 호흡 감지 (3차 측정 오차 0.4~1.4회/분, 2회)",
], num=2, size=13.5)
card(s, 8.84, 1.45, 3.89, 3.3, "현재 한계", [
    "실차 미검증, 실험은 실내와 전동차",
    "Pi 상시 ON: 이벤트 기반 활성화 범위만 절감 주장",
    "호흡은 정확도 주장 안 함, 레이더는 재실 판단에만 사용",
], num=3, size=13.5, accent=RED)
card(s, 0.6, 4.95, 12.13, 1.95, "결선 발표(11/6)까지 남은 일", [
    "UWB 줄자 5 m 이탈 시험, 상태별 전력 실측 (12V 전류 + USB 전력계), 상태 전환 시간, Fail-Safe 장애 주입 고장별 10회",
    "퇴장 뒤 유령 추적 대책: static2free 후보 비교 + 점 근거 확인을 메인 코드에 반영",
], size=13.5, accent=NAVY)

# =====================================================================
# 7. 개발 일정, 업무 분장 (2p)
# =====================================================================
s = page(7, "3명이 블록 하나씩 맡아 검증하고 인계 문서로 합쳤다", "7. 개발 일정 및 업무 분장 | 업무 분장")
table(s, 0.6, 1.45, 12.13, 3.0, ["No.", "구분", "성명", "참여 인원의 업무 분장"], [
    ["1", "팀장", "윤현서", "블록 A: 12V 전원 트리, 비상정지, MOSFET 팬, 부저 구동, ESP32 센서 노드 / 메인 통합"],
    ["2", "팀원", "최서현", "블록 C: UWB 2노드(차량측 TAG, 보호자측 ANCHOR), 이탈 판정 / 메인 통합"],
    ["3", "팀원", "윤홍은", "블록 B: Pi 5 세팅, Camera Module 3 움직임 검출, mmWave 펌웨어, cfg, 수신 리더, 정지 착석 시험, TwinLab 시뮬레이터"],
], col_w=[0.6, 1.0, 1.4, 9.1], size=14)
picture(s, BZ("car_side_top.jpg"), 0.6, 4.75, 3.0, 2.2)
bullets(s, 3.85, 5.05, 8.88, 1.85, [
    ("협업 방식", "블록별 단독 검증 → 인계 문서(HANDOFF) → 메인 통합"),
    ("기록 공유", "시험마다 원본 CSV, 사진, SHA256을 회신 패키지로 전달"),
    ("코드 관리", "GitHub Organization(SafeGuard-EWHA)에서 각자 계정으로 커밋"),
], size=13)

s = page(7, "9월 장비 수령 뒤 6주 동안 블록 검증과 통합", "7. 개발 일정 및 업무 분장 | 개발 일정")
months = ["5월", "6월", "7월", "8월", "9월", "10월"]
x0, wlab, wm = 0.6, 3.6, (12.13 - 3.6) / 6
y0 = 1.5
for i, m in enumerate(months):
    rect(s, x0 + wlab + i * wm, y0, wm - 0.04, 0.4, fill=NAVY, radius=0.1)
    text(s, x0 + wlab + i * wm, y0, wm - 0.04, 0.4, m, size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
rows = [
    ("개발계획서, 예선", 0.0, 1.35, NAVY2),
    ("1차 프로토타입 (Pi 4B), 논문", 1.3, 2.1, NAVY2),
    ("TwinLab 시뮬레이터", 1.6, 3.0, BLUE),
    ("장비 수령, 중간발표 (9/12, 9/21)", 4.35, 4.75, AMBER_D),
    ("블록 A/B/C 단독 검증", 4.5, 5.55, BLUE),
    ("mmWave 펌웨어, 정지 착석 시험", 5.7, 5.85, BLUE),
    ("메인 통합, FSM, 장애 주입", 5.8, 6.0, GREEN),
    ("결선 서류 (10/28), 발표 (11/6)", 5.88, 6.0, AMBER_D),
]
for j, (lab, a, b_, col) in enumerate(rows):
    y = y0 + 0.6 + j * 0.58
    text(s, x0, y, wlab - 0.1, 0.45, lab, size=12, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    rect(s, x0 + wlab + a * wm, y + 0.07, max((b_ - a) * wm, 0.18), 0.32, fill=col, radius=0.3)

# ---------------- 마무리 (분량 제외) ----------------
s = new_slide()
b = s.background; b.fill.solid(); b.fill.fore_color.rgb = WHITE
top_bars(s)
rect(s, 0, 3.4, 2.0, 0.03, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
rect(s, 11.33, 3.4, 2.0, 0.03, fill=LIME, shape=MSO_SHAPE.RECTANGLE)
text(s, 2.0, 2.95, 9.33, 0.8, "경청해 주셔서 감사합니다.", size=34, bold=True, color=INK, align=PP_ALIGN.CENTER)
text(s, 2.0, 3.8, 9.33, 0.45, "두고내리지말아조 (윤현서, 최서현, 윤홍은)", size=16, color=INK, align=PP_ALIGN.CENTER)
text(s, 2.0, 4.4, 9.33, 0.7, ["소스코드  " + GITHUB, "시연 영상  " + YOUTUBE], size=12, color=MUTED, align=PP_ALIGN.CENTER)
text(s, 0.6, 7.0, 3, 0.3, "2026. 10. 28", size=10, color=GRAY_T)

prs.save(OUT)
print("saved", OUT, "content pages:", PAGE[0])
