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
# 1. 표지
# =====================================================================
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
text(s, 0.8, 1.0, 7.5, 0.4, "제24회 임베디드SW경진대회  ·  자동차/모빌리티 부문  ·  중간 발표 (멘토링)", size=13, color=RGBColor(0xC9, 0xD3, 0xDE))
text(s, 0.8, 1.55, 7.5, 1.2, "SafeGuard", size=60, bold=True, color=WHITE)
text(s, 0.8, 2.75, 7.5, 1.1, ["UWB · mmWave 융합 기반 다단계 저전력 감지", "능동형 차량 내 잔류 탑승자 보호 시스템"], size=20, color=WHITE, line_spacing=1.2)
rect(s, 0.8, 4.1, 1.2, 0.05, fill=AMBER, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.8, 4.35, 7.5, 0.9, [[("1차 컨설팅 피드백 반영 설계 확정  ·  구현 현황  ·  질의", {"bold": True, "color": AMBER})],
                              "팀 두고내리지말아조   윤현서 · 최서현 · 윤홍은          2026. 09"], size=14, color=WHITE, line_spacing=1.4)
rect(s, 8.5, 1.3, 4.3, 3.6, fill=WHITE, radius=0.04)
picture(s, P("docx/image1.jpeg"), 8.6, 1.4, 4.1, 3.4)
text(s, 8.5, 4.95, 4.3, 0.4, "SafeGuard 동작 개요 (미래모빌리티 논문)", size=10, color=RGBColor(0xC9, 0xD3, 0xDE), align=PP_ALIGN.CENTER)
notes(s, "표지. 오늘은 완성도 나열이 아니라 '피드백을 어떻게 설계 결정으로 바꿨는지'를 중심으로 발표합니다.")

# =====================================================================
# 2. 발표 흐름
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 2, "오늘 발표의 구성", "멘토링 세션이므로 '피드백을 받았습니다'가 아니라 '설계를 이렇게 확정했습니다'까지 보고드립니다")
rect(s, 0.6, 1.5, 12.1, 0.9, fill=AMBER_L, radius=0.05)
text(s, 0.85, 1.55, 11.6, 0.8, [[("핵심 메시지  ", {"bold": True, "color": AMBER_D}), ("다단계 감지 구조는 유지하고, 센서 판단 조건 · 저전력 범위 · 시연 우선순위 · 성능지표를 확정했습니다. ", {}),
                                ("핵심 흐름(UWB → PIR/Camera → mmWave → 35°C 예측 → Fan/Buzzer)을 먼저 완성하고 6개 지표를 실측합니다.", {})]], size=13, anchor=MSO_ANCHOR.MIDDLE)
items = [("컨설팅 피드백 요약", ["긍정 평가 3가지", "보완 요구 8가지"]),
         ("설계 확정 6건", ["센서 융합 OR/AND", "Pi 상시 ON · 이벤트 기반", "시연 범위 · DEMO/REAL", "성능지표 · UWB 독립전원"]),
         ("지금까지 구현한 것", ["논문 프로토타입 (Pi 4B)", "TwinLab 시뮬레이터 결과", "신규 하드웨어 수령 · 설계"]),
         ("향후 계획 · 질문", ["단계별 일정과 담당", "기술 리스크 · fallback", "멘토님께 질문 3가지"])]
for i, (t, b) in enumerate(items):
    x = 0.6 + i * 3.075
    card(s, x, 2.7, 2.9, 3.9, t, b, num=i + 1, size=12.5, title_size=14)
notes(s, "발표 순서 안내. 2~3분.")

# =====================================================================
# 3. 프로젝트 리마인드
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 3, "프로젝트 리마인드: SafeGuard가 하는 일", "보호자 이탈 → 잔류 탑승자 단계적 확인 → 위험 온도 예측 → 능동 대응을 하나의 상태기계로 연결")
# stats
for i, (big, lab) in enumerate([("2~3배", "여름철 차내 온도 상승 배율\n(도로교통공단, 외기 대비)"), ("2026", "Euro NCAP 어린이 잔류 감지(CPD)\n정식 평가 항목 도입"), ("35°C", "SafeGuard 위험 판단 기준\n도달 '예상 시점'을 예측")]):
    x = 0.6 + i * 2.05
    rect(s, x, 1.5, 1.9, 1.55, fill=LIGHT, radius=0.05)
    text(s, x, 1.55, 1.9, 0.7, big, size=28, bold=True, color=AMBER_D, align=PP_ALIGN.CENTER)
    text(s, x + 0.08, 2.25, 1.74, 0.75, lab, size=9.5, color=MUTED, align=PP_ALIGN.CENTER)
chevron_flow(s, 0.6, 3.35, 6.0, 0.75, ["UWB\n5m 이탈", "PIR·Cam\n1차 감지", "mmWave\n존재 검증", "Thermal\n35°C 예측", "Fan·Buzzer\n대응"], size=8.5, first_fill=GREEN, last_fill=RED, adj=0.18)
bullets(s, 0.6, 4.3, 6.0, 2.6, [
    ("기존 방식의 한계:", "단일 센서 의존(조도·가림·정지 대상), 상시 구동으로 대기 전력 부담, 온도 초과 '이후' 반응"),
    ("SafeGuard의 차별점:", "필요한 센서만 순차 활성화하는 Cascading Wake-up + 위험 온도 도달 '이전' 선제 보호"),
    ("검증 방식:", "Raspberry Pi 프로토타입 + 시나리오 기반 시뮬레이터(TwinLab)로 상태 전이·Fail-Safe·에너지 검증"),
], size=12)
framed_picture(s, P("supp/p01_img0.png"), 6.9, 1.5, 5.8, 3.55, caption="보완 후 시스템 아키텍처 (Pi 5 = 판단·예측·로그, ESP32 = 센서 입출력·구동)")
framed_picture(s, P("supp/p01_img1.png"), 6.9, 5.2, 5.8, 1.75, caption="정상 경로(OR)와 mmWave 장애 경로(AND)")
notes(s, "간단히 리마인드만. 아키텍처는 보완설계 보고서 04장 그림.")

# =====================================================================
# 4. 1차 컨설팅 피드백 요약
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 4, "1차 컨설팅 피드백 요약", "작품에 대한 의견(긍정)과 보완사항(8건)을 받았습니다")
rect(s, 0.6, 1.5, 4.6, 5.4, fill=GREEN_L, radius=0.05)
text(s, 0.85, 1.6, 4.2, 0.45, "긍정적으로 평가받은 점", size=15, bold=True, color=GREEN)
bullets(s, 0.8, 2.15, 4.25, 4.6, [
    ("상태기계 연계:", "보호자 이탈 확인 → 잔류 감지 → 위험 온도 예측 → 능동 대응을 하나의 FSM으로 연결하고, 필요한 센서만 순차 활성화"),
    ("다단계 센서 융합:", "UWB → PIR·카메라 → mmWave 단계 사용으로 단일 센서의 오검출·미검출 보완, Thermal RC로 '도달 시점' 예측"),
    ("Fail-Safe 구체화:", "ESP32 독립 워치독, 센서·API 장애별 대체 경로, 과전류 보호 및 비상정지"),
], size=12, gap=8)
rect(s, 5.45, 1.5, 7.25, 5.4, fill=LIGHT, radius=0.05)
text(s, 5.7, 1.6, 6.8, 0.45, "보완이 필요하다고 지적된 점", size=15, bold=True, color=AMBER_D)
fb = ["PIR과 카메라 판단조건이 OR인지 AND인지 계획서·보고서에 혼재. mmWave 장애 시 확정 조건 제시 필요",
      "저전력 Wake-up 구조와 상태전이 조건을 조기에 하나로 확정. 각 단계 소비전력·전환시간 측정",
      "전원 차단 회로가 어려우면 Pi를 계속 구동하되, 성과를 '이벤트 기반 센서·연산 활성화 구조'로 한정",
      "보호자 이탈–탑승자 감지–온도 예측–팬·부저 핵심 흐름 우선 완성. 창문 개방은 추가 기능으로 분리",
      "실차 창문 스위치 서보는 재현성이 낮음 → 투명 모형차 창문 개방 우선",
      "시연 시간 내 온도 상승이 어려움 → 시트 위치별 온도 사전 설정으로 상황 재현",
      "성능지표: 이탈 판정오차 · 검출률/오검출률 · 상태전환시간 · 온도 예측오차 · Fail-Safe 전환 성공률",
      "차량 측 Anchor뿐 아니라 보호자 측 Tag도 독립 전원 필요 (5m 이탈 시험을 위해)"]
