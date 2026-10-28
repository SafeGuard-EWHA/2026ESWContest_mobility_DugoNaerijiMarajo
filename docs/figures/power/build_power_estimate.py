# -*- coding: utf-8 -*-
"""결선 장비의 상태별 소비전력 추정 (데이터시트 대표값 x 실제 상태기계 설정). 실측 아님.

상태 순서와 머무는 시간은 prototype/SafeGuard_Main/configs/real.json 값을 쓴다
(이탈 확인 10 s, 융합 창 2 s, 보호 판단 60 s 앞). 레이더는 지금 구현에서 계속 전원이 들어가 있으므로
SafeGuard에서도 끄지 않는다 (절감은 Pi 연산, 카메라, 구동부에서만 생긴다).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})

# 부품별 대표 전력 (W). 근거: 각 데이터시트, 보드 설명서의 대표 전류 x 공급 전압
PART = {
    "Raspberry Pi 5 (대기)": 2.7,      # 5 V 0.54 A, 유휴
    "Raspberry Pi 5 (연산 추가)": 1.3,  # 레이더 TLV 해석, 프레임 차분 시 늘어나는 몫
    "레이더 IWR6843ISK-ODS": 1.5,      # 5 V 약 0.3 A (보드 포함)
    "카메라 Module 3": 0.8,             # 촬영 중
    "UWB DWM1001-DEV": 0.35,           # 차량측, J-Link 포함
    "ESP32 + PIR + SHT31": 0.5,        # 5 V 약 0.1 A
    "12V 팬": 1.8,                      # 12 V 0.15 A
    "12V 부저": 0.36,                   # 12 V 0.03 A
}
STATES = ["STANDBY", "DEPARTURE\nCHECK", "PRIMARY", "MMWAVE", "THERMAL", "PROTECTION"]
ON = {  # 상태별로 켜지는 부품 (SafeGuard)
    "STANDBY": ["Raspberry Pi 5 (대기)", "레이더 IWR6843ISK-ODS", "UWB DWM1001-DEV", "ESP32 + PIR + SHT31"],
    "DEPARTURE\nCHECK": ["Raspberry Pi 5 (대기)", "레이더 IWR6843ISK-ODS", "UWB DWM1001-DEV", "ESP32 + PIR + SHT31"],
    "PRIMARY": ["Raspberry Pi 5 (대기)", "Raspberry Pi 5 (연산 추가)", "레이더 IWR6843ISK-ODS", "UWB DWM1001-DEV",
                "ESP32 + PIR + SHT31", "카메라 Module 3"],
    "MMWAVE": ["Raspberry Pi 5 (대기)", "Raspberry Pi 5 (연산 추가)", "레이더 IWR6843ISK-ODS", "UWB DWM1001-DEV",
               "ESP32 + PIR + SHT31", "카메라 Module 3"],
    "THERMAL": ["Raspberry Pi 5 (대기)", "Raspberry Pi 5 (연산 추가)", "레이더 IWR6843ISK-ODS", "UWB DWM1001-DEV",
                "ESP32 + PIR + SHT31"],
    "PROTECTION": ["Raspberry Pi 5 (대기)", "Raspberry Pi 5 (연산 추가)", "레이더 IWR6843ISK-ODS", "UWB DWM1001-DEV",
                   "ESP32 + PIR + SHT31", "12V 팬", "12V 부저"],
}
ALL_ON = list(PART)
COL = {"Raspberry Pi 5 (대기)": "#0d366b", "Raspberry Pi 5 (연산 추가)": "#2a78d6", "레이더 IWR6843ISK-ODS": "#eb6834",
       "카메라 Module 3": "#1baf7a", "UWB DWM1001-DEV": "#eda100", "ESP32 + PIR + SHT31": "#8a8f98",
       "12V 팬": "#c03b2b", "12V 부저": "#e8a0a0"}

# 10분 시나리오: 보호자 이탈 → 아이 남음 → 온도 상승 → 보호 (초)
SCEN = [("STANDBY", 120), ("DEPARTURE\nCHECK", 10), ("PRIMARY", 2), ("MMWAVE", 5), ("THERMAL", 223), ("PROTECTION", 240)]


def p_state(st):
    return sum(PART[k] for k in ON[st])


def main():
    allon = sum(PART.values())
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.4), gridspec_kw={"width_ratios": [1.5, 1.5, 1]})
    # (a) 상태별 전력 구성
    a = ax[0]; left = np.zeros(len(STATES) + 1)
    rows = STATES + ["All-on\n(비교)"]
    for k in PART:
        v = np.array([PART[k] if k in ON[s] else 0 for s in STATES] + [PART[k]])
        a.barh(rows, v, left=left, color=COL[k], edgecolor="white", lw=1.5, label=k, height=0.62)
        left += v
    for i, t in enumerate(left):
        a.text(t + 0.1, i, f"{t:.1f} W", va="center", fontsize=9.5)
    a.invert_yaxis(); a.set_xlim(0, 11); a.set_xlabel("추정 전력 (W)")
    a.set_title("(a) 상태별 켜지는 부품과 전력", loc="left", fontweight="bold")
    a.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    # (b) 10분 시나리오 전력 시간 축
    a = ax[1]; t = 0; xs, ys = [], []
    for st, d in SCEN:
        xs += [t, t + d]; ys += [p_state(st)] * 2; t += d
    a.fill_between(np.array(xs) / 60, ys, color="#2a78d6", alpha=0.25, lw=0)
    a.plot(np.array(xs) / 60, ys, color="#2a78d6", lw=2, label="SafeGuard (단계적 활성화)")
    a.axhline(allon, color="#eb6834", lw=2, ls="--", label=f"All-on (모두 상시 ON, {allon:.1f} W)")
    t = 0
    for st, d in SCEN:
        if d >= 100:
            a.text((t + d / 2) / 60, 0.4, st.replace("\n", " "), ha="center", fontsize=8.5, color="#444")
        t += d
    a.set_ylim(0, 12.5); a.set_xlabel("시간 (분)"); a.set_ylabel("추정 전력 (W)")
    a.set_title("(b) 10분 시나리오 (이탈 → 잔류 → 온도 상승 → 보호)", loc="left", fontweight="bold")
    a.legend(fontsize=8.5, frameon=False, loc="upper left")
    # (c) 에너지
    e_sg = sum(p_state(st) * d for st, d in SCEN) / 3600
    e_all = allon * sum(d for _, d in SCEN) / 3600
    e_park = p_state("STANDBY") * 3600 / 3600
    a = ax[2]
    b = a.bar(["All-on", "SafeGuard"], [e_all, e_sg], color=["#eb6834", "#2a78d6"], width=0.55)
    for r, v in zip(b, [e_all, e_sg]):
        a.text(r.get_x() + r.get_width() / 2, v + 0.02, f"{v:.2f} Wh", ha="center", fontsize=10, fontweight="bold")
    a.set_ylabel("10분 에너지 (Wh)"); a.set_ylim(0, e_all * 1.25)
    a.set_title(f"(c) 에너지: {(1 - e_sg / e_all) * 100:.0f}% 절감", loc="left", fontweight="bold")
    fig.suptitle("결선 장비 소비전력 추정 (데이터시트 대표값 x 상태기계 설정, 실측 아님)", x=0.01, ha="left",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = os.path.join(HERE, "fig_power_estimate.png")
    fig.savefig(out, dpi=170)
    print(f"all-on {allon:.2f} W, standby {p_state('STANDBY'):.2f} W, protection {p_state('PROTECTION'):.2f} W")
    print(f"10 min: all-on {e_all:.3f} Wh, safeguard {e_sg:.3f} Wh, saving {(1 - e_sg / e_all) * 100:.1f}%")
    print(f"주차 대기 1시간 (STANDBY): {e_park:.2f} Wh vs all-on {allon:.2f} Wh")


if __name__ == "__main__":
    main()
