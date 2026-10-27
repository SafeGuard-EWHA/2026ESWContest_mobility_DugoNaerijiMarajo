"""시험 3 raw.bin에서 (1) 퇴장 후 고정 추적 주변에 점이 있었는지, (2) 앉아 있는 사람 추적 주변 점이
끊긴 최장 시간을 다시 계산한다. B 저장소 hardware/mmwave/mmwave_reader.py의 파서를 그대로 쓴다.

  python analyze_test3_tracks.py <B저장소>/hardware/mmwave <시험3 폴더>

좌표 변환은 cfg sensorPosition(1.2 m, 15도)을 그대로 쓴다 (트래커도 이 값으로 변환).
"""

import csv
import math
import sys

sys.path.insert(0, sys.argv[1])
import mmwave_reader as m  # noqa: E402

D = sys.argv[2].rstrip("/") + "/"
T0 = 1793096881.728  # 빈자리 시작 안내 (Pi 시각, clock_offset.txt 기준)
H, TILT = 1.2, math.radians(15)
GHOSTS = {"id0": (-0.01, 0.81), "id4": (-0.37, 1.11)}  # 퇴장 후 고정된 두 추적 (x, y)

frames = m.FrameReader().feed(open(D + "test3_raw.bin", "rb").read())
rows = list(csv.DictReader(open(D + "test3_radar.csv", encoding="utf-8")))
assert len(frames) == len(rows)
T = [float(r["wall_time"]) - T0 for r in rows]


def world(x, y, z):
    return x, y * math.cos(TILT) - z * math.sin(TILT), -y * math.sin(TILT) + z * math.cos(TILT) + H


def near(f, gx, gy, r=0.5):
    """(gx, gy) 0.5 m 안의 점이 있는지, 그중 움직이는 점(|doppler| >= 0.01)이 있는지."""
    any_hit = dyn_hit = False
    for x, y, z, v in f["points"]:
        xw, yw, _ = world(x, y, z)
        if math.hypot(xw - gx, yw - gy) < r:
            any_hit = True
            dyn_hit |= abs(v) >= 0.01
    return any_hit, dyn_hit


print("(1) 고정 추적 주변 점이 있었던 프레임 수")
for a, b, name in [(0, 170, "빈자리1"), (315, 375, "퇴장 후 빈자리2")]:
    for k, (gx, gy) in GHOSTS.items():
        sel = [f for f, t in zip(frames, T) if a <= t < b]
        hits = [near(f, gx, gy) for f in sel]
        print(f"  {name} {k}: 프레임 {len(sel)}, 점 있음 {sum(h[0] for h in hits)}, 움직이는 점 있음 {sum(h[1] for h in hits)}")

print("(2) 앉아 있는 사람 추적(가장 작은 id) 주변 점이 끊긴 최장 시간")
for a, b, name in [(180, 300, "정지 2분"), (385, 416, "재착석 정지 30초")]:
    run_any = run_dyn = best_any = best_dyn = n = 0
    for f, t in zip(frames, T):
        if not (a <= t < b) or not f["tracks"]:
            continue
        _, gx, gy, _ = min(f["tracks"], key=lambda p: p[0])
        a_hit, d_hit = near(f, gx, gy)
        n += 1
        run_any = 0 if a_hit else run_any + 1
        run_dyn = 0 if d_hit else run_dyn + 1
        best_any, best_dyn = max(best_any, run_any), max(best_dyn, run_dyn)
    print(f"  {name}: 프레임 {n}, 점 없는 최장 {best_any}프레임({best_any * 0.055:.2f}s), "
          f"움직이는 점 없는 최장 {best_dyn}프레임({best_dyn * 0.055:.2f}s)")
