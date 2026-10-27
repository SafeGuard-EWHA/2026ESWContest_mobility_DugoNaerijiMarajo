"""src/data_loader.py 에 대한 단위 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.config import HARDWARE_LOG_COLUMNS, ScenarioConfig
from src.data_loader import (
    HardwareLogValidationError,
    generate_dummy_hardware_log,
    handle_missing_values,
    load_hardware_log,
    normalize_relay_columns,
    validate_hardware_log,
)


def test_generate_dummy_hardware_log_schema():
    """dummy 로그가 필수 스키마를 모두 만족해야 한다."""
    scenario = ScenarioConfig(duration_s=60)
    df = generate_dummy_hardware_log(scenario)
    for col in HARDWARE_LOG_COLUMNS:
        assert col in df.columns
    assert len(df) == 61  # 0..60 inclusive at 1s step


def test_generate_dummy_hardware_log_is_reproducible():
    """동일 시드의 시나리오는 동일한 dummy 로그를 생성해야 한다(재현성)."""
    s1 = ScenarioConfig(duration_s=30, seed=123)
    s2 = ScenarioConfig(duration_s=30, seed=123)
    df1 = generate_dummy_hardware_log(s1)
    df2 = generate_dummy_hardware_log(s2)
    pd.testing.assert_frame_equal(df1, df2)


def test_validate_hardware_log_missing_columns_raises():
    df = pd.DataFrame({"time_s": [0, 1]})
    with pytest.raises(HardwareLogValidationError):
        validate_hardware_log(df)


def test_normalize_relay_columns_handles_mixed_tokens():
    df = pd.DataFrame(
        {
            "relay_fan": ["ON", "off", 1, 0, np.nan],
            "relay_led": [True, False, "1", "0", "on"],
            "relay_buzzer": [0, 0, 0, 0, 0],
            "relay_motor": [1, 1, 1, 1, 1],
        }
    )
    out = normalize_relay_columns(df)
    assert out["relay_fan"].tolist() == [1, 0, 1, 0, 0]
    assert out["relay_led"].tolist() == [1, 0, 1, 0, 1]
    assert set(out["relay_fan"].unique()).issubset({0, 1})


def test_handle_missing_values_interpolates_dht22_failure():
    df = pd.DataFrame(
        {
            "temp_c": [25.0, np.nan, np.nan, 28.0],
            "humidity": [50.0, 51.0, np.nan, 53.0],
            "pir_val": [1, np.nan, 0, 1],
            "cpu_temp_c": [40.0, np.nan, 41.0, 42.0],
            "cpu_percent": [10.0, 11.0, np.nan, 13.0],
        }
    )
    with pytest.warns(UserWarning):
        out = handle_missing_values(df)
    assert not out["temp_c"].isna().any()
    assert not out["humidity"].isna().any()
    assert out["dht22_failure_flag"].sum() == 2
    assert out["pir_val"].tolist() == [1, 0, 0, 1]


def test_load_hardware_log_from_csv(tmp_path):
    scenario = ScenarioConfig(duration_s=10)
    df = generate_dummy_hardware_log(scenario)
    csv_path = tmp_path / "hardware_log.csv"
    df.drop(columns=["dht22_failure_flag"]).to_csv(csv_path, index=False)

    loaded = load_hardware_log(csv_path)
    for col in HARDWARE_LOG_COLUMNS:
        assert col in loaded.columns
