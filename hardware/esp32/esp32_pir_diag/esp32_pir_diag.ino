// PIR 배선 진단: GPIO27을 풀다운/풀업으로 번갈아 읽어서
//  - 센서가 실제로 신호를 내는지(어느 쪽이든 같은 값)
//  - 선이 떠 있는지(풀다운이면 0, 풀업이면 1로 끌려감)
// 를 구분한다. 시리얼 115200.
const int PIR_PIN = 27;

void measure(const char *mode, int pinmode) {
  pinMode(PIR_PIN, pinmode);
  delay(50);
  int hi = 0, n = 0, toggles = 0, last = -1;
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) {
    int v = digitalRead(PIR_PIN);
    if (last != -1 && v != last) toggles++;
    last = v; hi += v; n++;
    delay(2);
  }
  Serial.print(mode); Serial.print("  HIGH비율="); Serial.print(100.0 * hi / n, 1);
  Serial.print("%  토글="); Serial.println(toggles);
}

void setup() { Serial.begin(115200); delay(300); Serial.println("\n[PIR diag] start"); }

void loop() {
  measure("PULLDOWN", INPUT_PULLDOWN);
  measure("PULLUP  ", INPUT_PULLUP);
  Serial.println();
}
