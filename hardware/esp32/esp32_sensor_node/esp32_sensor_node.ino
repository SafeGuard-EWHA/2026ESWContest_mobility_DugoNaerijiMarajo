// SafeGuard ESP32 #1 센서·구동 노드 (블록 A 2단계용)
// 보드: ESP32 Dev Module / 시리얼: 115200
//
// 배선 (하드웨어 연결 가이드 4.3절):
//   PIR  : VCC->3V3, GND->GND, OUT->GPIO27
//   SHT31: VCC->3V3, GND->GND, SDA->GPIO32, SCL->GPIO33   ※ 10/16 실측 확인. 주소 0x45
//          (5핀 헤더 VCC GND SCL SDA INT에 4선 하우징 → INT 핀이 남게 꽂을 것)
//   PIR은 감지 시 HIGH, 평소 출력이 떠 있음 → INPUT_PULLDOWN 필수 (10/16 진단)
//   Q1(팬)  게이트 <- GPIO25 (220Ω),  Q2(부저) 게이트 <- GPIO26 (220Ω)   ※ 아직 안 꽂아도 됨
//
// 출력: 1초마다 JSON 한 줄
//   {"type":"telemetry","seq":12,"uptime_ms":12000,"pir":1,"temp_c":27.3,"hum":45.1,"temp_valid":true}
// 입력: 한 줄 명령 (시리얼 모니터에서 입력, 줄바꿈 "새 줄")
//   FAN 1 / FAN 0 / BUZ 1 / BUZ 0 / PING
//   응답: {"type":"ack","cmd":"FAN","value":1}

#include <Wire.h>
// SHT31은 라이브러리 없이 직접 읽음: Adafruit_SHT31 v2.2.2가 이 보드에서 감지는 되지만 읽기가 계속 실패함 (10/16 확인)

const int PIN_PIR = 27;
const int PIN_FAN = 25;
const int PIN_BUZ = 26;
const int PIN_LED = 2;
const int PIN_SDA = 32;
const int PIN_SCL = 33;

uint8_t shtAddr = 0;         // 0이면 미연결
bool shtOk = false;
unsigned long seq = 0;
unsigned long lastTx = 0;
bool pirSeen = false;        // 1초 창 안에 한 번이라도 HIGH였는지 (PIR 펄스 놓치지 않게)
String cmdBuf;

uint8_t crc8(const uint8_t *d, int n) {
  uint8_t c = 0xFF;
  for (int i = 0; i < n; i++) { c ^= d[i]; for (int b = 0; b < 8; b++) c = (c & 0x80) ? (c << 1) ^ 0x31 : (c << 1); }
  return c;
}

bool initSHT() {
  const uint8_t addrs[2] = {0x45, 0x44};   // 우리 보드는 0x45
  for (uint8_t a : addrs) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      shtAddr = a;
      Wire.beginTransmission(a); Wire.write(0x30); Wire.write(0xA2); Wire.endTransmission();  // soft reset
      delay(5);
      return true;
    }
  }
  shtAddr = 0;
  return false;
}

// 단발 측정(고정밀, clock stretching 없음) → CRC 확인 후 °C, %RH
bool readSHT(float &t, float &h) {
  if (!shtAddr) return false;
  Wire.beginTransmission(shtAddr); Wire.write(0x24); Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;
  delay(20);
  if (Wire.requestFrom((int)shtAddr, 6) != 6) return false;
  uint8_t b[6];
  for (int i = 0; i < 6; i++) b[i] = Wire.read();
  if (crc8(b, 2) != b[2] || crc8(b + 3, 2) != b[5]) return false;
  t = -45.0f + 175.0f * ((b[0] << 8) | b[1]) / 65535.0f;
  h = 100.0f * ((b[3] << 8) | b[4]) / 65535.0f;
  return true;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT_PULLDOWN);
  pinMode(PIN_FAN, OUTPUT); digitalWrite(PIN_FAN, LOW);
  pinMode(PIN_BUZ, OUTPUT); digitalWrite(PIN_BUZ, LOW);
  pinMode(PIN_LED, OUTPUT);
  Wire.begin(PIN_SDA, PIN_SCL);
  shtOk = initSHT();
  delay(300);
  Serial.printf("{\"type\":\"boot\",\"sht31\":%s}\n", shtOk ? "true" : "false");
}

void handleCommand(const String& line) {
  String s = line; s.trim(); s.toUpperCase();
  if (s.length() == 0) return;
  int sp = s.indexOf(' ');
  String cmd = sp > 0 ? s.substring(0, sp) : s;
  int val = sp > 0 ? s.substring(sp + 1).toInt() : 0;
  if (cmd == "FAN")      { digitalWrite(PIN_FAN, val ? HIGH : LOW); }
  else if (cmd == "BUZ") { digitalWrite(PIN_BUZ, val ? HIGH : LOW); }
  else if (cmd == "PING"){ val = 1; }
  else { Serial.printf("{\"type\":\"error\",\"msg\":\"unknown cmd\"}\n"); return; }
  Serial.printf("{\"type\":\"ack\",\"cmd\":\"%s\",\"value\":%d}\n", cmd.c_str(), val);
}

void loop() {
  // 명령 수신 (줄 단위)
  delay(5);
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { handleCommand(cmdBuf); cmdBuf = ""; }
    else if (cmdBuf.length() < 64) cmdBuf += c;
  }
  // PIR은 감지 중에도 0.3~1초 펄스로 토글됨 → 1초 창 동안 HIGH가 한 번이라도 있으면 1
  if (digitalRead(PIN_PIR)) pirSeen = true;

  // 1초 주기 telemetry
  unsigned long now = millis();
  if (now - lastTx >= 1000) {
    lastTx = now; seq++;
    int pir = pirSeen ? 1 : 0;
    pirSeen = false;
    digitalWrite(PIN_LED, pir ? HIGH : LOW);     // PIR 감지 시 온보드 LED 켜짐
    float t = NAN, h = NAN;
    if (!shtOk) shtOk = initSHT();               // 커넥터 접촉이 돌아오면 자동 재연결
    bool tv = shtOk && readSHT(t, h);
    if (shtOk && !tv) shtOk = false;             // 읽기 실패 → 다음 주기에 재초기화
    Serial.printf("{\"type\":\"telemetry\",\"seq\":%lu,\"uptime_ms\":%lu,\"pir\":%d,", seq, now, pir);
    if (tv) Serial.printf("\"temp_c\":%.2f,\"hum\":%.2f,\"temp_valid\":true}\n", t, h);
    else    Serial.printf("\"temp_c\":null,\"hum\":null,\"temp_valid\":false}\n");
  }
}
