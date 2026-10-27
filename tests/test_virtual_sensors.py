"""src/virtual_sensors.py 에 대한 단위 테스트 (UWB/mmWave/Camera edge case 포함).

mmWave는 단일 센서가 아니라 sensor profile(C4001_24GHz_LOW_COST /
TI_IWR6843ISK_REFERENCE) 선택에 따라 output field와 confirmation
threshold가 달라진다. 두 profile 모두 output-level virtual sensor
simulation이며 raw radar signal을 재현하지 않는다.
"""

import numpy as np
import pandas as pd

from src.config import (
    MMWAVE_C4001_CONFIDENCE_MIN,
    MMWAVE_PRESENCE_MAX_DISTANCE_M,
    MMWAVE_PRESENCE_MIN_DISTANCE_M,
    MMWAVE_PROFILE_C4001,
    MMWAVE_PROFILE_TI_IWR6843,
    MMWAVE_TI_CONFIDENCE_MIN,
    MMWAVE_TI_POINT_COUNT_MIN,
    ScenarioConfig,
)
from src.virtual_sensors import (
    compute_mmwave_validity,
    generate_mmwave,
    generate_uwb_distance,
    generate_virtual_sensor_log,
)


def test_uwb_distance_increases_after_departure():
    """보호자 이탈 시각 이후 rolling mean 거리가 증가해야 한다."""
    scenario = ScenarioConfig(duration_s=120, guardian_departure_time_s=10)
    df = generate_uwb_distance(scenario)
    before = df[df["time_s"] < 10]["guardian_distance_m"].mean()
    after = df[df["time_s"] > 60]["guardian_distance_m"].mean()
    assert after > before


def test_mmwave_no_occupant_mode_never_confirms():
    scenario = ScenarioConfig(duration_s=60, mmwave_mode="no_occupant")
    df = generate_mmwave(scenario)
    assert (df["presence_flag"] == 0).all()
    assert df["distance_m"].isna().all()
    assert not df["mmwave_valid_reading"].any()


def test_mmwave_timeout_mode_produces_no_response_tail():
    scenario = ScenarioConfig(duration_s=90, mmwave_mode="timeout")
    df = generate_mmwave(scenario)
    tail = df.iloc[-5:]
    assert not tail["response_ok"].any()
    assert tail["presence_flag"].isna().all()
    assert not tail["mmwave_valid_reading"].any()


def test_mmwave_out_of_range_never_valid_for_either_profile():
    for profile in (MMWAVE_PROFILE_C4001, MMWAVE_PROFILE_TI_IWR6843):
        scenario = ScenarioConfig(duration_s=30, mmwave_mode="out_of_range", mmwave_profile=profile)
        df = generate_mmwave(scenario)
        assert not df["mmwave_valid_reading"].any()
        assert (df["distance_m"] > MMWAVE_PRESENCE_MAX_DISTANCE_M).all()


def test_mmwave_normal_mode_is_valid_within_range_c4001():
    scenario = ScenarioConfig(
        duration_s=30,
        mmwave_mode="normal",
        occupant_exists=True,
        mmwave_profile=MMWAVE_PROFILE_C4001,
    )
    df = generate_mmwave(scenario)
    assert (df["presence_flag"] == 1).all()
    assert (
        (df["distance_m"] >= MMWAVE_PRESENCE_MIN_DISTANCE_M)
        & (df["distance_m"] <= MMWAVE_PRESENCE_MAX_DISTANCE_M)
    ).all()
    # normal 모드는 confidence_score가 대체로 높게 합성되어 대부분 유효해야 한다.
    assert df["mmwave_valid_reading"].mean() > 0.8


def test_mmwave_ti_profile_has_extra_fields():
    scenario = ScenarioConfig(duration_s=20, mmwave_profile=MMWAVE_PROFILE_TI_IWR6843)
    df = generate_mmwave(scenario)
    for col in ("point_count", "angle_deg", "micro_motion_score"):
        assert col in df.columns
    # C4001은 TI 전용 필드를 갖지 않는다.
    c4001_df = generate_mmwave(
        ScenarioConfig(duration_s=20, mmwave_profile=MMWAVE_PROFILE_C4001)
    )
    for col in ("point_count", "angle_deg", "micro_motion_score"):
        assert col not in c4001_df.columns


def test_mmwave_profile_column_records_selected_profile():
    for profile in (MMWAVE_PROFILE_C4001, MMWAVE_PROFILE_TI_IWR6843):
        df = generate_mmwave(ScenarioConfig(duration_s=10, mmwave_profile=profile))
        assert (df["mmwave_profile"] == profile).all()


def test_compute_mmwave_validity_c4001_accepts_moderate_confidence():
    """confidence_score가 0.6~0.75 사이면 C4001은 유효, TI는 무효로 갈려야 한다."""
    n = 5
    df = pd.DataFrame(
        {
            "response_ok": [True] * n,
            "presence_flag": [1.0] * n,
            "distance_m": [1.0] * n,
            "confidence_score": [0.65] * n,
            "point_count": [5] * n,
        }
    )
    c4001_valid = compute_mmwave_validity(MMWAVE_PROFILE_C4001, df)
    ti_valid = compute_mmwave_validity(MMWAVE_PROFILE_TI_IWR6843, df)
    assert c4001_valid.all()
    assert not ti_valid.any()


def test_compute_mmwave_validity_ti_requires_point_count():
    """confidence는 충분해도 point_count가 부족하면 TI는 무효여야 한다."""
    n = 5
    df = pd.DataFrame(
        {
            "response_ok": [True] * n,
            "presence_flag": [1.0] * n,
            "distance_m": [1.0] * n,
            "confidence_score": [0.95] * n,
            "point_count": [1] * n,  # MMWAVE_TI_POINT_COUNT_MIN(3) 미달
        }
    )
    assert not compute_mmwave_validity(MMWAVE_PROFILE_TI_IWR6843, df).any()


def test_compute_mmwave_validity_thresholds_match_config():
    assert MMWAVE_C4001_CONFIDENCE_MIN < MMWAVE_TI_CONFIDENCE_MIN
    assert MMWAVE_TI_POINT_COUNT_MIN >= 1


def test_generate_virtual_sensor_log_merges_all_columns():
    scenario = ScenarioConfig(duration_s=20)
    df = generate_virtual_sensor_log(scenario)
    expected_cols = {
        "time_s",
        "guardian_distance_m",
        "guardian_distance_rolling_mean",
        "camera_val",
        "response_ok",
        "presence_flag",
        "distance_m",
        "velocity_mps",
        "confidence_score",
        "mmwave_valid_reading",
        "mmwave_profile",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == 21
