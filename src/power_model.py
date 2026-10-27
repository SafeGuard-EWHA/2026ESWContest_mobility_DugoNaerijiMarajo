"""
SafeGuard TwinLab Agent - estimated power model.

**중요한 한계 명시**: 이 모듈이 산출하는 전력 값은 실측(measured power)이
아니라 datasheet/typical-value 기반의 "추정 전력 모델(estimated power
model)"이다. 실측값이 필요할 경우 data_loader.load_power_measure_log()로
읽은 power_measure_log.csv와 비교/검증하는 용도로만 사용해야 한다.
"""

from __future__ import annotations

import pandas as pd

from src.config import POWER_W, RELAY_CHANNELS, TIME_STEP_S

# device_activation의 컬럼명 -> POWER_W 딕셔너리 키 매핑.
DEVICE_TO_POWER_KEY: dict[str, str] = {
    "raspberry_pi_idle": "raspberry_pi_idle",
    "raspberry_pi_active": "raspberry_pi_active",
    "virtual_uwb": "virtual_uwb",
    "pir": "pir",
    "camera": "camera",
    "virtual_mmwave": "virtual_mmwave",
    "dht22": "dht22",
    "fan": "fan",
    "led": "led",
    "buzzer": "buzzer",
    "dc_motor": "dc_motor",
}

RELAY_COLUMNS: list[str] = [f"relay_{ch}" for ch in RELAY_CHANNELS]


def compute_power_timeline(activation_df: pd.DataFrame) -> pd.DataFrame:
    """device 활성화 표(0/1)로부터 순간 추정 전력(power_w) timeline을 계산한다.

    Args:
        activation_df: device_activation.compute_device_activation() 등의
            결과. time_s, state + 0/1 device 컬럼을 포함해야 한다.

    Returns:
        입력 DataFrame에 각 device의 전력 기여분(<device>_power_w) 컬럼과
        총 순간 전력 power_w 컬럼을 추가한 DataFrame.
    """
    df = activation_df.copy()
    total = pd.Series(0.0, index=df.index)

    for device_col, power_key in DEVICE_TO_POWER_KEY.items():
        if device_col not in df.columns:
            continue
        contribution = df[device_col].astype(float) * POWER_W[power_key]
        df[f"{device_col}_power_w"] = contribution
        total += contribution

    # 릴레이 채널: 활성화된 채널마다 relay_channel 전력을 추가로 합산한다.
    relay_contribution = pd.Series(0.0, index=df.index)
    for relay_col in RELAY_COLUMNS:
        if relay_col in df.columns:
            relay_contribution += df[relay_col].astype(float) * POWER_W["relay_channel"]
    df["relay_power_w"] = relay_contribution
    total += relay_contribution

    df["power_w"] = total
    return df


def compute_energy_by_state(power_df: pd.DataFrame) -> pd.DataFrame:
    """state별 소비 에너지를 계산한다 (논문용 표: energy by state).

    에너지(J) = sum(power_w * TIME_STEP_S), 에너지(Wh) = 에너지(J) / 3600.

    Returns:
        columns: state, energy_j, energy_wh, duration_s, avg_power_w
    """
    grouped = power_df.groupby("state").agg(
        energy_j=("power_w", lambda s: float((s * TIME_STEP_S).sum())),
        duration_s=("power_w", lambda s: float(len(s) * TIME_STEP_S)),
        avg_power_w=("power_w", "mean"),
    )
    grouped["energy_wh"] = grouped["energy_j"] / 3600.0
    return grouped.reset_index()


def compute_summary_metrics(power_df: pd.DataFrame) -> dict[str, float]:
    """전체 시뮬레이션 구간에 대한 요약 지표를 계산한다.

    Returns:
        dict(avg_power_w, max_power_w, total_energy_j, total_energy_wh,
             duration_s)
    """
    power = power_df["power_w"]
    duration_s = float(len(power_df) * TIME_STEP_S)
    total_energy_j = float((power * TIME_STEP_S).sum())
    return {
        "avg_power_w": float(power.mean()),
        "max_power_w": float(power.max()),
        "total_energy_j": total_energy_j,
        "total_energy_wh": total_energy_j / 3600.0,
        "duration_s": duration_s,
    }


def compute_savings_pct(candidate_energy_wh: float, baseline_energy_wh: float) -> float:
    """baseline(All-on) 대비 candidate 모델의 에너지 절감률(%)을 계산한다.

    Returns:
        절감률(%). 양수면 절감, 음수면 baseline보다 더 소비함을 의미한다.
    """
    if baseline_energy_wh <= 0:
        return 0.0
    return (1.0 - candidate_energy_wh / baseline_energy_wh) * 100.0
