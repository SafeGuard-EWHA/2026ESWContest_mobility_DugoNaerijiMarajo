# -*- coding: utf-8 -*-
"""TI 'Very Fine Motion Detection' 데모 화면 형식의 레이더 대시보드 (그림 + 영상).

레이더 원본 바이트(--raw로 저장한 .bin)를 mmwave_reader.py 파서로 풀어서 다섯 칸을 그린다.
  왼쪽 위  X-Y 산점도 (위에서 본 점 구름)
  왼쪽 아래 Doppler-Range (거리별 속도)
  오른쪽   관심 영역(좌석) 안 점 개수 / 대역통과 필터 결과 / 단측 진폭 스펙트럼
TI 데모는 MATLAB으로 그렸지만 같은 계산을 numpy, scipy, matplotlib로 한다.

  python build_radar_dashboard.py test3 [--video]
  python build_radar_dashboard.py rx60 [--video]
출력: img/final/dash_<name>.png, dash_<name>.mp4 (--video)
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
from matplotlib.patches import Rectangle
from scipy.signal import butter, filtfilt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
import mmwave_reader as m  # noqa: E402

CAPTURES = {
    # 이름: (폴더, raw, csv, 기준 시각(None=첫 프레임), 스펙트럼 구간(초), 단계 구분, 설명)
    "test3": ("B회신3_20261027/1_radar_test3", "test3_raw.bin", "test3_radar.csv", 1793096881.728, (190, 300),
              [(0, 178.7, "빈자리"), (178.7, 301.3, "앉아서 가만히"), (301.3, 388.4, "일어나 나간 뒤"), (388.4, 1e9, "다시 앉음")],
              "2026.10.27 시험 3, 레이더 높이 1.05 m"),
    "rx60": ("B회신2_20261027/2_pi_receive", "rx60_raw.bin", "rx60.csv", None, (5, 58), [],
             "2026.10.27 Pi 60초 수신 시험"),
}
H, TILT = 1.2, math.radians(15)            # cfg sensorPosition (트래커와 같은 기준)
AOI = (-0.65, 0.65, 0.5, 2.3, 0.2, 1.2)     # 관심 영역 = staticBoundaryBox (x, y, z)
BAND = (0.1, 0.6)                           # 대역통과 (Hz) = 분당 6~36회
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 9,
                     "animation.ffmpeg_path": imageio_ffmpeg.get_ffmpeg_exe()})
BG, PANEL, BLUE = "#C8CCD2", "#0B1E6E", "#1F77B4"


def world(x, y, z):
    return x, y * math.cos(TILT) - z * math.sin(TILT), -y * math.sin(TILT) + z * math.cos(TILT) + H


def load(name):
    folder, raw, csvf, t0, win, phases, desc = CAPTURES[name]
    d = os.path.join(ROOT, folder)
    frames = m.FrameReader().feed(open(os.path.join(d, raw), "rb").read())
    rows = list(csv.DictReader(open(os.path.join(d, csvf), encoding="utf-8")))
    assert len(frames) == len(rows)
    wt = np.array([float(r["wall_time"]) for r in rows])
    t = wt - (t0 if t0 is not None else wt[0])
    pts, count = [], []
    for f in frames:
        p = []
        n = 0
        for x, y, z, v in f["points"]:
            xw, yw, zw = world(x, y, z)
            p.append((xw, yw, math.sqrt(x * x + y * y + z * z), v))
            n += AOI[0] <= xw <= AOI[1] and AOI[2] <= yw <= AOI[3] and AOI[4] <= zw <= AOI[5]
        pts.append(p)
        count.append(n)
    count = np.array(count, float)
    fs = 1.0 / np.median(np.diff(t))
    b, a = butter(2, [BAND[0] / (fs / 2), BAND[1] / (fs / 2)], btype="band")
    filt = filtfilt(b, a, count - count.mean())
    return dict(name=name, t=t, pts=pts, count=count, filt=filt, fs=fs, win=win, phases=phases, desc=desc,
                tracks=[f["tracks"] or [] for f in frames])


def spectrum(sig, fs):
    n = len(sig)
    amp = np.abs(np.fft.rfft(sig * np.hanning(n))) * 2 / n
    return np.fft.rfftfreq(n, 1 / fs), amp


def peak(freq, amp):
    sel = (freq >= BAND[0]) & (freq <= BAND[1])
    k = np.argmax(amp[sel])
    return freq[sel][k]


def setup(D):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=BG)
    fig.text(0.012, 0.965, f"SafeGuard 60 GHz 레이더 대시보드  |  {D['desc']}", fontsize=13, fontweight="bold", color="#111")
    fig.text(0.012, 0.935, "IWR6843ISK-ODS + TI 3D People Tracking, 원본 바이트 재생 (Python: numpy, scipy, matplotlib)", fontsize=9, color="#333")
    axy = fig.add_axes([0.05, 0.52, 0.36, 0.355], facecolor=PANEL)
    adr = fig.add_axes([0.05, 0.07, 0.36, 0.37], facecolor=PANEL)
    ac = fig.add_axes([0.5, 0.71, 0.47, 0.19], facecolor="white")
    af = fig.add_axes([0.5, 0.41, 0.47, 0.19], facecolor="white")
    asp = fig.add_axes([0.5, 0.07, 0.47, 0.22], facecolor="white")
    for ax in (axy, adr):
        ax.grid(color="#3550B0", lw=0.5)
        ax.tick_params(labelsize=8)
    axy.set_xlim(-1.6, 1.6); axy.set_ylim(-0.2, 3.2); axy.set_aspect("equal")
    axy.set_xlabel("좌우 거리 (m)"); axy.set_ylabel("앞쪽 거리 (m)")
    axy.add_patch(Rectangle((AOI[0], AOI[2]), AOI[1] - AOI[0], AOI[3] - AOI[2], fill=False, ec="#FFD54F", lw=1.2, ls="--"))
    axy.scatter([0], [0], marker="^", s=90, c="#FF5252")
    adr.set_xlim(0, 3.5); adr.set_ylim(-1.2, 1.2)
    adr.set_xlabel("거리 (m)"); adr.set_ylabel("Doppler 속도 (m/s)")
    adr.axhline(0, color="#7F8FD0", lw=0.8)
    for ax in (ac, af, asp):
        ax.grid(color="#DDD", lw=0.6)
        ax.tick_params(labelsize=8)
    return fig, axy, adr, ac, af, asp


def static_figure(D):
    t, fs = D["t"], D["fs"]
    s, e = D["win"]
    sel = (t >= s) & (t <= e)
    fig, axy, adr, ac, af, asp = setup(D)
    tc = (s + e) / 2
    near = [i for i in range(len(t)) if tc - 0.5 <= t[i] < tc + 0.5]
    xs = [p[0] for i in near for p in D["pts"][i]]; ys = [p[1] for i in near for p in D["pts"][i]]
    axy.scatter(xs, ys, s=8, c="#E0E0E0", lw=0)
    for tid, x, y, z in D["tracks"][near[-1]]:
        axy.scatter([x], [y], s=260, facecolors="none", edgecolors="#FFD54F", linewidths=2)
    axy.set_title(f"X-Y 산점도 (t = {tc:.0f} s, 1초 누적, 점 {len(xs)}개)", fontsize=10, fontweight="bold")
    rs = [p[2] for i in near for p in D["pts"][i]]; vs = [p[3] for i in near for p in D["pts"][i]]
    adr.scatter(rs, vs, s=10, c="#E0E0E0", lw=0)
    adr.set_title("Doppler-Range", fontsize=10, fontweight="bold")
    ac.plot(t, D["count"], color=BLUE, lw=0.7)
    ac.axvspan(s, e, color="#FFD54F", alpha=0.25)
    ac.set_title("관심 영역(좌석) 안 점 개수", fontsize=10, fontweight="bold"); ac.set_xlabel("시간 (s)"); ac.set_ylabel("개수")
    af.plot(t, D["filt"], color=BLUE, lw=0.7)
    af.axvspan(s, e, color="#FFD54F", alpha=0.25)
    af.set_title(f"대역통과 필터 결과 ({BAND[0]}~{BAND[1]} Hz)", fontsize=10, fontweight="bold"); af.set_xlabel("시간 (s)")
    for a, b, lab in D["phases"]:
        ac.text(max(a, t[0]) + 2, ac.get_ylim()[1] * 0.85, lab, fontsize=8, color="#555")
    freq, amp = spectrum(D["filt"][sel], fs)
    pk = peak(freq, amp)
    asp.plot(freq, amp, color=BLUE, lw=1)
    asp.set_xlim(0, 1.5)
    asp.axvline(pk, color="#D32F2F", lw=1.2, ls="--")
    asp.text(pk + 0.03, amp.max() * 0.85, f"가장 큰 성분 {pk:.2f} Hz (분당 {pk * 60:.1f}회), 호흡 정답 없음", color="#D32F2F", fontsize=9.5, fontweight="bold")
    asp.set_title(f"단측 진폭 스펙트럼 (노란 구간 {s}~{e} s)", fontsize=10, fontweight="bold"); asp.set_xlabel("주파수 (Hz)")
    out = os.path.join(HERE, "img", "final", f"dash_{D['name']}.png")
    fig.savefig(out, dpi=150, facecolor=BG)
    print("saved", out, f"peak {pk:.3f} Hz ({pk * 60:.1f}/min)")


def video(D, step, out):
    t, fs = D["t"], D["fs"]
    fig, axy, adr, ac, af, asp = setup(D)
    sxy = axy.scatter([], [], s=8, c="#E0E0E0", lw=0)
    sdr = adr.scatter([], [], s=10, c="#E0E0E0", lw=0)
    ac.plot(t, D["count"], color=BLUE, lw=0.6); af.plot(t, D["filt"], color=BLUE, lw=0.6)
    ac.set_title("관심 영역(좌석) 안 점 개수", fontsize=10, fontweight="bold")
    af.set_title(f"대역통과 필터 결과 ({BAND[0]}~{BAND[1]} Hz)", fontsize=10, fontweight="bold"); af.set_xlabel("시간 (s)")
    c1 = ac.axvline(t[0], color="#D32F2F", lw=1.5); c2 = af.axvline(t[0], color="#D32F2F", lw=1.5)
    (lsp,) = asp.plot([], [], color=BLUE, lw=1)
    asp.set_xlim(0, 1.5); asp.set_xlabel("주파수 (Hz)")
    asp.set_title("단측 진폭 스펙트럼 (최근 30초)", fontsize=10, fontweight="bold")
    pk_line = asp.axvline(0, color="#D32F2F", lw=1, ls="--"); pk_txt = asp.text(0, 0, "", color="#D32F2F", fontsize=9.5, fontweight="bold")
    ttl = axy.set_title("", fontsize=10, fontweight="bold"); adr.set_title("Doppler-Range", fontsize=10, fontweight="bold")
    ph_txt = fig.text(0.6, 0.965, "", fontsize=13, fontweight="bold", color="#B71C1C")
    trk = []
    amax = 1e-9
    writer = FFMpegWriter(fps=20, bitrate=3500)
    with writer.saving(fig, out, dpi=100):
        for n, i in enumerate(range(0, len(t), step)):
            lo = i
            while lo > 0 and t[lo - 1] >= t[i] - 0.5:
                lo -= 1
            P = [p for j in range(lo, i + 1) for p in D["pts"][j]]
            sxy.set_offsets([(p[0], p[1]) for p in P] or [(9, 9)])
            sdr.set_offsets([(p[2], p[3]) for p in P] or [(9, 9)])
            for a in trk:
                a.remove()
            trk = [axy.scatter([x], [y], s=260, facecolors="none", edgecolors="#FFD54F", linewidths=2) for _tid, x, y, _z in D["tracks"][i]]
            ttl.set_text(f"X-Y 산점도  t = {t[i]:.1f} s, 추적 {len(D['tracks'][i])}개")
            c1.set_xdata([t[i], t[i]]); c2.set_xdata([t[i], t[i]])
            ph = next((lab for a, b, lab in D["phases"] if a <= t[i] < b), "")
            ph_txt.set_text(ph)
            w = (t >= t[i] - 30) & (t <= t[i])
            if w.sum() > fs * 10:
                freq, amp = spectrum(D["filt"][w], fs)
                amax = max(amax, amp[freq <= 1.5].max())
                lsp.set_data(freq, amp); asp.set_ylim(0, amax * 1.1)
                pk = peak(freq, amp)
                pk_line.set_xdata([pk, pk]); pk_txt.set_position((pk + 0.03, amax * 0.9)); pk_txt.set_text(f"가장 큰 성분 {pk * 60:.1f}회/분")
            writer.grab_frame(facecolor=BG)
            if n % 300 == 0:
                print(n, flush=True)
    print("saved", out)


if __name__ == "__main__":
    name = sys.argv[1]
    D = load(name)
    static_figure(D)
    if "--video" in sys.argv:
        step = 4 if name == "test3" else 1
        video(D, step, os.path.join(HERE, f"SafeGuard_radar_dashboard_{name}.mp4"))
