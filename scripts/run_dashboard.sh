#!/usr/bin/env bash
# SafeGuard TwinLab Agent - Streamlit dashboard 실행 스크립트.
# 사용법: bash scripts/run_dashboard.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python -m streamlit run app/streamlit_app.py
