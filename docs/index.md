---
title: SafeGuard TwinLab Agent
---

# SafeGuard TwinLab Agent

차량 내 잔류 탑승자 보호 시스템 **SafeGuard**의 end-to-end 시뮬레이션
프로젝트 홈페이지다. Raspberry Pi hardware log와 UWB/mmWave virtual
sensor를 결합해 event-driven state machine, 추정 전력(estimated power)
계산, 비교 모델 분석, 논문용 산출물까지 자동 생성한다.

**[▶ Live Demo (Streamlit)](https://safeguard-mmwave-simulator.streamlit.app)**
&nbsp;|&nbsp;
**[💻 Source Code (GitHub)](https://github.com/yoontf0/safeguard-mmwave-simulator)**
&nbsp;|&nbsp;
**[📄 Paper-ready Sample Outputs](sample_outputs/)**

> 위 Live Demo/Source Code 링크는 모두 실제 배포된 값으로 반영되어 있다.

---

## 프로젝트 개요

SafeGuard는 보호자가 차량에서 이탈한 뒤, 차량 내부에 잔류 탑승자가 있는지
**Cascading Wake-up** 방식으로 단계적으로 확인하고, 위험 온도에 도달하기
전에 fan/LED/buzzer/DC motor를 제어해 완화 조치를 취하는 시스템이다. 본
저장소는 이 동작을 재현 가능한 시뮬레이션으로 구현하고, 4가지 비교
모델(All-on / PiBase-style / Staged operation / SafeGuard proposed)의
추정 전력·에너지를 비교하여 절감 효과를 정량화한다.

## 시스템 구조

```
hardware_log.csv (또는 dummy)  ┐
                                 ├─ state machine (UWB→PIR/Camera→mmWave→Thermal→Actuator)
UWB/mmWave/Camera virtual log  ┘         │
                                          ▼
                    device activation (Cascading Wake-up, continuous/duty-cycle)
                                          │
                                          ▼
                    power model (추정 전력 timeline, energy by state)
                                          │
                                          ▼
        model comparison (All-on / PiBase / Staged / SafeGuard, mmWave profile 기록)
                                          │
                                          ▼
              report generator (표 CSV / 그림 PNG / 해석문·캡션·한계·Q&A TXT)
```

핵심 모듈(`src/`): `config.py`, `data_loader.py`, `virtual_sensors.py`,
`state_machine.py`, `device_activation.py`, `power_model.py`,
`model_comparison.py`, `report_generator.py`, `pipeline.py`. 대시보드는
`app/streamlit_app.py`이며 CLI 진입점은 `scripts/generate_paper_outputs.py`다.
자세한 구조는 저장소의 [README.md](https://github.com/yoontf0/safeguard-mmwave-simulator#readme)를 참고.

## 논문용 설명 (Paper-oriented notes)

- **Output-level virtual sensor simulation**: UWB/mmWave는 raw RF/radar
  signal(FMCW chirp, FFT spectrum 등)을 물리적으로 모델링하지 않고, 최종
  output 값(거리, presence flag, velocity, confidence 등)만 시나리오
  조건에 따라 합성한다.
- **mmWave sensor profile**: `C4001_24GHz_LOW_COST`(저가형 24GHz human
  presence radar)와 `TI_IWR6843ISK_REFERENCE`(TI IWR6843ISK 기반 reference
  profile) 두 가지를 선택할 수 있으며, 어느 쪽도 실제 하드웨어의 raw
  signal processing을 수행하지 않는다.
- **Estimated power model**: 모든 전력 값은 datasheet/typical-value 기반
  추정치이며 실측(measured power)이 아니다. 실측 로그(`power_measure_log.csv`)와
  교차 검증하는 경로가 마련되어 있다.
- **Continuous vs Duty-cycle**: ACTUATOR_CONTROL 단계의 두 제어 전략을
  항상 함께 계산/표시하여 비교 결과가 한쪽에 유리하게 편집되지 않았음을
  투명하게 보여준다.
- [Paper-ready Sample Outputs](sample_outputs/)에서 실제 생성된 표
  3종·그림 4종·해석문/캡션/한계/Q&A 문서 예시를 확인할 수 있다.

## 한계 (Limitations)

- 모든 결과는 특정 시나리오 조건 하의 **시뮬레이션 기반 추정치**이며
  실제 하드웨어 실측과 차이가 있을 수 있다.
- UWB/mmWave/Camera는 output-level virtual sensor simulation이므로 실제
  다중경로 반사, 노이즈 특성, OpenCV contour 연산 등 raw 신호 수준의
  현상은 반영하지 않는다.
- hardware_log.csv를 업로드해도 UWB/mmWave/Camera virtual sensor는
  대시보드 시나리오 설정에서 생성되며, 업로드된 CSV와 완전히 통합된 것은
  아니다.
- 자세한 한계 및 향후 개선점은 [sample_outputs/limitations_kr.txt](sample_outputs/limitations_kr.txt)
  참고.

## 프로젝트 정보

- Custom subagent 7종(`.claude/agents/`)으로 역할을 분리해 sensor
  simulation, hardware data engineering, state machine 검증, 전력
  최적화, 대시보드, 논문 작성, 심사위원 관점 QA를 각각 담당한다.
- 인용(citation)은 저장소의 [CITATION.cff](https://github.com/yoontf0/safeguard-mmwave-simulator/blob/main/CITATION.cff)를 참고.
