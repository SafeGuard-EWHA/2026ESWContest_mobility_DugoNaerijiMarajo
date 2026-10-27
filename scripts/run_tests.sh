#!/usr/bin/env bash
# SafeGuard TwinLab Agent - 전체 pytest 테스트 스위트 실행 스크립트.
# 사용법: bash scripts/run_tests.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python -m pytest tests/ -v
