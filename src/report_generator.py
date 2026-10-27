"""
SafeGuard TwinLab Agent - 논문용 표/그림/해석문/캡션/심사위원 피드백 생성.

이 모듈은 시뮬레이션 결과를 outputs/csv, outputs/figures, outputs/report에
저장 가능한 형태(CSV, PNG, TXT)로 변환한다. 모든 문장은 다음 표현 원칙을
따른다:
    - 센서: "output-level virtual sensor simulation" (raw signal 아님)
    - 전력: "추정 전력 모델(estimated power model)" (실측 아님)
    - 결과 서술: "추정 모델 기반", "시나리오 기반", "비교 모델 대비" 표현 사용,
      과장된 단정적 표현 지양.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 서버/헤드리스 환경에서도 그림을 렌더링할 수 있도록 설정.
import matplotlib.pyplot as plt
import pandas as pd

from src.config import (
    MMWAVE_PROFILE_DESCRIPTIONS_KR,
    MMWAVE_PROFILE_LABELS,
    MODEL_ALL_ON,
    MODEL_SAFEGUARD_CONTINUOUS,
    MODEL_SAFEGUARD_DUTY_CYCLE,
    OUTPUTS_CSV_DIR,
    OUTPUTS_FIGURES_DIR,
    OUTPUTS_REPORT_DIR,
    STATE_ORDER,
    ScenarioConfig,
)

# ---------------------------------------------------------------------------
# 저장 헬퍼
# ---------------------------------------------------------------------------


def save_table_csv(df: pd.DataFrame, filename: str) -> Path:
    """DataFrame을 outputs/csv/에 CSV로 저장한다."""
    path = OUTPUTS_CSV_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_figure(fig: plt.Figure, filename: str) -> Path:
    """matplotlib Figure를 outputs/figures/에 PNG로 저장한다."""
    path = OUTPUTS_FIGURES_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path


def save_text(text: str, filename: str) -> Path:
    """텍스트를 outputs/report/에 저장한다."""
    path = OUTPUTS_REPORT_DIR / filename
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 그림(Figure) 생성 함수 - 대시보드와 report 양쪽에서 공용으로 사용한다.
# ---------------------------------------------------------------------------


def fig_uwb_distance_timeline(sim_df: pd.DataFrame) -> plt.Figure:
    """Figure: UWB virtual distance timeline (guardian distance vs rolling mean)."""
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(sim_df["time_s"], sim_df["guardian_distance_m"], alpha=0.4, label="raw (virtual)")
    ax.plot(
        sim_df["time_s"],
        sim_df["guardian_distance_rolling_mean"],
        linewidth=2,
        label="rolling mean (window=7)",
    )
    ax.axhline(5.0, color="red", linestyle="--", linewidth=1, label="departure threshold (5m)")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("guardian distance (m)")
    ax.set_title("UWB Virtual Distance Timeline (output-level simulation)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def fig_temperature_timeline(sim_df: pd.DataFrame) -> plt.Figure:
    """Figure: DHT22 temperature timeline."""
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(sim_df["time_s"], sim_df["temp_c"], color="tab:orange")
    ax.axhline(32.0, color="red", linestyle="--", linewidth=1, label="action temp (32C)")
    ax.axhline(35.0, color="darkred", linestyle=":", linewidth=1, label="target temp (35C)")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("temperature (C)")
    ax.set_title("DHT22 Temperature Timeline")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def fig_state_timeline(state_df: pd.DataFrame) -> plt.Figure:
    """Figure: SafeGuard state timeline (categorical step plot)."""
    fig, ax = plt.subplots(figsize=(8, 3.0))
    state_index = {name: i for i, name in enumerate(STATE_ORDER)}
    y = state_df["state"].map(state_index)
    ax.step(state_df["time_s"], y, where="post")
    ax.set_yticks(list(state_index.values()))
    ax.set_yticklabels(list(state_index.keys()), fontsize=8)
    ax.set_xlabel("time (s)")
    ax.set_title("SafeGuard State Timeline")
    fig.tight_layout()
    return fig


def fig_power_timeline(power_df: pd.DataFrame) -> plt.Figure:
    """Figure: SafeGuard estimated power timeline."""
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(power_df["time_s"], power_df["power_w"], color="tab:green")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("estimated power (W)")
    ax.set_title("SafeGuard Estimated Power Timeline (power model, not measured)")
    fig.tight_layout()
    return fig


def fig_energy_by_state(energy_df: pd.DataFrame) -> plt.Figure:
    """Figure: energy by state (bar chart)."""
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(energy_df["state"], energy_df["energy_wh"], color="tab:blue")
    ax.set_ylabel("energy (Wh)")
    ax.set_title("Energy by State (estimated)")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.tight_layout()
    return fig


def fig_model_total_energy(summary_table: pd.DataFrame) -> plt.Figure:
    """Figure: model-level total energy comparison."""
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(summary_table["model"], summary_table["total_energy_wh"], color="tab:purple")
    ax.set_ylabel("total energy (Wh)")
    ax.set_title("Model-level Total Energy Comparison (estimated)")
    ax.tick_params(axis="x", rotation=20, labelsize=7)
    fig.tight_layout()
    return fig


def fig_model_avg_power(summary_table: pd.DataFrame) -> plt.Figure:
    """Figure: model-level average power comparison."""
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(summary_table["model"], summary_table["avg_power_w"], color="tab:cyan")
    ax.set_ylabel("average power (W)")
    ax.set_title("Model-level Average Power Comparison (estimated)")
    ax.tick_params(axis="x", rotation=20, labelsize=7)
    fig.tight_layout()
    return fig


def fig_savings_vs_allon(summary_table: pd.DataFrame) -> plt.Figure:
    """Figure: saving vs All-on comparison (bar chart, %)."""
    fig, ax = plt.subplots(figsize=(7, 3.5))
    plot_df = summary_table[summary_table["model"] != MODEL_ALL_ON]
    colors = ["tab:red" if v < 0 else "tab:green" for v in plot_df["savings_vs_allon_pct"]]
    ax.bar(plot_df["model"], plot_df["savings_vs_allon_pct"], color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("energy saving vs All-on (%)")
    ax.set_title("Saving vs All-on Comparison (estimated)")
    ax.tick_params(axis="x", rotation=20, labelsize=7)
    fig.tight_layout()
    return fig


def generate_all_figures(
    sim_df: pd.DataFrame,
    state_df: pd.DataFrame,
    power_df: pd.DataFrame,
    energy_df: pd.DataFrame,
    summary_table: pd.DataFrame,
) -> dict[str, Path]:
    """대시보드가 사용하는 8종 그래프를 모두 생성하여 outputs/figures/에 PNG로 저장한다.

    논문/심사용 paper-ready export 번들은 이 중 4종만 정식 산출물로
    사용한다 (`save_export_figures` 참고). 이 함수는 대시보드 전체 화면을
    그대로 파일로 남기고 싶을 때 사용하는 보조 유틸리티다.
    """
    figures = {
        "fig1_uwb_distance_timeline.png": fig_uwb_distance_timeline(sim_df),
        "fig2_temperature_timeline.png": fig_temperature_timeline(sim_df),
        "fig3_state_timeline.png": fig_state_timeline(state_df),
        "fig4_power_timeline.png": fig_power_timeline(power_df),
        "fig5_energy_by_state.png": fig_energy_by_state(energy_df),
        "fig6_model_total_energy.png": fig_model_total_energy(summary_table),
        "fig7_model_avg_power.png": fig_model_avg_power(summary_table),
        "fig8_savings_vs_allon.png": fig_savings_vs_allon(summary_table),
    }
    saved: dict[str, Path] = {}
    for filename, fig in figures.items():
        saved[filename] = save_figure(fig, filename)
        plt.close(fig)
    return saved


#: paper-ready export 번들이 생성하는 4개 공식 그림의 파일명 (요구사항 고정 목록).
EXPORT_FIGURE_FILENAMES: dict[str, str] = {
    "power_timeline": "figure_power_timeline.png",
    "energy_by_state": "figure_energy_by_state.png",
    "model_energy_comparison": "figure_model_energy_comparison.png",
    "saving_vs_all_on": "figure_saving_vs_all_on.png",
}


def save_export_figures(
    power_df: pd.DataFrame, energy_df: pd.DataFrame, summary_table: pd.DataFrame
) -> dict[str, Path]:
    """paper-ready export 번들에 포함되는 4개 공식 그림만 생성/저장한다."""
    figures = {
        EXPORT_FIGURE_FILENAMES["power_timeline"]: fig_power_timeline(power_df),
        EXPORT_FIGURE_FILENAMES["energy_by_state"]: fig_energy_by_state(energy_df),
        EXPORT_FIGURE_FILENAMES["model_energy_comparison"]: fig_model_total_energy(
            summary_table
        ),
        EXPORT_FIGURE_FILENAMES["saving_vs_all_on"]: fig_savings_vs_allon(summary_table),
    }
    saved: dict[str, Path] = {}
    for filename, fig in figures.items():
        saved[filename] = save_figure(fig, filename)
        plt.close(fig)
    return saved


# ---------------------------------------------------------------------------
# 캡션 (Figure/Table captions)
# ---------------------------------------------------------------------------


def generate_figure_captions() -> dict[str, str]:
    """paper-ready export 번들에 포함되는 4개 공식 그림의 한국어 캡션을 생성한다."""
    return {
        "figure_power_timeline.png": (
            "Figure 1. SafeGuard 추정 전력 모델(estimated power model) 기반 순간 전력 timeline. "
            "실측값이 아닌 datasheet 기반 추정치임에 유의한다."
        ),
        "figure_energy_by_state.png": (
            "Figure 2. SafeGuard state별 추정 소비 에너지 비교. 단계별 센서/액추에이터 "
            "활성화 시간의 차이가 에너지 분포에 반영된다."
        ),
        "figure_model_energy_comparison.png": (
            "Figure 3. 비교 모델(All-on, PiBase-style, Staged, SafeGuard) 간 "
            "총 추정 에너지 비교."
        ),
        "figure_saving_vs_all_on.png": (
            "Figure 4. All-on 모델 대비 각 비교 모델의 에너지 절감률(%). "
            "SafeGuard duty-cycle 정책이 continuous 정책 대비 추가 절감을 보이는지 확인한다."
        ),
    }


def generate_table_captions() -> dict[str, str]:
    """paper-ready export 번들에 포함되는 3개 표의 한국어 캡션을 생성한다."""
    return {
        "model_power_comparison.csv": (
            "Table 1. 비교 모델별 평균 전력, 최대 전력, 총 에너지, All-on 대비 절감률 "
            "(추정 전력 모델 기반, 시나리오 기반 결과)."
        ),
        "state_power_summary.csv": (
            "Table 2. SafeGuard state별 추정 소비 에너지 및 평균 전력."
        ),
        "event_log.csv": (
            "Table 3. SafeGuard event-driven state machine 전이 이력(event log)."
        ),
    }


# ---------------------------------------------------------------------------
# 논문용 한국어 결과 해석문
# ---------------------------------------------------------------------------


def generate_paper_summary_text(
    scenario: ScenarioConfig,
    summary_table: pd.DataFrame,
    event_log: list[dict],
    is_dummy_hardware: bool,
) -> str:
    """논문 결과 섹션에 바로 인용 가능한 한국어 해석문을 생성한다.

    과장된 단정적 표현 대신 "추정 모델 기반", "시나리오 기반", "비교 모델 대비"
    표현을 사용하여 결과의 성격을 명확히 한다.
    """
    allon_row = summary_table[summary_table["model"] == MODEL_ALL_ON].iloc[0]
    cont_row = summary_table[summary_table["model"] == MODEL_SAFEGUARD_CONTINUOUS].iloc[0]
    duty_row = summary_table[summary_table["model"] == MODEL_SAFEGUARD_DUTY_CYCLE].iloc[0]

    departure_events = [e for e in event_log if e["to_state"] == "PIR_CAMERA_CHECK"]
    confirm_events = [e for e in event_log if e["to_state"] == "THERMAL_PREDICTION"]
    failsafe_events = [e for e in event_log if e["to_state"] == "FAIL_SAFE"]
    actuator_events = [e for e in event_log if e["to_state"] == "ACTUATOR_CONTROL"]

    data_source_note = (
        "dummy(합성) hardware log"
        if is_dummy_hardware
        else "업로드된 실측 hardware_log.csv"
    )

    lines = [
        "[SafeGuard TwinLab Agent - 논문용 결과 해석문 (자동 생성, 초안)]",
        "",
        "0) Evidence / 데이터 출처 (대시보드 Evidence Panel과 동일 정보)",
        f"- 데이터 소스: {data_source_note} 기반 시나리오 기반 시뮬레이션.",
        (
            "- 센서 유형: UWB/mmWave는 output-level virtual sensor simulation "
            "(raw RF/radar signal이 아님)."
        ),
        (
            "- 전력 유형: 모든 전력 값은 datasheet 기반 추정 전력 모델(estimated power model) "
            "(실측(measured) 아님)."
        ),
        (
            f"- mmWave 센서 프로파일: "
            f"{MMWAVE_PROFILE_LABELS.get(scenario.mmwave_profile, scenario.mmwave_profile)} "
            f"({MMWAVE_PROFILE_DESCRIPTIONS_KR.get(scenario.mmwave_profile, '')})."
        ),
        "",
        "1) 시나리오 조건",
        (
            f"- 시뮬레이션 시간: {scenario.duration_s:.0f}s, "
            f"탑승자 존재 여부: {'있음' if scenario.occupant_exists else '없음'}, "
            f"보호자 이탈 시각: {scenario.guardian_departure_time_s:.0f}s"
        ),
        (
            f"- 초기 온도: {scenario.initial_temp_c:.1f}C, 외기 온도: {scenario.outside_temp_c:.1f}C, "
            f"mmWave 모드: {scenario.mmwave_mode}, 액추에이터 정책(사용자 선택): "
            f"{scenario.actuator_policy}"
        ),
        "",
        "2) SafeGuard state machine 이벤트 요약",
    ]

    if departure_events:
        lines.append(
            f"- 보호자 이탈 판정(UWB rolling mean >= 5m, 10s 유지): "
            f"t={departure_events[0]['time_s']:.0f}s"
        )
    else:
        lines.append("- 본 시나리오 구간 내 보호자 이탈이 판정되지 않았다.")

    if confirm_events:
        lines.append(
            f"- mmWave 기반 occupant_confirmed(연속 5회 유효 판독): "
            f"t={confirm_events[0]['time_s']:.0f}s"
        )
    if actuator_events:
        lines.append(f"- ACTUATOR_CONTROL 진입: t={actuator_events[0]['time_s']:.0f}s")
    if failsafe_events:
        lines.append(
            f"- mmWave timeout으로 인해 FAIL_SAFE로 전이: "
            f"t={failsafe_events[0]['time_s']:.0f}s ({failsafe_events[0]['reason']})"
        )

    lines += [
        "",
        "3) 비교 모델 대비 전력/에너지 결과 (추정 전력 모델 기반)",
        (
            f"- All-on 모델(상한 baseline) 총 에너지: {allon_row['total_energy_wh']:.3f} Wh, "
            f"평균 전력: {allon_row['avg_power_w']:.3f} W"
        ),
        (
            f"- SafeGuard(continuous) 총 에너지: {cont_row['total_energy_wh']:.3f} Wh "
            f"(All-on 대비 {cont_row['savings_vs_allon_pct']:.1f}% 절감)"
        ),
        (
            f"- SafeGuard(duty-cycle, 개선 제어 전략) 총 에너지: {duty_row['total_energy_wh']:.3f} Wh "
            f"(All-on 대비 {duty_row['savings_vs_allon_pct']:.1f}% 절감)"
        ),
        (
            "- duty-cycle 정책은 continuous 정책과 동일한 SafeGuard cascading 흐름 위에서 "
            "액추에이터 구동 방식만 다르게 적용한 결과이며, 두 결과를 함께 제시하여 "
            "제어 전략 변경에 따른 순수한 절감 효과를 비교 모델 대비 투명하게 보여준다."
        ),
        "",
        "4) 한계 및 해석상 주의사항",
        (
            "- 본 결과는 특정 시나리오 조건 하의 시뮬레이션 기반 추정치이며, "
            "실제 하드웨어 실측 전력과는 차이가 있을 수 있다."
        ),
        (
            "- UWB/mmWave는 output-level virtual sensor simulation이므로 "
            "실제 다중경로 반사, 노이즈 특성 등 raw signal 수준의 현상은 반영하지 않는다."
        ),
        "",
        "5) 첨부 표/그림 목록",
    ]

    captions = {**generate_table_captions(), **generate_figure_captions()}
    lines += [f"- {name}: {caption}" for name, caption in captions.items()]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 한계 및 향후 개선점 (독립 문서) - release 패키지 필수 산출물
# ---------------------------------------------------------------------------


def generate_limitations_text(scenario: ScenarioConfig, is_dummy_hardware: bool) -> str:
    """논문/보고서에 그대로 첨부 가능한 한계(limitations) 및 향후 개선점 문서를 생성한다.

    `generate_paper_summary_text`의 "4) 한계 및 해석상 주의사항"보다 더 넓은
    범위(데이터, 센서, 전력, 재현성, 향후 개선점)를 독립 문서로 정리한다.
    """
    data_note = (
        "이번 실행은 dummy(합성) hardware log를 사용했다. 실제 하드웨어 검증 이전 단계의 결과다."
        if is_dummy_hardware
        else "이번 실행은 업로드된 실측 hardware_log.csv를 사용했으나, UWB/mmWave/전력은 "
        "여전히 시나리오 기반 가상 센서/추정 모델이다."
    )

    lines = [
        "[SafeGuard TwinLab Agent - 한계 및 향후 개선점 (자동 생성)]",
        "",
        "1) 데이터 관련 한계",
        f"- {data_note}",
        (
            f"- 본 시나리오는 duration={scenario.duration_s:.0f}s, "
            f"guardian_departure_time_s={scenario.guardian_departure_time_s:.0f}s 등 "
            "특정 파라미터 조합에서의 결과이며, 모든 실제 상황을 대표하지 않는다."
        ),
        "",
        "2) 센서 관련 한계",
        (
            "- UWB(DWM1001-DEV 등가), mmWave는 raw RF/radar signal "
            "(FMCW chirp, FFT spectrum, 다중경로 반사 등)을 물리적으로 모델링하지 않는 "
            "output-level virtual sensor simulation이다."
        ),
        (
            f"- 이번 실행의 mmWave sensor profile: "
            f"{MMWAVE_PROFILE_LABELS.get(scenario.mmwave_profile, scenario.mmwave_profile)} "
            f"({MMWAVE_PROFILE_DESCRIPTIONS_KR.get(scenario.mmwave_profile, '')}). "
            "profile 선택은 output field 구성과 confirmation 임계값만 바꿀 뿐, "
            "실제 해당 하드웨어를 사용하거나 raw signal processing을 수행한 것이 아니다."
        ),
        (
            "- Camera 감지 역시 OpenCV contour 연산을 직접 재현하지 않고, "
            "light_condition에 따른 detection probability로 근사한 output-level 결과다."
        ),
        "",
        "3) 전력 관련 한계",
        (
            "- 모든 전력 값은 datasheet/typical-value 기반 추정 전력 모델(estimated power "
            "model)이며 실측(measured power)이 아니다."
        ),
        (
            "- 릴레이/액추에이터의 돌입전류(inrush current), 온도에 따른 소비전력 변화 등은 "
            "반영하지 않는다."
        ),
        "",
        "4) 재현성",
        "- 모든 난수는 RANDOM_SEED(고정값)로 초기화되어 동일 입력에 대해 동일 결과를 재현한다.",
        "- 실측 검증이 필요할 경우 data_loader.load_power_measure_log()로 power_measure_log.csv를 "
        "불러와 추정 모델과 교차 비교할 수 있는 경로가 이미 마련되어 있다.",
        "",
        "5) 향후 개선점",
        "- 실제 INA219/INA226 등 전류 센서를 이용한 estimated vs measured 오차율 정량화.",
        "- UWB/mmWave 실제 모듈의 raw signal 기반 재현 및 output-level 시뮬레이션과의 상관관계 검증.",
        "- 다양한 차량/센서 배치, 계절/외기온 조건에 대한 민감도 분석 확장.",
        "- 실차 환경에서의 장기 운용 데이터 수집을 통한 FAIL_SAFE 오탐/미탐률 정량 평가.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Judge Mode (심사위원 관점 피드백) - killer feature #4
# ---------------------------------------------------------------------------


def generate_judge_mode_feedback(
    scenario: ScenarioConfig,
    summary_table: pd.DataFrame,
    is_dummy_hardware: bool,
) -> str:
    """심사위원 관점에서 결과의 약점, 반박 문장, 추가 실험 제안, 데모 포인트를 생성한다."""
    duty_row = summary_table[summary_table["model"] == MODEL_SAFEGUARD_DUTY_CYCLE].iloc[0]

    weaknesses = [
        "전력 값이 실측이 아닌 추정 모델(datasheet 기반)이므로 실제 소비전력과 오차가 있을 수 있다.",
        "UWB/mmWave가 raw signal이 아닌 output-level virtual sensor simulation이라 "
        "실환경 노이즈/다중경로 반사에 대한 강건성은 검증되지 않았다.",
    ]
    if is_dummy_hardware:
        weaknesses.append(
            "이번 실행은 실제 hardware_log.csv가 아닌 dummy(합성) 데이터를 사용했으므로 "
            "실측 검증 이전 단계의 결과임을 명확히 해야 한다."
        )
    if duty_row["savings_vs_allon_pct"] > 90:
        weaknesses.append(
            f"All-on 대비 절감률({duty_row['savings_vs_allon_pct']:.1f}%)이 매우 높게 나타나 "
            "비교 baseline(All-on) 설정이 과도하게 불리하게 잡힌 것 아니냐는 지적이 나올 수 있다."
        )

    rebuttals = [
        "All-on은 실제 현장에서도 흔히 채택되는 '단순 상시 감시' 방식이며, "
        "SafeGuard는 이와 동일 센서/액추에이터 구성을 공유하므로 공정한 상한 baseline이다.",
        "power_measure_log.csv를 통해 실측 전력과 추정 모델을 교차 검증하는 절차를 "
        "시스템에 이미 마련해 두었다 (data_loader.load_power_measure_log).",
        "continuous와 duty-cycle 결과를 항상 함께 제시하여, 절감 효과가 특정 정책에 "
        "유리하게 편집된 것이 아님을 투명하게 보여준다.",
    ]

    further_experiments = [
        "실제 Raspberry Pi + INA219/INA226 등 전류 센서를 이용한 실측 전력 로그 확보 및 "
        "estimated vs measured 오차율 정량 분석.",
        "mmWave/UWB 실제 모듈을 이용한 raw signal 기반 재현으로 output-level 시뮬레이션과의 "
        "일치도(correlation) 검증.",
        "다양한 guardian_departure_time_s, 온도 상승률 시나리오에 대한 민감도 분석(sensitivity analysis).",
    ]

    demo_points = [
        "Failure Scenario Simulation 버튼으로 mmWave timeout, PIR false positive 등 "
        "edge case에서도 FAIL_SAFE가 정상 동작함을 실시간으로 시연한다.",
        "Continuous vs Duty-cycle 토글을 눈앞에서 전환하여 전력 timeline이 즉시 재계산되는 것을 보여준다.",
        "Judge Mode 자체가 '스스로 약점을 인지하고 방어 논리를 준비한 시스템'이라는 인상을 준다.",
    ]

    lines = [
        "[Judge Mode - 심사위원 관점 자동 피드백 (초안)]",
        "",
        "1) 이 결과의 약점",
        *[f"- {w}" for w in weaknesses],
        "",
        "2) 예상 반박 및 대응 논리",
        *[f"- {r}" for r in rebuttals],
        "",
        "3) 추가 실험 제안",
        *[f"- {e}" for e in further_experiments],
        "",
        "4) 데모 때 강조할 포인트",
        *[f"- {d}" for d in demo_points],
    ]
    return "\n".join(lines)


def generate_judge_qna_text(
    scenario: ScenarioConfig,
    summary_table: pd.DataFrame,
    is_dummy_hardware: bool,
) -> str:
    """심사위원이 실제로 물어볼 법한 질문과 준비된 답변을 Q&A 형식으로 생성한다.

    `generate_judge_mode_feedback`(약점/반박/추가실험/데모포인트 4분류)과
    상호보완적인, 발표 직전 예상 질의응답 리허설용 문서다.
    """
    duty_row = summary_table[summary_table["model"] == MODEL_SAFEGUARD_DUTY_CYCLE].iloc[0]
    cont_row = summary_table[summary_table["model"] == MODEL_SAFEGUARD_CONTINUOUS].iloc[0]
    allon_row = summary_table[summary_table["model"] == MODEL_ALL_ON].iloc[0]

    data_source_answer = (
        "이번 실행은 dummy(합성) hardware log입니다. seed가 고정되어 있어 재현 가능하며, "
        "실제 hardware_log.csv를 업로드하면 동일 파이프라인으로 즉시 재계산됩니다."
        if is_dummy_hardware
        else "이번 실행은 업로드된 실측 hardware_log.csv를 사용했습니다. "
        "다만 UWB/mmWave와 전력은 여전히 가상 센서/추정 모델입니다."
    )

    qna = [
        (
            "이 전력 값은 실제로 측정한 건가요?",
            "아니요. datasheet 기반 추정 전력 모델(estimated power model)입니다. "
            "실측이 필요하면 power_measure_log.csv를 업로드해 교차 검증할 수 있는 "
            "경로를 이미 구현해 두었습니다.",
        ),
        (
            "UWB/mmWave가 실제 센서 신호인가요?",
            "아니요. raw RF/radar signal이 아닌 output-level virtual sensor simulation입니다. "
            "presence, distance, velocity 같은 최종 출력값만 시나리오 조건에 따라 합성합니다.",
        ),
        (
            "TI IWR6843ISK 같은 실제 하드웨어를 사용하신 건가요?",
            f"아니요. 이번 실행은 {MMWAVE_PROFILE_LABELS.get(scenario.mmwave_profile, scenario.mmwave_profile)}"
            f"({MMWAVE_PROFILE_DESCRIPTIONS_KR.get(scenario.mmwave_profile, '')})입니다. "
            "해당 모듈이 보고하는 output field 구성과 confirmation 임계값만 참고한 것이며, "
            "실제 하드웨어나 raw signal processing을 사용한 것이 아닙니다.",
        ),
        (
            "지금 보여주는 데이터가 dummy인가요, 실제인가요?",
            data_source_answer,
        ),
        (
            "All-on 모델과 비교하는 게 SafeGuard에 유리하게 편향된 것 아닌가요?",
            "All-on은 SafeGuard와 동일한 센서/액추에이터 구성을 상시 가동하는 방식으로, "
            "현장에서도 흔히 채택되는 '단순 상시 감시' 방식입니다. 공정한 상한(upper bound) "
            f"baseline이며 이번 시나리오에서 총 에너지는 {allon_row['total_energy_wh']:.3f} Wh입니다.",
        ),
        (
            "duty-cycle이 실제로 얼마나 절감되나요?",
            f"이번 시나리오 기준 SafeGuard(continuous)는 All-on 대비 "
            f"{cont_row['savings_vs_allon_pct']:.1f}%, SafeGuard(duty-cycle)는 "
            f"{duty_row['savings_vs_allon_pct']:.1f}% 절감됩니다. 두 결과를 항상 함께 "
            "제시하여 정책 변경에 따른 순수한 절감 효과를 투명하게 보여줍니다.",
        ),
        (
            "이 결과가 재현 가능한가요?",
            "예. src/config.py의 RANDOM_SEED로 모든 난수를 고정하며, 동일 시나리오 "
            "조건이면 항상 동일한 이벤트 로그와 전력 timeline이 생성됩니다. "
            "tests/ 이하 pytest로 상태 전이와 전력 계산을 자동 검증합니다.",
        ),
    ]

    lines = ["[SafeGuard TwinLab Agent - 심사위원 예상 Q&A (자동 생성)]", ""]
    for i, (q, a) in enumerate(qna, start=1):
        lines.append(f"Q{i}. {q}")
        lines.append(f"A{i}. {a}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Paper-ready 자동 생성 번들 - killer feature #3
# ---------------------------------------------------------------------------


#: paper-ready export 번들이 생성해야 하는 필수 산출물 파일명 (release 요구사항 고정 목록).
REQUIRED_EXPORT_FILENAMES: list[str] = [
    "model_power_comparison.csv",
    "state_power_summary.csv",
    "event_log.csv",
    "figure_power_timeline.png",
    "figure_energy_by_state.png",
    "figure_model_energy_comparison.png",
    "figure_saving_vs_all_on.png",
    "paper_result_summary_kr.txt",
    "figure_captions_kr.txt",
    "limitations_kr.txt",
    "judge_qna_kr.txt",
]


def generate_paper_ready_bundle(
    sim_df: pd.DataFrame,
    state_df: pd.DataFrame,
    power_df: pd.DataFrame,
    energy_df: pd.DataFrame,
    summary_table: pd.DataFrame,
    event_log: list[dict],
    scenario: ScenarioConfig,
    is_dummy_hardware: bool,
) -> dict[str, Path]:
    """paper-ready export 번들(표 CSV + 그림 PNG + 해석문/캡션/한계/Q&A TXT)을 생성한다.

    생성되는 파일은 REQUIRED_EXPORT_FILENAMES에 정의된 11개 파일이며, 심사용
    release 패키지에 그대로 첨부할 수 있는 형태다. 대시보드의 "Paper-ready
    자동 생성" 버튼과 scripts/generate_paper_outputs.py가 이 함수를 공유한다.
    """
    from src.state_machine import event_log_to_dataframe  # 지연 import로 순환참조 방지

    saved: dict[str, Path] = {}

    saved["model_power_comparison.csv"] = save_table_csv(
        summary_table, "model_power_comparison.csv"
    )
    saved["state_power_summary.csv"] = save_table_csv(energy_df, "state_power_summary.csv")
    saved["event_log.csv"] = save_table_csv(
        event_log_to_dataframe(event_log), "event_log.csv"
    )

    saved.update(save_export_figures(power_df, energy_df, summary_table))

    summary_text = generate_paper_summary_text(
        scenario, summary_table, event_log, is_dummy_hardware
    )
    saved["paper_result_summary_kr.txt"] = save_text(
        summary_text, "paper_result_summary_kr.txt"
    )

    caption_text = "\n\n".join(
        f"[{k}]\n{v}" for k, v in generate_figure_captions().items()
    )
    saved["figure_captions_kr.txt"] = save_text(caption_text, "figure_captions_kr.txt")

    limitations_text = generate_limitations_text(scenario, is_dummy_hardware)
    saved["limitations_kr.txt"] = save_text(limitations_text, "limitations_kr.txt")

    judge_qna_text = generate_judge_qna_text(scenario, summary_table, is_dummy_hardware)
    saved["judge_qna_kr.txt"] = save_text(judge_qna_text, "judge_qna_kr.txt")

    assert set(REQUIRED_EXPORT_FILENAMES).issubset(saved.keys()), (
        "generate_paper_ready_bundle이 REQUIRED_EXPORT_FILENAMES를 모두 생성하지 않았습니다."
    )

    manifest = "\n".join(f"{name}: {path}" for name, path in saved.items())
    saved["export_manifest.txt"] = save_text(
        f"Generated at {datetime.now().isoformat()}\n\n{manifest}", "export_manifest.txt"
    )
    return saved
