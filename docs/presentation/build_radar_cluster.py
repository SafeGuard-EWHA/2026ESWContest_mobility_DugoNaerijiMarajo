# -*- coding: utf-8 -*-
"""레이더 원본 바이트로 3D 점 구름 → 영역 필터 → DBSCAN 군집 → 추적 과정을 그린다 (그림 + 회전 3D 영상).

탑승자 판정은 TI 3D People Tracking 펌웨어 안의 트래커(gtrack) 결과를 쓴다.
여기 DBSCAN은 Python에서 점을 사람 덩어리로 묶어 보여 주는 시각화이자, 트래커 결과를 다시 확인하는 후보 방법이다.

  python build_radar_cluster.py [--video]
출력: img/final/fig_cluster_pipeline.png, SafeGuard_radar_cluster3d_test3.mp4 (--video)
"""
import csv
import math
import os
import sys

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter
from sklearn.cluster import DBSCAN

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
import mmwave_reader as m  # noqa: E402

D = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
T0 = 1793096881.728
H, TILT = 1.2, math.radians(15)
BOX = (-0.8, 0.8, 0.3, 2.4, 0.0, 1.3)    # cfg boundaryBox (x, y, z)
EPS, MIN_PTS = 0.25, 8                   # DBSCAN (0.5초 누적 점 기준)
ACC = 0.5                                # 점 누적 시간 (초)
PHASES = [(0, 178.7, "빈자리"), (178.7, 301.3, "앉아서 가만히"), (301.3, 388.4, "일어나 나간 뒤"), (388.4, 1e9, "다시 앉음")]
CCOL = ["#D62728", "#1F77B4", "#FF7F0E", "#2CA02C", "#9467BD"]
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 9,
                     "animation.ffmpeg_path": imageio_ffmpeg.get_ffmpeg_exe()})


def world(x, y, z):
    return x, y * math.cos(TILT) - z * math.sin(TILT), -y * math.sin(TILT) + z * math.cos(TILT) + H


frames = m.FrameReader().feed(open(os.path.join(D, "test3_raw.bin"), "rb").read())
rows = list(csv.DictReader(open(os.path.join(D, "test3_radar.csv"), encoding="utf-8")))
assert len(frames) == len(rows)
T = np.array([float(r["wall_time"]) for r in rows]) - T0
RAW = [np.array([(x, y, z) for x, y, z, _v in f["points"]]).reshape(-1, 3) for f in frames]
WLD = [np.array([world(*p) for p in r]).reshape(-1, 3) for r in RAW]


def window(i):
    lo = i
    while lo > 0 and T[lo - 1] >= T[i] - ACC:
        lo -= 1
    return range(lo, i + 1)


def stage(i):
    """프레임 i 기준 0.5초 누적: 원본(센서 좌표), 영역 안 점(월드 좌표), DBSCAN 라벨, 추적."""
    w = window(i)
    raw = np.vstack([RAW[j] for j in w]) if w else np.empty((0, 3))
    wp = np.vstack([WLD[j] for j in w]) if w else np.empty((0, 3))
    inside = ((wp[:, 0] >= BOX[0]) & (wp[:, 0] <= BOX[1]) & (wp[:, 1] >= BOX[2]) & (wp[:, 1] <= BOX[3])
              & (wp[:, 2] >= BOX[4]) & (wp[:, 2] <= BOX[5]))
    pts = wp[inside]
    labels = DBSCAN(eps=EPS, min_samples=MIN_PTS).fit_predict(pts) if len(pts) >= MIN_PTS else -np.ones(len(pts), int)
    return raw, wp, pts, labels, frames[i]["tracks"] or []


def box3d(ax, p, col, lw=1.6):
    (x0, y0, z0), (x1, y1, z1) = p.min(0), p.max(0)
    for xs, ys, zs in [([x0, x1], [y0, y0], [z0, z0]), ([x0, x1], [y1, y1], [z0, z0]), ([x0, x1], [y0, y0], [z1, z1]), ([x0, x1], [y1, y1], [z1, z1]),
                       ([x0, x0], [y0, y1], [z0, z0]), ([x1, x1], [y0, y1], [z0, z0]), ([x0, x0], [y0, y1], [z1, z1]), ([x1, x1], [y0, y1], [z1, z1]),
                       ([x0, x0], [y0, y0], [z0, z1]), ([x1, x1], [y0, y0], [z0, z1]), ([x0, x0], [y1, y1], [z0, z1]), ([x1, x1], [y1, y1], [z0, z1])]:
        ax.plot(xs, ys, zs, color=col, lw=lw)


def style(ax, title, sensor=False):
    ax.set_title(title, fontsize=11, fontweight="bold", pad=0)
    if sensor:
        ax.set_xlim(-1.5, 1.5); ax.set_ylim(0, 3); ax.set_zlim(-1.2, 1.2)
    else:
        ax.set_xlim(-1.2, 1.2); ax.set_ylim(0, 2.6); ax.set_zlim(0, 1.6)
    ax.set_xlabel("X (m)", labelpad=-6); ax.set_ylabel("Y (m)", labelpad=-6); ax.set_zlabel("Z (m)", labelpad=-6)
    ax.tick_params(labelsize=7, pad=-2)
    ax.view_init(elev=18, azim=-60)


