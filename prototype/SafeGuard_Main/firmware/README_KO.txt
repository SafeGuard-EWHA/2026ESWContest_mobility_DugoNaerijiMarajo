SafeGuard 선택용 ESP32 참고 펌웨어
================================

1. 이 파일의 용도와 현재 상태

esp32_reference/esp32_reference.ino는 A블록 담당자와 통신 규약을 맞출 때
참고할 수 있는 별도 예제입니다. 기존 A코드와 호환된다고 보장하지 않습니다.
기존 보드에 바로 덮어쓸 파일이 아닙니다. 메인 프로그램은 자체 모의 입력으로
먼저 진행할 수 있으며, 이 예제를 설치해야만 메인 작업을 시작하는 것은 아닙니다.
독립 ESP32 #2, 서보, UWB 처리 기능은 만들지 않았습니다.

이 작성 환경에는 Arduino CLI가 없어서 실제 ESP32 대상 컴파일·업로드·배선
시험을 하지 않았습니다. 실물 보드에 기록하지 않았습니다. 아래 공식 API를
기준으로 작성했으며, 선택한 보드와 라이브러리 조합에서 Verify가 필요합니다.
별도로 PC에서 GPIO/시리얼을 가짜 장치로 대체하고 실제 ArduinoJson 6.21.5와
7.4.2를 사용해 출력 기본 비활성, JSON null, 긴 입력 줄 폐기, 명령 재전송,
순서 역전, heartbeat 단절, ESTOP/재가동, 세션 인계의 상태 전이를 확인했습니다.
이 검사는 ESP32용 툴체인 빌드나 전기적 동작 시험을 대신하지 않습니다.

재현 가능한 호스트 검사:
  python3 tests/test_firmware_reference.py --arduinojson-dir /실제/ArduinoJson/경로

ArduinoJson 6/7의 소스 폴더와 g++가 필요합니다. 이 스크립트는 라이브러리를
자동 다운로드하지 않습니다. 출력 기본 비활성, 동기화용 telemetry/ACK,
보고 사이의 짧은 ESTOP 입력, 재가동, 세션 인계와 송신 크기를 검사합니다.
ArduinoJson 6.21.5와 7.4.2에서 이 검사가 통과했습니다.

2. 먼저 확인할 핀과 부품

다음은 보완 보고서의 계획값이며, 실제 배선으로 확인한 값이 아닙니다.

  PIR 입력                 GPIO 27
  SHT31 I2C SDA / SCL       GPIO 21 / GPIO 22, 주소 0x44
  팬 드라이버 제어          GPIO 25
  부저 드라이버 제어        GPIO 26
  선택적 물리 ESTOP 입력    GPIO 32

ESP32의 정확한 모델/개발보드가 다르면 이 번호가 없거나 사용할 수 없을 수
있습니다. A담당자가 보드 핀 표와 실제 배선을 대조한 후 상단 상수를 고칩니다.

ENABLE_ACTUATORS = false가 기본값입니다. 이 상태에서는 팬/부저 핀에 대해
pinMode나 digitalWrite를 호출하지 않고, 출력 명령의 ACK는 accepted:false,
reason:"actuation_disabled"입니다. OFF 명령도 승인하지 않습니다.
팬/부저의 물리적 OFF는 코드만으로 보장되지 않으므로 드라이버의 풀다운/풀업이
필요합니다. 센서는 기본적으로 활성화되어 있으며 I2C 통신 핀에는 신호가
나갑니다. 센서 핀도 아직 확인하지 않았다면 ENABLE_PIR와 ENABLE_SHT31을
false로 두고 시험하세요. 센서를 끈 경우 값은 null, valid는 false입니다.

팬과 부저 부하를 ESP32 GPIO에 직접 연결하지 않습니다. 실제 부하의 전압/전류에
맞는 MOSFET 또는 트랜지스터 드라이버, 게이트/베이스 저항, 부팅 중 OFF를 잡는
풀 저항, 부하용 전원, 공통 GND 등을 회로 담당자가 확인해야 합니다.
유도성 부하의 역기전력 보호 방법도 해당 팬/부하 데이터시트에 맞춰 확인합니다.
ESP32 입력에 5V를 직접 넣지 않도록 실제 PIR 출력과 SHT31 모듈의 I2C 풀업
전압을 확인합니다. 이 예제의 부저는 ON/OFF형 능동 부저 또는 드라이버를
가정합니다. 수동 피에조 부저의 주파수 생성/PWM은 구현하지 않았습니다.
FAN_ACTIVE_LEVEL / BUZZER_ACTIVE_LEVEL도 드라이버 회로에 맞춰야 합니다.

