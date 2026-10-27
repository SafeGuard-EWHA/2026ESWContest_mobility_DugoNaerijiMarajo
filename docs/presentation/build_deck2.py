# -*- coding: utf-8 -*-
"""SafeGuard 중간발표(멘토링) 덱 생성 — python-pptx."""
import sys, os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "SafeGuard_midterm.pptx"
IMG = "img"
FONT = "Malgun Gothic"

# ---------------- 팔레트 ----------------
NAVY = RGBColor(0x1B, 0x2A, 0x41)
NAVY2 = RGBColor(0x24, 0x38, 0x55)
INK = RGBColor(0x1F, 0x29, 0x33)
MUTED = RGBColor(0x5B, 0x6B, 0x7F)
AMBER = RGBColor(0xE3, 0x9B, 0x1B)
AMBER_D = RGBColor(0xB9, 0x77, 0x0E)
AMBER_L = RGBColor(0xFD, 0xF3, 0xE0)
LIGHT = RGBColor(0xF3, 0xF5, 0xF7)
LINE = RGBColor(0xD5, 0xDB, 0xE1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2E, 0x8B, 0x57)
GREEN_L = RGBColor(0xE6, 0xF4, 0xEC)
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
        if isinstance(p, list) and p and isinstance(p[-1], dict):
            pass
    return tb

def bullets(slide, x, y, w, h, items, size=13, color=INK, gap=4, bullet="•", bold_lead=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, it in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(gap); para.line_spacing = 1.12
        lead, body = (it if isinstance(it, tuple) else (None, it))
        r = para.add_run(); r.text = bullet + " "; r.font.name = FONT; r.font.size = Pt(size); r.font.color.rgb = AMBER_D; r.font.bold = True
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

def framed_picture(slide, path, x, y, w, h, caption=None, cap_size=9, fill=WHITE, line=LINE):
    rect(slide, x, y, w, h, fill=fill, line=line, radius=0.03)
    ch = 0.28 if caption else 0
    picture(slide, path, x + 0.08, y + 0.08, w - 0.16, h - 0.16 - ch)
    if caption:
        text(slide, x, y + h - ch - 0.04, w, ch, caption, size=cap_size, color=MUTED, align=PP_ALIGN.CENTER)

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

def table(slide, x, y, w, h, header_row, rows, col_w=None, size=10.5, head_fill=NAVY, head_color=WHITE, zebra=True, first_bold=False, row_h=None):
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
    rect(slide, x, y, w, h, fill=fill, radius=0.05)
    tx = x + 0.2
    if num is not None:
        c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + 0.18), Inches(y + 0.17), Inches(0.36), Inches(0.36))
        rgb(c.fill, accent); c.line.fill.background(); c.shadow.inherit = False
        tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(num); r.font.name = FONT; r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = WHITE
        tx = x + 0.62
    text(slide, tx, y + 0.12, w - (tx - x) - 0.15, 0.45, title, size=title_size, bold=True, color=title_color, anchor=MSO_ANCHOR.MIDDLE)
    if body_items:
        bullets(slide, x + 0.15, y + 0.62, w - 0.3, h - 0.7, body_items, size=size)

def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt

def P(name): return os.path.join(IMG, name)


# =====================================================================
# v2: 10분용 14장. 슬라이드 본문은 짧게, 대본은 노트 + docx로.
# =====================================================================
SCRIPT = {}
def S_(n, t): SCRIPT[n] = t

def pic_box(slide, x, y, w, h, path, caption=None, cap_size=8.5):
    """비율 유지·자르지 않음. 캡션은 박스 아래."""
    ch = 0.26 if caption else 0
    rect(slide, x, y, w, h, fill=WHITE, line=LINE, radius=0.03)
    picture(slide, path, x + 0.06, y + 0.06, w - 0.12, h - 0.12 - ch)
    if caption:
        text(slide, x, y + h - ch - 0.03, w, ch, caption, size=cap_size, color=MUTED, align=PP_ALIGN.CENTER)

def small_stat(slide, x, y, w, big, lab, col=AMBER_D, big_size=22):
    rect(slide, x, y, w, 1.0, fill=LIGHT, radius=0.05)
    text(slide, x, y + 0.03, w, 0.55, big, size=big_size, bold=True, color=col, align=PP_ALIGN.CENTER)
    text(slide, x, y + 0.6, w, 0.35, lab, size=9, color=MUTED, align=PP_ALIGN.CENTER)

# ---------------------------------------------------------------- 1. 표지
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
text(s, 0.8, 1.0, 7.5, 0.4, "제24회 임베디드SW경진대회  ·  자동차/모빌리티 부문  ·  중간 발표 (멘토링)", size=13, color=RGBColor(0xC9, 0xD3, 0xDE))
text(s, 0.8, 1.55, 7.5, 1.2, "SafeGuard", size=60, bold=True, color=WHITE)
text(s, 0.8, 2.75, 7.5, 1.1, ["UWB · mmWave 융합 기반 다단계 저전력 감지", "능동형 차량 내 잔류 탑승자 보호 시스템"], size=20, color=WHITE, line_spacing=1.2)
rect(s, 0.8, 4.1, 1.2, 0.05, fill=AMBER, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.8, 4.35, 7.5, 0.9, [[("컨설팅 피드백 반영 설계 확정  ·  구현 현황  ·  질의", {"bold": True, "color": AMBER})],
                              "팀 두고내리지말아조   윤현서 · 최서현 · 윤홍은          2026. 09"], size=14, color=WHITE, line_spacing=1.4)
rect(s, 8.5, 1.3, 4.3, 3.6, fill=WHITE, radius=0.04)
picture(s, P("docx/image1.jpeg"), 8.6, 1.4, 4.1, 3.4)
text(s, 8.5, 4.95, 4.3, 0.4, "SafeGuard 동작 개요", size=10, color=RGBColor(0xC9, 0xD3, 0xDE), align=PP_ALIGN.CENTER)
S_(1, "안녕하십니까, 두고내리지말아조의 발표를 시작하겠습니다. 저희 작품 SafeGuard는 주차 후 보호자가 이탈했을 때 차 안에 남은 탑승자를 단계적으로 감지하고, 위험 온도에 도달하기 전에 팬과 부저로 먼저 대응하는 시스템입니다. "
      "오늘은 멘토링 자리인 만큼 완성도를 나열하기보다, 1차 컨설팅에서 받은 피드백을 저희가 어떤 설계 결정으로 바꿨는지, 지금까지 무엇을 만들었고 앞으로 무엇을 할지, 그리고 여쭙고 싶은 질문 세 가지를 말씀드리겠습니다. (약 20초)")

# ---------------------------------------------------------------- 2. 한눈에 보기
s = prs.slides.add_slide(BLANK); header(s, 2, "SafeGuard 한눈에 보기", "필요한 센서만 순차 활성화하는 Cascading Wake-up + 위험 온도 도달 ‘이전’ 선제 보호")
chevron_flow(s, 0.6, 1.5, 12.1, 0.95, ["보호자 UWB\n5m 이탈", "PIR / Camera\n1차 감지 (OR)", "mmWave\n존재 검증", "Thermal RC\n35°C 도달시간 예측", "Fan · Buzzer\n능동 대응"], size=12, first_fill=GREEN, last_fill=RED)
for i, (big, lab) in enumerate([("2~3배", "여름철 차내 온도 상승 배율 (외기 대비)"), ("2026", "Euro NCAP 어린이 잔류 감지(CPD) 평가 도입"), ("35°C", "위험 판단 기준 — ‘도달 시점’을 예측")]):
    small_stat(s, 0.6 + i * 2.05, 2.75, 1.9, big, lab, big_size=24)
