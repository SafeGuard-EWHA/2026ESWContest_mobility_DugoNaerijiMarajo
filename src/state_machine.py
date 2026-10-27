"""
SafeGuard TwinLab Agent - event-driven state machine.

흐름:
    UWB_DEPARTURE_CHECK -> PIR_CAMERA_CHECK -> MMWAVE_CHECK
    -> THERMAL_PREDICTION -> ACTUATOR_CONTROL
    (MMWAVE_CHECK 에서 timeout 시 FAIL_SAFE로 분기)

이 모듈은 단방향(forward-only) 상태 전이를 시간축을 따라 한 번 순회하며
계산한다. 각 시간 스텝(row)마다 현재 상태를 기록하고, 상태가 바뀌는 시점마다
event_log에 전이 기록을 남긴다.
"""

from __future__ import annotations

import pandas as pd

from src.config import (
    MMWAVE_CONSECUTIVE_CONFIRM_COUNT,
    MMWAVE_TIMEOUT_S,
    STATE_ACTUATOR_CONTROL,
    STATE_FAIL_SAFE,
    STATE_MMWAVE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_THERMAL_PREDICTION,
    STATE_UWB_DEPARTURE_CHECK,
    THERMAL_ACTION_TEMP_C,
    THERMAL_MIN_RISE_RATE_C_PER_S,
    THERMAL_RISE_RATE_WINDOW,
    THERMAL_TARGET_TEMP_C,
    THERMAL_TIME_TO_TARGET_THRESHOLD_S,
    UWB_DEPARTURE_DISTANCE_M,
    UWB_DEPARTURE_HOLD_S,
)


def build_simulation_frame(
    hardware_df: pd.DataFrame, virtual_df: pd.DataFrame
) -> pd.DataFrame:
    """hardware_log와 virtual sensor log를 time_s 기준으로 병합한다.

    두 DataFrame은 동일한 시간 해상도(TIME_STEP_S)와 동일한 duration으로
    생성되어야 정합된다 (실제 CSV 업로드 시 오케스트레이션 레이어에서
    scenario.duration_s를 hardware_df의 최대 time_s에 맞춰야 한다).
    """
    merged = pd.merge(hardware_df, virtual_df, on="time_s", how="inner")
    if merged.empty:
        raise ValueError(
            "hardware_df와 virtual_df의 time_s가 겹치지 않습니다. "
            "두 데이터의 시간축(duration, step)이 일치하는지 확인하세요."
        )
    return merged.sort_values("time_s").reset_index(drop=True)


def compute_thermal_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """최근 온도 상승률 기반으로 35도 도달 예상 시간(time_to_35c_s)을 계산한다.

    rate = (temp_now - temp_[t-window]) / (t_now - t_[t-window])
    rate가 거의 0 이하(냉각/정체)이면 도달 예상 시간을 무한대(inf)로 둔다.
    이미 목표 온도 이상이면 0으로 clip한다.
    """
    df = df.copy()
    shifted_temp = df["temp_c"].shift(THERMAL_RISE_RATE_WINDOW)
    shifted_time = df["time_s"].shift(THERMAL_RISE_RATE_WINDOW)

    dt = df["time_s"] - shifted_time
    d_temp = df["temp_c"] - shifted_temp
    rate = d_temp / dt.replace(0, pd.NA)
    rate = rate.astype(float).fillna(0.0)

    remaining = THERMAL_TARGET_TEMP_C - df["temp_c"]
    time_to_target = remaining / rate.where(rate > THERMAL_MIN_RISE_RATE_C_PER_S)
    time_to_target = time_to_target.fillna(float("inf"))
    time_to_target = time_to_target.clip(lower=0.0)

    df["temp_rise_rate_c_per_s"] = rate
    df["time_to_35c_s"] = time_to_target
    return df