for i, f in enumerate(fb):
    y = 2.15 + i * 0.58
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(5.7), Inches(y + 0.08), Inches(0.32), Inches(0.32)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(i + 1); r.font.name = FONT; r.font.size = Pt(10); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 6.12, y, 6.45, 0.55, f, size=11, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "심사 원문 요약. 8개 보완사항이 다음 슬라이드에서 각각 설계 결정으로 이어집니다.")

# =====================================================================
# 5. 피드백 → 설계 확정 총괄
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 5, "피드백 반영 및 설계 확정 (총괄)", "받은 보완사항 → 팀이 확정한 설계 → 실제 구현·검증 방법")
rows = [
    ["PIR/Camera OR냐 AND냐", ("정상 경로는 OR", AMBER_L, INK, True), "PIR 또는 Camera 중 하나가 감지되면 mmWave 검증 단계 진입"],
    ["mmWave 장애 시 확정 방법", ("Fail-Safe에서는 PIR AND Camera", AMBER_L, INK, True), "시간창 내 둘 다 유효 감지 시 SUSPECTED로 보수적 보호 진행, 불충족은 UNKNOWN"],
    ["저전력 Wake-up 구조 불명확", ("Pi 상시 ON, 센서·연산은 이벤트 기반 활성화", AMBER_L, INK, True), "완전 전원차단은 주장하지 않음. 상태별 활성화표 + 전력·에너지 비교"],
    ["상태전이 조건 확정 필요", ("5m 이탈 → 1차 감지 → mmWave → Thermal → Protection", AMBER_L, INK, True), "상태별 timestamp와 전력 측정. 유지시간·평활화는 실측 후 calibration"],
    ["핵심 시연 먼저", ("UWB → PIR/Camera → mmWave → 35°C 예측 → Fan/Buzzer", AMBER_L, INK, True), "창문 서보는 추가 기능으로 분리, 모형차 창문에서 우선"],
    ["온도 상승 재현 어려움", ("DEMO MODE에 사전 설정 온도 시나리오 3종", AMBER_L, INK, True), "성능 평가는 REAL MODE 실측 데이터로 별도 수행"],
    ["정량 성능지표 필요", ("6개 지표군을 실험 계획으로 고정", AMBER_L, INK, True), "거리오차 · 검출률/오검출률 · 전환시간 · 온도오차 · Fail-Safe 성공률 · 전력/에너지"],
    ["보호자측 UWB 독립전원", ("보호자 노드 = 10,000mAh 보조배터리", AMBER_L, INK, True), "차량 노드 = Pi USB 급전. 실제 5m 이탈 시험 수행"],
]
table(s, 0.6, 1.5, 12.1, 5.3, ["받은 보완사항", "중간발표에서 확정한 안", "실제 구현 / 검증"], rows, col_w=[2.6, 4.2, 5.3], size=11, first_bold=True)
notes(s, "이 표가 오늘 발표의 핵심. 각 행을 6~11번 슬라이드에서 상세 설명.")

# =====================================================================
# 6. 확정 1: 센서 융합 조건
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 6, "확정 ① 센서 융합 조건: 정상 OR / 장애 AND", "PIR·Camera는 최종 확정 센서가 아니라 고전력 mmWave 검증 단계로 진입하기 위한 1차 screening 센서")
# 정상 경로
rect(s, 0.6, 1.5, 6.3, 2.35, fill=GREEN_L, radius=0.05); text(s, 0.8, 1.55, 3, 0.35, "정상 경로", size=13, bold=True, color=GREEN)
def node(slide, x, y, w, h, t, fill=NAVY2, color=WHITE, size=10.5):
    r = rect(slide, x, y, w, h, fill=fill, radius=0.12); tf = r.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    for j, ln in enumerate(t.split("\n")):
        p = tf.paragraphs[0] if j == 0 else tf.add_paragraph(); p.alignment = PP_ALIGN.CENTER
        rr = p.add_run(); rr.text = ln; rr.font.name = FONT; rr.font.size = Pt(size); rr.font.bold = (j == 0); rr.font.color.rgb = color
node(s, 0.85, 1.95, 1.1, 0.5, "PIR"); node(s, 0.85, 2.85, 1.1, 0.5, "Camera")
node(s, 2.35, 2.45, 0.85, 0.65, "OR", fill=AMBER)
arrow(s, 1.95, 2.2, 2.35, 2.7); arrow(s, 1.95, 3.1, 2.35, 2.85)
node(s, 3.55, 2.45, 1.3, 0.65, "mmWave\n검증"); arrow(s, 3.2, 2.78, 3.55, 2.78)
node(s, 5.2, 2.45, 1.5, 0.65, "CONFIRMED\n→ Thermal", fill=GREEN); arrow(s, 4.85, 2.78, 5.2, 2.78)
text(s, 0.8, 3.45, 6.0, 0.4, "AND로 하면 카메라(어두움·가림)와 PIR(정지 대상) 중 하나만 놓쳐도 미검출 → OR로 미검출을 줄이는 방향", size=10, color=MUTED)
# 장애 경로
rect(s, 0.6, 4.05, 6.3, 2.85, fill=RED_L, radius=0.05); text(s, 0.8, 4.1, 6.0, 0.35, "mmWave 장애 경로 (timeout · UART fault · USB 소실)", size=13, bold=True, color=RED)
node(s, 0.85, 4.6, 1.4, 0.65, "mmWave\n장애 감지", fill=RED); node(s, 2.6, 4.6, 1.3, 0.65, "FAIL_SAFE"); arrow(s, 2.25, 4.93, 2.6, 4.93)
node(s, 4.25, 4.6, 1.1, 0.65, "PIR AND\nCamera", fill=AMBER); arrow(s, 3.9, 4.93, 4.25, 4.93)
node(s, 5.6, 4.35, 1.2, 0.55, "SUSPECTED\n→ Thermal", fill=GREEN, size=9.5); node(s, 5.6, 5.05, 1.2, 0.55, "UNKNOWN\n경고·재평가", fill=MUTED, size=9.5)
arrow(s, 5.35, 4.8, 5.6, 4.63); arrow(s, 5.35, 5.05, 5.6, 5.3)
text(s, 0.8, 5.75, 6.0, 1.1, [[("발표 문장  ", {"bold": True, "color": RED}), ("“mmWave 장애 상황에서는 PIR과 Camera가 동시에 잔류 가능성을 나타낼 경우 Fail-Safe 조건으로 판단하여 보수적으로 Thermal/Protection 단계로 진행합니다.” ", {}),
                                ("정상은 CONFIRMED, 장애는 SUSPECTED로 구분하고 mmWave 없이 탑승자를 완벽히 확정한다고 말하지 않습니다.", {"color": MUTED})]], size=10.5)
