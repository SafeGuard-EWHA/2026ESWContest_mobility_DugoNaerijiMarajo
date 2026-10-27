# SafeGuard: UWB와 mmWave를 융합한 Cascading Wake-up 기반 차량 내 잔류 탑승자 선제 보호 시스템

**제24회 임베디드SW경진대회 자동차/모빌리티 부문 결선 제출 저장소** · 팀 두고내리지말아조 (윤현서, 최서현, 윤홍은, 이화여자대학교)

<img src="docs/presentation/img/benz/car_side_teddy.jpg" width="100%" alt="SafeGuard 시연 시제품">

| 제출 자료 | 위치 |
|---|---|
| 개발완료보고서 (PDF, 본문 20쪽) | [`2026ESWContest_모빌리티_두고내리지말아조_개발완료보고서.pdf`](docs/presentation/2026ESWContest_모빌리티_두고내리지말아조_개발완료보고서.pdf) |
| 작품소개서 (Word, 2쪽) | [`2026ESWContest_모빌리티_두고내리지말아조_작품소개서.docx`](docs/presentation/2026ESWContest_모빌리티_두고내리지말아조_작품소개서.docx) |
| 시연 동영상 (YouTube) | 업로드 후 링크 추가 |
| 레이더 영상 5종, 논문용 그림 7장, 실측 그래프 | 아래 본문 (페이지를 열면 바로 재생) |

| 폴더 | 내용 |
|---|---|
| [`prototype/`](prototype/) | **장치 제어 소스**: C++ 상태기계와 열 관측기(`SafeGuard_Main/src`), Python 센서 허브와 대시보드(`scripts`), ESP32 펌웨어, 측정 원본 |
| [`hardware/`](hardware/) | 블록 B 레이더 수신기(`mmwave/mmwave_reader.py`), 카메라 움직임 검출, ESP32 시험 스케치, 배선 가이드 |
| [`src/`](src/), [`app/`](app/), [`tests/`](tests/) | TwinLab 시뮬레이터 (상태기계, 가상 센서, 전력 모델, Streamlit 대시보드, pytest) |
| [`docs/figures/paper/`](docs/figures/paper/) | 논문용 그림 7장과 생성 스크립트 (실측 원본에서 재현) |
| [`docs/presentation/`](docs/presentation/) | 보고서, 소개서, 영상, 그림 생성 스크립트 |
| `B회신*_20261027/` | 레이더, 카메라 시험 원본 (CSV, 원본 바이트, 사진, 분석) |
| [`pic_red_benz/`](pic_red_benz/), [`pics/`](pics/) | 시연 시제품과 부품 사진 |