def run_state_machine(sim_df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """SafeGuard event-driven state machine을 시간축을 따라 실행한다.

    Args:
        sim_df: build_simulation_frame()의 결과. 다음 컬럼이 필요하다:
            time_s, pir_val, camera_val, guardian_distance_rolling_mean,
            response_ok, mmwave_valid_reading, temp_c.
            mmwave_valid_reading은 virtual_sensors.compute_mmwave_validity()가
            선택된 mmWave sensor profile(C4001/TI)의 confirmation rule에
            따라 이미 계산해 둔 프레임별 유효성 판정 결과다. 이 함수는
            profile 세부 필드(confidence_score, point_count 등)를 직접
            참조하지 않는다.

    Returns:
        (state_df, event_log)
        - state_df: sim_df + [state, occupant_confirmed, time_to_35c_s, ...]
        - event_log: 상태 전이 기록 list[dict(time_s, from_state, to_state, reason)]
    """
    df = compute_thermal_prediction(sim_df)

    state = STATE_UWB_DEPARTURE_CHECK
    departure_hold_start: float | None = None
    mmwave_entry_time: float | None = None
    mmwave_last_response_time: float | None = None
    mmwave_streak = 0
    occupant_confirmed = False

    states: list[str] = []
    occupant_confirmed_col: list[bool] = []

    event_log: list[dict] = [
        {
            "time_s": float(df["time_s"].iloc[0]),
            "from_state": None,
            "to_state": STATE_UWB_DEPARTURE_CHECK,
            "reason": "simulation_start",
        }
    ]

    for row in df.itertuples(index=False):
        t = float(row.time_s)

        if state == STATE_UWB_DEPARTURE_CHECK:
            if row.guardian_distance_rolling_mean >= UWB_DEPARTURE_DISTANCE_M:
                if departure_hold_start is None:
                    departure_hold_start = t
                elif t - departure_hold_start >= UWB_DEPARTURE_HOLD_S:
                    event_log.append(
                        {
                            "time_s": t,
                            "from_state": state,
                            "to_state": STATE_PIR_CAMERA_CHECK,
                            "reason": (
                                f"guardian rolling mean distance >= "
                                f"{UWB_DEPARTURE_DISTANCE_M}m for "
                                f">= {UWB_DEPARTURE_HOLD_S}s"
                            ),
                        }
                    )
                    state = STATE_PIR_CAMERA_CHECK
            else:
                departure_hold_start = None

        elif state == STATE_PIR_CAMERA_CHECK:
            pir_hit = bool(row.pir_val)
            camera_hit = bool(row.camera_val)
            if pir_hit or camera_hit:  # PIR OR Camera
                event_log.append(
                    {
                        "time_s": t,
                        "from_state": state,
                        "to_state": STATE_MMWAVE_CHECK,
                        "reason": f"pir_val={int(pir_hit)} OR camera_val={int(camera_hit)}",
                    }
                )
                state = STATE_MMWAVE_CHECK
                mmwave_entry_time = t
                mmwave_last_response_time = None
                mmwave_streak = 0

        elif state == STATE_MMWAVE_CHECK:
            responded = bool(row.response_ok)
            valid = bool(row.mmwave_valid_reading)
            if responded:
                mmwave_last_response_time = t
            mmwave_streak = mmwave_streak + 1 if valid else 0

            if mmwave_streak >= MMWAVE_CONSECUTIVE_CONFIRM_COUNT:
                occupant_confirmed = True
                event_log.append(
                    {
                        "time_s": t,
                        "from_state": state,
                        "to_state": STATE_THERMAL_PREDICTION,
                        "reason": (
                            f"mmWave presence confirmed for "
                            f">= {MMWAVE_CONSECUTIVE_CONFIRM_COUNT} consecutive samples"
                        ),
                    }
                )
                state = STATE_THERMAL_PREDICTION
            else:
                baseline = (
                    mmwave_last_response_time
                    if mmwave_last_response_time is not None
                    else mmwave_entry_time
                )
                if baseline is not None and (t - baseline) >= MMWAVE_TIMEOUT_S:
                    event_log.append(
                        {
                            "time_s": t,
                            "from_state": state,
                            "to_state": STATE_FAIL_SAFE,
                            "reason": (
                                f"mmWave timeout: no sensor response for "
                                f">= {MMWAVE_TIMEOUT_S}s"
                            ),
                        }
                    )
                    state = STATE_FAIL_SAFE

        elif state == STATE_THERMAL_PREDICTION:
            temp_now = float(row.temp_c)
            time_to_35c = float(row.time_to_35c_s)
            if (
                temp_now >= THERMAL_ACTION_TEMP_C
                or time_to_35c <= THERMAL_TIME_TO_TARGET_THRESHOLD_S
            ):
                event_log.append(
                    {
                        "time_s": t,
                        "from_state": state,
                        "to_state": STATE_ACTUATOR_CONTROL,
                        "reason": (
                            f"temp_c={temp_now:.2f} >= {THERMAL_ACTION_TEMP_C} "
                            f"OR time_to_35c_s={time_to_35c:.1f} <= "
                            f"{THERMAL_TIME_TO_TARGET_THRESHOLD_S}"
                        ),
                    }
                )
                state = STATE_ACTUATOR_CONTROL

        # ACTUATOR_CONTROL, FAIL_SAFE: 종단 상태이므로 별도 전이 없음.

        states.append(state)
        occupant_confirmed_col.append(occupant_confirmed)

    df["state"] = states
    df["occupant_confirmed"] = occupant_confirmed_col
    return df, event_log


def event_log_to_dataframe(event_log: list[dict]) -> pd.DataFrame:
    """event_log(list[dict])를 표시/저장이 용이한 DataFrame으로 변환한다."""
    return pd.DataFrame(event_log)
