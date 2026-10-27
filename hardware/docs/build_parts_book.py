# -*- coding: utf-8 -*-
"""SafeGuard 부품 식별·배선 그림책 PDF 생성기."""
import sys, math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, KeepTogether)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon, Circle, Ellipse, Wedge, Path

OUT = sys.argv[1] if len(sys.argv) > 1 else "parts_book.pdf"
pdfmetrics.registerFont(TTFont("NG", r"C:\Windows\Fonts\NanumGothic.ttf"))
pdfmetrics.registerFont(TTFont("NGB", r"C:\Windows\Fonts\NanumGothicBold.ttf"))
pdfmetrics.registerFontFamily("NG", normal="NG", bold="NGB", italic="NG", boldItalic="NGB")

HEAD = colors.HexColor("#2C3E50"); GRAY = colors.HexColor("#555555"); LIGHT = colors.HexColor("#F2F3F4")
BLK = {"A": colors.HexColor("#B9770E"), "B": colors.HexColor("#C0392B"), "C": colors.HexColor("#1E8449"),
       "공용": colors.HexColor("#5D6D7E"), "통합": colors.HexColor("#5D6D7E")}
PCB = colors.HexColor("#1E8449"); PCB_D = colors.HexColor("#145A32"); PCB_BLUE = colors.HexColor("#1F618D")
BLACK = colors.HexColor("#222222"); METAL = colors.HexColor("#AEB6BF"); GOLD = colors.HexColor("#D4AC0D")
RED = colors.HexColor("#E74C3C"); YEL = colors.HexColor("#F4D03F"); WHITE = colors.white
WIRE_R = colors.HexColor("#E74C3C"); WIRE_K = colors.HexColor("#222222"); WIRE_O = colors.HexColor("#F39C12")
WIRE_Y = colors.HexColor("#F1C40F"); WIRE_B = colors.HexColor("#2E86C1"); WIRE_G = colors.HexColor("#27AE60")

S = {
 "title": ParagraphStyle("t", fontName="NGB", fontSize=22, leading=30, alignment=TA_CENTER, textColor=HEAD),
 "sub": ParagraphStyle("s", fontName="NG", fontSize=11, leading=16, alignment=TA_CENTER, textColor=GRAY),
 "h1": ParagraphStyle("h1", fontName="NGB", fontSize=16, leading=22, spaceBefore=8, spaceAfter=6, textColor=HEAD),
 "h2": ParagraphStyle("h2", fontName="NGB", fontSize=12, leading=16, spaceBefore=8, spaceAfter=4, textColor=HEAD),
 "p": ParagraphStyle("p", fontName="NG", fontSize=9.5, leading=14, spaceAfter=4),
 "bul": ParagraphStyle("b", fontName="NG", fontSize=9.5, leading=14, leftIndent=12, bulletIndent=2, spaceAfter=2),
 "cname": ParagraphStyle("cn", fontName="NGB", fontSize=10, leading=13, textColor=HEAD),
 "cell": ParagraphStyle("c", fontName="NG", fontSize=8, leading=11),
 "note": ParagraphStyle("n", fontName="NG", fontSize=9, leading=13, backColor=colors.HexColor("#FEF9E7"),
                        borderColor=colors.HexColor("#F1C40F"), borderWidth=0.8, borderPadding=5, spaceBefore=4, spaceAfter=8),
}
story = []
def H1(t): story.append(Paragraph(t, S["h1"]))
def H2(t): story.append(Paragraph(t, S["h2"]))
def P(t): story.append(Paragraph(t, S["p"]))
def BUL(items):
    for it in items: story.append(Paragraph(it, S["bul"], bulletText="•"))
def NOTE(t): story.append(Paragraph("<b>참고</b> " + t, S["note"]))

W, H = A4
def on_page(canv, doc):
    canv.saveState(); canv.setFont("NG", 8); canv.setFillColor(GRAY)
    canv.drawString(15*mm, 10*mm, "SafeGuard 부품 식별·배선 그림책 v1.0  |  팀 두고내리지말아조  |  2026-09-12")
    canv.drawRightString(W-15*mm, 10*mm, f"{doc.page}")
    canv.setStrokeColor(colors.HexColor("#D5D8DC")); canv.line(15*mm, 14*mm, W-15*mm, 14*mm); canv.restoreState()
doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=14*mm, bottomMargin=18*mm,
                      title="SafeGuard 부품 식별·배선 그림책 v1.0", author="두고내리지말아조")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=on_page)])
CW = doc.width

# ---------------------------------------------------------------- 그리기 도우미
def T(d, x, y, s, size=7, bold=False, color=BLACK, anchor="middle"):
    d.add(String(x, y, s, fontName="NGB" if bold else "NG", fontSize=size, fillColor=color, textAnchor=anchor))
def R(d, x, y, w, h, fill, stroke=None, sw=0.6, rx=2):
    d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=stroke or fill, strokeWidth=sw, rx=rx, ry=rx))
def C(d, cx, cy, r, fill, stroke=None, sw=0.6):
    d.add(Circle(cx, cy, r, fillColor=fill, strokeColor=stroke or fill, strokeWidth=sw))
def L(d, x1, y1, x2, y2, color=BLACK, sw=1):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=sw))
def pins(d, x, y, n, dx=4, vertical=False, r=1.1, fill=GOLD):
    for i in range(n):
        if vertical: C(d, x, y + i*dx, r, fill, BLACK, 0.3)
        else: C(d, x + i*dx, y, r, fill, BLACK, 0.3)
def label_arrow(d, x1, y1, x2, y2, text, size=6, color=HEAD):
    L(d, x1, y1, x2, y2, color, 0.7)
    T(d, x1, y1 + (2 if y1 >= y2 else -7), text, size, True, color, "middle")

# ---------------------------------------------------------------- 아이콘 (각 함수는 0..150 x 0..95 박스 기준)
def ic_pi(d):
    R(d, 15, 12, 120, 75, PCB, PCB_D, 1, 4)
    R(d, 118, 60, 20, 12, METAL, BLACK, 0.4, 1); R(d, 118, 42, 20, 12, METAL, BLACK, 0.4, 1)      # USB
    R(d, 118, 18, 20, 18, METAL, BLACK, 0.4, 1)                                                     # 이더넷
    R(d, 18, 12, 14, 8, METAL, BLACK, 0.4, 1); T(d, 25, 4, "USB-C 전원", 5.5)
    R(d, 40, 12, 12, 6, BLACK); T(d, 46, 4, "micro HDMI ×2", 5.5); R(d, 56, 12, 12, 6, BLACK)
    R(d, 76, 12, 6, 14, WHITE, BLACK, 0.4, 1); R(d, 86, 12, 6, 14, WHITE, BLACK, 0.4, 1); T(d, 84, 28, "CAM0 CAM1", 5, True)
    R(d, 45, 45, 40, 30, colors.HexColor("#333333"), BLACK, 0.4, 1); T(d, 65, 58, "BCM2712", 5, False, WHITE)
    for i in range(20): C(d, 22 + i*4.8, 84, 1, GOLD, BLACK, 0.3); C(d, 22 + i*4.8, 80, 1, GOLD, BLACK, 0.3)
    T(d, 70, 90, "GPIO 40핀 (이번 설계에서는 사용 안 함)", 5.5, False, GRAY)
    T(d, 128, 76, "USB ×4", 5.5); T(d, 128, 12, "LAN", 5.5)
    R(d, 15, 40, 4, 10, BLACK); T(d, 8, 43, "SD", 5)
