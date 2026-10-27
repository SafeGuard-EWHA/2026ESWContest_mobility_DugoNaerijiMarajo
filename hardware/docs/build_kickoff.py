# -*- coding: utf-8 -*-
"""SafeGuard 하드웨어 착수 가이드 (뭐부터 할까) — 그림책의 아이콘/도우미를 재사용해 생성."""
import sys, io, os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "SafeGuard_착수가이드_뭐부터할까_v1.0.pdf")

# ---- 그림책 스크립트의 정의부(스타일·도우미·아이콘·배선그림)만 불러오기
src = io.open(os.path.join(HERE, "build_parts_book.py"), encoding="utf-8").read()
src = src[:src.index("# ================================================================= 문서 구성")]
sys.argv = [sys.argv[0], os.path.join(HERE, "_tmp_unused.pdf")]
exec(compile(src, "parts_book_defs", "exec"))
story = []  # 새로 시작
GREEN = colors.HexColor("#1E8449"); AMBER = colors.HexColor("#B9770E"); HEAD = HEAD

from reportlab.platypus import Table, TableStyle, PageBreak, Spacer, Paragraph, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon, Circle

TODAY = "2026-10-16"
def on_page2(canv, doc):
    canv.saveState(); canv.setFont("NG", 8); canv.setFillColor(GRAY)
    canv.drawString(15*mm, 10*mm, f"SafeGuard 착수 가이드 v1.0 — 뭐부터 할까  |  팀 두고내리지말아조  |  {TODAY}")
    canv.drawRightString(W-15*mm, 10*mm, f"{doc.page}")
    canv.setStrokeColor(colors.HexColor("#D5D8DC")); canv.line(15*mm, 14*mm, W-15*mm, 14*mm); canv.restoreState()
doc = BaseDocTemplate(OUT_PDF, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=14*mm, bottomMargin=18*mm,
                      title="SafeGuard 착수 가이드 v1.0", author="두고내리지말아조")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=on_page2)])

S["code"] = ParagraphStyle("code", fontName="NG", fontSize=8.5, leading=12, backColor=LIGHT, borderPadding=4, leftIndent=6, spaceBefore=2, spaceAfter=6)
S["warn"] = ParagraphStyle("warn", fontName="NG", fontSize=9, leading=13.5, backColor=colors.HexColor("#FDEDEC"),
                           borderColor=colors.HexColor("#E74C3C"), borderWidth=0.8, borderPadding=5, spaceBefore=4, spaceAfter=8)
S["h3"] = ParagraphStyle("h3", fontName="NGB", fontSize=10.5, leading=15, spaceBefore=6, spaceAfter=3)
def WARN(t): story.append(Paragraph("<b>주의</b> " + t, S["warn"]))
def H3(t): story.append(Paragraph(t, S["h3"]))
def CODE(t):
    out = []
    for ln in t.split("\n"):
        face = "Courier" if all(ord(c) < 128 for c in ln) else "NG"
        out.append('<font face="%s">' % face + ln.replace(" ", "&nbsp;") + "</font>")
    story.append(Paragraph("<br/>".join(out), S["code"]))
def NUM(items):
    for i, it in enumerate(items, 1):
        story.append(Paragraph(it, S["bul"], bulletText=f"{i}."))