# 진리표
text(s, 7.2, 1.5, 5.5, 0.4, "센서 융합 진리표", size=13, bold=True, color=NAVY)
table(s, 7.2, 1.95, 5.5, 2.6, ["PIR", "Camera", "정상 경로", "mmWave 장애 경로"], [
    ["0", "0", "1차 감지 재평가", ("UNKNOWN, 경고·재평가", None, MUTED)],
    ["1", "0", ("mmWave 검증 진입", GREEN_L, GREEN, True), ("UNKNOWN, 경고·재평가", None, MUTED)],
    ["0", "1", ("mmWave 검증 진입", GREEN_L, GREEN, True), ("UNKNOWN, 경고·재평가", None, MUTED)],
    ["1", "1", ("mmWave 검증 진입", GREEN_L, GREEN, True), ("SUSPECTED → Thermal/Protection", AMBER_L, AMBER_D, True)],
    ["무효", "임의", "무효 입력은 감지 1로 사용 안 함", ("UNKNOWN, 입력 장애 기록", None, MUTED)],
], col_w=[0.7, 0.9, 1.9, 2.0], size=10)
rect(s, 7.2, 4.75, 5.5, 2.15, fill=LIGHT, radius=0.05)
bullets(s, 7.3, 4.85, 5.3, 2.0, [
    ("'동시에'의 정의:", "같은 순간 비트가 아니라 설정된 시간창(fusion_window) 안에 두 감지 증거가 모두 유효"),
    ("Camera=1:", "ROI 내 프레임 차분 면적·연속 프레임 조건 충족 (인물 식별기 아님)"),
    ("UNKNOWN:", "판단 불가일 뿐 '탑승자 없음'이나 '안전'을 뜻하지 않음. 별도 상태가 아닌 FAIL_SAFE 내부 판단 결과"),
    ("검증:", "진리표 4조합 + 유효시간 경계 + stale 입력 + UART 단절을 분리해 예상 전이와 로그 비교"),
], size=10.5)
notes(s, "가장 중요한 확정 사항. 심사에서 OR/AND 혼재를 지적받았으므로 '정상은 OR, 장애는 AND'로 딱 잘라 말한다.")

# =====================================================================
# 7. 확정 2: 저전력 범위 현실화
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 7, "확정 ② 저전력 범위 현실화: Pi 상시 ON + 이벤트 기반 활성화", "‘완전한 저전력 전원관리’가 아니라 ‘이벤트 기반 센서·연산 활성화 구조’로 성과 범위를 정의")
rect(s, 0.6, 1.5, 5.6, 1.5, fill=RED_L, radius=0.05)
text(s, 0.8, 1.55, 5.2, 0.4, "사용하지 않을 표현", size=12, bold=True, color=RED)
bullets(s, 0.75, 1.95, 5.3, 1.0, ["“완전 저전력 전원관리 시스템을 구현했다”", "“mmWave 전원을 껐다 켠다” (실제 전원 차단이 아니면)", "“소비전력이 N% 감소했다” (실측 전)"], size=11, gap=2)
rect(s, 0.6, 3.15, 5.6, 1.5, fill=GREEN_L, radius=0.05)
text(s, 0.8, 3.2, 5.2, 0.4, "사용할 표현", size=12, bold=True, color=GREEN)
bullets(s, 0.75, 3.6, 5.3, 1.0, ["“Raspberry Pi는 상시 구동하고, UWB 이벤트에 따라 Camera/mmWave/연산을 순차 활성화한다”", "“mmWave 검증 및 데이터 처리 루틴을 이벤트 기반으로 활성화한다”", "“상태별 전력과 전환시간을 측정하겠다”"], size=11, gap=2)
rect(s, 0.6, 4.8, 5.6, 2.1, fill=LIGHT, radius=0.05)
text(s, 0.8, 4.85, 5.2, 0.4, "구현 방법", size=12, bold=True, color=NAVY)
bullets(s, 0.75, 5.25, 5.3, 1.6, [
    "모듈별 enable_processing 플래그 / 이벤트 큐로 상태 진입·종료 시 활성화",
    "카메라 스트리밍과 분석 분리, mmWave는 sensorStop/Start 지원 여부 확인 후 미지원 시 ‘검증 연산 비활성’으로 표기",
    "실제 하드웨어 스위칭은 Fan/Buzzer(MOSFET)만. ESP32 딥슬립은 명령 수신을 방해하지 않는 구조 검증 후 확장",
], size=10.5, gap=3)
table(s, 6.5, 1.5, 6.2, 3.6, ["상태", "상시 유지", "단계별 활성화", "절감 주장 범위"], [
    ["STANDBY", "Pi, UWB, ESP32 통신·기본 센서", "고부하 영상·검증 처리 최소화", "대기 처리 부하"],
    ["PRIMARY", "공통 수집·로그", "PIR/Camera 감지 루틴", "영상 처리 시간"],
    ["MMWAVE", "공통 수집·로그", "검증 데이터 처리·선택적 측정 시작", "구현한 제어 수준만"],
    ["THERMAL", "필요 센서·오류 감시", "RC 예측 및 외기 입력 갱신", "예측 계산 비용"],
    ["PROTECTION", "FSM·로그·온도 감시", "Fan/Buzzer 구동", "구동 전력은 별도 집계"],
], col_w=[1.2, 1.8, 2.0, 1.4], size=10, first_bold=True)
rect(s, 6.5, 5.3, 6.2, 1.6, fill=AMBER_L, radius=0.05)
text(s, 6.7, 5.35, 5.8, 0.4, "검증 방법 (심사 질문 ‘소비전력을 뭐로 비교하나’ 대응)", size=12, bold=True, color=AMBER_D)
bullets(s, 6.65, 5.75, 5.9, 1.1, ["동일 하드웨어·시나리오·실행시간에서 All-on 처리군 vs Event-driven 처리군 비교", "평균 전력이 아니라 전체 에너지 E = Σ(V×I×Δt). 12V 입력 전류 직렬 측정 + USB 전력계로 장치별 분리", "보호자 배터리·별도 Pi 전원은 측정 경계를 명시하고 중복 집계하지 않음"], size=10.5, gap=2)
notes(s, "심사 코멘트 '라즈베리파이는 상시 구동시켜야 할 듯'을 그대로 수용. 절감 수치는 실측 후에만 말한다.")

