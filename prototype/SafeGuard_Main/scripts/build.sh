#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

if ! command -v cmake >/dev/null 2>&1; then
  printf '%s\n' 'CMake가 없습니다. bash scripts/install_pi.sh 를 먼저 실행하세요.' >&2
  exit 1
fi
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel "${BUILD_JOBS:-2}"
ctest --test-dir build --output-on-failure
printf '%s\n' '빌드 완료: build/safeguard_main' \
  '소프트웨어 시뮬레이션: bash scripts/run_demo.sh'