3. Arduino IDE 준비

  1) Arduino IDE에서 실제 보드에 맞는 Espressif Systems의 "esp32" 보드
     패키지를 설치하고 정확한 보드를 고릅니다. GPIO 계획은 일반 ESP32를
     전제로 하며 ESP32-C3/S3 등에 그대로 적용한다고 가정하지 않습니다.
  2) 라이브러리 관리자에서 다음을 설치합니다.
       - ArduinoJson, Benoit Blanchon: 6.21.x 또는 7.x
       - Adafruit SHT31 Library, Adafruit: readBoth가 있는 2.2.2 기준
       - Adafruit BusIO, Adafruit: SHT31 라이브러리의 의존성
     Arduino.h / Wire.h / esp_random.h / driver/gpio.h는 ESP32 보드
     패키지에서 제공합니다.
     ESP32Servo, DHT 라이브러리, ArduinoJson 5는 사용하지 않습니다.
  3) esp32_reference 폴더 안의 esp32_reference.ino를 엽니다.
  4) ENABLE_ACTUATORS=false를 유지하고, 센서 연결 여부와 핀을 확인합니다.
  5) 먼저 Verify(컴파일)만 수행합니다. A담당자의 기존 코드 백업 및 배선
     확인 후에만 실물 업로드 여부를 결정합니다.
  6) 시리얼은 115200 baud, 8N1입니다. 줄 끝은 LF 또는 CRLF를 사용합니다.
     한 포트는 메인 프로그램과 시리얼 모니터가 동시에 열지 않습니다.

ArduinoJson 6은 StaticJsonDocument<1536>, 7은 JsonDocument를 사용하도록
컴파일 시 버전을 분기합니다. 6/7 공통 deserializeJson, serializeJson,
is<T> API를 사용합니다. 실제 두 버전에서 컴파일 완료했다고 주장하지 않습니다.

4. 센서 데이터: ESP32 → Pi

500ms마다 JSON 한 줄을 보냅니다. 값이 유효하지 않으면 NaN, Infinity 또는
임의의 0 대신 JSON null을 보냅니다. true/false는 문자열이 아닌 JSON bool입니다.

{"type":"telemetry","seq":0,"uptime_ms":500,"boot_id":"0123456789abcdef","pir":null,"pir_valid":false,"temp_c":24.5,"temp_valid":true,"humidity":48.2,"humidity_valid":true,"estop":null,"estop_valid":false,"estop_latched":false,"fan_cmd":false,"buzzer_cmd":false,"actuators_enabled":false,"active_run":"","heartbeat_fault":true}

estop는 현재 물리 스위치 상태, estop_latched는 한 번 눌린 뒤 유지되는 정지
기억입니다. 짧게 눌렀다 놓아도 estop_latched:true가 다음 보고에 남으므로
Pi가 정지를 놓치지 않습니다. 재가동 허용은 별도의 실제 estop 해제 여부와
수동 요청을 함께 확인합니다. estop_valid:false이면 실제 스위치 상태를
확인한 것으로 취급하지 않습니다.

fan_cmd/buzzer_cmd는 현재 논리적 출력값, actuators_enabled는 출력 허용
설정, active_run은 MCU가 받아들인 Pi 실행 ID, heartbeat_fault는 현재
heartbeat 만료 여부입니다. 이 항목은 재접속·메인 재시작 시 상태 동기화에
사용합니다. 새 메인은 신선한 보고에서 세션과 출력값을 확인하기 전에는
초기 OFF 명령을 보내면 안 됩니다. 이전 보호 출력이 남아 있으면 보호 상태를
이어받아 해제 조건을 다시 확인해야 합니다. ACK만으로 실물 동작을 단정하지
않으며, MCU 재부팅·통신 단절 뒤에는 이전 ACK를 그대로 유지하지 않습니다.

PIR_WARMUP_MS 기본값은 예시 60000ms입니다. 실제 PIR의 준비 시간에 맞춰
수정합니다. 준비 시간에는 pir:null / pir_valid:false이므로 사람이 없다고
판정하면 안 됩니다. 준비 시간이 끝난 뒤에도 단순 디지털 PIR 입력은 배선
단선/센서 고장을 구별하지 못합니다. valid=true는 전기적 자가진단 성공이
아니라 "설정상 활성화되어 준비 시간이 지난 입력"이라는 의미입니다.

SHT31은 500ms 간격으로 readBoth를 호출하고, 실패 시 유효성을 false로
만들며 5초 간격으로 연결을 재시도합니다. 정상 읽기라도 유한수가 아니거나
온도가 -40~125°C, 습도가 0~100% 범위를 벗어나면 해당 값은 null입니다.
라이브러리의 측정 대기 약 20ms 및 I2C 처리 시간은 발생합니다. loop의
주기 제어에는 delay를 사용하지 않지만 완전한 실시간 제어기는 아닙니다.

