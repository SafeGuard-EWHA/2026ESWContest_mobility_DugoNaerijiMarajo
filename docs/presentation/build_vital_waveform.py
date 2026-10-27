# -*- coding: utf-8 -*-
"""TI Vital Signs GUI 형식 그림/영상: 호흡 파형, 심박 파형, 호흡수와 심박수 (레이더 원본 바이트에서).

입력은 mmwave_reader.py --raw 로 저장한 Vital Signs With People Tracking 펌웨어의 원본 바이트와 .idx.csv.
TLV 1040 형식은 TI Applications_Visualizer common/parseTLVs.py parseVitalSignsTLV와 같다:
  '2H33f' = id, rangeBin, breathDeviation, heartRate, breathRate, 심박 파형[5:20], 호흡 파형[20:35]
TI vital_signs.py는 묶음(15개, NUM_FRAMES_PER_VITALS_PACKET)을 순서대로 이어 붙여 그리므로 여기서도 이어 붙이고,
샘플 간격은 '프레임 1개'로 본다. 이 가정은 실행할 때 호흡 파형 스펙트럼 최대 주파수와 펌웨어 호흡수를 비교해 출력한다.
표시 규칙도 TI와 같다: breathDeviation 0 = 사람 없음, 0.02 미만 = 숨 참음.

  python build_vital_waveform.py <raw.bin> [--count 30-90:13,120-180:12] [--video]
  (--count: 직접 센 호흡수 구간, 초:회/분)
출력: 입력 파일 이름 기준 img/final/fig_vital_wave_<이름>.png, SafeGuard_vital_wave_<이름>.mp4
"""
import argparse
import csv
import os
import struct
import sys

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "hardware", "mmwave"))
import mmwave_reader as m  # noqa: E402

VITALS_SIZE = struct.calcsize(m.VITALS_FMT)
WIN = 150  # TI GUI와 같은 표시 길이 (샘플)
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10,
                     "animation.ffmpeg_path": imageio_ffmpeg.get_ffmpeg_exe()})


def packets(buf):
    """매직워드로 패킷을 나눠 (바이트 위치, 패킷) 목록을 낸다. 길이가 맞지 않는 헤더는 건너뛴다."""
    out, pos = [], 0
    while True:
        s = buf.find(m.MAGIC, pos)
        if s < 0 or s + m.HEADER_LEN > len(buf):
            return out
        total = struct.unpack_from("<I", buf, s + len(m.MAGIC) + 4)[0]
        if total < m.HEADER_LEN or total > m.MAX_PACKET_LEN or s + total > len(buf):
            pos = s + len(m.MAGIC)
            continue
        out.append((s, buf[s:s + total]))
        pos = s + total


def vitals_of(pkt):
    """패킷 안의 TLV 1040을 찾아 (프레임 번호, 값 dict) 또는 (프레임 번호, None)."""
    hdr = struct.unpack_from(m.HEADER_FMT, pkt, len(m.MAGIC))
    frame_no, num_tlvs = hdr[3], hdr[6]
    off = m.HEADER_LEN
    for _ in range(num_tlvs):
        if off + 8 > len(pkt):
            break
        t, ln = struct.unpack_from(m.TLV_HEADER_FMT, pkt, off)
        off += 8
        if t == m.TLV_VITALS and ln >= VITALS_SIZE and off + VITALS_SIZE <= len(pkt):
            v = struct.unpack_from(m.VITALS_FMT, pkt, off)
            return frame_no, dict(id=v[0], range_bin=v[1], breath_dev=v[2], heart_rate=v[3], breath_rate=v[4],
                                  heart=np.array(v[5:20]), breath=np.array(v[20:35]))
        off += ln
    return frame_no, None


def load(raw_path):
    buf = open(raw_path, "rb").read()
    idx_path = str(raw_path) + ".idx.csv"
    offs, walls = [], []
    if os.path.exists(idx_path):
        for r in csv.DictReader(open(idx_path, encoding="utf-8")):
            offs.append(int(r["byte_offset"])); walls.append(float(r["wall_time"]))
    offs, walls = np.array(offs), np.array(walls)
    P = packets(buf)
    frames, vit = [], []
    for s, pkt in P:
        fno, v = vitals_of(pkt)
        t = walls[max(0, np.searchsorted(offs, s, side="right") - 1)] if len(offs) else float(fno)
        frames.append((fno, t))
        if v is not None:
            v["t"] = t
            vit.append(v)
    if not vit:
        raise SystemExit("TLV 1040(Vital Signs)이 없습니다. Vital Signs 펌웨어로 받은 원본인지 확인하세요.")
    ft = np.array([t for _f, t in frames])
    t0 = ft[0]
    fps = (len(ft) - 1) / (ft[-1] - ft[0]) if ft[-1] > ft[0] else 11.1
    # 묶음 15개를 이어 붙이고, 각 샘플 시각은 묶음이 도착한 시각에서 프레임 간격만큼 거꾸로 센다
    bw, hw, wt, st = [], [], [], []
    for v in vit:
        n = len(v["breath"])
        ts = v["t"] - t0 - (n - 1 - np.arange(n)) / fps
        flat = v["breath_dev"] == 0
        bw += list(np.zeros(n) if flat else v["breath"]); hw += list(np.zeros(n) if flat else v["heart"])
        wt += list(ts)
        st += ["none" if flat else ("hold" if v["breath_dev"] < 0.02 else "ok")] * n
    return dict(t0=t0, fps=fps, vit=vit, bw=np.array(bw), hw=np.array(hw), wt=np.array(wt), st=np.array(st),
                n_frames=len(frames))


