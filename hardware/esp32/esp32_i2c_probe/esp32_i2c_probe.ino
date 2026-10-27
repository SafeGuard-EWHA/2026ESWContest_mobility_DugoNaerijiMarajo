// SDA(32)/SCL(33) 선의 쉬는 전압을 읽어 센서에 전원이 가는지 추정한다.
// 센서 보드에 전원이 들어가면 보드 풀업 때문에 두 선이 ~3.3V로 올라간다. 0V 근처면 센서 전원 없음.
void setup() {
  Serial.begin(115200);
  pinMode(32, INPUT); pinMode(33, INPUT);     // 내부 풀업 끔
  analogSetAttenuation(ADC_11db);             // 0~3.3V 범위
  delay(300);
}
void loop() {
  int a32 = analogReadMilliVolts(32);
  int a33 = analogReadMilliVolts(33);
  Serial.print("SDA(GPIO32)="); Serial.print(a32); Serial.print(" mV   SCL(GPIO33)="); Serial.print(a33); Serial.print(" mV   -> ");
  if (a32 > 2500 && a33 > 2500) Serial.println("센서 전원 OK (풀업 있음)");
  else if (a32 < 300 && a33 < 300) Serial.println("두 선 모두 0V: 센서에 전원 안 감 (레일 ↔ 3V3/GND 점퍼 확인)");
  else Serial.println("애매함: 접촉 불량 또는 한 선만 연결");
  delay(1000);
}
