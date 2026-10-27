/* SafeGuard competition demonstration integration 0.3.0.
 * Same GPIO wiring as sketch_oct24b.ino; physical ESTOP is NOT installed.
 * Every MCU boot starts latched OFF; explicit computer Resume is required.
 * Manual STOP switches fan/buzzer OFF and disables servo PWM. PWM OFF does
 * not cut servo supply, brake the shaft, or move the window to a safe angle.
 * Heartbeat loss retains fan/buzzer protection requests and disables servo PWM.
 * Software STOP requires the functioning computer, USB link and MCU.
 */
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SHT31.h>
#include <ArduinoJson.h>
#include <esp_random.h>
#include <esp_arduino_version.h>
#include <driver/gpio.h>
#include <math.h>
#include <string.h>

#if ARDUINOJSON_VERSION_MAJOR == 6
using Message = StaticJsonDocument<1536>;
#elif ARDUINOJSON_VERSION_MAJOR == 7
using Message = JsonDocument;
#else
#error "Install ArduinoJson 6.21.x or 7.x"
#endif

// The user explicitly excluded the physical ESTOP from this model prototype.
constexpr bool SOFTWARE_STOP_DEMO = true;
constexpr bool ENABLE_ACTUATORS = true;
constexpr bool ENABLE_SERVO = true;
constexpr int SERVO_PIN = 13;
constexpr int SERVO_CHANNEL = 0;
constexpr int SERVO_MIN = 45, SERVO_MAX = 135; // command limits, NOT window calibration
constexpr bool ENABLE_PIR = true;
constexpr bool ENABLE_SHT31 = true;
constexpr bool ENABLE_ESTOP = false;  // NOT INSTALLED. Never report as a valid released switch.
constexpr int PIR_PIN = 27;
constexpr int SDA_PIN = 32;
constexpr int SCL_PIN = 33;
constexpr int FAN_PIN = 25;
constexpr int BUZZER_PIN = 26;
constexpr int ESTOP_PIN = -1;  // UNASSIGNED: never reuse SHT31 SDA32.
constexpr int PIR_ACTIVE_LEVEL = HIGH;
constexpr int FAN_ACTIVE_LEVEL = HIGH;
constexpr int BUZZER_ACTIVE_LEVEL = HIGH;
constexpr int ESTOP_ACTIVE_LEVEL = -1;  // UNASSIGNED: verify the actual stop circuit.
constexpr int ESTOP_INPUT_MODE = INPUT_PULLUP;  // Example only; verify circuit.
constexpr uint8_t SHT31_PRIMARY_ADDRESS = 0x44;
constexpr uint8_t SHT31_FALLBACK_ADDRESS = 0x45;
constexpr char FIRMWARE_ID[] = "SafeGuard_Software_Stop-0.3.0";
// Classic ESP32 pins with internal pull-up, excluding flash/boot-strapping pins.
// Passing this check does not prove the physical wiring or board pinout.
constexpr bool ESTOP_PIN_ASSIGNMENT_VALID =
    (ESTOP_PIN == 4 || ESTOP_PIN == 13 || ESTOP_PIN == 14 ||
     ESTOP_PIN == 16 || ESTOP_PIN == 17 || ESTOP_PIN == 18 ||
     ESTOP_PIN == 19 || ESTOP_PIN == 21 || ESTOP_PIN == 22 ||
     ESTOP_PIN == 23 || ESTOP_PIN == 25 || ESTOP_PIN == 26 ||
     ESTOP_PIN == 27 || ESTOP_PIN == 32 || ESTOP_PIN == 33) &&
    ESTOP_PIN != SDA_PIN && ESTOP_PIN != SCL_PIN && ESTOP_PIN != PIR_PIN &&
    ESTOP_PIN != FAN_PIN && ESTOP_PIN != BUZZER_PIN && ESTOP_PIN != SERVO_PIN;
constexpr bool ESTOP_LEVEL_VALID = ESTOP_ACTIVE_LEVEL == LOW || ESTOP_ACTIVE_LEVEL == HIGH;
static_assert(!ENABLE_ESTOP || (ESTOP_PIN_ASSIGNMENT_VALID && ESTOP_LEVEL_VALID),
              "Assign and verify a non-conflicting ESTOP GPIO and active level before enabling ESTOP.");
