#include <Wire.h>
#include <Adafruit_SHT31.h>
#include <math.h>
#include <stdlib.h>
#include <esp_arduino_version.h>

const int PIR_PIN = 27;
const int FAN_PIN = 25;
const int BUZZER_PIN = 26;
const int SERVO_PIN = 13;
const int SERVO_CHANNEL = 0;  // ESP32 보드 패키지 2.x용

Adafruit_SHT31 sht31;
float thresholdC = 35.0f;

bool sensorFound = false;
bool sensorHealthy = false;
bool manualMode = false;
bool manualFan = false;
bool manualBuzzer = false;
bool alarmOn = false;
bool beepOn = false;
bool servoReady = false;
bool servoActive = false;
int servoAngle = 90;

unsigned long lastRead = 0;
unsigned long lastBeep = 0;
unsigned long beepStarted = 0;
String input = "";

void writeServoPulse(int pulseUs) {
  if (!servoReady) return;

  // 50 Hz = 20,000 us 주기, 16비트 PWM
  uint32_t duty = (uint32_t)pulseUs * 65536UL / 20000UL;

#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(SERVO_PIN, duty);
#else
  ledcWrite(SERVO_CHANNEL, duty);
#endif
}

void setServoAngle(int angle) {
  // 0~180도를 500~2500 us 신호로 변환
  int pulseUs = 500 + (angle * 2000 / 180);
  writeServoPulse(pulseUs);
  servoAngle = angle;
  servoActive = true;
}

