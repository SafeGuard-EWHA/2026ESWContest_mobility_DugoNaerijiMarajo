"""
SafeGuard TwinLab Agent - 비교 모델(All-on / PiBase / Staged / SafeGuard) 구축.

4가지(SafeGuard는 continuous/duty-cycle 2종 포함 5개) 모델의 device 활성화
표를 만들고, 각 모델의 전력/에너지 지표와 All-on 대비 절감률을 계산한다.

비교 모델 정의:
    1. All-on: 모든 센서/액추에이터를 전체 구간 상시 ON (상한선 baseline).
    2. PiBase-style: Raspberry Pi active + PIR + Camera + DHT22 상시 ON,
       UWB/mmWave 미사용. 감지 시 LED/Buzzer, 위험 온도 시 fan, motor는 OFF.
    3. Staged operation: UWB/PIR-Camera/mmWave/Thermal/Actuator 5단계를
       실제 감지 여부와 무관하게 "동일 시간 비율"로 고정 순차 실행하는
       naive baseline (SafeGuard의 event-driven cascading과 대비하기 위함).
    4/5. SafeGuard proposed (continuous / duty-cycle): Cascading Wake-up
       기반으로 필요한 단계의 센서/제어부만 조건부 활성화.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    ActuatorPolicy,
    MODEL_ALL_ON,
    MODEL_PIBASE,
    MODEL_SAFEGUARD_CONTINUOUS,
    MODEL_SAFEGUARD_DUTY_CYCLE,
    MODEL_STAGED,
    STATE_ACTUATOR_CONTROL,
    STATE_MMWAVE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_THERMAL_PREDICTION,
    STATE_UWB_DEPARTURE_CHECK,
    THERMAL_ACTION_TEMP_C,
)
from src.device_activation import (
    DEVICE_COLUMNS,
    compute_actuator_series,
    compute_device_activation,
)
from src.power_model import compute_power_timeline, compute_savings_pct, compute_summary_metrics

STAGED_ORDER: list[str] = [
    STATE_UWB_DEPARTURE_CHECK,
    STATE_PIR_CAMERA_CHECK,
    STATE_MMWAVE_CHECK,
    STATE_THERMAL_PREDICTION,
    STATE_ACTUATOR_CONTROL,
]


def _empty_activation(time_s: np.ndarray, state: np.ndarray) -> dict[str, np.ndarray]:
    n = len(time_s)
    return {name: np.zeros(n, dtype=int) for name in DEVICE_COLUMNS}


def build_all_on_activation(sim_df: pd.DataFrame) -> pd.DataFrame:
    """All-on 모델: 전체 구간 모든 센서/액추에이터 상시 ON."""
    time_s = sim_df["time_s"].to_numpy(dtype=float)
    n = len(time_s)
    cols = {name: np.ones(n, dtype=int) for name in DEVICE_COLUMNS}
    cols["raspberry_pi_idle"] = np.zeros(n, dtype=int)  # idle 없이 항상 active로 취급

    out = pd.DataFrame(cols)
    out.insert(0, "time_s", time_s)
    # state는 SafeGuard 기준 상태를 참조용으로만 태깅한다 (energy-by-state 비교축 정렬 목적).
    out.insert(1, "state", sim_df["state"].to_numpy() if "state" in sim_df else "ALL_ON")
    return out


def build_pibase_activation(sim_df: pd.DataFrame) -> pd.DataFrame:
    """PiBase-style(PIR+Camera always-on) 모델의 device 활성화 표를 만든다.

    UWB/mmWave는 사용하지 않고, PIR 또는 Camera 감지 시 LED/Buzzer 경고,
    위험 온도(>= THERMAL_ACTION_TEMP_C) 도달 시 fan을 구동한다. motor는
    이 모델에서 항상 OFF로 둔다 (spec 명시).
    """
    time_s = sim_df["time_s"].to_numpy(dtype=float)
    n = len(time_s)
    cols = _empty_activation(time_s, sim_df.get("state", np.array([""] * n)))

    cols["raspberry_pi_active"][:] = 1
    cols["pir"][:] = 1
    cols["camera"][:] = 1
    cols["dht22"][:] = 1

    detected = (
        (sim_df["pir_val"].to_numpy() == 1) | (sim_df["camera_val"].to_numpy() == 1)
    ).astype(int)
    cols["led"] = detected
    cols["buzzer"] = detected
    cols["fan"] = (sim_df["temp_c"].to_numpy() >= THERMAL_ACTION_TEMP_C).astype(int)
    # dc_motor는 항상 0 (PiBase-style spec).

    cols["relay_fan"] = cols["fan"].copy()
    cols["relay_led"] = cols["led"].copy()
    cols["relay_buzzer"] = cols["buzzer"].copy()
    cols["relay_motor"] = cols["dc_motor"].copy()

    out = pd.DataFrame(cols)
    out.insert(0, "time_s", time_s)
    out.insert(1, "state", sim_df["state"].to_numpy() if "state" in sim_df else "PIBASE")
    return out


def build_staged_activation(
    sim_df: pd.DataFrame, actuator_policy: ActuatorPolicy
) -> pd.DataFrame:
    """Staged operation 모델: 5단계를 동일 시간 비율로 고정 순차 실행한다.

    실제 센서 감지 결과와 무관하게 전체 구간을 5등분하여 각 구간에
    해당 단계의 장치만 순서대로 ON한다. SafeGuard의 event-driven
    cascading과 달리 "고정 스케줄"이라는 점이 핵심 차이이며, 이 baseline은
    단순 순차 운용이 이벤트 기반 운용보다 비효율적임을 보여주기 위한
    비교군이다.
    """
    time_s = sim_df["time_s"].to_numpy(dtype=float)
    n = len(time_s)
    cols = _empty_activation(time_s, None)

    segment_len = max(n // len(STAGED_ORDER), 1)
    stage_labels = np.empty(n, dtype=object)
    for seg_idx, stage_name in enumerate(STAGED_ORDER):
        start = seg_idx * segment_len
        end = (seg_idx + 1) * segment_len if seg_idx < len(STAGED_ORDER) - 1 else n
        stage_labels[start:end] = stage_name

    cols["dht22"][:] = 1

    is_uwb = stage_labels == STATE_UWB_DEPARTURE_CHECK
    is_pir_cam = stage_labels == STATE_PIR_CAMERA_CHECK
    is_mmwave = stage_labels == STATE_MMWAVE_CHECK
    is_thermal = stage_labels == STATE_THERMAL_PREDICTION
    is_actuator = stage_labels == STATE_ACTUATOR_CONTROL

    cols["raspberry_pi_idle"][is_uwb] = 1
    cols["raspberry_pi_active"][~is_uwb] = 1
    cols["virtual_uwb"][is_uwb] = 1
    cols["pir"][is_pir_cam] = 1
    cols["camera"][is_pir_cam] = 1
    cols["virtual_mmwave"][is_mmwave] = 1
    # THERMAL_PREDICTION 구간은 dht22 데이터 처리만 수행 (추가 장치 없음).

    if is_actuator.any():
        idx = np.where(is_actuator)[0]
        entry_time = time_s[idx].min()
        t_rel = time_s[idx] - entry_time
        fan, led, buzzer, motor = compute_actuator_series(
            t_rel, actuator_policy, allow_motor=True, limit_buzzer_window=True
        )
        cols["fan"][idx] = fan
        cols["led"][idx] = led
        cols["buzzer"][idx] = buzzer
        cols["dc_motor"][idx] = motor

    cols["relay_fan"] = cols["fan"].copy()
    cols["relay_led"] = cols["led"].copy()
    cols["relay_buzzer"] = cols["buzzer"].copy()
    cols["relay_motor"] = cols["dc_motor"].copy()

    out = pd.DataFrame(cols)
    out.insert(0, "time_s", time_s)
    out.insert(1, "state", stage_labels)
    return out


def run_all_model_comparisons(
    sim_df: pd.DataFrame, state_df: pd.DataFrame, actuator_policy: ActuatorPolicy
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """5개 모델(All-on/PiBase/Staged/SafeGuard-continuous/SafeGuard-duty)을 모두 계산한다.

    SafeGuard는 사용자가 선택한 actuator_policy와 무관하게 continuous와
    duty-cycle 결과를 "항상 함께" 산출한다. 이는 결과가 유리하게 조작된
    것처럼 보이지 않도록 두 제어 전략을 투명하게 병기하기 위함이다.

    Args:
        sim_df: build_simulation_frame() 결과 (pir_val, camera_val, temp_c 포함).
        state_df: run_state_machine() 결과 (SafeGuard state 포함).
        actuator_policy: Staged 모델의 액추에이터 구간에 적용할 정책
            (SafeGuard와 동일 정책으로 맞춰 공정 비교한다).

    Returns:
        (power_df_by_model, summary_table)
        - power_df_by_model: 모델명 -> compute_power_timeline() 결과 DataFrame.
        - summary_table: 모델별 mmwave_profile, avg_power_w, max_power_w,
          total_energy_wh, savings_vs_allon_pct 를 담은 비교 표.
    """
    activations = {
        MODEL_ALL_ON: build_all_on_activation(state_df),
        MODEL_PIBASE: build_pibase_activation(sim_df),
        MODEL_STAGED: build_staged_activation(sim_df, actuator_policy),
        MODEL_SAFEGUARD_CONTINUOUS: compute_device_activation(state_df, "continuous"),
        MODEL_SAFEGUARD_DUTY_CYCLE: compute_device_activation(state_df, "duty_cycle"),
    }

    power_df_by_model: dict[str, pd.DataFrame] = {
        name: compute_power_timeline(df) for name, df in activations.items()
    }

    baseline_wh = compute_summary_metrics(power_df_by_model[MODEL_ALL_ON])["total_energy_wh"]

    # 이번 시뮬레이션 실행에 사용된 mmWave sensor profile을 표에 함께 기록한다
    # (선택한 profile을 결과 표에서도 추적할 수 있도록).
    mmwave_profile = (
        sim_df["mmwave_profile"].iloc[0] if "mmwave_profile" in sim_df.columns else None
    )

    rows = []
    for name, power_df in power_df_by_model.items():
        summary = compute_summary_metrics(power_df)
        rows.append(
            {
                "model": name,
                "mmwave_profile": mmwave_profile,
                "avg_power_w": summary["avg_power_w"],
                "max_power_w": summary["max_power_w"],
                "total_energy_wh": summary["total_energy_wh"],
                "duration_s": summary["duration_s"],
                "savings_vs_allon_pct": compute_savings_pct(
                    summary["total_energy_wh"], baseline_wh
                ),
            }
        )

    summary_table = pd.DataFrame(rows)
    return power_df_by_model, summary_table