rect(s, 6.9, 2.75, 5.8, 4.15, fill=WHITE, line=LINE, radius=0.03)
picture(s, P("supp/p01_img0.png"), 6.98, 2.83, 5.64, 3.7)
text(s, 6.9, 6.58, 5.8, 0.28, "보완 후 시스템 아키텍처 (Pi 5 = 판단·예측·로그 / ESP32 = 센서 입출력·구동)", size=8.5, color=MUTED, align=PP_ALIGN.CENTER)
rect(s, 0.6, 3.95, 6.05, 2.95, fill=AMBER_L, radius=0.05)
text(s, 0.8, 4.0, 5.7, 0.4, "오늘 발표의 핵심 메시지", size=13, bold=True, color=AMBER_D)
bullets(s, 0.75, 4.45, 5.8, 2.4, [("피드백 → 설계 확정:", "센서 판단 조건 · 저전력 범위 · 시연 우선순위 · 성능지표를 확정"),
                                  ("핵심 흐름 먼저:", "UWB → PIR/Camera → mmWave → 35°C 예측 → Fan/Buzzer를 우선 완성"),
                                  ("근거는 실측으로:", "6개 정량 지표를 실험으로 측정, 추정치는 추정치라고 말하기")], size=12, gap=6)
S_(2, "먼저 시스템을 한 장으로 정리했습니다. 보호자가 UWB 노드를 들고 5m 이상 멀어지면, PIR과 카메라로 1차 감지를 하고, 둘 중 하나라도 잡히면 mmWave로 존재를 검증합니다. "
      "이후 Thermal RC 모델로 35도 도달 시점을 예측해서, 도달하기 전에 팬과 부저를 먼저 켭니다. 오른쪽은 보완 후 아키텍처입니다. Raspberry Pi 5가 판단·예측·로그를, ESP32가 센서 입출력과 구동을 맡습니다. "
      "오늘의 핵심 메시지는 세 가지입니다. 피드백을 설계 결정으로 바꿨다는 것, 핵심 흐름을 먼저 완성한다는 것, 그리고 모든 근거를 실측으로 제시하겠다는 것입니다. (약 45초)")

# ---------------------------------------------------------------- 3. 피드백 요약
s = prs.slides.add_slide(BLANK); header(s, 3, "1차 컨설팅 피드백 요약", "긍정 평가 3가지와 보완 요구 8가지")
rect(s, 0.6, 1.5, 4.3, 5.4, fill=GREEN_L, radius=0.05)
text(s, 0.85, 1.6, 4.0, 0.4, "긍정적으로 평가받은 점", size=14, bold=True, color=GREEN)
bullets(s, 0.8, 2.15, 4.0, 4.6, [("하나의 상태기계", "로 이탈 확인 → 감지 → 온도 예측 → 대응을 연계"),
                                 ("다단계 센서 융합", "으로 단일 센서의 오검출·미검출 보완"),
                                 ("Thermal RC", "로 현재 온도가 아닌 ‘도달 시점’을 예측"),
                                 ("Fail-Safe 구체화", ": 독립 워치독, 장애별 대체 경로, 과전류 보호·비상정지")], size=12, gap=10)
rect(s, 5.15, 1.5, 7.55, 5.4, fill=LIGHT, radius=0.05)
text(s, 5.4, 1.6, 7.0, 0.4, "보완이 필요하다고 지적된 점", size=14, bold=True, color=AMBER_D)
fb = ["PIR·카메라 판단조건 OR/AND 혼재, mmWave 장애 시 확정 조건 필요",
      "저전력 Wake-up 구조·상태전이 조건 조기 확정, 단계별 전력·전환시간 측정",
      "전원 차단이 어려우면 Pi 상시 구동 + ‘이벤트 기반 활성화’로 성과 한정",
      "이탈–감지–온도 예측–팬·부저 핵심 흐름 우선, 창문 개방은 추가 기능",
      "실차 창문 스위치 서보는 재현성 낮음 → 모형차 창문 우선",
      "시연 중 온도 상승 어려움 → 시트 위치별 온도 사전 설정으로 재현",
      "성능지표: 이탈 판정오차·검출률·전환시간·온도 예측오차·Fail-Safe 성공률",
      "보호자 측 UWB 노드도 독립 전원 필요 (5m 이탈 시험)"]
for i, f in enumerate(fb):
    y = 2.15 + i * 0.58
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(5.4), Inches(y + 0.1), Inches(0.32), Inches(0.32)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(i + 1); r.font.name = FONT; r.font.size = Pt(10); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 5.82, y, 6.75, 0.55, f, size=11.5, anchor=MSO_ANCHOR.MIDDLE)
S_(3, "1차 컨설팅에서 받은 피드백입니다. 상태기계로 전체를 연계한 점, 다단계 센서 융합, 도달 시점 예측, Fail-Safe 구체화는 긍정적으로 평가받았습니다. "
      "보완 요구는 여덟 가지였습니다. 핵심만 말씀드리면, PIR과 카메라의 OR/AND가 문서마다 달랐다는 점, 저전력 구조를 하나로 확정하라는 점, 팬·부저까지의 핵심 흐름을 먼저 완성하고 창문은 추가 기능으로 빼라는 점, 성능지표 다섯 가지, 그리고 보호자 측 UWB 노드에 독립 전원이 필요하다는 점입니다. "
      "다음 장부터 이 여덟 가지를 어떻게 확정했는지 보여드리겠습니다. (약 45초)")