static_assert(!ENABLE_ACTUATORS || SOFTWARE_STOP_DEMO ||
              (ENABLE_ESTOP && ESTOP_PIN_ASSIGNMENT_VALID && ESTOP_LEVEL_VALID),
              "Select a validated physical ESTOP or the software-stop demonstration profile.");
constexpr uint32_t PIR_WARMUP_MS = 60000;  // Set from actual sensor datasheet/test.
constexpr uint32_t TELEMETRY_MS = 500;
constexpr uint32_t SHT31_SAMPLE_MS = 500;
constexpr uint32_t SHT31_RETRY_MS = 5000;
constexpr uint32_t HEARTBEAT_TIMEOUT_MS = 3000;  // Pi sends a heartbeat every 500 ms.
constexpr uint32_t ESTOP_RELEASE_STABLE_MS = 200;
constexpr size_t RUN_ID_MAX = 64;
constexpr size_t RX_CAPACITY = 512;  // Max JSON payload 511 bytes + terminating NUL.
constexpr size_t TX_CAPACITY = 1024;
constexpr uint8_t TX_SLOTS = 8;
constexpr uint8_t CACHE_SLOTS = 32;
constexpr uint8_t RETIRED_RUN_SLOTS = 8;

Adafruit_SHT31 sht31;
bool shtReady = false;
uint8_t sht31Address = 0;  // 0 means no sensor acknowledged either address.
float temperatureC = NAN, humidityRH = NAN;
bool temperatureValid = false, humidityValid = false;
bool pirWarmed = false;
bool fanCommand = false, buzzerCommand = false;
bool softwareStopLatched = true;  // reboot cannot silently resume
uint32_t stopGeneration = 1;
char stopNonce[65] = "boot";
bool servoReady = false;
int servoCommand = -1;  // -1 PWM OFF; 45..135 requested angle, NOT measured position

void setServoCommand(int angle) {
  if (!ENABLE_ACTUATORS || !ENABLE_SERVO || !servoReady) return;
  uint32_t duty = angle < 0 ? 0 :
      static_cast<uint32_t>(500 + angle * 2000 / 180) * 65536UL / 20000UL;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(SERVO_PIN, duty);
#else
  ledcWrite(SERVO_CHANNEL, duty);
#endif
  servoCommand = angle;
}
bool estopActive = false, estopLatched = false;
bool estopReleasedTiming = false;
uint32_t estopReleasedSince = 0;
uint32_t bootAt = 0, lastClock = 0;
uint64_t uptimeMs = 0;
char bootId[17] = {};
uint32_t telemetrySequence = 0;
uint32_t lastTelemetry = 0, lastSensor = 0, lastSensorRetry = 0, lastStatus = 0;

char activeRun[RUN_ID_MAX + 1] = {};
char retiredRuns[RETIRED_RUN_SLOTS][RUN_ID_MAX + 1] = {};
uint8_t retiredRunCount = 0;
uint32_t heartbeatSequence = 0, lastHeartbeat = 0;
bool heartbeatFault = true;
uint32_t heartbeatLossCount = 0, rxErrorCount = 0, txDropCount = 0;
const char *lastFault = "awaiting_heartbeat";
uint32_t highestRequestId = 0;

struct RequestRecord {
  bool used;
  uint32_t id;
  bool rearm;
  bool fan;
  bool buzzer;
  int servo;
  bool accepted;
  const char *reason;
};
// Explicit declaration keeps the Arduino .ino prototype generator from moving
// this custom return type ahead of its definition.
RequestRecord *findRequest(uint32_t id);
RequestRecord requestCache[CACHE_SLOTS] = {};
uint8_t cacheNext = 0;

struct TxPacket {
  char data[TX_CAPACITY];
  size_t length;
  size_t sent;
};
TxPacket txQueue[TX_SLOTS] = {};
uint8_t txHead = 0, txCount = 0;
char rxLine[RX_CAPACITY] = {};
size_t rxLength = 0;
bool rxDiscard = false;

bool elapsed(uint32_t now, uint32_t then, uint32_t interval) {
  return static_cast<uint32_t>(now - then) >= interval;
}

