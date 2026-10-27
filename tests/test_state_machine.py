"""src/state_machine.py 에 대한 상태 전이 단위 테스트.

각 테스트는 결정론적으로 구성한 합성 sim_df를 사용하여 SafeGuard 상태
전이 규칙을 정확히 검증한다 (UWB -> PIR/Camera -> mmWave -> Thermal ->
Actuator, 그리고 mmWave timeout -> FAIL_SAFE 분기).
"""

import numpy as np
import pandas as pd
import pytest

from src.config import (
    STATE_ACTUATOR_CONTROL,
    STATE_FAIL_SAFE,
    STATE_MMWAVE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_THERMAL_PREDICTION,
    STATE_UWB_DEPARTURE_CHECK,
)
from src.state_machine import compute_thermal_prediction, run_state_machine


def _base_frame(n=60):
    """state_machine이 요구하는 최소 컬럼(response_ok, mmwave_valid_reading 등)을
    갖춘 결정론적 합성 프레임. 두 컬럼은 virtual_sensors.compute_mmwave_validity()가
    profile별 confirmation rule을 적용해 미리 계산해 두는 값을 흉내낸 것이다.
    """
    t = np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "time_s": t,
            "pir_val": np.zeros(n, dtype=int),
            "camera_val": np.zeros(n, dtype=int),
            "guardian_distance_rolling_mean": np.full(n, 2.0),
            "response_ok": np.zeros(n, dtype=bool),
            "mmwave_valid_reading": np.zeros(n, dtype=bool),
            "temp_c": 20 + 0.5 * t,
        }
    )


def test_full_happy_path_reaches_actuator_control():
    df = _base_frame(60)
    # t=10부터 거리 6m(>=5m 임계값)로 이탈 시작.
    df.loc[df["time_s"] >= 10, "guardian_distance_rolling_mean"] = 6.0
    # PIR_CAMERA_CHECK 진입 후(t>=20) t=25부터 PIR 감지.
    df.loc[df["time_s"] >= 25, "pir_val"] = 1
    # MMWAVE_CHECK 진입 후(t>=25) 5회 연속 유효 감지.
    df.loc[df["time_s"] >= 25, "response_ok"] = True
    df.loc[df["time_s"] >= 25, "mmwave_valid_reading"] = True

    result_df, event_log = run_state_machine(df)

    # UWB 이탈 판정: 5m 이상이 10초 유지된 시점(t=20)에 전이.
    departure_events = [e for e in event_log if e["to_state"] == STATE_PIR_CAMERA_CHECK]
    assert len(departure_events) == 1
    assert departure_events[0]["time_s"] == 20.0

    # PIR OR Camera 감지(t=25)에서 MMWAVE_CHECK로 전이.
    mmwave_events = [e for e in event_log if e["to_state"] == STATE_MMWAVE_CHECK]
    assert mmwave_events[0]["time_s"] == 25.0

    # MMWAVE_CHECK 상태 판정 로직은 t=26부터 시작해 5회 연속 유효 판독 후
    # t=30에 occupant_confirmed로 전이한다 (진입 시점 행은 이전 상태 로직이
    # 이미 소비했으므로 다음 행부터 카운트가 시작된다).
    thermal_events = [e for e in event_log if e["to_state"] == STATE_THERMAL_PREDICTION]
    assert thermal_events[0]["time_s"] == 30.0
    assert result_df.loc[result_df["time_s"] == 30, "occupant_confirmed"].iloc[0]

    # 온도가 32도 이상이 되는 시점 이후 ACTUATOR_CONTROL로 전이.
    actuator_events = [e for e in event_log if e["to_state"] == STATE_ACTUATOR_CONTROL]
    assert len(actuator_events) == 1
    assert result_df["state"].iloc[-1] == STATE_ACTUATOR_CONTROL


def test_uwb_departure_requires_10s_hold_not_just_5m():
    """5m 이상이어도 10초 미만이면 이탈로 판정하지 않아야 한다."""
    df = _base_frame(60)
    # t=10~15만 6m, 이후 다시 2m로 복귀 (hold 조건 미충족).
    df.loc[(df["time_s"] >= 10) & (df["time_s"] < 15), "guardian_distance_rolling_mean"] = 6.0
    result_df, event_log = run_state_machine(df)
    assert all(s == STATE_UWB_DEPARTURE_CHECK for s in result_df["state"])
    assert len(event_log) == 1  # simulation_start만 존재


def test_pir_or_camera_either_triggers_transition():
    """PIR 없이 Camera만 감지되어도 MMWAVE_CHECK로 전이해야 한다 (OR 조건)."""
    df = _base_frame(40)
    df.loc[df["time_s"] >= 10, "guardian_distance_rolling_mean"] = 6.0
    df.loc[df["time_s"] >= 22, "camera_val"] = 1  # PIR은 계속 0
    result_df, event_log = run_state_machine(df)
    mmwave_events = [e for e in event_log if e["to_state"] == STATE_MMWAVE_CHECK]
    assert len(mmwave_events) == 1
    assert mmwave_events[0]["reason"].startswith("pir_val=0 OR camera_val=1")


def test_mmwave_timeout_triggers_fail_safe():
    """mmWave 응답이 timeout 기준 이상 없으면 FAIL_SAFE로 전이해야 한다."""
    df = _base_frame(40)
    df.loc[df["time_s"] >= 10, "guardian_distance_rolling_mean"] = 6.0
    df.loc[df["time_s"] >= 20, "pir_val"] = 1
    # response_ok가 전 구간 False(기본값) -> mmWave 무응답(timeout) 재현.
    result_df, event_log = run_state_machine(df)
    failsafe_events = [e for e in event_log if e["to_state"] == STATE_FAIL_SAFE]
    assert len(failsafe_events) == 1
    assert "timeout" in failsafe_events[0]["reason"]
    assert result_df["state"].iloc[-1] == STATE_FAIL_SAFE


def test_mmwave_streak_resets_on_invalid_sample():
    """연속 유효 판독 중간에 무효 샘플이 끼면 streak가 리셋되어야 한다."""
    df = _base_frame(50)
    df.loc[df["time_s"] >= 10, "guardian_distance_rolling_mean"] = 6.0
    df.loc[df["time_s"] >= 20, "pir_val"] = 1
    df.loc[df["time_s"] >= 20, "response_ok"] = True
    df.loc[df["time_s"] >= 20, "mmwave_valid_reading"] = True
    # t=23 에 무효 샘플(응답은 했으나 profile 기준 미달) 삽입 -> streak 리셋.
    df.loc[df["time_s"] == 23, "mmwave_valid_reading"] = False
    result_df, event_log = run_state_machine(df)
    thermal_events = [e for e in event_log if e["to_state"] == STATE_THERMAL_PREDICTION]
    # streak: 20,21,22(3) -> reset at 23 -> 24,25,26,27,28(5) -> confirm at 28
    assert thermal_events[0]["time_s"] == 28.0


def test_compute_thermal_prediction_time_to_target_decreases():
    n = 30
    t = np.arange(n, dtype=float)
    df = pd.DataFrame({"time_s": t, "temp_c": 20 + 0.5 * t})
    out = compute_thermal_prediction(df)
    # 온도가 선형 상승하므로 시간이 지날수록 목표까지 남은 시간이 감소해야 한다.
    later = out["time_to_35c_s"].iloc[15:].dropna()
    assert later.is_monotonic_decreasing or (later.diff().dropna() <= 0).all()
