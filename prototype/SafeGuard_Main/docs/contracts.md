# 센서와 메인 사이 연결 규약

현재 제공된 A/B 구현 소스가 없으므로 이 문서는 **새로 구현한 메인의 입력 계약**이다. 기존 A/B 펌웨어와의 호환 완료 선언이 아니다. 센서 수집과 최종 판단은 분리하고, `src/core.cpp`의 단일 FSM만 보호 상태를 결정한다.

## 공통 원칙

Python hub → C++는 JSON 한 객체와 LF 한 개를 보낸다. 값이 없으면 `null` 또는 `valid:false`를 사용한다. `false`와 숫자 0은 서로 다른 값이다. `source`, 실행 ID, 순서, 시각을 확인한 뒤 입력을 사용한다. `REAL` 프로필은 DEMO 센서값을 거부한다. 하드웨어 DEMO에서 가상으로 바꿀 수 있는 것은 명시된 온도와 외기 프리셋뿐이다.

`rx_monotonic_s`는 **같은 Pi, 같은 부팅 세션**의 수신 단조시각이다. MCU `uptime_ms`를 여기에 복사하지 않는다. UWB는 기존 reader의 원래 시각을 보존한다. MCU는 로컬 수신시각을 추가하고 원래 `boot_id`, `seq`, `uptime_ms`도 보존한다. 중복 패킷을 새 증거로 갱신하지 않는다.

## C: UWB

포함된 `scripts/safeguard_uwb_reader.py`는 기존 v1.1.0 파일의 바이트를 그대로 사용한다. 115200/8N1, 보호자 0CA7, MA7와 시간 만료 처리를 유지한다. main은 이미 평균을 낸 `distance_m`에 MA7을 다시 적용하지 않는다. hub는 UART 설정/역할/lec를 변경하지 않는다.

## A: ESP32

UART 115200, 한 줄에 telemetry 하나. 참고 펌웨어의 예시는 다음과 같다. 아래 숫자는 **형식 설명용**이며 실행 기록이 아니다.

```json
{"type":"telemetry","boot_id":"example-boot","seq":1,"uptime_ms":500,"pir":false,"pir_valid":true,"temp_c":null,"temp_valid":false,"humidity":null,"humidity_valid":false,"estop":false,"estop_valid":true,"estop_latched":false,"fan_cmd":false,"buzzer_cmd":false,"actuators_enabled":false,"active_run":"","heartbeat_fault":true}
```

hub는 같은 boot의 seq가 증가하고 uptime이 역행하지 않는지 확인한다. 다른 boot로 바뀌면 과거 이벤트를 초기화한다. MCU의 실제 입력 시각과 Pi의 수신시각은 서로 다른 기준임을 로그에 남긴다.

명시적인 `source`/`mode`가 있으면 각각 `REAL_ESP32`/`REAL`이어야 한다. 참고 MCU 코드처럼 이 두 필드를 생략할 수는 있지만 `DEMO`라고 표시한 입력을 REAL로 바꾸지 않는다. `estop`은 물리 스위치의 현재 상태이고 `estop_latched`는 짧은 누름도 기억한 정지 상태다. `fan_cmd`/`buzzer_cmd`는 MCU가 적용한 출력 명령이며 실제 회전·소리 센서값이 아니다. 실제 구동 모드에서는 여섯 상태 필드의 유효성, 현재 부팅과 heartbeat로 확립된 `active_run`을 확인한 뒤에만 명령을 보낸다. 누락 필드를 OFF/해제로 가정하지 않는다.

Pi → ESP32 명령에는 `run_id`, 양의 정수 `id`, JSON bool인 `fan`과 `buzzer`가 들어간다. 재전송은 같은 ID와 같은 내용이며, ACK는 같은 run/ID, 현재 `boot_id`와 적용된 명령값을 돌려준다. 이전 부팅의 ACK는 거부한다. 하드웨어 ACK도 실제 팬 회전 증거는 아니다.