boot_id는 부팅마다 만든 64비트 난수의 16자리 16진 문자열입니다. 보안 토큰이나
영구 일련번호가 아닙니다. uptime_ms는 millis 오버플로를 누적해 64비트로
표시합니다. seq는 uint32이며 재부팅하면 초기화됩니다.

5. heartbeat, 세션, 출력 명령, ACK

Pi는 먼저 heartbeat를 보내고 이후 500ms마다 seq를 증가시켜 보냅니다.

{"type":"heartbeat","run_id":"20261023T120000_123456","seq":1}

run_id는 1~64자의 영문/숫자/-/_/./: 문자열입니다. Pi 프로세스를 새로
시작할 때 새 run_id를 만듭니다. heartbeat seq는 0~4294967295 정수이며
같거나 작은 번호를 재전송해도 생존 시간이 갱신되지 않습니다.

heartbeat로 세션을 연 다음 명령을 보냅니다.

{"type":"command","run_id":"20261023T120000_123456","id":1,"fan":true,"buzzer":true}

id는 세션 안에서 증가하는 1~4294967295 정수입니다. fan/buzzer는 반드시
JSON true/false입니다. 0/1이나 "true" 문자열은 거부합니다.
응답 예(기본 비활성 상태):

{"type":"ack","run_id":"20261023T120000_123456","boot_id":"0123456789abcdef","id":1,"accepted":false,"fan_cmd":false,"buzzer_cmd":false,"reason":"actuation_disabled"}

ACK의 fan_cmd/buzzer_cmd는 펌웨어가 현재 유지하는 논리적 출력 명령입니다.
실제 팬 회전/부저 소리/릴레이 접점 피드백이 아닙니다. accepted:true도
실물 동작 확인을 대신하지 않습니다. ACK의 boot_id는 가장 최근 동기화한
telemetry의 MCU 부팅 ID와 일치해야 하며, 이전 부팅의 응답을 재사용하면
안 됩니다.

재시도 규칙:
  - 같은 run_id + id + 같은 명령 종류/출력값이면 GPIO에 재적용하지 않습니다.
    최근 32개 요청의 결과를 기억합니다. 이미 승인된 요청이라도 현재 출력이
    후속 명령으로 바뀌었으면 duplicate_superseded로 거부하며 옛 출력으로
    되돌리지 않습니다. ESTOP/heartbeat 만료도 이전 승인을 우선하지 않습니다.
  - 같은 id에 다른 종류/출력값을 붙이면 id_payload_conflict로 거부합니다.
  - 캐시에서 빠진 오래된 id 또는 순서가 역전된 id는 stale_id로 거부합니다.
  - 구문이 올바른 요청은 실행이 거부되어도 id를 소비합니다. 조건을 고친 뒤
    다시 시도하려면 새 id를 써야 합니다. 재전송이 갑자기 부하를 켜지 않습니다.
  - JSON 구문/필드 타입 오류, 다른 run_id는 명령 ID를 소비하지 않습니다.
    식별자까지 깨진 프레임은 ACK 대신 status의 오류 횟수를 증가시킵니다.
  - heartbeat는 별도 seq이며 command/rearm은 하나의 id 순서를 공유합니다.

세션 인계:
  - 최초 유효 heartbeat가 활성 run_id를 정합니다.
  - 다른 run_id는 기존 heartbeat가 3초 이상 끊긴 뒤에만 인수할 수 있습니다.
    메인 프로그램 재실행 직후 session_busy/run_mismatch가 보이면 새 세션의
    heartbeat를 유지하고 3초 뒤 새 id로 명령을 다시 보냅니다.
  - 인계할 때 팬/부저 출력과 ESTOP 래치를 유지합니다. 새 세션이라는 이유로
    이전 보호 출력을 OFF로 바꾸거나 정상 상태라고 간주하면 안 됩니다.
  - 인계된 이전 run_id는 이 ESP32 부팅 동안 재사용할 수 없습니다. 이전
    세션 8개를 보관하고 그 이상 인계는 session_history_full로 거부합니다.
    실행 중 무작정 보드를 재부팅하는 대신 출력 상태를 확인하고 담당자가
    정지/재시작 절차를 수행해야 합니다. 재부팅 시 RAM 기록은 사라집니다.
  - USB 링크는 신뢰된 로컬 연결을 전제로 합니다. 인증/암호화는 없습니다.

