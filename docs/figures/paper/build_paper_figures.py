# -*- coding: utf-8 -*-
"""SafeGuard 논문용 그림 6장 (모두 저장소 안 실측 원본에서 계산, 6번만 설계 규칙 지도).

  Fig1 UWB ranging characterization        prototype/measurements/raw/uwb_20261016
  Fig2 mmWave occupancy evaluation         B회신_20261027/csv, B회신3_20261027/1_radar_test3
  Fig3 Camera motion-feature separability  B회신3_20261027 (test3 카메라, 조명 시험)
  Fig4 Multimodal complementarity          시험 3 레이더 + 카메라 동시 기록 (같은 Pi 시계)
  Fig5 Sensor timing                       각 원본의 수신 시각
  Fig6 Thermal decision map                src/config.py 규칙 (측정 아님)

색: 기본 검증 팔레트(dataviz palette.md) 범주색 1~4번을 고정 순서로, 크기는 파랑 한 색 단계.
한 그림 안에서 y축은 하나만 쓴다.

  python docs/figures/paper/build_paper_figures.py
출력: 같은 폴더의 fig*.png (300 dpi), fig*.pdf (벡터)
"""
import csv
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap, BoundaryNorm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
sys.path.insert(0, ROOT)
import mmwave_reader as m  # noqa: E402
from src import config as cfg  # noqa: E402

S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"      # 범주색 고정 순서
BLUE = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]    # 파랑 단계 (연 → 진)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
plt.rcParams.update({
    "font.family": ["Arial", "DejaVu Sans"], "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "legend.frameon": False, "legend.fontsize": 8, "lines.linewidth": 1.4, "savefig.bbox": "tight", "axes.axisbelow": True,
})
T3 = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
T0 = 1793096881.728  # 시험 3 빈자리 시작 (Pi 시각)
PH = [("Empty", 0, 170), ("Seated, still", 180, 300), ("After exit", 315, 375), ("Re-seated", 390, 415)]
H, TILT = 1.2, math.radians(15)


def panel(ax, k):
    ax.text(-0.13, 1.06, f"({k})", transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom")


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(HERE, f"{name}.{ext}"), dpi=300)
    plt.close(fig)
    print("saved", name)