def ic_camera(d):
    R(d, 40, 30, 40, 40, PCB, PCB_D, 1, 3); C(d, 60, 50, 11, BLACK); C(d, 60, 50, 6, colors.HexColor("#1B4F72")); C(d, 58, 52, 2, WHITE)
    R(d, 82, 25, 55, 10, colors.HexColor("#F5B041"), BLACK, 0.4, 0); R(d, 130, 22, 8, 16, colors.HexColor("#2E86C1"))
    T(d, 108, 14, "리본 케이블 (Pi 5는 22핀 mini 필요)", 5.5); T(d, 60, 76, "렌즈 (imx708)", 6, True)
def ic_mmwave(d):
    R(d, 20, 15, 110, 65, PCB_BLUE, BLACK, 1, 3)
    R(d, 28, 40, 45, 32, colors.HexColor("#D6EAF8"), BLACK, 0.4, 1)
    for i in range(3):
        for j in range(4): R(d, 31 + j*10, 44 + i*9, 7, 6, GOLD)
    T(d, 50, 34, "안테나 패치(ODS)", 5.5, True)
    R(d, 20, 55, 10, 8, METAL, BLACK, 0.4, 1); T(d, 8, 66, "micro", 5); T(d, 8, 60, "USB", 5)
    R(d, 90, 20, 20, 10, BLACK); T(d, 100, 12, "SOP 스위치 S1", 5.5, True)
    R(d, 80, 55, 40, 20, colors.HexColor("#333333")); T(d, 100, 63, "XDS110", 5, False, WHITE)
    T(d, 75, 86, "IWR6843ISK-ODS  (파란 PCB, 60GHz)", 6, True)
def ic_uwb(d):
    R(d, 30, 15, 90, 60, PCB, PCB_D, 1, 3)
    R(d, 30, 55, 10, 8, METAL, BLACK, 0.4, 1); T(d, 20, 66, "micro", 5); T(d, 20, 60, "USB", 5)
    R(d, 45, 40, 25, 25, colors.HexColor("#333333")); T(d, 57, 50, "DWM1001", 4.5, False, WHITE)
    R(d, 95, 45, 18, 22, WHITE, BLACK, 0.4, 1); T(d, 104, 70, "UWB 안테나", 5.5, True)
    pins(d, 33, 20, 12, 5); T(d, 60, 24, "확장핀 (미사용)", 5)
    R(d, 115, 18, 6, 8, WHITE, BLACK, 0.4, 1); T(d, 120, 12, "JST 배터리(미사용)", 5)
    T(d, 75, 84, "2개 동일 — 라벨로 '차량측/보호자측' 구분", 6, True)
def ic_esp32(d):
    R(d, 30, 20, 95, 50, BLACK, GRAY, 0.6, 3)
    R(d, 36, 30, 35, 30, METAL, GRAY, 0.5, 1); T(d, 53, 43, "WROOM-32D", 4.5, False, BLACK); T(d, 53, 36, "(은색 캔)", 4.5, False, BLACK)
    pins(d, 36, 70, 19, 4.6); pins(d, 36, 20, 19, 4.6)
    R(d, 120, 38, 8, 12, METAL, BLACK, 0.4, 1); T(d, 138, 50, "micro", 5); T(d, 138, 44, "USB", 5)
    R(d, 108, 62, 8, 5, BLACK, GRAY); T(d, 112, 74, "EN", 5); R(d, 108, 24, 8, 5, BLACK, GRAY); T(d, 112, 14, "BOOT", 5)
    T(d, 75, 80, "핀 라벨(GPIO 번호)이 보드 뒷면/옆에 인쇄됨", 5.5)
def ic_sht31(d):
    R(d, 45, 30, 50, 40, PCB, PCB_D, 1, 3); R(d, 62, 45, 12, 12, METAL, BLACK, 0.4, 1); C(d, 68, 51, 2, WHITE)
    pins(d, 50, 34, 4, 10);
    for i, n in enumerate(["VCC", "GND", "SDA", "SCL"]): T(d, 50 + i*10, 24, n, 5, True)
    T(d, 70, 78, "SHT31 온습도 (손톱 크기, 4핀)", 6, True)
def ic_pir(d):
    R(d, 45, 25, 55, 40, PCB, PCB_D, 1, 3); C(d, 72, 52, 13, WHITE, GRAY, 0.5); C(d, 72, 52, 9, colors.HexColor("#FBFCFC"), GRAY, 0.3)
    T(d, 72, 20, "흰색 돔 렌즈", 5.5, True)
    pins(d, 52, 29, 3, 12)
    for i, n in enumerate(["VCC", "GND", "OUT"]): T(d, 52 + i*12, 12, n, 5, True)
    T(d, 72, 78, "PIR EKMC4607112K (SparkFun 빨간 PCB일 수 있음)", 5.5, True)
def ic_mosfet(d):
    R(d, 55, 50, 40, 30, METAL, BLACK, 0.5, 1); C(d, 75, 72, 4, WHITE, BLACK, 0.5)
    R(d, 55, 28, 40, 26, BLACK, BLACK, 0.5, 1); T(d, 75, 38, "IRLZ44N", 5, True, WHITE)
    for i, n in enumerate(["G", "D", "S"]):
        R(d, 62 + i*12, 8, 3, 20, METAL); T(d, 63.5 + i*12, 1, n, 6, True)
    T(d, 118, 60, "금속 방열탭", 5.5); T(d, 118, 54, "(=드레인)", 5)
    T(d, 30, 40, "표식면을", 5.5); T(d, 30, 34, "정면으로", 5.5)
    T(d, 75, 88, "TO-220 (검정 몸통 + 은색 탭, 다리 3개)", 6, True)
def ic_diode(d):
    R(d, 45, 40, 60, 18, colors.HexColor("#333333"), BLACK, 0.5, 4); R(d, 88, 40, 8, 18, METAL)
    L(d, 15, 49, 45, 49, METAL, 2); L(d, 105, 49, 135, 49, METAL, 2)
    T(d, 92, 64, "띠 = 캐소드(−)", 5.5, True); T(d, 92, 30, "→ +12V 쪽으로", 5.5)
    T(d, 30, 30, "애노드(+)", 5.5); T(d, 75, 80, "1N5819 쇼트키 (작은 검정 원통, 은색 띠)", 6, True)
def ic_resistor(d):
    R(d, 45, 42, 60, 14, colors.HexColor("#F5CBA7"), BLACK, 0.4, 5)
    for i, c in enumerate([RED, RED, colors.HexColor("#8B4513"), GOLD]): R(d, 52 + i*11, 42, 4, 14, c)
    L(d, 15, 49, 45, 49, METAL, 1.5); L(d, 105, 49, 135, 49, METAL, 1.5)
    T(d, 75, 30, "색띠로 값 읽기: 220Ω=빨빨갈,  10kΩ=갈검주", 5.5)
    T(d, 75, 78, "막대저항 (샘플키트에서 골라 쓰기)", 6, True)
def ic_buzzer(d):
    C(d, 70, 50, 24, BLACK, GRAY, 0.5); C(d, 70, 50, 6, colors.HexColor("#444444")); T(d, 82, 68, "+", 8, True, WHITE)
    L(d, 60, 26, 45, 8, WIRE_R, 2); L(d, 80, 26, 95, 8, WIRE_K, 2); T(d, 40, 2, "빨강 +", 5.5, True); T(d, 100, 2, "검정 −", 5.5, True)
    T(d, 70, 84, "12V 능동 부저 (검정 원통, 선 2가닥)", 6, True)
def ic_fan(d, big=True):
    s = 60 if big else 46
    R(d, 75 - s/2, 48 - s/2, s, s, BLACK, GRAY, 0.6, 4)
    for i in range(7):
        a = i*360/7
        d.add(Wedge(75, 48, s*0.42, a, a+30, fillColor=colors.HexColor("#5D6D7E"), strokeColor=None))
    C(d, 75, 48, s*0.15, BLACK)
    L(d, 75 + s/2, 40, 130, 25, WIRE_R, 1.5); L(d, 75 + s/2, 36, 130, 18, WIRE_K, 1.5)
    T(d, 138, 25, "+", 6, True); T(d, 138, 17, "−", 6, True)
    T(d, 75, 88, "120mm LED 팬 (큰 것)" if big else "108F 12V 팬 (작은 것)", 6, True)
    if big: T(d, 75, 5, "3·4핀 커넥터면 노랑/파랑 선은 미사용", 5.5)