def TBL(header, rows, widths, head_color=HEAD):
    data = [[Paragraph(h, ParagraphStyle("ch", fontName="NGB", fontSize=8.5, leading=12, textColor=WHITE)) for h in header]]
    for r in rows:
        data.append([Paragraph(str(c), S["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), head_color), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFC9CA")),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i in range(1, len(data)):
        if i % 2 == 0: st.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(st)); story.append(t); story.append(Spacer(1, 6))

# ---------------------------------------------------------------- 공통 그림 도우미
def mock_window(d, x, y, w, h, title, lines, hl=None, title_fill=colors.HexColor("#2C3E50"), mono=False, body_fill=WHITE):
    """단순 모형 창: 제목줄 + 본문 줄. hl = 강조할 줄 번호 집합"""
    R(d, x, y, w, h, body_fill, GRAY, 0.6, 3)
    R(d, x, y + h - 14, w, 14, title_fill, title_fill, 0.3, 3)
    T(d, x + 6, y + h - 10, title, 6.5, True, WHITE, "start")
    C(d, x + w - 8, y + h - 7, 2.2, RED); C(d, x + w - 16, y + h - 7, 2.2, YEL); C(d, x + w - 24, y + h - 7, 2.2, GREEN)
    for i, ln in enumerate(lines):
        ly = y + h - 26 - i * 11
        if hl and i in hl:
            R(d, x + 3, ly - 3, w - 6, 11, colors.HexColor("#FEF9E7"), AMBER, 0.5, 1)
        T(d, x + 8, ly, ln, 6.5, bool(hl and i in hl), BLACK, "start")

def step_badge(d, x, y, n, fill=HEAD):
    C(d, x, y, 7, fill); T(d, x, y - 2.5, str(n), 7.5, True, WHITE)

def laptop(d, x, y, w=70, h=45):
    R(d, x, y + 8, w, h - 8, colors.HexColor("#2C3E50"), BLACK, 0.5, 3)
    R(d, x + 4, y + 12, w - 8, h - 16, colors.HexColor("#D6EAF8"), None, 0, 1)
    R(d, x - 4, y + 2, w + 8, 6, colors.HexColor("#34495E"), BLACK, 0.5, 2)
    T(d, x + w/2, y + h/2 + 2, "노트북", 6.5, True, HEAD)

def usb_cable(d, x1, y1, x2, y2):
    L(d, x1, y1, x2, y2, BLACK, 1.6); R(d, x1 - 5, y1 - 3, 10, 6, METAL, BLACK, 0.4, 1); R(d, x2 - 5, y2 - 3, 10, 6, METAL, BLACK, 0.4, 1)

def arrow(d, x1, y1, x2, y2, color=GRAY, sw=1.0):
    import math
    L(d, x1, y1, x2, y2, color, sw)
    a = math.atan2(y2 - y1, x2 - x1); s = 5
    d.add(Polygon([x2, y2, x2 - s*math.cos(a-0.45), y2 - s*math.sin(a-0.45), x2 - s*math.cos(a+0.45), y2 - s*math.sin(a+0.45)], fillColor=color, strokeColor=color))

def scaled(fn, w=150, h=95, sx=1.0, sy=None, dx=0, dy=0):
    sub = Drawing(w, h); fn(sub); sub.scale(sx, sy or sx); sub.translate(dx / sx, dy / (sy or sx)); return sub

# ---------------------------------------------------------------- 그림들
def fig_timeline():
    d = Drawing(CW, 120)
    T(d, CW/2, 110, "<그림 1> 우리는 지금 어디에 있나", 8.5, True, HEAD)
    stages = [("0 준비", "9/12 장비 수령\n가이드·그림책 작성", GREEN), ("1 단독 검증", "A/B/C 각자\n← 지금 여기", AMBER), ("2 통합", "GND·USB·전원\n투입 순서", colors.HexColor("#5D6D7E")),
              ("3 FSM", "상태기계\nDEMO/REAL", colors.HexColor("#5D6D7E")), ("4 장애 주입", "mmWave 뽑기\nAPI 차단", colors.HexColor("#5D6D7E")), ("5 성능 측정", "6개 지표", colors.HexColor("#5D6D7E")), ("6 시연 고정", "리허설", colors.HexColor("#5D6D7E"))]
    n = len(stages); cw = (CW - 10) / n
    for i, (t, sub, col) in enumerate(stages):
        x = 5 + i * cw
        pts = [x, 60, x + cw - 14, 60, x + cw - 4, 78, x + cw - 14, 96, x, 96, x + 10 if i > 0 else x, 78]
        d.add(Polygon(pts, fillColor=col, strokeColor=WHITE, strokeWidth=1))
        T(d, x + cw/2 - 2, 76, t, 7.5, True, WHITE)
        for j, ln in enumerate(sub.split("\n")): T(d, x + cw/2 - 2, 46 - j*10, ln, 6.5, i == 1, AMBER if i == 1 else GRAY)
    R(d, 5 + cw - 6, 8, cw + 12, 14, AMBER, AMBER, 0.3, 7); T(d, 5 + cw*1.5, 12, "10/16 현재 위치", 6.5, True, WHITE)
    return d

def fig_three_people():
    d = Drawing(CW, 150)
    T(d, CW/2, 140, "<그림 2> 세 사람이 각자 이번 주에 만들 것", 8.5, True, HEAD)
    cols = [("담당 1 · 블록 A", BLK["A"], "전원 · 구동 · ESP32", ["ESP32 꽂아 LED 깜빡이기", "PIR·SHT31 값 시리얼로 보기", "12V 레일 → 팬/부저 ON/OFF"], ic_esp32),
            ("담당 2 · 블록 B", BLK["B"], "Pi 5 · 카메라 · mmWave", ["Pi 5 부팅 + SSH 접속", "카메라로 사진 1장 저장", "mmWave 점 구름 보기"], ic_pi),
            ("담당 3 · 블록 C", BLK["C"], "UWB 거리 측정", ["두 노드 역할 설정", "거리값 셸에 찍히는지 보기", "보조배터리 10분 유지"], ic_uwb)]
    cw = (CW - 20) / 3
    for i, (t, col, sub, items, icon) in enumerate(cols):
        x = 5 + i * (cw + 5)
        R(d, x, 5, cw, 128, colors.HexColor("#FBFCFC"), col, 1.0, 5)
        R(d, x, 113, cw, 20, col, col, 0.3, 5); T(d, x + cw/2, 120, t, 8, True, WHITE)
        T(d, x + cw/2, 102, sub, 7.5, True, col)
        d.add(scaled(icon, sx=0.30, dx=x + cw - 52, dy=58))
        for j, it in enumerate(items):
            C(d, x + 12, 80 - j*17, 5, col); T(d, x + 12, 77.5 - j*17, str(j+1), 6, True, WHITE)
            T(d, x + 21, 77.5 - j*17, it, 6.3, False, BLACK, "start")
        T(d, x + cw/2, 12, "셋 다 되면 → 2단계 통합 (다같이)", 6, False, GRAY)
    return d

def fig_laptops():
    d = Drawing(CW, 135)
    T(d, CW/2, 125, "<그림 3> 노트북은 각자 자기 것 (하나로 안 해도 됨)", 8.5, True, HEAD)
    items = [("담당 1", "Arduino IDE\nCP210x 드라이버", BLK["A"], ic_esp32), ("담당 2", "Raspberry Pi Imager\nSSH(PowerShell)\nTI UniFlash·Visualizer", BLK["B"], ic_pi), ("담당 3", "Tera Term 또는 PuTTY\n(시리얼 터미널)", BLK["C"], ic_uwb)]
    cw = (CW - 20) / 3
    for i, (t, sw, col, icon) in enumerate(items):
        x = 5 + i * (cw + 5)
        laptop(d, x + 8, 62, 70, 45); T(d, x + 43, 50, t, 7.5, True, col)
        for j, ln in enumerate(sw.split("\n")): T(d, x + 43, 40 - j*9, ln, 6, False, GRAY)
        d.add(scaled(icon, sx=0.35, dx=x + 92, dy=60)); usb_cable(d, x + 80, 82, x + 98, 86)
    T(d, CW/2, 4, "통합 단계에서는 노트북이 빠지고 Pi 5가 메인이 됩니다. 노트북 1대는 SSH로 로그만 봅니다.", 6.5, False, GRAY)
    return d

def fig_esp_connect():
    d = Drawing(CW, 245)
    T(d, CW/2, 236, "<그림 A-1> ESP32 첫 연결: 선 하나, 화면 셋", 8.5, True, HEAD)
    # left: physical
    laptop(d, 20, 150, 80, 55); d.add(scaled(ic_esp32, sx=0.55, dx=120, dy=145)); usb_cable(d, 100, 175, 150, 170)
    T(d, 60, 138, "① 드라이버 설치 후", 6.5, True); T(d, 60, 130, "② micro-USB로 꽂기", 6.5, True)
    T(d, 170, 138, "빨간 LED 켜짐 = 전원 OK", 6.5, False, RED)
    step_badge(d, 15, 215, 1, BLK["A"])
    # right top: device manager
    mock_window(d, 250, 150, 240, 72, "장치 관리자", ["> 디스크 드라이브", "> 모니터", "v 포트(COM & LPT)", "     Silicon Labs CP210x USB to UART Bridge (COM3)"], hl={3})
    step_badge(d, 245, 218, 3, BLK["A"]); T(d, 370, 141, "③ 여기 COM 번호를 기억 (사람마다 다름)", 6.5, True)
    # bottom: arduino IDE menu
    mock_window(d, 20, 15, 225, 110, "Arduino IDE 2.x", ["파일  편집  스케치  도구  도움말", "도구 >  보드: \"ESP32 Dev Module\"       ← 보드 매니저에서 esp32 설치 후", "도구 >  포트: \"COM3\"                     ← ③에서 본 번호", "", "[→] 업로드 버튼  ← 클릭", "", "출력창:  Connecting....  Writing at 0x0001000...", "         Hard resetting via RTS pin...   ← 성공"], hl={1, 2, 7})
    step_badge(d, 15, 120, 4, BLK["A"])
    # bottom right: serial monitor
    mock_window(d, 260, 15, 230, 110, "시리얼 모니터  (도구 > 시리얼 모니터)", ["보드레이트:  115200 baud   ← 오른쪽 아래에서 바꾸기", "", "[SafeGuard] ESP32 hello test start", "{\"hello\":0,\"led\":1}", "{\"hello\":0,\"led\":0}", "{\"hello\":1,\"led\":1}", "...", "파란 LED가 1초마다 깜빡이면 완료"], hl={0, 7}, mono=True)
    step_badge(d, 255, 120, 5, BLK["A"])
    return d

def fig_breadboard():
    d = Drawing(CW, 215)
    T(d, CW/2, 205, "<그림 A-2> PIR + SHT31 브레드보드 연결 (선 7가닥)", 8.5, True, HEAD)
    # breadboard background
    R(d, 15, 25, 330, 160, colors.HexColor("#F4F6F6"), GRAY, 0.6, 3)
    for r in range(14):
        for c in range(30): C(d, 27 + c*10.5, 33 + r*10.5, 1.1, colors.HexColor("#BDC3C7"))
    T(d, 180, 190, "브레드보드 (같은 세로줄 5칸이 서로 연결됨)", 6.5, False, GRAY)
    # ESP32
    R(d, 35, 60, 90, 110, BLACK, GRAY, 0.5, 3); R(d, 50, 120, 60, 35, METAL); T(d, 80, 135, "ESP32 #1", 7, True, BLACK)
    R(d, 70, 60, 20, 6, METAL); T(d, 80, 50, "USB → 노트북", 5.5, False, GRAY)
    pin_y = {"3V3": 160, "GND": 146, "GPIO27": 132, "GPIO21": 118, "GPIO22": 104}
    for nm, py in pin_y.items():
        C(d, 125, py, 2, GOLD, BLACK, 0.3); T(d, 121, py - 2.3, nm, 5.5, True, WHITE, "end")
    # PIR box
    R(d, 240, 115, 90, 60, PCB, PCB_D, 0.6, 3); C(d, 300, 150, 12, WHITE, GRAY, 0.4); T(d, 262, 160, "PIR", 7.5, True, WHITE)
    pir_pins = [("VCC", 125), ("GND", 140), ("OUT", 155)]
    for nm, py in [("VCC", 162), ("GND", 148), ("OUT", 134)]:
        C(d, 240, py, 2, GOLD, BLACK, 0.3); T(d, 246, py - 2.3, nm, 5.5, True, WHITE, "start")
    # SHT31 box
    R(d, 240, 35, 90, 65, PCB, PCB_D, 0.6, 3); R(d, 295, 60, 14, 14, METAL); T(d, 262, 88, "SHT31", 7.5, True, WHITE)
    for nm, py in [("VCC", 80), ("GND", 68), ("SDA", 56), ("SCL", 44)]:
        C(d, 240, py, 2, GOLD, BLACK, 0.3); T(d, 246, py - 2.3, nm, 5.5, True, WHITE, "start")
    # wires: (esp pin y, target y, color, x_mid)
    def w(y1, y2, col, xm):
        L(d, 125, y1, xm, y1, col, 1.4); L(d, xm, y1, xm, y2, col, 1.4); L(d, xm, y2, 240, y2, col, 1.4)
    w(160, 162, WIRE_O, 150); w(160, 80, WIRE_O, 150)      # 3V3 -> PIR VCC, SHT VCC
    w(146, 148, WIRE_K, 165); w(146, 68, WIRE_K, 165)      # GND
    w(132, 134, WIRE_B, 180)                               # GPIO27 -> PIR OUT
    w(118, 56, WIRE_B, 195); w(104, 44, WIRE_B, 210)       # SDA, SCL
    # legend
    R(d, 355, 25, 140, 160, colors.HexColor("#FBFCFC"), GRAY, 0.5, 3); T(d, 425, 172, "연결표 (가이드 4.4 · 4.5절)", 7.5, True, HEAD)
    rows = [("PIR VCC", "3V3", WIRE_O), ("PIR GND", "GND", WIRE_K), ("PIR OUT", "GPIO27", WIRE_B), ("SHT31 VCC", "3V3", WIRE_O), ("SHT31 GND", "GND", WIRE_K), ("SHT31 SDA", "GPIO21", WIRE_B), ("SHT31 SCL", "GPIO22", WIRE_B)]
    for i, (a, b, col) in enumerate(rows):
        y = 155 - i*15; R(d, 362, y - 1, 10, 4, col); T(d, 378, y - 1, a, 6.5, False, BLACK, "start"); T(d, 432, y - 1, "→", 6.5); T(d, 444, y - 1, b, 6.5, True, BLACK, "start")
    T(d, 425, 38, "주황=3.3V  검정=GND  파랑=신호", 6, False, GRAY)
    T(d, CW/2, 8, "5V 핀이 아니라 3V3 핀. 전원은 ESP32 USB에서 옴(별도 전원 X). 시리얼에 {\"pir\":0,\"temp\":25.1,\"hum\":48.2} 가 뜨면 완료.", 6.5, False, RED)
    return d

def fig_pi_imager():
    d = Drawing(CW, 230)
    T(d, CW/2, 220, "<그림 B-1> Pi 5 OS 굽기 → 부팅 → SSH 접속", 8.5, True, HEAD)
    mock_window(d, 15, 110, 230, 100, "Raspberry Pi Imager", ["장치:  Raspberry Pi 5", "운영체제:  Raspberry Pi OS (64-bit)", "저장소:  [SD 카드 리더기 128GB]", "", "[다음] → 사용자 지정 설정 편집 →", "   호스트명 safeguard  /  사용자·비밀번호", "   Wi-Fi: 팀 핫스팟 SSID + 비밀번호", "   서비스: SSH 켜기  → [쓰기]"], hl={0, 1, 2, 6, 7}, title_fill=colors.HexColor("#C51A4A"))
    step_badge(d, 10, 205, 1, BLK["B"])
    # physical
    d.add(scaled(ic_pi, sx=0.6, dx=265, dy=115)); d.add(scaled(ic_sd, sx=0.4, dx=380, dy=150)); d.add(scaled(ic_adapter, sx=0.45, dx=400, dy=105))
    arrow(d, 395, 160, 345, 150, GRAY); T(d, 400, 185, "② SD를 Pi 아랫면 슬롯에", 6.5, True, BLACK, "start")
    arrow(d, 420, 118, 345, 128, GRAY); T(d, 400, 100, "③ 27W 어댑터 → USB-C (부팅 약 30초)", 6.5, True, BLACK, "start")
    step_badge(d, 258, 205, 2, BLK["B"])
    mock_window(d, 15, 10, 230, 90, "PowerShell (노트북, Pi와 같은 Wi-Fi)", ["> ssh pi@safeguard.local", "pi@safeguard.local's password: ******", "", "pi@safeguard:~ $ vcgencmd measure_temp", "temp=41.2'C", "pi@safeguard:~ $ vcgencmd get_throttled", "throttled=0x0        ← 전원 정상"], hl={0, 6}, title_fill=colors.HexColor("#012456"))
    step_badge(d, 10, 95, 4, BLK["B"])
    R(d, 260, 10, 230, 90, colors.HexColor("#FBFCFC"), GRAY, 0.5, 3); T(d, 375, 90, "안 될 때", 7.5, True, RED)
    for i, ln in enumerate(["• safeguard.local 못 찾음 → 핫스팟 켜져 있는지, 노트북도 같은 핫스팟인지", "• 그래도 안 되면 핫스팟 앱에서 Pi의 IP 확인 → ssh pi@192.168.x.x", "• 초록 LED가 안 깜빡이면 SD 굽기 실패 → Imager 다시", "• 비밀번호는 Imager에서 넣은 것"]):
        T(d, 268, 74 - i*14, ln, 6.3, False, BLACK, "start")
    return d

def fig_camera():
    d = Drawing(CW, 175)
    T(d, CW/2, 165, "<그림 B-2> 카메라 케이블 (Pi 전원 OFF 상태에서!)", 8.5, True, HEAD)
    R(d, 30, 65, 120, 70, PCB, PCB_D, 1, 3); T(d, 90, 125, "Pi 5 (CAM/DISP 커넥터 확대)", 6.5, True, WHITE)
    R(d, 60, 70, 12, 30, WHITE, BLACK, 0.5, 1); R(d, 85, 70, 12, 30, WHITE, BLACK, 0.5, 1); T(d, 66, 105, "CAM0", 5.5, True, WHITE); T(d, 91, 105, "CAM1", 5.5, True, WHITE)
    R(d, 85, 100, 12, 3, colors.HexColor("#5D4037")); T(d, 110, 101, "← 갈색 잠금 탭을 살짝 위로", 5.5, False, WHITE, "start")
    R(d, 88, 38, 6, 33, colors.HexColor("#F5B041")); R(d, 86, 36, 10, 8, colors.HexColor("#2E86C1")); T(d, 105, 50, "22핀 좁은 쪽 → Pi", 6, True, BLACK, "start"); T(d, 105, 41, "파란 면 = 잠금 탭 쪽, 금속 접점 = 반대", 6, False, GRAY, "start")
    d.add(scaled(ic_camera, sx=0.6, dx=250, dy=65))
    T(d, 370, 150, "동봉 15핀 케이블은 Pi 5에 안 꽂힘 → 22핀↔15핀 케이블 먼저 확인!", 6.5, True, RED)
    for i, ln in enumerate(["① Pi 전원 뽑기  ② 탭 올리기  ③ 케이블 끝까지 밀어 넣기  ④ 탭 눌러 잠그기  ⑤ 카메라 쪽(15핀)도 같은 방법", "⑥ 부팅 후:  rpicam-hello --list-cameras   → imx708 이 보이면 OK", "⑦ 사진:  rpicam-still -o test.jpg -t 2000   → 노트북에서 scp 로 받아 확인"]):
        T(d, 30, 24 - i*9, ln, 6.3, i == 0, BLACK, "start")
    return d

def fig_mmwave():
    d = Drawing(CW, 200)
    T(d, CW/2, 190, "<그림 B-3> mmWave 살리기: 노트북에서 먼저, 그다음 Pi", 8.5, True, HEAD)
    d.add(scaled(ic_mmwave, sx=0.6, dx=10, dy=95)); laptop(d, 125, 110, 60, 40); usb_cable(d, 95, 130, 128, 128)
    T(d, 60, 90, "① micro-USB 하나로 전원+통신", 6.5, True)
    steps = ["② TI 계정 → UniFlash, mmWave SDK, Industrial Toolbox, Demo Visualizer 설치",
             "③ 보드 S1(SOP) 스위치 → Flashing 모드 (보드 실크/TI 가이드 표 참고)",
             "④ UniFlash: 디바이스 IWR6843 → User UART COM → 'Out of Box Demo (ISK-ODS)' .bin → Load",
             "⑤ S1 → Functional 모드 → USB 재연결",
             "⑥ Demo Visualizer: xWR6843, ODS, COM 2개 지정 → Send Config → 손 흔들면 점이 찍힘",
             "⑦ 쓴 .cfg 파일 저장 (Pi에서 재사용)"]
    for i, ln in enumerate(steps): T(d, 200, 165 - i*13, ln, 6.5, i in (3, 5), BLACK, "start")
    mock_window(d, 10, 10, 230, 70, "Pi 5 터미널", ["$ ls /dev/ttyACM*", "/dev/ttyACM0  /dev/ttyACM1", "   ↑ CLI(115200)   ↑ Data(921600)", "$ pip install pyserial  → cfg 전송 + 프레임 수신 (TI 파이썬 예제)"], hl={1}, title_fill=colors.HexColor("#012456"))
    T(d, 125, 4, "⑧ Pi에 꽂고 포트 2개 확인. 반복 리셋되면 config.txt에 usb_max_current_enable=1", 6.3, False, BLACK)
    R(d, 255, 10, 235, 70, colors.HexColor("#FDEDEC"), RED, 0.6, 3); T(d, 372, 70, "이번 단계의 목표는 '점 구름이 보인다'까지", 7, True, RED)
    for i, ln in enumerate(["호흡 검출(Vital Signs)은 그다음 단계.", "점 구름 수신 = 통신 성공이지 탑승자 검출이 아님.", "가장 비싼 부품: 안테나 앞 금속·손 금지, 정전기 주의."]):
        T(d, 262, 54 - i*13, ln, 6.3, False, BLACK, "start")
    return d

def fig_uwb():
    d = Drawing(CW, 215)
    T(d, CW/2, 205, "<그림 C-1> UWB 두 노드: 라벨 → 설정 → 거리 보기", 8.5, True, HEAD)
    # two nodes
    d.add(scaled(ic_uwb, sx=0.5, dx=5, dy=130)); R(d, 20, 190, 50, 12, BLK["B"], BLK["B"], 0.3, 2); T(d, 45, 193.5, "차량측 라벨", 6, True, WHITE)
    d.add(scaled(ic_uwb, sx=0.5, dx=95, dy=130)); R(d, 110, 190, 50, 12, BLK["C"], BLK["C"], 0.3, 2); T(d, 135, 193.5, "보호자측 라벨", 6, True, WHITE)
    T(d, 92, 112, "① 똑같이 생겼으니 마스킹테이프로 먼저 라벨", 6.5, True)
    mock_window(d, 200, 120, 290, 82, "Tera Term — 115200 / 8N1  (한 노드씩 USB로)", ["(Enter 두 번)", "dwm> si                     ← 시스템 정보", "dwm> nis 0x1234             ← 네트워크 ID (둘 다 같은 값)", "dwm> nmt   ← 차량측에서만: TAG   |   nmi  ← 보호자측에서만: ANCHOR init", "dwm> lec                    ← 차량측에서: 거리 출력 시작/정지", "DIST,1,AN0,xxxx,0.00,0.00,0.00,2.31   ← 2.31 m"], hl={3, 5}, title_fill=colors.HexColor("#1E8449"))
    T(d, 345, 112, "② ③ 설정은 노트북 1대에 한 노드씩 꽂아서", 6.5, True)
    # distance test
    d.add(scaled(ic_uwb, sx=0.3, dx=12, dy=58)); laptop(d, 15, 20, 45, 28); T(d, 38, 12, "차량측 (노트북)", 5.5)
    for i, m in enumerate(["0.5", "1", "2", "3", "5", "7"]):
        x = 110 + i * 60; L(d, x, 60, x, 70, GRAY, 0.8); T(d, x, 73, m + " m", 6, True)
    L(d, 90, 65, 470, 65, GRAY, 0.8)
    d.add(scaled(ic_powerbank, sx=0.3, dx=380, dy=18)); d.add(scaled(ic_uwb, sx=0.3, dx=420, dy=22)); T(d, 440, 10, "보호자측 (보조배터리)", 5.5)
    T(d, 280, 48, "④ 줄자로 지점 표시 → 각 지점 20초 정지 → lec 값 평균·표준편차 기록 → 오차표 (가이드 6.4절)", 6.5, False, BLACK)
    T(d, 280, 36, "실내는 벽 반사로 값이 튐 → 긴 복도나 야외에서", 6.3, False, GRAY)
    T(d, 280, 24, "⑤ 보조배터리에 꽂고 10분 방치 → 꺼지면 저전류 모드/다른 배터리/더미 부하 (가이드 6.3절)", 6.5, True, RED)
    return d

def fig_share():
    d = Drawing(CW, 95)
    T(d, CW/2, 86, "<그림 4> 매일 저녁 팀 채팅에 올릴 것 (이 양식 그대로)", 8.5, True, HEAD)
    mock_window(d, 20, 5, 300, 72, "팀 채팅", ["[블록 A · 10/17] ESP32 hello OK (COM4), PIR 손 흔들면 1, SHT31 24.8°C", "막힌 것: SHT31 not found → 주소 0x45였음, 해결", "내일: 12V 레일 + 팬 1개", "📷 사진 2장 첨부 (배선 / 시리얼 모니터)"], hl={1}, title_fill=colors.HexColor("#F7E600"))
    R(d, 335, 5, 155, 72, colors.HexColor("#FBFCFC"), GRAY, 0.5, 3)
    for i, ln in enumerate(["왜?", "• 통합 때 '이 선이 어디 갔더라'가", "  제일 오래 걸림 → 사진 필수", "• 막힌 걸 적어야 다른 사람이 도움", "• 가이드 완료 조건 표의 번호(A1~)로"]):
        T(d, 342, 64 - i*12, ln, 6.5, i == 0, HEAD if i == 0 else BLACK, "start")
    return d

# ================================================================= 문서 구성
story.append(Spacer(1, 6))
story.append(Paragraph("SafeGuard 하드웨어 착수 가이드", S["title"]))
story.append(Paragraph("뭐부터 할까? — 거의 처음부터 시작하는 사람을 위한 그림 설명서", S["sub"]))
story.append(Paragraph(f"v1.0  |  {TODAY}  |  팀 두고내리지말아조  |  연결 가이드 v1.0 · 부품 그림책과 함께 보기", S["sub"]))
story.append(Spacer(1, 8))
story.append(fig_timeline())
story.append(Spacer(1, 4))
P("<b>현재 상황 한 줄</b>: 9월 12일에 장비를 다 받았고 가이드·그림책·발표자료까지 만들었지만, <b>실제로 선을 꽂고 켜 본 것은 아직 거의 없습니다.</b> "
  "그래서 지금은 <b>1단계 '단독 검증'</b>의 맨 앞입니다. 세 사람이 각자 자기 블록을 들고 '불이 켜지고 값이 찍히는 것'까지 만드는 게 이번 주 목표입니다.")
story.append(fig_three_people())
story.append(Spacer(1, 4))
P("<b>이 문서 보는 법</b>: 1장은 다 같이 읽고(30분이면 됨), 2·3·4장은 자기 블록만 읽으면 됩니다. 각 단계 끝에 '완료 표시'가 있으니 되면 체크하고 사진 찍어 채팅에 올립니다. 자세한 핀 번호·명령은 연결 가이드의 절 번호를 적어 두었습니다.")
story.append(PageBreak())

# ---------------------------------------------------------------- 1장 공통
H1("1. 다 같이 먼저 할 것 (첫날, 1~2시간)")
H2("1.1 노트북과 프로그램 준비")
story.append(fig_laptops())
TBL(["담당", "설치할 것", "어디서", "확인 방법"],
    [["담당 1 (A)", "CP210x 드라이버, Arduino IDE 2.x, 보드 매니저에서 esp32", "저장소 CP210x_VCP_Windows 폴더 / arduino.cc", "도구 → 보드에 'ESP32 Dev Module' 보임"],
     ["담당 2 (B)", "Raspberry Pi Imager, (Windows) TI UniFlash + mmWave Demo Visualizer", "raspberrypi.com/software / ti.com (계정 필요)", "Imager 실행됨, UniFlash 실행됨"],
     ["담당 3 (C)", "Tera Term 또는 PuTTY", "teratermproject.github.io / putty.org", "시리얼 포트 선택 화면이 열림"],
     ["모두", "팀 핫스팟 하나 정하기 (핸드폰) — SSID·비밀번호 공유", "-", "세 노트북이 같은 핫스팟에 붙음"]],
    [20*mm, 58*mm, 52*mm, CW-130*mm])
story.append(PageBreak())
H2("1.2 상자 열고 부품 나누기 (부품 그림책 1쪽 지도 사용)")
story.append(fig_map())
P("상자 A/B/C 세 개를 만들어 위 지도 색깔대로 나눕니다. 공용 도구(테스터기·인두·매트)는 블록 A 자리에 둡니다. 없는 부품·파손은 그 자리에서 채팅에 올립니다.")
story.append(PageBreak())
H2("1.3 지금 당장 주문해야 하는 것 (없으면 중간에 멈춤)")
d = Drawing(CW, 100); d.add(scaled(ic_cables, sx=1.0, dx=0, dy=0));
T(d, 320, 80, "micro-USB 데이터 케이블 4개", 8, True, HEAD, "start"); T(d, 320, 68, "mmWave · UWB 차량측 · ESP32 · UWB 보호자측. 현재 1개뿐.", 6.5, False, BLACK, "start"); T(d, 320, 58, "충전 전용 케이블은 인식 안 됨 → 노트북에 꽂아 장치가 뜨는지로 판별", 6.5, False, RED, "start")
T(d, 320, 40, "Pi 5용 카메라 케이블 (22핀 mini ↔ 15핀)", 8, True, HEAD, "start"); T(d, 320, 28, "Camera Module 3 동봉 케이블은 Pi 4용. Pi 5에 안 꽂힘. ~3,000원", 6.5, False, BLACK, "start")
T(d, 320, 12, "벤치용 12V 5A 어댑터 + DC잭 터미널", 8, True, HEAD, "start"); T(d, 320, 1, "실내에서 팬·부저·컨버터를 돌릴 12V 소스. 시거잭은 실차 전용. ~12,000원", 6.5, False, BLACK, "start")
story.append(d)
TBL(["항목", "수량", "담당", "주문 여부"], [["micro-USB 데이터 케이블 (1m)", "4", "담당 3", "☐"], ["Raspberry Pi 5 카메라 케이블 Standard-Mini 200~300mm", "1", "담당 2", "☐"], ["12V 5A DC 어댑터 (5.5×2.1) + DC잭→터미널 변환", "1+1", "담당 1", "☐"], ["브레드보드 + 점퍼선 (기존 Pi 4B 것 재활용 가능)", "1", "담당 1", "☐"], ["Pi 5 액티브 쿨러 (권장)", "1", "담당 2", "☐"], ["USB 전력 측정기 (선택, 소비전력 비교용)", "1", "담당 1", "☐"]], [84*mm, 14*mm, 20*mm, CW-118*mm])
H2("1.4 안전 규칙 5개 (작업대에 붙이기)")
NUM(["배선은 <b>전원 OFF</b>에서. 전원 넣기 전 테스터기 저항 모드로 +12V–GND가 쇼트(0Ω)가 아닌지 확인.",
     "<b>3.3V·5V 핀에 12V 절대 금지.</b> 빨강=12V, 주황/노랑=5V, 검정=GND로 색 고정.",
     "<b>서보는 ESP32/Pi의 5V 핀에서 급전 금지</b> (컨버터#2에서만). 순간 2A 이상.",
     "다이오드 띠(은색)는 +12V 쪽. 거꾸로 달면 전원 넣는 순간 퓨즈 단선.",
     "Pi 5는 반드시 <font face='Courier'>sudo shutdown -h now</font> 후 전원 분리. 카메라 케이블은 전원 OFF에서만."])
story.append(fig_share())
story.append(PageBreak())

# ---------------------------------------------------------------- 2장 블록 A
H1("2. 담당 1 · 블록 A: 전원 · 구동 · ESP32 (이번 주 할 일)")
P("순서를 지키면 부품을 태울 일이 거의 없습니다. <b>ESP32 단독 → 센서 2개 → 12V 레일 → 팬·부저</b> 순서. 서보는 이번 주 범위 밖입니다.")
H2("A-1. ESP32 첫 연결 (반나절)")
story.append(fig_esp_connect())
NUM(["드라이버: 저장소의 <font face='Courier'>CP210x_VCP_Windows\\CP210x_VCP_Windows\\CP210xVCPInstaller_x64.exe</font> 실행 → 다음 → 완료.",
     "ESP32 옆면 은색 사다리꼴 구멍(micro-USB)에 케이블 → 노트북. 빨간 LED 켜짐.",
     "윈도우 키 → '장치 관리자' → 포트(COM & LPT) → <b>Silicon Labs CP210x (COMx)</b>. 안 보이면 케이블 교체.",
     "Arduino IDE: 파일 → 환경설정 → 추가 보드 관리자 URL에 아래 주소 → 도구 → 보드 매니저 → esp32 설치 → 보드 'ESP32 Dev Module', 포트 COMx."])
CODE("https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json")
NUM(["파일 → 열기 → <font face='Courier'>hardware\\esp32\\esp32_hello_test\\esp32_hello_test.ino</font> → 업로드(→). 'Connecting...'만 반복되면 <b>BOOT 버튼 누른 채</b> 다시 업로드.",
     "도구 → 시리얼 모니터 → 115200 → JSON 한 줄씩 올라오고 파란 LED 깜빡이면 완료."])
P("<b>완료 표시 A1</b> ☐ LED 깜빡임 + 시리얼 출력 사진 1장 → 채팅")
story.append(PageBreak())
H2("A-2. PIR + SHT31 브레드보드 (반나절)")
story.append(fig_breadboard())
NUM(["ESP32를 브레드보드 가운데 홈에 걸치게 꽂습니다 (양쪽 핀 줄이 서로 다른 쪽에).",
     "위 연결표대로 7가닥. <b>3V3</b> 핀을 씁니다 (5V 아님).",
     "Arduino IDE → 스케치 → 라이브러리 관리 → 'Adafruit SHT31' 설치. 예제 → Adafruit SHT31 → SHT31test 업로드 → 온습도 뜨는지. 안 뜨면 주소를 0x45로 바꿔 시도.",
     "PIR: 전원 후 <b>30초 기다린 뒤</b> 손 흔들기. 테스터기로 OUT–GND 전압을 재서 감지 시 3.3V(HIGH)인지 확인. 반대면 코드에서 반전.",
     "두 센서를 합쳐 1초마다 <font face='Courier'>{\"pir\":1,\"temp\":27.3,\"hum\":45.1}</font> 형식으로 출력하는 스케치로 정리 (이 형식이 나중에 Pi 입력)."])
P("<b>완료 표시 A2</b> ☐ 시리얼에 pir/temp/hum이 1초마다 뜸, 손 흔들면 pir 0→1")
H2("A-3. 12V 레일 부하 없이 (반나절) — 가이드 4.1절 그림 2")
NUM(["12V 어댑터(추가 구매) → DC잭 터미널 → 퓨즈홀더(10A) → 비상정지 NC 접점 → 퓨즈홀더(5A) → 컨버터#1·#2 입력. 아직 팬·부저는 연결하지 않음.",
     "비상정지 접점 판별: 테스터기 부저 모드. <b>안 누른 상태에서 '삐', 누르면 끊기는 쌍 = NC</b>.",
     "전원 넣기 전: 저항 모드로 12V+ – GND 쇼트 아닌지. 넣은 후: 컨버터 출력 5.0±0.2V, 비상정지 누르면 구동 분기 0V (컨버터#1은 5V 유지)."])
P("<b>완료 표시 A3</b> ☐ 5V 두 계통 측정값, 비상정지 동작 영상")
H2("A-4. MOSFET → 팬 1개 (반나절) — 가이드 4.2절 그림 3")
NUM(["브레드보드에 IRLZ44N 1개: 표식면 보고 왼쪽부터 G–D–S. G ← 220Ω ← ESP32 GPIO25, G–S 사이 10kΩ, S → GND, D → 팬 검정(−), 팬 빨강(+) → 12V 레일. 1N5819 띠가 +12V 쪽.",
     "ESP32 GND와 12V GND를 <b>반드시 한 선으로 묶기</b> (안 묶으면 팬이 안 돎).",
     "GPIO25를 HIGH/LOW로 토글하는 스케치 → 팬 ON/OFF. MOSFET 손으로 만져 미지근 이하.",
     "되면 팬 2개 병렬, 그다음 GPIO26 + 두 번째 MOSFET으로 부저."])
P("<b>완료 표시 A4</b> ☐ 시리얼 명령 <font face='Courier'>FAN 1</font> / <font face='Courier'>BUZ 1</font>로 ON/OFF 영상. 여기까지가 이번 주 블록 A 목표.")
story.append(PageBreak())

# ---------------------------------------------------------------- 3장 블록 B
H1("3. 담당 2 · 블록 B: Pi 5 · 카메라 · mmWave (이번 주 할 일)")
H2("B-1. OS 굽기 → 부팅 → SSH (반나절)")
story.append(fig_pi_imager())
NUM(["Imager '사용자 지정 설정'에서 <b>SSID = 팀 핫스팟 이름, 비밀번호 = 그 핫스팟의 Wi-Fi 비밀번호</b>. (SSID 비밀번호라는 건 따로 없음)",
     "굽기 끝나면 SD를 Pi 아랫면 슬롯에 → 27W 어댑터 → 초록 LED 깜빡이며 부팅.",
     "노트북을 같은 핫스팟에 붙이고 PowerShell에서 <font face='Courier'>ssh 사용자@safeguard.local</font>.",
     "접속되면 아래 3줄. <font face='Courier'>get_throttled</font>가 0x0이면 전원 정상."])
CODE("sudo apt update && sudo apt full-upgrade -y\nsudo raspi-config        # Interface Options → I2C, Serial Port(로그인 셸 No, 하드웨어 Yes)\necho usb_max_current_enable=1 | sudo tee -a /boot/firmware/config.txt   # 비PD 전원·USB 3개용")
P("<b>완료 표시 B1</b> ☐ SSH 접속 화면 캡처 (hostname, get_throttled=0x0)")
H2("B-2. 카메라 (1시간, 케이블 도착 후)")
story.append(fig_camera())
P("<b>완료 표시 B2</b> ☐ <font face='Courier'>rpicam-hello --list-cameras</font>에 imx708, test.jpg 1장")
story.append(PageBreak())
H2("B-3. mmWave 레이더 (1~2일, 가장 어려움)")
story.append(fig_mmwave())
NUM(["TI 사이트에서 계정 → UniFlash, mmWave SDK 3.x, mmWave Industrial Toolbox(Resource Explorer), mmWave Demo Visualizer(Chrome + TI Cloud Agent).",
     "보드 S1 스위치 → Flashing 모드. 조합은 보드 실크 또는 'IWR6843ISK-ODS User's Guide' SOP 표 (플래싱/기능 두 조합만 기억).",
     "USB 연결 → 장치 관리자에 'XDS110 Class Application/User UART'와 'Auxiliary Data Port' COM 번호 확인.",
     "UniFlash → IWR6843 → User UART COM → Industrial Toolbox의 Out-of-Box Demo (IWR6843ISK-ODS) .bin → Load Image.",
     "S1 → Functional 모드 → USB 재연결 → Visualizer: 플랫폼 xWR6843, 안테나 ODS, COM 2개 → Send Config → Plots에서 손 흔들면 점.",
     ".cfg 저장 → Pi에 꽂고 <font face='Courier'>ls /dev/ttyACM*</font> 2개 확인 → pyserial로 cfg 전송·프레임 수신 (TI 파이썬 파서 예제)."])
P("<b>완료 표시 B3</b> ☐ Visualizer 점 구름 캡처, Pi에서 프레임/초 숫자. <b>호흡 검출은 이번 주 목표가 아님</b>.")
WARN("mmWave는 블록 B에서 가장 오래 걸립니다. B1·B2가 끝나면 B3에 들어가되, 하루 이상 막히면 채팅에 올리고 담당 1·3이 같이 봅니다. 가이드 5.3절과 부록 C FAQ 참고.")
story.append(PageBreak())

# ---------------------------------------------------------------- 4장 블록 C
H1("4. 담당 3 · 블록 C: UWB 거리 측정 (이번 주 할 일)")
story.append(fig_uwb())
H2("C-1. 라벨 + 설정 (2시간)")
NUM(["두 보드에 마스킹테이프로 '차량' '보호자' 라벨.",
     "차량측 노드를 micro-USB로 노트북에 → 장치 관리자 COM 번호 → Tera Term 시리얼 115200 → <b>Enter 두 번</b> → <font face='Courier'>dwm></font> 프롬프트.",
     "<font face='Courier'>si</font> 로 펌웨어 확인 (PANS). <font face='Courier'>nis 0x1234</font> → <font face='Courier'>nmt</font> (태그, 재부팅됨).",
     "보호자측 노드로 바꿔 꽂고 같은 방법으로 <font face='Courier'>nis 0x1234</font> → <font face='Courier'>nmi</font> (앵커 initiator).",
     "차량측을 다시 꽂고 <font face='Courier'>lec</font> → 보호자측 노드를 켜 둔 상태에서 거리(m)가 1초에 몇 번씩 찍히면 성공. 같은 명령을 다시 치면 정지.",
     "거리가 안 뜨면: 네트워크 ID가 같은지, 한쪽이 nmi(앵커)인지, 두 노드 모두 전원 들어왔는지."])
P("<b>완료 표시 C1</b> ☐ si 출력 2장, lec 거리 출력 캡처")
NOTE("보고서의 '차량 Anchor / 보호자 Tag'와 반대로 보이지만, PANS 펌웨어는 거리값을 <b>Tag 쪽 셸에 출력</b>하기 때문에 Pi가 읽을 차량측이 Tag여야 합니다. 발표 용어는 '차량측/보호자측 노드'로 씁니다. 보드에 다른 펌웨어가 올라와 있으면 명령이 다를 수 있으니 si 출력을 먼저 확인하세요.")
H2("C-2. 보조배터리 테스트 (10분 + 기다림)")
NUM(["보호자측 노드를 보조배터리에 꽂고 LED 점등 확인 → <b>10분 방치</b>.",
     "꺼지면: 배터리의 저전류(소형기기) 모드 버튼 → 없으면 다른 보조배터리 → 그래도 안 되면 USB LED 조명 같은 더미 부하를 같이 꽂기."])
P("<b>완료 표시 C2</b> ☐ 10분 후에도 LED 켜짐 (시간 적힌 사진 2장)")
H2("C-3. 거리 오차표 (반나절, 복도나 야외)")
TBL(["실거리(m)", "평균 측정(m)", "표준편차", "오차(m)", "비고 (LOS/가림)"], [[m, "", "", "", ""] for m in ["0.5", "1", "2", "3", "5", "7"]], [26*mm, 32*mm, 26*mm, 26*mm, CW-110*mm])
P("5m 지점에서 10초 이상 연속으로 5m 초과가 찍히는지 꼭 확인 (이탈 판정 기준). 이 표가 그대로 성능지표 '보호자 이탈 판정오차'가 됩니다.")
P("<b>완료 표시 C3</b> ☐ 오차표 채움. 다음은 Pi에서 pyserial로 lec를 읽는 스크립트 (가이드 6.5절) — 담당 2와 같이.")
story.append(Spacer(1, 6))

# ---------------------------------------------------------------- 5장 체크표
H1("5. 이번 주 완료 체크표 (프린트해서 벽에)")
TBL(["블록", "번호", "완료 조건", "증거", "한 날짜", "확인"],
    [["A", "A1", "ESP32 LED 깜빡임 + 시리얼 출력", "사진", "", "☐"], ["A", "A2", "PIR/SHT31 JSON 1초마다, 손 흔들면 pir=1", "캡처", "", "☐"], ["A", "A3", "12V 레일 5V 두 계통, 비상정지 차단", "측정값·영상", "", "☐"], ["A", "A4", "FAN 1 / BUZ 1 명령으로 ON/OFF", "영상", "", "☐"],
     ["B", "B1", "SSH 접속, get_throttled 0x0", "캡처", "", "☐"], ["B", "B2", "카메라 목록 imx708 + test.jpg", "사진", "", "☐"], ["B", "B3", "mmWave 점 구름 (Visualizer) + Pi 프레임 수신", "캡처", "", "☐"],
     ["C", "C1", "두 노드 설정, lec 거리 출력", "캡처", "", "☐"], ["C", "C2", "보조배터리 10분 유지", "사진", "", "☐"], ["C", "C3", "거리 오차표 6지점", "표", "", "☐"],
     ["공통", "0", "추가 구매 6종 주문, 핫스팟 공유, 부품 분류", "채팅", "", "☐"]],
    [14*mm, 12*mm, 72*mm, 22*mm, 24*mm, CW-144*mm])
H2("다음 주 (A1~C3 다 되면)")
BUL(["<b>2단계 통합 (다같이, 1일)</b>: GND 공통 → Pi USB에 ESP32·UWB·mmWave 3개 → 12V 투입 순서 → 통합 체크리스트 12항목 (가이드 7장).",
     "<b>3단계 FSM</b>: Pi에서 ESP32 JSON, UWB 거리, mmWave 프레임을 한 로그로 모으고 상태 전이 코드 작성. 기존 <font face='Courier'>hardware/pi_hardware_logger.py</font>는 Pi 4B 핀맵이라 새로 씀.",
     "<b>선택</b>: 서보(창문), ESP32 #2 워치독은 핵심 흐름이 돈 뒤에."])
H2("막히면")
TBL(["증상", "먼저 볼 것"],
    [["ESP32 업로드 'Failed to connect'", "BOOT 누른 채 업로드 / 데이터 케이블 / 드라이버"], ["COM 포트가 아예 안 뜸", "충전 전용 케이블 (가장 흔함)"], ["SHT31 not found", "SDA/SCL 바뀜, 주소 0x45"], ["PIR 항상 1 또는 0", "30초 워밍업, 극성 반전, 창밖 움직임 → 렌즈 마스킹"],
     ["safeguard.local 못 찾음", "같은 핫스팟인지, IP로 접속"], ["카메라 목록 없음", "케이블 방향·22핀 여부·DISP 포트에 꽂음"], ["mmWave Visualizer no data", "SOP가 플래싱 모드 그대로 / 포트 순서"], ["UWB lec에 거리 없음", "nis 불일치, 둘 다 태그, 앵커가 nmi 아님"], ["보조배터리 꺼짐", "저전류 모드 / 더미 부하"]],
    [60*mm, CW-60*mm])
P("<i>연결 가이드 v1.0(18쪽)과 부품 그림책(8쪽)은 hardware/docs 폴더에 있습니다. 이 문서는 '무엇을 어떤 순서로'만 다루고, 핀 번호·회로·명령 전체는 가이드를 봅니다.</i>")

doc.build(story)
try: os.remove(os.path.join(HERE, "_tmp_unused.pdf"))
except OSError: pass
print("OK", OUT_PDF)
