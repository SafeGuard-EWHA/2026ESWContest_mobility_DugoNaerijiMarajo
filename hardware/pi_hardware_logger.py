"""
SafeGuard TwinLab Agent - 실제 Raspberry Pi hardware log 수집 스크립트.

**중요**: 이 파일은 실제 Raspberry Pi 하드웨어(GPIO)에서만 실행 가능하며,
Streamlit Cloud/대시보드(app/streamlit_app.py, src/ 이하 모든 모듈)는
이 파일을 절대 import하지 않는다. gpiozero, RPi.GPIO, adafruit_dht,
board는 이 스크립트에서만 사용되는 하드웨어 전용 의존성이며,
requirements.txt(웹 배포용)가 아니라 hardware/requirements-pi.txt에
별도로 명시되어 있다.

이 스크립트는 SafeGuard의 실시간 제어 로직 자체를 포함하지 않는
**데이터 수집(logging) 전용** 유틸리티다. 제어 로직(state machine,
actuator policy)의 정확성 검증은 src/state_machine.py 시뮬레이션과
tests/ 이하 pytest로 이루어진다. 이 스크립트가 만드는 hardware_log.csv는
data_loader.HARDWARE_LOG_COLUMNS 스키마를 그대로 따르므로, 수집 후
대시보드에 업로드하거나 scripts/generate_paper_outputs.py의
--hardware-csv 옵션으로 바로 사용할 수 있다.

배선 가정(예시, 실제 배선에 맞게 GPIO 핀 번호를 조정할 것):
    - PIR 센서: GPIO17 (BCM)
    - DHT22 온습도 센서: GPIO4 (board.D4)
    - Relay(fan/led/buzzer/motor): GPIO27/22/23/24 (BCM), active_high 가정

사용법 (Raspberry Pi에서):
    python -m pip install -r hardware/requirements-pi.txt
    python hardware/pi_hardware_logger.py --duration 900 --out data/hardware_log.csv
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import HARDWARE_LOG_COLUMNS, TIME_STEP_S  # noqa: E402  (하드웨어 무관, 스키마만 재사용)

try:
    import board  # type: ignore
    import adafruit_dht  # type: ignore
    from gpiozero import MotionSensor, OutputDevice  # type: ignore
except ImportError as exc:  # pragma: no cover - Raspberry Pi 밖에서는 의도적으로 실패
    raise ImportError(
        "이 스크립트는 Raspberry Pi 전용 패키지(board, adafruit_dht, gpiozero)가 "
        "필요합니다. 'pip install -r hardware/requirements-pi.txt'로 설치한 뒤 "
        "실제 Raspberry Pi에서 실행하세요. Streamlit Cloud/대시보드에서는 이 "
        "스크립트를 import하지 않습니다."
    ) from exc


# --- GPIO 핀 배치 (실제 배선에 맞게 수정) ---------------------------------
PIR_PIN = 17
DHT22_PIN = board.D4
RELAY_FAN_PIN = 27
RELAY_LED_PIN = 22
RELAY_BUZZER_PIN = 23
RELAY_MOTOR_PIN = 24


def _read_cpu_temp_c() -> float:
    """/sys/class/thermal에서 Raspberry Pi CPU 온도(C)를 읽는다."""
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return float(raw) / 1000.0
    except OSError:
        return float("nan")


def _read_cpu_percent(prev_stat: tuple[int, int] | None) -> tuple[float, tuple[int, int]]:
    """/proc/stat 두 샘플 간 차이로 CPU 사용률(%)을 근사 계산한다."""
    fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values = list(map(int, fields))
    idle, total = values[3], sum(values)
    if prev_stat is None:
        return 0.0, (idle, total)
    prev_idle, prev_total = prev_stat
    d_idle = idle - prev_idle
    d_total = total - prev_total
    percent = 0.0 if d_total <= 0 else (1.0 - d_idle / d_total) * 100.0
    return percent, (idle, total)


def collect_hardware_log(duration_s: float, out_path: Path) -> None:
    """duration_s 동안 TIME_STEP_S 간격으로 센서를 샘플링해 hardware_log.csv에 기록한다."""
    pir = MotionSensor(PIR_PIN)
    dht = adafruit_dht.DHT22(DHT22_PIN)
    relay_fan = OutputDevice(RELAY_FAN_PIN)
    relay_led = OutputDevice(RELAY_LED_PIN)
    relay_buzzer = OutputDevice(RELAY_BUZZER_PIN)
    relay_motor = OutputDevice(RELAY_MOTOR_PIN)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prev_stat: tuple[int, int] | None = None

    with out_path.open("w", encoding="utf-8") as f:
        f.write(",".join(HARDWARE_LOG_COLUMNS) + "\n")

        n_steps = int(duration_s // TIME_STEP_S) + 1
        for step in range(n_steps):
            t = step * TIME_STEP_S

            try:
                temp_c = dht.temperature
                humidity = dht.humidity
            except RuntimeError:
                # DHT22는 간헐적 read failure가 흔하다. data_loader.py가
                # NaN/sentinel을 보간 처리하므로 그대로 -999를 기록한다.
                temp_c, humidity = -999.0, -999.0

            cpu_percent, prev_stat = _read_cpu_percent(prev_stat)

            row = [
                f"{t:.1f}",
                "",  # state: 실시간 제어 로직 미포함이므로 공란(파이프라인이 재계산)
                str(int(pir.motion_detected)),
                f"{temp_c if temp_c is not None else -999.0:.2f}",
                f"{humidity if humidity is not None else -999.0:.2f}",
                str(int(relay_fan.value)),
                str(int(relay_led.value)),
                str(int(relay_buzzer.value)),
                str(int(relay_motor.value)),
                f"{_read_cpu_temp_c():.2f}",
                f"{cpu_percent:.2f}",
            ]
            f.write(",".join(row) + "\n")
            f.flush()
            time.sleep(TIME_STEP_S)

    print(f"hardware log saved: {out_path} ({n_steps} rows)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SafeGuard Raspberry Pi hardware logger")
    parser.add_argument("--duration", type=float, default=900.0, help="수집 시간(초)")
    parser.add_argument(
        "--out", type=str, default="data/hardware_log.csv", help="출력 CSV 경로"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    collect_hardware_log(args.duration, Path(args.out))