# ---------------------------------------------------------------- 4. 총괄표
s = prs.slides.add_slide(BLANK); header(s, 4, "피드백 → 설계 확정 (총괄)", "‘반영하겠습니다’가 아니라 ‘이렇게 확정했습니다’")
rows = [
    ["PIR/Camera OR냐 AND냐", ("정상 경로는 OR", AMBER_L, INK, True), "둘 중 하나 감지 → mmWave 검증 진입"],
    ["mmWave 장애 시 확정", ("Fail-Safe에서는 PIR AND Camera", AMBER_L, INK, True), "둘 다 감지 → SUSPECTED로 보수적 보호, 불충족은 UNKNOWN"],
    ["저전력 구조 불명확", ("Pi 상시 ON + 이벤트 기반 활성화", AMBER_L, INK, True), "완전 전원차단 주장 안 함. 상태별 전력·에너지 실측"],
    ["상태전이 조건 확정", ("5m 이탈 → 1차 → mmWave → Thermal → Protection", AMBER_L, INK, True), "유지시간·평활화는 UWB 실측 후 calibration"],
    ["핵심 시연 먼저", ("UWB → PIR/Camera → mmWave → 35°C 예측 → Fan/Buzzer", AMBER_L, INK, True), "창문 서보는 추가 기능, 모형차 창문"],
    ["온도 상승 재현 어려움", ("DEMO MODE 사전 설정 온도 3종", AMBER_L, INK, True), "성능 평가는 REAL MODE 실측으로 별도"],
    ["정량 성능지표", ("6개 지표군 실험 계획 고정", AMBER_L, INK, True), "거리오차·검출률·전환시간·온도오차·Fail-Safe·전력"],
    ["보호자측 UWB 독립전원", ("보호자 노드 = 보조배터리", AMBER_L, INK, True), "차량 노드 = Pi USB. 실제 5m 이탈 시험"],
]
table(s, 0.6, 1.5, 12.1, 5.3, ["받은 보완사항", "확정한 설계", "구현 · 검증"], rows, col_w=[2.6, 4.6, 4.9], size=12, first_bold=True)
S_(4, "여덟 가지 보완사항을 설계 결정으로 바꾼 총괄표입니다. 가운데 열이 저희가 확정한 안입니다. "
      "정상 경로는 OR, mmWave 장애 시에는 AND. Pi는 상시 켜 두고 센서와 연산만 이벤트 기반으로 활성화. 상태 전이 순서는 고정하되 시간값은 실측 후 보정. 핵심 시연은 팬·부저까지, 창문은 추가 기능. 온도는 DEMO MODE로 시연하고 성능은 REAL MODE로 평가. 성능지표 여섯 개. 보호자 노드는 보조배터리. "
      "이 중 앞의 네 가지를 다음 세 장에서 자세히 설명드리겠습니다. (약 1분)")

# ---------------------------------------------------------------- 5. 확정 ① OR/AND
s = prs.slides.add_slide(BLANK); header(s, 5, "확정 ① 센서 융합: 정상 OR / 장애 AND", "PIR·Camera는 최종 확정 센서가 아니라 mmWave 검증으로 진입하기 위한 1차 screening")
def node(slide, x, y, w, h, t, fill=NAVY2, color=WHITE, size=10.5):
    r = rect(slide, x, y, w, h, fill=fill, radius=0.12); tf = r.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    for j, ln in enumerate(t.split("\n")):
        p = tf.paragraphs[0] if j == 0 else tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        rr = p.add_run(); rr.text = ln; rr.font.name = FONT; rr.font.size = Pt(size); rr.font.bold = (j == 0); rr.font.color.rgb = color
rect(s, 0.6, 1.5, 6.3, 2.2, fill=GREEN_L, radius=0.05); text(s, 0.8, 1.55, 3, 0.35, "정상 경로", size=13, bold=True, color=GREEN)
node(s, 0.85, 1.95, 1.1, 0.5, "PIR"); node(s, 0.85, 2.85, 1.1, 0.5, "Camera")
node(s, 2.35, 2.4, 0.85, 0.6, "OR", fill=AMBER); arrow(s, 1.95, 2.2, 2.35, 2.65); arrow(s, 1.95, 3.1, 2.35, 2.8)
node(s, 3.55, 2.4, 1.3, 0.6, "mmWave\n검증"); arrow(s, 3.2, 2.7, 3.55, 2.7)
node(s, 5.2, 2.4, 1.5, 0.6, "CONFIRMED\n→ Thermal", fill=GREEN); arrow(s, 4.85, 2.7, 5.2, 2.7)
text(s, 0.8, 3.35, 6.0, 0.3, "AND면 어두움·가림·정지 대상 중 하나만 놓쳐도 미검출 → 미검출을 줄이는 방향", size=9.5, color=MUTED)
rect(s, 0.6, 3.9, 6.3, 2.2, fill=RED_L, radius=0.05); text(s, 0.8, 3.95, 6.0, 0.35, "mmWave 장애 경로 (timeout · UART fault · USB 소실)", size=13, bold=True, color=RED)
node(s, 0.85, 4.5, 1.4, 0.6, "mmWave\n장애 감지", fill=RED); node(s, 2.6, 4.5, 1.3, 0.6, "FAIL_SAFE"); arrow(s, 2.25, 4.8, 2.6, 4.8)
node(s, 4.25, 4.5, 1.1, 0.6, "PIR AND\nCamera", fill=AMBER); arrow(s, 3.9, 4.8, 4.25, 4.8)
node(s, 5.6, 4.25, 1.2, 0.5, "SUSPECTED\n→ Thermal", fill=GREEN, size=9.5); node(s, 5.6, 4.9, 1.2, 0.5, "UNKNOWN\n경고·재평가", fill=MUTED, size=9.5)
arrow(s, 5.35, 4.7, 5.6, 4.5); arrow(s, 5.35, 4.9, 5.6, 5.15)
text(s, 0.8, 5.55, 6.0, 0.5, "정상 = CONFIRMED, 장애 = SUSPECTED로 구분. mmWave 없이 탑승자를 완벽히 확정한다고 말하지 않음", size=9.5, color=MUTED)
rect(s, 0.6, 6.25, 6.3, 0.65, fill=LIGHT, radius=0.05)
text(s, 0.75, 6.28, 6.0, 0.6, [[("‘동시에’ = ", {"bold": True}), ("같은 순간이 아니라 설정된 시간창(fusion_window) 안에 두 감지 증거가 모두 유효.  ", {}), ("UNKNOWN = ", {"bold": True}), ("판단 불가 (탑승자 없음·안전 아님)", {})]], size=9.5, anchor=MSO_ANCHOR.MIDDLE)
text(s, 7.2, 1.5, 5.5, 0.4, "센서 융합 진리표", size=13, bold=True, color=NAVY)
table(s, 7.2, 1.95, 5.5, 3.0, ["PIR", "Camera", "정상 경로", "mmWave 장애 경로"], [
    ["0", "0", "1차 감지 재평가", ("UNKNOWN", None, MUTED)],
    ["1", "0", ("mmWave 검증 진입", GREEN_L, GREEN, True), ("UNKNOWN", None, MUTED)],
    ["0", "1", ("mmWave 검증 진입", GREEN_L, GREEN, True), ("UNKNOWN", None, MUTED)],
    ["1", "1", ("mmWave 검증 진입", GREEN_L, GREEN, True), ("SUSPECTED → Thermal", AMBER_L, AMBER_D, True)],
    ["무효", "임의", "감지 1로 사용 안 함", ("UNKNOWN, 장애 기록", None, MUTED)],
], col_w=[0.7, 0.9, 1.9, 2.0], size=11)
rect(s, 7.2, 5.15, 5.5, 1.75, fill=AMBER_L, radius=0.05)
text(s, 7.35, 5.2, 5.2, 0.35, "발표 문장", size=12, bold=True, color=AMBER_D)
text(s, 7.35, 5.55, 5.2, 1.3, "“1차 감지는 PIR과 Camera를 OR로 확정했습니다. mmWave 장애 시에는 두 센서가 함께 감지한 경우에만 잔류 의심 상태로 보호 경로에 진입합니다.”", size=11, color=INK, italic=True)
S_(5, "첫 번째 확정, 센서 융합 조건입니다. 정상 경로에서는 PIR 또는 카메라 중 하나만 감지돼도 mmWave 검증으로 넘어갑니다. 두 센서는 최종 확정용이 아니라 고전력 mmWave를 깨우는 트리거이기 때문에, AND로 하면 카메라가 어두움에서, PIR이 정지 대상에서 놓칠 때 미검출이 커집니다. "
      "반대로 mmWave가 timeout이나 USB 소실로 죽으면 FAIL_SAFE로 가고, 이때는 PIR과 카메라가 시간창 안에서 둘 다 감지한 경우에만 잔류 의심, SUSPECTED로 보호 경로에 진입합니다. 둘 다 아니면 UNKNOWN으로 경고하고 재평가합니다. UNKNOWN은 안전하다는 뜻이 아니라 판단 불가라는 뜻입니다. "
      "오른쪽 진리표대로 네 조합과 무효 입력을 분리해서 시험할 계획입니다. (약 1분)")