def ic_servo(d):
    R(d, 45, 25, 50, 40, BLACK, GRAY, 0.6, 3); R(d, 38, 55, 64, 6, BLACK); C(d, 60, 65, 6, WHITE, BLACK, 0.5)
    R(d, 30, 62, 45, 5, WHITE, BLACK, 0.5, 2); T(d, 60, 74, "혼(팔)", 5.5)
    L(d, 95, 35, 135, 35, colors.HexColor("#8B4513"), 2); L(d, 95, 40, 135, 40, WIRE_R, 2); L(d, 95, 45, 135, 45, WIRE_O, 2)
    T(d, 140, 33, "갈 GND", 5, True, BLACK, "start"); T(d, 140, 38, "빨 5V", 5, True, BLACK, "start"); T(d, 140, 43, "주 신호", 5, True, BLACK, "start")
    T(d, 75, 12, "DS3218 (금속 기어, 무거움, 선 3가닥)", 6, True)
def ic_estop(d):
    C(d, 70, 48, 26, YEL, BLACK, 0.5); C(d, 70, 50, 18, RED, colors.HexColor("#922B21"), 0.8); T(d, 70, 47, "STOP", 5, True, WHITE)
    R(d, 105, 30, 30, 36, BLACK, GRAY, 0.5, 2); C(d, 112, 60, 2, METAL); C(d, 128, 60, 2, METAL); C(d, 112, 36, 2, METAL); C(d, 128, 36, 2, METAL)
    T(d, 120, 22, "뒷면 접점 단자", 5.5); T(d, 120, 16, "(NC / NO)", 5.5)
    T(d, 70, 10, "비상정지 CRE-30M1R (빨간 버섯 버튼)", 6, True)
def ic_fuse(d):
    R(d, 30, 40, 36, 26, colors.HexColor("#E74C3C"), BLACK, 0.4, 2); R(d, 36, 28, 8, 14, METAL); R(d, 52, 28, 8, 14, METAL); T(d, 48, 50, "10", 8, True, WHITE)
    T(d, 48, 72, "블레이드(카) 퓨즈", 5.5, True); T(d, 48, 20, "색=암페어 (10A 빨강, 5A 갈색)", 5)
    R(d, 90, 38, 30, 28, BLACK, GRAY, 0.5, 2); L(d, 80, 52, 90, 52, WIRE_R, 2); L(d, 120, 52, 130, 52, WIRE_R, 2)
    T(d, 105, 72, "퓨즈홀더", 5.5, True); T(d, 105, 28, "(선 2가닥, 뚜껑 열고 삽입)", 5)
def ic_converter(d):
    R(d, 35, 30, 80, 40, METAL, BLACK, 0.6, 3); T(d, 75, 57, "12V→5V 10A", 6, True); T(d, 75, 48, "DC-DC 컨버터", 5.5)
    R(d, 45, 32, 12, 8, BLACK); R(d, 62, 32, 12, 8, BLACK); T(d, 58, 24, "USB-A 출력 ×2 (5V)", 5.5)
    L(d, 20, 60, 35, 60, WIRE_R, 2); L(d, 20, 50, 35, 50, WIRE_K, 2); T(d, 14, 64, "IN+", 5, True); T(d, 14, 44, "IN−", 5, True)
    T(d, 75, 80, "12V 입력선 2가닥, 5V USB 출력 (2개 보유)", 6, True)
def ic_cig(d):
    R(d, 30, 40, 45, 20, BLACK, GRAY, 0.5, 8); C(d, 30, 50, 5, METAL); R(d, 75, 36, 30, 28, BLACK, GRAY, 0.5, 3)
    R(d, 80, 42, 8, 6, BLACK, WHITE, 0.4); R(d, 92, 42, 8, 6, BLACK, WHITE, 0.4); T(d, 90, 30, "USB 포트", 5.5)
    T(d, 70, 76, "차량 시거잭 충전기 (실차 전용)", 6, True); T(d, 70, 18, "※ 12V 원시 출력이 없으면 실차 12V 인입 별도 검토", 5)
def ic_adapter(d):
    R(d, 40, 30, 50, 34, BLACK, GRAY, 0.5, 4); R(d, 30, 40, 10, 3, METAL); R(d, 30, 50, 10, 3, METAL)
    L(d, 90, 47, 125, 47, BLACK, 2); R(d, 125, 43, 8, 8, METAL, BLACK, 0.4, 3); T(d, 129, 34, "USB-C", 5.5, True)
    T(d, 80, 74, "Pi 27W 정품 어댑터 (벤치용 Pi 전원)", 6, True)
def ic_powerbank(d):
    R(d, 35, 30, 80, 36, colors.HexColor("#34495E"), BLACK, 0.5, 8); T(d, 75, 50, "10,000mAh", 6, True, WHITE); T(d, 75, 40, "일체형 케이블", 5, False, WHITE)
    R(d, 115, 42, 10, 8, BLACK, WHITE, 0.4); T(d, 130, 44, "USB-A", 5.5, True, BLACK, "start")
    T(d, 75, 76, "보조배터리 (UWB 보호자측 전원)", 6, True); T(d, 75, 20, "저전류 자동차단 여부 10분 테스트!", 5.5, True, RED)
def ic_sd(d):
    R(d, 55, 30, 30, 40, colors.HexColor("#1B4F72"), BLACK, 0.5, 2); R(d, 55, 62, 8, 8, colors.HexColor("#1B4F72"))
    for i in range(8): R(d, 58 + i*3, 32, 2, 6, GOLD)
    T(d, 70, 22, "microSD 128GB", 5.5, True); R(d, 95, 35, 30, 30, BLACK, GRAY, 0.5, 3); T(d, 110, 27, "카드리더기", 5.5)
    T(d, 80, 80, "Pi 5 OS 저장 (Pi Imager로 굽기)", 6, True)
def ic_perfboard(d):
    R(d, 35, 20, 80, 60, colors.HexColor("#8B6914"), BLACK, 0.5, 2)
    for i in range(12):
        for j in range(9): C(d, 41 + i*6.2, 25 + j*6.2, 1, colors.HexColor("#F5CBA7"), colors.HexColor("#5D4E1F"), 0.3)
    T(d, 75, 88, "100×100 양면 만능기판 (갈색, 구멍 격자) ×4", 6, True); T(d, 75, 10, "MOSFET 회로 납땜용", 5.5)
def ic_jst(d):
    R(d, 30, 40, 30, 20, WHITE, BLACK, 0.6, 2); pins(d, 36, 45, 3, 8); T(d, 45, 30, "하우징(암)", 5.5)
    R(d, 80, 40, 30, 20, WHITE, BLACK, 0.6, 2); for_ = None
    for i in range(3): R(d, 84 + i*8, 42, 3, 12, METAL)
    T(d, 95, 30, "핀 헤더(수)", 5.5); T(d, 70, 78, "JST 커넥터 키트 (흰색 작은 커넥터, 압착 단자)", 6, True)
    T(d, 70, 18, "센서·팬·서보 탈착용", 5.5)
def ic_standoff(d):
    for i in range(3):
        x = 40 + i*30
        R(d, x, 30, 8, 40, GOLD, BLACK, 0.4, 1); R(d, x - 2, 70, 12, 4, GOLD, BLACK, 0.4); R(d, x + 1, 22, 6, 8, METAL)
    T(d, 75, 84, "M3×30 육각 스탠드오프 + 나사/너트", 6, True); T(d, 75, 12, "Pi·기판을 아크릴에 띄워 고정", 5.5)
