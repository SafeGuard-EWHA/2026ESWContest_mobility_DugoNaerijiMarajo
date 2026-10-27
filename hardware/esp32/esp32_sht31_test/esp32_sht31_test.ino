// SafeGuard ESP32 SHT31 온습도 테스트 (+ PIR 선택)
// 보드: ESP32 Dev Module / 시리얼 모니터: 115200 baud
// 배선: SHT31 VCC→3V3, GND→GND, SDA→GPIO32, SCL→GPIO33  (보드 왼쪽 핀 열 사용)
//       (선택) PIR  VCC→3V3, GND→GND, OUT→GPIO27
// 라이브러리: 스케치 → 라이브러리 관리 → "Adafruit SHT31" 설치 (Adafruit BusIO 같이 설치됨)
//
// 정상 출력 예: {"temp_c":24.8,"hum":47.3,"pir":0,"ok":true}
// 센서가 안 잡히면 I2C 주소 스캔 결과를 먼저 출력함.

#include <Wire.h>
#include "Adafruit_SHT31.h"

const int SDA_PIN = 32;   // 왼쪽 핀 열
const int SCL_PIN = 33;
const int PIR_PIN = 27;   // PIR 안 꽂았으면 그냥 0으로 찍힘
const int LED_PIN = 2;

Adafruit_SHT31 sht31 = Adafruit_SHT31();
uint8_t sht_addr = 0;

void scanI2C() {
  Serial.print("[I2C scan] SDA=GPIO"); Serial.print(SDA_PIN);
  Serial.print(", SCL=GPIO"); Serial.println(SCL_PIN);
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("  found device at 0x");
      if (a < 16) Serial.print("0");
      Serial.print(a, HEX);
      if (a == 0x44 || a == 0x45) Serial.print("  <- SHT31");
      Serial.println();
      found++;
    }
  }
  if (found == 0) Serial.println("  (없음) -> SDA/SCL 바뀜, VCC가 3V3인지, 선 접촉 확인");
}

bool initSHT() {
  if (sht31.begin(0x44)) { sht_addr = 0x44; return true; }
  if (sht31.begin(0x45)) { sht_addr = 0x45; return true; }
  return false;
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT_PULLDOWN);   // PIR은 평소 선을 놓음 → 풀다운 필수
  delay(500);
  Serial.println();
  Serial.println("[SafeGuard] SHT31 test start");
  Wire.begin(SDA_PIN, SCL_PIN);
  scanI2C();
  if (initSHT()) {
    Serial.print("[SHT31] OK at 0x"); Serial.println(sht_addr, HEX);
  } else {
    Serial.println("[SHT31] NOT FOUND - 배선 확인 후 EN(리셋) 버튼");
  }
}

void loop() {
  bool ok = false;
  float t = NAN, h = NAN;
  if (sht_addr == 0) {
    ok = initSHT();           // 나중에 꽂아도 잡히게 재시도
  } else {
    t = sht31.readTemperature();
    h = sht31.readHumidity();
    ok = !isnan(t) && !isnan(h);
  }
  int pir = digitalRead(PIR_PIN);
  digitalWrite(LED_PIN, ok ? HIGH : LOW);

  if (ok) {
    Serial.print("{\"temp_c\":"); Serial.print(t, 1);
    Serial.print(",\"hum\":");    Serial.print(h, 1);
    Serial.print(",\"pir\":");    Serial.print(pir);
    Serial.println(",\"ok\":true}");
  } else {
    Serial.print("{\"temp_c\":null,\"hum\":null,\"pir\":"); Serial.print(pir);
    Serial.println(",\"ok\":false}");
  }
  delay(1000);
}