# ---------------------------------------------------------------- 6. 확정 ② 저전력 + FSM
s = prs.slides.add_slide(BLANK); header(s, 6, "확정 ② 저전력 범위 현실화: Pi 상시 ON + 이벤트 기반 활성화", "‘완전 저전력 전원관리’가 아니라 ‘이벤트 기반 센서·연산 활성화 구조’로 성과 범위를 정의")
rect(s, 0.6, 1.5, 4.0, 1.75, fill=RED_L, radius=0.05); text(s, 0.8, 1.55, 3.6, 0.35, "사용하지 않을 표현", size=12, bold=True, color=RED)
bullets(s, 0.75, 1.95, 3.7, 1.3, ["“완전 저전력 전원관리 구현”", "“mmWave 전원을 껐다 켠다”", "“소비전력 N% 감소” (실측 전)"], size=11, gap=3)
rect(s, 0.6, 3.4, 4.0, 1.75, fill=GREEN_L, radius=0.05); text(s, 0.8, 3.45, 3.6, 0.35, "사용할 표현", size=12, bold=True, color=GREEN)
bullets(s, 0.75, 3.85, 3.7, 1.3, ["“Pi 상시 구동, UWB 이벤트에 따라 Camera/mmWave/연산을 순차 활성화”", "“상태별 전력과 전환시간을 측정하겠다”"], size=11, gap=3)
rect(s, 0.6, 5.3, 4.0, 1.6, fill=LIGHT, radius=0.05); text(s, 0.8, 5.35, 3.6, 0.35, "구현", size=12, bold=True, color=NAVY)
bullets(s, 0.75, 5.7, 3.7, 1.2, ["모듈별 enable 플래그 / 이벤트 큐", "실제 전원 스위칭은 Fan/Buzzer(MOSFET)만", "ESP32 딥슬립은 검증 후 확장"], size=10.5, gap=2)
table(s, 4.9, 1.5, 7.8, 3.2, ["상태", "상시 유지", "단계별 활성화", "절감 주장 범위"], [
    ["STANDBY", "Pi, UWB, ESP32 기본 센서", "영상·검증 처리 최소화", "대기 처리 부하"],
    ["PRIMARY", "공통 수집·로그", "PIR/Camera 감지 루틴", "영상 처리 시간"],
    ["MMWAVE", "공통 수집·로그", "검증 데이터 처리", "구현한 제어 수준만"],
    ["THERMAL", "필요 센서·오류 감시", "RC 예측·외기 입력", "예측 계산 비용"],
    ["PROTECTION", "FSM·로그·온도 감시", "Fan/Buzzer 구동", "구동 전력 별도 집계"],
], col_w=[1.4, 2.1, 2.2, 1.7], size=10.5, first_bold=True)
rect(s, 4.9, 4.9, 7.8, 2.0, fill=AMBER_L, radius=0.05)
text(s, 5.1, 4.95, 7.4, 0.35, "상태전이 조건 · 측정 방법", size=12, bold=True, color=AMBER_D)
bullets(s, 5.05, 5.35, 7.5, 1.55, [("확정:", "STANDBY → DEPARTURE_CHECK(5m 초과) → PRIMARY(OR) → MMWAVE → THERMAL(35°C) → PROTECTION, FAIL_SAFE·ESTOP 별도"),
                                   ("보정:", "유지시간 10초 · 이동평균 7점은 초기값, UWB 거리 실측 후 config로 고정"),
                                   ("측정:", "All-on vs Event-driven 동일 시나리오, E = Σ(V×I×Δt), 12V 입력 전류 직렬 + USB 전력계로 장치별 분리")], size=10.5, gap=3)
S_(6, "두 번째, 저전력 범위입니다. 심사에서 ‘라즈베리파이는 상시 구동시켜야 할 듯’이라는 코멘트를 그대로 수용했습니다. 앞으로 ‘완전 저전력 전원관리’나 ‘mmWave 전원을 껐다 켠다’는 표현은 쓰지 않고, ‘Pi는 상시 구동하되 센서 처리와 연산을 이벤트 기반으로 순차 활성화한다’고 말하겠습니다. "
      "오른쪽 표가 상태별로 무엇이 항상 켜져 있고 무엇이 단계별로 켜지는지를 정리한 것입니다. 실제 전원 스위칭은 MOSFET으로 구동하는 팬과 부저만입니다. "
      "상태 전이 순서는 고정했고, 5m 유지시간 10초와 이동평균 7점은 초기값이라 UWB 실측 후 보정합니다. 전력은 All-on과 Event-driven을 같은 시나리오로 돌려서 에너지 총량으로 비교하겠습니다. (약 1분)")

# ---------------------------------------------------------------- 7. 확정 ③ 시연 + DEMO/REAL
s = prs.slides.add_slide(BLANK); header(s, 7, "확정 ③ 필수 시연 범위와 DEMO / REAL MODE 분리", "심사 제안 그대로 하나의 필수 시나리오로 · 창문 서보는 추가 기능")
chevron_flow(s, 0.6, 1.5, 12.1, 0.9, ["보호자 UWB\n5m 이상 이동", "PIR / Camera\n1차 감지 (OR)", "mmWave\n존재 검증", "35°C 도달\n예상시간 예측", "Fan ON", "Buzzer ON"], size=11.5, first_fill=GREEN, last_fill=RED)
text(s, 0.6, 2.5, 12.1, 0.4, [[("추가 기능(별도 표시): ", {"bold": True, "color": AMBER_D}), ("모형차 창문 서보는 핵심 시연 뒤에 실행, 성공/실패를 분리 기록.  ", {}), ("장애 대응: ", {"bold": True, "color": RED}), ("별도 회차에서 mmWave 통신 차단 → FAIL_SAFE → AND → SUSPECTED", {})]], size=10.5, anchor=MSO_ANCHOR.MIDDLE)
rect(s, 0.6, 3.1, 5.95, 3.8, fill=BLUE_L, radius=0.05); text(s, 0.8, 3.15, 5.5, 0.4, "REAL MODE — 성능 평가용", size=13, bold=True, color=BLUE)
chevron_flow(s, 0.8, 3.65, 5.55, 0.65, ["SHT31 실측", "외기 정보", "RC + Euler", "35°C 도달시간"], fill=BLUE, size=10, adj=0.22)
bullets(s, 0.75, 4.5, 5.65, 2.3, ["빈 시험체 가열·냉각 데이터로 R·C·열유입 보정 (보정용/평가용 분리)", "t0 정보만으로 t0+h 온도를 예측해 실측과 비교", "지표: horizon별 MAE·RMSE, 35°C 도달시간 오차"], size=11, gap=5)
rect(s, 6.75, 3.1, 5.95, 3.8, fill=AMBER_L, radius=0.05); text(s, 6.95, 3.15, 5.5, 0.4, "DEMO MODE — 현장 시연용", size=13, bold=True, color=AMBER_D)
for i, (t, d) in enumerate([("Scenario 1", "정상 초기온도"), ("Scenario 2", "기준 근접 온도"), ("Scenario 3", "위험 근접 온도")]):
    x = 6.95 + i * 1.85
    rect(s, x, 3.65, 1.7, 0.7, fill=WHITE, line=LINE, radius=0.08)
    text(s, x, 3.67, 1.7, 0.33, t, size=10.5, bold=True, color=AMBER_D, align=PP_ALIGN.CENTER)
    text(s, x, 3.98, 1.7, 0.33, d, size=10, color=INK, align=PP_ALIGN.CENTER)