def ic_consumables(d):
    C(d, 35, 50, 16, colors.HexColor("#333333"), BLACK, 0.4); C(d, 35, 50, 6, WHITE)
    d.add(Wedge(35, 50, 16, 0, 120, fillColor=WIRE_R, strokeColor=None)); d.add(Wedge(35, 50, 16, 120, 240, fillColor=WIRE_K, strokeColor=None)); d.add(Wedge(35, 50, 16, 240, 360, fillColor=WIRE_Y, strokeColor=None))
    T(d, 35, 26, "20AWG 3색 와이어", 5.5, True)
    for i, c in enumerate([RED, WIRE_B, WIRE_K, YEL]): R(d, 62, 38 + i*8, 25, 5, c)
    T(d, 75, 26, "수축튜브", 5.5, True)
    R(d, 98, 40, 40, 20, BLACK, GRAY, 0.5, 1); R(d, 98, 62, 40, 6, colors.HexColor("#444444")); T(d, 118, 26, "벨크로/케이블타이", 5.5, True)
    T(d, 75, 84, "배선 소모품 묶음 (와이어·수축튜브·벨크로·타이·그랜드)", 6, True)
def ic_tools(d):
    L(d, 25, 30, 60, 65, colors.HexColor("#1B4F72"), 5); L(d, 60, 65, 72, 77, METAL, 3); T(d, 45, 20, "납땜인두", 5.5, True)
    R(d, 85, 30, 40, 50, colors.HexColor("#F4D03F"), BLACK, 0.6, 3); R(d, 90, 60, 30, 14, colors.HexColor("#D5F5E3"), BLACK, 0.4); C(d, 105, 45, 8, BLACK)
    T(d, 105, 20, "테스터기 DM-1010", 5.5, True); T(d, 75, 88, "도구 묶음 (납땜세트·테스터기·돋보기·절연매트)", 6, True)
def ic_cables(d):
    # micro-USB, USB-A, USB-C, CSI
    R(d, 15, 60, 14, 7, METAL, BLACK, 0.4, 1); T(d, 22, 50, "micro-USB", 5.5, True); T(d, 22, 44, "(납작 사다리꼴)", 5)
    R(d, 55, 58, 16, 9, METAL, BLACK, 0.4, 0); T(d, 63, 50, "USB-A", 5.5, True); T(d, 63, 44, "(네모)", 5)
    R(d, 95, 59, 14, 7, METAL, BLACK, 0.4, 3); T(d, 102, 50, "USB-C", 5.5, True); T(d, 102, 44, "(둥근 타원)", 5)
    R(d, 15, 15, 60, 8, colors.HexColor("#F5B041"), BLACK, 0.4, 0); R(d, 15, 12, 10, 14, colors.HexColor("#2E86C1")); R(d, 65, 12, 10, 14, colors.HexColor("#2E86C1"))
    T(d, 45, 30, "CSI 리본 (넓은쪽 15핀 ↔ 좁은쪽 22핀)", 5.5, True)
    R(d, 95, 12, 40, 14, BLACK, GRAY, 0.5, 3); C(d, 135, 19, 4, METAL, BLACK, 0.4); T(d, 115, 30, "DC 잭 5.5×2.1 (벤치 12V)", 5.5, True)
    T(d, 75, 80, "케이블·커넥터 모양 구별", 6, True)

