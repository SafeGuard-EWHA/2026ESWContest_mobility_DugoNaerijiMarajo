"""
sample_data/ 이하 3개 hardware_log.csv를 재현 가능하게 생성하는 일회성 스크립트.

각 CSV는 대응하는 Demo Mode 프리셋(src.config.DEMO_SCENARIOS)과 동일한
시나리오 조건으로 생성되며, pir_val/temp_c 컬럼을 의도적으로 조정하여
hardware_log.csv 내용만으로도 state machine 결과가 뚜렷이 달라지도록 한다.

사용법: python scripts/_gen_sample_data.py
(release 패키지에는 결과 CSV만 포함되며, 이 스크립트는 재현/재생성 참고용이다.)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DEMO_SCENARIOS, SAMPLE_DATA_DIR
from src.data_loader import generate_dummy_hardware_log

SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save(df, filename: str) -> None:
    df = df.drop(columns=["dht22_failure_flag"], errors="ignore")
    path = SAMPLE_DATA_DIR / filename
    df.to_csv(path, index=False)
    print(f"saved: {path} ({len(df)} rows)")


# 1) Normal Risk: PIR이 t=20s부터 감지되고, 온도가 32C를 넘어 위험 수준까지 상승.
normal_risk = generate_dummy_hardware_log(DEMO_SCENARIOS["Normal Risk Scenario"])
normal_risk.loc[normal_risk["time_s"] >= 20, "pir_val"] = 1
normal_risk.loc[normal_risk["time_s"] < 20, "pir_val"] = 0
_save(normal_risk, "sample_hardware_log_normal_risk.csv")

# 2) No Occupant: PIR이 전 구간 미감지, 온도도 낮은 수준에서 안정적으로 유지.
no_occupant = generate_dummy_hardware_log(DEMO_SCENARIOS["No Occupant Scenario"])
no_occupant["pir_val"] = 0
_save(no_occupant, "sample_hardware_log_no_occupant.csv")

# 3) Fail-safe: PIR이 t=10s부터 빠르게 감지되어 MMWAVE_CHECK까지는 신속히 도달하지만,
#    (Demo Mode의 mmWave Timeout 프리셋과 함께 사용 시) mmWave 무응답으로 FAIL_SAFE에 진입한다.
failsafe = generate_dummy_hardware_log(DEMO_SCENARIOS["mmWave Timeout Fail-safe Scenario"])
failsafe.loc[failsafe["time_s"] >= 10, "pir_val"] = 1
failsafe.loc[failsafe["time_s"] < 10, "pir_val"] = 0
_save(failsafe, "sample_hardware_log_failsafe.csv")