bullets(s, 6.9, 4.5, 5.65, 2.3, ["시나리오를 바꾸면 35°C 예상 도달시간과 warning level이 즉시 변하는 것을 시연", "화면에 ‘DEMO’와 입력 출처 표시, 실제 SHT31 값도 함께 표시", ("발표 문장:", "“DEMO 입력값은 시연용이며 예측오차는 SHT31 실측으로 별도 검증합니다”")], size=11, gap=5)
S_(7, "세 번째, 시연 범위입니다. 컨설팅에서 사실상 정답을 주셨기 때문에 그대로 확정했습니다. 보호자가 UWB 노드를 들고 5m 이상 이동, PIR·카메라 1차 감지, mmWave 검증, 35도 도달시간 예측, 팬, 부저까지를 하나의 흐름으로 반복 재현합니다. 창문 서보는 핵심 시연 뒤에 추가 기능으로만 보여드리고, 장애 대응은 별도 회차에서 mmWave 통신을 끊어서 보여드립니다. "
      "온도는 두 모드로 나눴습니다. REAL MODE는 SHT31 실측과 외기 정보로 예측오차를 평가하는 용도이고, DEMO MODE는 현장에서 정상·근접·위험 초기온도 세 가지 시나리오를 눌러서 도달시간과 warning level이 바뀌는 것을 보여주는 용도입니다. 화면에 DEMO라고 표시하고, 성능지표는 실측으로만 계산하겠습니다. (약 45초)")

# ---------------------------------------------------------------- 8. 확정 ④ 지표 + UWB
s = prs.slides.add_slide(BLANK); header(s, 8, "확정 ④ 정량 성능지표 6개 · 보호자측 UWB 독립전원", "아직 숫자는 없습니다. ‘이렇게 측정하겠습니다’를 확정하는 단계")
metrics = [("이탈 판정오차", "줄자 0.5~7 m, 지점당 20초×3회 → MAE, 5m 오판정 횟수, LOS/NLOS"),
           ("검출률 · 오검출률", "있음/없음 × 움직임/정지 × 밝음/어두움 × 가림, 조건별 10회 → TP/FN, FP/TN"),
           ("상태전환시간", "입력 → 상태 진입 → 명령 → ACK → 실동작 timestamp, 구간별 평균·최댓값"),
           ("온도 예측오차", "보정/평가 분리, horizon별 MAE·RMSE, 35°C 도달시간 오차"),
           ("Fail-Safe 성공률", "mmWave USB 뽑기 · API 차단 · UWB 중단 · heartbeat 중단, 고장별 10회"),
           ("전력 · 에너지", "상태별 안정 구간 V·I·dt, All-on vs Event-driven 3쌍, 측정 경계 명시")]
for i, (t, b) in enumerate(metrics):
    col, row = i % 3, i // 3
    x = 0.6 + col * 2.75; y = 1.5 + row * 1.75
    rect(s, x, y, 2.6, 1.6, fill=LIGHT, radius=0.05)
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + 0.15), Inches(y + 0.15), Inches(0.34), Inches(0.34)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(i + 1); r.font.name = FONT; r.font.size = Pt(10.5); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, x + 0.55, y + 0.1, 2.0, 0.45, t, size=12, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.15, y + 0.6, 2.35, 1.0, b, size=9.5, color=INK)
rect(s, 8.95, 1.5, 3.75, 3.35, fill=WHITE, line=LINE, radius=0.05)
text(s, 9.1, 1.55, 3.5, 0.4, "UWB 두 노드 구성", size=12.5, bold=True, color=NAVY)
rect(s, 9.1, 2.0, 3.45, 1.3, fill=BLUE_L, radius=0.06); text(s, 9.2, 2.03, 3.3, 0.32, "차량측 노드 = Pi USB 전원", size=11, bold=True, color=BLUE)
bullets(s, 9.15, 2.35, 3.35, 0.95, ["거리값을 차량에서 직접 수집", "펌웨어상 TAG 모드 (거리 출력 측)"], size=10, gap=1)
rect(s, 9.1, 3.4, 3.45, 1.35, fill=GREEN_L, radius=0.06); text(s, 9.2, 3.43, 3.3, 0.32, "보호자측 노드 = 보조배터리", size=11, bold=True, color=GREEN)
bullets(s, 9.15, 3.75, 3.35, 1.0, ["10,000mAh 독립 전원, 보호자 소지", "저전류 자동차단 10분 시험"], size=10, gap=1)
rect(s, 0.6, 5.1, 12.1, 1.8, fill=AMBER_L, radius=0.05)
text(s, 0.8, 5.15, 11.7, 0.35, "지표를 이렇게 정한 이유", size=12, bold=True, color=AMBER_D)
bullets(s, 0.75, 5.55, 11.8, 1.3, [("심사 지표 5개 + 전력:", "이탈 판정오차 · 검출률/오검출률 · 상태전환시간 · 온도 예측오차 · Fail-Safe 전환 성공률에 컨설팅 질의였던 소비전력 비교를 더함"),
                                   ("모든 지표는 원시 로그 + 계산식 + 반복 수 + 실패 수를 함께 제출.", "실패·결측을 삭제하지 않고, 사람 검출 시험과 물체 시연을 분리"),
                                   ("Anchor/Tag 용어:", "발표는 ‘차량측/보호자측 노드’로. 질문 시 “거리 데이터를 차량에서 직접 수집하기 위해 차량측을 Tag 모드로 구성”")], size=10.5, gap=3)
S_(8, "네 번째, 성능지표와 UWB 전원입니다. 아직 숫자는 없지만 측정 방법을 고정했습니다. 심사에서 주신 다섯 개, 이탈 판정오차, 검출률과 오검출률, 상태전환시간, 온도 예측오차, Fail-Safe 전환 성공률에 소비전력 비교를 더해 여섯 개입니다. 각 카드에 조건과 반복 횟수, 계산식을 적어 두었고, 모든 지표는 원시 로그와 실패 수까지 같이 제출하겠습니다. "
      "UWB는 보호자 측 노드에 10,000mAh 보조배터리를 붙여 실제로 들고 5m 이상 이동하는 시험을 합니다. 차량 측 노드는 Pi USB 전원이고 거리값을 차량에서 직접 읽습니다. (약 45초)")

