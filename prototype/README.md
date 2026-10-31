# SafeGuard

차량 잔류 탑승자 보호 **연구·시연용 시제품** 소스 모음입니다.
UWB 보호자 거리, PIR/카메라 움직임 증거, 온도 입력을 상태 기계로 처리하고 ESP32에 보호 출력을 요청합니다.


**2026-10-31 운영 갱신:** [Pi 접속·첫 장치 연결 절차](docs/OPERATIONS.md) · [현재 상태](docs/STATUS.md) · [실내·외기 열 예측](docs/THERMAL_MODEL.md). 팀 Pi는 현재 접속 점검 모드이며 실제 제어 메인은 비활성입니다. 아래 기준본 설명과 과거 수동 실행 명령은 10월 28일 이력으로 남깁니다.

**팀원 PPT 자료:** [측정 원본·그래프·사진 안내](measurements/README.md). **10월 28일 선제 보호:** [구현·검증 패키지](maintenance/SafeGuard_Predictive_Control_20261028/README.md).

## 10월 28일 기준본의 출처와 범위

- 정리 기준일: 2026-10-28 (한국 시간).
- 현재 소스: 사용자가 Pi에서 가져온 `SafeGuard_Link_Debug.tar.gz`에 설치 확인된 `SafeGuard_Link_Fix_20261028`을 반영했습니다.
- 진단 묶음에 없던 CMake 빌드 파일, 기본 테스트·도구 등은 앞서 전달한 전체 `SafeGuard_Main` 패키지에서 보완했습니다. **Pi 전체를 새로 백업한 파일이 아닙니다.** 파일별 출처는 [SOURCE_ORIGINS.json](docs/SOURCE_ORIGINS.json)을 참고하세요.
- 이후 전달한 열 추정 모듈을 현재 실행 소스에 반영했습니다. 서보 해결은 사용자 보고로 기록했으며, 팀원의 별도 수정 소스·배선 변경 내역은 제공되지 않아 임의로 재구성하지 않았습니다.
- 현재 기준 설정은 **위험 온도 35°C / 서보 보호 각도 80° / 열 예측 ON / 60초 이내 도달 예측 시 선제 보호 ON**입니다. 사용자가 35°C·80° 저장을 확인했고, 후속 화면에서 추정 곡선 표시가 확인됐고 선제 보호 코드와 검증을 추가했습니다. GitHub 업로드는 Pi에 자동 배포되지 않습니다.
- 저장소의 `prototype/` 폴더에 장치 제어 소스를 모았습니다. 저장소 루트의 TwinLab 시뮬레이터와는 별도 실행 경로입니다.

## 구성

| 경로 | 용도 |
|---|---|
| `SafeGuard_Main/src/` | C++ 상태 기계, 입력 검증, 수동 정지 및 출력 제어 |
| `SafeGuard_Main/scripts/` | 센서 허브, UWB 리더, 카메라, 위치·날씨, 대시보드 |
| `SafeGuard_Main/configs/real_navigation_control.json` | 현재 소프트웨어 정지 방식의 기준 설정 |
| `SafeGuard_Software_Stop_20261024/firmware/SafeGuard_Software_Stop/` | ESP32 펌웨어 `SafeGuard_Software_Stop-0.3.0` |
| `SafeGuard_Software_Stop_20261024/run_control.py` | 펌웨어 확인 후 메인 실행 |
| `test_links.py` | 통신 복구 관련 14개 모의 테스트 |
| `maintenance/` | 과거 전달한 업데이트·진단·설치 도구 원본 보관 |
| `docs/` | 현재 검증 현황, 출처, 팀 작업 절차 |

`maintenance/` 및 각 `patch/`, `originals/`는 이력·비교용입니다. 현재 실행 파일은 `SafeGuard_Main/`입니다. **과거 설치 스크립트를 위에서부터 차례로 실행하지 마세요.** 버전별 해시 가드와 적용 전제가 다릅니다. 기본 프로젝트의 `README_BASE_20261023.md`, `firmware/esp32_reference`, 과거 검증 문서는 당시 참고 자료이며 현재 사용할 펌웨어나 최신 실측 성적표가 아닙니다.

## 현재 장치와 확인 범위

| 장치 | 구성 / 상태 |
|---|---|
| 호스트 | Raspberry Pi 5 |
| 출력 제어 | ESP32, CP2102 USB UART, 115200 baud |
| 온습도 | SHT31, SDA GPIO32 / SCL GPIO33 |
| 움직임 | PIR GPIO27, Pi Camera Module 3 |
| 보호자 거리 | DWM1001-DEV, 대상 앵커 `0CA7` |
| 팬 / 부저 | GPIO25 / GPIO26, 외부 12V 사용 |
| 서보 | GPIO13, 12V→5V 컨버터 사용. 사용자가 해결 보고. 원인·수정 내역 및 부하 시험은 별도 확인 필요 |
| mmWave | IWR6843ISK-ODS. 10월 28일 고장 보고 후 10월 31일 사용자 수리 완료 보고. 새 운영본 입력 연결·검증은 다음 실물 점검 대상 |

거리·온도·PIR 수신, 대체 판단을 통한 탑승 의심/온도 판단 진입, 실제 팬 두 개와 부저 작동 및 수동 정지 결과가 사용자 관찰로 확인됐습니다. 자세한 검증 한계는 [STATUS.md](docs/STATUS.md)를 참고하세요.