# =====================================================================
# 8. 확정 3: 상태전이 조건 (FSM)
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 8, "확정 ③ 상태전이 조건과 FSM 명세", "정상 경로 순서는 고정, 시간값은 calibration 후 config로 고정 · ESTOP은 모든 구동 명령보다 우선")
table(s, 0.6, 1.5, 7.6, 5.4, ["상태", "수행 작업", "전이 조건"], [
    ["INIT", "장치·설정·출력 초기상태 점검", "필수 입력 준비 → STANDBY / 장애 → FAULT"],
    ["STANDBY", "Pi 유지, UWB 감시", "유효 거리 5m 초과 → DEPARTURE_CHECK"],
    ["DEPARTURE_CHECK", "이탈 유지시간 확인", "연속 유지 충족 → PRIMARY / 불충족 → STANDBY"],
    ["PRIMARY", "PIR·Camera 유효 감지 평가", "OR 참 → MMWAVE / 미감지 → 제한 주기로 재평가"],
    ["MMWAVE", "유효 데이터와 검출 증거 평가", "검출 → THERMAL / 정상 미검출 → PRIMARY / 장애 → FAIL_SAFE"],
    ["FAIL_SAFE", "PIR AND Camera 평가", "AND 참 → SUSPECTED 후 THERMAL / 불충족 → UNKNOWN 경고·재평가"],
    ["THERMAL", "현재 온도와 35°C 도달시간 계산", "위험 조건 → PROTECTION / 미충족 → 감시 지속"],
    ["PROTECTION", "Fan/Buzzer 명령·응답 확인", "해제 조건 충족 → STANDBY / 장애 시 보호 요구·오류 유지"],
    ["FAULT", "필수 입력 이상·통합 오류 기록", "복구·재점검 → 해당 경로 (자동 정상 판정 금지)"],
    ["ESTOP", "구동 레일 차단, 로그 유지", "스위치 복귀 + 수동 재무장 → INIT"],
], col_w=[1.5, 2.6, 3.5], size=10, first_bold=True)
rect(s, 8.5, 1.5, 4.2, 2.55, fill=AMBER_L, radius=0.05)
text(s, 8.7, 1.55, 3.9, 0.4, "이탈 판정 기준: 확정값과 보정값 구분", size=12, bold=True, color=AMBER_D)
bullets(s, 8.65, 1.95, 3.95, 2.1, [("확정:", "보호자 이탈 거리 5m 초과, 위험 온도 35°C"), ("후보값:", "유지시간 10초 · 이동평균 7점 (하드웨어 가이드 초기값)"), ("발표 문장:", "“유지시간과 window는 초기값으로 두고, UWB 거리 실측 결과로 최종 calibration할 예정입니다”")], size=10.5, gap=3)
rect(s, 8.5, 4.2, 4.2, 2.7, fill=LIGHT, radius=0.05)
text(s, 8.7, 4.25, 3.9, 0.4, "통합 전 고정할 전이 규칙", size=12, bold=True, color=NAVY)
bullets(s, 8.65, 4.65, 3.95, 2.2, ["보호자 복귀는 별도 거리 기준·유지시간으로 판정 (이탈과 구분)", "보호 중 해제 조건을 명확히: 한 프레임 미검출로 종료하지 않음", "UNKNOWN은 별도 상태가 아닌 FAIL_SAFE 내부 판단 결과", "OR 미감지 후 제한시간 뒤 mmWave 재검사는 향후 비교 검증 항목 (기본 전이에 미포함)"], size=10.5, gap=3)
notes(s, "상태명은 보완설계 보고서 07장 기준. 논문 프로토타입의 4단계 FSM(STANDBY/DETECT/CONFIRM/PROTECT)을 확장한 것.")

# =====================================================================
# 9. 확정 4: 필수 시연 범위 + DEMO/REAL
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 9, "확정 ④ 필수 시연 범위와 DEMO / REAL MODE 분리", "심사 제안 그대로: UWB 거리 증가 → PIR·카메라 → mmWave → 35°C 도달시간 예측 → 팬·부저를 하나의 필수 시나리오로")
text(s, 0.6, 1.45, 6, 0.35, "필수 시연 시나리오 (한 흐름으로 반복 재현)", size=13, bold=True, color=NAVY)
chevron_flow(s, 0.6, 1.85, 12.1, 0.85, ["보호자 UWB 들고\n5m 이상 이동", "PIR / Camera\n1차 감지 (OR)", "mmWave\n존재 검증", "35°C 도달\n예상시간 예측", "Fan ON", "Buzzer ON"], size=11, first_fill=GREEN, last_fill=RED)
rect(s, 0.6, 2.85, 12.1, 0.55, fill=LIGHT, radius=0.05)
text(s, 0.8, 2.87, 11.7, 0.5, [[("추가 기능(별도 표시): ", {"bold": True, "color": AMBER_D}), ("모형차 창문 개방(서보)은 핵심 시연 뒤에 실행하고 성공/실패를 핵심 시연 성공률과 분리 기록. 실차 창문 스위치 가압은 재현성이 낮아 제외.", {}),
                                ("  장애 대응은 별도 회차에서 mmWave 통신을 차단해 FAIL_SAFE → AND → SUSPECTED 경로를 시연.", {"color": MUTED})]], size=10.5, anchor=MSO_ANCHOR.MIDDLE)
# REAL / DEMO
rect(s, 0.6, 3.6, 5.95, 3.3, fill=BLUE_L, radius=0.05); text(s, 0.8, 3.65, 5.5, 0.4, "REAL MODE — 성능 평가용", size=13, bold=True, color=BLUE)
chevron_flow(s, 0.8, 4.1, 5.55, 0.6, ["SHT31 실측", "외기 정보", "RC + Euler", "35°C 도달시간"], fill=BLUE, size=9.5)
bullets(s, 0.75, 4.85, 5.65, 2.0, ["빈 시험체 가열·냉각 데이터로 R·C·열유입 보정 → 보정용/평가용 실험 분리", "t0 정보만으로 t0+h 온도를 예측해 실제 측정과 비교 (매 시점 재초기화로 오차를 작게 보이게 하지 않음)", "지표: 예측 horizon별 MAE·RMSE, 35°C 도달시간 실제 vs 예측 오차"], size=10.5, gap=3)
rect(s, 6.75, 3.6, 5.95, 3.3, fill=AMBER_L, radius=0.05); text(s, 6.95, 3.65, 5.5, 0.4, "DEMO MODE — 현장 시연용", size=13, bold=True, color=AMBER_D)
for i, (t, d) in enumerate([("Scenario 1", "정상 초기온도"), ("Scenario 2", "기준 근접 온도"), ("Scenario 3", "위험 근접 온도")]):
    x = 6.95 + i * 1.85
    rect(s, x, 4.1, 1.7, 0.75, fill=WHITE, line=LINE, radius=0.08)
    text(s, x, 4.12, 1.7, 0.35, t, size=10.5, bold=True, color=AMBER_D, align=PP_ALIGN.CENTER)
    text(s, x, 4.45, 1.7, 0.35, d, size=10, color=INK, align=PP_ALIGN.CENTER)
bullets(s, 6.9, 4.95, 5.65, 1.9, ["버튼으로 초기온도 시나리오를 바꾸면 35°C 예상 도달시간과 warning level이 즉시 변하는 것을 시연", "화면에 ‘DEMO’와 입력 출처를 표시하고 실제 SHT31 값은 별도 항목에 함께 표시", ("발표 문장:", "“DEMO MODE 입력값은 시연용이며, 온도예측 성능지표는 실제 SHT31 측정 데이터로 별도 검증합니다”")], size=10.5, gap=3)
notes(s, "심사 코멘트: '정해진 온도값을 설정했다도 okay'. 단 시연과 성능평가를 반드시 분리해서 말한다.")