bool queueJson(JsonDocument &doc) {
  const size_t length = measureJson(doc);
  if (doc.overflowed() || length + 2 > TX_CAPACITY || txCount == TX_SLOTS) {
    ++txDropCount;
    return false;
  }
  TxPacket &packet = txQueue[(txHead + txCount) % TX_SLOTS];
  packet.length = serializeJson(doc, packet.data, TX_CAPACITY);
  packet.data[packet.length++] = '\n';
  packet.sent = 0;
  ++txCount;
  return true;
}

void drainSerialTx() {
  if (!txCount) return;
  const int available = Serial.availableForWrite();
  if (available <= 0) return;  // Disconnected/slow host never blocks the loop.
  TxPacket &packet = txQueue[txHead];
  size_t count = packet.length - packet.sent;
  if (count > static_cast<size_t>(available)) count = available;
  if (count > 64) count = 64;
  packet.sent += Serial.write(
      reinterpret_cast<const uint8_t *>(packet.data + packet.sent), count);
  if (packet.sent == packet.length) {
    txHead = (txHead + 1) % TX_SLOTS;
    --txCount;
  }
}

void applyOutputs(bool fan, bool buzzer) {
  if (!ENABLE_ACTUATORS) return;  // Includes OFF: never touch these GPIOs.
  if (estopLatched || estopActive || softwareStopLatched) fan = buzzer = false;
  if (fan != fanCommand) {
    digitalWrite(FAN_PIN, fan ? FAN_ACTIVE_LEVEL : !FAN_ACTIVE_LEVEL);
  }
  if (buzzer != buzzerCommand) {
    digitalWrite(BUZZER_PIN, buzzer ? BUZZER_ACTIVE_LEVEL : !BUZZER_ACTIVE_LEVEL);
  }
  fanCommand = fan;
  buzzerCommand = buzzer;
}

void stopAll(const char *reason) {
  softwareStopLatched = true;
  applyOutputs(false, false);
  setServoCommand(-1); // PWM off; external servo power is still present.
  lastFault = reason;
}

void sampleEstop(uint32_t now) {
  if (!ENABLE_ESTOP) return;
  estopActive = digitalRead(ESTOP_PIN) == ESTOP_ACTIVE_LEVEL;
  if (estopActive) {
    estopLatched = true;
    estopReleasedTiming = false;
    lastFault = "estop_latched";
    applyOutputs(false, false);
    setServoCommand(-1);
  } else if (!estopReleasedTiming) {
    estopReleasedTiming = true;
    estopReleasedSince = now;
  }
}

bool heartbeatFresh(uint32_t now) {
  return activeRun[0] && !elapsed(now, lastHeartbeat, HEARTBEAT_TIMEOUT_MS);
}

void updateHeartbeatFault(uint32_t now) {
  if (activeRun[0] && !heartbeatFresh(now) && !heartbeatFault) {
    heartbeatFault = true;
    ++heartbeatLossCount;
    lastFault = "heartbeat_timeout_fan_buzzer_retained";
    setServoCommand(-1);  // no automatic return/closing movement
  }
}

bool validRunId(JsonVariantConst value) {
  if (!value.is<const char *>()) return false;
  const char *text = value.as<const char *>();
  const size_t size = strlen(text);
  if (!size || size > RUN_ID_MAX || size != value.as<JsonString>().size()) return false;
  for (size_t i = 0; i < size; ++i) {
    const char c = text[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == ':')) {
      return false;
    }
  }
  return true;
}

bool retiredRun(const char *run) {
  for (uint8_t i = 0; i < retiredRunCount; ++i) {
    if (strcmp(run, retiredRuns[i]) == 0) return true;
  }
  return false;
}

void handleHeartbeat(JsonDocument &doc, uint32_t now) {
  if (!validRunId(doc["run_id"]) || !doc["seq"].is<uint32_t>()) {
    ++rxErrorCount;
    lastFault = "invalid_heartbeat";
    return;
  }
  const char *run = doc["run_id"].as<const char *>();
  const uint32_t sequence = doc["seq"].as<uint32_t>();
  if (strcmp(run, activeRun) == 0) {
    if (sequence <= heartbeatSequence) return;  // Replay is not evidence of life.
  } else {
    if (retiredRun(run)) {
      lastFault = "retired_run";
      return;
    }
    if (activeRun[0]) {
      if (heartbeatFresh(now)) {
        lastFault = "session_busy";
        return;
      }
      if (retiredRunCount == RETIRED_RUN_SLOTS) {
        lastFault = "session_history_full";
        return;  // Never evict a retired ID and accidentally permit its replay.
      }
      strcpy(retiredRuns[retiredRunCount++], activeRun);
    }
    strcpy(activeRun, run);
    highestRequestId = 0;
    memset(requestCache, 0, sizeof(requestCache));
    cacheNext = 0;
    lastFault = "session_started";
    // New Pi process does not clear any physical/software stop latch.
  }
  heartbeatSequence = sequence;
  lastHeartbeat = now;
  heartbeatFault = false;
}

