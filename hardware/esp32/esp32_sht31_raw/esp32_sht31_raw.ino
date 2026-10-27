// SHT31 원시 읽기 진단: 측정 명령 → 6바이트 → CRC 확인. 라이브러리 없이 직접.
// 시리얼 115200. SDA=32, SCL=33, 주소는 자동(0x44/0x45).
#include <Wire.h>

const int SDA_PIN = 32, SCL_PIN = 33;
uint8_t addr = 0;

uint8_t crc8(const uint8_t *d, int n) {
  uint8_t c = 0xFF;
  for (int i = 0; i < n; i++) { c ^= d[i]; for (int b = 0; b < 8; b++) c = (c & 0x80) ? (c << 1) ^ 0x31 : (c << 1); }
  return c;
}

bool cmd(uint16_t c) {
  Wire.beginTransmission(addr); Wire.write(c >> 8); Wire.write(c & 0xFF);
  return Wire.endTransmission() == 0;
}

void tryRead(const char *name, uint16_t c, int waitMs) {
  bool ok = cmd(c);
  delay(waitMs);
  int n = Wire.requestFrom((int)addr, 6);
  uint8_t b[6] = {0};
  for (int i = 0; i < n && i < 6; i++) b[i] = Wire.read();
  bool crcT = crc8(b, 2) == b[2], crcH = crc8(b + 3, 2) == b[5];
  float t = -45 + 175.0 * ((b[0] << 8) | b[1]) / 65535.0;
  float h = 100.0 * ((b[3] << 8) | b[4]) / 65535.0;
  Serial.printf("%-14s cmd=%s got=%d bytes [%02X %02X %02X %02X %02X %02X] crcT=%s crcH=%s -> T=%.2f C, H=%.2f %%\n",
                name, ok ? "ACK" : "NACK", n, b[0], b[1], b[2], b[3], b[4], b[5], crcT ? "ok" : "BAD", crcH ? "ok" : "BAD", t, h);
}

void setup() {
  Serial.begin(115200); delay(300);
  pinMode(SDA_PIN, INPUT_PULLUP); pinMode(SCL_PIN, INPUT_PULLUP);
  Wire.begin(SDA_PIN, SCL_PIN, 100000);
  for (uint8_t a : {0x44, 0x45}) { Wire.beginTransmission(a); if (Wire.endTransmission() == 0) { addr = a; break; } }
  Serial.printf("\n[SHT31 raw] addr=0x%02X\n", addr);
  if (addr) { cmd(0x30A2); delay(5); }   // soft reset
}

void loop() {
  // 매번 다시 찾기 (접촉 불량이면 있다/없다가 번갈아 나옴)
  addr = 0;
  Wire.setClock(100000);
  for (uint8_t a : {0x44, 0x45}) { Wire.beginTransmission(a); if (Wire.endTransmission() == 0) { addr = a; break; } }
  if (!addr) { Serial.println("no device"); delay(1000); return; }
  Serial.print("present at 0x"); Serial.println(addr, HEX);
  Wire.setClock(100000);
  tryRead("100kHz high", 0x2400, 20);
  tryRead("100kHz low", 0x2416, 10);
  Wire.setClock(10000);
  tryRead("10kHz high", 0x2400, 30);
  Serial.println();
  delay(1500);
}