# =====================================================================
# 10. 확정 5: 정량 성능지표
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 10, "확정 ⑤ 정량 성능지표 6개와 측정 계획", "아직 숫자는 없습니다. ‘최종적으로 이렇게 측정하겠습니다’를 확정하는 단계")
metrics = [
    ("보호자 이탈 판정오차", ["줄자 기준 0.5 / 1 / 2 / 3 / 5 / 7 m + 5m 주변 추가 지점, 지점당 20초 × 3회", "Distance MAE, bias·표준편차·결측률, 5m threshold 오판정 횟수", "LOS / NLOS(가림) 조건 분리"]),
    ("탑승자 검출률 · 오검출률", ["있음/없음 × 움직임/정지 × 밝음/어두움 × 가림, 조건별 10회", "Detection Rate = TP/(TP+FN), FPR = FP/(FP+TN)", "사람 검출과 물체 시연 분리"]),
    ("상태전환시간", ["이벤트 입력 → 조건 충족 → 상태 진입 → 명령 → ACK → 실동작 시각을 timestamp로 기록", "UWB→Camera, Camera→mmWave, mmWave→Occupant, Occupant→Fan 구간별 평균·중앙값·최댓값", "설계상 유지시간과 처리 지연 분리"]),
    ("온도 예측오차", ["보정/평가 실험 분리, 고정 horizon별 MAE·RMSE", "35°C 도달시간 실제 vs 예측 오차", "센서 위치·외기·팬 상태 기록, 팬 구동 전후 분리"]),
    ("Fail-Safe 전환 성공률", ["고장 주입: mmWave USB 뽑기 · API 차단 · UWB 중단 · Pi heartbeat 중단, 고장별 10회", "성공 횟수 / 전체 주입 횟수 × 100 (기대 상태·출력·시간 한계 모두 충족)", "고장 감지율·전환율·보호 출력 분리, 복구 시험 포함"]),
    ("전력 · 에너지", ["각 상태 안정 구간 측정, 동일 시나리오로 All-on vs Event-driven 3쌍", "실제 V·I·dt로 전체 에너지 계산, 측정 경계 명시", "멀티미터 순간값만으로 피크를 말하지 않음"]),
]
for i, (t, b) in enumerate(metrics):
    col, row = i % 3, i // 3
    x = 0.6 + col * 4.1; y = 1.5 + row * 2.75
    card(s, x, y, 3.9, 2.6, t, b, num=i + 1, size=10.5, title_size=12.5)
notes(s, "심사 코멘트의 5개 지표 + 컨설팅 Q2(소비전력)를 더해 6개 지표군.")

# =====================================================================
# 11. 확정 6: UWB 독립전원 + Pi/ESP32 역할
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 11, "확정 ⑥ 보호자측 UWB 독립전원과 Pi / ESP32 역할 구분", "‘보호자 Tag도 독립 전원’과 ‘ESP에서 뭐하고 Pi에서 뭐하고 구분’ 두 코멘트에 대한 답")
rect(s, 0.6, 1.5, 5.7, 2.5, fill=LIGHT, radius=0.05)
text(s, 0.8, 1.55, 5.3, 0.4, "UWB 두 노드 구성 (DWM1001-DEV ×2)", size=13, bold=True, color=NAVY)
rect(s, 0.8, 2.0, 2.6, 1.85, fill=BLUE_L, line=None, radius=0.06)
text(s, 0.9, 2.05, 2.4, 0.35, "차량측 UWB Node", size=11.5, bold=True, color=BLUE)
bullets(s, 0.85, 2.4, 2.5, 1.45, ["Raspberry Pi USB 전원", "거리값을 차량에서 직접 수집", "펌웨어상 TAG 모드 (거리 출력 측)"], size=10, gap=2)
rect(s, 3.6, 2.0, 2.6, 1.85, fill=GREEN_L, line=None, radius=0.06)
text(s, 3.7, 2.05, 2.4, 0.35, "보호자측 UWB Node", size=11.5, bold=True, color=GREEN)
bullets(s, 3.65, 2.4, 2.5, 1.45, ["10,000mAh 보조배터리 독립 전원", "보호자가 직접 소지, 5m 이탈 시험", "저전류 자동차단 여부 10분 시험"], size=10, gap=2)
rect(s, 0.6, 4.15, 5.7, 2.75, fill=AMBER_L, radius=0.05)
text(s, 0.8, 4.2, 5.3, 0.4, "질문이 들어오면", size=12, bold=True, color=AMBER_D)
bullets(s, 0.75, 4.6, 5.4, 2.25, [("Anchor/Tag 용어:", "“본 prototype에서는 차량측에서 거리 데이터를 직접 수집하기 위해 차량측 노드를 Tag 모드로 구성했습니다.” 발표에서는 ‘차량측/보호자측 노드’로 표기"),
                                   ("BLE plan B:", "UWB 데이터 중단 시 fault 기록·감시 재시도가 기본. BLE 전환은 별도 구현 검증 전까지 ‘선택 계획’으로만 언급 (미검증 자동전환 주장 금지)"),
                                   ("펌웨어:", "PANS 기본 펌웨어 셸 명령(nmt/nmi/lec)은 실제 보드 도움말과 대조 후 사용")], size=10.5, gap=3)
framed_picture(s, P("hw/guide_fig1.png"), 6.55, 1.5, 6.15, 3.55, caption="하드웨어 연결 개요 (연결 가이드 v1.0 그림 1)")
table(s, 6.55, 5.2, 6.15, 1.7, ["장치", "담당 기능"], [
    ["Raspberry Pi 5 (상시 ON)", "FSM · Camera 프레임 차분 · mmWave UART 파싱 · UWB 거리 파싱 · Thermal RC · 로그/대시보드"],
    ["ESP32 #1 (센서·구동 노드)", "PIR · SHT31 읽기 → JSON telemetry, Fan/Buzzer(MOSFET) · 서보 명령 실행, 비상정지 상태 보고"],
    ["ESP32 #2", "예비. 독립 워치독은 전원·출력 중재 설계 후 확장 검토"],
], col_w=[1.8, 4.35], size=9.5, first_bold=True)
notes(s, "PANS 펌웨어에서는 거리값이 Tag 셸에 출력되므로 차량측이 Tag. 심사 코멘트의 취지(보호자측 독립전원)는 동일하게 충족.")

# =====================================================================
# 12. 지금까지 ① 논문 프로토타입
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 12, "구현 ① Raspberry Pi 하드웨어 프로토타입", "미래모빌리티 논문 단계: Pi 4B + DHT22 + PIR + Pi Camera V2 + 릴레이(팬·DC모터·LED)로 FSM end-to-end 실행 확인")
framed_picture(s, P("docx/image12.png"), 0.6, 1.5, 3.1, 5.4, caption="빵판 기반 프로토타입 (Pi 4B, 릴레이, LCD)")
photos = [("docx/image6.png", "(a) STANDBY: 저전력 대기"), ("docx/image7.png", "(b) DETECT: PIR 잔류자 감지"), ("docx/image9.png", "(d) THERMAL: Euler 예측"), ("docx/image10.png", "(e) PROTECT: 팬·모터·LED 구동")]
for i, (pth, cap) in enumerate(photos):
    x = 3.9 + i * 2.25
    framed_picture(s, P(pth), x, 1.5, 2.1, 3.4, caption=cap, cap_size=8.5)
framed_picture(s, P("video/v1_07.jpg"), 3.9, 5.05, 3.4, 1.85, caption="실제 구동 영상 캡처: 팬 ON + LCD", cap_size=8.5)
rect(s, 7.5, 5.05, 5.2, 1.85, fill=LIGHT, radius=0.05)
bullets(s, 7.6, 5.12, 5.0, 1.75, [("확인한 것:", "PIR·DHT22 입력 → FSM 전이 → 릴레이 출력이 하나의 소프트웨어 시퀀스로 동작. 상태 전이는 log_event()로 기록"),
                                   ("Euler 선제 전이:", "현재 27.8°C에서 35°C 도달 190초 예측 → risk=True → PROTECT 선제 진입"),
                                   ("이번 대회에서 바뀌는 것:", "Pi 5 + ESP32 분리, SHT31, MOSFET 구동, 실제 UWB·mmWave 연결")], size=10, gap=2)
notes(s, "논문 그림 6·8. 사진은 실제 팀 촬영본.")

