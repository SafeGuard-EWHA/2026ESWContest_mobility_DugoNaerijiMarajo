"""
SafeGuard TwinLab Agent - hardware log loading, validation, and dummy generation.

이 모듈은 실제 Raspberry Pi에서 수집된 hardware_log.csv (와 선택적으로
power_measure_log.csv)를 읽고 검증/정규화한다. 파일이 없으면 재현 가능한
dummy hardware log를 생성한다.

hardware_log.csv 컬럼: time_s, state, pir_val, temp_c, humidity,
relay_fan, relay_led, relay_buzzer, relay_motor, cpu_temp_c, cpu_percent
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    HARDWARE_LOG_COLUMNS,
    POWER_MEASURE_LOG_COLUMNS,
    ScenarioConfig,
    TIME_STEP_S,
    set_global_seed,
)

RELAY_RAW_COLUMNS: list[str] = [
    "relay_fan",
    "relay_led",
    "relay_buzzer",
    "relay_motor",
]


class HardwareLogValidationError(ValueError):
    """hardware_log.csv 스키마 검증 실패 시 발생하는 예외."""


def validate_hardware_log(df: pd.DataFrame) -> None:
    """hardware_log DataFrame이 필수 컬럼을 모두 포함하는지 검증한다.

    Args:
        df: 검증 대상 DataFrame.

    Raises:
        HardwareLogValidationError: 필수 컬럼이 하나 이상 누락된 경우.
    """
    missing = [c for c in HARDWARE_LOG_COLUMNS if c not in df.columns]
    if missing:
        raise HardwareLogValidationError(
            f"hardware_log.csv에 필수 컬럼이 없습니다: {missing}. "
            f"필요한 컬럼: {HARDWARE_LOG_COLUMNS}"
        )
    if df.empty:
        raise HardwareLogValidationError("hardware_log.csv가 비어 있습니다.")


def normalize_relay_columns(df: pd.DataFrame) -> pd.DataFrame:
    """relay_* 컬럼을 0/1 정수로 정규화한다.

    True/False, "ON"/"OFF", "1"/"0", 1.0/0.0 등 다양한 표기를 허용하고
    결측치는 0(OFF)으로 처리한다 (fail-safe 기본값).
    """
    df = df.copy()
    on_tokens = {"1", "on", "true", "high"}
    for col in RELAY_RAW_COLUMNS:
        if col not in df.columns:
            df[col] = 0
            continue

        def _to_binary(value: object) -> int:
            if pd.isna(value):
                return 0
            if isinstance(value, (int, float, np.integer, np.floating)):
                return int(bool(value))
            return int(str(value).strip().lower() in on_tokens)

        df[col] = df[col].apply(_to_binary).astype(int)
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """센서 결측치를 처리한다 (DHT22 read failure 포함).

    - temp_c / humidity: DHT22 read failure로 인한 NaN 또는 -999 sentinel을
      선형 보간(interpolate)하고, 처리된 행 수를 dht22_failure_flag로 표시한다.
    - pir_val: 결측 시 0(미감지)으로 채운다 (보수적 fail-safe).
    - cpu_temp_c / cpu_percent: 결측 시 앞/뒤 값으로 채운다.

    Returns:
        결측치가 처리된 DataFrame. 'dht22_failure_flag' 컬럼이 추가된다.
    """
    df = df.copy()

    # DHT22 오류를 흔히 나타내는 sentinel 값(-999)을 NaN으로 통일한다.
    for col in ("temp_c", "humidity"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] <= -999, col] = np.nan

    df["dht22_failure_flag"] = (df["temp_c"].isna() | df["humidity"].isna()).astype(int)

    for col in ("temp_c", "humidity"):
        n_missing = df[col].isna().sum()
        if n_missing:
            df[col] = df[col].interpolate(limit_direction="both")
            if df[col].isna().any():
                # 전체가 결측인 극단적 경우 기본값으로 대체한다.
                fallback = 25.0 if col == "temp_c" else 50.0
                df[col] = df[col].fillna(fallback)
            warnings.warn(
                f"DHT22 read failure 감지: '{col}' 컬럼 {n_missing}개 값을 보간했습니다.",
                stacklevel=2,
            )

    if "pir_val" in df.columns:
        df["pir_val"] = pd.to_numeric(df["pir_val"], errors="coerce").fillna(0).astype(int)

    for col in ("cpu_temp_c", "cpu_percent"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").ffill().bfill()

    return df


def load_hardware_log(path: str | Path) -> pd.DataFrame:
    """hardware_log.csv를 읽고 검증/정규화까지 수행한다.

    Args:
        path: hardware_log.csv 경로.

    Returns:
        스키마 검증, relay 정규화, 결측치 처리가 완료된 DataFrame.
    """
    df = pd.read_csv(path)
    validate_hardware_log(df)
    df = df.sort_values("time_s").reset_index(drop=True)
    df = normalize_relay_columns(df)
    df = handle_missing_values(df)
    return df


def load_power_measure_log(path: str | Path) -> pd.DataFrame:
    """선택적 power_measure_log.csv(실측 전력)를 읽는다.

    이 로그는 존재할 경우 estimated power model과의 비교/검증용으로만 쓰이며,
    시뮬레이션 파이프라인의 필수 입력은 아니다.
    """
    df = pd.read_csv(path)
    missing = [c for c in POWER_MEASURE_LOG_COLUMNS if c not in df.columns]
    if missing:
        raise HardwareLogValidationError(
            f"power_measure_log.csv에 필수 컬럼이 없습니다: {missing}"
        )
    return df.sort_values("time_s").reset_index(drop=True)


def generate_dummy_hardware_log(scenario: ScenarioConfig) -> pd.DataFrame:
    """재현 가능한 dummy Raspberry Pi hardware log를 생성한다.

    실제 hardware_log.csv가 없을 때 시뮬레이션 파이프라인을 테스트/시연하기
    위한 합성 데이터이다. 온도는 뉴턴 냉각(가열) 법칙 근사로 outside_temp_c를
    향해 상승하고, PIR/CPU 부하는 occupant_exists/motion_state 조건에 따라
    합성된다.

    Args:
        scenario: 시나리오 설정.

    Returns:
        HARDWARE_LOG_COLUMNS 스키마를 만족하는 DataFrame.
    """
    set_global_seed(scenario.seed)
    rng = np.random.default_rng(scenario.seed)

    n_steps = int(scenario.duration_s // TIME_STEP_S) + 1
    time_s = np.arange(n_steps) * TIME_STEP_S

    # --- 온도: 뉴턴 가열 근사 T(t) = T_out - (T_out - T0) * exp(-k t) ---
    t0 = scenario.initial_temp_c
    t_out = scenario.outside_temp_c
    rate_per_s = max(scenario.temp_rise_rate_c_per_min / 60.0, 1e-4)
    delta = t_out - t0
    k = rate_per_s / abs(delta) if abs(delta) > 1e-6 else 1e-4
    temp_c = t_out - delta * np.exp(-k * time_s)
    temp_c = temp_c + rng.normal(0, 0.05, size=n_steps)  # 센서 노이즈

    if scenario.dht22_failure:
        # 임의 구간에서 DHT22 read failure를 시뮬레이션한다 (NaN 삽입).
        fail_start = rng.integers(low=0, high=max(n_steps - 20, 1))
        fail_len = min(10, n_steps - fail_start)
        temp_c[fail_start : fail_start + fail_len] = np.nan

    humidity = np.clip(
        scenario.humidity_pct + rng.normal(0, 1.5, size=n_steps), 0, 100
    )

    # --- PIR: occupant 존재 및 motion_state에 따른 감지 패턴 ---
    if scenario.occupant_exists:
        base_p = 0.9 if scenario.motion_state == "moving" else 0.4
    else:
        base_p = 0.02 if scenario.pir_false_positive else 0.0
    pir_val = (rng.random(n_steps) < base_p).astype(int)

    # --- CPU 부하: PIR 감지 시 소폭 상승 ---
    cpu_percent = 15.0 + 10.0 * pir_val + rng.normal(0, 2.0, size=n_steps)
    cpu_percent = np.clip(cpu_percent, 2, 95)
    cpu_temp_c = 40.0 + 0.25 * cpu_percent + rng.normal(0, 0.3, size=n_steps)

    df = pd.DataFrame(
        {
            "time_s": time_s,
            "state": "",  # dummy 원시 로그는 상태를 기록하지 않음 (state_machine이 재계산)
            "pir_val": pir_val,
            "temp_c": temp_c,
            "humidity": humidity,
            "relay_fan": 0,
            "relay_led": 0,
            "relay_buzzer": 0,
            "relay_motor": 0,
            "cpu_temp_c": cpu_temp_c,
            "cpu_percent": cpu_percent,
        }
    )
    df = normalize_relay_columns(df)
    df = handle_missing_values(df)
    return df


def load_or_generate_hardware_log(
    scenario: ScenarioConfig, path: str | Path | None = None
) -> tuple[pd.DataFrame, bool]:
    """hardware_log.csv가 존재하면 로드하고, 없으면 dummy 데이터를 생성한다.

    Args:
        scenario: dummy 생성 시 사용할 시나리오 설정.
        path: hardware_log.csv 경로. None이면 dummy만 생성한다.

    Returns:
        (DataFrame, is_dummy) 튜플. is_dummy=True이면 합성 데이터임을 의미한다.
    """
    if path is not None and Path(path).exists():
        return load_hardware_log(path), False
    return generate_dummy_hardware_log(scenario), True
