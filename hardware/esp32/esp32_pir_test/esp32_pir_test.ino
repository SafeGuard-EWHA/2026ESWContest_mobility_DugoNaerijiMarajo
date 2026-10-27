// SafeGuard PIR 테스트 (SparkFun EKMC4607112K)
// 보드: ESP32 Dev Module / 시리얼 모니터: 115200 baud
// 배선: PIR VCC→3V3, GND→GND, OUT→GPIO27
//
// 동작:
//  1) 전원 후 30초 워밍업 (이 동안은 값이 튈 수 있음)
//  2) 감지 시작/끝을 이벤트로 출력:  [PIR] 감지 시작 / 감지 끝 (지속 x.x초)
//  3) 1초마다 상태 JSON:  {"pir":1,"since_ms":1234,"count":3}
//  4) 감지 중에는 온보드 파란 LED(GPIO2) 켜짐
//
// 출력이 반대로(평소 1, 감지 시 0) 나오면 ACTIVE_LOW를 true로 바꾸세요.

const int  PIR_PIN    = 27;
const int  LED_PIN    = 2;
const bool ACTIVE_LOW = false;
const unsigned long WARMUP_MS = 30000;

int lastState = -1;
unsigned long changedAt = 0, lastPrint = 0;
unsigned long detectCount = 0;
bool warmDone = false;

int readPir() {
  int v = digitalRead(PIR_PIN);
  return ACTIVE_LOW ? !v : v;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT_PULLDOWN); // 이 PIR은 감지 시 HIGH, 평소엔 선을 놓음 → 풀다운 필수 (10/16 진단)
  pinMode(LED_PIN, OUTPUT);
  delay(300);
  Serial.println();
  Serial.println("[SafeGuard] PIR test start (GPIO27)");
  Serial.println("[PIR] 워밍업 30초... 센서 앞에서 움직이지 마세요");
}

void loop() {
  unsigned long now = millis();

  if (!warmDone && now >= WARMUP_MS) {
    warmDone = true;
    Serial.println("[PIR] 워밍업 끝. 이제 손을 흔들어 보세요");
  }

  int s = readPir();
  digitalWrite(LED_PIN, s ? HIGH : LOW);

  if (s != lastState) {
    if (lastState != -1 && warmDone) {
      if (s == 1) {
        detectCount++;
        Serial.print("[PIR] 감지 시작  #"); Serial.println(detectCount);
      } else {
        Serial.print("[PIR] 감지 끝   (지속 ");
        Serial.print((now - changedAt) / 1000.0, 1);
        Serial.println("초)");
      }
    }
    lastState = s;
    changedAt = now;
  }

  if (now - lastPrint >= 1000) {
    lastPrint = now;
    Serial.print("{\"pir\":"); Serial.print(s);
    Serial.print(",\"since_ms\":"); Serial.print(now - changedAt);
    Serial.print(",\"count\":"); Serial.print(detectCount);
    Serial.print(",\"warm\":"); Serial.print(warmDone ? "true" : "false");
    Serial.println("}");
  }
  delay(20);
}