void sendAck(const char *run, uint32_t id, bool accepted, const char *reason) {
  Message reply;
  reply["type"] = "ack";
  reply["run_id"] = run;
  reply["boot_id"] = bootId;
  reply["id"] = id;
  reply["accepted"] = accepted;
  reply["fan_cmd"] = fanCommand;
  reply["buzzer_cmd"] = buzzerCommand;
  if (servoCommand < 0) reply["servo_cmd"] = nullptr;
  else reply["servo_cmd"] = servoCommand;
  reply["software_stop_latched"] = softwareStopLatched;
  reply["stop_generation"] = stopGeneration;
  reply["reason"] = reason;
  queueJson(reply);
}

RequestRecord *findRequest(uint32_t id) {
  for (uint8_t i = 0; i < CACHE_SLOTS; ++i) {
    if (requestCache[i].used && requestCache[i].id == id) return &requestCache[i];
  }
  return nullptr;
}

void handleRequest(JsonDocument &doc, bool rearm, uint32_t now) {
  // Without a valid correlation ID, report the parse fault through status only.
  if (!validRunId(doc["run_id"]) || !doc["id"].is<uint32_t>() ||
      doc["id"].as<uint32_t>() == 0) {
    ++rxErrorCount;
    lastFault = "invalid_request_identity";
    return;
  }
  const char *run = doc["run_id"].as<const char *>();
  const uint32_t id = doc["id"].as<uint32_t>();
  if (!rearm && (!doc["fan"].is<bool>() || !doc["buzzer"].is<bool>())) {
    sendAck(run, id, false, "fan_buzzer_must_be_boolean");
    return;
  }
  if (rearm && (!doc["fan"].isNull() || !doc["buzzer"].isNull())) {
    sendAck(run, id, false, "rearm_has_no_output_payload");
    return;
  }
  int servo = -2;  // absent: preserve servo; null: PWM OFF
  if (!doc["servo_deg"].isUnbound()) {
    if (rearm) { sendAck(run, id, false, "rearm_has_no_output_payload"); return; }
    if (doc["servo_deg"].isNull()) servo = -1;
    else if (doc["servo_deg"].is<int>() &&
             doc["servo_deg"].as<int>() >= SERVO_MIN && doc["servo_deg"].as<int>() <= SERVO_MAX)
      servo = doc["servo_deg"].as<int>();
    else { sendAck(run, id, false, "servo_angle_use_45_to_135"); return; }
    if (servo >= 0 && (!ENABLE_SERVO || !servoReady)) {
      sendAck(run, id, false, "servo_pwm_unavailable"); return;
    }
  }
  const bool fan = rearm ? false : doc["fan"].as<bool>();
  const bool buzzer = rearm ? false : doc["buzzer"].as<bool>();
  if (!activeRun[0] || strcmp(run, activeRun) != 0) {
    sendAck(run, id, false, "run_mismatch_send_heartbeat_first");
    return;
  }
  if (rearm && (!doc["boot_id"].is<const char *>() ||
      strcmp(doc["boot_id"].as<const char *>(), bootId) != 0 ||
      !doc["stop_generation"].is<uint32_t>() ||
      doc["stop_generation"].as<uint32_t>() != stopGeneration)) {
    sendAck(run, id, false, "resume_requires_current_boot_and_stop_generation");
    return;
  }
  RequestRecord *previous = findRequest(id);
  if (previous) {
    if (previous->rearm != rearm || previous->fan != fan || previous->buzzer != buzzer || previous->servo != servo) {
      sendAck(run, id, false, "id_payload_conflict");
    } else if (previous->accepted && (estopLatched || estopActive || softwareStopLatched)) {
      sendAck(run, id, false, softwareStopLatched ? "software_stop_latched" : "estop_latched");
    } else if (previous->accepted && !heartbeatFresh(now)) {
      sendAck(run, id, false, "heartbeat_timeout");
    } else if (previous->accepted &&
               (fan != fanCommand || buzzer != buzzerCommand || (servo != -2 && servo != servoCommand))) {
      sendAck(run, id, false, "duplicate_superseded");
    } else {
      sendAck(run, id, previous->accepted,
              previous->accepted ? "duplicate_no_change" : previous->reason);
    }
    return;  // Replays NEVER write GPIO or clear a latch.
  }
  if (id <= highestRequestId) {
    sendAck(run, id, false, "stale_id");
    return;  // Includes requests evicted from the bounded cache.
  }
  highestRequestId = id;
  bool accepted = false;
  const char *reason = "accepted";
  if (!ENABLE_ACTUATORS) {
    reason = "actuation_disabled";
  } else if (!heartbeatFresh(now)) {
    reason = "heartbeat_timeout";
  } else if (rearm) {
    if (softwareStopLatched && !estopLatched && !estopActive) {
      softwareStopLatched = false;
      applyOutputs(false, false);
      setServoCommand(-1);
      accepted = true;
      reason = "software_stop_rearmed_outputs_off";
    } else if (!ENABLE_ESTOP) {
      reason = "nothing_to_rearm";
    } else if (!estopLatched) {
      reason = "estop_not_latched";  // Do not turn protection OFF on a stray rearm.
    } else if (estopActive || !estopReleasedTiming ||
               !elapsed(now, estopReleasedSince, ESTOP_RELEASE_STABLE_MS)) {
      reason = "estop_not_stably_released";
    } else {
      // A fresh rearm only clears the latch. It does not restore previous outputs.
      estopLatched = false;
      applyOutputs(false, false);
      accepted = true;
      reason = "rearmed_outputs_off";
    }
  } else if (estopActive || estopLatched || softwareStopLatched) {
    reason = softwareStopLatched ? "software_stop_latched" : "estop_latched";
  } else {
    applyOutputs(fan, buzzer);
    if (servo != -2) setServoCommand(servo);
    accepted = true;
  }
  requestCache[cacheNext] = {true, id, rearm, fan, buzzer, servo, accepted, reason};
  cacheNext = (cacheNext + 1) % CACHE_SLOTS;
  sendAck(run, id, accepted, reason);
}

