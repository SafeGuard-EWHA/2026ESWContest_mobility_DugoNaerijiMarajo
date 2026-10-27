# SafeGuard 메인 프로그램

**현재 버전: 0.1.1 (2026-10-23 재검토 수정본).** 초기화·센서 경고, ESP32 재시작·통신 복구, 짧은 비상정지, 입력 출처와 부팅 구분 문제를 재현하고 수정했습니다. 검토 결과와 실행한 검사는 `docs/code_review_20261023.md`에 있습니다. 기존 0.1.0 대신 이 버전을 사용합니다.

이 패키지는 **여러 센서의 입력을 한 상태기계로 모아 판단하는 C++17 메인**과 Python 센서 연결부, 상태 화면을 제공합니다. 지금 성공한 UWB 코드를 유지하면서 A/B블록을 붙일 자리를 마련한 버전입니다.

현재 확인된 실물 진척은 Pi 5의 OS·SSH·카메라 인식과 촬영, C블록의 실제 UWB JSON·7점 평균·보호자 노드 전원 끊김과 복구입니다. **이 새 메인 프로그램의 전체 센서·팬·부저 연결은 아직 실물 검증 전**입니다. 이전 발표자료의 릴레이·DHT22 프로토타입과 시뮬레이터 실적은 현재 ESP32·SHT31·mmWave 통합 완료와 구분합니다.

## 1. 처음에는 무엇을 실행하나

처음 실행할 것은 `bash scripts/run_demo.sh`입니다. 이것은 **SOFTWARE SIMULATION, 즉 가상 입력으로 프로그램의 판단 순서를 확인하는 실행**입니다. 센서를 추가 연결하지 않아도 됩니다. 실제 측정 성능이나 실제 팬 동작을 보여 주는 실행은 아닙니다.

| 실행 명령 | 설정 파일 | 입력 | 기본 구동 |
|---|---|---|---|
| `bash scripts/run_demo.sh` | `configs/simulation.json` | 가상 거리·감지·온도·고장 | 소프트웨어에서만 모사 |
| `bash scripts/run_demo.sh --hardware` | `configs/demo.json` | 실제 감지 입력 + 표시된 DEMO 온도·외기 프리셋 | DRY_RUN |
| `bash scripts/run_real.sh` | `configs/real.json` | 실제 입력만 사용 | DRY_RUN |

**DRY_RUN은 출력 요청을 계산하고 표시하지만 실제 구동 명령을 보내지 않는 설정**입니다. 하드웨어 DEMO/REAL에서는 이를 성공 ACK로 꾸미지 않으며 `NOT_SENT_DRY_RUN`으로 구분합니다. 가상 ACK는 SIMULATION에서만 사용합니다.

하드웨어 DEMO와 REAL의 기본 설정에서는 A/B 포트가 비어 있고 카메라 분석도 꺼져 있습니다. 따라서 이 입력들은 무효로 남습니다. UWB가 잘 나와도 전체 흐름이 보호 동작까지 가지 않는 것이 정상입니다. 미연결 센서를 자동으로 `감지됨`으로 채우지 않습니다.

## 2. Windows에서 Pi로 옮기기

기존 `~/safeguard_c` 폴더는 그대로 둡니다. 새 패키지는 `~/SafeGuard_Main`에 별도로 풉니다. 기존 UWB 프로그램이 실행 중이면 **그 프로그램이 실행 중인 Pi SSH 창에서 `Ctrl+C`**로 종료합니다. 같은 UWB 포트를 두 프로그램이 동시에 열면 안 됩니다. UWB의 USB나 Pi 전원은 그대로 둡니다.

1. 받은 ZIP을 Windows의 `C:\SafeGuard_Main.zip`에 둡니다.
2. Pi와 노트북을 현재 Pi가 접속하는 핫스팟에 연결합니다. 현재 팀 환경은 `safeguardhotspot`입니다.
3. **Windows의 새 PowerShell 창**에서 아래 명령을 실행합니다.

```powershell
scp C:\SafeGuard_Main.zip pi@safeguard.local:/home/pi/
ssh pi@safeguard.local
```