# ---------------------------------------------------------------- 9. 구현 ① 프로토타입 사진
s = prs.slides.add_slide(BLANK); header(s, 9, "구현 ① Raspberry Pi 프로토타입 실제 구동", "Pi 4B + DHT22 + PIR + Pi Camera V2 + 릴레이(팬·DC모터·LED) — FSM을 STANDBY부터 PROTECT까지 end-to-end 실행")
pic_box(s, 0.6, 1.5, 3.0, 5.4, P("docx/image12.png"), caption="빵판 프로토타입 (Pi 4B · 릴레이 · LCD)")
caps = [("docx/image6.png", "(a) STANDBY 저전력 대기"), ("docx/image7.png", "(b) DETECT PIR 감지"), ("docx/image8.png", "(c) CONFIRM 온습도 확인"), ("docx/image9.png", "(d) THERMAL Euler 예측"), ("docx/image10.png", "(e) PROTECT 구동")]
for i, (pth, cap) in enumerate(caps):
    x = 3.75 + i * 1.82
    pic_box(s, x, 1.5, 1.72, 3.75, P(pth), caption=cap, cap_size=8)
vids = [("video/v1_02.jpg", "영상: 손 접근 → PIR 감지"), ("video/v1_07.jpg", "영상: 팬 ON + LCD"), ("video/v1_08.jpg", "영상: PROTECT 로그")]
for i, (pth, cap) in enumerate(vids):
    x = 3.75 + i * 2.35
    pic_box(s, x, 5.35, 2.25, 1.55, P(pth), caption=cap, cap_size=8)
rect(s, 10.85, 5.35, 1.85, 1.55, fill=AMBER_L, radius=0.05)
text(s, 10.9, 5.4, 1.75, 1.5, [[("27.8°C → 190 s", {"bold": True, "color": AMBER_D, "size": 11})], "현재 온도가 낮아도 35°C 도달 예측(risk=True)으로 PROTECT 선제 진입"], size=9, anchor=MSO_ANCHOR.MIDDLE)
S_(9, "여기서부터는 지금까지 실제로 만든 것입니다. 이건 미래모빌리티 공모전 논문 단계에서 만든 Raspberry Pi 4B 프로토타입입니다. DHT22, PIR, Pi Camera, 릴레이로 팬과 DC모터, LED를 연결했고, 왼쪽이 빵판 실물 사진입니다. "
      "가운데 다섯 장은 FSM이 STANDBY, DETECT, CONFIRM, THERMAL, PROTECT로 실제 전이하는 LCD 화면이고, 아래는 구동 영상 캡처입니다. 손을 가까이 대면 PIR이 잡고, 예측 결과 위험이면 팬이 돌고 LCD에 표시됩니다. "
      "특히 현재 온도가 27.8도로 낮은데도 190초 뒤 35도 도달이 예측돼서 PROTECT로 먼저 들어간 로그를 확인했습니다. 이게 저희가 말하는 선제 보호입니다. (약 1분)")

# ---------------------------------------------------------------- 10. 구현 ② 카메라·대시보드·로그
s = prs.slides.add_slide(BLANK); header(s, 10, "구현 ② 카메라 · 대시보드 · 실측 로그 · Euler 예측", "OpenCV 프레임 차분, Flask 보호자 대시보드, 180초 하드웨어 로그, 선제 PROTECT 전이")
for i, (pth, cap) in enumerate([("docx/image13.jpg", "기준 프레임"), ("docx/image14.jpg", "검출 결과 (경계 상자)"), ("docx/image15.jpg", "차분 이진영상")]):
    pic_box(s, 0.6 + i * 2.05, 1.5, 1.95, 1.85, P(pth), caption=cap, cap_size=8)
pic_box(s, 6.85, 1.5, 2.85, 1.85, P("docx/image22.png"), caption="Flask 대시보드: STANDBY", cap_size=8)
pic_box(s, 9.85, 1.5, 2.85, 1.85, P("docx/image23.png"), caption="Flask 대시보드: PIR 감지", cap_size=8)
pic_box(s, 0.6, 3.5, 4.0, 2.2, P("docx/image17.png"), caption="실측 로그: DHT22 온습도 (180 s)", cap_size=8)
pic_box(s, 4.75, 3.5, 4.0, 2.2, P("docx/image18.png"), caption="실측 로그: PIR · 릴레이 상태", cap_size=8)
pic_box(s, 8.9, 3.5, 3.8, 2.2, P("docx/image19.png"), caption="Euler 선제 PROTECT 전이 timeline", cap_size=8)
rect(s, 0.6, 5.85, 12.1, 1.05, fill=LIGHT, radius=0.05)
bullets(s, 0.75, 5.9, 11.8, 1.0, [("카메라:", "프레임 차분 → 이진화 → 윤곽 면적 임계값. 인물 식별이 아닌 움직임 판단 (이번 대회: 고정 ROI + 연속 프레임 조건, Camera Module 3)"),
                                  ("로그 연동:", "실제 Pi 로그 180초를 시뮬레이터에 입력 → t=28s 이탈, t=29s 1차 감지, t=34s mmWave 확인까지 전이. 온도 27.8~28.3°C라 ACTUATOR 미진입 (설계 의도대로)")], size=10.5, gap=3)
S_(10, "두 번째 구현입니다. 왼쪽 위는 Pi Camera 프레임 차분 결과입니다. 기준 프레임과 비교해 움직임 영역을 경계 상자로 잡고, 이진영상에서 실루엣이 분리되는 것을 확인했습니다. 인물 식별이 아니라 움직임 여부만 판단하는 경량 방식입니다. "
      "오른쪽 위는 보호자가 스마트폰으로 접속하는 Flask 대시보드로, 실측 온습도와 PIR 상태가 실시간 반영됩니다. "
      "아래는 실제 Pi에서 180초 동안 수집한 로그입니다. 이 로그를 시뮬레이터에 넣었을 때 이탈, 1차 감지, mmWave 확인까지 전이했지만 온도가 28도 수준이라 액추에이터로는 가지 않았습니다. 감지만으로 팬을 켜지 않는다는 설계 의도가 로그로 확인된 셈입니다. 맨 오른쪽이 Euler 예측으로 PROTECT에 선제 진입한 타임라인입니다. (약 45초)")

# ---------------------------------------------------------------- 11. 구현 ③ TwinLab
s = prs.slides.add_slide(BLANK); header(s, 11, "구현 ③ TwinLab 시뮬레이터 (웹 공개)", "하드웨어로 반복하기 어려운 예외(mmWave timeout, API 실패)를 시나리오로 검증 · 상태 전이 · Fail-Safe · 추정 에너지")
pic_box(s, 0.6, 1.5, 3.3, 2.75, P("sim_arch.png"), caption="TwinLab 구성", cap_size=8)
pic_box(s, 4.05, 1.5, 5.6, 2.75, P("docx/image16.png"), caption="실행 화면 (Streamlit): 시나리오 입력 · 상태별 에너지 · 모델 비교", cap_size=8)
rect(s, 9.8, 1.5, 2.9, 2.75, fill=LIGHT, radius=0.05)
picture(s, P("docx/image26.png"), 9.9, 1.6, 1.3, 1.3)
text(s, 11.25, 1.65, 1.4, 1.3, "웹 데모\n브라우저에서 바로 시나리오 조작", size=9, color=MUTED)
for i, (t, col, b) in enumerate([("Normal Risk", GREEN, "t=35s ACTUATOR_CONTROL (35°C 도달 77.3 s 예측)"), ("No Occupant", BLUE, "camera FP → mmWave 단계가 걸러냄"), ("mmWave Timeout", RED, "6 s 무응답 → t=35s FAIL_SAFE")]):
    text(s, 9.9, 2.95 + i * 0.42, 2.75, 0.4, [[(t + "  ", {"bold": True, "color": col}), (b, {"color": INK})]], size=8.5)