# ---------------------------------------------------------------- 부품 카드 데이터
CARDS = [
 # (No, 블록, 이름, 아이콘함수, 생김새, 핀/단자, 연결, 주의)
 ("1", "B", "Raspberry Pi 5 16GB", ic_pi,
  "신용카드 크기 초록 보드. 옆면에 USB 4개(파란 2개=USB3)와 LAN, 반대편에 USB-C 전원과 micro-HDMI 2개, 가운데 하얀 CSI 커넥터 2개.",
  "USB-C(전원), USB-A ×4, CAM0/CAM1(22핀), microSD 슬롯(아랫면)",
  "USB: mmWave·UWB·ESP32 / CAM: 카메라 / USB-C: 27W 어댑터 또는 컨버터#1",
  "전원 끄기 전 반드시 shutdown. 카메라 케이블은 전원 OFF에서만."),
 ("2", "B", "Pi Camera Module 3", ic_camera,
  "2.5cm 정사각 초록 보드에 검은 렌즈. 주황색 얇은 리본 케이블 동봉(15핀, Pi 4용).",
  "리본 케이블 커넥터 1개",
  "Pi 5 CAM1 (22핀 mini 케이블 필요 → 추가 구매)",
  "렌즈 보호필름 제거. 리본 접점면 방향 주의."),
 ("3", "B", "IWR6843ISK-ODS mmWave", ic_mmwave,
  "손바닥 크기 파란 보드. 한쪽 끝에 금색 안테나 패치 12개 격자, 작은 DIP 스위치(S1), micro-USB 1개.",
  "micro-USB(전원+2 COM 포트), SOP 스위치 S1, 60핀 커넥터(미사용)",
  "Pi 5 USB3 포트 (먼저 노트북에서 플래싱)",
  "안테나 앞 금속·손 가리지 않기. 정전기 주의(가장 비싼 부품)."),
 ("4", "C", "DWM1001-DEV (UWB) ×2", ic_uwb,
  "성냥갑 크기 초록 보드 2개. 흰 사각 UWB 안테나, micro-USB, 확장핀, 작은 JST 배터리 커넥터. 둘이 똑같이 생김.",
  "micro-USB(전원+시리얼 셸), JST 배터리(미사용)",
  "#1 차량측 → Pi USB / #2 보호자측 → 보조배터리",
  "받자마자 마스킹테이프로 '차량' '보호자' 라벨 붙이기."),
 ("13", "A", "ESP32 DevKitC WROOM-32D ×2", ic_esp32,
  "길쭉한 검정 보드, 은색 금속 캔(WROOM-32D), 양옆 핀 19개씩, micro-USB, EN/BOOT 버튼 2개.",
  "GPIO 핀 38개 (핀 이름 인쇄), micro-USB(전원+시리얼)",
  "#1: PIR·SHT31·MOSFET·서보 → Pi USB / #2: 예비",
  "업로드 실패 시 BOOT 누른 채 시작. 5V 핀에서 서보 급전 금지."),
 ("11", "A", "SHT31 온습도 센서", ic_sht31,
  "손톱 크기 초록 보드, 가운데 은색 작은 사각 칩(구멍 있음), 핀 4개.",
  "VCC / GND / SDA / SCL (보드 실크 인쇄)",
  "ESP32: 3V3 / GND / GPIO21 / GPIO22",
  "3.3V 급전. 핀 헤더 납땜 필요할 수 있음."),
 ("12", "A", "PIR 센서 EKMC4607112K", ic_pir,
  "SparkFun 빨간(또는 초록) 보드 위에 흰색 반구 돔 렌즈. 핀 3개.",
  "VCC / GND / OUT",
  "ESP32: 3V3 / GND / GPIO27",
  "전원 후 30초 워밍업. 시야가 넓어 렌즈 옆을 테이프로 가림."),
 ("31", "A", "IRLZ44N MOSFET ×2", ic_mosfet,
  "검정 플라스틱 몸통 + 위쪽 은색 금속 탭(구멍), 다리 3개. 'IRLZ44N' 인쇄.",
  "표식면 정면 왼쪽부터 G(게이트) D(드레인) S(소스)",
  "G←ESP32 GPIO25/26(220Ω) / D→팬·부저 − / S→GND",
  "탭=드레인. 두 MOSFET 탭이 서로 닿지 않게."),
 ("15", "A", "1N5819 쇼트키 다이오드 ×5", ic_diode,
  "쌀알보다 조금 큰 검정 원통, 한쪽 끝 은색 띠, 다리 2개.",
  "띠 쪽 = 캐소드(−), 반대 = 애노드(+)",
  "팬·부저 양단에 병렬, 띠가 +12V 쪽",
  "거꾸로 달면 전원 넣는 순간 퓨즈 단선."),
 ("33", "A", "막대저항 샘플키트", ic_resistor,
  "베이지색 작은 막대에 색띠 4~5개, 다리 2개. 값별로 종이 띠에 묶여 있음.",
  "극성 없음",
  "220Ω(게이트 직렬) ×2, 10kΩ(게이트 풀다운) ×2",
  "테스터기 저항 모드로 값 확인 후 사용."),
 ("14", "A", "12V 능동 부저 ×2", ic_buzzer,
  "검정 원통(동전 크기), 윗면 구멍, 선 2가닥(빨강 +, 검정 −). '+' 표시 있음.",
  "빨강 + / 검정 −",
  "+ → 12V 구동 레일 / − → Q2 드레인",
  "능동형이라 전원만 주면 '삐' 남. 극성 지키기."),
 ("17", "A", "LED 120mm 쿨링팬", ic_fan,
  "손바닥보다 큰 검정 사각 팬, LED 내장. 3~4핀 커넥터 또는 선 여러 가닥.",
  "빨강 + / 검정 − (노랑·파랑은 RPM/PWM, 미사용)",
  "+ → 12V 구동 레일 / − → Q1 드레인",
  "커넥터 잘라 JST로 재단. 미사용 선은 절연."),
 ("18", "A", "DC팬 108F 12V", lambda d: ic_fan(d, False),
  "작은 검정 사각 팬, 선 2가닥.",
  "빨강 + / 검정 −",
  "120mm 팬과 병렬 → Q1",
  "회전 방향(바람) 확인 후 장착."),
 ("10", "A", "DS3218 Pro 서보 ×2", ic_servo,
  "검정 직사각 몸통(금속 기어, 무거움), 흰 혼(팔), 선 3가닥(갈·빨·주).",
  "갈색 GND / 빨강 5V / 주황 신호",
  "5V·GND → 컨버터#2 / 신호 → ESP32 GPIO18·19",
  "순간 2A 이상. 절대 보드 5V 핀 사용 금지. 플러스알파 기능."),
 ("19", "A", "비상정지 CRE-30M1R", ic_estop,
  "빨간 버섯 모양 버튼 + 노란 링, 뒷면에 나사 단자 접점 블록.",
  "NC 접점(평소 통전) / NO 접점(평소 차단)",
  "NC → 12V 구동 레일 직렬 / NO → ESP32 GPIO32(선택)",
  "테스터기 부저 모드로 NC/NO 먼저 판별. 돌려서 해제."),
 ("29/30", "A", "카퓨즈 세트 + 퓨즈홀더 ×5", ic_fuse,
  "색깔 플라스틱 블레이드 퓨즈 여러 개(숫자=A). 홀더는 검정 뚜껑에 선 2가닥.",
  "극성 없음, 직렬 삽입",
  "메인 10A(12V 입력 직후), 분기 5A(비상정지 뒤)",
  "끊어지면 원인부터 찾고 교체."),
 ("34", "A", "12V→5V 10A 컨버터 ×2", ic_converter,
  "은색/검정 금속 케이스, 한쪽 12V 입력선 2가닥, 반대쪽 USB-A 포트.",
  "IN+ / IN− / USB-A 5V 출력",
  "#1 → Pi 5 USB-C / #2 → 서보 5V(USB 케이블 잘라 사용)",
  "입력 극성 확인. 출력 전압 5.0V 실측."),
 ("20", "A", "차량 시거잭 충전기", ic_cig,
  "차량 시거 소켓에 꽂는 원통 플러그 + USB 포트.",
  "USB 출력",
  "실차 테스트 시 Pi 보조 전원",
  "12V 원시 출력이 없으면 12V 인입은 별도 검토(벤치는 12V 어댑터)."),
 ("21", "B", "Pi 27W USB-C 어댑터", ic_adapter,
  "검정 어댑터, USB-C 케이블 일체형, Raspberry Pi 로고.",
  "USB-C 5V 5A",
  "Pi 5 USB-C (벤치·개발 중 전원)",
  "5A PD라 USB 주변기기 전류 여유 있음."),
 ("35", "C", "보조배터리 10,000mAh", ic_powerbank,
  "손바닥 크기 납작 배터리, 케이블 일체형, USB-A 포트.",
  "USB-A 출력",
  "UWB 보호자측 노드 전원",
  "저전류 자동차단 → 10분 켜짐 테스트 필수."),
 ("28", "B", "microSD 128GB + 리더기", ic_sd,
  "손톱 크기 카드 + USB 리더기.",
  "-", "Pi 5 아랫면 슬롯", "Pi Imager로 OS 굽기. 뺄 때 전원 OFF."),
 ("6", "A", "양면 만능기판 ×4", ic_perfboard,
  "10×10cm 갈색/초록 판에 구멍 격자, 양면 동박.",
  "-", "MOSFET·저항·다이오드·JST 납땜", "브레드보드 검증 후에만 납땜."),
 ("26", "A", "JST 커넥터 키트", ic_jst,
  "흰색 작은 플라스틱 커넥터 암/수 + 압착 핀 여러 개.",
  "2·3·4핀", "센서·팬·서보·12V 인입 탈착부", "압착기가 없으면 납땜 후 수축튜브."),
 ("27", "B", "M3×30 스탠드오프 키트", ic_standoff,
  "금색 육각 기둥 + 나사·너트.", "-", "Pi·기판·카메라 고정", "-"),
 ("8/22/23/24/25", "A/통합", "배선 소모품 묶음", ic_consumables,
  "3색 실리콘 와이어(빨·검·노), 수축튜브 색색 세트, 검정 벨크로(듀얼락), 벨크로 케이블타이, 케이블 그랜드(검정 너트형).",
  "-", "색 규칙: 빨강=12V, 노랑/주황=5V, 검정=GND", "수축튜브는 납땜 전에 먼저 끼우기."),
 ("5/7/9/16", "공용", "도구 묶음", ic_tools,
  "납땜인두 세트, 노란 디지털 테스터기 DM-1010, LED 돋보기 스탠드, 실리콘 절연매트.",
  "-", "블록 A 작업대", "테스터기 10A 전류 단자는 직렬로만."),
 ("36+", "통합", "케이블·커넥터 모양", ic_cables,
  "micro-USB(납작 사다리꼴), USB-A(네모), USB-C(둥근 타원), CSI 리본(주황), DC잭.",
  "-", "micro-USB 데이터 케이블 4개 필요 (현재 1개)", "충전 전용 케이블은 인식 안 됨."),
]

def card(no, blk, name, fn, look, pinsd, conn, warn):
    d = Drawing(150, 95); fn(d)
    bc = BLK.get(blk.split("/")[0], BLK["공용"])
    badge = Table([[Paragraph(f"<font color='white'><b>No.{no}</b></font>", S["cell"]),
                    Paragraph(f"<font color='white'><b>블록 {blk}</b></font>", S["cell"])]], colWidths=[22*mm, 22*mm])
    badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), HEAD), ("BACKGROUND", (1, 0), (1, 0), bc),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    rows = [[Paragraph("<b>생김새</b>", S["cell"]), Paragraph(look, S["cell"])],
            [Paragraph("<b>핀/단자</b>", S["cell"]), Paragraph(pinsd, S["cell"])],
            [Paragraph("<b>연결</b>", S["cell"]), Paragraph(conn, S["cell"])],
            [Paragraph("<b>주의</b>", S["cell"]), Paragraph(warn, S["cell"])]]
    info = Table(rows, colWidths=[14*mm, 70*mm])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                              ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                              ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#D5D8DC"))]))
    inner = Table([[badge], [Paragraph(name, S["cname"])], [d], [info]], colWidths=[CW/2 - 6*mm])
    inner.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, bc), ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                               ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("ALIGN", (0, 2), (0, 2), "CENTER")]))
    return inner

