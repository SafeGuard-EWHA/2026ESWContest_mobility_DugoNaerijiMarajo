#!/usr/bin/env python3
"""Optional host test of the reference sketch with real ArduinoJson headers.

Usage: python3 tests/test_firmware_reference.py --arduinojson-dir PATH/ArduinoJson
No libraries are downloaded. GPIO, UART, I2C and clock are mocks; this is not an
ESP32 target build or a physical test. Accepts an ArduinoJson checkout or src dir.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile


HEADERS = {
    "Arduino.h": r'''
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <deque>
#include <vector>
#include <utility>
#define HIGH 1
#define LOW 0
#define INPUT 1
#define OUTPUT 2
#define INPUT_PULLUP 3
inline uint32_t clockMs=0;
inline int pinLevels[64]={};
inline std::vector<std::pair<int,int>> writes, modes;
inline uint32_t millis(){return clockMs;}
inline int digitalRead(int p){return pinLevels[p];}
inline void digitalWrite(int p,int v){pinLevels[p]=v;writes.emplace_back(p,v);}
inline void pinMode(int p,int v){modes.emplace_back(p,v);}
struct SerialStub {
  std::deque<unsigned char> rx; std::string tx;
  void begin(int){} int available(){return rx.size();}
  int read(){if(rx.empty())return -1;int c=rx.front();rx.pop_front();return c;}
  int availableForWrite(){return 512;}
  size_t write(const uint8_t* p,size_t n){tx.append((const char*)p,n);return n;}
};
inline SerialStub Serial;
''',
    "Wire.h": "#pragma once\nstruct WireStub {bool begin(int,int,int){return true;}"
              "void setTimeOut(int){}};inline WireStub Wire;\n",
    "Adafruit_SHT31.h": "#pragma once\n#include <cmath>\n"
              "struct Adafruit_SHT31 {bool begin(int){return true;} "
              "bool readBoth(float* t,float* h){*t=23.0f;*h=48.0f;return true;}};\n",
    "esp_random.h": "#pragma once\n#include <cstdint>\n"
              "inline uint32_t esp_random(){static uint32_t x=12345;return ++x;}\n",
    "driver/gpio.h": "#pragma once\nusing gpio_num_t=int; "
              "inline int gpio_set_level(int p,int v){digitalWrite(p,v);return 0;}\n",
}

HARNESS = r'''
#include "sketch.ino"
#include <cassert>
#include <iostream>
void clearTx(){txHead=txCount=0;Serial.tx.clear();}
Message frame(const std::string& line,uint32_t t){
  clearTx();clockMs=t;strcpy(rxLine,line.c_str());rxLength=line.size();processLine(t);
  Message answer;
  if(txCount)assert(!deserializeJson(answer,static_cast<const char*>(txQueue[txHead].data),txQueue[txHead].length));
  return answer;
}
void beat(const char* run,uint32_t seq,uint32_t t){
  frame(std::string("{\"type\":\"heartbeat\",\"run_id\":\"")+run+
    "\",\"seq\":"+std::to_string(seq)+"}",t);
}
Message command(uint32_t id,bool on,uint32_t t,const char* run="runA"){
  return frame(std::string("{\"type\":\"command\",\"run_id\":\"")+run+
    "\",\"id\":"+std::to_string(id)+",\"fan\":"+(on?"true":"false")+
    ",\"buzzer\":"+(on?"true":"false")+"}",t);
}
Message telemetry(uint32_t t){
  clearTx();sendTelemetry(t);assert(txCount==1);Message result;
  assert(!deserializeJson(result,static_cast<const char*>(txQueue[txHead].data),txQueue[txHead].length));
  return result;
}
int main(){
  pinLevels[32]=HIGH;setup();beat("runA",1,1000);
  auto a=command(1,true,1100);
  assert(a["boot_id"]==bootId);
  auto t=telemetry(1500);
  assert(t["estop_latched"].is<bool>() && t["fan_cmd"].is<bool>() &&
         t["buzzer_cmd"].is<bool>() && t["actuators_enabled"].is<bool>() &&
         t["heartbeat_fault"].is<bool>() && t["active_run"]=="runA");
  assert(t["heartbeat_fault"]==false);
  if(!ENABLE_ACTUATORS){
    assert(a["accepted"]==false && t["actuators_enabled"]==false);
    for(auto p:writes)assert(p.first!=25 && p.first!=26);
    for(auto p:modes)assert(p.first!=25 && p.first!=26);
    assert(t["estop"].isNull() && t["estop_valid"]==false);
    std::cout<<"default output guard and synchronization telemetry PASS\n";
    return 0;
  }
  assert(a["accepted"]==true && fanCommand && buzzerCommand);
  assert(t["fan_cmd"]==true && t["actuators_enabled"]==true);
  // A 50 ms pulse between reports must remain visible after physical release.
  pinLevels[32]=LOW;sampleEstop(1600);assert(estopLatched&&!fanCommand);
  pinLevels[32]=HIGH;sampleEstop(1650);
  t=telemetry(2000);
  assert(t["estop"]==false && t["estop_valid"]==true);
  assert(t["estop_latched"]==true && t["fan_cmd"]==false);
  a=command(2,true,2050);assert(a["accepted"]==false && !fanCommand);
  a=frame("{\"type\":\"rearm\",\"run_id\":\"runA\",\"id\":3}",2100);
  assert(a["accepted"]==true && !estopLatched && !fanCommand);
  t=telemetry(2500);assert(t["estop_latched"]==false);
  // Heartbeat handover itself preserves outputs and reports the accepted run.
  a=command(4,true,2600);assert(fanCommand);
  updateHeartbeatFault(4100);assert(fanCommand && heartbeatFault);
  beat("runB",1,4200);assert(fanCommand && !heartbeatFault);
  t=telemetry(4500);assert(t["active_run"]=="runB" && t["fan_cmd"]==true);
  // Maximum-width identity/counters still fit a single bounded TX slot.
  memset(activeRun,'x',RUN_ID_MAX);activeRun[RUN_ID_MAX]='\0';
  telemetrySequence=UINT32_MAX;uptimeMs=UINT64_MAX;
  t=telemetry(5000);assert(txQueue[txHead].length<TX_CAPACITY);
  assert(t["active_run"].as<JsonString>().size()==RUN_ID_MAX);
  std::cout<<"short ESTOP pulse, rearm, handover telemetry and TX bound PASS\n";
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arduinojson-dir", required=True, type=Path)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    include = args.arduinojson_dir.resolve()
    if not (include / "ArduinoJson.h").is_file():
        include /= "src"
    if not (include / "ArduinoJson.h").is_file():
        parser.error("ArduinoJson.h not found; supply an existing ArduinoJson 6/7 source tree")
    sketch = (Path(__file__).resolve().parents[1] / "firmware" /
              "esp32_reference" / "esp32_reference.ino").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="safeguard-firmware-host-") as tmp:
        root = Path(tmp)
        for name, content in HEADERS.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (root / "harness.cpp").write_text(HARNESS, encoding="utf-8")
        for mode in ("default", "enabled"):
            source = sketch
            if mode == "enabled":
                source = source.replace("constexpr bool ENABLE_ACTUATORS = false;",
                                        "constexpr bool ENABLE_ACTUATORS = true;")
                source = source.replace("constexpr bool ENABLE_ESTOP = false;",
                                        "constexpr bool ENABLE_ESTOP = true;")
            (root / "sketch.ino").write_text(source, encoding="utf-8")
            binary = root / ("test-" + mode)
            subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I" + str(root), "-I" + str(include),
                            str(root / "harness.cpp"), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print("Host mocks only; ESP32 target compilation and physical validation remain pending.")


if __name__ == "__main__":
    main()