def self_check(D):
    """샘플 간격 가정 확인: 호흡 파형 스펙트럼 최대 주파수 vs 펌웨어 호흡수."""
    ok = D["st"] == "ok"
    if ok.sum() < 200:
        print("자체 확인: 정상 호흡 구간이 짧아 건너뜀")
        return
    x = D["bw"][ok] - D["bw"][ok].mean()
    f = np.fft.rfftfreq(len(x), 1 / D["fps"]); a = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    sel = (f >= 0.08) & (f <= 0.8)
    wave_bpm = f[sel][np.argmax(a[sel])] * 60
    fw = np.median([v["breath_rate"] for v in D["vit"] if v["breath_dev"] >= 0.02 and v["breath_rate"] > 0])
    msg = "일치 (샘플 간격 = 프레임 1개 가정 맞음)" if abs(wave_bpm - fw) <= 0.25 * fw else "불일치 → 파형 시간축 가정을 다시 확인할 것"
    print(f"자체 확인: 파형 스펙트럼 {wave_bpm:.1f}회/분, 펌웨어 호흡수 중앙값 {fw:.1f}회/분 → {msg}")


def summary(D, counts):
    rows = []
    for a, b, truth in counts:
        seg = [v["breath_rate"] for v in D["vit"] if a <= v["t"] - D["t0"] < b and v["breath_dev"] >= 0.02]
        med = float(np.median(seg)) if seg else float("nan")
        rows.append((a, b, truth, med))
        print(f"{a}~{b}초: 직접 셈 {truth}, 레이더 1분 중앙값 {med:.1f}, 차이 {med - truth:+.1f}")
    return rows


def figure(D, counts, out):
    vt = np.array([v["t"] - D["t0"] for v in D["vit"]])
    br = np.array([v["breath_rate"] for v in D["vit"]]); hr = np.array([v["heart_rate"] for v in D["vit"]])
    dev = np.array([v["breath_dev"] for v in D["vit"]])
    fig = plt.figure(figsize=(13, 8.2), facecolor="white")
    gs = fig.add_gridspec(4, 1, height_ratios=[1.1, 1.1, 0.9, 1.1], hspace=0.55)
    ax = [fig.add_subplot(gs[i]) for i in range(4)]
    for k, (key, col, name) in enumerate([("bw", "#3949AB", "호흡 파형 (Breathing Waveform)"), ("hw", "#C62828", "심박 파형 (Heart Waveform)")]):
        a = ax[k]
        a.plot(D["wt"], D[key], color=col, lw=0.8)
        for lab, c in [("hold", "#FFCDD2"), ("none", "#ECEFF1")]:
            s = D["st"] == lab
            if s.any():
                a.fill_between(D["wt"], a.get_ylim()[0], a.get_ylim()[1], where=s, color=c, alpha=0.8, step="mid", lw=0)
        a.set_title(name, loc="left", fontweight="bold"); a.set_xlim(0, D["wt"].max()); a.grid(color="#EEE")
    ax[0].text(0.995, 1.02, "분홍 = 숨 참음 판정, 회색 = 사람 없음", transform=ax[0].transAxes, ha="right", fontsize=9, color="#777")
    a = ax[2]
    a.plot(vt, dev, color="#555", lw=1); a.axhline(0.02, color="#C62828", ls="--", lw=1)
    a.text(vt.max(), 0.022, "숨 참음 기준 0.02", ha="right", fontsize=8.5, color="#C62828")
    a.set_title("호흡 흔들림 (breathDeviation)", loc="left", fontweight="bold"); a.set_xlim(0, D["wt"].max()); a.grid(color="#EEE")
    a = ax[3]
    okm = dev >= 0.02
    a.scatter(vt[okm], br[okm], s=14, c="#3949AB", label="호흡수 (회/분)")
    a.scatter(vt, hr, s=10, c="#E57373", label="심박수 (회/분, 정답 없음)")
    for a0, b0, truth, med in counts:
        a.hlines(truth, a0, b0, colors="#111", lw=3, label="직접 센 호흡수" if a0 == counts[0][0] else None)
        a.text((a0 + b0) / 2, truth + 6, f"정답 {truth} / 레이더 {med:.1f}", ha="center", fontsize=9.5, fontweight="bold", color="#3949AB")
    a.set_title("펌웨어가 낸 호흡수와 심박수", loc="left", fontweight="bold"); a.set_xlabel("시간 (초)")
    a.set_xlim(0, D["wt"].max()); a.set_ylim(0, max(110, np.nanmax(hr) + 10)); a.grid(color="#EEE")
    a.legend(loc="upper right", fontsize=8.5, ncol=3, frameon=False)
    fig.suptitle(f"SafeGuard 레이더 Vital Signs 파형  |  {len(D['vit'])}개 묶음, {D['n_frames']}프레임, {D['fps']:.1f} fps", x=0.01, ha="left",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=160)
    print("saved", out)