# ---------------------------------------------------------------- 큰 배선 그림
def wire(d, pts, color, sw=1.6):
    for i in range(len(pts) - 1):
        L(d, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], color, sw)

def fig_blockA():
    d = Drawing(CW, 470)
    T(d, CW/2, 458, "<그림 A> 블록 A 배선 그림 — 전원부 · MOSFET · ESP32 센서 노드 (선 색: 빨강 12V, 주황 5V, 검정 GND, 파랑 3.3V 신호)", 8, True, HEAD)
    # 12V source
    R(d, 10, 380, 90, 50, LIGHT, BLACK, 0.6, 3); T(d, 55, 415, "12V 입력", 7, True); T(d, 55, 404, "벤치: 12V 어댑터+DC잭", 5.5); T(d, 55, 395, "실차: 시거잭 12V", 5.5)
    T(d, 20, 384, "+", 7, True, RED); T(d, 88, 384, "−", 7, True)
    # fuse
    R(d, 130, 400, 40, 18, BLACK, GRAY, 0.5, 2); R(d, 140, 404, 20, 10, RED); T(d, 150, 407, "10A", 5, True, WHITE); T(d, 150, 424, "메인 퓨즈홀더", 5.5, True)
    wire(d, [(20, 380), (20, 370), (115, 370), (115, 409), (130, 409)], WIRE_R)
    # ground bus
    wire(d, [(88, 380), (88, 30), (520, 30)], WIRE_K, 2); T(d, 300, 20, "GND 버스 (모든 검정선이 여기로 모임)", 6, True)
    # split node
    C(d, 200, 409, 3, RED); wire(d, [(170, 409), (200, 409)], WIRE_R)
    # converter 1 (top right)
    R(d, 240, 395, 90, 34, METAL, BLACK, 0.6, 3); T(d, 285, 418, "컨버터 #1 (12V→5V)", 6, True); T(d, 285, 407, "USB-A → USB-C → Pi 5", 5.5)
    wire(d, [(200, 409), (240, 420)], WIRE_R); wire(d, [(240, 400), (215, 400), (215, 30)], WIRE_K)
    R(d, 360, 385, 150, 50, colors.HexColor("#FADBD8"), BLK["B"], 0.8, 3); T(d, 435, 420, "Raspberry Pi 5 (블록 B)", 7, True, BLK["B"]); T(d, 435, 408, "USB-C ← 컨버터#1 (또는 27W 어댑터)", 5.5); T(d, 435, 396, "USB-A → ESP32 (전원+시리얼)", 5.5)
    wire(d, [(330, 412), (360, 412)], WIRE_O)
    # E-stop
    R(d, 190, 320, 60, 34, YEL, BLACK, 0.6, 3); C(d, 220, 337, 11, RED); T(d, 220, 312, "비상정지 NC 접점", 5.5, True)
    wire(d, [(200, 409), (200, 360), (190, 360), (190, 345)], WIRE_R); wire(d, [(250, 345), (270, 345), (270, 337)], WIRE_R)
    R(d, 270, 328, 36, 18, BLACK, GRAY, 0.5, 2); R(d, 278, 332, 20, 10, colors.HexColor("#B9770E")); T(d, 288, 335, "5A", 5, True, WHITE); T(d, 288, 352, "분기 퓨즈", 5.5, True)
    C(d, 340, 337, 3, RED); wire(d, [(306, 337), (340, 337)], WIRE_R); T(d, 340, 345, "12V 구동 레일", 6, True, RED)
    # loads: fans and buzzer on rail
    wire(d, [(340, 337), (340, 240)], WIRE_R)
    # fan1
    R(d, 380, 280, 40, 40, BLACK, GRAY, 0.5, 3); C(d, 400, 300, 14, colors.HexColor("#5D6D7E")); T(d, 400, 272, "팬 120mm", 5.5, True)
    R(d, 430, 285, 30, 30, BLACK, GRAY, 0.5, 3); C(d, 445, 300, 10, colors.HexColor("#5D6D7E")); T(d, 445, 277, "팬 108F", 5.5, True)
    wire(d, [(340, 310), (380, 310)], WIRE_R); wire(d, [(420, 310), (430, 310)], WIRE_R)
    wire(d, [(380, 290), (370, 290), (370, 250)], WIRE_K); wire(d, [(430, 290), (425, 290), (425, 250), (370, 250)], WIRE_K)
    # buzzer
    C(d, 490, 300, 14, BLACK); T(d, 490, 280, "부저 12V", 5.5, True); wire(d, [(340, 330), (470, 330), (470, 305), (476, 305)], WIRE_R)
    wire(d, [(490, 286), (490, 250), (480, 250)], WIRE_K)
    # converter 2 -> servo
    R(d, 410, 195, 80, 30, METAL, BLACK, 0.6, 3); T(d, 450, 214, "컨버터 #2 (12V→5V)", 6, True); T(d, 450, 203, "→ 서보 5V 전용", 5.5)
    wire(d, [(340, 240), (340, 215), (410, 215)], WIRE_R); wire(d, [(410, 202), (395, 202), (395, 30)], WIRE_K)
    R(d, 430, 140, 50, 30, BLACK, GRAY, 0.5, 3); T(d, 455, 152, "서보 DS3218", 5.5, True, WHITE); T(d, 455, 132, "(플러스알파)", 5.5)
    wire(d, [(490, 195), (500, 195), (500, 160), (480, 160)], WIRE_O); wire(d, [(480, 150), (505, 150), (505, 30)], WIRE_K)
    # MOSFET Q1, Q2
    for (qx, qy, nm, gpio, loadname) in [(280, 240, "Q1", "GPIO25", "팬 −"), (280, 170, "Q2", "GPIO26", "부저 −")]:
        R(d, qx, qy, 40, 26, METAL, BLACK, 0.5, 1); R(d, qx, qy - 18, 40, 18, BLACK, BLACK, 0.5, 1); T(d, qx + 20, qy - 12, "IRLZ44N " + nm, 5, True, WHITE)
        T(d, qx + 6, qy - 26, "G", 5, True); T(d, qx + 20, qy - 26, "D", 5, True); T(d, qx + 34, qy - 26, "S", 5, True)
        wire(d, [(qx + 34, qy - 18), (qx + 34, qy - 40), (qx + 60, qy - 40), (qx + 60, 30)], WIRE_K)    # S -> GND
        # D -> load
        if nm == "Q1": wire(d, [(qx + 20, qy - 18), (qx + 20, qy - 32), (370, qy - 32), (370, 250)], WIRE_K)
        else: wire(d, [(qx + 20, qy - 18), (qx + 20, qy - 32), (480, qy - 32), (480, 250)], WIRE_K)
        # diode
        R(d, qx + 45, qy + 4, 14, 6, BLACK, BLACK, 0.3, 2); R(d, qx + 55, qy + 4, 3, 6, METAL); T(d, qx + 52, qy + 13, "1N5819", 4.5)
        # gate
        R(d, qx - 40, qy - 26, 22, 7, colors.HexColor("#F5CBA7"), BLACK, 0.3, 3); T(d, qx - 29, qy - 35, "220Ω", 4.5)
        wire(d, [(qx + 6, qy - 18), (qx + 6, qy - 22), (qx - 18, qy - 22)], WIRE_B)
        R(d, qx - 52, qy - 52, 7, 22, colors.HexColor("#F5CBA7"), BLACK, 0.3, 3); T(d, qx - 62, qy - 44, "10k", 4.5)
        wire(d, [(qx - 48, qy - 22), (qx - 48, qy - 30)], WIRE_B); wire(d, [(qx - 48, qy - 52), (qx - 48, 30)], WIRE_K)
        wire(d, [(qx - 40, qy - 22), (qx - 48, qy - 22), (qx - 90, qy - 22)], WIRE_B)
    # ESP32
    R(d, 30, 120, 110, 150, BLACK, GRAY, 0.6, 4); R(d, 45, 200, 50, 40, METAL); T(d, 70, 218, "ESP32 #1", 6, True)
    T(d, 85, 138, "USB → Pi", 5.5, True, WHITE); R(d, 60, 118, 20, 8, METAL)
    pl = [("3V3", 258), ("GND", 246), ("GPIO27", 234), ("GPIO21", 222), ("GPIO22", 210), ("GPIO25", 198), ("GPIO26", 186), ("GPIO18", 174), ("GPIO19", 162), ("GPIO32", 150)]
    for nm, py in pl:
        C(d, 140, py, 1.6, GOLD, BLACK, 0.3); T(d, 136, py - 2, nm, 4.8, True, WHITE, "end")
    wire(d, [(140, 198), (190, 198), (190, 218)], WIRE_B); wire(d, [(140, 186), (190, 186), (190, 148)], WIRE_B)
    wire(d, [(140, 246), (150, 246), (150, 30)], WIRE_K)
    # PIR / SHT31 left of ESP32? put below-left
    R(d, 20, 40, 50, 40, PCB, PCB_D, 0.6, 3); C(d, 45, 62, 9, WHITE, GRAY, 0.4); T(d, 45, 44, "PIR", 6, True, WHITE)
    R(d, 80, 40, 50, 40, PCB, PCB_D, 0.6, 3); T(d, 105, 60, "SHT31", 6, True, WHITE); T(d, 105, 48, "I2C", 5, False, WHITE)
    wire(d, [(140, 258), (160, 258), (160, 100), (30, 100), (30, 80)], WIRE_O); wire(d, [(160, 100), (90, 100), (90, 80)], WIRE_O); T(d, 165, 262, "3.3V → PIR·SHT31 VCC", 4.8, True, WIRE_O, "start")
    wire(d, [(140, 234), (168, 234), (168, 92), (45, 92), (45, 80)], WIRE_B); T(d, 175, 230, "PIR OUT", 4.8, True, WIRE_B, "start")
    wire(d, [(140, 222), (172, 222), (172, 88), (110, 88), (110, 80)], WIRE_B); wire(d, [(140, 210), (176, 210), (176, 84), (120, 84), (120, 80)], WIRE_B); T(d, 182, 216, "SDA/SCL", 4.8, True, WIRE_B, "start")
    wire(d, [(60, 40), (60, 30)], WIRE_K); wire(d, [(100, 40), (100, 30)], WIRE_K)
    # servo signal
    wire(d, [(140, 174), (180, 174), (180, 110), (455, 110), (455, 140)], WIRE_B); T(d, 300, 113, "서보 신호 GPIO18 (주황선)", 4.8, True, WIRE_B)
    return d