비밀번호는 Pi 계정 `pi`의 비밀번호입니다. 예전 IP 주소가 항상 유지된다고 가정하지 않습니다. `safeguard.local`로 연결되지 않으면 현재 핫스팟에서 확인한 Pi IP를 사용합니다.

4. 접속 후 프롬프트가 `pi@safeguard`로 바뀌면 **이제부터 명령은 Pi에서 실행**됩니다.

```bash
python3 -m zipfile -e ~/SafeGuard_Main.zip ~
cd ~/SafeGuard_Main
bash scripts/install_pi.sh
bash scripts/build.sh
bash scripts/run_demo.sh
```

설치는 처음 한 번이면 됩니다. 빌드는 C++ 소스를 실행 파일로 만드는 작업입니다. 다음 실행부터는 아래 두 줄이면 됩니다.

```bash
cd ~/SafeGuard_Main
bash scripts/run_demo.sh
```

## 3. 노트북에서 상태 화면 보기

메인 실행 창은 켜 둡니다. **Windows PowerShell을 하나 더 열어** 아래 명령을 실행합니다.

```powershell
ssh -N -L 8080:127.0.0.1:8080 pi@safeguard.local
```

로그인 뒤 화면이 조용히 멈춰 있는 것이 정상입니다. Pi의 로컬 상태 화면을 노트북으로 연결하는 창이므로 그대로 둡니다. 노트북 브라우저에서 아래 주소를 엽니다.

<http://localhost:8080>

화면에는 실행 모드와 입력 출처, FSM 상태, UWB, 감지 입력, 온도 입력, 보호 출력 요청과 ACK 상태가 표시됩니다. 화면의 해제·재무장 버튼은 **메인에 요청**을 보냅니다. 버튼을 눌렀다고 조건을 무시하고 즉시 해제되는 것은 아닙니다.

종료할 때는 메인이 실행 중인 Pi 창에서 `Ctrl+C`를 누릅니다. 로그가 남습니다. SSH 터널 창도 `Ctrl+C`로 닫습니다. 실제 구동을 연결한 이후에는 프로그램 종료를 물리 비상정지 대신 사용하지 않습니다. 통신 상실은 보호의 자동 해제 조건이 아닙니다.

## 4. 가상 시나리오 실행

실행 중인 메인을 `Ctrl+C`로 종료한 뒤 다음 시나리오를 실행합니다. 한 번에 한 개만 실행합니다.

| 명령 | 확인하는 판단 |
|---|---|
| `bash scripts/run_demo.sh normal` | 이탈 → 1차 감지 → mmWave 검증 → 온도 판단 → 보호 요청 |
| `bash scripts/run_demo.sh mmwave_fault` | mmWave 장애에서 PIR AND Camera에 근거한 SUSPECTED 경로 |
| `bash scripts/run_demo.sh unknown` | 장애 AND 불충족을 UNKNOWN으로 유지 |
| `bash scripts/run_demo.sh api_fault` | 외기 입력 장애와 현재 온도에 따른 반응형 판단 |
| `bash scripts/run_demo.sh estop` | 비상정지 우선, 스위치 복귀만으로 자동 재가동하지 않음 |

예를 들어 20초만 실행하려면 다음과 같습니다.

```bash
bash scripts/run_demo.sh mmwave_fault --duration 20
```

가상 시나리오의 감지 결과·온도·ACK는 실측 데이터가 아닙니다. `simulation.json`의 이탈 유지시간 1초는 빠른 흐름 확인용이며, 실제 설정의 10초와 구분됩니다. 실물 시연에는 `--hardware`를 사용하고 실제 센서 입력을 연결해야 합니다. `--hardware`에 가상 장애 시나리오 이름을 함께 넣는 기능은 제공하지 않습니다.

## 5. 지금 성공한 실제 UWB를 새 메인에서 읽기

가상 실행을 종료하고 다음 명령을 실행합니다.

```bash
bash scripts/run_real.sh
```