메인 재시작 때 MCU에 ON 출력이 남아 있으면 보호 요구를 복원하고 기존 복귀·수동 해제 조건을 유지한다. 이때 탑승자를 임의로 CONFIRMED로 만들지 않는다. MCU 상태가 만료되면 과거 ACK를 무효화하고, MCU 재시작·통신 복구 후 현재 보호 요구를 새 명령 ID로 다시 전송한다. 전원이 실제로 끊겨 있던 시간 동안 물리 출력이 유지되었다는 보장은 아니다.

`ESTOP` 해제는 센서 스위치 복귀와 사용자 재무장 요청을 모두 필요로 한다. 실제 구동에서는 **ESP32의 rearm ACK가 승인된 다음** C++ FSM 재무장을 허용한다. 거절·유실되면 ESTOP을 유지하고 수동 재시도할 수 있다. 보호 중 임의의 rearm 요청은 ESP32로 전달하지 않는다.

## B: Camera

Picamera2로 영상을 받고 고정 ROI의 프레임 차분 면적과 연속 프레임 조건을 검사한다. 설정에는 해상도, ROI, 면적, 프레임 수가 포함된다. 이는 사람 식별기가 아니다. 분석 활성화와 카메라 하드웨어 전원 차단은 구분한다.

정규화 메시지에는 `type:camera`, `source:REAL_CAMERA`, 공통 seq/run/rx 시각, `valid`, `motion`이 들어간다. 이 연결부의 실제 카메라 동작과 ROI 임계값은 Pi에서 확인해야 한다.

## B: mmWave

**현재 연결부는 TI 바이너리 UART/TLV 파서를 포함하지 않는다.** 선택된 TI 데모·버전·cfg·원시 프레임이 제공되지 않았으므로 임의의 TLV 번호를 정하거나 점 개수를 presence로 바꾸지 않았다. B 담당 파서는 선택한 펌웨어의 공식 규격으로 원시 프레임과 대상 ROI·검출 지속성을 검증한 뒤 아래 계약을 출력해야 한다.

```json
{"type":"mmwave","schema_version":1,"source":"REAL_MMWAVE","run_id":"worker-example","seq":1,"rx_monotonic_s":123.0,"valid":true,"health":"ok","evidence":false,"evidence_kind":"presence","validated":false}
```

위 시각 123.0 역시 형식 예시다. 실제 worker는 현재 Pi의 수신시각을 넣어야 한다. 이 JSON을 복사해 실시간 데이터처럼 재생하면 오래된 입력으로 거부된다.

`hardware.mmwave_json_port`는 이 계약을 출력하는 **동일 Pi의 B worker가 연결한 로컬 시리얼/PTY**를 위한 것이다. TI 센서 데이터 포트를 그대로 지정하면 작동하지 않는다. worker의 run/seq와 원래 Pi 단조시각을 보존하며, 과거·중복·역순 프레임을 새 증거로 만들지 않는다.

`health:ok`와 `evidence:false`는 정상 미검출이다. 통신 장애와 다르다. `validated:true` 및 `hardware.mmwave_validated:true`는 실제 firmware/ROI/검출 조건의 확인을 나타내야 하며, 연결만 됐다는 의미로 켜면 안 된다. 필수 검출 목표는 presence/미세 움직임이며, 호흡은 별도 검증한 추가 기능이다.

## 외기와 Thermal

외기 입력 계약은 `type:ambient`, `source:REAL_AMBIENT`, 공통 run/seq/rx, `valid`, `temp_c`이다. 실제 API 어댑터·키·지역 설정은 아직 연결되지 않았다. 현재 REAL hub는 외기를 무효로 보고한다. API 발표시각/조회시각/출처와 만료 정책을 실제 제공기관 규격에 맞춰 추가해야 한다.

REAL 예측 모델도 보정 전 기본 비활성이다. 유효한 실내온도가 위험 기준 이상인 경우에는 검증된 보호 경로에서 반응형 판단을 할 수 있다. R/C/Q 숫자, DEMO 온도와 예측 곡선을 실제 측정·성능 수치로 사용하지 않는다.
