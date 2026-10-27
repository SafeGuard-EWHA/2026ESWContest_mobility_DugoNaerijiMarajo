# hardware/esp32 — 블록 A (ESP32 #1 센서·구동 노드)

마지막 확인: 2026-10-16, ESP32 DevKitC(ESP-32D) on COM5, esp32 core 3.3.12

## 지금 쓰는 코드

| 폴더 | 용도 | 상태 |
|---|---|---|
| `esp32_sensor_node/` | **최종 센서 노드.** PIR + SHT31을 1초마다 JSON으로 출력, `FAN`/`BUZ`/`PING` 명령 수신 | ✅ 10/16 동작 확인 |
| `esp32_hello_test/` | 첫 연결 확인 (LED 깜빡임 + 시리얼) | ✅ |
| `esp32_pir_test/` | PIR 단독 (감지 시작/끝 이벤트, 30초 워밍업) | ✅ |
| `esp32_sht31_test/` | SHT31 Adafruit 라이브러리 버전 | ⚠️ 감지는 되나 읽기 실패 → 쓰지 말 것 |
| `esp32_sht31_raw/` | SHT31 원시 읽기 진단 (CRC, 클럭별) | 진단용 |
| `esp32_i2c_finder/` | I2C 핀 조합 18개 자동 스캔 | 진단용 |
| `esp32_pir_diag/` | PIR 풀업/풀다운 비교 (선이 떠 있는지 판별) | 진단용 |
| `esp32_diag/`, `esp32_i2c_probe/` | 이전 진단 시도 | 참고용 |

## 실제 배선 (가이드와 다른 점 ⚠️)

| 부품 | 핀 | ESP32 | 비고 |
|---|---|---|---|
| SHT31 | VCC / GND | 3V3 / GND | |
| SHT31 | **SDA** | **GPIO32** | 가이드의 21이 아님 (왼쪽 핀 열로 몰기 위해) |
| SHT31 | **SCL** | **GPIO33** | 가이드의 22가 아님 |
| SHT31 | INT | 비움 | |
| PIR | VCC / GND / OUT | 3V3 / GND / GPIO27 | |
| (예정) 팬 MOSFET Q1 | 게이트 | GPIO25 | 220Ω 경유 |
| (예정) 부저 MOSFET Q2 | 게이트 | GPIO26 | 220Ω 경유 |

## 10/16에 알아낸 것 (같은 실수 반복 금지)

1. **SHT31 커넥터 밀림.** 보드 헤더는 5핀(`VCC GND SCL SDA INT`)인데 케이블 하우징은 4선이다. 한 칸 밀려 꽂히면 VCC가 빠져서 I2C 스캔에 아무것도 안 나온다. **INT 핀이 밖으로 남게** 꽂을 것. 접촉이 약해서 테이프로 고정 필요.
2. **SHT31 주소는 0x45** (0x44 아님).
3. **Adafruit_SHT31 라이브러리(v2.2.2)는 이 조합에서 읽기가 계속 실패**한다 (`begin()`은 성공, `readTemperature()`가 NaN). 원시 I2C로 읽으면 정상. 그래서 `esp32_sensor_node`는 라이브러리 없이 직접 읽는다.
4. **PIR은 감지 시 HIGH, 평소엔 출력을 놓아 버린다(떠 있음).** `INPUT_PULLDOWN` 필수. 풀다운 없으면 값이 무작위로 튄다.
5. **PIR은 움직이는 동안에도 0.3~1초 간격으로 0/1을 오간다.** 센서 노드는 1초 창 안에 한 번이라도 HIGH면 `pir:1`로 보낸다. 상태기계에서는 추가로 유지 시간을 둘 것.
6. 전원 후 PIR은 약 30초 워밍업.

## 확인된 출력 (10/16, 실내)

```
{"type":"boot","sht31":true}
{"type":"telemetry","seq":1,"uptime_ms":1001,"pir":1,"temp_c":23.80,"hum":56.73,"temp_valid":true}
{"type":"ack","cmd":"FAN","value":1}
{"type":"ack","cmd":"FAN","value":0}
```

SHT31 실내값: 23.5~23.8 °C, 56~57 %RH. 손을 대면 30 °C 이상으로 오른다 (정상 반응).

## 업로드 방법

- Arduino IDE: File → Open → `esp32_sensor_node/esp32_sensor_node.ino` → 보드 `ESP32 Dev Module`, 포트 COM번호 → 업로드 → 시리얼 모니터 **115200**
- 명령 테스트: 시리얼 모니터 입력창에 `PING`, `FAN 1`, `FAN 0` (줄 끝 "New Line")
- 업로드가 `could not open port`로 실패하면 **시리얼 모니터를 닫고** 다시
- 보드 매니저에서 "Arduino ESP32 Boards"(Nano ESP32용) 설치가 UTF-8 오류로 실패해도 무시. 필요한 건 **esp32 by Espressif Systems**

## 다음 할 일 (블록 A)

- [ ] SHT31 커넥터 테이프 고정
- [ ] A3: 12V 레일 무부하 시험 (퓨즈 → 비상정지 → 컨버터 #1·#2)
- [ ] A4: IRLZ44N + 팬 1개 → `FAN 1`로 실제 회전 확인 → 부저