# =====================================================================
# 13. 지금까지 ② 카메라 · 대시보드 · Euler
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 13, "구현 ② 카메라 검출 · 대시보드 · 선제 예측", "OpenCV 프레임 차분(경량), Flask 웹 대시보드, Thermal RC + Euler 기반 PROTECT 선제 전이")
text(s, 0.6, 1.45, 6, 0.35, "Pi Camera 프레임 차분 기반 움직임 검출", size=12.5, bold=True, color=NAVY)
for i, (pth, cap) in enumerate([("docx/image13.jpg", "기준 프레임 (대상 진입 전)"), ("docx/image14.jpg", "검출 결과 (경계 상자)"), ("docx/image15.jpg", "차분 이진영상 (실루엣)")]):
    framed_picture(s, P(pth), 0.6 + i * 2.1, 1.85, 2.0, 1.85, caption=cap, cap_size=8.5)
bullets(s, 0.6, 3.8, 6.2, 1.0, ["연속 프레임 차분 → 이진화 → 윤곽선 면적 임계값 초과 시 motion=1. 인물 식별이 아닌 움직임 여부 판단에 집중", "이번 대회: 고정 ROI + 연속 프레임 조건으로 조명 변화 오검출 억제, Camera Module 3로 교체"], size=10.5, gap=2)
text(s, 7.0, 1.45, 6, 0.35, "Flask 보호자 웹 대시보드 (실측 온습도 · PIR 반영)", size=12.5, bold=True, color=NAVY)
framed_picture(s, P("docx/image22.png"), 7.0, 1.85, 2.8, 1.85, caption="STANDBY · 잔류자 없음", cap_size=8.5)
framed_picture(s, P("docx/image23.png"), 9.9, 1.85, 2.8, 1.85, caption="PIR 감지 반영", cap_size=8.5)
text(s, 0.6, 4.95, 6, 0.35, "Euler 기반 선제 PROTECT 전이 (FSM demonstration log)", size=12.5, bold=True, color=NAVY)
framed_picture(s, P("docx/image19.png"), 0.6, 5.3, 6.2, 1.6)
rect(s, 7.0, 4.95, 5.7, 1.95, fill=AMBER_L, radius=0.05)
for i, (big, lab) in enumerate([("27.8°C", "현재 측정 온도"), ("190 s", "35°C 도달 예상시간"), ("PROTECT", "risk=True → 선제 전이")]):
    x = 7.15 + i * 1.85
    text(s, x, 5.05, 1.75, 0.6, big, size=20, bold=True, color=AMBER_D, align=PP_ALIGN.CENTER)
    text(s, x, 5.65, 1.75, 0.35, lab, size=9.5, color=MUTED, align=PP_ALIGN.CENTER)
text(s, 7.15, 6.05, 5.4, 0.8, "현재 온도가 35°C보다 낮아도 도달 가능성이 확인되면 보호 동작을 먼저 시작하는 구조를 실제 로그로 확인. 이번 대회에서는 SHT31 + 외기 API 입력으로 확장하고 예측오차를 실측.", size=10, color=INK)
notes(s, "논문 그림 9, 13, 17.")

# =====================================================================
# 14. 지금까지 ③ TwinLab 시뮬레이터
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 14, "구현 ③ TwinLab 시스템 레벨 시뮬레이터", "하드웨어로 반복 재현하기 어려운 예외(mmWave timeout, API 실패 등)를 시나리오로 검증하는 Python 가상 테스트베드 (웹 공개)")
framed_picture(s, P("sim_arch.png"), 0.6, 1.5, 4.3, 3.6, caption="TwinLab 구성: 시나리오·하드웨어 로그·가상 센서 → FSM → 전력 모델 → 리포트")
framed_picture(s, P("docx/image16.png"), 5.05, 1.5, 7.65, 3.6, caption="TwinLab 실행 화면 (Streamlit): 시나리오 입력 · 상태별 에너지 · 모델 비교")
for i, (t, fill, col, b) in enumerate([
    ("Normal Risk", GREEN_L, GREEN, "t=28s 이탈 → t=29s PIR/Camera → t=34s mmWave 5회 연속 → 35°C 도달 77.3s 예측 → t=35s ACTUATOR_CONTROL"),
    ("No Occupant", BLUE_L, BLUE, "PIR=0인데 camera=1로 t=54s mmWave 진입 → 1차 OR의 false positive 가능성을 mmWave 검증 단계가 걸러냄"),
    ("mmWave Timeout", RED_L, RED, "MMWAVE_CHECK 진입 후 6s 무응답 주입 → t=35s FAIL_SAFE 전이. 응답 실패에도 정지하지 않고 보수적 안전 상태로"),
]):
    x = 0.6 + i * 3.1
    rect(s, x, 5.3, 2.95, 1.6, fill=fill, radius=0.05)
    text(s, x + 0.15, 5.33, 2.7, 0.35, t, size=11.5, bold=True, color=col)
    text(s, x + 0.15, 5.68, 2.7, 1.2, b, size=9.5, color=INK)
rect(s, 9.95, 5.3, 2.75, 1.6, fill=LIGHT, radius=0.05)
picture(s, P("docx/image26.png"), 10.05, 5.4, 1.4, 1.4)
text(s, 11.45, 5.45, 1.25, 1.3, "웹 데모 공개\n설치 없이 브라우저에서 시나리오 조작 · 재현", size=9, color=MUTED)
notes(s, "180초 실제 하드웨어 로그도 TwinLab에 입력해 실제 센서 로그가 시뮬레이션에 연동됨을 확인 (논문 표 2, 그림 11·12).")

# =====================================================================
# 15. 지금까지 ④ 에너지 비교 결과
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 15, "구현 ④ 추정 에너지 비교 → 이번엔 실측으로", "논문 결과는 typical power value × duty cycle 기반 추정치. 심사 코멘트대로 실측 전력·에너지 비교로 바꿉니다")
framed_picture(s, P("docx/image24.png"), 0.6, 1.5, 4.0, 2.6, caption="모델별 총 추정 에너지 (Wh)", cap_size=8.5)
framed_picture(s, P("docx/image25.png"), 4.75, 1.5, 4.0, 2.6, caption="All-on 대비 추정 절감률 (%)", cap_size=8.5)
framed_picture(s, P("docx/image21.png"), 8.9, 1.5, 3.8, 2.6, caption="Normal Risk 상태별 추정 에너지", cap_size=8.5)
for i, (big, lab, col) in enumerate([("0.675 Wh", "All-on baseline", MUTED), ("0.496 Wh", "SafeGuard continuous (−26.5%)", BLUE), ("0.334 Wh", "SafeGuard duty-cycle (−50.6%)", GREEN)]):
    x = 0.6 + i * 2.75
    rect(s, x, 4.3, 2.6, 1.1, fill=LIGHT, radius=0.05)
    text(s, x, 4.33, 2.6, 0.6, big, size=22, bold=True, color=col, align=PP_ALIGN.CENTER)
    text(s, x, 4.93, 2.6, 0.4, lab, size=9.5, color=MUTED, align=PP_ALIGN.CENTER)
rect(s, 8.9, 4.3, 3.8, 1.1, fill=AMBER_L, radius=0.05)
text(s, 9.0, 4.35, 3.6, 1.0, [[("시사점  ", {"bold": True, "color": AMBER_D}), ("ACTUATOR_CONTROL 구간이 에너지 대부분 차지 → 센서 wake-up보다 actuator 구동 정책(duty-cycle)이 절감에 더 큰 영향", {})]], size=10, anchor=MSO_ANCHOR.MIDDLE)
rect(s, 0.6, 5.6, 12.1, 1.3, fill=LIGHT, radius=0.05)
text(s, 0.8, 5.65, 11.7, 0.35, "이번 대회에서의 변경", size=12, bold=True, color=NAVY)
bullets(s, 0.75, 6.0, 11.8, 0.9, ["추정 모델 대신 12V 입력 전류(테스터기 직렬) + USB 전력계로 상태별 실측 → E=Σ(V×I×Δt), All-on vs Event-driven 동일 시나리오 3쌍 비교", "실제 절감이 확인되지 않으면 ‘활성화 제어 구현’과 ‘소비전력 결과’를 분리해서 그대로 발표 (절감률 선언 금지)"], size=10.5, gap=2)
notes(s, "논문 그림 16·18·19. 수치는 추정치임을 반드시 강조.")