void outputsOff() {
  digitalWrite(FAN_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  alarmOn = false;
  beepOn = false;
  manualFan = false;
  manualBuzzer = false;
}

void printAck(const char *command, int value) {
  Serial.print("{\"type\":\"ack\",\"command\":\"");
  Serial.print(command);
  Serial.print("\",\"value\":");
  Serial.print(value);
  Serial.println("}");
}

void processCommand(String line) {
  line.trim();
  if (line.length() == 0) return;
  line.toUpperCase();

  if (line == "SERVO OFF") {
    writeServoPulse(0);  // 신호만 중지. 서보 5V 전원 차단은 아님.
    servoActive = false;
    Serial.println("{\"type\":\"ack\",\"command\":\"SERVO OFF\"}");
    return;
  }

  if (line.startsWith("SERVO ")) {
    String number = line.substring(6);
    char *endPtr;
    long angle = strtol(number.c_str(), &endPtr, 10);

    // 처음에는 가운데 근처만 움직여서 확인
    if (!servoReady || endPtr == number.c_str() ||
        *endPtr != '\0' || angle < 45 || angle > 135) {
      Serial.println(
        "{\"type\":\"error\",\"error\":\"SERVO_ANGLE_USE_70_TO_110\"}");
      return;
    }

    setServoAngle((int)angle);
    printAck("SERVO", servoAngle);
    return;
  }

  if (line == "AUTO") {
    outputsOff();
    manualMode = false;
    Serial.println("{\"type\":\"ack\",\"command\":\"AUTO\"}");
    return;
  }

  bool isFan = line == "FAN 0" || line == "FAN 1";
  bool isBuzzer = line == "BUZ 0" || line == "BUZ 1";

  if (isFan || isBuzzer) {
    if (!sensorHealthy) {
      outputsOff();
      Serial.println("{\"type\":\"error\",\"error\":\"SHT31_NOT_READY\"}");
      return;
    }

    if (!manualMode) {
      outputsOff();
      manualMode = true;
    }

    bool turnOn = line.endsWith("1");
    if (isFan) {
      manualFan = turnOn;
      digitalWrite(FAN_PIN, turnOn ? HIGH : LOW);
      printAck("FAN", turnOn);
    } else {
      manualBuzzer = turnOn;
      digitalWrite(BUZZER_PIN, turnOn ? HIGH : LOW);
      printAck("BUZ", turnOn);
    }
    return;
  }

  // 숫자만 보내면 온도 기준값 변경. 예: 35
  char *endPtr;
  float value = strtof(line.c_str(), &endPtr);

  if (endPtr != line.c_str() && *endPtr == '\0' &&
      isfinite(value) && value >= -20.0f && value <= 80.0f) {
    thresholdC = value;
    Serial.print("Threshold set to ");
    Serial.println(thresholdC, 1);
  } else {
    Serial.println("{\"type\":\"error\",\"error\":\"UNKNOWN_COMMAND\"}");
  }
}

void setup() {
  digitalWrite(FAN_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  pinMode(FAN_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);

  Serial.begin(115200);
  Wire.begin(32, 33);

#if ESP_ARDUINO_VERSION_MAJOR >= 3
  servoReady = ledcAttach(SERVO_PIN, 50, 16);
#else
  servoReady = ledcSetup(SERVO_CHANNEL, 50, 16) > 0;
  if (servoReady) ledcAttachPin(SERVO_PIN, SERVO_CHANNEL);
#endif

  if (servoReady) setServoAngle(90);

  sensorFound = sht31.begin(0x44);
  if (!sensorFound) sensorFound = sht31.begin(0x45);

  Serial.println(
    "Commands: FAN 1/0, BUZ 1/0, AUTO, SERVO 70..110, SERVO OFF, 35");
  if (!sensorFound) Serial.println("SHT31 not found. Check wiring.");
  if (!servoReady) Serial.println("Servo PWM setup failed.");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      processCommand(input);
      input = "";
    } else if (input.length() < 32) {
      input += c;
    }
  }

  unsigned long now = millis();

  if (now - lastRead >= 1000UL) {
    lastRead = now;

    float temp = sensorFound ? sht31.readTemperature() : NAN;
    float hum = sensorFound ? sht31.readHumidity() : NAN;
    sensorHealthy = !isnan(temp) && !isnan(hum);

    if (!sensorHealthy) {
      outputsOff();
      Serial.println(
        "{\"sensor_ok\":false,\"error\":\"SHT31\","
        "\"fan\":0,\"alarm\":0,\"buzzer\":0}");
    } else {
      if (!manualMode) {
        if (temp >= thresholdC && !alarmOn) {
          alarmOn = true;
          lastBeep = now - 3000UL;
        } else if (temp <= thresholdC - 1.0f) {
          alarmOn = false;
        }

        digitalWrite(FAN_PIN, alarmOn ? HIGH : LOW);

        if (!alarmOn) {
          digitalWrite(BUZZER_PIN, LOW);
          beepOn = false;
        }
      }

      Serial.print("{\"sensor_ok\":true,\"temp\":");
      Serial.print(temp, 1);
      Serial.print(",\"hum\":");
      Serial.print(hum, 1);
      Serial.print(",\"pir\":");
      Serial.print(digitalRead(PIR_PIN));
      Serial.print(",\"threshold\":");
      Serial.print(thresholdC, 1);
      Serial.print(",\"fan\":");
      Serial.print(manualMode ? manualFan : alarmOn);
      Serial.print(",\"alarm\":");
      Serial.print(manualMode ? 0 : alarmOn);
      Serial.print(",\"buzzer\":");
      Serial.print(manualMode ? manualBuzzer : beepOn);
      Serial.print(",\"servo\":");
      if (servoActive) Serial.print(servoAngle);
      else Serial.print("null");
      Serial.print(",\"mode\":\"");
      Serial.print(manualMode ? "MANUAL" : "AUTO");
      Serial.println("\"}");
    }
  }

  if (sensorHealthy && !manualMode && alarmOn) {
    if (beepOn && now - beepStarted >= 200UL) {
      digitalWrite(BUZZER_PIN, LOW);
      beepOn = false;
    } else if (!beepOn && now - lastBeep >= 3000UL) {
      digitalWrite(BUZZER_PIN, HIGH);
      beepOn = true;
      beepStarted = now;
      lastBeep = now;
    }
  }
}