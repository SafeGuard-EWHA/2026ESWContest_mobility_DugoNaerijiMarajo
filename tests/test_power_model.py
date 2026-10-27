"""src/power_model.py 에 대한 단위 테스트 (전력/에너지 계산 검증)."""

import numpy as np
import pandas as pd
import pytest

from src.config import POWER_W
from src.power_model import (
    compute_energy_by_state,
    compute_power_timeline,
    compute_savings_pct,
    compute_summary_metrics,
)


def _make_activation_df():
    n = 10
    return pd.DataFrame(
        {
            "time_s": np.arange(n, dtype=float),
            "state": ["S1"] * 5 + ["S2"] * 5,
            "raspberry_pi_idle": [1] * 5 + [0] * 5,
            "raspberry_pi_active": [0] * 5 + [1] * 5,
            "virtual_uwb": [1] * 5 + [0] * 5,
            "pir": [0] * 10,
            "camera": [0] * 10,
            "virtual_mmwave": [0] * 10,
            "dht22": [1] * 10,
            "fan": [0] * 5 + [1] * 5,
            "led": [0] * 10,
            "buzzer": [0] * 10,
            "dc_motor": [0] * 10,
            "relay_fan": [0] * 5 + [1] * 5,
            "relay_led": [0] * 10,
            "relay_buzzer": [0] * 10,
            "relay_motor": [0] * 10,
        }
    )


def test_compute_power_timeline_matches_manual_sum():
    df = _make_activation_df()
    out = compute_power_timeline(df)

    expected_s1 = POWER_W["raspberry_pi_idle"] + POWER_W["virtual_uwb"] + POWER_W["dht22"]
    expected_s2 = (
        POWER_W["raspberry_pi_active"]
        + POWER_W["dht22"]
        + POWER_W["fan"]
        + POWER_W["relay_channel"]
    )

    assert out.loc[0, "power_w"] == pytest.approx(expected_s1)
    assert out.loc[9, "power_w"] == pytest.approx(expected_s2)


def test_compute_energy_by_state_sums_correctly():
    df = _make_activation_df()
    power_df = compute_power_timeline(df)
    energy = compute_energy_by_state(power_df)

    s1_row = energy[energy["state"] == "S1"].iloc[0]
    expected_power_s1 = (
        POWER_W["raspberry_pi_idle"] + POWER_W["virtual_uwb"] + POWER_W["dht22"]
    )
    # TIME_STEP_S = 1.0s, 5 samples -> energy_j = power * 5
    assert s1_row["energy_j"] == pytest.approx(expected_power_s1 * 5)
    assert s1_row["duration_s"] == pytest.approx(5.0)


def test_compute_summary_metrics():
    df = _make_activation_df()
    power_df = compute_power_timeline(df)
    summary = compute_summary_metrics(power_df)

    assert summary["max_power_w"] == pytest.approx(power_df["power_w"].max())
    assert summary["avg_power_w"] == pytest.approx(power_df["power_w"].mean())
    assert summary["total_energy_j"] == pytest.approx(power_df["power_w"].sum() * 1.0)
    assert summary["total_energy_wh"] == pytest.approx(summary["total_energy_j"] / 3600.0)


def test_compute_savings_pct_positive_and_zero_baseline():
    assert compute_savings_pct(50.0, 100.0) == pytest.approx(50.0)
    assert compute_savings_pct(150.0, 100.0) == pytest.approx(-50.0)
    assert compute_savings_pct(10.0, 0.0) == 0.0