# =====================================================================
# 16. 하드웨어 구현 현황
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 16, "현재 하드웨어 구현 현황 (2026-09-12 기준)", "지원 장비 36품목 수령 완료 → 3인 블록 분담으로 단독 검증 시작")
framed_picture(s, P("hw/parts_map.png"), 0.6, 1.5, 6.3, 4.1, caption="수령 부품 지도 (부품 식별·배선 그림책 v1.0) — 블록 B(빨강) · C(초록) · A(주황) · 공용")
table(s, 7.1, 1.5, 5.6, 4.1, ["블록 / 담당", "범위", "상태"], [
    ["A  전원·구동·ESP32", "12V 전원 트리, 퓨즈·비상정지, MOSFET Fan/Buzzer, 서보, PIR·SHT31, ESP32 telemetry", ("장비 수령 · Arduino IDE/ESP32 보드 패키지 세팅 중", AMBER_L, AMBER_D, True)],
    ["B  Pi 5·Camera·mmWave", "Pi OS·SSH, 22핀 CSI 카메라, IWR6843ISK-ODS 플래싱·UART 수신", ("Pi Imager로 OS 이미징 중 (Wi-Fi·SSH 설정)", AMBER_L, AMBER_D, True)],
    ["C  UWB 2노드", "차량측/보호자측 역할 설정, 보조배터리, 거리 오차표, Pi 파서", ("착수 예정 (펌웨어·명령 대조 후)", LIGHT, MUTED, True)],
    ["통합", "GND 공통, USB 3개, 전원 투입 순서, 통합 체크리스트 12항목", ("A/B/C 완료 조건 충족 후", LIGHT, MUTED, True)],
], col_w=[1.6, 2.4, 1.6], size=9.5, first_bold=True)
rect(s, 0.6, 5.75, 12.1, 1.15, fill=LIGHT, radius=0.05)
text(s, 0.8, 5.8, 11.7, 0.35, "설계 산출물 (팀 공유 완료)", size=12, bold=True, color=NAVY)
bullets(s, 0.75, 6.15, 11.8, 0.75, ["하드웨어 연결 가이드 v1.0 (18쪽): 전원 트리 · MOSFET 회로 · ESP32 핀맵 · 블록별 절차와 완료 조건 표 · 통합 순서 · 소비전력 측정표", "부품 식별·배선 그림책 (8쪽) · 보완설계 및 구현실행보고서 (21쪽): FSM 명세, 진리표, 통신 계약(JSON), 시험 계획, 리스크·fallback"], size=10.5, gap=2)
notes(s, "상태 칸은 발표 당일 실제 진행 상황에 맞게 수정. 추가 구매 필요 항목: Pi 5용 22핀 카메라 케이블, micro-USB 데이터 케이블 4개, 벤치용 12V 어댑터.")

# =====================================================================
# 17. 하드웨어 설계: 전원·구동 회로
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 17, "하드웨어 설계 확정: 전원·구동부 (블록 A 배선)", "12V 구동부와 5V/3.3V 로직부 분리, GND만 공통 · 비상정지는 구동 레일만 차단하고 Pi 로그는 유지")
framed_picture(s, P("hw/wiring_A.png"), 0.6, 1.5, 7.7, 5.4, caption="블록 A 배선 그림 (빨강 12V · 주황 5V · 파랑 3.3V 신호 · 검정 GND)")
cards = [("전원 경로", "12V 입력 → 메인 퓨즈 10A → [컨버터#1 → Pi 5 USB-C, 항상 ON] / [비상정지 NC → 퓨즈 5A → 12V 구동 레일]"),
         ("구동단", "IRLZ44N 로우사이드 MOSFET 2채널 (Q1 팬 2개 병렬, Q2 부저), 220Ω 게이트 + 10kΩ 풀다운, 1N5819 프리휠"),
         ("서보(선택)", "구동 레일 → 컨버터#2 5V 전용 급전. 보드 5V 핀 급전 금지, 핵심 회로와 독립"),
         ("확인 필요", "IRLZ44N 3.3V 구동 적합성 · 다이오드 전류 정격 · 퓨즈 10A/5A 적정성은 실물·데이터시트 대조 후 확정")]
for i, (t, b) in enumerate(cards):
    y = 1.5 + i * 1.37
    rect(s, 8.5, y, 4.2, 1.25, fill=AMBER_L if i == 3 else LIGHT, radius=0.05)
    text(s, 8.65, y + 0.05, 3.9, 0.35, t, size=11.5, bold=True, color=AMBER_D if i == 3 else NAVY)
    text(s, 8.65, y + 0.4, 3.9, 0.85, b, size=10, color=INK)
notes(s, "가이드 4장. 브레드보드 검증 후 만능기판 이관.")

# =====================================================================
# 18. 향후 계획
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 18, "향후 구현 일정: 단계별 통과 조건으로 운영", "마감일을 임의로 정하지 않고, 각 단계의 완료 산출물이 나와야 다음 단계 진입")
steps = ["0 준비", "1 단독", "2 통합", "3 FSM", "4 장애", "5 성능", "6 시연", "7 추가"]
chevron_flow(s, 0.6, 1.5, 12.1, 0.7, steps, size=10.5, first_fill=GREEN, last_fill=MUTED)
tag(s, 0.6, 2.3, 2.9, "현재 위치: 0단계 → 1단계 진입", fill=GREEN, size=10)
table(s, 0.6, 2.75, 12.1, 4.15, ["단계", "담당", "실행 항목", "완료 산출물"], [
    ["0 준비", "공동", "부품 실물·버전·추가 케이블·전원 확인 (인벤토리 36항목)", "인벤토리 체크표, 미확인 연결 목록"],
    ["1 단독", "A / B / C 분담", "A 전원·입출력, B 영상·레이더 bring-up, C 두 노드 거리 출력", "블록별 완료 조건 표 · 원시 로그 · 배선 사진"],
    ["2 통합", "공동", "전원 → USB → 데이터 계약(JSON) → 시간축 통합, udev 고정 이름", "통합 로그, 장치 식별표"],
    ["3 FSM", "Pi 제어 + ESP32", "무구동 FSM → 구동 FSM, DEMO/REAL 분리, 진리표 시험", "정상 경로 · 진리표 시험 로그"],
    ["4 장애", "모듈 담당 공동", "mmWave USB 소실 · API 차단 · UWB 중단 · 비상정지 주입", "고장별 결과·복구 기록"],
    ["5 성능", "실험·분석 분담", "거리·검출·지연·전력·온도 6개 지표군 측정", "조건별 지표, 실패 사례"],
    ["6 시연 고정", "전원·시연·화면", "입력·설정·순서 고정, 반복 리허설", "실행 config · 영상 · 시연 대본"],
    ["7 추가", "가용 인원", "모형 창문 서보, 독립 워치독 확장 검토", "핵심과 분리한 시험 기록"],
], col_w=[1.2, 1.6, 5.2, 4.1], size=10, first_bold=True)
notes(s, "의존성: B의 mmWave 기본 수신과 C의 두 노드 거리 출력이 감지 통합의 선행 조건. 전원부 검수 전 통합 전원 인가 금지.")