차량측 J-Link serial `000760217939`로 USB 포트를 찾고 보호자측 ID `0CA7`의 거리를 읽습니다. `/dev/ttyACM0`을 영구 고정값으로 가정하지 않습니다. 기존 UWB reader는 센서 허브가 자동 실행하므로 별도로 띄우거나 파이프로 연결하지 않습니다.

**차량측의 `lec` 거리 출력이 이미 켜져 있어야 합니다.** USB·전원을 그대로 유지했다면 다시 명령을 보낼 필요 없습니다. 이 패키지는 펌웨어를 바꾸거나 `lec`를 임의로 토글하지 않습니다.

재부팅·USB 재연결로 출력이 꺼진 경우에만 메인을 종료하고 다음 순서로 수동으로 켭니다.

```bash
python3 scripts/safeguard_uwb_reader.py --list
```

표시된 차량측 포트를 확인한 뒤 아래의 `실제_포트`를 그 경로로 바꿉니다. 예시 문자열을 그대로 입력하지 않습니다.

```bash
python3 -m serial.tools.miniterm 실제_포트 115200 --eol CR
```

이미 `DIST,...`가 나오면 `lec`를 입력하지 않습니다. 아무 거리 출력도 없으면 Enter를 두 번 눌러 `dwm>`를 확인하고 `lec`를 한 번 입력합니다. 거리가 나오면 **Ctrl+]**로 miniterm만 종료하고 `bash scripts/run_real.sh`를 실행합니다. USB는 빼지 않습니다.

실제 입력을 읽는 단계에서도 `actuation.enabled=false`가 기본입니다. 현재 미연결 A/B는 무효이며 실측 외기나 열 보정값도 제공되지 않았으므로, 이것을 전체 시스템 완료로 보지는 않습니다.

## 6. 메인의 전체 판단 흐름

1. `INIT`: 입력과 설정 확인.
2. `STANDBY`: 보호자 거리 감시.
3. `DEPARTURE_CHECK`: 유효 거리가 **5m 초과**로 설정 시간 동안 계속 유지되는지 확인.
4. `PRIMARY`: 유효한 PIR 또는 Camera 움직임이 있으면 mmWave로 진행.
5. `MMWAVE`: 정상적인 presence/미세 움직임 증거가 지속되면 `CONFIRMED`.
6. mmWave 장애 시 `FAIL_SAFE`: PIR과 Camera의 최근 유효 감지가 모두 있으면 `SUSPECTED`, 아니면 `UNKNOWN`과 장애 표시.
7. `THERMAL`: 현재 선택 온도와 유효한 35°C 도달시간 예측으로 위험 판단.
8. `PROTECTION`: Fan/Buzzer 요청과 응답 확인. 실제 동작 여부는 별도 확인.

`UNKNOWN`은 탑승자가 없다는 뜻이 아닙니다. 거리 데이터가 끊겨도 0m나 보호자 복귀로 처리하지 않습니다. 비상정지 `ESTOP`은 어느 단계보다 우선합니다.

보호 중에는 한 프레임 미검출로 출력을 해제하지 않습니다. 유효한 복귀 조건과 수동 해제 조건을 사용합니다. 비상정지 해제 뒤에도 수동 재무장을 거쳐 다시 시작합니다. 복귀 4m·3초, 센서 유효시간 등 제공 설정은 **초기 구현값**이며 검증된 성능값이 아닙니다.

최신 컨설팅에 따라 본선 mmWave 핵심 목표는 **presence/미세 움직임 검출**입니다. 호흡은 실제 설치 조건에서 안정성이 확인될 때 추가 기능으로 제시합니다. UART 데이터나 점 구름만 수신된 것을 생명체·호흡 검출로 표시하지 않습니다.

## 7. A/B를 붙이기 위해 필요한 다음 자료

메인 설치와 가상 실행은 지금 바로 진행할 수 있습니다. 아래 자료는 **실물 연결을 정확히 맞추기 위해** 필요합니다.