void processLine(uint32_t now) {
  // Serial-monitor STOP is an additional software stop, never a hardware ESTOP.
  if (rxLength == 4 && memcmp(rxLine, "STOP", 4) == 0) {
    ++stopGeneration;
    strcpy(stopNonce, "serial-stop");
    stopAll("operator_software_stop");
    return;
  }
  Message request;
  const DeserializationError error = deserializeJson(
      request, rxLine, rxLength, DeserializationOption::NestingLimit(4));
  if (error || !request.is<JsonObject>() || !request["type"].is<const char *>()) {
    ++rxErrorCount;
    lastFault = "invalid_json_frame";
    return;
  }
  const char *type = request["type"].as<const char *>();
  sampleEstop(now);  // Recheck physical input immediately before any command.
  if (strcmp(type, "manual_stop") == 0) {
    if (!validRunId(request["stop_nonce"])) {
      ++rxErrorCount; lastFault = "invalid_stop_nonce"; return;
    }
    const char *nonce = request["stop_nonce"].as<const char *>();
    if (!softwareStopLatched || strcmp(nonce, stopNonce) != 0) {
      ++stopGeneration;
      strcpy(stopNonce, nonce);
    }
    stopAll("operator_software_stop");
    // The nonce in fresh telemetry confirms this specific request, not an old stop.
  }
  else if (strcmp(type, "heartbeat") == 0) handleHeartbeat(request, now);
  else if (strcmp(type, "command") == 0) handleRequest(request, false, now);
  else if (strcmp(type, "rearm") == 0) handleRequest(request, true, now);
  else {
    ++rxErrorCount;
    lastFault = "unknown_message_type";
  }
}

