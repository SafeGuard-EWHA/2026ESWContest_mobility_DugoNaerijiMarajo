# -*- coding: utf-8 -*-
"""부품 아이콘 PNG 추출 — hardware/docs/build_parts_book.py의 ic_* 그리기 함수를 글자 없이 렌더링."""
import os
import sys

import io

import pymupdf
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "hardware", "docs", "build_parts_book.py")
OUT = os.path.join(HERE, "img", "final", "icons")
os.makedirs(OUT, exist_ok=True)

code = open(SRC, encoding="utf-8").read()
code = code[:code.index("# ---------------------------------------------------------------- 부품 카드 데이터")]
ns = {"__name__": "parts_icons"}
sys.argv = ["x", os.devnull]
exec(compile(code, SRC, "exec"), ns)
ns["T"] = lambda *a, **k: None  # 부품 그림 안의 작은 안내 글자 제거



def save_png(d, path):
    """Drawing → PDF(메모리) → PNG (renderPM 백엔드가 없어 pymupdf로 래스터화)."""
    buf = io.BytesIO()
    renderPDF.drawToFile(d, buf)
    page = pymupdf.open(stream=buf.getvalue(), filetype="pdf")[0]
    page.get_pixmap(dpi=400).save(path)


ICONS = ["pi", "camera", "mmwave", "uwb", "esp32", "sht31", "pir", "buzzer", "servo", "estop", "powerbank"]
for name in ICONS:
    d = Drawing(150, 95)
    ns["ic_" + name](d)
    save_png(d, os.path.join(OUT, name + ".png"))
d = Drawing(150, 95)
ns["ic_fan"](d, True)
save_png(d, os.path.join(OUT, "fan.png"))
print("icons:", sorted(os.listdir(OUT)))