def video(D, out, speed=1.0):
    vt = np.array([v["t"] - D["t0"] for v in D["vit"]])
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#F4F4F4")
    fig.text(0.02, 0.95, "SafeGuard 레이더 Vital Signs (원본 바이트 재생)", fontsize=16, fontweight="bold")
    boxes = {}
    for k, (name, x) in enumerate([("호흡수", 0.06), ("심박수 (정답 없음)", 0.53)]):
        fig.text(x + 0.2, 0.86, name, ha="center", fontsize=13)
        boxes[k] = fig.text(x + 0.2, 0.77, "", ha="center", fontsize=30, fontweight="bold",
                            bbox=dict(boxstyle="round", fc="white", ec="#999"))
    ab = fig.add_axes([0.06, 0.12, 0.42, 0.5]); ah = fig.add_axes([0.53, 0.12, 0.42, 0.5])
    lb, = ab.plot([], [], color="#3949AB", lw=1.6); lh, = ah.plot([], [], color="#C62828", lw=1.2)
    for a, t in [(ab, "Breathing Waveform"), (ah, "Heart Waveform")]:
        a.set_title(t, fontweight="bold"); a.set_xlim(0, WIN); a.grid(color="#DDD"); a.set_xlabel("샘플 (최근 150개)")
    yb = np.percentile(np.abs(D["bw"]), 99) * 1.2 or 1; yh = np.percentile(np.abs(D["hw"]), 99) * 1.2 or 1
    ab.set_ylim(-yb, yb); ah.set_ylim(-yh, yh)
    status = fig.text(0.5, 0.03, "", ha="center", fontsize=13, fontweight="bold")
    fps_out = 15
    tmax = D["wt"].max()
    writer = FFMpegWriter(fps=fps_out, bitrate=2500)
    with writer.saving(fig, out, dpi=100):
        for t in np.arange(WIN / D["fps"], tmax, speed / fps_out):
            k = np.searchsorted(D["wt"], t)
            lo = max(0, k - WIN)
            lb.set_data(np.arange(k - lo), D["bw"][lo:k]); lh.set_data(np.arange(k - lo), D["hw"][lo:k])
            j = max(0, np.searchsorted(vt, t) - 1)
            v = D["vit"][j]
            if v["breath_dev"] == 0:
                txt, hold = ("N/A", "N/A"), "사람 없음"
            elif v["breath_dev"] < 0.02:
                txt, hold = ("0", f"{v['heart_rate']:.0f}"), "숨 참음"
            else:
                txt, hold = (f"{v['breath_rate']:.1f}", f"{v['heart_rate']:.0f}"), "정상 호흡"
            boxes[0].set_text(txt[0]); boxes[1].set_text(txt[1])
            boxes[0].get_bbox_patch().set_facecolor("#EF5350" if hold == "숨 참음" else "white")
            status.set_text(f"t = {t:5.1f} s   상태: {hold}")
            writer.grab_frame(facecolor=fig.get_facecolor())
    print("saved", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--count", default="", help="직접 센 호흡수, 예: 30-90:13,120-180:12")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--name", help="출력 이름 (기본: 원본 파일 이름)")
    args = ap.parse_args()
    counts = []
    for part in filter(None, args.count.split(",")):
        rng, truth = part.split(":"); a, b = rng.split("-")
        counts.append((float(a), float(b), float(truth)))
    name = args.name or os.path.splitext(os.path.basename(args.raw))[0]
    D = load(args.raw)
    print(f"프레임 {D['n_frames']}개, Vital Signs 묶음 {len(D['vit'])}개, {D['fps']:.2f} fps")
    self_check(D)
    rows = summary(D, counts)
    figure(D, rows, os.path.join(HERE, "img", "final", f"fig_vital_wave_{name}.png"))
    if args.video:
        video(D, os.path.join(HERE, f"SafeGuard_vital_wave_{name}.mp4"))
