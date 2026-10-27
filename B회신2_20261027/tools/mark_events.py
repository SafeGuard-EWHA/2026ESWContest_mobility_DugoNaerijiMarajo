"""시험 행동 시각 기록기. 행동을 실제로 한 순간 Enter를 누르면 Pi 시계로 기록한다.

레이더·카메라 리더와 같은 Pi에서 실행해야 CSV의 wall_time과 같은 시계가 된다.
계획은 화면에 안내만 하고, 기록되는 시각은 Enter를 누른 실제 시각이다.

  python3 mark_events.py radar  ~/b_reply_20261027/test3_events.csv
  python3 mark_events.py camera ~/b_reply_20261027/cam_events.csv
"""

import csv
import sys
import time

PLANS = {
    # 시험 3: 빈자리 3분 → 착석 정지 2분 → 퇴장 후 빈자리 1분 → 재착석 30초
    "radar": [
        ("start_empty", "빈자리 시작 (사람은 보드 대각선 뒤 멀리). 리더 시작 직후 Enter", 180),
        ("sit_down", "앉기 시작하는 순간 Enter", 0),
        ("seated_still", "앉아서 가만히 있기 시작한 순간 Enter", 120),
        ("stand_up", "일어나기 시작하는 순간 Enter", 0),
        ("left_area", "보드 대각선 뒤로 다 나간 순간 Enter", 60),
        ("sit_again", "다시 앉기 시작하는 순간 Enter", 0),
        ("seated_again", "다시 앉아 가만히 있기 시작한 순간 Enter", 30),
        ("end", "끝 (리더 종료 전) Enter", 0),
    ],
    # 카메라: 사람 움직임과 조명만 바뀔 때 구분
    "camera": [
        ("start_empty", "빈 화면 시작 (화면 안에 아무도 없음) Enter", 30),
        ("move_start", "사람이 화면 안에서 움직이기 시작 Enter", 15),
        ("still_start", "의자에 앉아 가만히 있기 시작 Enter", 20),
        ("leave", "일어나 화면 밖으로 나간 순간 Enter", 15),
        ("light_off_1", "천장 조명 끈 순간 Enter (화면 안 사람 없음)", 10),
        ("light_on_1", "천장 조명 켠 순간 Enter", 10),
        ("light_off_2", "다시 끈 순간 Enter", 10),
        ("light_on_2", "다시 켠 순간 Enter", 15),
        ("move_again", "사람이 다시 들어와 움직이기 시작 Enter", 15),
        ("end", "끝 Enter", 0),
    ],
}


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in PLANS:
        sys.exit("사용: python3 mark_events.py radar|camera 저장경로.csv")
    steps, path = PLANS[sys.argv[1]], sys.argv[2]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event", "wall_time", "monotonic_s", "local_time", "note"])
        for name, prompt, hold_s in steps:
            note = input(f"\n[{name}] {prompt}\n  (메모가 있으면 적고 Enter) > ").strip()
            now = time.time()
            w.writerow([name, f"{now:.3f}", f"{time.monotonic():.3f}",
                        time.strftime("%H:%M:%S", time.localtime(now)), note])
            f.flush()
            print(f"  기록 {time.strftime('%H:%M:%S', time.localtime(now))}"
                  + (f" → 다음까지 약 {hold_s}초" if hold_s else ""))
    print(f"\n저장: {path}")


if __name__ == "__main__":
    main()