void readSerialRx(uint32_t now) {
  // Reserve room for a command ACK; limit work so a flood cannot starve ESTOP.
  uint16_t budget = 128;
  while (budget-- && Serial.available() > 0 && txCount < TX_SLOTS - 1) {
    const int raw = Serial.read();
    if (raw < 0) break;
    const char c = static_cast<char>(raw);
    if (c == '\n') {
      if (!rxDiscard && rxLength) {
        rxLine[rxLength] = '\0';
        processLine(now);
      }
      rxLength = 0;
      rxDiscard = false;
    } else if (c == '\r') {
      continue;  // JSONL with either LF or CRLF; bare CR is not a delimiter.
    } else if (!rxDiscard) {
      if (c == '\0' || rxLength >= RX_CAPACITY - 1) {
        rxDiscard = true;
        rxLength = 0;
        ++rxErrorCount;
        lastFault = "rx_frame_too_long_or_nul";
      } else {
        rxLine[rxLength++] = c;
      }
    }
  }
}

bool beginSht31() {
  sht31Address = 0;
  if (sht31.begin(SHT31_PRIMARY_ADDRESS)) {
    sht31Address = SHT31_PRIMARY_ADDRESS;
    return true;
  }
  if (sht31.begin(SHT31_FALLBACK_ADDRESS)) {
    sht31Address = SHT31_FALLBACK_ADDRESS;
    return true;
  }
  return false;
}

void readSensors(uint32_t now) {
  if (!ENABLE_SHT31) return;
  if (!shtReady && elapsed(now, lastSensorRetry, SHT31_RETRY_MS)) {
    lastSensorRetry = now;
    shtReady = beginSht31();
  }
  if (!elapsed(now, lastSensor, SHT31_SAMPLE_MS)) return;
  lastSensor = now;
  temperatureValid = humidityValid = false;
  if (!shtReady) return;
  float t = NAN, h = NAN;
  const bool ok = sht31.readBoth(&t, &h);  // One conversion; library waits ~20 ms.
  temperatureValid = ok && isfinite(t) && t >= -40.0f && t <= 125.0f;
  humidityValid = ok && isfinite(h) && h >= 0.0f && h <= 100.0f;
  temperatureC = temperatureValid ? t : NAN;
  humidityRH = humidityValid ? h : NAN;
  if (!ok) {
    shtReady = false;
    sht31Address = 0;
    lastSensorRetry = now;
    lastFault = "sht31_read_failed";
  }
}

void sendTelemetry(uint32_t now) {
  if (!elapsed(now, lastTelemetry, TELEMETRY_MS)) return;
  lastTelemetry = now;
  if (txCount >= TX_SLOTS - 2) return;  // Leave two queue slots for ACKs.
  const bool pirValid = ENABLE_PIR && pirWarmed;
  Message report;
  report["type"] = "telemetry";
  report["seq"] = telemetrySequence++;
  report["uptime_ms"] = uptimeMs;
  report["boot_id"] = bootId;
  if (pirValid) report["pir"] = digitalRead(PIR_PIN) == PIR_ACTIVE_LEVEL;
  else report["pir"] = nullptr;
  report["pir_valid"] = pirValid;
  if (temperatureValid) report["temp_c"] = temperatureC;
  else report["temp_c"] = nullptr;
  report["temp_valid"] = temperatureValid;
  if (humidityValid) report["humidity"] = humidityRH;
  else report["humidity"] = nullptr;
  report["humidity_valid"] = humidityValid;
  if (ENABLE_ESTOP) report["estop"] = estopActive;
  else report["estop"] = nullptr;
  report["estop_valid"] = ENABLE_ESTOP;
  // Keep the physical switch and the persisted stop latch separate. A brief
  // press can occur entirely between 500 ms reports; the latch must still reach
  // the controller, while the raw switch indicates whether rearm is permitted.
  report["estop_latched"] = estopLatched;
  // A new Pi process must synchronize these before sending its initial command.
  // Otherwise its default OFF could clear protection retained across restart.
  report["fan_cmd"] = fanCommand;
  report["buzzer_cmd"] = buzzerCommand;
  report["actuators_enabled"] = ENABLE_ACTUATORS && !softwareStopLatched;
  report["active_run"] = activeRun;
  report["heartbeat_fault"] = heartbeatFault;
  report["physical_estop_installed"] = ENABLE_ESTOP;
  report["software_stop_latched"] = softwareStopLatched;
  report["software_control_version"] = 1;
  report["stop_generation"] = stopGeneration;
  report["stop_nonce"] = stopNonce;
  report["servo_ready"] = servoReady;
  if (servoCommand < 0) report["servo_cmd"] = nullptr;
  else report["servo_cmd"] = servoCommand;
  queueJson(report);
}