def fig_blockB():
    d = Drawing(CW, 256)
    T(d, CW/2, 248, "<그림 B> 블록 B 연결 그림 — Pi 5에 무엇을 어디에 꽂나", 8, True, HEAD)
    # Pi board
    R(d, 150, 40, 220, 150, PCB, PCB_D, 1, 5); T(d, 260, 170, "Raspberry Pi 5", 9, True, WHITE)
    R(d, 355, 140, 22, 16, colors.HexColor("#2E86C1"), BLACK, 0.4, 1); R(d, 355, 118, 22, 16, colors.HexColor("#2E86C1"), BLACK, 0.4, 1)
    R(d, 355, 92, 22, 16, METAL, BLACK, 0.4, 1); R(d, 355, 70, 22, 16, METAL, BLACK, 0.4, 1); R(d, 355, 42, 22, 24, METAL, BLACK, 0.4, 1)
    T(d, 366, 160, "USB3", 5, True, WHITE); T(d, 366, 110, "USB2", 5, True); T(d, 366, 34, "LAN", 5)
    R(d, 152, 44, 18, 9, METAL, BLACK, 0.4, 1); T(d, 161, 34, "USB-C", 5, True)
    R(d, 200, 42, 10, 18, WHITE, BLACK, 0.4, 1); R(d, 216, 42, 10, 18, WHITE, BLACK, 0.4, 1); T(d, 213, 34, "CAM0  CAM1", 5, True)
    R(d, 150, 90, 5, 14, BLACK); T(d, 140, 96, "SD", 5, True, BLACK, "end")
    # peripherals
    R(d, 430, 140, 100, 40, PCB_BLUE, BLACK, 0.6, 3); T(d, 480, 165, "mmWave", 7, True, WHITE); T(d, 480, 153, "IWR6843ISK-ODS", 5.5, False, WHITE)
    wire(d, [(377, 148), (430, 160)], BLACK, 1.2); T(d, 405, 160, "micro-USB", 5, True)
    R(d, 430, 85, 100, 34, PCB, PCB_D, 0.6, 3); T(d, 480, 106, "UWB 차량측 (TAG)", 6.5, True, WHITE); T(d, 480, 94, "DWM1001-DEV #1", 5.5, False, WHITE)
    wire(d, [(377, 100), (430, 102)], BLACK, 1.2); T(d, 405, 106, "micro-USB", 5, True)
    R(d, 430, 40, 100, 30, BLACK, GRAY, 0.6, 3); T(d, 480, 58, "ESP32 #1 (블록 A)", 6.5, True, WHITE); T(d, 480, 46, "DevKitC", 5.5, False, WHITE)
    wire(d, [(377, 78), (430, 55)], BLACK, 1.2); T(d, 405, 72, "micro-USB", 5, True)
    R(d, 190, 200, 40, 30, PCB, PCB_D, 0.6, 3); C(d, 210, 215, 8, BLACK); T(d, 236, 212, "Camera Module 3", 6, True, BLACK, "start")
    R(d, 214, 60, 4, 140, colors.HexColor("#F5B041")); T(d, 240, 130, "CSI 리본 22↔15핀", 5.5, True, BLACK, "start")
    R(d, 20, 40, 100, 30, BLACK, GRAY, 0.6, 3); T(d, 70, 58, "27W 어댑터 (벤치)", 6.5, True, WHITE); T(d, 70, 46, "또는 컨버터#1 (실차)", 5.5, False, WHITE)
    wire(d, [(120, 52), (152, 48)], WIRE_O, 1.5)
    R(d, 20, 100, 100, 30, colors.HexColor("#1B4F72"), BLACK, 0.6, 3); T(d, 70, 118, "microSD (OS)", 6.5, True, WHITE); T(d, 70, 106, "Pi Imager로 굽기", 5.5, False, WHITE)
    wire(d, [(120, 112), (150, 97)], BLACK, 1)
    T(d, 260, 20, "USB 3개 + CSI 1개 + 전원 1개 = Pi에 꽂는 선은 총 5개", 6.5, True, HEAD)
    return d

