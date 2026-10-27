#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
extra=()
while (( $# )); do
  case "$1" in
    --duration)
      if (( $# < 2 )); then
        printf '%s\n' '--duration 뒤에 실행 시간을 초 단위로 넣으세요.' >&2; exit 2
      fi
      extra+=(--duration "$2"); shift 2 ;;
    --no-dashboard) extra+=(--no-dashboard); shift ;;
    -h|--help)
      printf '%s\n' '사용: bash scripts/run_real.sh [--duration 초] [--no-dashboard]' \
        'configs/real.json 사용. 기본은 DRY_RUN이며 미연결 센서는 무효입니다.'
      exit 0 ;;
    *) printf '알 수 없는 옵션: %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [[ ! -x build/safeguard_main ]]; then
  printf '%s\n' '먼저 bash scripts/build.sh 를 실행하세요.' >&2
  exit 1
fi
printf '%s\n' 'REAL 입력: 차량 UWB의 lec 출력이 이미 켜져 있어야 합니다.' \
  '기본은 DRY_RUN. 연결하지 않은 A/B 입력과 보정하지 않은 예측은 무효로 표시합니다.'
exec ./build/safeguard_main --config configs/real.json "${extra[@]}"