heartbeat가 3초 끊기면 fault와 누적 횟수를 기록합니다. 이미 켜져 있던 팬/
부저 보호 출력은 유지합니다. heartbeat가 다시 정상이어도 기존 출력을
자동으로 바꾸지 않으며 새 명령 또는 물리 ESTOP이 필요합니다.
전원 상실/ESP32 리셋 중에는 출력 유지가 보장되지 않습니다. 부팅 시 OFF로
초기화하고, 회로 수준의 정지/유지 정책은 실제 장치에 맞춰 별도로 검토합니다.

6. 선택적 ESTOP과 재가동

기본 ENABLE_ESTOP=false: 실제 결선이 확인되지 않았으므로
estop:null / estop_valid:false입니다. false(해제 상태)로 가장하지 않습니다.

회로 확인 후 활성화할 경우 ESTOP_ACTIVE_LEVEL과 ESTOP_INPUT_MODE를
실물에 맞춥니다. 현재 예시는 INPUT_PULLUP + LOW 활성으로, 단선 검출이나
안전 등급을 보장하는 회로가 아닙니다. 이 입력의 소프트웨어 처리는 물리적
부하 전원 차단 장치를 대체하지 않습니다. I2C/USB 처리로 검출 지연이 생깁니다.

활성 입력을 한 번이라도 읽으면 즉시 가능한 시점에 팬/부저를 OFF로 하고
estopLatched를 세웁니다. 버튼을 놓거나 heartbeat/세션이 바뀌어도 자동으로
풀지 않습니다. ESTOP가 200ms 연속 비활성이며 heartbeat가 살아 있을 때,
사용자의 명시적 재가동 요청을 새 id로 전달해야 래치를 해제합니다.

{"type":"rearm","run_id":"20261023T120000_123456","id":2}

성공 ACK의 reason은 rearmed_outputs_off, fan_cmd/buzzer_cmd는 false입니다.
재가동은 출력 복원이 아닙니다. 이후 별도의 새 command가 있어야 켜집니다.
옛 command 재전송이나 옛 rearm 재전송으로 다시 래치를 풀거나 켤 수 없습니다.
출력 비활성 모드에서는 rearm도 actuation_disabled로 거부합니다.
ESTOP 입력을 꺼 둔 상태의 rearm은 estop_input_disabled로 거부합니다.
래치가 없는 상태의 새 rearm은 estop_not_latched로 거부하며, 실행 중인
보호 출력을 끄지 않습니다.

7. 추가 status와 통신 한계

매초 type:"status" 행을 보냅니다. estop_latched, heartbeat_fault,
heartbeat_loss_count, actuators_enabled, fan_cmd, buzzer_cmd, rx_error_count,
tx_drop_count, last_fault가 포함됩니다. last_fault는 마지막 사건의 기록이므로
과거 오류 문자열이 남아 있어도 현재 heartbeat_fault 등과 구별해서 봅니다.
정지 래치·출력·활성 세션 등 제어 동기화에 필요한 항목은 telemetry에도
포함됩니다. status는 추가 진단 정보이며 별도로 로그에 보관할 수 있습니다.

입력은 LF로 끝나는 최대 511바이트 JSON 문자열입니다. CRLF도 받습니다.
넘친 줄/NUL이 있는 줄은 다음 LF까지 전부 버려 다음 정상 프레임과 분리합니다.
한 loop의 수신량과 송신 큐를 제한합니다. 송신 여유가 없으면 telemetry/status는
생략하고 ACK 공간을 우선 확보합니다. 연결이 멎어도 무한 대기하지 않습니다.
과도한 입력/물리 USB 버퍼 넘침까지 복구를 보장하지는 않습니다. 메인은 ACK
시간 제한, 동일 id 재시도, stale 데이터 판정을 유지해야 합니다.

8. 공식 참고 자료

ArduinoJson 6→7 문서/버전별 JsonDocument:
https://arduinojson.org/v7/how-to/upgrade-from-v6/
https://arduinojson.org/v6/api/jsonvariant/is/

Adafruit SHT31 공식 API/readBoth와 라이브러리 의존성:
https://adafruit.github.io/Adafruit_SHT31/html/class_adafruit___s_h_t31.html
https://github.com/adafruit/Adafruit_SHT31/blob/master/library.properties
https://learn.adafruit.com/adafruit-sht31-d-temperature-and-humidity-sensor-breakout/wiring-and-test

Espressif 공식 Arduino ESP32 GPIO/I2C:
https://docs.espressif.com/projects/arduino-esp32/en/latest/api/gpio.html
https://docs.espressif.com/projects/arduino-esp32/en/latest/api/i2c.html
https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/random.html
https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html