def fig_blockC():
    d = Drawing(CW, 170)
    T(d, CW/2, 160, "<그림 C> 블록 C — UWB 두 노드의 역할과 전원", 8, True, HEAD)
    R(d, 20, 40, 190, 90, colors.HexColor("#EAF2F8"), BLK["B"], 0.8, 4); T(d, 115, 118, "차량 (모형차 안)", 7, True, BLK["B"])
    R(d, 40, 60, 70, 40, PCB, PCB_D, 0.6, 3); T(d, 75, 86, "DWM1001 #1", 6, True, WHITE); T(d, 75, 75, "TAG (nmt)", 6, True, YEL); T(d, 75, 65, "거리값 출력 lec", 5, False, WHITE)
    R(d, 130, 60, 60, 40, colors.HexColor("#FADBD8"), BLK["B"], 0.6, 3); T(d, 160, 84, "Pi 5", 7, True, BLK["B"]); T(d, 160, 72, "USB", 5.5); wire(d, [(110, 80), (130, 80)], BLACK, 1.2)
    T(d, 115, 48, "보호자와의 거리(m)를 Pi가 읽음", 5.5)
    R(d, 320, 40, 190, 90, colors.HexColor("#EAFAF1"), BLK["C"], 0.8, 4); T(d, 415, 118, "보호자 (손에 들고 5m 이상 이동)", 7, True, BLK["C"])
    R(d, 340, 60, 70, 40, PCB, PCB_D, 0.6, 3); T(d, 375, 86, "DWM1001 #2", 6, True, WHITE); T(d, 375, 75, "ANCHOR init (nmi)", 6, True, YEL); T(d, 375, 65, "출력 안 읽음", 5, False, WHITE)
    R(d, 430, 62, 70, 36, colors.HexColor("#34495E"), BLACK, 0.5, 6); T(d, 465, 84, "보조배터리", 6.5, True, WHITE); T(d, 465, 72, "10,000mAh", 5.5, False, WHITE); wire(d, [(410, 80), (430, 80)], BLACK, 1.2)
    T(d, 415, 48, "10분 이상 안 꺼지는지 확인", 5.5, True, RED)
    d.add(Line(210, 85, 320, 85, strokeColor=BLK["C"], strokeWidth=1.2, strokeDashArray=(4, 3))); T(d, 265, 90, "UWB 무선 TWR 거리 측정 (같은 네트워크 ID: nis)", 6, True, BLK["C"])
    T(d, 265, 20, "두 보드는 똑같이 생겼으니 반드시 라벨을 붙인다.  설정 명령: nmt(태그) / nmi(앵커 initiator) / nis 0x1234 / lec", 6, True, HEAD)
    return d

def fig_map():
    """한 장짜리 부품 지도: 카테고리별 그리드"""
    d = Drawing(CW, 560)
    T(d, CW/2, 548, "<그림 0> 부품 지도 — 상자에서 꺼내며 이 그림 위에 놓아 보세요 (색 = 담당 블록)", 8.5, True, HEAD)
    groups = [
        ("블록 B  두뇌·눈 (Pi 5 담당)", BLK["B"], [("1 Pi 5", ic_pi), ("2 카메라", ic_camera), ("3 mmWave", ic_mmwave), ("21 어댑터", ic_adapter), ("28 microSD", ic_sd)]),
        ("블록 C  UWB (거리 측정 담당)", BLK["C"], [("4 DWM1001 ×2", ic_uwb), ("35 보조배터리", ic_powerbank), ("36 케이블", ic_cables)]),
        ("블록 A  전원·구동·센서 (ESP32 담당)", BLK["A"], [("13 ESP32 ×2", ic_esp32), ("12 PIR", ic_pir), ("11 SHT31", ic_sht31), ("31 MOSFET ×2", ic_mosfet), ("15 다이오드", ic_diode), ("33 저항", ic_resistor),
                                                   ("17 팬 120", ic_fan), ("18 팬 108F", lambda dd: ic_fan(dd, False)), ("14 부저", ic_buzzer), ("10 서보 ×2", ic_servo), ("19 비상정지", ic_estop), ("29/30 퓨즈", ic_fuse),
                                                   ("34 컨버터 ×2", ic_converter), ("20 시거잭", ic_cig), ("6 만능기판", ic_perfboard), ("26 JST", ic_jst)]),
        ("공용  도구·소모품", BLK["공용"], [("5/7/9/16 도구", ic_tools), ("8/22~25 소모품", ic_consumables), ("27 스탠드오프", ic_standoff)]),
    ]
    cellw, cellh = 90, 62; cols = 6
    y = 540
    for title, col, items in groups:
        nrows = math.ceil(len(items) / cols)
        gh = nrows * cellh + 16
        y -= gh
        R(d, 0, y, CW, gh, colors.HexColor("#FBFCFC"), col, 0.8, 4); T(d, 6, y + gh - 11, title, 7, True, col, "start")
        for i, (nm, fn) in enumerate(items):
            r, c = divmod(i, cols); x0 = 4 + c * cellw; y0 = y + gh - 16 - (r + 1) * cellh
            sub = Drawing(150, 95); fn(sub)
            sub.scale(cellw / 150 * 0.95, cellh / 95 * 0.8); sub.translate(x0 / (cellw / 150 * 0.95), (y0 + 10) / (cellh / 95 * 0.8))
            d.add(sub); T(d, x0 + cellw/2, y0 + 3, nm, 5.5, True, col)
        y -= 4
    return d

# ================================================================= 문서 구성
story.append(Spacer(1, 10))
story.append(Paragraph("SafeGuard 부품 식별·배선 그림책", S["title"]))
story.append(Paragraph("36개 부품, 뭐가 뭔지 그림으로 찾기 — 연결 가이드 v1.0의 그림판", S["sub"]))
story.append(Paragraph("2026-09-12  |  팀 두고내리지말아조  |  블록 A(주황)=전원·구동·ESP32, B(빨강)=Pi·카메라·mmWave, C(초록)=UWB", S["sub"]))
story.append(Spacer(1, 10))
P("<b>쓰는 법</b>: ① 상자를 열면 아래 지도와 대조해 부품을 블록별 상자(A/B/C/공용)로 나눈다. ② 다음 장의 부품 카드(생김새·핀·연결·주의)를 보고 라벨을 붙인다. ③ 마지막 배선 그림(A/B/C)을 보며 선을 잇는다. "
  "그림은 사진이 아니라 특징을 강조한 도식이라 색·크기가 실물과 다를 수 있다. 헷갈리면 부품에 인쇄된 글자(IRLZ44N, 1N5819, DWM1001 등)를 먼저 읽는다.")
story.append(fig_map())
story.append(PageBreak())

H1("1. 부품 카드")
P("각 카드: 번호(엑셀 No.) · 담당 블록 · 그림 · 생김새 · 핀/단자 · 연결 대상 · 주의. 카드를 잘라 부품 봉투에 붙여도 된다.")
cards = [card(*c) for c in CARDS]
rows = []
for i in range(0, len(cards), 2):
    rows.append([cards[i], cards[i+1] if i+1 < len(cards) else ""])
grid = Table(rows, colWidths=[CW/2, CW/2])
grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
story.append(grid)
story.append(PageBreak())

H1("2. 배선 그림")
P("연결 가이드 4~6장의 표를 그림으로 옮긴 것이다. <b>선 색 규칙</b>: 빨강=12V, 주황=5V, 파랑=3.3V 신호, 검정=GND. 실제 배선도 같은 색으로 하면 디버깅이 쉽다.")
story.append(fig_blockA())
story.append(PageBreak())
story.append(fig_blockB())
story.append(Spacer(1, 10))
story.append(fig_blockC())
story.append(Spacer(1, 8))
H2("배선 전 5초 체크")
BUL(["12V(빨강)가 ESP32·Pi·센서의 어떤 핀에도 닿지 않는가?",
     "GND(검정)가 12V 전원, 컨버터 2개, ESP32, MOSFET 소스, 서보에 모두 연결되어 하나로 묶였는가?",
     "다이오드 띠(은색)가 +12V 쪽을 향하는가? MOSFET 표식면 기준 G-D-S 순서가 맞는가?",
     "서보 빨간선이 ESP32 5V가 아니라 컨버터#2에서 오는가?",
     "비상정지를 누른 상태에서 전원을 넣는가?"])
NOTE("상세 절차·명령·완료 조건 표는 <b>SafeGuard_하드웨어_연결_가이드_v1.0.pdf</b>를 함께 본다. 이 그림책은 '뭐가 뭔지'와 '어디에 꽂는지'만 담았다.")

doc.build(story)
print("OK", OUT)
