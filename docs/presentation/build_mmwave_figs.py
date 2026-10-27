# -*- coding: utf-8 -*-
"""결선 보고서용 실측 그래프 (mmWave 레이더, Pi 카메라) — 모두 블록 B 시험 원본 CSV에서 그림.

출력: img/final/fig_*.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "final")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False})
NAVY, AMBER, GREEN, RED, GRAY = "#1B2A41", "#E39B1B", "#2E8B57", "#C0392B", "#8A949E"


def rel(df, t0=None):
    t0 = df.wall_time.iloc[0] if t0 is None else t0
    return df.wall_time - t0


# ---------- 1. 정지 착석 시험 A/B/C (2026-10-24, 5분, 센서 1.2 m) ----------
csv = os.path.join(ROOT, "B회신_20261027", "csv")
tests = [
    ("A  원본 cfg (6 m 방), 3명 착석", "testA_origcfg_3people_still_orig.csv", GRAY, (78, 240), "정지 중 0명 판정 0%"),
    ("B  차량용 cfg (ODS_sedan_est), 1명 착석", "testB_sedancfg_1person_still_car.csv", GREEN, (78, 240), "정확히 1명 95.7%, 유령 0"),
    ("C  원본 cfg (6 m 방), 1명 착석", "testC_origcfg_1person_still_orig1.csv", RED, (85, 240), "정확히 1명 0%, 유령 2~5개"),
]
fig, axes = plt.subplots(3, 1, figsize=(10, 6.2), sharex=True)
for ax, (label, fn, col, (s, e), note) in zip(axes, tests):
    d = pd.read_csv(os.path.join(csv, fn))
    t = rel(d)
    ax.axvspan(s, e, color=col, alpha=0.08)
    ax.step(t, d.num_tracks, where="post", color=col, lw=1.2)
    ax.axvline(240, color=NAVY, ls="--", lw=1)
    ax.set_ylim(-0.3, 6.5); ax.set_yticks([0, 1, 2, 3, 4, 5, 6])
    ax.set_ylabel("추적 수")
    ax.set_title(label, loc="left", fontsize=12, fontweight="bold", color=NAVY)
    ax.text(s + 3, 5.6, note, fontsize=11, color=col, fontweight="bold")
axes[1].add_patch(Rectangle((78, 0.4), 162, 1.2, fill=False, ec=RED, lw=2.2))
axes[0].text(242, 5.6, "일어나 퇴장", fontsize=10, color=NAVY)
axes[-1].set_xlabel("시간 (초)   |   음영 = 가만히 앉아 있는 구간, 점선 = 퇴장")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_still_tests.png"), dpi=200)
plt.close(fig)

# ---------- 2. 시험 3 타임라인 (2026-10-27, 레이더 1.05 m) ----------
t3 = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
d = pd.read_csv(os.path.join(t3, "test3_radar.csv"))
act = pd.read_csv(os.path.join(t3, "test3_action_times.csv"))
t0 = float(act.loc[act.event == "start_empty", "안내_pi_time"].iloc[0])
t = rel(d, t0)
phases = [(0, 178.7, "빈자리", GRAY), (178.7, 301.3, "착석 · 정지", GREEN), (301.3, 388.4, "퇴장 후 빈자리", RED), (388.4, 420.7, "재착석", GREEN)]
fig, ax = plt.subplots(figsize=(10, 3.6))
for s, e, lab, col in phases:
    ax.axvspan(s, e, color=col, alpha=0.08)
    ax.text((s + e) / 2, 3.55, lab.replace(" · ", ", "), ha="center", fontsize=11, color=col, fontweight="bold")
ax.step(t, d.num_tracks, where="post", color=NAVY, lw=1.2, label="추적 수")
ax.fill_between(t, 0, d.presence * 0.4, step="post", color=AMBER, alpha=0.5, label="재실 신호(presence)")
ax.add_patch(Rectangle((303, 0.6), 84, 2.0, fill=False, ec=RED, lw=2.2))
ax.annotate("사람이 나간 뒤에도\n다시 앉을 때까지 87초 동안\n추적 2개가 남음", xy=(387, 1.4), xytext=(435, 1.0), fontsize=10.5,
            color=RED, ha="left", arrowprops=dict(arrowstyle="->", color=RED))
ax.set_xlim(-5, 545); ax.set_ylim(-0.2, 3.9); ax.set_yticks([0, 1, 2, 3])
ax.set_xlabel("시간 (초, 빈자리 시작 = 0)"); ax.set_ylabel("추적 수")
ax.legend(loc="upper left", bbox_to_anchor=(0, 0.88), fontsize=9.5, frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_test3_timeline.png"), dpi=200)
plt.close(fig)

# ---------- 3. Pi 수신 안정성 (시험 3, 460초) ----------
fn = d.frame_number.to_numpy()
missing = int(np.clip(np.diff(fn) - 1, 0, None).sum())
sec = np.floor(t - t.iloc[0]).astype(int)
fps = pd.Series(1, index=sec).groupby(level=0).sum()
fps = fps.iloc[1:-1]
fig, ax = plt.subplots(figsize=(6.2, 3.4))
ax.plot(fps.index, fps.values, color=NAVY, lw=1)
ax.axhline(18.2, color=GREEN, ls="--", lw=1)
ax.set_ylim(0, 22); ax.set_xlabel("시간 (초)"); ax.set_ylabel("초당 프레임")
ax.text(5, 4.5, f"{len(d):,}프레임 수신, 누락 {missing}, 깨짐 {int(d.bad_frame.sum())}", fontsize=12, color=GREEN, fontweight="bold")
ax.text(5, 1.5, "Raspberry Pi 5, USB 921600 bps, 2026.10.27 시험 3", fontsize=9.5, color=GRAY)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_pi_fps.png"), dpi=200)
plt.close(fig)
print("pi missing", missing, "frames", len(d))

# ---------- 4. 카메라 조명 시험 (2026-10-27) ----------
cam = os.path.join(ROOT, "B회신3_20261027", "2_camera")
c = pd.read_csv(os.path.join(cam, "cam_light.csv"))
cues = pd.read_csv(os.path.join(cam, "cam_light_cues.csv"))
ct0 = float(cues.loc[cues.event == "start_empty", "pi_time"].iloc[0])
tc = rel(c, ct0)
fig, ax = plt.subplots(figsize=(6.2, 3.4))
ax.fill_between(tc, 0, c.motion_active * 0.30, step="post", color=GREEN, alpha=0.35, label="움직임 판정")
ax.plot(tc, c.ratio.clip(upper=0.3), color=NAVY, lw=0.9, label="프레임 차분 비율")
for _, r in cues.iterrows():
    if r.event.startswith("light"):
        x = r.pi_time - ct0
        ax.axvline(x, color=AMBER, lw=1.4)
ax.text(112, 0.17, "조명 끔/켬 4회\n움직임 판정 0회", ha="center", color=RED, fontsize=10.5, fontweight="bold",
        bbox=dict(fc="white", ec="none", alpha=0.9))
ax.add_patch(Rectangle((92, -0.005), 40, 0.255, fill=False, ec=RED, lw=2))
ax.set_xlim(-2, 168); ax.set_ylim(-0.01, 0.31)
ax.set_xlabel("시간 (초)"); ax.set_ylabel("차분 비율")
ax.legend(loc="center left", bbox_to_anchor=(0.0, 0.55), fontsize=9, frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_cam_light.png"), dpi=200)
plt.close(fig)
print("saved figs to", OUT)
