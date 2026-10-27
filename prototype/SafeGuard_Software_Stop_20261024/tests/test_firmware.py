"""Host build of delivered firmware, real ArduinoJson, mocked ESP32 peripherals."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from mock_headers import HEADERS
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "sketch.ino"
#include <cassert>
#include <iostream>
void clearTx(){txHead=txCount=0;Serial.tx.clear();}
Message frame(const std::string& line,uint32_t t){
 clearTx();clockMs=t;strcpy(rxLine,line.c_str());rxLength=line.size();processLine(t);
 Message ans;if(txCount)assert(!deserializeJson(ans,(const char*)txQueue[txHead].data,txQueue[txHead].length));return ans;
}
void beat(uint32_t seq,uint32_t t){frame("{\"type\":\"heartbeat\",\"run_id\":\"runA\",\"seq\":"+std::to_string(seq)+"}",t);}
Message cmd(int id,uint32_t t){return frame("{\"type\":\"command\",\"run_id\":\"runA\",\"id\":"+std::to_string(id)+",\"fan\":true,\"buzzer\":true,\"servo_deg\":100}",t);}
std::string resume(int id,unsigned gen){return std::string("{\"type\":\"rearm\",\"run_id\":\"runA\",\"id\":")+std::to_string(id)+",\"boot_id\":\""+bootId+"\",\"stop_generation\":"+std::to_string(gen)+"}";}
int main(){
 setup();assert(softwareStopLatched&&!fanCommand&&!buzzerCommand&&servoCommand==-1&&servoDuty==0);
 assert(observedSda==32&&observedScl==33&&PIR_PIN==27&&FAN_PIN==25&&BUZZER_PIN==26&&SERVO_PIN==13);
 beat(1,500);auto a=cmd(1,501);assert(a["accepted"]==false&&!fanCommand);
 frame("{\"type\":\"manual_stop\",\"stop_nonce\":\"main.stop.1\"}",510);auto gen=stopGeneration;
 frame("{\"type\":\"manual_stop\",\"stop_nonce\":\"main.stop.1\"}",520);assert(stopGeneration==gen);
 a=frame(resume(2,gen),530);assert(a["accepted"]==true&&!softwareStopLatched&&!fanCommand&&servoDuty==0);
 a=cmd(3,540);assert(a["accepted"]==true&&fanCommand&&buzzerCommand&&servoCommand==100);
 auto writesBefore=writes.size();a=cmd(3,550);assert(a["accepted"]==true&&writes.size()==writesBefore);
 // An operator stop overrides active outputs; a stale resume cannot undo it.
 frame("{\"type\":\"manual_stop\",\"stop_nonce\":\"main.stop.2\"}",560);
 assert(stopGeneration==gen+1&&softwareStopLatched&&!fanCommand&&!buzzerCommand&&servoDuty==0);
 a=cmd(3,570);assert(a["accepted"]==false);
 a=frame(resume(4,gen),580);assert(a["accepted"]==false&&softwareStopLatched);
 a=frame(resume(4,stopGeneration),590);assert(a["accepted"]==true&&!fanCommand);
 a=cmd(5,600);assert(a["accepted"]==true&&fanCommand&&buzzerCommand);
 updateHeartbeatFault(3500);assert(heartbeatFault&&fanCommand&&buzzerCommand&&servoDuty==0);
 // STOP is accepted even after heartbeat loss, without a valid current owner.
 frame("{\"type\":\"manual_stop\",\"stop_nonce\":\"main.stop.3\"}",3510);
 assert(softwareStopLatched&&!fanCommand&&!buzzerCommand);
 a=frame(resume(6,stopGeneration),3520);assert(a["accepted"]==false);
 beat(2,3530);a=frame(resume(7,stopGeneration),3540);assert(a["accepted"]==true);
 frame("STOP",3550);assert(softwareStopLatched&&!fanCommand&&servoDuty==0);
 // Protocol snapshots never claim a physical ESTOP exists.
 readSensors(4000);clearTx();sendTelemetry(4000);assert(txCount==1);Message t;
 assert(!deserializeJson(t,(const char*)txQueue[txHead].data,txQueue[txHead].length));
 assert(t["estop_valid"]==false&&t["estop"].isNull()&&t["physical_estop_installed"]==false);
 assert(t["software_control_version"]==1&&t["software_stop_latched"]==true);
 assert(t["temp_valid"]==true&&t["servo_cmd"].isNull());
 memset(activeRun,'x',RUN_ID_MAX);activeRun[RUN_ID_MAX]=0;memset(stopNonce,'y',64);stopNonce[64]=0;
 telemetrySequence=UINT32_MAX;uptimeMs=UINT64_MAX;clearTx();sendTelemetry(5000);
 assert(txCount==1&&txQueue[txHead].length<TX_CAPACITY);
 std::cout<<"PASS firmware: boot latch, STOP active outputs, idempotent retries, stale resume, lost heartbeat, physical-input truth, bounded telemetry\n";
}
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--arduinojson-dir',type=Path,required=True);a=p.parse_args()
 inc=a.arduinojson_dir
 if not (inc/'ArduinoJson.h').exists():inc/='src'
 with tempfile.TemporaryDirectory() as tmp:
  d=Path(tmp)
  for name,value in HEADERS.items():
   f=d/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(value)
  (d/'sketch.ino').write_text((ROOT/'firmware/SafeGuard_Software_Stop/SafeGuard_Software_Stop.ino').read_text())
  (d/'test.cpp').write_text(HARNESS)
  for major in (2,3):
   (d/'esp_arduino_version.h').write_text('#define ESP_ARDUINO_VERSION_MAJOR '+str(major)+'\n')
   subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(d),'-I'+str(inc),str(d/'test.cpp'),'-o',str(d/'test')],check=True)
   subprocess.run([str(d/'test')],check=True)
if __name__=='__main__':main()