---

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://safeguard-mmwave-simulator.streamlit.app)
[![Source Code](https://img.shields.io/badge/Source-GitHub-181717?logo=github)](https://github.com/SafeGuard-EWHA/2026ESWContest_mobility_DugoNaerijiMarajo)
[![Paper-ready Outputs](https://img.shields.io/badge/Paper--ready-Outputs-blue)](docs/sample_outputs/)

> 위 배지의 GitHub/Streamlit 링크는 모두 실제 배포된 값으로 반영되어 있다.
> 배포 절차 자체를 다시 확인하려면 [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) 참고.

차량 내 잔류 탑승자 보호 시스템 **SafeGuard**를 위한 end-to-end agentic
simulator다. 실제 Raspberry Pi hardware log와 UWB/mmWave virtual sensor를
결합하여 event-driven state machine, actuator 제어, 추정 전력(estimated
power) 계산, 비교 모델 분석, 논문용 표/그림/해석문까지 자동 생성한다.

>
> 라이브 데모 : https://safeguard-mmwave-simulator.streamlit.app/ 

## 시연 시제품: 유아용 전동차 위 SafeGuard (2026.10.28)

빨간 유아용 전동차를 차량 실내 모형으로 쓰고, 뒷좌석 자리에 인형(잔류 탑승자 역할)을 앉혔다.
60 GHz 레이더(mmWave)는 운전대 앞 판에 붙여 좌석을 향하게 했고, 나머지 부품은 이름표를 붙여 옆에 배치했다.

<img src="docs/presentation/img/benz/car_side_teddy.jpg" width="100%" alt="전동차 옆모습과 인형, 운전대 앞 레이더">

| 위에서 본 전체 배치 | 정면: 운전대 앞 레이더 |
|---|---|
| <img src="docs/presentation/img/benz/car_top_full.jpg" width="100%"> | <img src="docs/presentation/img/benz/car_front_radar.jpg" width="100%"> |

<img src="docs/presentation/img/benz/car_side_top.jpg" width="100%" alt="옆에서 본 전체 배치와 이름표">

| 레이더 (IWR6843ISK-ODS) | 운전대 앞 판에 장착 |
|---|---|
| <img src="docs/presentation/img/benz/radar_close.jpg" width="100%"> | <img src="docs/presentation/img/benz/radar_on_dashboard.jpg" width="100%"> |

| UWB, Pi Camera, Raspberry Pi 5 | ESP32, PIR, 온습도센서, 팬, 부저 | 서보, PIR, 12V 배선 |
|---|---|---|
| <img src="docs/presentation/img/benz/uwb_pi_camera.jpg" width="100%"> | <img src="docs/presentation/img/benz/esp32_pir_sht31.jpg" width="100%"> | <img src="docs/presentation/img/benz/servo_pir.jpg" width="100%"> |

사진 23장 (긴 변 2000 px로 줄이고 위치 정보 제거): [`pic_red_benz/`](pic_red_benz/)

## 결선 하드웨어 결과 한눈에 보기

제24회 임베디드SW경진대회 자동차/모빌리티 부문 결선 시제품(두고내리지말아조)의 실측 결과다.
아래 영상과 그래프는 모두 시험 원본 CSV와 레이더 원본 바이트에서 다시 그린 것이다
(생성 스크립트: [`docs/presentation/`](docs/presentation/)). 움직이는 그림은 GIF라서 페이지를 열면 바로 재생되고,
고화질 MP4는 각 그림 아래 링크로 받을 수 있다.

### 논문용 그림 6장 (실측 원본 기반)

생성: [`docs/figures/paper/build_paper_figures.py`](docs/figures/paper/build_paper_figures.py) · 각 그림은 PNG(300 dpi)와 PDF(벡터)로 저장.
모두 한 사람, 한 번의 시험이라 프레임끼리 독립이 아니며, 일반화된 정확도로 쓰지 않는다.

**Fig. 1 UWB 거리 측정 특성.** 정지 구간 잡음 σ 3.5 cm / 6.7 cm, 이동평균 창이 커질수록 잡음은 줄고 지연은 늘어남 (N = 7은 약 1.6 s 지연). 정답 거리가 없어 정밀도만 보고 정확도는 주장하지 않음.

<img src="docs/figures/paper/fig1_uwb_ranging.png" width="100%" alt="Fig 1 UWB">

**Fig. 2 레이더 재실 판정.** 시험 3에서 빈자리 0%, 착석 100%였지만 퇴장 뒤 빈자리도 100% (유령 추적). 정지 착석 시험에서 차량용 cfg만 정확히 1명 95.7%.

<img src="docs/figures/paper/fig2_radar_occupancy.png" width="100%" alt="Fig 2 radar">

**Fig. 3 카메라 움직임 특징.** 사람이 움직일 때만 1% 기준을 넘고, 가만히 앉은 사람과 조명 변화는 대부분 판정되지 않음 (조명 0%).

<img src="docs/figures/paper/fig3_camera_feature.png" width="100%" alt="Fig 3 camera">

**Fig. 4 센서 상호보완.** 카메라만으로는 정지 착석을 12%만 잡고, 레이더는 100%지만 퇴장 뒤에도 100%. 사후 분석으로 "추적 주변 0.45 m 안에 0.5 s 동안 점 3개 이상" 조건을 더하면 퇴장 뒤 0%, 착석 100% (메인 코드 미반영, 해결 후보).

<img src="docs/figures/paper/fig4_multimodal.png" width="100%" alt="Fig 4 multimodal">

**Fig. 5 센서별 수신 주기.** 레이더 55 ms (누락 0), 카메라 100 ms, UWB 531 ms. UWB 99%가 1.1 s 안에 도착해 2 s 만료 기준 안쪽.

<img src="docs/figures/paper/fig5_sensor_timing.png" width="100%" alt="Fig 5 timing">

**Fig. 6 온도 판단 규칙 지도 (측정 아님).** `src/config.py` 규칙: 32 °C 이상 또는 35 °C 도달 예상 300 s 이하이면 PROTECT.

<img src="docs/figures/paper/fig6_thermal_rule_map.png" width="70%" alt="Fig 6 thermal rule">

**Fig. 7 열 예측 모델의 문헌 데이터 보정 (우리 측정 아님).** McLaren et al., Pediatrics 2005 Fig. 3의 곡선 7개를 읽은 값에 맞춘 결과: A = 23.0 °C, τ = 19.0 분. 곡선 하나씩 빼고 검증하면 35 °C 도달 시간 오차 평균 1.9 분, 5분 뒤 예측 RMSE 0.81 °C (단순 유지 1.47, 직선 1.04). 한 연구의 그래프 읽기 값이라 실차 검증이 아니며, 7개 중 6개 곡선은 이력 10분이 쌓일 때 이미 35 °C를 넘는다.

<img src="docs/figures/paper/fig7_thermal_literature.png" width="100%" alt="Fig 7 thermal literature">

PIR, SHT31, ESP32는 시간 기록이 있는 실측 로그가 아직 짧아(블록 A 시리얼 10줄) 통계 그림에서 뺐다.

### 레이더 점 구름 (위에서 본 모습, 시험 3, 약 4배속)

앉기 → 가만히 → 일어나 나감 → 다시 앉기. 사람이 나간 뒤에도 추적 2개가 남는 문제가 보인다.

<img src="docs/presentation/img/readme/pointcloud_topview.gif" width="100%" alt="레이더 점 구름 재생">

MP4 (1분 2초): [`SafeGuard_mmwave_pointcloud_test3.mp4`](docs/presentation/SafeGuard_mmwave_pointcloud_test3.mp4)

### 사람 추적과 점 연결 (TI People Tracking 데모 형식)

위: 점 구름과 최근 6초 추적 경로. 아래: 추적 0.45 m 안의 점을 같은 색으로 표시.
사람이 나간 뒤에는 원 안에 점이 하나도 없는데 추적 2개가 남는다.

<img src="docs/presentation/img/readme/tracking_test3.gif" width="100%" alt="사람 추적과 점 연결 영상">

MP4 (1분 2초): [`SafeGuard_radar_tracking_test3.mp4`](docs/presentation/SafeGuard_radar_tracking_test3.mp4)

<img src="docs/presentation/img/final/fig_tracking_assoc.png" width="100%" alt="사람 추적과 점 연결 정지 화면">

### 3D 군집 (DBSCAN)과 TI 트래커 추적

<img src="docs/presentation/img/readme/cluster3d_test3.gif" width="100%" alt="3D 군집 영상">

MP4: [`SafeGuard_radar_cluster3d_test3.mp4`](docs/presentation/SafeGuard_radar_cluster3d_test3.mp4)

<img src="docs/presentation/img/final/fig_cluster_pipeline.png" width="100%" alt="점 구름 처리 과정">

윗줄은 앉아 있을 때 군집 1개와 추적 1개가 일치한다. 아랫줄은 사람이 나간 뒤 군집은 0개인데 TI 트래커 추적은 2개 남는다.
군집으로 추적을 다시 확인하면 유령 추적을 걸러낼 수 있다 (해결 후보, 메인 코드 미반영).

### TI 데모 형식 대시보드 (X-Y, Doppler-Range, 좌석 영역 점 개수, 필터, 스펙트럼)

<img src="docs/presentation/img/readme/dashboard_test3.gif" width="100%" alt="시험 3 대시보드 영상">

MP4: [`SafeGuard_radar_dashboard_test3.mp4`](docs/presentation/SafeGuard_radar_dashboard_test3.mp4)

<img src="docs/presentation/img/readme/dashboard_rx60.gif" width="100%" alt="60초 수신 시험 대시보드 영상">

MP4 (55초): [`SafeGuard_radar_dashboard_rx60.mp4`](docs/presentation/SafeGuard_radar_dashboard_rx60.mp4).
스펙트럼의 가장 큰 성분은 표시만 하며, 호흡 정답이 없어 호흡수로 주장하지 않는다.

| 시험 3 대시보드 (정지 화면) | 60초 수신 대시보드 (정지 화면) |
|---|---|
| <img src="docs/presentation/img/final/dash_test3.png" width="100%"> | <img src="docs/presentation/img/final/dash_rx60.png" width="100%"> |

### 부록: Vital Signs 호흡수 (참고용)

<img src="docs/presentation/img/final/fig_vital_breath.png" width="100%" alt="레이더 호흡수와 직접 센 값 비교">

- **조건**: TI Vital Signs 펌웨어, 레이더 앞 약 0.95 m 착석, 거리 칸 11 고정, 안정 호흡(분당 12~13회), 친구가 날숨을 1분씩 직접 셈 (2026.10.24, Pi 5 수신)
- **결과**: 1분 중앙값 기준 오차 0.4~1.4회/분 (3차). 거리 자동이던 2차는 40~47% 낮게 나옴
- **한계**: 측정 2회뿐이고 거리와 호흡 속도가 함께 바뀌어 원인을 나눌 수 없음. 펌웨어 최대 출력 21.8회/분.
  People Tracking과 다른 펌웨어라 잔류 감지와 동시에 쓰지 못함. 심박은 정답 미측정. **정확도는 주장하지 않는다.**

### 시스템 구성과 실물

<img src="docs/presentation/img/final/system_diagram_crop.png" width="100%" alt="SafeGuard 시스템 구성도">

| 결선 시제품 전체 (2026.10.28) | 블록 B, C: Pi 5, 카메라, 레이더, UWB |
|---|---|
| <img src="docs/presentation/img/final/sys_overview.jpg" width="100%"> | <img src="docs/presentation/img/final/pi_radar_uwb.jpg" width="100%"> |
| **블록 A: ESP32, 12V 팬, 부저** | **레이더 정지 착석 시험 배치 (2026.10.27)** |
| <img src="docs/presentation/img/final/blockA_fan.jpg" width="100%"> | <img src="docs/presentation/img/final/radar_test_setup.jpg" width="100%"> |

### 60 GHz 레이더 측정 결과 (IWR6843ISK-ODS, TI 3D People Tracking)

**1. 감지 영역을 차 실내 크기로 줄이자, 가만히 앉은 1명을 5분 동안 95.7% 정확히 1명으로 판정했다.**
TI 원본 cfg(6 m 방 기준)에서는 같은 조건에서 0%였다 (벽 다중 반사로 유령 추적 2~5개).

<img src="docs/presentation/img/final/fig_still_tests.png" width="100%" alt="정지 착석 시험 A/B/C">

**2. 하차 후 추적이 남는 시간.** 원인은 정지 추적 소거 시간 `static2free 3000`(약 165초)으로 분석했다.

<img src="docs/presentation/img/final/fig_pointcloud.png" width="100%" alt="시험 3 점 구름 4장면">

<img src="docs/presentation/img/final/fig_test3_timeline.png" width="100%" alt="시험 3 타임라인">

| Raspberry Pi 5 수신 안정성 | 카메라 조명 변화 시험 |
|---|---|
| <img src="docs/presentation/img/final/fig_pi_fps.png" width="100%"> | <img src="docs/presentation/img/final/fig_cam_light.png" width="100%"> |
| 460초 동안 8,363프레임, 누락 0, 깨짐 0 (18.2 fps) | 천장 조명 끔/켬 4회, 움직임 오검출 0회 |

### 센서 검증 그래프 (시간 축 기록)

**카메라와 레이더 같은 시간축 비교 (시험 3).** 카메라는 움직일 때만, 레이더는 가만히 앉아 있어도 잡는다. 퇴장 뒤 레이더 추적이 남는 구간도 함께 보인다.

<img src="docs/presentation/img/final/fig_val_fusion.png" width="100%" alt="카메라와 레이더 비교">

**레이더 수신 품질.** 시험 3(460초)과 Pi 60초 수신 모두 누락 0, 깨짐 0, 프레임 간격 중앙값 55 ms.

<img src="docs/presentation/img/final/fig_val_rates.png" width="100%" alt="레이더 수신 품질">

**7월 1차 시제품 로그 (Pi 4B, DHT22, PIR, 릴레이, 180초).** 결선 장비(SHT31, ESP32) 이전 시제품의 데이터 로거 기록.

<img src="docs/presentation/img/final/fig_val_logger.png" width="100%" alt="1차 시제품 로그">

자세한 시험 기록: [`hardware/mmwave/people_tracking/README.md`](hardware/mmwave/people_tracking/README.md), [`hardware/HANDOFF_BLOCK_B.md`](hardware/HANDOFF_BLOCK_B.md)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 구조](#2-시스템-구조)
3. [실행 방법](#3-실행-방법)
4. [입력 CSV 형식](#4-입력-csv-형식)
5. [Dashboard 사용법](#5-dashboard-사용법)
6. [Output-level Virtual Sensor Simulation](#6-output-level-virtual-sensor-simulation)
7. [Estimated Power Model](#7-estimated-power-model)
8. [Continuous vs Duty-cycle Actuator Policy](#8-continuous-vs-duty-cycle-actuator-policy)
9. [Paper-ready Export](#9-paper-ready-export)
10. [Sample Data & Demo Mode](#10-sample-data--demo-mode)
11. [테스트](#11-테스트)
12. [한계와 향후 개선점](#12-한계와-향후-개선점)

---

## 1. 프로젝트 개요

SafeGuard는 보호자가 차량에서 이탈한 후 차량 내부에 잔류 탑승자가 있는지
단계적으로(Cascading Wake-up) 확인하고, 위험 온도에 도달하기 전에
fan/LED/buzzer/DC motor를 제어해 완화 조치를 취하는 시스템이다.

이 저장소는 SafeGuard의 동작을 **재현 가능한 시뮬레이션**으로 구현하고,
아래 4가지 비교 모델(All-on / PiBase-style / Staged operation / SafeGuard
proposed)의 추정 전력·에너지를 비교하여 절감 효과를 정량화한다. 모든
결과는 Streamlit dashboard와 CLI 스크립트 양쪽에서 동일한 core simulation
engine(`src/`)을 통해 생성되며, pytest로 상태 전이·전력 계산의 정확성을
검증한다.

## 2. 시스템 구조

```
.
├── app/
│   └── streamlit_app.py       # 대시보드 (Demo Mode, Evidence Panel, 9개 섹션)
├── src/
│   ├── config.py               # 상수, 임계값, ScenarioConfig, Demo Mode 프리셋
│   ├── data_loader.py          # hardware_log.csv 검증/정규화/dummy 생성
│   ├── virtual_sensors.py      # UWB/mmWave/Camera output-level virtual sensor
│   ├── state_machine.py        # SafeGuard event-driven state machine
│   ├── device_activation.py    # Cascading Wake-up 기반 device ON/OFF 표
│   ├── power_model.py          # 추정 전력/에너지 계산
│   ├── model_comparison.py     # All-on/PiBase/Staged/SafeGuard 비교
│   ├── report_generator.py     # 표/그림/해석문/캡션/한계/Q&A 생성
│   └── pipeline.py             # 위 모듈을 엮는 end-to-end 오케스트레이션
├── scripts/
│   ├── run_dashboard.sh        # streamlit 대시보드 실행
│   ├── run_tests.sh            # pytest 전체 실행
│   ├── generate_paper_outputs.py  # CLI로 paper-ready export 번들 생성
│   ├── clean_outputs.py        # outputs/ 초기화
│   └── regenerate_sample_data.py  # sample_data/ CSV 재생성(참고용)
├── sample_data/                # 재현 가능한 예시 hardware_log.csv 3종
├── hardware/                   # 실제 Raspberry Pi 전용 코드 (dashboard는 import하지 않음)
│   ├── pi_hardware_logger.py   # gpiozero/RPi.GPIO/adafruit_dht/board 사용
│   └── requirements-pi.txt     # 하드웨어 전용 의존성 (웹 배포 requirements.txt와 분리)
├── tests/                      # pytest 단위/통합 테스트
├── outputs/
│   ├── csv/                    # 논문용 표
│   ├── figures/                # 논문용 그림(PNG)
│   └── report/                 # 결과 해석문/캡션/한계/Q&A(TXT)
├── docs/                       # GitHub Pages 홈페이지 + paper-ready 샘플 산출물
├── .claude/agents/             # 커스텀 서브에이전트 7종 (역할 분리)
└── requirements.txt             # 웹 배포용 (Raspberry Pi 전용 패키지 미포함)
```

### 데이터 흐름

```
hardware_log.csv (또는 dummy)  ┐
                                 ├─ build_simulation_frame ─ run_state_machine
UWB/mmWave/Camera virtual log  ┘         │
                                          ▼
                         device_activation (Cascading Wake-up, continuous/duty-cycle)
                                          │
                                          ▼
                         power_model (추정 전력 timeline, energy by state)
                                          │
                                          ▼
                model_comparison (All-on / PiBase / Staged / SafeGuard 비교)
                                          │
                                          ▼
                    report_generator (표 CSV / 그림 PNG / 해석문·캡션·한계·Q&A TXT)
```

### SafeGuard state machine

```
UWB_DEPARTURE_CHECK → PIR_CAMERA_CHECK → MMWAVE_CHECK → THERMAL_PREDICTION → ACTUATOR_CONTROL
                                              │
                                              └─ (timeout) → FAIL_SAFE
```

## 3. 실행 방법

### 3.1 의존성 설치

```bash
python -m pip install -r requirements.txt
```

### 3.2 Dashboard 실행

```bash
bash scripts/run_dashboard.sh
# 또는
python -m streamlit run app/streamlit_app.py
```

브라우저에서 `http://localhost:8501` 접속.

### 3.3 테스트 실행

```bash
bash scripts/run_tests.sh
# 또는
python -m pytest tests/ -v
```

### 3.4 CLI로 paper-ready export 생성 (대시보드 없이)

```bash
# 기본 시나리오
python scripts/generate_paper_outputs.py

# Demo Mode 프리셋 사용
python scripts/generate_paper_outputs.py --demo normal_risk

# 실제/샘플 hardware_log.csv + 프리셋 조합
python scripts/generate_paper_outputs.py \
    --hardware-csv sample_data/sample_hardware_log_failsafe.csv \
    --demo mmwave_timeout

# 사용 가능한 --demo 옵션 확인
python scripts/generate_paper_outputs.py --list-demos
```

### 3.5 outputs/ 초기화

```bash
python scripts/clean_outputs.py
```

### 3.6 Streamlit Community Cloud 배포

익명 사용자가 PowerShell이나 로컬 설치 없이 웹 링크만으로 접속할 수
있도록 아래 순서로 배포한다 (GitHub push가 먼저 필요 — 자세한 절차는
[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) 참고).

1. [share.streamlit.io](https://share.streamlit.io) 접속 후 GitHub 계정으로 로그인
2. **"New app"** 클릭
3. **Repository**: 이 프로젝트를 push한 GitHub repo 선택
4. **Branch**: `main` 선택
5. **Main file path**: `app/streamlit_app.py` 입력 (entry point는 이
   경로로 고정되어 있으며, 저장소에 다른 `streamlit_app.py`가 존재하지
   않는다)
6. **Deploy** 클릭 → 수 분 내 `https://<app-name>.streamlit.app` 형태의
   공개 URL이 발급된다

배포 환경 참고사항:

- `requirements.txt`(저장소 루트)만 설치되며, `gpiozero`/`RPi.GPIO`/
  `adafruit_dht`/`board` 등 Raspberry Pi 전용 패키지는 포함되어 있지
  않다. 이 패키지들은 `hardware/pi_hardware_logger.py`에서만 사용되고
  `hardware/requirements-pi.txt`로 별도 관리되므로 Cloud 환경에서
  import 오류가 발생하지 않는다.
- 업로드 없이도 dummy 데이터로 바로 실행되며, 사이드바에서
  `sample_data/`의 예시 CSV를 선택하면 실제 파일 업로드 없이도 CSV 기반
  결과를 볼 수 있다.
- "Paper-ready 자동 생성" 버튼은 서버의 `outputs/`에도 저장하지만,
  다운로드 버튼은 그 순간 메모리에 읽어들인 바이트를 서빙하므로 여러
  익명 사용자가 동시에 접속해도 서로의 다운로드 내용이 섞이지 않는다.

## 4. 입력 CSV 형식

### hardware_log.csv (필수 스키마)

| 컬럼 | 설명 |
|---|---|
| `time_s` | 경과 시간(초) |
| `state` | 원본 로그 상태 라벨(파이프라인이 재계산하므로 참고용) |
| `pir_val` | PIR 감지(0/1) |
| `temp_c` | DHT22 온도(°C) |
| `humidity` | DHT22 습도(%) |
| `relay_fan` / `relay_led` / `relay_buzzer` / `relay_motor` | 릴레이 채널 상태(0/1, ON/OFF, True/False 모두 허용) |
| `cpu_temp_c` | Raspberry Pi CPU 온도(°C) |
| `cpu_percent` | Raspberry Pi CPU 사용률(%) |

- 파일이 없으면 `src/data_loader.py`가 재현 가능한 dummy 데이터를 생성한다.
- 결측치는 선형보간, DHT22 read failure는 자동 감지·보간되며
  `dht22_failure_flag`로 표시된다.
- **주의**: UWB/mmWave/Camera virtual sensor는 hardware_log.csv가 아니라
  대시보드 시나리오 설정(occupant_exists, mmwave_mode 등)에서 별도로
  생성된다. 자세한 내용은 [10. Sample Data & Demo Mode](#10-sample-data--demo-mode) 참고.

### power_measure_log.csv (선택, 실측 검증용)

| 컬럼 | 설명 |
|---|---|
| `time_s` | 경과 시간(초) |
| `state` | 상태 라벨 |
| `voltage_v` | 실측 전압(V) |
| `current_a` | 실측 전류(A) |
| `power_w` | 실측 전력(W) |

`src/data_loader.load_power_measure_log()`로 읽어 estimated power model과
교차 비교하는 용도로만 사용한다(파이프라인 필수 입력 아님).

## 5. Dashboard 사용법

사이드바 구성:

- **Demo Mode**: 4개 버튼(Normal Risk / No Occupant / mmWave Timeout
  Fail-safe / Duty-cycle Optimized)으로 완결된 시나리오를 한 번에 적용.
- **Failure Scenario Simulation**: mmWave timeout, PIR false positive,
  Camera dark, DHT22 fail, No occupant, Guardian nearby 개별 edge case 토글.
- **시나리오 파라미터**: duration, occupant exists, guardian departure
  time, 온도/습도, light/motion condition, mmWave mode, actuator policy
  (continuous/duty_cycle), hardware_log.csv 업로드.

메인 화면 구성:

| 섹션 | 내용 |
|---|---|
| Evidence Panel | 데이터 소스(Dummy/실측), 센서 유형(Virtual), 전력 유형(Estimated) 표시 |
| 1. Scenario Summary | 현재 적용된 시나리오 파라미터 표 |
| 2. State Machine Event Log | 상태 전이 이력 |
| 3. Sensor Timeline | UWB 거리, DHT22 온도 timeline |
| 4. State Timeline | SafeGuard 상태 timeline |
| 5. Power Timeline | 추정 전력 timeline (선택된 정책 기준) |
| 6. Energy by State | state별 추정 에너지 |
| 7. Model Comparison | All-on/PiBase/Staged/SafeGuard(continuous+duty-cycle) 비교표·그래프 |
| 8. Paper-ready Korean Summary | 결과 해석문 + "Paper-ready 자동 생성" 버튼(11개 파일 저장/다운로드) |
| 9. Judge Mode Feedback | 약점/반박/추가실험/데모포인트 + "예상 Q&A 보기" |

시나리오 조건을 바꾸면 `st.cache_data`가 변경을 감지해 전체 파이프라인이
자동으로 재계산된다.

## 6. Output-level Virtual Sensor Simulation

UWB(DWM1001-DEV 등가)와 mmWave 센서 데이터는 **raw RF/radar signal(FMCW
chirp, FFT spectrum, 다중경로 반사 등)을 물리적으로 모델링하지 않는다.**
대신 시나리오 조건(보호자 이탈 시점, 탑승자 존재 여부, mmWave 모드 등)에
따라 최종 output 값(거리, presence flag, velocity, confidence 등)만
합성하는 **output-level virtual sensor simulation**이다.

지원하는 mmWave edge case (mmWave mode):

| 모드 | 설명 |
|---|---|
| `normal` | 정상 감지 (presence=1, 유효 거리 범위) |
| `no_occupant` | 탑승자 없음, presence 항상 0 |
| `intermittent` | 통신이 간헐적으로 끊김(무응답) |
| `timeout` | 센서가 전 구간 무응답 → FAIL_SAFE 유발 |
| `out_of_range` | presence는 감지되나 거리값이 유효 범위 밖 |

### mmWave Sensor Profile

mmWave는 단일 센서로 고정되지 않고, 사이드바의 **mmWave Sensor Profile**
셀렉트박스에서 아래 두 profile 중 선택할 수 있다. 두 profile 모두 raw
signal processing을 수행하지 않는 output-level simulation이며, 실제
해당 하드웨어를 사용했다는 의미가 아니다.

| Profile | Output fields | Confirmation rule |
|---|---|---|
| `C4001_24GHz_LOW_COST` (저가형 24GHz human presence radar) | response_ok, presence_flag, distance_m, velocity_mps, confidence_score | response_ok, presence=1, 0.2~3.0m, confidence≥0.6, 연속 5프레임 |
| `TI_IWR6843ISK_REFERENCE` (TI IWR6843ISK 기반 reference profile) | 위 필드 + point_count, angle_deg, micro_motion_score | 위 조건 + point_count≥3, confidence≥0.75(더 엄격), 연속 5프레임 |

선택한 profile은 결과 해석문 "0) Evidence" 섹션과 model comparison 표
(`mmwave_profile` 컬럼)에 그대로 기록되어 추적 가능하다.

Camera 감지도 OpenCV contour 연산을 재현하지 않고, `light_condition`에
따른 detection probability로 근사한다(예: `dark` 조건에서 감지 확률 급감).

## 7. Estimated Power Model

`src/config.py`의 `POWER_W` 딕셔너리는 **datasheet/typical-value 기반
추정치**이며 실측(measured power)이 아니다.

| 장치 | 추정 전력(W) |
|---|---|
| Raspberry Pi (idle) | 2.70 |
| Raspberry Pi (active) | 3.40 |
| Virtual UWB | 0.50 |
| PIR | 0.003 |
| Camera | 0.50 |
| Virtual mmWave | 0.80 |
| DHT22 | 0.013 |
| Relay channel (개당) | 0.36 |
| Fan | 0.50 |
| LED | 0.02 |
| Buzzer | 0.10 |
| DC motor | 0.80 |

실측 검증이 필요하면 `power_measure_log.csv`를 업로드해
`load_power_measure_log()`로 estimated 모델과 교차 비교할 수 있는 경로가
이미 마련되어 있다(자동 비교 UI는 아직 미구현, 향후 개선점 참고).

## 8. Continuous vs Duty-cycle Actuator Policy

ACTUATOR_CONTROL 단계의 두 가지 제어 전략을 **항상 함께** 계산/표시하여
비교 결과가 한쪽에 유리하게 편집되지 않았음을 투명하게 보여준다.

| 장치 | continuous | duty-cycle (개선 제어 전략) |
|---|---|---|
| Fan | 지속 ON | 10초 중 5초 ON |
| LED | 지속 ON | 2초 중 1초 ON |
| Buzzer | 지속 ON | 초기 10초 동안만 2초 중 1초 ON |
| DC motor | 지속 ON | 초기 5초만 ON |

FAIL_SAFE 상태에서는 안전을 위해 DC motor는 정책과 무관하게 항상 OFF다
(occupant_confirmed 되지 않았기 때문).

## 9. Paper-ready Export

대시보드의 "Paper-ready 자동 생성" 버튼 또는
`scripts/generate_paper_outputs.py`를 실행하면 아래 11개 파일이
`outputs/` 이하에 생성된다.

| 파일 | 위치 |
|---|---|
| `model_power_comparison.csv` | outputs/csv |
| `state_power_summary.csv` | outputs/csv |
| `event_log.csv` | outputs/csv |
| `figure_power_timeline.png` | outputs/figures |
| `figure_energy_by_state.png` | outputs/figures |
| `figure_model_energy_comparison.png` | outputs/figures |
| `figure_saving_vs_all_on.png` | outputs/figures |
| `paper_result_summary_kr.txt` | outputs/report |
| `figure_captions_kr.txt` | outputs/report |
| `limitations_kr.txt` | outputs/report |
| `judge_qna_kr.txt` | outputs/report |

(`export_manifest.txt`가 생성 목록 확인용으로 추가 저장된다.)

## 10. Sample Data & Demo Mode

`sample_data/`의 3개 CSV는 각각 대응하는 Demo Mode 프리셋과 **함께
사용할 때** 의도한 시나리오를 완전히 재현한다 (UWB/mmWave/Camera는
hardware_log.csv가 아니라 시나리오 설정에서 생성되기 때문).

| CSV | 짝지어 사용할 Demo Mode 버튼 | 결과 |
|---|---|---|
| `sample_hardware_log_normal_risk.csv` | Normal Risk Scenario | ACTUATOR_CONTROL까지 도달 |
| `sample_hardware_log_no_occupant.csv` | No Occupant Scenario | MMWAVE_CHECK에서 정지 (오탐 없이 escalation 안 됨) |
| `sample_hardware_log_failsafe.csv` | mmWave Timeout Fail-safe Scenario | FAIL_SAFE로 전이 |

각 CSV만으로도 `pir_val`/`temp_c` 패턴이 이미 다르게 설계되어 있어
(예: no_occupant는 pir_val 전 구간 0, temp_c가 32°C를 넘지 않음)
hardware 신호 자체의 차이도 Sensor Timeline에서 확인할 수 있다.
재생성하려면 `python scripts/regenerate_sample_data.py`.

## 11. 테스트

```bash
python -m pytest tests/ -v
```

상태 전이(경계값 포함), 전력/에너지 계산, device activation의 Cascading
Wake-up 배타성, 모델 비교, 리포트 생성 문구까지 pytest로 검증한다.

## 12. 한계와 향후 개선점

- 공모전에 제출한 논문에는 실측 전력 값을 이 시뮬레이터에 넣어서 결과 분석 후 제출하였지만, 
- 현재 이 시뮬레이터의 전력 값은 **추정 전력 모델**이며 실측이 아니다. 
- `outputs/report/limitations_kr.txt`(자동 생성)에 최신 상세 내용이 저장된다.
- UWB/mmWave는 **output-level virtual sensor simulation**이므로 실제
  다중경로 반사, 노이즈 특성 등 raw signal 수준의 현상은 반영하지 않는다.
- hardware_log.csv를 업로드해도 UWB/mmWave/Camera virtual sensor는 여전히
  시나리오 설정에서 생성된다(하드웨어 CSV와 완전히 통합된 것은 아님).
- 향후 개선점: 실제 전류 센서(INA219/INA226 등)를 이용한 estimated vs
  measured 오차율 정량화, mmWave/UWB raw signal 기반 재현, 다양한
  시나리오에 대한 민감도 분석, 실차 장기 운용 데이터 기반 FAIL_SAFE
  오탐/미탐률 평가.


