"""
SafeGuard TwinLab Agent - central configuration module.

이 모듈은 시뮬레이션 전반에서 사용되는 상수, 임계값, 경로, 시나리오 기본값을
한 곳에서 관리한다. 다른 모든 src/ 모듈은 이 파일의 값을 참조해야 하며,
값을 하드코딩하지 않는다.

주의(한계 명시):
- 여기 정의된 전력 값(POWER_W)은 datasheet/typical-value 기반의
  "추정 전력 모델(estimated power model)"이며, 실측(measured power)이 아니다.
  실측이 필요하면 power_measure_log.csv를 사용한다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

# ---------------------------------------------------------------------------
# 재현성 (Reproducibility)
# ---------------------------------------------------------------------------
RANDOM_SEED: int = 42


def set_global_seed(seed: int = RANDOM_SEED) -> None:
    """모든 난수 생성기의 시드를 고정하여 실행 결과를 재현 가능하게 만든다."""
    random.seed(seed)
    np.random.seed(seed)


# ---------------------------------------------------------------------------
# 경로 (Paths)
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
OUTPUTS_CSV_DIR: Path = OUTPUTS_DIR / "csv"
OUTPUTS_FIGURES_DIR: Path = OUTPUTS_DIR / "figures"
OUTPUTS_REPORT_DIR: Path = OUTPUTS_DIR / "report"

HARDWARE_LOG_PATH: Path = DATA_DIR / "hardware_log.csv"
POWER_MEASURE_LOG_PATH: Path = DATA_DIR / "power_measure_log.csv"

for _dir in (DATA_DIR, OUTPUTS_CSV_DIR, OUTPUTS_FIGURES_DIR, OUTPUTS_REPORT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# CSV 스키마
# ---------------------------------------------------------------------------
HARDWARE_LOG_COLUMNS: list[str] = [
    "time_s",
    "state",
    "pir_val",
    "temp_c",
    "humidity",
    "relay_fan",
    "relay_led",
    "relay_buzzer",
    "relay_motor",
    "cpu_temp_c",
    "cpu_percent",
]

POWER_MEASURE_LOG_COLUMNS: list[str] = [
    "time_s",
    "state",
    "voltage_v",
    "current_a",
    "power_w",
]

# ---------------------------------------------------------------------------
# SafeGuard 상태 (State machine states)
# ---------------------------------------------------------------------------
STATE_UWB_DEPARTURE_CHECK = "UWB_DEPARTURE_CHECK"
STATE_PIR_CAMERA_CHECK = "PIR_CAMERA_CHECK"
STATE_MMWAVE_CHECK = "MMWAVE_CHECK"
STATE_THERMAL_PREDICTION = "THERMAL_PREDICTION"
STATE_ACTUATOR_CONTROL = "ACTUATOR_CONTROL"
STATE_FAIL_SAFE = "FAIL_SAFE"

STATE_ORDER: list[str] = [
    STATE_UWB_DEPARTURE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_MMWAVE_CHECK,
    STATE_THERMAL_PREDICTION,
    STATE_ACTUATOR_CONTROL,
    STATE_FAIL_SAFE,
]

# ---------------------------------------------------------------------------
# 시뮬레이션 시간 해상도
# ---------------------------------------------------------------------------
TIME_STEP_S: float = 1.0  # 1초 해상도로 모든 타임라인을 생성한다.

# ---------------------------------------------------------------------------
# 1. UWB_DEPARTURE_CHECK 임계값
# ---------------------------------------------------------------------------
UWB_ROLLING_WINDOW: int = 7  # rolling mean window (samples)
UWB_DEPARTURE_DISTANCE_M: float = 5.0  # 보호자 이탈 판정 거리(m)
UWB_DEPARTURE_HOLD_S: float = 10.0  # 이탈 판정 유지 시간(s)

# ---------------------------------------------------------------------------
# 3. MMWAVE_CHECK 임계값
# ---------------------------------------------------------------------------
MMWAVE_PRESENCE_MIN_DISTANCE_M: float = 0.2
MMWAVE_PRESENCE_MAX_DISTANCE_M: float = 3.0
MMWAVE_CONSECUTIVE_CONFIRM_COUNT: int = 5  # 연속 유효 감지 횟수
MMWAVE_TIMEOUT_S: float = 6.0  # 이 시간 동안 유효 신호가 없으면 timeout -> FAIL_SAFE

# ---------------------------------------------------------------------------
# 4. THERMAL_PREDICTION 임계값
# ---------------------------------------------------------------------------
THERMAL_TARGET_TEMP_C: float = 35.0
THERMAL_ACTION_TEMP_C: float = 32.0  # 현재 온도가 이 값 이상이면 즉시 ACTUATOR_CONTROL
THERMAL_TIME_TO_TARGET_THRESHOLD_S: float = 300.0  # 35도 도달 예상 시간이 이 이하이면 ACTUATOR_CONTROL
THERMAL_RISE_RATE_WINDOW: int = 5  # 온도 상승률 추정에 사용할 최근 샘플 수
THERMAL_MIN_RISE_RATE_C_PER_S: float = 1e-4  # 0에 가까운 상승률로 인한 나눗셈 폭주 방지

# ---------------------------------------------------------------------------
# 5. ACTUATOR_CONTROL: duty-cycle 정책 파라미터
# ---------------------------------------------------------------------------
DUTY_FAN_PERIOD_S: float = 10.0
DUTY_FAN_ON_S: float = 5.0

DUTY_LED_PERIOD_S: float = 2.0
DUTY_LED_ON_S: float = 1.0

DUTY_BUZZER_PERIOD_S: float = 2.0
DUTY_BUZZER_ON_S: float = 1.0
DUTY_BUZZER_ACTIVE_WINDOW_S: float = 10.0  # ACTUATOR_CONTROL 진입 후 이 시간 동안만 buzzer duty 적용

DUTY_MOTOR_ON_WINDOW_S: float = 5.0  # ACTUATOR_CONTROL 진입 후 이 시간만 motor ON

ActuatorPolicy = Literal["continuous", "duty_cycle"]

# ---------------------------------------------------------------------------
# 전력 추정 모델 (Estimated power model, NOT measured)
# 단위: W (Watt)
# ---------------------------------------------------------------------------
POWER_W: dict[str, float] = {
    "raspberry_pi_idle": 2.70,
    "raspberry_pi_active": 3.40,
    "virtual_uwb": 0.50,
    "pir": 0.003,
    "camera": 0.50,
    "virtual_mmwave": 0.80,
    "dht22": 0.013,
    "relay_channel": 0.36,
    "fan": 0.50,
    "led": 0.02,
    "buzzer": 0.10,
    "dc_motor": 0.80,
}

# 4개 릴레이 채널(fan/led/buzzer/motor)이 활성화될 때 채널당 부가되는 전력.
# 릴레이 모듈 자체의 구동 전력이며 액추에이터 전력과 별도로 합산한다.
RELAY_CHANNELS: list[str] = ["fan", "led", "buzzer", "motor"]

# ---------------------------------------------------------------------------
# 비교 모델 이름
# ---------------------------------------------------------------------------
MODEL_ALL_ON = "All-on"
MODEL_PIBASE = "PiBase-style (PIR+Camera always-on)"
MODEL_STAGED = "Staged operation"
MODEL_SAFEGUARD_CONTINUOUS = "SafeGuard (continuous)"
MODEL_SAFEGUARD_DUTY_CYCLE = "SafeGuard (duty-cycle)"

COMPARISON_MODELS: list[str] = [
    MODEL_ALL_ON,
    MODEL_PIBASE,
    MODEL_STAGED,
    MODEL_SAFEGUARD_CONTINUOUS,
    MODEL_SAFEGUARD_DUTY_CYCLE,
]

# ---------------------------------------------------------------------------
# mmWave 가상 센서 동작 모드 (edge case / failure scenario)
# ---------------------------------------------------------------------------
MmwaveMode = Literal[
    "normal", "no_occupant", "intermittent", "timeout", "out_of_range"
]
MMWAVE_MODES: list[str] = [
    "normal",
    "no_occupant",
    "intermittent",
    "timeout",
    "out_of_range",
]

# PIR/Camera 관련 failure scenario
LightCondition = Literal["bright", "dim", "dark"]
MotionState = Literal["still", "moving"]

# ---------------------------------------------------------------------------
# mmWave sensor profile (하드웨어 후보군별 output-level virtual sensor 스펙)
# ---------------------------------------------------------------------------
# 두 profile 모두 raw radar signal(FFT, point cloud raw capture 등)을 직접
# 재현하지 않는 output-level virtual sensor simulation이다. TI profile을
# 선택했다고 해서 실제 TI IWR6843ISK 하드웨어를 사용한 것은 아니며, 단지
# 해당 모듈이 보고하는 output field 구조와 confirmation 임계값을 참고해
# 근사한 것이다.
MMWAVE_PROFILE_C4001 = "C4001_24GHz_LOW_COST"
MMWAVE_PROFILE_TI_IWR6843 = "TI_IWR6843ISK_REFERENCE"

MmwaveProfile = Literal["C4001_24GHz_LOW_COST", "TI_IWR6843ISK_REFERENCE"]

MMWAVE_PROFILES: list[str] = [MMWAVE_PROFILE_C4001, MMWAVE_PROFILE_TI_IWR6843]

#: 대시보드 셀렉트박스에 표시할 사람이 읽기 좋은 label.
MMWAVE_PROFILE_LABELS: dict[str, str] = {
    MMWAVE_PROFILE_C4001: "C4001 24GHz Low-cost profile",
    MMWAVE_PROFILE_TI_IWR6843: "TI IWR6843ISK Reference profile",
}

#: 결과 해석문/한계 문서에 그대로 삽입되는 한국어 한계 명시 문구 (요구사항 고정 표현).
MMWAVE_PROFILE_DESCRIPTIONS_KR: dict[str, str] = {
    MMWAVE_PROFILE_C4001: (
        "low-cost 24GHz radar module profile 기반 output-level virtual sensor simulation"
    ),
    MMWAVE_PROFILE_TI_IWR6843: (
        "TI IWR6843ISK reference profile 기반 output-level virtual sensor simulation"
    ),
}

# C4001_24GHz_LOW_COST confirmation 임계값
# (response_ok, presence_flag=1, 0.2<=distance_m<=3.0 은 공통 규칙에서 처리)
MMWAVE_C4001_CONFIDENCE_MIN: float = 0.6

# TI_IWR6843ISK_REFERENCE confirmation 임계값
MMWAVE_TI_CONFIDENCE_MIN: float = 0.75
MMWAVE_TI_POINT_COUNT_MIN: int = 3


@dataclass(frozen=True)
class ScenarioConfig:
    """대시보드/테스트에서 시나리오 조건을 구성하기 위한 데이터클래스.

    이 값들은 실제 하드웨어 측정값이 아니라 사용자가 조정하는
    "시나리오 기반" 입력 파라미터이다.
    """

    duration_s: float = 900.0  # 전체 시뮬레이션 길이(s)
    occupant_exists: bool = True
    guardian_departure_time_s: float = 15.0  # 보호자가 멀어지기 시작하는 시각
    initial_temp_c: float = 28.0
    outside_temp_c: float = 38.0
    humidity_pct: float = 55.0
    temp_rise_rate_c_per_min: float = 0.6  # 초기 온도 상승 속도(대략치, 뉴턴 냉각식으로 보정됨)
    light_condition: LightCondition = "bright"
    motion_state: MotionState = "moving"
    mmwave_mode: MmwaveMode = "normal"
    mmwave_profile: MmwaveProfile = MMWAVE_PROFILE_C4001
    actuator_policy: ActuatorPolicy = "duty_cycle"
    pir_false_positive: bool = False
    dht22_failure: bool = False
    seed: int = RANDOM_SEED


# ---------------------------------------------------------------------------
# Demo Mode 프리셋 (dashboard와 scripts/generate_paper_outputs.py가 공유)
# ---------------------------------------------------------------------------
DEMO_NORMAL_RISK = "Normal Risk Scenario"
DEMO_NO_OCCUPANT = "No Occupant Scenario"
DEMO_MMWAVE_TIMEOUT = "mmWave Timeout Fail-safe Scenario"
DEMO_DUTY_CYCLE_OPTIMIZED = "Duty-cycle Optimized Scenario"

#: Demo Mode 시나리오 프리셋. Normal Risk와 Duty-cycle Optimized는 동일한
#: 발생 조건(보호자 이탈, 온도 상승)에서 액추에이터 정책만 다르게 하여
#: continuous 대비 duty-cycle의 절감 효과를 명확히 대비시키기 위한 쌍이다.
DEMO_SCENARIOS: dict[str, ScenarioConfig] = {
    DEMO_NORMAL_RISK: ScenarioConfig(
        duration_s=300.0,
        occupant_exists=True,
        guardian_departure_time_s=10.0,
        initial_temp_c=30.0,
        outside_temp_c=42.0,
        humidity_pct=55.0,
        temp_rise_rate_c_per_min=3.5,
        light_condition="bright",
        motion_state="moving",
        mmwave_mode="normal",
        actuator_policy="continuous",
        pir_false_positive=False,
        dht22_failure=False,
    ),
    DEMO_NO_OCCUPANT: ScenarioConfig(
        duration_s=300.0,
        occupant_exists=False,
        guardian_departure_time_s=10.0,
        initial_temp_c=25.0,
        outside_temp_c=27.0,
        humidity_pct=50.0,
        temp_rise_rate_c_per_min=0.2,
        light_condition="bright",
        motion_state="still",
        mmwave_mode="no_occupant",
        actuator_policy="duty_cycle",
        pir_false_positive=False,
        dht22_failure=False,
    ),
    DEMO_MMWAVE_TIMEOUT: ScenarioConfig(
        duration_s=300.0,
        occupant_exists=True,
        guardian_departure_time_s=10.0,
        initial_temp_c=30.0,
        outside_temp_c=42.0,
        humidity_pct=55.0,
        temp_rise_rate_c_per_min=3.5,
        light_condition="bright",
        motion_state="moving",
        mmwave_mode="timeout",
        actuator_policy="duty_cycle",
        pir_false_positive=False,
        dht22_failure=False,
    ),
    DEMO_DUTY_CYCLE_OPTIMIZED: ScenarioConfig(
        duration_s=300.0,
        occupant_exists=True,
        guardian_departure_time_s=10.0,
        initial_temp_c=30.0,
        outside_temp_c=42.0,
        humidity_pct=55.0,
        temp_rise_rate_c_per_min=3.5,
        light_condition="bright",
        motion_state="moving",
        mmwave_mode="normal",
        actuator_policy="duty_cycle",
        pir_false_positive=False,
        dht22_failure=False,
    ),
}

# ---------------------------------------------------------------------------
# sample_data/ 경로 (release 패키지에 포함되는 재현 가능한 예시 hardware log)
# ---------------------------------------------------------------------------
SAMPLE_DATA_DIR: Path = PROJECT_ROOT / "sample_data"