pic_box(s, 0.6, 4.4, 3.0, 2.5, P("docx/image20.png"), caption="추정 전력 timeline (Normal Risk)", cap_size=8)
pic_box(s, 3.75, 4.4, 3.0, 2.5, P("docx/image21.png"), caption="상태별 추정 에너지", cap_size=8)
pic_box(s, 6.9, 4.4, 3.0, 2.5, P("docx/image24.png"), caption="모델별 총 추정 에너지 (Wh)", cap_size=8)
pic_box(s, 10.05, 4.4, 2.65, 2.5, P("docx/image25.png"), caption="All-on 대비 추정 절감률 (%)", cap_size=8)
S_(11, "세 번째는 저희가 만든 시스템 레벨 시뮬레이터, TwinLab입니다. mmWave 응답 실패나 API 실패처럼 하드웨어로 반복 재현하기 어려운 예외를 시나리오로 넣어서 상태 전이와 Fail-Safe, 추정 에너지를 계산하고, 웹으로 공개해서 브라우저에서 바로 돌려볼 수 있습니다. "
      "세 시나리오를 돌렸습니다. Normal Risk에서는 35초에 액추에이터 제어로 진입했고, No Occupant에서는 카메라 오검출을 mmWave 단계가 걸러냈고, mmWave Timeout에서는 6초 무응답 뒤 FAIL_SAFE로 전이했습니다. "
      "아래 그래프는 추정 에너지 비교입니다. All-on 0.675Wh 대비 duty-cycle 정책이 0.334Wh로 약 절반이었지만, 이건 typical power 값 기반 추정치입니다. 그래서 이번 대회에서는 이 비교를 실측으로 대체하는 것이 목표입니다. (약 1분)")

# ---------------------------------------------------------------- 12. 하드웨어 현황 + 계획
s = prs.slides.add_slide(BLANK); header(s, 12, "현재 하드웨어 현황과 향후 계획", "지원 장비 36품목 수령(9/12) → 3인 블록 분담 단독 검증 → 통합 → FSM → 장애 → 성능 → 시연 고정")
pic_box(s, 0.6, 1.5, 4.6, 3.3, P("hw/parts_map.png"), caption="수령 부품 지도 (블록 A 주황 · B 빨강 · C 초록)", cap_size=8)
pic_box(s, 5.35, 1.5, 4.0, 3.3, P("hw/wiring_A.png"), caption="블록 A 배선 설계 (12V 구동부 / 로직부 분리, 비상정지)", cap_size=8)
table(s, 9.5, 1.5, 3.2, 3.3, ["블록", "상태"], [
    ["A 전원·구동·ESP32", ("IDE·보드 세팅 중", AMBER_L, AMBER_D, True)],
    ["B Pi 5·Camera·mmWave", ("OS 이미징 중", AMBER_L, AMBER_D, True)],
    ["C UWB 2노드", ("착수 예정", LIGHT, MUTED, True)],
    ["설계 문서", ("연결 가이드 · 그림책 · 보완설계 보고서 완료", GREEN_L, GREEN, True)],
], col_w=[1.5, 1.7], size=9.5, first_bold=True)
chevron_flow(s, 0.6, 5.05, 12.1, 0.65, ["0 준비", "1 단독 A/B/C", "2 통합", "3 FSM", "4 장애 주입", "5 성능 측정", "6 시연 고정", "7 추가"], size=10, first_fill=GREEN, last_fill=MUTED, adj=0.22)
tag(s, 0.6, 5.8, 2.6, "현재 위치: 0단계 → 1단계 진입", fill=GREEN, size=9.5)
text(s, 3.4, 5.78, 9.3, 0.35, "마감일 대신 단계별 통과 조건으로 운영. B의 mmWave 기본 수신과 C의 두 노드 거리 출력이 감지 통합의 선행 조건", size=10, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
rect(s, 0.6, 6.2, 12.1, 0.7, fill=AMBER_L, radius=0.05)
text(s, 0.75, 6.22, 11.8, 0.65, [[("주요 리스크와 fallback: ", {"bold": True, "color": AMBER_D}), ("mmWave Vital Signs 불안정 → presence/미세 움직임으로 대체(호흡 검출 완료라고 말하지 않음) · UWB 멀티패스 → LOS/NLOS 시험·유지시간 보정 · 보조배터리 자동 꺼짐 → 저전류 모드/더미 부하 · USB 전원 부족 → 공식 전원·powered hub", {})]], size=9.5, anchor=MSO_ANCHOR.MIDDLE)
S_(12, "현재 하드웨어 현황입니다. 9월 12일에 지원 장비 36품목을 모두 받았고, 왼쪽이 부품 지도, 가운데가 전원·구동부 배선 설계입니다. 12V 구동부와 로직부를 분리하고 비상정지는 구동 레일만 끊어서 Pi 로그가 남게 했습니다. "
      "세 명이 블록 A 전원·ESP32, B Pi·카메라·mmWave, C UWB로 나눠서 단독 검증 중이고, 연결 가이드와 부품 그림책, 보완설계 보고서를 만들어 팀에 공유했습니다. "
      "이후 일정은 마감일 대신 단계별 통과 조건으로 운영합니다. 단독 검증, 통합, FSM, 장애 주입, 성능 측정, 시연 고정 순서입니다. 리스크는 mmWave 호흡 검출이 불안정하면 presence로 대체하되 호흡 검출을 완료했다고는 말하지 않는 것, UWB 멀티패스, 보조배터리 자동 꺼짐, USB 전원 부족 순으로 대응책을 준비했습니다. (약 45초)")

# ---------------------------------------------------------------- 13. 질문
s = prs.slides.add_slide(BLANK); header(s, 13, "멘토님께 여쭙고 싶은 것 3가지", "설계 확정 과정에서 팀이 판단하기 어려웠던 지점")
qs = [("mmWave: 호흡(Vital Signs) vs 존재(presence) 검출",
       "IWR6843ISK-ODS는 천장 장착용 안테나. 계획서는 호흡 검출이 목표였으나 실내 시연에서 불안정할 가능성",
       "ODS 천장 장착에서 호흡 검출까지 가는 것이 현실적인지, 처음부터 presence/미세 움직임으로 확정하는 것이 심사 관점에서 더 안전한지. point cloud 기반일 때 ‘생명체 확인’으로 인정받을 조건은?"),
      ("소비전력 비교: 측정 경계와 계측 수준",
       "Pi는 별도 5V, 구동부는 12V, 보호자 노드는 배터리로 전원 경계가 나뉨",
       "12V 입력 전류(테스터기 직렬) + USB 인라인 전력계 수준이면 충분한지, 전력 로거가 필요한지. 상태별 전환시간·전력 표에서 심사가 기대하는 최소 형식(평균/피크/에너지)은?"),
      ("온도 시연과 고려 범위",
       "현장은 DEMO MODE 3종 시나리오, 예측오차는 REAL MODE 실측으로 분리 평가. 좌석별·외부 온도는 보고서에만 기술 예정",
       "시연(DEMO)과 성능평가(REAL) 분리 방식이 최종 심사에서 인정되는지. 좌석별 온도는 보고서·안내문만으로 되는지, 최소 몇 지점의 실측이 있어야 설득력이 있는지?")]
for i, (t, bg, q) in enumerate(qs):
    y = 1.5 + i * 1.8
    rect(s, 0.6, y, 12.1, 1.68, fill=LIGHT, radius=0.05)
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(y + 0.2), Inches(0.55), Inches(0.55)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = f"Q{i+1}"; r.font.name = FONT; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 1.55, y + 0.1, 10.9, 0.4, t, size=14, bold=True, color=NAVY)
    text(s, 1.55, y + 0.52, 3.9, 1.1, [[("배경  ", {"bold": True, "color": MUTED}), (bg, {"color": MUTED})]], size=10)
    text(s, 5.6, y + 0.52, 6.95, 1.1, [[("질문  ", {"bold": True, "color": AMBER_D}), (q, {})]], size=10.5)
