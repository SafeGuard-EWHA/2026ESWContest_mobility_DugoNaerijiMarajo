"""
SafeGuard TwinLab Agent - end-to-end 파이프라인 오케스트레이션.

hardware log 로딩(또는 dummy 생성) -> virtual sensor 생성 -> state machine
실행 -> device activation -> power/energy 계산 -> model comparison까지
전체 core simulation engine을 한 번에 실행한다.

`app/streamlit_app.py`(대시보드, st.cache_data로 래핑)와
`scripts/generate_paper_outputs.py`(CLI)가 이 함수를 공유하여 두 실행
경로의 결과가 항상 동일하도록 보장한다.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import IO

from src.config import ScenarioConfig
from src.data_loader import generate_dummy_hardware_log, load_hardware_log
from src.device_activation import compute_device_activation
from src.model_comparison import run_all_model_comparisons
from src.power_model import compute_energy_by_state, compute_power_timeline
from src.state_machine import build_simulation_frame, run_state_machine
from src.virtual_sensors import generate_virtual_sensor_log


def run_full_pipeline(
    scenario: ScenarioConfig, hardware_source: str | Path | IO[bytes] | None = None
) -> dict:
    """core simulation engine 전체를 실행하고 모든 산출물을 dict로 반환한다.

    Args:
        scenario: 시나리오 설정 (dummy 생성 시 사용, 실제 CSV 사용 시에도
            occupant_exists/mmwave_mode 등 virtual sensor 파라미터로 쓰인다).
        hardware_source: 실제 hardware_log.csv 경로 또는 file-like 객체.
            None이면 scenario 기반 dummy hardware log를 생성한다.

    Returns:
        scenario(정렬됨), is_dummy, hw_df, sim_df, state_df, event_log,
        power_df, energy_df, power_by_model, summary_table을 담은 dict.
    """
    if hardware_source is not None:
        hw_df = load_hardware_log(hardware_source)
        is_dummy = False
        # 실제 로그의 길이에 맞춰 virtual sensor(UWB/mmWave/Camera) 시간축을 정렬한다.
        aligned_scenario = ScenarioConfig(
            **{**asdict(scenario), "duration_s": float(hw_df["time_s"].max())}
        )
    else:
        hw_df = generate_dummy_hardware_log(scenario)
        is_dummy = True
        aligned_scenario = scenario

    vs_df = generate_virtual_sensor_log(aligned_scenario)
    sim_df = build_simulation_frame(hw_df, vs_df)
    state_df, event_log = run_state_machine(sim_df)

    activation_df = compute_device_activation(state_df, aligned_scenario.actuator_policy)
    power_df = compute_power_timeline(activation_df)
    energy_df = compute_energy_by_state(power_df)

    power_by_model, summary_table = run_all_model_comparisons(
        sim_df, state_df, aligned_scenario.actuator_policy
    )

    return {
        "scenario": aligned_scenario,
        "is_dummy": is_dummy,
        "hw_df": hw_df,
        "sim_df": sim_df,
        "state_df": state_df,
        "event_log": event_log,
        "power_df": power_df,
        "energy_df": energy_df,
        "power_by_model": power_by_model,
        "summary_table": summary_table,
    }
