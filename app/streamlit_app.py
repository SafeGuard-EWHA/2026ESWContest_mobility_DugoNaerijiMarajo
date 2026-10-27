"""
SafeGuard TwinLab Agent - Streamlit interactive dashboard.

사용자가 사이드바에서 시나리오 조건을 바꾸면 core simulation engine
(src/ 이하 모듈)이 다시 실행되어 모든 그래프/표/해석문이 재계산된다.

주의: 이 대시보드가 보여주는 UWB/mmWave 값은 output-level virtual sensor
simulation이며, 전력 값은 실측이 아닌 추정 전력 모델(estimated power
model)이다. 모든 결과는 시나리오 기반 추정치로 해석해야 한다.
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

# app/ 밖의 src 패키지를 import할 수 있도록 프로젝트 루트를 sys.path에 추가한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from src.config import (
    DEMO_SCENARIOS,
    MMWAVE_MODES,
    MMWAVE_PROFILE_LABELS,
    MMWAVE_PROFILES,
    MODEL_ALL_ON,
    RANDOM_SEED,
    SAMPLE_DATA_DIR,
    ScenarioConfig,
)
from src.pipeline import run_full_pipeline as _run_full_pipeline
from src.report_generator import (
    fig_energy_by_state,
    fig_model_avg_power,
    fig_model_total_energy,
    fig_power_timeline,
    fig_savings_vs_allon,
    fig_state_timeline,
    fig_temperature_timeline,
    fig_uwb_distance_timeline,
    generate_judge_mode_feedback,
    generate_judge_qna_text,
    generate_paper_ready_bundle,
    generate_paper_summary_text,
)
from src.state_machine import event_log_to_dataframe

st.set_page_config(page_title="SafeGuard TwinLab Agent", layout="wide")

_DEFAULTS = ScenarioConfig()


def _init_session_state() -> None:
    """시나리오 관련 session_state 기본값을 최초 1회 초기화한다."""
    defaults = {
        "duration_s": _DEFAULTS.duration_s,
        "occupant_exists": _DEFAULTS.occupant_exists,
        "guardian_departure_time_s": _DEFAULTS.guardian_departure_time_s,
        "initial_temp_c": _DEFAULTS.initial_temp_c,
        "outside_temp_c": _DEFAULTS.outside_temp_c,
        "humidity_pct": _DEFAULTS.humidity_pct,
        "temp_rise_rate_c_per_min": _DEFAULTS.temp_rise_rate_c_per_min,
        "light_condition": _DEFAULTS.light_condition,
        "motion_state": _DEFAULTS.motion_state,
        "mmwave_mode": _DEFAULTS.mmwave_mode,
        "mmwave_profile": _DEFAULTS.mmwave_profile,
        "actuator_policy": _DEFAULTS.actuator_policy,
        "pir_false_positive": _DEFAULTS.pir_false_positive,
        "dht22_failure": _DEFAULTS.dht22_failure,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


@st.cache_data(show_spinner="시뮬레이션 파이프라인 실행 중...")
def run_full_pipeline(scenario: ScenarioConfig, uploaded_csv_bytes: bytes | None):
    """core simulation engine 전체를 실행하고 대시보드에 필요한 모든 산출물을 반환한다.

    scenario 또는 uploaded_csv_bytes가 바뀌면 Streamlit이 자동으로 캐시를
    무효화하고 재계산한다 (요구사항: "시나리오 조건을 바꾸면 결과가 다시 계산").
    실제 계산 로직은 src.pipeline.run_full_pipeline에 있으며,
    scripts/generate_paper_outputs.py와 동일한 함수를 공유한다.
    """
    hardware_source = BytesIO(uploaded_csv_bytes) if uploaded_csv_bytes is not None else None
    return _run_full_pipeline(scenario, hardware_source)


def _render_sidebar() -> tuple[ScenarioConfig, bytes | None]:
    """사이드바 UI를 렌더링하고 (ScenarioConfig, 업로드된 CSV bytes)를 반환한다."""
    st.sidebar.title("SafeGuard TwinLab Agent")
    st.sidebar.caption("차량 내 잔류 탑승자 보호 시스템 - 시나리오 입력")

    st.sidebar.subheader("Demo Mode")
    st.sidebar.caption("버튼 클릭 시 완결된 시나리오 프리셋이 한 번에 적용됩니다 (발표/시연용).")
    for demo_name, preset in DEMO_SCENARIOS.items():
        if st.sidebar.button(demo_name, key=f"demo_{demo_name}"):
            preset_values = asdict(preset)
            preset_values.pop("seed", None)
            for field_name, field_value in preset_values.items():
                st.session_state[field_name] = field_value
    st.sidebar.markdown("---")

    st.sidebar.subheader("Failure Scenario Simulation")
    st.sidebar.caption("버튼 클릭 시 아래 파라미터가 해당 edge case로 자동 설정됩니다.")
    fc1, fc2 = st.sidebar.columns(2)
    if fc1.button("mmWave timeout"):
        st.session_state["mmwave_mode"] = "timeout"
    if fc2.button("PIR false positive"):
        st.session_state["pir_false_positive"] = True
        st.session_state["occupant_exists"] = False
    if fc1.button("Camera dark"):
        st.session_state["light_condition"] = "dark"
    if fc2.button("DHT22 fail"):
        st.session_state["dht22_failure"] = True
    if fc1.button("No occupant"):
        st.session_state["occupant_exists"] = False
        st.session_state["mmwave_mode"] = "no_occupant"
    if fc2.button("Guardian nearby"):
        st.session_state["guardian_departure_time_s"] = 1_000_000.0
    if st.sidebar.button("시나리오 초기화 (defaults)"):
        for key in (
            "occupant_exists",
            "guardian_departure_time_s",
            "light_condition",
            "mmwave_mode",
            "mmwave_profile",
            "pir_false_positive",
            "dht22_failure",
        ):
            st.session_state[key] = getattr(_DEFAULTS, key)

    st.sidebar.markdown("---")
    st.sidebar.subheader("시나리오 파라미터")

    st.sidebar.number_input(
        "Simulation duration (s)", min_value=30.0, max_value=3600.0, step=30.0, key="duration_s"
    )
    st.sidebar.checkbox("Occupant exists", key="occupant_exists")
    st.sidebar.number_input(
        "Guardian departure time (s)",
        min_value=0.0,
        max_value=1_000_000.0,
        step=1.0,
        key="guardian_departure_time_s",
    )
    st.sidebar.number_input(
        "Initial temp (C)", min_value=-10.0, max_value=60.0, step=0.5, key="initial_temp_c"
    )
    st.sidebar.number_input(
        "Outside temp (C)", min_value=-10.0, max_value=70.0, step=0.5, key="outside_temp_c"
    )
    st.sidebar.slider("Humidity (%)", min_value=0.0, max_value=100.0, key="humidity_pct")
    st.sidebar.number_input(
        "Temp rise speed (C/min)",
        min_value=0.0,
        max_value=20.0,
        step=0.1,
        key="temp_rise_rate_c_per_min",
    )
    st.sidebar.selectbox("Light condition", options=["bright", "dim", "dark"], key="light_condition")
    st.sidebar.selectbox("Motion state", options=["still", "moving"], key="motion_state")
    st.sidebar.selectbox("mmWave mode", options=MMWAVE_MODES, key="mmwave_mode")
    st.sidebar.selectbox(
        "mmWave Sensor Profile",
        options=MMWAVE_PROFILES,
        format_func=lambda p: MMWAVE_PROFILE_LABELS.get(p, p),
        key="mmwave_profile",
    )
    st.sidebar.caption(
        "두 profile 모두 output-level virtual sensor simulation입니다 "
        "(raw radar signal 재현 아님)."
    )
    st.sidebar.radio(
        "Actuator policy (SafeGuard 대표 timeline)",
        options=["continuous", "duty_cycle"],
        key="actuator_policy",
        horizontal=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("hardware_log.csv")
    st.sidebar.caption(
        "업로드 없이도 dummy 데이터로 바로 실행됩니다. "
        "sample_data/의 예시 CSV를 선택하면 파일 업로드 없이 실제 로그 형태의 "
        "결과를 즉시 볼 수 있습니다 (익명 방문자용 데모 경로)."
    )
    sample_files = (
        sorted(p.name for p in SAMPLE_DATA_DIR.glob("*.csv")) if SAMPLE_DATA_DIR.exists() else []
    )
    no_sample_option = "(dummy 데이터 사용 - 선택 안 함)"
    sample_choice = st.sidebar.selectbox(
        "샘플 hardware_log.csv 선택",
        options=[no_sample_option, *sample_files],
        index=0,
        key="sample_hardware_choice",
    )
    uploaded_file = st.sidebar.file_uploader(
        "또는 직접 hardware_log.csv 업로드 (선택 시 샘플보다 우선 적용)", type=["csv"]
    )

    scenario = ScenarioConfig(
        duration_s=float(st.session_state["duration_s"]),
        occupant_exists=bool(st.session_state["occupant_exists"]),
        guardian_departure_time_s=float(st.session_state["guardian_departure_time_s"]),
        initial_temp_c=float(st.session_state["initial_temp_c"]),
        outside_temp_c=float(st.session_state["outside_temp_c"]),
        humidity_pct=float(st.session_state["humidity_pct"]),
        temp_rise_rate_c_per_min=float(st.session_state["temp_rise_rate_c_per_min"]),
        light_condition=st.session_state["light_condition"],
        motion_state=st.session_state["motion_state"],
        mmwave_mode=st.session_state["mmwave_mode"],
        mmwave_profile=st.session_state["mmwave_profile"],
        actuator_policy=st.session_state["actuator_policy"],
        pir_false_positive=bool(st.session_state["pir_false_positive"]),
        dht22_failure=bool(st.session_state["dht22_failure"]),
        seed=RANDOM_SEED,
    )
    if uploaded_file is not None:
        # 사용자가 직접 업로드한 파일이 sample_data 선택보다 항상 우선한다.
        hardware_bytes = uploaded_file.getvalue()
    elif sample_choice != no_sample_option:
        hardware_bytes = (SAMPLE_DATA_DIR / sample_choice).read_bytes()
    else:
        hardware_bytes = None
    return scenario, hardware_bytes


def main() -> None:
    """대시보드 전체를 렌더링하는 진입점."""
    _init_session_state()
    scenario, uploaded_bytes = _render_sidebar()

    st.title("SafeGuard TwinLab Agent")
    st.caption(
        "Raspberry Pi hardware log + UWB/mmWave virtual sensor 기반 "
        "차량 내 잔류 탑승자 보호 시스템 end-to-end simulator"
    )

    try:
        result = run_full_pipeline(scenario, uploaded_bytes)
    except Exception as exc:  # noqa: BLE001 - 대시보드 사용자에게 원인을 그대로 노출
        st.error(f"시뮬레이션 실행 중 오류가 발생했습니다: {exc}")
        st.stop()

    # ---------------------------------------------------------------- Evidence Panel
    st.subheader("Evidence Panel")
    ec1, ec2, ec3 = st.columns(3)
    ec1.metric(
        "데이터 소스",
        "Dummy (합성)" if result["is_dummy"] else "실측 CSV 업로드",
    )
    ec2.metric("UWB / mmWave", "Virtual Sensor")
    ec3.metric("Power", "Estimated (추정)")
    st.caption(
        "현재 결과가 어떤 근거로 생성되었는지 투명하게 보여주는 패널입니다. "
        "데이터 소스가 Dummy이면 재현 가능한 seed 기반 합성 데이터이고, "
        "UWB/mmWave는 항상 output-level virtual sensor simulation이며, "
        "전력은 항상 datasheet 기반 추정 전력 모델입니다 (실측 아님). "
        "이 정보는 8번 섹션의 결과 해석문 0)항목에도 동일하게 반영됩니다."
    )

    # ---------------------------------------------------------------- 1
    st.subheader("1. Scenario Summary")
    if result["is_dummy"]:
        st.info(
            "hardware_log.csv가 업로드되지 않아 dummy(합성) hardware log를 사용 중입니다. "
            "(재현 가능한 seed 기반 합성 데이터, 실측 아님)"
        )
    else:
        st.success("업로드된 hardware_log.csv를 사용 중입니다.")
    scenario_df = pd.DataFrame([asdict(result["scenario"])])
    st.dataframe(scenario_df, width='stretch')

    # ---------------------------------------------------------------- 2
    st.subheader("2. State Machine Event Log")
    st.dataframe(event_log_to_dataframe(result["event_log"]), width='stretch')

    # ---------------------------------------------------------------- 3
    st.subheader("3. Sensor Timeline")
    c1, c2 = st.columns(2)
    with c1:
        st.pyplot(fig_uwb_distance_timeline(result["sim_df"]), clear_figure=True)
        st.caption("UWB virtual distance timeline (output-level virtual sensor simulation)")
    with c2:
        st.pyplot(fig_temperature_timeline(result["sim_df"]), clear_figure=True)
        st.caption("DHT22 temperature timeline")

    # ---------------------------------------------------------------- 4
    st.subheader("4. State Timeline")
    st.pyplot(fig_state_timeline(result["state_df"]), clear_figure=True)

    # ---------------------------------------------------------------- 5
    st.subheader("5. Power Timeline")
    st.pyplot(fig_power_timeline(result["power_df"]), clear_figure=True)
    st.caption(
        f"현재 선택된 정책: **{result['scenario'].actuator_policy}** "
        "(estimated power model 기준, 실측 아님). "
        "continuous/duty-cycle 비교는 아래 7번 섹션에서 항상 함께 확인할 수 있습니다."
    )

    # ---------------------------------------------------------------- 6
    st.subheader("6. Energy by State")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.pyplot(fig_energy_by_state(result["energy_df"]), clear_figure=True)
    with c2:
        st.dataframe(result["energy_df"], width='stretch')

    # ---------------------------------------------------------------- 7
    st.subheader("7. Model Comparison")
    st.caption(
        "All-on / PiBase-style / Staged operation / SafeGuard(continuous) / "
        "SafeGuard(duty-cycle) 를 항상 함께 표시하여 비교 조건이 유리하게 "
        "편집되지 않았음을 투명하게 보여준다."
    )
    st.dataframe(result["summary_table"], width='stretch')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.pyplot(fig_model_total_energy(result["summary_table"]), clear_figure=True)
    with c2:
        st.pyplot(fig_model_avg_power(result["summary_table"]), clear_figure=True)
    with c3:
        st.pyplot(fig_savings_vs_allon(result["summary_table"]), clear_figure=True)

    # ---------------------------------------------------------------- 8
    st.subheader("8. Paper-ready Korean Summary")
    summary_text = generate_paper_summary_text(
        result["scenario"], result["summary_table"], result["event_log"], result["is_dummy"]
    )
    st.text_area("결과 해석문 (자동 생성 초안)", summary_text, height=320)

    if st.button("Paper-ready 자동 생성 (표 3종 + 그림 4종 + 해석문/캡션/한계/Q&A TXT 저장)"):
        saved = generate_paper_ready_bundle(
            result["sim_df"],
            result["state_df"],
            result["power_df"],
            result["energy_df"],
            result["summary_table"],
            result["event_log"],
            result["scenario"],
            result["is_dummy"],
        )
        st.success(f"{len(saved)}개 파일이 outputs/ 이하에 저장되었습니다.")
        # 웹 배포 환경에서는 여러 익명 사용자가 동시에 같은 outputs/ 경로에
        # 쓸 수 있으므로, 다운로드는 "지금 이 세션이 생성한 파일의 바이트"를
        # 이 시점에 즉시 메모리로 읽어 session_state에 고정한다. 이후
        # 다른 사용자가 같은 파일을 덮어써도 이 세션의 다운로드 버튼은
        # 항상 자신이 생성한 내용만 서빙한다 (경로를 재읽지 않음).
        st.session_state["_last_bundle"] = {
            name: Path(path).read_bytes() for name, path in saved.items()
        }

    if "_last_bundle" in st.session_state:
        with st.expander("최근 생성된 paper-ready 파일 다운로드"):
            for name, data in st.session_state["_last_bundle"].items():
                st.download_button(
                    f"{name} 다운로드",
                    data=data,
                    file_name=name,
                    key=f"dl_{name}",
                )

    # ---------------------------------------------------------------- 9
    st.subheader("9. Judge Mode Feedback")
    st.caption("심사위원 관점에서 이 결과의 약점/반박 논리/추가 실험/데모 포인트를 미리 점검한다.")
    jc1, jc2 = st.columns(2)
    if jc1.button("Judge Mode 실행"):
        st.session_state["_judge_text"] = generate_judge_mode_feedback(
            result["scenario"], result["summary_table"], result["is_dummy"]
        )
    if jc2.button("예상 Q&A 보기"):
        st.session_state["_judge_qna_text"] = generate_judge_qna_text(
            result["scenario"], result["summary_table"], result["is_dummy"]
        )
    if "_judge_text" in st.session_state:
        st.text_area("Judge Mode 피드백", st.session_state["_judge_text"], height=320)
    if "_judge_qna_text" in st.session_state:
        st.text_area("심사위원 예상 Q&A", st.session_state["_judge_qna_text"], height=320)


if __name__ == "__main__":
    main()
