// SafeGuard 배선 진단 v2: I2C 스캔(SDA=D33, SCL=D32) + PIR(D27) 풀다운/풀업 양쪽 읽기
// pd = 내부 풀다운으로 읽은 값, pu = 내부 풀업으로 읽은 값
//   pd==pu 이면 센서가 핀을 확실히 구동 중(떠 있지 않음)
//   pd=0,pu=1 이면 핀이 떠 있음(OUT 선 접촉 불량)
#include <Wire.h>
const int PIN_PIR = 27;

void scanI2C() {
  int n = 0;
  Serial.print("{\"type\":\"i2c_scan\",\"found\":[");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { if (n++) Serial.print(","); Serial.printf("\"0x%02X\"", a); }
  }
  Serial.printf("],\"count\":%d}\n", n);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(33, 32);
  delay(300);
  Serial.println("{\"type\":\"diag_boot\",\"ver\":2}");
  scanI2C();
}

unsigned long last = 0; int n = 0;
void loop() {
  if (millis() - last >= 250) {
    last = millis(); n++;
    pinMode(PIN_PIR, INPUT_PULLDOWN); delayMicroseconds(200); int pd = digitalRead(PIN_PIR);
    pinMode(PIN_PIR, INPUT_PULLUP);   delayMicroseconds(200); int pu = digitalRead(PIN_PIR);
    Serial.printf("{\"t_s\":%.2f,\"pd\":%d,\"pu\":%d}\n", millis() / 1000.0, pd, pu);
    if (n % 40 == 0) scanI2C();
  }
}