# ---------------------------------------------------------------- Fig 1 UWB
def fig_uwb():
    U = os.path.join(ROOT, "prototype", "measurements", "raw", "uwb_20261016")
    s = {}
    for k in ("session_01", "session_02"):
        d = pd.read_csv(os.path.join(U, k, "telemetry.csv"))
        d = d[d.valid == True].copy()  # noqa: E712
        d["t"] = d.monotonic_s - d.monotonic_s.iloc[0]
        s[k] = d
    d1, d2 = s["session_01"], s["session_02"]
    fig, ax = plt.subplots(2, 2, figsize=(7.2, 5.4))
    a = ax[0, 0]
    a.plot(d1.t, d1.raw_distance_m, color=BLUE[1], lw=0.8, label="Raw range")
    a.plot(d1.t, d1.filtered_distance_m, color=S1, lw=1.4, label="Moving average (N = 7)")
    a.axvspan(0, 40, color=S3, alpha=0.12, lw=0); a.text(20, 0.60, "quasi-static", ha="center", fontsize=7, color=INK2)
    a.set_xlabel("Time (s)"); a.set_ylabel("Range (m)"); a.set_title("Session 1 range trace (602 s, 1,106 samples)", loc="left")
    a.set_ylim(0.55, 1.95); a.legend(loc="upper left", ncol=2, fontsize=7.5); panel(a, "a")
    # 정지 구간 잔차 분포
    a = ax[0, 1]
    segs = [(d1[d1.t < 40].raw_distance_m.values, "Session 1, 0–40 s", S1), (d2.raw_distance_m.values, "Session 2, 57 s", S2)]
    bins = np.arange(-0.30, 0.31, 0.02)
    for x, lab, col in segs:
        r = x - np.median(x)
        a.hist(r, bins=bins, histtype="step", lw=1.6, color=col, density=True,
               label=f"{lab}: σ = {np.std(r, ddof=1) * 100:.1f} cm, n = {len(r)}")
    a.set_xlabel("Deviation from segment median (m)"); a.set_ylabel("Probability density")
    a.set_ylim(0, 23); a.set_title("Quasi-static ranging noise", loc="left"); a.legend(loc="upper left"); panel(a, "b")
    # 창 크기 상충: 잡음
    Ns = np.arange(1, 16)
    a = ax[1, 0]
    for x, lab, col in segs:
        sd = [pd.Series(x).rolling(n).mean().dropna().std() * 100 for n in Ns]
        a.plot(Ns, sd, marker="o", ms=4, color=col, label=lab)
    a.axvline(7, color=INK2, ls="--", lw=0.9); a.text(7.3, 5.0, "deployed N = 7", fontsize=7.5, color=INK2)
    a.set_xlabel("Moving-average window N (samples)"); a.set_ylabel("Residual σ (cm)")
    a.set_ylim(0.6, 7.2); a.set_title("Window length vs. noise", loc="left"); a.legend(loc="upper right"); panel(a, "c")
    # 계단 부분 확대: 원본과 이동평균 N = 3, 7, 15 (단일 계단이라 지연을 숫자로 내지 않고 모양으로 비교)
    a = ax[1, 1]
    st = d1[(d1.t > 515) & (d1.t < 575)]
    a.plot(st.t, st.raw_distance_m, color=BLUE[1], lw=0.8, marker="o", ms=2, label="Raw")
    for n, col in [(3, S3), (7, S1), (15, S2)]:
        a.plot(st.t, st.raw_distance_m.rolling(n).mean(), color=col, lw=1.6,
               label=f"N = {n} (group delay {(n - 1) / 2 * np.median(np.diff(d1.t)):.1f} s)")
    a.set_xlabel("Time (s)"); a.set_ylabel("Range (m)")
    a.set_title("Step response around 535 s", loc="left"); a.legend(loc="lower right", fontsize=7); panel(a, "d")
    fig.suptitle("Fig. 1  UWB (DWM1001) ranging characterization, 2026-10-16. No reference distance: precision only, not accuracy.",
                 x=0.0, ha="left", fontsize=9, color=INK2)
    fig.tight_layout()
    save(fig, "fig1_uwb_ranging")


# ---------------------------------------------------------------- Fig 2 mmWave
def load_test3():
    r = pd.read_csv(os.path.join(T3, "test3_radar.csv")); r["t"] = r.wall_time - T0
    c = pd.read_csv(os.path.join(T3, "test3_cam.csv")); c["t"] = c.wall_time - T0
    return r, c


def phase_mask(t, a, b):
    return (t >= a) & (t < b)