S_(13, "마지막으로 세 가지를 여쭙고 싶습니다. 첫째, mmWave입니다. 저희 보드는 천장 장착용 ODS 안테나인데, 이 조건에서 호흡 검출까지 가는 게 현실적인지, 아니면 처음부터 존재 검출로 확정하는 것이 심사 관점에서 더 안전한지, 그리고 point cloud 기반일 때 생명체 확인으로 인정받으려면 어떤 조건을 갖추면 되는지 궁금합니다. "
      "둘째, 소비전력 비교입니다. 전원이 Pi, 12V 구동부, 보호자 배터리로 나뉘는데, 테스터기 직렬 측정과 USB 전력계 수준이면 충분한지, 심사에서 기대하는 최소 표 형식이 무엇인지 여쭙고 싶습니다. "
      "셋째, 온도 시연입니다. DEMO 모드로 시연하고 REAL 모드로 성능을 평가하는 분리 방식이 최종 심사에서 인정되는지, 좌석별 온도는 보고서로만 다뤄도 되는지, 최소 몇 지점 실측이 있어야 설득력이 있는지 조언 부탁드립니다. (약 1분)")

# ---------------------------------------------------------------- 14. 마무리
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
text(s, 0.8, 0.9, 11.5, 0.5, "정리", size=14, color=AMBER, bold=True)
msgs = [("피드백 → 설계 확정", "정상 OR / 장애 AND · Pi 상시 ON + 이벤트 활성화 · 필수 시연 범위 · DEMO/REAL 분리 · 6개 지표 · 보호자 UWB 독립전원"),
        ("핵심 흐름을 먼저 완성", "UWB 5m 이탈 → PIR/Camera → mmWave → 35°C 도달시간 예측 → Fan/Buzzer. 창문 서보·워치독은 추가 기능"),
        ("말할 수 있는 것과 없는 것을 구분", "검출 정확도·절감률·호흡 검출 완료는 실측 후에만. 추정치는 추정치로")]
for i, (t, b) in enumerate(msgs):
    y = 1.6 + i * 1.4
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(y + 0.1), Inches(0.5), Inches(0.5)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(i + 1); r.font.name = FONT; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 1.5, y, 11.0, 0.45, t, size=18, bold=True, color=WHITE)
    text(s, 1.5, y + 0.5, 11.0, 0.8, b, size=12, color=RGBColor(0xC9, 0xD3, 0xDE))
rect(s, 0.8, 5.9, 1.2, 0.05, fill=AMBER, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.8, 6.1, 11.5, 0.6, "감사합니다.  두고내리지말아조 · 윤현서 · 최서현 · 윤홍은", size=16, bold=True, color=WHITE)
S_(14, "정리하겠습니다. 피드백을 여섯 가지 설계 결정으로 확정했고, 팬·부저까지의 핵심 흐름을 먼저 완성하며, 검출 정확도나 절감률처럼 아직 실측하지 않은 것은 실측 후에만 말하겠습니다. 감사합니다. 질문과 조언 부탁드립니다. (약 15초)")

# ---------------------------------------------------------------- 노트 + 대본 문서
for i, sl in enumerate(prs.slides, 1):
    if i in SCRIPT:
        sl.notes_slide.notes_text_frame.text = SCRIPT[i]
prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")

import docx
from docx.shared import Pt as DPt
d = docx.Document()
st = d.styles["Normal"]; st.font.name = "맑은 고딕"; st.font.size = DPt(11)
st.element.rPr.rFonts.set(docx.oxml.ns.qn("w:eastAsia"), "맑은 고딕")
d.add_heading("SafeGuard 중간 발표 대본 (10분, 14장)", 0)
d.add_paragraph("시간 배분: 표지 0:20 · 한눈에 0:45 · 피드백 0:45 · 총괄 1:00 · 확정① 1:00 · 확정② 1:00 · 확정③ 0:45 · 확정④ 0:45 · 구현① 1:00 · 구현② 0:45 · 구현③ 1:00 · 현황·계획 0:45 · 질문 1:00 · 마무리 0:15  = 약 10분")
titles = {1: "표지", 2: "SafeGuard 한눈에 보기", 3: "1차 컨설팅 피드백 요약", 4: "피드백 → 설계 확정 (총괄)", 5: "확정 ① 센서 융합 OR/AND", 6: "확정 ② 저전력 범위 + 상태전이", 7: "확정 ③ 필수 시연 + DEMO/REAL", 8: "확정 ④ 성능지표 6개 + UWB 독립전원",
          9: "구현 ① Pi 하드웨어 프로토타입", 10: "구현 ② 카메라·대시보드·로그·Euler", 11: "구현 ③ TwinLab 시뮬레이터", 12: "하드웨어 현황과 향후 계획", 13: "멘토님께 질문 3가지", 14: "마무리"}
for i in range(1, 15):
    d.add_heading(f"슬라이드 {i}. {titles[i]}", level=2)
    d.add_paragraph(SCRIPT[i])
d.add_heading("예상 질문 대비 메모", level=2)
for q in ["Anchor/Tag가 왜 반대인가? → PANS 펌웨어는 거리값을 Tag 셸에 출력하므로 차량측(Pi)이 Tag. 발표 용어는 ‘차량측/보호자측 노드’.",
          "BLE plan B는? → UWB 중단 시 fault 기록·재시도가 기본. BLE 자동전환은 별도 검증 전까지 ‘선택 계획’.",
          "소비전력 절감률이 얼마냐? → 논문 수치는 추정치(50.6%). 이번에는 실측으로 대체, 절감이 안 나오면 그대로 분리 보고.",
          "mmWave로 호흡을 잡았나? → 아직 bring-up 단계. Out-of-Box 데이터 수신 → Vital Signs 적용성 → presence fallback 순으로 검증.",
          "온도를 어떻게 35°C까지 올리나? → 현장은 DEMO MODE 시나리오, 예측오차는 REAL MODE 실측으로 별도."]:
    d.add_paragraph(q, style="List Bullet")
d.save(OUT.replace(".pptx", "_대본.docx"))
print("script docx saved")
