"""
SafeGuard TwinLab Agent - paper-ready export 번들을 CLI에서 생성하는 스크립트.

대시보드의 "Paper-ready 자동 생성" 버튼과 동일한 src.pipeline /
src.report_generator 함수를 사용하므로, 브라우저 없이도 동일한 11개 산출물
(model_power_comparison.csv, state_power_summary.csv, event_log.csv,
figure_power_timeline.png, figure_energy_by_state.png,
figure_model_energy_comparison.png, figure_saving_vs_all_on.png,
paper_result_summary_kr.txt, figure_captions_kr.txt, limitations_kr.txt,
judge_qna_kr.txt)을 outputs/ 이하에 생성한다.

사용법:
    python scripts/generate_paper_outputs.py --demo normal_risk
    python scripts/generate_paper_outputs.py --hardware-csv sample_data/sample_hardware_log_failsafe.csv --demo mmwave_timeout
    python scripts/generate_paper_outputs.py --list-demos
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DEMO_SCENARIOS, ScenarioConfig
from src.pipeline import run_full_pipeline
from src.report_generator import generate_paper_ready_bundle

DEMO_ALIASES: dict[str, str] = {
    "normal_risk": "Normal Risk Scenario",
    "no_occupant": "No Occupant Scenario",
    "mmwave_timeout": "mmWave Timeout Fail-safe Scenario",
    "duty_cycle_optimized": "Duty-cycle Optimized Scenario",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SafeGuard TwinLab Agent paper-ready export 번들 생성"
    )
    parser.add_argument(
        "--demo",
        choices=sorted(DEMO_ALIASES.keys()),
        default=None,
        help="Demo Mode 프리셋 시나리오를 사용한다 (지정하지 않으면 기본 ScenarioConfig 사용).",
    )
    parser.add_argument(
        "--hardware-csv",
        type=str,
        default=None,
        help="실제 hardware_log.csv 경로. 지정하지 않으면 dummy 데이터를 생성한다.",
    )
    parser.add_argument(
        "--actuator-policy",
        choices=["continuous", "duty_cycle"],
        default=None,
        help="액추에이터 정책을 강제로 덮어쓴다 (지정하지 않으면 시나리오 기본값 사용).",
    )
    parser.add_argument(
        "--list-demos",
        action="store_true",
        help="사용 가능한 --demo 옵션 목록을 출력하고 종료한다.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.list_demos:
        for alias, full_name in DEMO_ALIASES.items():
            print(f"{alias:22s} -> {full_name}")
        return

    if args.demo:
        scenario = DEMO_SCENARIOS[DEMO_ALIASES[args.demo]]
    else:
        scenario = ScenarioConfig()

    if args.actuator_policy:
        scenario = replace(scenario, actuator_policy=args.actuator_policy)

    result = run_full_pipeline(scenario, args.hardware_csv)

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

    print(f"시나리오: {args.demo or '(기본값)'}  |  hardware_csv: {args.hardware_csv or '(dummy)'}")
    print(f"총 {len(saved)}개 파일 생성:")
    for name, path in saved.items():
        print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
