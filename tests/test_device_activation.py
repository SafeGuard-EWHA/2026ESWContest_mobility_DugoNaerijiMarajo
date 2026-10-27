"""src/device_activation.py 에 대한 단위 테스트 (Cascading Wake-up 및 duty-cycle 검증)."""

import numpy as np
import pandas as pd
import pytest

from src.config import (
    STATE_ACTUATOR_CONTROL,
    STATE_FAIL_SAFE,
    STATE_MMWAVE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_UWB_DEPARTURE_CHECK,
)
from src.device_activation import compute_device_activation, compute_duty_cycle_series


def test_duty_cycle_series_fan_pattern():
    """fan은 10초 중 5초 ON 패턴을 정확히 따라야 한다."""
    t_rel = np.arange(20, dtype=float)
    fan = compute_duty_cycle_series(t_rel, period_s=10.0, on_s=5.0)
    assert fan[0:5].tolist() == [1, 1, 1, 1, 1]
    assert fan[5:10].tolist() == [0, 0, 0, 0, 0]
    assert fan[10:15].tolist() == [1, 1, 1, 1, 1]


def test_duty_cycle_series_active_window_cuts_off():
    """active_window_s 이후에는 duty 패턴과 무관하게 항상 OFF여야 한다."""
    t_rel = np.arange(15, dtype=float)
    buzzer = compute_duty_cycle_series(
        t_rel, period_s=2.0, on_s=1.0, active_window_s=10.0
    )
    assert buzzer[10:].sum() == 0


def _make_state_df():
    segments = (
        [STATE_UWB_DEPARTURE_CHECK] * 10
        + [STATE_PIR_CAMERA_CHECK] * 10
        + [STATE_MMWAVE_CHECK] * 10
        + [STATE_ACTUATOR_CONTROL] * 20
    )
    n = len(segments)
    return pd.DataFrame({"time_s": np.arange(n, dtype=float), "state": segments})


def test_cascading_wakeup_sensors_are_mutually_exclusive():
    """각 단계에서는 해당 단계의 센서만 ON이어야 한다 (cascading, 누적 아님)."""
    df = _make_state_df()
    out = compute_device_activation(df, "duty_cycle")

    uwb_rows = out[out["state"] == STATE_UWB_DEPARTURE_CHECK]
    assert (uwb_rows["virtual_uwb"] == 1).all()
    assert (uwb_rows["pir"] == 0).all()
    assert (uwb_rows["virtual_mmwave"] == 0).all()

    pir_rows = out[out["state"] == STATE_PIR_CAMERA_CHECK]
    assert (pir_rows["pir"] == 1).all()
    assert (pir_rows["camera"] == 1).all()
    assert (pir_rows["virtual_uwb"] == 0).all()

    mmwave_rows = out[out["state"] == STATE_MMWAVE_CHECK]
    assert (mmwave_rows["virtual_mmwave"] == 1).all()
    assert (mmwave_rows["pir"] == 0).all()


def test_continuous_policy_keeps_actuators_on_entire_control_window():
    df = _make_state_df()
    out = compute_device_activation(df, "continuous")
    actuator_rows = out[out["state"] == STATE_ACTUATOR_CONTROL]
    assert (actuator_rows["fan"] == 1).all()
    assert (actuator_rows["led"] == 1).all()
    assert (actuator_rows["buzzer"] == 1).all()
    assert (actuator_rows["dc_motor"] == 1).all()


def test_duty_cycle_policy_motor_only_first_5s_of_actuator_control():
    df = _make_state_df()
    out = compute_device_activation(df, "duty_cycle")
    actuator_rows = out[out["state"] == STATE_ACTUATOR_CONTROL].reset_index(drop=True)
    assert actuator_rows.loc[0:4, "dc_motor"].tolist() == [1, 1, 1, 1, 1]
    assert actuator_rows.loc[5:, "dc_motor"].sum() == 0


def test_fail_safe_never_activates_motor_regardless_of_policy():
    n = 15
    df = pd.DataFrame(
        {"time_s": np.arange(n, dtype=float), "state": [STATE_FAIL_SAFE] * n}
    )
    for policy in ("continuous", "duty_cycle"):
        out = compute_device_activation(df, policy)
        assert (out["dc_motor"] == 0).all()
        assert (out["relay_motor"] == 0).all()


def test_dht22_is_always_on_across_all_states():
    df = _make_state_df()
    out = compute_device_activation(df, "duty_cycle")
    assert (out["dht22"] == 1).all()


def test_relay_channels_mirror_their_actuator():
    df = _make_state_df()
    out = compute_device_activation(df, "continuous")
    assert (out["relay_fan"] == out["fan"]).all()
    assert (out["relay_led"] == out["led"]).all()
    assert (out["relay_buzzer"] == out["buzzer"]).all()
    assert (out["relay_motor"] == out["dc_motor"]).all()