def fig_radar():
    r, _c = load_test3()
    occ = ((r.num_tracks > 0) | (r.presence == 1)).astype(int)
    fig, ax = plt.subplots(2, 2, figsize=(7.2, 5.6))
    a = ax[0, 0]
    rates = [occ[phase_mask(r.t, s, e)].mean() * 100 for _n, s, e in PH]
    ns = [int(phase_mask(r.t, s, e).sum()) for _n, s, e in PH]
    truth = [0, 1, 0, 1]
    cols = [S2 if g == 0 else S1 for g in truth]
    b = a.bar(range(4), rates, color=cols, width=0.62)
    for i, (v, n) in enumerate(zip(rates, ns)):
        a.text(i, v + 2, f"{v:.1f}%\n{n:,} fr", ha="center", fontsize=7, color=INK)
    a.set_xticks(range(4)); a.set_xticklabels([p[0] for p in PH], fontsize=8)
    a.set_ylim(0, 132); a.set_yticks(range(0, 101, 20)); a.set_ylabel("Frames flagged occupied (%)")
    a.set_title("Test 3: occupancy decision by phase", loc="left")
    a.bar([0], [0], color=S1, label="occupant present"); a.bar([0], [0], color=S2, label="seat empty")
    a.legend(loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0), fontsize=7.5); panel(a, "a")
    # 정지 착석 시험 A/B/C 추적 수 분포
    a = ax[0, 1]
    still = os.path.join(ROOT, "B회신_20261027", "csv")
    tests = [("A: TI cfg,\n3 people", "testA_origcfg_3people_still_orig.csv", (85, 240), 3),
             ("B: vehicle cfg,\n1 person", "testB_sedancfg_1person_still_car.csv", (85, 240), 1),
             ("C: TI cfg,\n1 person", "testC_origcfg_1person_still_orig1.csv", (85, 240), 1)]
    cats = ["0", "1", "2", "3", "≥4"]
    shares = []
    for _lab, fn, (s, e), _n in tests:
        d = pd.read_csv(os.path.join(still, fn)); t = d.wall_time - d.wall_time.iloc[0]
        k = d.num_tracks[(t >= s) & (t < e)].clip(upper=4)
        shares.append([(k == i).mean() * 100 for i in range(5)])
    shares = np.array(shares)
    left = np.zeros(3)
    for j in range(5):
        a.barh(range(3), shares[:, j], left=left, color=BLUE[j], height=0.6, edgecolor="#fcfcfb", lw=1, label=f"{cats[j]} track" + ("" if cats[j] == "1" else "s"))
        left += shares[:, j]
    for i, (_l, _f, _w, n) in enumerate(tests):
        a.text(101, i, f"true = {n}\ncorrect {shares[i, n]:.1f}%", va="center", fontsize=7.5)
    a.set_yticks(range(3)); a.set_yticklabels([x[0] for x in tests], fontsize=8); a.invert_yaxis()
    a.set_xlim(0, 100); a.set_xlabel("Share of still-period frames (%)"); a.grid(axis="y", visible=False)
    a.set_title("Track count while seated still (5 min)", loc="left")
    a.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=5, fontsize=7, handlelength=1); panel(a, "b")
    # 단계별 점 개수 분포
    a = ax[1, 0]
    data = [r.num_points[phase_mask(r.t, s, e)].values + 1 for _n, s, e in PH]
    bp = a.boxplot(data, widths=0.5, patch_artist=True, showfliers=False, medianprops=dict(color=INK, lw=1.2))
    for p, g in zip(bp["boxes"], truth):
        p.set_facecolor(S1 if g else S2); p.set_alpha(0.55); p.set_edgecolor(INK2)
    a.set_yscale("log"); a.set_xticks(range(1, 5)); a.set_xticklabels([p[0] for p in PH], fontsize=8)
    a.set_ylabel("Points per frame + 1 (log)"); a.set_title("Point-cloud density by phase", loc="left"); panel(a, "c")
    # 시간에 따른 점 개수 (축) + 재실 판정 (배경 음영)
    a = ax[1, 1]
    sec = np.floor(r.t).astype(int)
    g = pd.DataFrame({"sec": sec, "occ": occ, "pts": r.num_points}).groupby("sec").mean()
    on = (g.occ > 0.5).values
    a.fill_between(g.index, 0, 1, where=on, transform=a.get_xaxis_transform(), color=S1, alpha=0.15, lw=0, step="mid",
                   label="tracker says occupied")
    a.plot(g.index, g.pts + 0.1, color=INK, lw=0.8, label="mean points per frame (1 s)")
    pass  # 빈자리 구간은 제목으로 설명
    a.set_yscale("log"); a.set_ylim(0.08, 300); a.set_xlim(-30, 425)
    a.set_xlabel("Time from empty-seat start (s)"); a.set_ylabel("Points per frame + 0.1 (log)")
    a.set_title("Tracks persist after exit with no points", loc="left"); a.legend(loc="upper left", fontsize=7); panel(a, "d")
    fig.suptitle("Fig. 2  60 GHz radar (IWR6843ISK-ODS, TI 3D People Tracking) occupancy evaluation. Single-subject trials; frames are not independent.",
                 x=0.0, ha="left", fontsize=9, color=INK2)
    fig.tight_layout()
    save(fig, "fig2_radar_occupancy")