1. **A의 현재 ESP32 코드와 실제 핀 연결표:** PIR·SHT31·비상정지·Fan/Buzzer, 시리얼 출력 예시, 실제 명령과 ACK 형식. 제공 참고 코드가 있더라도 실제 배선 확인 없이 기존 보드에 덮어쓰지 않습니다.
2. **B의 TI 레이더 정보:** 정확한 보드 리비전·펌웨어/데모 이름과 버전, 사용 `.cfg`, 원시 UART 로그, 이미 있는 파서. TI의 바이너리 출력은 일반 JSON과 다르므로 현재 `mmwave_json_port`에 그대로 넣으면 안 됩니다.
3. **기존 열 모델/보정 자료:** R·C·열유입값의 근거, 외기 입력 방법, 가열·냉각 로그. 없으면 REAL 예측은 꺼 둡니다. 임시 숫자를 실측 보정값으로 포장하지 않습니다.

`configs/real.json`에서 `hardware.esp32_port`, `hardware.mmwave_json_port`, `hardware.camera_enabled` 등을 실제 자료에 맞춥니다. `mmwave_validated=true`는 UART 연결 성공 표시가 아니라 실제 설치·판정 조건을 확인한 뒤 사용하는 설정입니다. `required`의 기본 `false`는 단계적 연결을 위한 것이며 누락된 센서를 정상으로 만드는 기능이 아닙니다.

실제 구동을 켜면 ESP32의 부팅 ID, 현재 제어 세션, 출력 명령 상태와 비상정지 기억을 먼저 확인합니다. 이 상태 필드를 보내지 않는 기존 A 코드는 `WAITING_CONTROLLER`에 머무르므로 `docs/contracts.md`에 맞춰 연결해야 합니다. 참고 펌웨어에도 해당 필드를 포함했습니다. 메인을 재시작했을 때 이미 켜져 있는 보호 출력은 유지하며, ESP32 재부팅·통신 복구 뒤에는 현재 보호 요청을 새 명령으로 다시 전달합니다. ACK와 보고된 출력 명령 상태는 실제 팬 회전 측정값이 아닙니다.

카메라 분석을 켤 때 필요한 패키지는 다음으로 추가 설치할 수 있습니다.

```bash
bash scripts/install_pi.sh --camera
```

Pi 카메라가 이미 인식됐다는 것과 새 움직임 분석의 ROI·임계값이 적절하다는 것은 다른 확인입니다. 사람 식별 기능으로 설명하지 않습니다.

## 8. 로그와 실제 성능의 구분

실행별 로그는 `runs/` 아래 새 폴더에 저장됩니다. 그 안의 `current_state.json`은 최신 상태이고, `config_used.json`은 그 실행에 사용한 설정입니다. 원시 입력은 `raw_input.jsonl`, 상태 기록은 `states.jsonl`, 표 형식 요약은 `telemetry.csv`에 남습니다. 상태 화면은 센서 허브가 자동으로 띄웁니다. 설정과 입력 출처를 함께 기록하므로 SIMULATION, DEMO, REAL 결과를 구분할 수 있습니다.

REAL에서는 열 모델이 `enabled=false`, `calibrated=false`로 시작합니다. 따라서 현재 파일 안의 R·C·열유입 후보값을 실제 예측 성능으로 사용하지 않습니다. 유효한 실내온도가 공급되면 프로젝트 기준 35°C에 대한 반응형 판단을 구성할 수 있으며, 예측은 보정된 입력과 파라미터를 연결한 뒤 켭니다.

팬 요청, ACK 수신, 실제 팬 회전은 서로 다른 증거입니다. 이 프로그램의 상태 로그만으로 실제 팬·부저 동작이나 전력 절감률이 확인되는 것은 아닙니다. 실제 전력 결과에는 Pi 전원·12V 구동부·보호자 전원의 측정 범위를 표시합니다. 최신 컨설팅은 12V 직류 측정과 USB 인라인 전력계 사용을 인정하며, 짧은 피크를 분석할 때만 전력 로거를 권장했습니다.

세부 근거 대응은 `docs/requirements_trace.md`, 단계별 완료 기준은 `docs/bringup_checklist.md`를 참고합니다.