void sendStatus(uint32_t now) {
  if (!elapsed(now, lastStatus, 1000) || txCount >= TX_SLOTS - 2) return;
  lastStatus = now;
  Message report;
  report["type"] = "status";
  report["firmware_id"] = FIRMWARE_ID;
  if (sht31Address) report["sht31_address"] = sht31Address;
  else report["sht31_address"] = nullptr;
  report["boot_id"] = bootId;
  report["run_id"] = activeRun;
  report["actuators_enabled"] = ENABLE_ACTUATORS && !softwareStopLatched;
  report["fan_cmd"] = fanCommand;
  report["buzzer_cmd"] = buzzerCommand;
  report["estop_latched"] = estopLatched;
  report["heartbeat_fault"] = heartbeatFault;
  report["physical_estop_installed"] = ENABLE_ESTOP;
  report["software_stop_latched"] = softwareStopLatched;
  report["software_control_version"] = 1;
  report["stop_generation"] = stopGeneration;
  report["stop_nonce"] = stopNonce;
  report["servo_ready"] = servoReady;
  if (servoCommand < 0) report["servo_cmd"] = nullptr;
  else report["servo_cmd"] = servoCommand;
  report["heartbeat_loss_count"] = heartbeatLossCount;
  report["rx_error_count"] = rxErrorCount;
  report["tx_drop_count"] = txDropCount;
  report["last_fault"] = lastFault;  // Historical diagnostic, not a live fault enum.
  queueJson(report);
}

void setup() {
  bootAt = lastClock = millis();
  snprintf(bootId, sizeof(bootId), "%08lx%08lx",
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()));
  Serial.begin(115200);
  if (ENABLE_PIR) pinMode(PIR_PIN, INPUT);
  if (ENABLE_ESTOP) {
    pinMode(ESTOP_PIN, ESTOP_INPUT_MODE);
    sampleEstop(millis());
  }
  if (ENABLE_ACTUATORS) {
    // External gate/base pull resistors must hold OFF during boot/reset, too.
    // Preload the GPIO output latch before enabling output. Arduino-ESP32 3.x
    // digitalWrite() itself requires pinMode() first, so use IDF for preloading.
    gpio_set_level(static_cast<gpio_num_t>(FAN_PIN), !FAN_ACTIVE_LEVEL);
    gpio_set_level(static_cast<gpio_num_t>(BUZZER_PIN), !BUZZER_ACTIVE_LEVEL);
    pinMode(FAN_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(FAN_PIN, !FAN_ACTIVE_LEVEL);
    digitalWrite(BUZZER_PIN, !BUZZER_ACTIVE_LEVEL);
  }
  if (ENABLE_ACTUATORS && ENABLE_SERVO) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    servoReady = ledcAttach(SERVO_PIN, 50, 16);
#else
    servoReady = ledcSetup(SERVO_CHANNEL, 50, 16) > 0;
    if (servoReady) ledcAttachPin(SERVO_PIN, SERVO_CHANNEL);
#endif
    setServoCommand(-1);
  }
  if (ENABLE_SHT31) {
    Wire.begin(SDA_PIN, SCL_PIN, 100000);
    Wire.setTimeOut(25);
    shtReady = beginSht31();
    lastSensorRetry = millis();
  }
}

void loop() {
  uint32_t now = millis();
  uptimeMs += static_cast<uint32_t>(now - lastClock);
  lastClock = now;
  if (!pirWarmed && elapsed(now, bootAt, PIR_WARMUP_MS)) pirWarmed = true;
  sampleEstop(now);
  updateHeartbeatFault(now);
  drainSerialTx();
  readSerialRx(now);
  readSensors(now);
  now = millis();
  sampleEstop(now);  // Also check after the SHT31 conversion.
  updateHeartbeatFault(now);
  sendTelemetry(now);
  sendStatus(now);
  drainSerialTx();
  // No delay(), readStringUntil(), wait-for-USB, or unbounded RX loop.
}