# =====================================================================
# 19. 기술 리스크 & fallback
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 19, "기술 리스크와 fallback", "fallback은 검증 수준을 낮춘다는 뜻이 아니라, 대체 기능의 시험 조건·출력 의미·성과 범위를 함께 바꾼다는 뜻")
table(s, 0.6, 1.5, 12.1, 5.4, ["리스크", "영향", "대응 · fallback", "발표에서 지킬 한계"], [
    ["mmWave Vital Signs 호환·신호 불안정", "호흡 기반 검증 지연", "지원 펌웨어 확인 → Out-of-Box 데이터 수신 먼저 → Vital Signs 적용성 검토 → presence/미세 움직임 fallback", "호흡 검출 완료라고 말하지 않음"],
    ["point cloud가 물체에도 반응", "탑승자 오검출", "빈 좌석·팬·외부 움직임·ROI 시험, 지속성 조건", "데이터 수신 = 생명체 확인이 아님"],
    ["UWB 거리 불안정 (멀티패스·가림)", "이탈/복귀 오판정", "LOS/NLOS 시험, 필터·유지시간 보정, 복도·야외 측정", "5m 기준의 오차·결측 공개"],
    ["보조배터리 저전류 자동 꺼짐", "보호자 노드 소실", "10분 유지 시험, 저전류 모드·다른 전원, 더미 부하", "LiPo 직결은 확인 전 미적용"],
    ["USB·구동 전원 부족", "Pi 리셋·데이터 단절", "공식 27W 전원, usb_max_current_enable, powered hub 검토", "설정값만으로 해결 단정 금지"],
    ["API·온도 입력 장애", "예측 무효", "유효 캐시 → 만료 시 SHT31 실측 반응형 제어, 온도도 무효면 fault", "가정 입력을 실측으로 표기 금지"],
    ["RC 모델 이전성 (모형 ↔ 실차)", "예측오차 차이", "시험체별 보정·평가, 팬 구동 전후 분리", "모형 오차를 실차 성능으로 확장 금지"],
], col_w=[2.5, 1.7, 5.0, 2.9], size=10, first_bold=True)
notes(s, "보완설계 보고서 18장.")

# =====================================================================
# 20. 멘토님께 질문
# =====================================================================
s = prs.slides.add_slide(BLANK); header(s, 20, "멘토님께 여쭙고 싶은 것 3가지", "설계 확정 과정에서 팀이 판단하기 어려웠던 지점")
qs = [
    ("mmWave: 호흡(Vital Signs) vs 존재(presence) 검출",
     "IWR6843ISK-ODS는 오버헤드(천장) 장착용 안테나입니다. 계획서는 호흡 검출을 목표로 했지만, 실내 시연 조건에서 Vital Signs 랩이 불안정할 가능성이 있습니다.",
     "① ODS 천장 장착 조건에서 호흡 검출까지 가는 것이 현실적인지, 아니면 처음부터 presence/미세 움직임 검출을 잔류 검증 신호로 확정하는 것이 심사 관점에서 더 안전한지 ② point cloud 기반일 때 ‘생명체 확인’으로 인정받으려면 어떤 조건(지속시간·ROI·빈 좌석 대조)을 갖추면 되는지"),
    ("소비전력 비교: 측정 경계와 계측 수준",
     "Pi 상시 ON 구조에서 All-on 처리군 vs Event-driven 처리군의 에너지 E=Σ(V×I×Δt)를 비교할 계획입니다. Pi는 별도 5V 전원, 구동부는 12V, 보호자 노드는 배터리로 전원 경계가 나뉩니다.",
     "① 12V 입력 전류(테스터기 직렬) + USB 인라인 전력계 수준이면 충분한지, 전력 로거가 필요한지 ② ‘current metadata’ 기준으로 상태별 전환시간과 전력을 표로 낼 때 심사에서 기대하는 최소 형식(평균/피크/에너지)은 무엇인지"),
    ("온도 시연과 고려 범위",
     "현장에서는 DEMO MODE(정상·근접·위험 초기온도 3종)로 35°C 도달시간 변화를 보이고, 예측오차는 REAL MODE 실측으로 별도 평가합니다. 좌석별·외부(창문/트렁크) 온도는 보고서에만 상세 기술할 예정입니다.",
     "① 시연(DEMO)과 성능평가(REAL)를 분리해 제시하는 방식이 최종 심사에서 감점 없이 인정되는지 ② 좌석별 온도 차이는 시연 없이 보고서·안내문으로만 다뤄도 되는지, 최소한 몇 개 지점의 실측이 있어야 설득력이 있는지"),
]
for i, (t, bg, q) in enumerate(qs):
    y = 1.5 + i * 1.82
    rect(s, 0.6, y, 12.1, 1.7, fill=LIGHT, radius=0.05)
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(y + 0.2), Inches(0.55), Inches(0.55)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = f"Q{i+1}"; r.font.name = FONT; r.font.size = Pt(13); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 1.55, y + 0.1, 10.9, 0.4, t, size=13.5, bold=True, color=NAVY)
    text(s, 1.55, y + 0.5, 4.3, 1.15, [[("배경  ", {"bold": True, "color": MUTED}), (bg, {"color": MUTED})]], size=9.5)
    text(s, 6.0, y + 0.5, 6.55, 1.15, [[("질문  ", {"bold": True, "color": AMBER_D}), (q, {})]], size=9.5)
notes(s, "추가로 시간이 되면: UWB 차량측 Tag 구성이 괜찮은지, BLE plan B는 어디까지만 준비하면 되는지.")

# =====================================================================
# 21. 마무리
# =====================================================================
s = prs.slides.add_slide(BLANK)
s.background.fill.solid(); s.background.fill.fore_color.rgb = NAVY
text(s, 0.8, 0.9, 11.5, 0.5, "정리", size=14, color=AMBER, bold=True)
msgs = [("피드백 → 설계 확정 6건", "정상 OR / 장애 AND · Pi 상시 ON + 이벤트 기반 활성화 · FSM 명세 · 필수 시연 범위 · DEMO/REAL 분리 · 6개 정량 지표 · 보호자 UWB 독립전원"),
        ("핵심 흐름을 먼저 완성", "UWB 5m 이탈 → PIR/Camera → mmWave → 35°C 도달시간 예측 → Fan/Buzzer. 창문 서보와 워치독은 추가 기능으로 분리"),
        ("말할 수 있는 것과 없는 것을 구분", "‘OR/AND를 구분해 구현하겠습니다’ · ‘상태별 전력·전환시간을 측정하겠습니다’ · ‘Vital Signs 적용 가능성을 검증하겠습니다’ — 검출 정확도 확보·절감률·호흡 검출 완료는 실측 후에만")]
for i, (t, b) in enumerate(msgs):
    y = 1.55 + i * 1.45
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(y + 0.1), Inches(0.5), Inches(0.5)); rgb(c.fill, AMBER); c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; r = p.add_run(); r.text = str(i + 1); r.font.name = FONT; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = WHITE
    text(s, 1.5, y, 11.0, 0.45, t, size=18, bold=True, color=WHITE)
    text(s, 1.5, y + 0.5, 11.0, 0.8, b, size=12, color=RGBColor(0xC9, 0xD3, 0xDE))
rect(s, 0.8, 6.0, 1.2, 0.05, fill=AMBER, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.8, 6.2, 11.5, 0.6, "감사합니다.  두고내리지말아조 · 윤현서 · 최서현 · 윤홍은", size=16, bold=True, color=WHITE)
notes(s, "질의응답.")

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
