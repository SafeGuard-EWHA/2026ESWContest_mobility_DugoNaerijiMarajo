# -*- coding: utf-8 -*-
"""Vital Signs 호흡수 그래프 (Pi 2차, 3차 측정, 친구가 날숨을 1분씩 직접 셈).

TI Visualizer 표시 규칙과 같게 호흡 흔들림(breath_dev) 0.02 미만은 '숨 참음'으로 보고 값에서 뺀다.
이 규칙으로 계산한 1분 중앙값은 hardware/mmwave/vital_signs/README.md 표와 같다.

  python build_vital_fig.py [CSV 폴더 (기본: 바탕화면)]
출력: img/final/fig_vital_breath.png
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})
RUNS = [
    ("vital2.csv", "2차: 거리 자동 (칸 15 = 1.26 m), 평소 호흡", [(30, 90, 22), (120, 180, 25)], "#C62828"),
    ("vital3.csv", "3차: 거리 고정 (칸 11 = 0.95 m), 천천히 호흡", [(30, 90, 13), (120, 180, 12)], "#2E7D32"),
]

fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
for ax, (fn, title, counts, col) in zip(axes, RUNS):
    d = pd.read_csv(os.path.join(SRC, fn))
    t = d.wall_time - d.wall_time.iloc[0]
    d = d.assign(t=t)[d.breath_rate.notna()]
    ok = d[d.breath_dev >= 0.02]
    hold = d[d.breath_dev < 0.02]
    ax.scatter(ok.t, ok.breath_rate, s=14, c="#90A4AE", label="레이더 값 (약 1.4초마다)")
    ax.scatter(hold.t, [4] * len(hold), s=14, marker="|", c="#B0BEC5", label="숨 참음 판정 (제외)")
    for a, b, truth in counts:
        seg = ok[(ok.t >= a) & (ok.t < b)].breath_rate
        med = seg.median()
        ax.hlines(truth, a, b, colors="#111", lw=3, label="친구가 센 값 (1분)" if a == 30 else None)
        ax.hlines(med, a, b, colors=col, lw=3, ls="--", label="레이더 1분 중앙값" if a == 30 else None)
        diff = med - truth
        ax.text((a + b) / 2, max(truth, med, 20.5) + 3.4, f"정답 {truth} / 레이더 {med:.1f}\n차이 {diff:+.1f} ({diff / truth * 100:+.0f}%)",
                ha="center", fontsize=10, fontweight="bold", color=col, bbox=dict(fc="white", ec="none", alpha=0.9))
    ax.axhline(21.8, color="#888", lw=0.8, ls=":")
    ax.text(182, 22.1, "펌웨어 최대 출력 21.8", fontsize=8.5, color="#666", ha="right")
    ax.set_title(title, fontsize=11.5, fontweight="bold", loc="left")
    ax.set_xlabel("시간 (초)"); ax.set_xlim(0, 182); ax.set_ylim(0, 33)
    ax.grid(color="#EEE")
axes[0].set_ylabel("호흡수 (회/분)")
h, lab = axes[0].get_legend_handles_labels()
fig.legend(h, lab, loc="lower center", bbox_to_anchor=(0.5, 0.055), ncol=4, fontsize=9.5, frameon=False)
fig.text(0.01, 0.01, "IWR6843ISK-ODS + TI Vital Signs With People Tracking 펌웨어, Raspberry Pi 5 수신, 2026.10.24, 성인 1명 착석, 각 3분. "
         "정답은 친구가 날숨만 1분씩 셈. 심박은 정답 미측정이라 그리지 않음.", fontsize=9, color="#555")
fig.tight_layout(rect=(0, 0.11, 1, 1))
out = os.path.join(HERE, "img", "final", "fig_vital_breath.png")
fig.savefig(out, dpi=180)
print("saved", out)
