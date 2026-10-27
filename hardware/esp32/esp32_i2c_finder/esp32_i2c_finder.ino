// SafeGuard I2C 핀 찾기: 여러 SDA/SCL 조합을 돌며 SHT31(0x44/0x45)이 어디 붙었는지 찾는다.
// 시리얼 모니터 115200. 한 번 전체 스캔 후 5초마다 반복.
#include <Wire.h>

const int PAIRS[][2] = {
  {32, 33}, {33, 32}, {21, 22}, {22, 21}, {25, 26}, {26, 25}, {16, 17}, {17, 16},
  {18, 19}, {19, 18}, {4, 5}, {5, 4}, {13, 14}, {14, 13}, {27, 14}, {14, 27}, {23, 19}, {19, 23}
};
const int NPAIRS = sizeof(PAIRS) / sizeof(PAIRS[0]);

int scanPair(int sda, int scl) {
  Wire.end();
  pinMode(sda, INPUT_PULLUP); pinMode(scl, INPUT_PULLUP);   // 내부 풀업 (보드에 풀업 없을 때 대비)
  Wire.begin(sda, scl, 50000);                              // 50kHz 느리게
  Wire.setTimeOut(20);
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("  SDA=GPIO"); Serial.print(sda); Serial.print(" SCL=GPIO"); Serial.print(scl);
      Serial.print("  -> 0x"); if (a < 16) Serial.print("0"); Serial.print(a, HEX);
      if (a == 0x44 || a == 0x45) Serial.print("  <== SHT31 여기!");
      Serial.println();
      found++;
    }
  }
  return found;
}

void setup() {
  Serial.begin(115200);
  delay(500);
}

void loop() {
  Serial.println();
  Serial.println("[I2C finder] 모든 핀 조합 스캔 시작");
  int total = 0;
  for (int i = 0; i < NPAIRS; i++) total += scanPair(PAIRS[i][0], PAIRS[i][1]);
  if (total == 0) Serial.println("  어떤 조합에서도 장치 없음 -> VCC/GND(전원) 또는 접촉 문제");
  Serial.println("[I2C finder] 스캔 끝. 5초 후 다시.");
  delay(5000);
}
