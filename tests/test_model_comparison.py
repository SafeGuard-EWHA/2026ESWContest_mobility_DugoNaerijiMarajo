"""src/model_comparison.py 에 대한 단위/통합 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.config import (
    MMWAVE_PROFILE_TI_IWR6843,
    MODEL_ALL_ON,
    MODEL_SAFEGUARD_CONTINUOUS,
    MODEL_SAFEGUARD_DUTY_CYCLE,
    POWER_W,
    ScenarioConfig,
)
from src.data_loader import generate_dummy_hardware_log
from src.model_comparison import (
    build_all_on_activation,
    build_pibase_activation,
    build_staged_activation,
    run_all_model_comparisons,
)
from src.state_machine import build_simulation_frame, run_state_machine
from src.virtual_sensors import generate_virtual_sensor_log


def _run_pipeline(duration_s=200, temp_rise_rate=6.0, mmwave_profile=None):
    kwargs = dict(
        duration_s=duration_s,
        guardian_departure_time_s=5,
        initial_temp_c=28.0,
        outside_temp_c=40.0,
        temp_rise_rate_c_per_min=temp_rise_rate,
        mmwave_mode="normal",
    )
    if mmwave_profile is not None:
        kwargs["mmwave_profile"] = mmwave_profile
    scenario = ScenarioConfig(**kwargs)
    hw = generate_dummy_hardware_log(scenario)
    # PIR/카메라/mmWave가 SafeGuard 흐름을 확실히 통과하도록 강제 오버라이드.
    hw.loc[hw["time_s"] >= 10, "pir_val"] = 1
    vs = generate_virtual_sensor_log(scenario)
    sim_df = build_simulation_frame(hw, vs)
    state_df, event_log = run_state_machine(sim_df)
    return sim_df, state_df


def test_build_all_on_activation_all_devices_on():
    sim_df, state_df = _run_pipeline()
    out = build_all_on_activation(state_df)
    device_cols = [c for c in out.columns if c not in ("time_s", "state")]
    for col in device_cols:
        if col == "raspberry_pi_idle":
            assert (out[col] == 0).all()
        else:
            assert (out[col] == 1).all()


def test_build_pibase_activation_never_uses_uwb_mmwave_or_motor():
    sim_df, state_df = _run_pipeline()
    out = build_pibase_activation(sim_df)
    assert (out["virtual_uwb"] == 0).all()
    assert (out["virtual_mmwave"] == 0).all()
    assert (out["dc_motor"] == 0).all()
    assert (out["pir"] == 1).all()
    assert (out["camera"] == 1).all()


def test_build_staged_activation_segments_are_exclusive():
    sim_df, state_df = _run_pipeline()
    out = build_staged_activation(sim_df, "duty_cycle")
    # UWB 활성 구간과 mmWave 활성 구간은 서로 겹치지 않아야 한다 (고정 순차 스케줄).
    overlap = ((out["virtual_uwb"] == 1) & (out["virtual_mmwave"] == 1)).sum()
    assert overlap == 0


def test_run_all_model_comparisons_allon_has_zero_savings_and_is_upper_bound():
    sim_df, state_df = _run_pipeline()
    power_df_by_model, summary = run_all_model_comparisons(sim_df, state_df, "duty_cycle")

    allon_row = summary[summary["model"] == MODEL_ALL_ON].iloc[0]
    assert allon_row["savings_vs_allon_pct"] == pytest.approx(0.0)

    max_energy = summary["total_energy_wh"].max()
    assert allon_row["total_energy_wh"] == pytest.approx(max_energy)


def test_safeguard_duty_cycle_saves_more_than_continuous():
    sim_df, state_df = _run_pipeline(duration_s=300, temp_rise_rate=8.0)
    _, summary = run_all_model_comparisons(sim_df, state_df, "duty_cycle")

    cont_row = summary[summary["model"] == MODEL_SAFEGUARD_CONTINUOUS].iloc[0]
    duty_row = summary[summary["model"] == MODEL_SAFEGUARD_DUTY_CYCLE].iloc[0]

    # duty-cycle은 continuous보다 에너지를 덜 쓰거나 같아야 한다 (ACTUATOR_CONTROL 진입 시).
    assert duty_row["total_energy_wh"] <= cont_row["total_energy_wh"]
    assert duty_row["savings_vs_allon_pct"] >= cont_row["savings_vs_allon_pct"]


def test_summary_table_records_selected_mmwave_profile():
    """선택한 mmWave sensor profile 이름이 비교 표에 함께 저장되어야 한다."""
    sim_df, state_df = _run_pipeline(mmwave_profile=MMWAVE_PROFILE_TI_IWR6843)
    _, summary = run_all_model_comparisons(sim_df, state_df, "duty_cycle")
    assert "mmwave_profile" in summary.columns
    assert (summary["mmwave_profile"] == MMWAVE_PROFILE_TI_IWR6843).all()