## 빌드와 테스트

Linux/Pi에서 CMake, C++17 컴파일러, `nlohmann-json` 헤더가 필요합니다. Pi 장치 런타임은 pyserial, NumPy, OpenCV, Picamera2 및 해당 OS의 카메라 드라이버를 사용합니다. ESP32 빌드는 Arduino-ESP32, Adafruit SHT31, ArduinoJson이 필요합니다. 현재 제공 자료만으로 모든 의존성 버전이 고정된 것은 아닙니다.

저장소 루트에서 `prototype/`로 이동한 뒤 실행합니다:

```bash
cd prototype
cmake -S SafeGuard_Main -B SafeGuard_Main/build -DCMAKE_BUILD_TYPE=Release
cmake --build SafeGuard_Main/build --parallel 2
ctest --test-dir SafeGuard_Main/build --output-on-failure
python3 test_links.py
python3 SafeGuard_Main/scripts/safeguard_uwb_reader.py --self-test
```

추가 JSON 헤더 경로가 필요하면 CMake에 `-DJSON_INCLUDE_DIR=/path/to/include`를 지정합니다. 위 테스트의 통과는 실제 하드웨어·차량에서의 동작 보증이 아닙니다.

## 기존 수동 실행 경로 — 10월 28일 이력

**이미 설치된 팀 Pi와 새로 복제한 작업 폴더를 구분하세요.** 기존 `~/SafeGuard_Main` 위로 무조건 복사하지 말고, 변경 파일을 검토한 뒤 적용합니다. 제어 설정의 USB 경로와 위치 파일 경로도 대상 장치에 맞게 확인해야 합니다. 위치 수신 서비스와 TLS 인증서는 소스 복제만으로 설치되지 않습니다.

기존 설치된 팀 Pi에서 사용하는 명령:

```bash
python3 -u ~/SafeGuard_Software_Stop_20261024/run_control.py --project ~/SafeGuard_Main
```

항상 수동 정지 유지 상태로 시작합니다. 화면의 정지 확인과 실제 출력 상태를 확인한 뒤 명시적으로 감시를 재개합니다. 종료는 대시보드 전체 정지 → 정지 확인 → 실제 출력 확인 후 수행합니다. 포트 8080을 다른 프로세스가 사용 중이면 중복 실행하지 않습니다.

## 10월 28일 시연 기준과 당시 확인 범위

- 임시 18°C 시험 후 위험 기준을 35°C로 복구했습니다. 설정 저장 확인과 실제 35°C 통합 동작 시험 완료는 구분합니다.
- 열 예측은 필수 개발 기능입니다. 현재 연구용 추정은 최근 10분 온도 이력과 문헌에서 적합한 시간상수로 향후 5분을 계산합니다. 차량 정확도는 미검증이며, 현재는 유효한 예측을 선제 보호 제어에 연결했습니다. 기존 판단 조건을 거쳐 60초 이내 35°C 도달 예상 시 팬·부저·서보 보호 출력을 요청합니다. 실측 온도 기반 보호도 유지합니다.
- 화면의 “향후 5분”은 예측 범위이지 35°C까지 남은 시간이 아닙니다. 준비 완료 후 “향후 5분 내 도달 추정 없음” 곡선이 확인됐습니다. 선제 보호 출력의 실제 통합 성공 결과는 아직 제출되지 않았습니다.
- 10월 31일 새 운영 코드의 방법과 한계는 [실내·외기 열 예측](docs/THERMAL_MODEL.md)을 우선합니다. 기존 실내 추세 기반 모듈과 촬영본은 이력으로 보존합니다.
- [열 추정 방법·문헌](maintenance/SafeGuard_Thermal_20261028/METHOD.md), [검증 및 한계](maintenance/SafeGuard_Thermal_20261028/VALIDATION.md)를 참고하세요.
- 핫팩을 이용한 센서 주변 가열은 차량 전체의 열 모델 검증이 아닙니다.
- PIR·카메라는 움직임 증거입니다. 호흡·생체 상태를 측정하지 않습니다.
- 물리 비상정지가 없습니다. 소프트웨어 정지는 PC·통신·MCU 정상 동작에 의존합니다.
- 통신 heartbeat 상실 시 팬·부저 보호 요청은 유지하고 서보 PWM을 해제하도록 설계되어 있습니다. USB 분리/프로그램 종료를 전체 정지 대신 사용하지 않습니다.
- 서보 PWM OFF는 전원 차단, 축 제동 또는 창문 원위치 복귀가 아닙니다. 현재 실제 창문 연결은 하지 않습니다.

## 팀 작업

[CONTRIBUTING.md](CONTRIBUTING.md)에 따라 기능별 브랜치와 PR을 사용합니다. 서보 담당자의 변경과 이 기준본은 비교 후 병합하세요. 현재 팀원별 최신 소스가 모두 합쳐졌다는 의미는 아닙니다.

일반 실행 로그, 위치 좌표 파일, 인증서 개인키, 토큰, 빌드 결과는 업로드하지 않습니다. `measurements/raw`의 검토된 측정·진단 로그는 원본 자료로 별도 보관합니다. GitHub 연결에 암호나 토큰을 채팅으로 공유할 필요는 없습니다.
