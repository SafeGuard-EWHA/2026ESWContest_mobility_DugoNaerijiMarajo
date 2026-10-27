#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    '사용: bash scripts/run_demo.sh [시나리오] [--hardware] [--duration 초] [--no-dashboard]' \
    '시나리오: normal, mmwave_fault, unknown, api_fault, estop' \
    '기본: configs/simulation.json / SOFTWARE SIMULATION / 합성 입력' \
    '--hardware: configs/demo.json / 실제 감지 입력 + 표시된 DEMO 온도' \
    '예: bash scripts/run_demo.sh mmwave_fault --duration 20' \
    '예: bash scripts/run_demo.sh --hardware'
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
config=configs/simulation.json
scenario=''
extra=()
while (( $# )); do
  case "$1" in
    --hardware) config=configs/demo.json; shift ;;
    --scenario)
      if (( $# < 2 )); then usage >&2; exit 2; fi
      scenario="$2"; shift 2 ;;
    normal|mmwave_fault|unknown|api_fault|estop)
      if [[ -n "$scenario" ]]; then
        printf '%s\n' '시나리오는 한 개만 지정하세요.' >&2; exit 2
      fi
      scenario="$1"; shift ;;
    --duration)
      if (( $# < 2 )); then usage >&2; exit 2; fi
      extra+=(--duration "$2"); shift 2 ;;
    --no-dashboard) extra+=(--no-dashboard); shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf '알 수 없는 옵션: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ -n "$scenario" ]]; then
  case "$scenario" in
    normal|mmwave_fault|unknown|api_fault|estop) ;;
    *) printf '지원하지 않는 시나리오: %s\n' "$scenario" >&2; exit 2 ;;
  esac
fi
if [[ "$config" == configs/demo.json && -n "$scenario" && "$scenario" != normal ]]; then
  printf '%s\n' '장애 시나리오 자동 주입은 SOFTWARE SIMULATION에서 사용하세요.' \
    '--hardware에서는 실제 감지 입력을 사용합니다.' >&2
  exit 2
fi
if [[ ! -x build/safeguard_main ]]; then
  printf '%s\n' '먼저 bash scripts/build.sh 를 실행하세요.' >&2
  exit 1
fi
if [[ "$config" == configs/simulation.json ]]; then
  printf '%s\n' 'SOFTWARE SIMULATION: 기본 입력은 합성값입니다. 실제 센서 통합 성능이 아닙니다.'
else
  printf '%s\n' 'HARDWARE DEMO: 감지는 실제 장치, 온도는 표시된 DEMO 설정값입니다.' \
    '기본은 DRY_RUN입니다. 미연결 입력을 자동으로 정상 처리하지 않습니다.'
fi
args=(--config "$config")
if [[ -n "$scenario" ]]; then args+=(--scenario "$scenario"); fi
exec ./build/safeguard_main "${args[@]}" "${extra[@]}"