# ---------------------------------------------------------------- Fig 3 Camera
def fig_camera():
    r, c = load_test3()
    L = pd.read_csv(os.path.join(ROOT, "B회신3_20261027", "2_camera", "cam_light.csv"))
    cues = pd.read_csv(os.path.join(ROOT, "B회신3_20261027", "2_camera", "cam_light_cues.csv")).set_index("event").pi_time
    lt = L.wall_time
    light = np.zeros(len(L), bool)
    for ev in ("light_off_1", "light_on_1", "light_off_2", "light_on_2"):
        light |= (lt >= cues[ev] - 0.5).values & (lt <= cues[ev] + 3).values
    move = ((lt >= cues["move_start"]) & (lt < cues["still_start"])) | ((lt >= cues["move_again"]) & (lt < cues["end"]))
    groups = [
        ("Empty seat", c.ratio[phase_mask(c.t, 0, 170)].values),
        ("Seated still", c.ratio[phase_mask(c.t, 190, 300)].values),
        ("Person moving", L.ratio[move.values].values),
        ("Light switch", L.ratio[light].values),
    ]
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.6), gridspec_kw={"width_ratios": [1.5, 1]})
    a = ax[0]
    floor = 1e-4
    rng = np.random.default_rng(0)
    for i, (lab, x) in enumerate(groups):
        y = np.clip(x, floor, None)
        jit = rng.uniform(-0.18, 0.18, len(y))
        a.scatter(i + jit, y, s=3, color=[S1, S1, S3, S4][i], alpha=0.35, lw=0)
        a.hlines(np.median(y), i - 0.28, i + 0.28, color=INK, lw=1.4)
    a.axhline(0.01, color=INK2, ls="--", lw=0.9); a.text(-0.45, 0.012, "motion 1%", fontsize=7, color=INK2)
    a.axhline(0.6, color=INK2, ls=":", lw=0.9); a.text(-0.45, 0.68, "lighting 60%", fontsize=7, color=INK2)
    a.set_yscale("log"); a.set_ylim(floor * 0.8, 1.3)
    a.set_xticks(range(4)); a.set_xticklabels([g[0] for g in groups], fontsize=8)
    a.set_ylabel("Changed-pixel ratio (log)"); a.set_title("Frame-difference feature by condition", loc="left"); panel(a, "a")
    a = ax[1]
    labs = [g[0] for g in groups]
    above = [np.mean(g[1] > 0.01) * 100 for g in groups]
    act = [c.motion_active[phase_mask(c.t, 0, 170)].mean() * 100, c.motion_active[phase_mask(c.t, 190, 300)].mean() * 100,
           L.motion_active[move.values].mean() * 100, L.motion_active[light].mean() * 100]
    y = np.arange(4)
    a.barh(y - 0.18, above, height=0.34, color=BLUE[1], label="ratio > 1% (raw)")
    a.barh(y + 0.18, act, height=0.34, color=S1, label="motion decision (3-frame + light rule)")
    for i in range(4):
        a.text(max(above[i], act[i]) + 2, i, f"{act[i]:.1f}%", va="center", fontsize=7.5)
    a.set_yticks(y); a.set_yticklabels(labs, fontsize=8); a.invert_yaxis(); a.set_xlim(0, 110); a.grid(axis="y", visible=False)
    a.set_xlabel("Frames (%)"); a.set_title("Raw threshold vs. rule output", loc="left")
    a.legend(loc="lower center", bbox_to_anchor=(0.4, -0.62), fontsize=7); panel(a, "b")
    fig.suptitle("Fig. 3  Pi Camera Module 3 motion feature (10 fps, pixel Δ > 25). Camera detects motion, not a still occupant.",
                 x=0.0, ha="left", fontsize=9, color=INK2)
    fig.tight_layout()
    save(fig, "fig3_camera_feature")
    print("camera medians", [f"{np.median(g[1]):.4f}" for g in groups], "decision%", [round(v, 1) for v in act])


# ---------------------------------------------------------------- Fig 4 Multimodal
def point_support(gate=0.45, win=0.5, k=3):
    """사후 분석: 추적 주변 gate 안에 최근 win초 동안 점이 k개 이상 있으면 '근거 있는 추적'."""
    frames = m.FrameReader().feed(open(os.path.join(T3, "test3_raw.bin"), "rb").read())
    r, _ = load_test3()
    t = r.t.values
    W = []
    for f in frames:
        W.append(np.array([(x, y * math.cos(TILT) - z * math.sin(TILT)) for x, y, z, _v in f["points"]]).reshape(-1, 2))
    sup = np.zeros(len(frames), int)
    lo = 0
    for i, f in enumerate(frames):
        while t[lo] < t[i] - win:
            lo += 1
        tr = f["tracks"] or []
        if not tr:
            continue
        P = np.vstack(W[lo:i + 1])
        if len(P) == 0:
            continue
        C = np.array([(x, y) for _id, x, y, _z in tr])
        dmin = np.linalg.norm(P[:, None, :] - C[None, :, :], axis=2).min(1)
        sup[i] = int((dmin <= gate).sum() >= k)
    return sup


