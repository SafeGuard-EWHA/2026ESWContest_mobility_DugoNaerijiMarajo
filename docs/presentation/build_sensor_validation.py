# -*- coding: utf-8 -*-
"""센서 검증용 대표 그래프 (데이터 로거, 시리얼 플로터 형식). 모두 저장소 안의 실측 CSV에서 그린다.

  1. fig_val_logger.png  7월 1차 시제품 Pi 로그 180초: 온도, 습도, PIR, 릴레이, CPU (hardware_log.csv)
  2. fig_val_fusion.png  10/27 시험 3: 카메라 움직임과 레이더 추적, 재실, 가장 가까운 점 거리를 같은 시간축에
  3. fig_val_rates.png   레이더 수신 품질: 초당 프레임과 프레임 간격 분포 (시험 3, Pi 60초 수신)
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "img", "final")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})
C = {"temp": "#D32F2F", "hum": "#1976D2", "pir": "#7B1FA2", "fan": "#2E7D32", "led": "#F9A825",
     "buz": "#6D4C41", "mot": "#00838F", "cpu": "#455A64", "cam": "#00897B", "trk": "#283593", "pres": "#EF6C00"}


def logger():
    d = pd.read_csv(os.path.join(ROOT, "hardware_log.csv"))
    t = d.time_s
    fig, ax = plt.subplots(4, 1, figsize=(12, 8.2), sharex=True, gridspec_kw={"height_ratios": [1.3, 0.9, 1.0, 0.9]})
    a = ax[0]
    a.plot(t, d.temp_c, color=C["temp"], marker="o", ms=2.5, lw=1.2, label="온도 (°C)")
    a.set_ylabel("온도 (°C)", color=C["temp"])
    b = a.twinx()
    b.plot(t, d.humidity, color=C["hum"], marker="s", ms=2.2, lw=1.2, label="습도 (%)")
    b.set_ylabel("습도 (%)", color=C["hum"]); b.spines["right"].set_visible(True)
    a.set_title("DHT22 온습도 (1초 간격)", loc="left", fontweight="bold")
    a.legend(handles=a.get_lines() + b.get_lines(), loc="upper right", fontsize=9, frameon=False, ncol=2)
    a = ax[1]
    a.step(t, d.pir_val, where="post", color=C["pir"], lw=1.6)
    a.fill_between(t, 0, d.pir_val, step="post", color=C["pir"], alpha=0.15)
    a.set_yticks([0, 1]); a.set_yticklabels(["0", "1 감지"]); a.set_ylim(-0.15, 1.3)
    a.set_title("PIR 디지털 출력", loc="left", fontweight="bold")
    a = ax[2]
    for k, (col, name, key) in enumerate([("relay_fan", "팬", "fan"), ("relay_led", "LED", "led"),
                                          ("relay_buzzer", "부저", "buz"), ("relay_motor", "모터", "mot")]):
        a.step(t, d[col] * 0.8 + k, where="post", color=C[key], lw=2)
    a.set_yticks([0.4, 1.4, 2.4, 3.4]); a.set_yticklabels(["팬", "LED", "부저", "모터"]); a.set_ylim(-0.2, 4)
    a.set_title("릴레이 구동 출력 (높으면 ON)", loc="left", fontweight="bold")
    a = ax[3]
    a.plot(t, d.cpu_temp_c, color=C["cpu"], lw=1.2, label="CPU 온도 (°C)")
    b = a.twinx(); b.bar(t, d.cpu_percent, width=0.9, color="#90A4AE", alpha=0.6, label="CPU 사용률 (%)")
    b.set_ylabel("CPU (%)"); b.spines["right"].set_visible(True)
    a.set_ylabel("CPU 온도 (°C)"); a.set_title("Raspberry Pi 상태", loc="left", fontweight="bold")
    a.set_xlabel("시간 (초)")
    fig.suptitle("7월 1차 시제품 (Pi 4B, DHT22, PIR, 릴레이) 실측 로그 180초", x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_val_logger.png"), dpi=170)
    print("logger: temp", d.temp_c.min(), "~", d.temp_c.max(), "PIR on", int(d.pir_val.sum()), "s")


def fusion():
    D = os.path.join(ROOT, "B회신3_20261027", "1_radar_test3")
    T0 = 1793096881.728
    r = pd.read_csv(os.path.join(D, "test3_radar.csv")); c = pd.read_csv(os.path.join(D, "test3_cam.csv"))
    tr, tc = r.wall_time - T0, c.wall_time - T0
    phases = [(0, 178.7, "빈자리", "#ECEFF1"), (178.7, 301.3, "앉아서 가만히", "#E8F5E9"),
              (301.3, 388.4, "일어나 나간 뒤", "#FFEBEE"), (388.4, 430, "다시 앉음", "#E8F5E9")]
    fig, ax = plt.subplots(4, 1, figsize=(12, 8.4), sharex=True, gridspec_kw={"height_ratios": [1, 0.6, 1, 1]})
    for a in ax:
        for s, e, lab, col in phases:
            a.axvspan(s, e, color=col, lw=0)
        a.grid(color="#EEE")
    for s, e, lab, _col in phases:
        ax[0].text((s + e) / 2, 1.02, lab, transform=ax[0].get_xaxis_transform(), ha="center", fontsize=9.5, fontweight="bold")
    a = ax[0]
    a.plot(tc, c.ratio.clip(upper=0.3), color=C["cam"], lw=0.8)
    a.set_ylabel("차분 비율"); a.set_title("Pi 카메라 프레임 차분 비율", loc="left", fontweight="bold", pad=18)
    a = ax[1]
    a.fill_between(tc, 0, c.motion_active, step="post", color=C["cam"], alpha=0.6)
    a.set_yticks([0, 1]); a.set_yticklabels(["", "움직임"]); a.set_ylim(0, 1.2)
    a.set_title("카메라 움직임 판정 (3프레임 연속 규칙)", loc="left", fontweight="bold")
    a = ax[2]
    a.step(tr, r.num_tracks, where="post", color=C["trk"], lw=1, label="레이더 추적 수")
    a.fill_between(tr, 0, r.presence * 0.5, step="post", color=C["pres"], alpha=0.45, label="재실 신호 (presence)")
    a.set_ylabel("개수"); a.set_ylim(0, 3.6); a.legend(loc="upper left", fontsize=9, frameon=False, ncol=2)
    a.set_title("레이더 추적 수와 재실 신호", loc="left", fontweight="bold")
    a = ax[3]
    a.scatter(tr, r.nearest_range_m, s=1.5, c="#5C6BC0", alpha=0.5)
    a.set_ylabel("거리 (m)"); a.set_ylim(0, 4.6); a.set_xlabel("시간 (초, 빈자리 시작 = 0)")
    a.set_title("레이더 가장 가까운 점까지 거리 (프레임마다)", loc="left", fontweight="bold")
    a.set_xlim(-35, 430)
    fig.suptitle("센서 비교 (2026.10.27 시험 3): 카메라는 움직일 때만, 레이더는 가만히 앉아도 잡는다", x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_val_fusion.png"), dpi=170)
    still = (tc >= 190) & (tc < 300)
    print("fusion: camera motion during still", int(c.motion_active[still].sum()), "of", int(still.sum()),
          "| radar presence during still", round(r.presence[(tr >= 190) & (tr < 300)].mean() * 100, 1), "%")


def rates():
    runs = [("시험 3 (460초)", os.path.join(ROOT, "B회신3_20261027", "1_radar_test3", "test3_radar.csv"), "#283593"),
            ("Pi 60초 수신", os.path.join(ROOT, "B회신2_20261027", "2_pi_receive", "rx60.csv"), "#EF6C00")]
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.8))
    for name, path, col in runs:
        r = pd.read_csv(path)
        dt = np.diff(r.wall_time.to_numpy()) * 1000
        gap = int(np.clip(np.diff(r.frame_number.to_numpy()) - 1, 0, None).sum())
        sec = np.floor(r.wall_time - r.wall_time.iloc[0]).astype(int)
        fps = pd.Series(1, index=sec).groupby(level=0).sum().iloc[1:-1]
        ax[0].plot(fps.index, fps.values, color=col, lw=1, label=f"{name}: 누락 {gap}, 깨짐 {int(r.bad_frame.sum())}")
        ax[1].hist(dt, bins=np.arange(0, 140, 2), color=col, alpha=0.55, label=f"{name}: 중앙값 {np.median(dt):.0f} ms")
    ax[0].set_ylim(0, 22); ax[0].set_xlabel("시간 (초)"); ax[0].set_ylabel("초당 프레임")
    ax[0].set_title("초당 수신 프레임", loc="left", fontweight="bold"); ax[0].legend(fontsize=9, frameon=False, loc="lower right")
    ax[1].set_xlabel("프레임 간격 (ms)"); ax[1].set_ylabel("프레임 수"); ax[1].set_yscale("log")
    ax[1].set_title("프레임 간격 분포", loc="left", fontweight="bold"); ax[1].legend(fontsize=9, frameon=False)
    for a in ax:
        a.grid(color="#EEE")
    fig.suptitle("레이더 데이터 수신 품질 (Raspberry Pi 5, USB 921600 bps)", x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_val_rates.png"), dpi=170)
    print("rates saved")


if __name__ == "__main__":
    logger(); fusion(); rates()
