"""src/report_generator.py 에 대한 단위 테스트."""

from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from src.config import MMWAVE_PROFILE_C4001, MMWAVE_PROFILE_TI_IWR6843, ScenarioConfig
from src.data_loader import generate_dummy_hardware_log
from src.device_activation import compute_device_activation
from src.model_comparison import run_all_model_comparisons
from src.power_model import compute_energy_by_state, compute_power_timeline
from src.report_generator import (
    REQUIRED_EXPORT_FILENAMES,
    generate_all_figures,
    generate_figure_captions,
    generate_judge_mode_feedback,
    generate_judge_qna_text,
    generate_limitations_text,
    generate_paper_ready_bundle,
    generate_paper_summary_text,
    generate_table_captions,
    save_export_figures,
)
from src.state_machine import build_simulation_frame, run_state_machine
from src.virtual_sensors import generate_virtual_sensor_log


@pytest.fixture(scope="module")
def pipeline_result():
    scenario = ScenarioConfig(
        duration_s=200,
        guardian_departure_time_s=5,
        initial_temp_c=28.0,
        outside_temp_c=40.0,
        temp_rise_rate_c_per_min=6.0,
        mmwave_mode="normal",
    )
    hw = generate_dummy_hardware_log(scenario)
    hw.loc[hw["time_s"] >= 10, "pir_val"] = 1
    vs = generate_virtual_sensor_log(scenario)
    sim_df = build_simulation_frame(hw, vs)
    state_df, event_log = run_state_machine(sim_df)
    activation_df = compute_device_activation(state_df, "duty_cycle")
    power_df = compute_power_timeline(activation_df)
    energy_df = compute_energy_by_state(power_df)
    _, summary_table = run_all_model_comparisons(sim_df, state_df, "duty_cycle")
    return {
        "scenario": scenario,
        "sim_df": sim_df,
        "state_df": state_df,
        "power_df": power_df,
        "energy_df": energy_df,
        "summary_table": summary_table,
        "event_log": event_log,
    }


def test_generate_all_figures_creates_8_png_files(pipeline_result):
    r = pipeline_result
    saved = generate_all_figures(
        r["sim_df"], r["state_df"], r["power_df"], r["energy_df"], r["summary_table"]
    )
    assert len(saved) == 8
    for path in saved.values():
        assert Path(path).exists()
        assert Path(path).suffix == ".png"


def test_paper_summary_text_contains_required_disclaimers(pipeline_result):
    r = pipeline_result
    text = generate_paper_summary_text(
        r["scenario"], r["summary_table"], r["event_log"], is_dummy_hardware=True
    )
    assert "추정" in text
    assert "output-level virtual sensor simulation" in text
    assert "시나리오" in text


def test_paper_summary_text_states_mmwave_profile_disclaimer(pipeline_result):
    r = pipeline_result

    c4001_scenario = replace(r["scenario"], mmwave_profile=MMWAVE_PROFILE_C4001)
    c4001_text = generate_paper_summary_text(
        c4001_scenario, r["summary_table"], r["event_log"], is_dummy_hardware=True
    )
    assert "low-cost 24GHz radar module profile 기반 output-level virtual sensor simulation" in c4001_text

    ti_scenario = replace(r["scenario"], mmwave_profile=MMWAVE_PROFILE_TI_IWR6843)
    ti_text = generate_paper_summary_text(
        ti_scenario, r["summary_table"], r["event_log"], is_dummy_hardware=True
    )
    assert "TI IWR6843ISK reference profile 기반 output-level virtual sensor simulation" in ti_text


def test_judge_qna_denies_real_ti_hardware_usage(pipeline_result):
    r = pipeline_result
    ti_scenario = replace(r["scenario"], mmwave_profile=MMWAVE_PROFILE_TI_IWR6843)
    text = generate_judge_qna_text(ti_scenario, r["summary_table"], is_dummy_hardware=True)
    assert "TI IWR6843ISK reference profile 기반 output-level virtual sensor simulation" in text
    assert "실제 하드웨어나 raw signal processing을 사용한 것이 아닙니다" in text


def test_judge_mode_feedback_has_four_sections(pipeline_result):
    r = pipeline_result
    text = generate_judge_mode_feedback(
        r["scenario"], r["summary_table"], is_dummy_hardware=True
    )
    assert "이 결과의 약점" in text
    assert "예상 반박" in text
    assert "추가 실험 제안" in text
    assert "데모 때 강조할 포인트" in text


def test_captions_cover_export_figures_and_tables():
    fig_captions = generate_figure_captions()
    table_captions = generate_table_captions()
    assert len(fig_captions) == 4
    assert set(fig_captions.keys()) == {
        "figure_power_timeline.png",
        "figure_energy_by_state.png",
        "figure_model_energy_comparison.png",
        "figure_saving_vs_all_on.png",
    }
    assert "model_power_comparison.csv" in table_captions
    assert "state_power_summary.csv" in table_captions


def test_save_export_figures_creates_4_png_files(pipeline_result):
    r = pipeline_result
    saved = save_export_figures(r["power_df"], r["energy_df"], r["summary_table"])
    assert len(saved) == 4
    for path in saved.values():
        assert Path(path).exists()
        assert Path(path).suffix == ".png"


def test_limitations_text_contains_required_disclaimers(pipeline_result):
    r = pipeline_result
    text = generate_limitations_text(r["scenario"], is_dummy_hardware=True)
    assert "추정 전력 모델" in text
    assert "output-level virtual sensor simulation" in text
    assert "향후 개선점" in text


def test_judge_qna_text_has_numbered_qa_pairs(pipeline_result):
    r = pipeline_result
    text = generate_judge_qna_text(r["scenario"], r["summary_table"], is_dummy_hardware=True)
    assert "Q1." in text
    assert "A1." in text
    assert "Q6." in text
    assert "A6." in text


def test_generate_paper_ready_bundle_creates_all_required_files(pipeline_result):
    r = pipeline_result
    saved = generate_paper_ready_bundle(
        r["sim_df"],
        r["state_df"],
        r["power_df"],
        r["energy_df"],
        r["summary_table"],
        r["event_log"],
        r["scenario"],
        is_dummy_hardware=True,
    )
    assert set(REQUIRED_EXPORT_FILENAMES).issubset(saved.keys())
    for path in saved.values():
        assert Path(path).exists()