def fig_fusion():
    r, c = load_test3()
    radar = ((r.num_tracks > 0) | (r.presence == 1)).astype(int).values
    supp = point_support()
    sec_r = np.floor(r.t).astype(int); sec_c = np.floor(c.t).astype(int)
    R = pd.Series(radar).groupby(sec_r.values).max(); Ps = pd.Series(supp).groupby(sec_r.values).max()
    Cm = pd.Series(c.motion_active.values).groupby(sec_c.values).max()
    idx = R.index.intersection(Cm.index)
    R, Ps, Cm = R[idx], Ps[idx], Cm[idx]
    # 카메라 움직임은 2초 유지 후 꺼지므로 '최근 10초 안에 움직임'을 1차 감지 기억으로 본다 (FSM의 1차 감지 후 레이더 확인 구조)
    Cmem = Cm.rolling(10, min_periods=1).max()
    series = [("Camera (motion)", Cm, S3), ("Radar (tracker)", R, S1), ("Camera OR radar", np.maximum(Cm, R), S4),
              ("Radar + point support", Ps, S2)]
    fig, ax = plt.subplots(1, 1, figsize=(7.2, 3.2))
    x = np.arange(4); w = 0.2
    for j, (lab, ser, col) in enumerate(series):
        v = [ser[(ser.index >= s) & (ser.index < e)].mean() * 100 for _n, s, e in PH]
        ax.bar(x + (j - 1.5) * w, v, width=w * 0.92, color=col, label=lab)
        for i, vv in enumerate(v):
            ax.text(x[i] + (j - 1.5) * w, vv + 1.5, f"{vv:.0f}", ha="center", fontsize=6.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels([f"{n}\n(truth: {'occupied' if g else 'empty'})" for (n, _s, _e), g in zip(PH, [0, 1, 0, 1])], fontsize=8)
    ax.set_ylabel("Seconds flagged occupied (%)"); ax.set_ylim(0, 112); ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.13), fontsize=7.5)
    fig.text(0.0, -0.06, "Fig. 4  Per-second occupancy flag in test 3 (one subject, one trial). Higher is better for occupied phases, lower is better for empty phases.\n"
             "Point support (offline): a track counts only if ≥3 radar points fall within 0.45 m of it in the last 0.5 s — a post-hoc check, not deployed.",
             ha="left", fontsize=8, color=INK2)
    fig.tight_layout()
    save(fig, "fig4_multimodal")
    for lab, ser, _c in series:
        print(lab, [round(ser[(ser.index >= s) & (ser.index < e)].mean() * 100, 1) for _n, s, e in PH])


# ---------------------------------------------------------------- Fig 5 Timing
def fig_timing():
    U = os.path.join(ROOT, "prototype", "measurements", "raw", "uwb_20261016", "session_01", "telemetry.csv")
    u = pd.read_csv(U); u = u[u.valid == True]  # noqa: E712
    r, c = load_test3()
    rx = pd.read_csv(os.path.join(ROOT, "B회신2_20261027", "2_pi_receive", "rx60.csv"))
    srcs = [("Radar, test 3 (8,363 fr)", np.diff(r.wall_time.values) * 1e3, S1),
            ("Radar, 60 s run (1,091 fr)", np.diff(rx.wall_time.values) * 1e3, S2),
            ("Camera, test 3 (4,594 fr)", np.diff(c.wall_time.values) * 1e3, S3),
            ("UWB, session 1 (1,106)", np.diff(u.monotonic_s.values) * 1e3, S4)]
    fig, ax = plt.subplots(1, 1, figsize=(7.2, 3.0))
    for lab, dt, col in srcs:
        x = np.sort(dt); y = np.arange(1, len(x) + 1) / len(x)
        ax.step(x, y, where="post", color=col, lw=1.6,
                label=f"{lab}: median {np.median(dt):.0f} ms, p99 {np.percentile(dt, 99):.0f} ms")
    ax.axvline(2000, color=INK2, ls="--", lw=0.9); ax.text(1900, 0.06, "UWB stale timeout 2 s", ha="right", fontsize=7.5, color=INK2)
    ax.set_xscale("log"); ax.set_xlim(20, 4000); ax.set_ylim(0, 1.02)
    ax.set_xlabel("Inter-arrival time (ms, log)"); ax.set_ylabel("Cumulative fraction")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2, fontsize=7.2)
    fig.text(0.0, -0.2, "Fig. 5  Inter-arrival ECDF on the Raspberry Pi 5 host. Radar frame loss: 0 of 8,363 and 0 of 1,091 (frame-number gaps).",
             ha="left", fontsize=8, color=INK2)
    fig.tight_layout()
    save(fig, "fig5_sensor_timing")


