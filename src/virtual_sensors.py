"""
SafeGuard TwinLab Agent - UWB / mmWave / Camera virtual sensor generation.

**중요한 한계(limitation) 명시**:
이 모듈이 생성하는 UWB, mmWave 신호는 raw RF/radar signal(FMCW chirp, FFT
spectrum 등)을 물리적으로 모델링한 것이 아니라, 최종 output-level 값
(거리, presence flag, velocity, confidence 등)만을 시나리오 조건에 따라
합성하는 "output-level virtual sensor simulation"이다. 실제 DWM1001-DEV
(UWB)나 mmWave 모듈의 raw waveform, 안테나 특성, 다중경로 반사 등은
모델링하지 않는다. 논문/보고서에 결과를 기술할 때는 반드시 이 한계를
명시해야 한다.

mmWave는 단일 센서로 고정되지 않고 `ScenarioConfig.mmwave_profile`로
선택 가능한 **sensor profile** 기반으로 생성된다 (src.config.MMWAVE_PROFILES
참고). 각 profile은 서로 다른 output field 구성과 confirmation 임계값을
가지지만, 어느 profile을 선택하더라도 실제 하드웨어의 raw signal
processing을 수행하지 않는 output-level 시뮬레이션이라는 점은 동일하다.

Camera 감지도 OpenCV contour 기반 판정을 직접 재현하지 않고, light_condition에
따른 detection probability로 근사한 output-level 시뮬레이션이다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    MMWAVE_C4001_CONFIDENCE_MIN,
    MMWAVE_PRESENCE_MAX_DISTANCE_M,
    MMWAVE_PRESENCE_MIN_DISTANCE_M,
    MMWAVE_PROFILE_C4001,
    MMWAVE_PROFILE_TI_IWR6843,
    MMWAVE_TI_CONFIDENCE_MIN,
    MMWAVE_TI_POINT_COUNT_MIN,
    ScenarioConfig,
    TIME_STEP_S,
    UWB_ROLLING_WINDOW,
    set_global_seed,
)


def _time_axis(scenario: ScenarioConfig) -> np.ndarray:
    n_steps = int(scenario.duration_s // TIME_STEP_S) + 1
    return np.arange(n_steps) * TIME_STEP_S


def generate_uwb_distance(scenario: ScenarioConfig) -> pd.DataFrame:
    """보호자-차량 간 UWB 가상 거리 timeline을 생성한다 (output-level).

    guardian_departure_time_s 이전에는 근접 거리(1~2m)를 유지하고, 이후에는
    점진적으로 멀어지는 램프(ramp) + 노이즈로 근사한다. rolling mean은
    설정된 UWB_ROLLING_WINDOW로 계산하여 state_machine의 이탈 판정에 사용된다.

    Returns:
        columns: time_s, guardian_distance_m, guardian_distance_rolling_mean
    """
    set_global_seed(scenario.seed)
    rng = np.random.default_rng(scenario.seed)
    t = _time_axis(scenario)

    near_distance = rng.uniform(0.8, 1.5)
    far_distance = rng.uniform(12.0, 25.0)
    ramp_duration_s = 20.0  # 이탈 시작 후 far_distance까지 도달하는 데 걸리는 시간

    distance = np.full_like(t, near_distance, dtype=float)
    departed_mask = t >= scenario.guardian_departure_time_s
    elapsed = np.clip(
        (t - scenario.guardian_departure_time_s) / ramp_duration_s, 0.0, 1.0
    )
    distance[departed_mask] = near_distance + elapsed[departed_mask] * (
        far_distance - near_distance
    )
    distance += rng.normal(0, 0.15, size=t.shape)
    distance = np.clip(distance, 0.0, None)

    df = pd.DataFrame({"time_s": t, "guardian_distance_m": distance})
    df["guardian_distance_rolling_mean"] = (
        df["guardian_distance_m"]
        .rolling(window=UWB_ROLLING_WINDOW, min_periods=1)
        .mean()
    )
    return df


def generate_camera_detection(scenario: ScenarioConfig) -> pd.DataFrame:
    """Camera(OpenCV contour 기반 판정) 감지 결과를 output-level로 근사한다.

    light_condition == 'dark'인 경우 감지 확률이 크게 낮아지는
    "Camera dark condition" failure scenario를 재현한다.
    """
    set_global_seed(scenario.seed + 1)
    rng = np.random.default_rng(scenario.seed + 1)
    t = _time_axis(scenario)

    detect_prob_map = {"bright": 0.95, "dim": 0.7, "dark": 0.15}
    base_p = detect_prob_map.get(scenario.light_condition, 0.9)
    if not scenario.occupant_exists:
        base_p = 0.02  # 오탐 가능성만 소폭 반영

    camera_val = (rng.random(t.shape) < base_p).astype(int)
    return pd.DataFrame({"time_s": t, "camera_val": camera_val})


def generate_mmwave(scenario: ScenarioConfig) -> pd.DataFrame:
    """mmWave presence/distance/velocity를 scenario.mmwave_profile에 따라 output-level로 생성한다.

    scenario.mmwave_mode에 따라 5가지 edge case를 지원한다:
        - normal: 탑승자 존재 시 유효 범위(0.2~3.0m) 내 안정적 presence.
        - no_occupant: 탑승자 없음, presence_flag 항상 0.
        - intermittent: presence가 간헐적으로 끊기는 불안정 신호.
        - timeout: 특정 구간 이후 신호 자체가 끊김(NaN) -> FAIL_SAFE 유발.
        - out_of_range: presence는 감지되나 거리값이 유효 범위를 벗어남.

    scenario.mmwave_profile에 따라 output field 구성과 confirmation
    임계값이 달라진다 (src.config.MMWAVE_PROFILES 참고):
        - C4001_24GHz_LOW_COST: response_ok, presence_flag, distance_m,
          velocity_mps, confidence_score. confidence_score >= 0.6이면 유효.
        - TI_IWR6843ISK_REFERENCE: 위 필드에 더해 point_count, angle_deg,
          micro_motion_score를 추가로 보고한다. point_count >= 3 이고
          confidence_score >= 0.75이어야 유효 (더 엄격한 confirmation).

    velocity_mps는 호흡에 의한 미세 움직임(0.2~0.5Hz)을 사인파로 근사한다
    (논문에서 언급된 breathing rate 12~30bpm 대역과 일치).

    Returns:
        columns: time_s, response_ok, presence_flag, distance_m,
        velocity_mps, confidence_score, mmwave_valid_reading, mmwave_profile
        (+ TI profile 선택 시 point_count, angle_deg, micro_motion_score).
    """
    set_global_seed(scenario.seed + 2)
    rng = np.random.default_rng(scenario.seed + 2)
    t = _time_axis(scenario)
    n = t.shape[0]

    breathing_hz = rng.uniform(0.2, 0.5)
    base_distance = rng.uniform(0.5, 1.2)
    velocity = 0.02 * np.sin(2 * np.pi * breathing_hz * t) + rng.normal(0, 0.005, n)

    response_ok = np.ones(n, dtype=bool)
    presence_flag = np.ones(n, dtype=float)
    distance_m = base_distance + rng.normal(0, 0.03, n)

    if not scenario.occupant_exists or scenario.mmwave_mode == "no_occupant":
        # 센서는 정상 응답하지만(response_ok=True) 탑승자가 없어 presence=0으로 보고한다.
        presence_flag[:] = 0.0
        distance_m[:] = np.nan
        velocity[:] = 0.0
    elif scenario.mmwave_mode == "intermittent":
        # 센서 응답 자체가 순간적으로 끊기는 불안정 통신을 재현한다.
        dropout_mask = rng.random(n) < 0.35
        response_ok[dropout_mask] = False
        presence_flag[dropout_mask] = np.nan
        distance_m[dropout_mask] = np.nan
    elif scenario.mmwave_mode == "timeout":
        # 센서가 처음부터 전혀 응답하지 않는 완전 통신두절 상황을 재현한다.
        # MMWAVE_CHECK 진입 시점과 무관하게 항상 timeout이 관찰되도록 전 구간에
        # 적용한다 (Failure Scenario Simulation 데모의 결정론적 재현을 위함).
        response_ok[:] = False
        presence_flag[:] = np.nan
        distance_m[:] = np.nan
        velocity[:] = np.nan
    elif scenario.mmwave_mode == "out_of_range":
        # presence는 감지되지만 유효 거리 범위를 벗어나 occupant_confirmed 되지 않는다.
        distance_m = np.full(n, MMWAVE_PRESENCE_MAX_DISTANCE_M + rng.uniform(0.5, 1.5))
    # 'normal'은 위에서 생성된 기본값을 그대로 사용한다.

    distance_m = np.where(np.isnan(distance_m), np.nan, np.clip(distance_m, 0.0, None))

    # presence가 유효 범위 내에 안정적으로 잡히는 프레임인지(=confirmation 후보)를
    # 먼저 판단한 뒤, 이를 기준으로 confidence_score 등 부가 필드를 합성한다.
    presence_candidate = (
        response_ok
        & (presence_flag == 1)
        & ~np.isnan(distance_m)
        & (distance_m >= MMWAVE_PRESENCE_MIN_DISTANCE_M)
        & (distance_m <= MMWAVE_PRESENCE_MAX_DISTANCE_M)
    )

    confidence_score = np.where(
        presence_candidate,
        rng.uniform(0.72, 0.97, n),
        rng.uniform(0.05, 0.55, n),
    )
    confidence_score = np.where(response_ok, confidence_score, np.nan)

    data: dict[str, np.ndarray] = {
        "time_s": t,
        "response_ok": response_ok,
        "presence_flag": presence_flag,
        "distance_m": distance_m,
        "velocity_mps": velocity,
        "confidence_score": confidence_score,
    }

    if scenario.mmwave_profile == MMWAVE_PROFILE_TI_IWR6843:
        point_count = np.where(
            presence_candidate,
            rng.integers(3, 12, n),
            rng.integers(0, 3, n),
        ).astype(float)
        angle_deg = np.where(
            presence_candidate, rng.uniform(-15, 15, n), rng.uniform(-60, 60, n)
        )
        micro_motion_score = np.clip(
            np.abs(velocity) / 0.02 * rng.uniform(0.8, 1.0, n), 0.0, 1.0
        )
        data["point_count"] = np.where(response_ok, point_count, np.nan)
        data["angle_deg"] = np.where(response_ok, angle_deg, np.nan)
        data["micro_motion_score"] = np.where(response_ok, micro_motion_score, np.nan)

    df = pd.DataFrame(data)
    df["mmwave_valid_reading"] = compute_mmwave_validity(scenario.mmwave_profile, df)
    df["mmwave_profile"] = scenario.mmwave_profile
    return df


def compute_mmwave_validity(profile: str, df: pd.DataFrame) -> pd.Series:
    """mmWave sensor profile별 confirmation rule에 따라 프레임 유효성을 벡터화 계산한다.

    두 profile 모두 공통으로 response_ok, presence_flag=1,
    0.2<=distance_m<=3.0m을 요구하며, 여기에 profile별 추가 조건이 더해진다:
        - C4001_24GHz_LOW_COST: confidence_score >= MMWAVE_C4001_CONFIDENCE_MIN.
        - TI_IWR6843ISK_REFERENCE: point_count >= MMWAVE_TI_POINT_COUNT_MIN
          이고 confidence_score >= MMWAVE_TI_CONFIDENCE_MIN (더 엄격).

    "연속 5회 이상" 조건은 시간적(state) 개념이므로 이 함수가 아니라
    state_machine.run_state_machine()의 streak 카운팅에서 처리한다.

    Args:
        profile: MMWAVE_PROFILE_C4001 또는 MMWAVE_PROFILE_TI_IWR6843.
        df: response_ok, presence_flag, distance_m, confidence_score
            (+ TI profile이면 point_count)를 포함하는 DataFrame.

    Returns:
        프레임별 유효 여부를 나타내는 bool Series.
    """
    response_ok = df["response_ok"].fillna(False).astype(bool)
    presence_ok = df["presence_flag"] == 1
    distance_ok = df["distance_m"].between(
        MMWAVE_PRESENCE_MIN_DISTANCE_M, MMWAVE_PRESENCE_MAX_DISTANCE_M
    )

    if profile == MMWAVE_PROFILE_TI_IWR6843:
        confidence_ok = df["confidence_score"] >= MMWAVE_TI_CONFIDENCE_MIN
        point_count_ok = df["point_count"] >= MMWAVE_TI_POINT_COUNT_MIN
        valid = response_ok & presence_ok & distance_ok & confidence_ok & point_count_ok
    else:  # MMWAVE_PROFILE_C4001 (default)
        confidence_ok = df["confidence_score"] >= MMWAVE_C4001_CONFIDENCE_MIN
        valid = response_ok & presence_ok & distance_ok & confidence_ok

    return valid.fillna(False)


def generate_virtual_sensor_log(scenario: ScenarioConfig) -> pd.DataFrame:
    """UWB, Camera, mmWave 가상 센서 로그를 time_s 기준으로 병합한다.

    Returns:
        columns: time_s, guardian_distance_m, guardian_distance_rolling_mean,
                  camera_val, response_ok, presence_flag, distance_m,
                  velocity_mps, confidence_score, mmwave_valid_reading,
                  mmwave_profile (+ TI profile 선택 시 point_count,
                  angle_deg, micro_motion_score)
    """
    uwb = generate_uwb_distance(scenario)
    camera = generate_camera_detection(scenario)
    mmwave = generate_mmwave(scenario)

    merged = uwb.merge(camera, on="time_s").merge(mmwave, on="time_s")
    return merged
