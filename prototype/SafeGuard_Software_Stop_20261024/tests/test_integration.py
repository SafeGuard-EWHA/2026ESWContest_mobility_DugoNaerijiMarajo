"""SOFTWARE ONLY. Real delivered MCU logic + hub + C++ + HTTP, mocked peripherals.
Synthetic camera/UWB are injected ONLY into a disposable test copy, never shipped
in production scripts/configs. This is not evidence of live sensor/output behavior.
"""
import argparse, errno, json, os, pty, select, shutil, socket, subprocess, tempfile
import threading, time, tty, urllib.request
from pathlib import Path
from mock_headers import HEADERS
ROOT=Path(__file__).resolve().parents[1]
BRIDGE=r'''
#include "sketch.ino"
#include <chrono>
#include <unistd.h>
#include <poll.h>
int main(){
 setup();pirWarmed=true;pinLevels[PIR_PIN]=HIGH;
 auto start=std::chrono::steady_clock::now();
 while(true){
  clockMs=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
  pollfd p{STDIN_FILENO,POLLIN,0};poll(&p,1,2);
  if(p.revents&POLLIN){char b[2048];auto n=read(STDIN_FILENO,b,sizeof b);if(n<=0)break;for(int i=0;i<n;i++)Serial.rx.push_back(b[i]);}
  loop();if(!Serial.tx.empty()){auto n=write(STDOUT_FILENO,Serial.tx.data(),Serial.tx.size());if(n<0)break;Serial.tx.erase(0,n);}
 }
}
'''
FIXTURE='''
                # TEST COPY ONLY: synthetic sensor evidence, never production.
                if not hasattr(self, "fixture_uwb"):
                    self.fixture_uwb=self.uwb_module.DistanceState(7,2.0,"0CA7","TEST_ONLY")
                    self.emit(self.uwb_module.main_message(self.fixture_uwb.snapshot(tick_start),window=7,timeout_s=2.0,run_id=self.run_id+"-fixture"))
                self.fixture_uwb.accept(6.0,tick_start)
                self.emit(self.uwb_module.main_message(self.fixture_uwb.snapshot(tick_start),window=7,timeout_s=2.0,run_id=self.run_id+"-fixture"))
                camera=self.envelope("camera","REAL_CAMERA",tick_start)
                camera.update(valid=True,motion=True)
                self.remember("camera",tick_start);self.emit(camera)
'''
def run(project,include):
 with tempfile.TemporaryDirectory(prefix='software-stop-test-') as td:
  d=Path(td);fwdir=d/'fw';fwdir.mkdir();main=d/'main';main.mkdir()
  for name,value in HEADERS.items():
   p=fwdir/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
  (fwdir/'esp_arduino_version.h').write_text('#define ESP_ARDUINO_VERSION_MAJOR 3\n')
  shutil.copyfile(ROOT/'firmware/SafeGuard_Software_Stop/SafeGuard_Software_Stop.ino',fwdir/'sketch.ino')
  (fwdir/'bridge.cpp').write_text(BRIDGE)
  subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(fwdir),'-I'+str(include),str(fwdir/'bridge.cpp'),'-o',str(fwdir/'bridge')],check=True)
  for name in ('scripts','configs'):shutil.copytree(project/name,main/name)
  (main/'build').mkdir();shutil.copyfile(project/'build/safeguard_main',main/'build/safeguard_main')
  os.chmod(main/'build/safeguard_main',0o755)
  hp=main/'scripts/sensor_hub.py';s=hp.read_text();needle='                tick_start = self.clock()\n'
  assert needle in s;hp.write_text(s.replace(needle,needle+FIXTURE))
  master,slave=pty.openpty();tty.setraw(slave);port=os.ttyname(slave)
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));http_port=sock.getsockname()[1]
  cfg=json.loads((main/'configs/real_navigation.json').read_text())
  cfg['hardware'].update(esp32_port=port,esp32_protocol='link',uwb_enabled=False,camera_enabled=False,mmwave_json_port='')
  cfg['required'].update(esp32=False,camera=True,mmwave=False)
  cfg['actuation'].update(enabled=True,servo_protect_deg=100)
  cfg['manual_control']={'enabled':True};cfg['ambient_provider']={'enabled':False}
  cfg['dashboard']['port']=http_port;cfg['thermal']['risk_temp_c']=22.0
  cfg['fsm'].update(departure_hold_s=.3,mmwave_timeout_s=.3)
  cp=main/'configs/test_only.json';cp.write_text(json.dumps(cfg))
  fw=subprocess.Popen([str(fwdir/'bridge')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,bufsize=0)
  end=threading.Event();wire=[];board=[];errors=[];pause=[False];drop_resume_acks=[1];rxbuffer=bytearray();txbuffer=bytearray()
  def pump():
   try:
    while not end.is_set():
     ready,_,_=select.select([master,fw.stdout],[],[],.03)
     for fd in ready:
      if fd==master:
       try:b=os.read(master,4096)
       except OSError as e:
        if e.errno==errno.EIO:continue
        raise
       txbuffer.extend(b)
       while b'\n' in txbuffer:
        line,_,tail=txbuffer.partition(b'\n');txbuffer[:]=tail
        try:wire.append(json.loads(line))
        except ValueError:pass
       if not pause[0]:fw.stdin.write(b)
      else:
       b=os.read(fw.stdout.fileno(),4096)
       if not b:return
       rxbuffer.extend(b)
       while b'\n' in rxbuffer:
        line,_,tail=rxbuffer.partition(b'\n');rxbuffer[:]=tail
        row=json.loads(line);board.append(row)
        if row.get('type')=='ack' and row.get('reason')=='software_stop_rearmed_outputs_off' and drop_resume_acks[0]>0:
         drop_resume_acks[0]-=1;continue
        if not pause[0]:os.write(master,line+b'\n')
   except Exception as e:errors.append(repr(e))
  thread=threading.Thread(target=pump,daemon=True);thread.start()
  out=(d/'console.txt').open('w+');proc=None;url=f'http://127.0.0.1:{http_port}'
  def start():
   return subprocess.Popen([str(main/'build/safeguard_main'),'--config',str(cp),'--duration','45'],cwd=main,stdout=out,stderr=out)
  def state():
   try:
    with urllib.request.urlopen(url+'/api/state',timeout=.5) as r:return json.load(r)
   except (OSError,ValueError):return {}
  def until(test,seconds=8):
   deadline=time.monotonic()+seconds;last={}
   while time.monotonic()<deadline:
    last=state()
    if last and test(last):return last
    if proc.poll() is not None:break
    time.sleep(.08)
   out.flush();raise AssertionError((last,(d/'console.txt').read_text()[-5000:]))
  def action(name):
   payload={'action':name}
   if name=='manual_resume':payload['stop_request_id']=state()['manual_control']['stop_request_id']
   q=urllib.request.Request(url+'/api/control',json.dumps(payload).encode(),{'Content-Type':'application/json','Origin':url},method='POST')
   with urllib.request.urlopen(q,timeout=2) as r:assert r.status==202
  def stopped(s):return s.get('manual_control',{}).get('stop_confirmed') is True
  def protected(s):return s.get('state')=='PROTECTION' and s.get('outputs',{}).get('ack_status')=='ACK_RECEIVED_NOT_PHYSICAL_FEEDBACK' and s['manual_control'].get('servo_cmd')==100
  try:
   proc=start();initial=until(stopped);assert initial['state']=='MANUAL_STOP'
   assert not any(x.get('type')=='command' and x.get('fan') for x in wire)
   action('manual_resume');on=until(protected,12)
   assert on['manual_control']['fan_cmd'] and on['manual_control']['buzzer_cmd']
   # All actuators ON -> HTTP STOP -> production hub -> MCU -> fresh telemetry.
   action('manual_stop');s=until(stopped);assert s['manual_control']['servo_cmd'] is None
   assert not s['manual_control']['fan_cmd'] and not s['manual_control']['buzzer_cmd']
   since=len(wire);time.sleep(1.3);assert not any(x.get('type')=='command' and x.get('fan') for x in wire[since:])
   previous=state()['manual_control']['stop_request_id']
   action('manual_resume');action('manual_stop')
   until(lambda s:stopped(s) and s['manual_control']['stop_request_id']!=previous)
   action('manual_resume');until(protected,12)
   # Both directions interrupted. Do not report stopped from old data.
   pause[0]=True;s=until(lambda s:s.get('manual_control',{}).get('status')=='CONTROLLER_UNAVAILABLE_STOP_UNCONFIRMED')
   assert s['manual_control']['stop_confirmed'] is False
   time.sleep(1.3)
   latest=next(x for x in reversed(board) if x.get('type')=='telemetry')
   assert latest['fan_cmd'] and latest['buzzer_cmd'] and latest['heartbeat_fault'] and latest['servo_cmd'] is None
   pause[0]=False;until(stopped)
   # Restarting the real main cannot silently clear the software latch.
   proc.terminate();proc.wait(timeout=5);time.sleep(.3);proc=start();until(stopped)
   assert not errors,errors
   assert not any(x.get('estop_valid') is True for x in board)
   print('PASS integration: startup hold; explicit resume with lost-ACK retry; FSM requests fan/buzzer/servo ON; live HTTP STOP; holds; resume/stop race; lost-link status; retained fan/buzzer; reconnect STOP; main restart remains held.')
   print('SOFTWARE ONLY: synthetic sensor fixtures and mocked GPIO. No live hardware verified.')
  finally:
   if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=5)
   end.set();thread.join(2);fw.terminate();fw.wait(timeout=3);os.close(master);os.close(slave);out.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--arduinojson-dir',type=Path,required=True);a=p.parse_args()
 inc=a.arduinojson_dir
 if not (inc/'ArduinoJson.h').exists():inc/='src'
 run(a.project.resolve(),inc)