# ---------------------------------------------------------------- Fig 6 Thermal rule map
def fig_thermal():
    T = np.linspace(25, 35, 601); rate = np.linspace(0.01, 3.0, 600)  # °C/min
    TT, RR = np.meshgrid(T, rate)
    ttt = (cfg.THERMAL_TARGET_TEMP_C - TT) / (RR / 60)  # s
    protect = (TT >= cfg.THERMAL_ACTION_TEMP_C) | (ttt <= cfg.THERMAL_TIME_TO_TARGET_THRESHOLD_S)
    fig, ax = plt.subplots(1, 1, figsize=(5.6, 3.6))
    levels = [0, 120, 300, 600, 1200, 3600]
    cmap = ListedColormap(BLUE[::-1]); norm = BoundaryNorm(levels, cmap.N)
    cs = ax.contourf(TT, RR, np.clip(ttt, 0, 3599), levels=levels, cmap=cmap, norm=norm)
    ax.contour(TT, RR, protect.astype(float), levels=[0.5], colors=INK, linewidths=1.6)
    cb = fig.colorbar(cs, ax=ax, pad=0.02); cb.set_label("Predicted time to 35 °C (s)")
    ax.axvline(cfg.THERMAL_ACTION_TEMP_C, color=INK, ls="--", lw=0.9)
    ax.text(33.5, 2.75, "PROTECT", ha="center", fontsize=9, fontweight="bold", color="white")
    ax.text(26.6, 0.22, "MONITOR", ha="center", fontsize=9, fontweight="bold", color=INK)
    hw = pd.read_csv(os.path.join(ROOT, "hardware_log.csv"))
    pt_T = hw.temp_c.iloc[-1]; pt_r = max((hw.temp_c.iloc[-1] - hw.temp_c.iloc[-31]) / 30 * 60, 0.02)
    ax.scatter([pt_T], [pt_r], s=40, color=S2, zorder=5, edgecolor="white", lw=1)
    ax.annotate(f"July bench log (last 30 s)\n{pt_T:.1f} °C, {pt_r:.2f} °C/min", (pt_T, pt_r), xytext=(25.4, 1.05), fontsize=7.5,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.set_xlabel("Current cabin temperature (°C)"); ax.set_ylabel("Recent rise rate (°C/min)")
    fig.text(0.0, -0.06, f"Fig. 6  Decision rule from src/config.py (design rule, not a measurement): PROTECT if T ≥ {cfg.THERMAL_ACTION_TEMP_C:.0f} °C\n"
             f"or (35 °C − T) / rate ≤ {cfg.THERMAL_TIME_TO_TARGET_THRESHOLD_S:.0f} s. Black line = boundary.", ha="left", fontsize=8, color=INK2)
    fig.tight_layout()
    save(fig, "fig6_thermal_rule_map")


# ---------------------------------------------------------------- Fig 7 Thermal model on literature data
def fig_thermal_lit():
    """McLaren 2005 Pediatrics Fig.3 그래프 읽은 값(친구 작업)과 그 적합 결과. 우리 측정 아님."""
    import json
    R = os.path.join(ROOT, "prototype", "maintenance", "SafeGuard_Thermal_20261028", "research")
    dg = json.load(open(os.path.join(R, "digitized_fig3.json"), encoding="utf-8"))
    rs = json.load(open(os.path.join(R, "results.json"), encoding="utf-8"))
    A, tau = rs["mclaren_fig3_common_fit"]["A_C"], rs["mclaren_fig3_common_fit"]["tau_min"]
    t = np.array(dg["minutes"]); tf = np.linspace(0, 60, 241)
    keys = sorted(dg["temperature_F"], key=lambda k: int(k.split("_")[1][:-1]))
    ramp = ["#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
    fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1.3, 1, 1]})
    a = ax[0]
    for k, col in zip(keys, ramp):
        y = (np.array(dg["temperature_F"][k]) - 32) / 1.8
        a.plot(t, y, "o", ms=2.8, color=col)
        a.plot(tf, y[0] + A * (1 - np.exp(-tf / tau)), color=col, lw=1)
    a.axhline(35, color=INK2, ls="--", lw=0.9); a.text(59, 35.6, "35 °C", ha="right", fontsize=7.5, color=INK2)
    a.text(31, 24.2, f"common fit: T0 + A(1−e^(−t/τ))\nA = {A:.1f} °C, τ = {tau:.1f} min", fontsize=7, color=INK)
    a.set_xlabel("Time after closing (min)"); a.set_ylabel("Cabin temperature (°C)")
    a.set_title("     7 curves, ambient 23–34 °C", loc="left"); panel(a, "a")
    a = ax[1]
    folds = rs["loco"]["folds"]
    obs = [f["observed35_graph_interpolated_min"] for f in folds]; pred = [f["predicted35_min"] for f in folds]
    amb = [round((int(f["case"].split("_")[1][:-1]) - 32) / 1.8) for f in folds]
    a.plot([0, 16], [0, 16], color=INK2, ls=":", lw=1)
    for o, p_, c_, col in zip(obs, pred, amb, ramp):
        a.scatter([o], [p_], s=34, color=col, edgecolor="white", lw=0.8, zorder=3)
    a.text(15.5, 1.0, f"mean |error| {np.mean(np.abs(np.array(pred) - np.array(obs))):.1f} min", ha="right", fontsize=7.5)
    a.set_xlim(0, 16); a.set_ylim(0, 16); a.set_aspect("equal")
    a.set_xlabel("Read-off time to 35 °C (min)"); a.set_ylabel("Predicted (min)")
    a.set_title("      Leave-one-curve-out", loc="left"); panel(a, "b")
    a = ax[2]
    rf = rs["rolling_forecast"]; names = [("persistence", "Persistence", S2), ("linear", "Linear trend", S3), ("adaptive_rc", "Adaptive RC", S1)]
    x = np.arange(2); w = 0.26
    for j, (k, lab, col) in enumerate(names):
        v = [rf[h][k]["rmse_C"] for h in ("5", "10")]
        a.bar(x + (j - 1) * w, v, width=w * 0.92, color=col, label=lab)
        for i, vv in enumerate(v):
            a.text(x[i] + (j - 1) * w, vv + 0.05, f"{vv:.2f}", ha="center", fontsize=6.5)
    a.set_xticks(x); a.set_xticklabels(["5 min", "10 min"]); a.set_xlabel("Forecast horizon"); a.set_ylabel("RMSE (°C)")
    a.set_ylim(0, 4.2); a.grid(axis="x", visible=False); a.legend(loc="upper left", fontsize=7, ncol=1)
    a.set_title("      Forecast error", loc="left"); panel(a, "c")
    fig.text(0.0, -0.13, "Fig. 7  Thermal predictor calibrated on curves read from McLaren et al., Pediatrics 2005, Fig. 3 (integer °F readings, not raw data, not SafeGuard measurements).\n"
             "This is calibration on one study, not field validation. 6 of 7 curves already exceed 35 °C when 10 min of history is available, so a history-only forecast\n"
             "cannot warn early in those cases.", ha="left", fontsize=7.5, color=INK2)
    fig.tight_layout()
    save(fig, "fig7_thermal_literature")


if __name__ == "__main__":
    fig_uwb(); fig_radar(); fig_camera(); fig_fusion(); fig_timing(); fig_thermal(); fig_thermal_lit()