def draw_clusters(ax, pts, labels, tracks, show_tracks=True):
    noise = labels < 0
    ax.scatter(pts[noise, 0], pts[noise, 1], pts[noise, 2], s=10, c="#9E9E9E", marker="x", depthshade=False)
    ncl = 0
    for k in sorted(set(labels) - {-1}):
        p = pts[labels == k]
        col = CCOL[ncl % len(CCOL)]
        ax.scatter(p[:, 0], p[:, 1], p[:, 2], s=12, c=col, depthshade=False)
        box3d(ax, p, col)
        ncl += 1
    if show_tracks:
        for tid, x, y, z in tracks:
            ax.plot([x, x], [y, y], [0, max(z, 0.05) + 0.9], color="#111", lw=2.2)
            ax.scatter([x], [y], [0], s=60, c="#111", marker="o")
            ax.text(x + 0.08, y, 1.05, f"ID {tid}", fontsize=10, fontweight="bold", color="#111")
    return ncl


def pipeline_figure():
    rows_t = [(250.0, "앉아서 가만히 (t = 250 s)"), (345.0, "일어나 나간 뒤 (t = 345 s)")]
    fig = plt.figure(figsize=(16, 8.4), facecolor="white")
    heads = ["① 원본 점 구름 (센서 좌표)", "② 좌표 변환 + 감지 영역 필터", "③ DBSCAN 군집", "④ TI 트래커 추적과 비교"]
    for r, (tc, lab) in enumerate(rows_t):
        i = int(np.argmin(np.abs(T - tc)))
        raw, wp, pts, labels, tracks = stage(i)
        for c in range(4):
            ax = fig.add_subplot(2, 4, r * 4 + c + 1, projection="3d")
            if c == 0:
                ax.scatter(raw[:, 0], raw[:, 1], raw[:, 2], s=8, c="#7B1FA2", depthshade=False)
                style(ax, heads[c], sensor=True)
            elif c == 1:
                ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=8, c="#7B1FA2", depthshade=False)
                style(ax, heads[c])
            elif c == 2:
                n = draw_clusters(ax, pts, labels, tracks, show_tracks=False)
                style(ax, f"{heads[c]}: 군집 {n}개")
            else:
                n = draw_clusters(ax, pts, labels, tracks, show_tracks=True)
                style(ax, f"{heads[c]}: 추적 {len(tracks)}개, 군집 {n}개")
        fig.text(0.005, 0.74 - r * 0.47, lab, rotation=90, fontsize=12, fontweight="bold", va="center",
                 color="#2E7D32" if r == 0 else "#C62828")
    fig.text(0.5, 0.012, "시험 3 원본 바이트, 0.5초 누적. 회색 x = DBSCAN 잡음, 색 상자 = 군집, 검은 막대 = TI 트래커 추적 위치. "
             "아래 줄: 사람이 나간 뒤 군집은 0개인데 트래커 추적은 2개 남음 → 군집으로 추적을 다시 확인하면 유령 추적을 걸러낼 수 있음",
             ha="center", fontsize=10.5)
    fig.subplots_adjust(left=0.02, right=0.99, top=0.95, bottom=0.05, wspace=0.02, hspace=0.12)
    out = os.path.join(HERE, "img", "final", "fig_cluster_pipeline.png")
    fig.savefig(out, dpi=140)
    print("saved", out)


def video(out, start=150.0, end=425.0, step=4):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="white")
    ax = fig.add_axes([0.0, 0.02, 0.66, 0.92], projection="3d")
    info = fig.text(0.67, 0.86, "", fontsize=13, fontweight="bold", va="top")
    fig.text(0.67, 0.95, "SafeGuard 레이더 3D 군집 (DBSCAN)", fontsize=16, fontweight="bold")
    fig.text(0.67, 0.30, "점 = 0.5초 누적 점 구름 (감지 영역 안)\n색 상자 = DBSCAN 군집\n회색 x = 잡음\n검은 막대 = TI 트래커 추적 위치\n\n"
             "2026.10.27 시험 3 원본 바이트 재생, 약 4배속\n탑승자 판정은 TI 트래커 결과를 쓰고,\nDBSCAN은 시각화와 재확인용",
             fontsize=10.5, color="#444", va="top")
    idx = [i for i in range(len(T)) if start <= T[i] <= end][::step]
    writer = FFMpegWriter(fps=20, bitrate=3500)
    with writer.saving(fig, out, dpi=100):
        for n, i in enumerate(idx):
            ax.cla()
            _raw, _wp, pts, labels, tracks = stage(i)
            ncl = draw_clusters(ax, pts, labels, tracks)
            style(ax, "")
            ax.view_init(elev=20, azim=-75 + 40 * math.sin(n / len(idx) * 2 * math.pi))
            ph = next(lab for a, b, lab in PHASES if a <= T[i] < b)
            info.set_text(f"t = {T[i]:5.1f} s\n{ph}\n\n군집 {ncl}개\nTI 추적 {len(tracks)}개\n점 {len(pts)}개")
            info.set_color("#C62828" if ph == "일어나 나간 뒤" else "#1B5E20")
            writer.grab_frame()
            if n % 300 == 0:
                print(n, "/", len(idx), flush=True)
    print("saved", out)


if __name__ == "__main__":
    pipeline_figure()
    if "--video" in sys.argv:
        video(os.path.join(HERE, "SafeGuard_radar_cluster3d_test3.mp4"))
