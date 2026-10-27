"""
SafeGuard TwinLab Agent - device ON/OFF activation table 생성.

SafeGuard proposed model은 Cascading Wake-up 방식을 따른다: 현재 state에서
"필요한" 센서/제어부만 조건부로 활성화하고, 이전 단계의 센서는 끈다. 이는
All-on 모델(모든 장치 상시 ON)과 대비되는 SafeGuard의 핵심 절전 메커니즘이다.

모델링 가정(assumption, 문서화):
- DHT22(온습도)는 소비전력이 매우 낮고(0.013W) THERMAL_PREDICTION 단계에서
  온도 상승률을 계산하려면 사전 이력이 필요하므로, 전 구간에서 상시 ON으로
  가정한다.
- relay_channel 전력은 해당 채널의 액추에이터가 ON일 때만 소비된다고
  가정한다 (옵토커플러/MOSFET 구동형 릴레이 모듈 기준).
- FAIL_SAFE에서는 occupant_confirmed가 되지 않은 상태이므로 DC motor는
  절대 구동하지 않는다 (안전 보수적 정책). buzzer는 경고 목적상 10초
  제한 없이 정책(continuous/duty-cycle)에 따라 지속 동작한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    ActuatorPolicy,
    DUTY_BUZZER_ACTIVE_WINDOW_S,
    DUTY_BUZZER_ON_S,
    DUTY_BUZZER_PERIOD_S,
    DUTY_FAN_ON_S,
    DUTY_FAN_PERIOD_S,
    DUTY_LED_ON_S,
    DUTY_LED_PERIOD_S,
    DUTY_MOTOR_ON_WINDOW_S,
    STATE_ACTUATOR_CONTROL,
    STATE_FAIL_SAFE,
    STATE_MMWAVE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_UWB_DEPARTURE_CHECK,
)

DEVICE_COLUMNS: list[str] = [
    "raspberry_pi_idle",
    "raspberry_pi_active",
    "virtual_uwb",
    "pir",
    "camera",
    "virtual_mmwave",
    "dht22",
    "fan",
    "led",
    "buzzer",
    "dc_motor",
    "relay_fan",
    "relay_led",
    "relay_buzzer",
    "relay_motor",
]


def compute_duty_cycle_series(
    t_rel: np.ndarray,
    period_s: float,
    on_s: float,
    active_window_s: float | None = None,
) -> np.ndarray:
    """duty-cycle 주기 패턴의 ON/OFF(1/0) 시퀀스를 계산한다.

    Args:
        t_rel: 해당 액추에이터 제어가 시작된 시점을 0으로 하는 상대 시간(s).
        period_s: duty-cycle 주기(s).
        on_s: 주기 내 ON 유지 시간(s).
        active_window_s: 지정 시, 이 시간 이후에는 무조건 OFF로 강제한다
            (예: buzzer/motor의 초기 활성 구간 제한).

    Returns:
        0/1 int array.
    """
    phase = np.mod(t_rel, period_s)
    on = (phase < on_s).astype(int)
    if active_window_s is not None:
        on = np.where(t_rel < active_window_s, on, 0)
    return on


def compute_actuator_series(
    t_rel: np.ndarray,
    policy: ActuatorPolicy,
    allow_motor: bool,
    limit_buzzer_window: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """fan/led/buzzer/motor의 ON/OFF 시퀀스를 정책에 따라 계산하는 내부 헬퍼."""
    n = len(t_rel)
    if policy == "continuous":
        fan = np.ones(n, dtype=int)
        led = np.ones(n, dtype=int)
        buzzer = np.ones(n, dtype=int)
        motor = np.ones(n, dtype=int) if allow_motor else np.zeros(n, dtype=int)
        return fan, led, buzzer, motor

    # duty_cycle policy
    fan = compute_duty_cycle_series(t_rel, DUTY_FAN_PERIOD_S, DUTY_FAN_ON_S)
    led = compute_duty_cycle_series(t_rel, DUTY_LED_PERIOD_S, DUTY_LED_ON_S)
    buzzer_window = DUTY_BUZZER_ACTIVE_WINDOW_S if limit_buzzer_window else None
    buzzer = compute_duty_cycle_series(
        t_rel, DUTY_BUZZER_PERIOD_S, DUTY_BUZZER_ON_S, active_window_s=buzzer_window
    )
    motor = np.zeros(n, dtype=int)
    if allow_motor:
        motor = (t_rel < DUTY_MOTOR_ON_WINDOW_S).astype(int)
    return fan, led, buzzer, motor


def compute_device_activation(
    state_df: pd.DataFrame, actuator_policy: ActuatorPolicy
) -> pd.DataFrame:
    """SafeGuard proposed model의 Cascading Wake-up 기반 device 활성화 표를 만든다.

    Args:
        state_df: state_machine.run_state_machine()의 결과 (time_s, state 포함).
        actuator_policy: "continuous" 또는 "duty_cycle".

    Returns:
        time_s, state + DEVICE_COLUMNS(0/1) 로 구성된 DataFrame.
        이 표가 power_model.compute_power_timeline()의 입력이 된다.
    """
    t = state_df["time_s"].to_numpy(dtype=float)
    state = state_df["state"].to_numpy()
    n = len(t)

    cols: dict[str, np.ndarray] = {
        name: np.zeros(n, dtype=int) for name in DEVICE_COLUMNS
    }

    # DHT22는 열 예측 이력 확보를 위해 상시 ON으로 가정한다 (전력 영향 미미).
    cols["dht22"][:] = 1

    is_uwb = state == STATE_UWB_DEPARTURE_CHECK
    is_pir_cam = state == STATE_PIR_CAMERA_CHECK
    is_mmwave = state == STATE_MMWAVE_CHECK
    is_actuator = state == STATE_ACTUATOR_CONTROL
    is_failsafe = state == STATE_FAIL_SAFE

    # Stage 1: UWB_DEPARTURE_CHECK -> Raspberry Pi 절전(idle) + UWB만 ON.
    cols["raspberry_pi_idle"][is_uwb] = 1
    cols["virtual_uwb"][is_uwb] = 1

    # Stage 2 이후: Pi는 능동 처리 모드로 전환된다.
    cols["raspberry_pi_active"][~is_uwb] = 1

    # Stage 2: PIR_CAMERA_CHECK -> PIR + Camera ON (UWB는 cascading에 따라 OFF).
    cols["pir"][is_pir_cam] = 1
    cols["camera"][is_pir_cam] = 1

    # Stage 3: MMWAVE_CHECK -> mmWave만 ON.
    cols["virtual_mmwave"][is_mmwave] = 1

    # Stage 5: ACTUATOR_CONTROL -> continuous/duty-cycle 정책에 따른 액추에이터 구동.
    if is_actuator.any():
        idx = np.where(is_actuator)[0]
        entry_time = t[idx].min()
        t_rel = t[idx] - entry_time
        fan, led, buzzer, motor = compute_actuator_series(
            t_rel, actuator_policy, allow_motor=True, limit_buzzer_window=True
        )
        cols["fan"][idx] = fan
        cols["led"][idx] = led
        cols["buzzer"][idx] = buzzer
        cols["dc_motor"][idx] = motor

    # Stage 6: FAIL_SAFE -> 보수적 경고/완화 제어 (motor는 항상 OFF).
    if is_failsafe.any():
        idx = np.where(is_failsafe)[0]
        entry_time = t[idx].min()
        t_rel = t[idx] - entry_time
        fan, led, buzzer, _motor = compute_actuator_series(
            t_rel, actuator_policy, allow_motor=False, limit_buzzer_window=False
        )
        cols["fan"][idx] = fan
        cols["led"][idx] = led
        cols["buzzer"][idx] = buzzer

    # 릴레이 채널은 해당 액추에이터가 ON일 때만 전력을 소비한다고 가정한다.
    cols["relay_fan"] = cols["fan"].copy()
    cols["relay_led"] = cols["led"].copy()
    cols["relay_buzzer"] = cols["buzzer"].copy()
    cols["relay_motor"] = cols["dc_motor"].copy()

    out = pd.DataFrame(cols)
    out.insert(0, "time_s", t)
    out.insert(1, "state", state)
    return out
