// SafeGuard ESP32 첫 연결 테스트 스케치
// 보드: ESP32 Dev Module / 시리얼 모니터: 115200 baud
// 성공 조건: 온보드 LED(GPIO2)가 1초 간격으로 깜빡이고, 시리얼 모니터에 카운트가 올라감.

const int LED_PIN = 2;   // DevKitC 온보드 파란 LED
unsigned long count = 0;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  delay(500);
  Serial.println();
  Serial.println("[SafeGuard] ESP32 hello test start");
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.printf("{\"hello\":%lu,\"led\":1}\n", count);
  delay(500);
  digitalWrite(LED_PIN, LOW);
  Serial.printf("{\"hello\":%lu,\"led\":0}\n", count);
  delay(500);
  count++;
}
