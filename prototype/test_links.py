import importlib.util,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'SafeGuard_Main/scripts'))
from uwb_startup import UwbStartup
spec=importlib.util.spec_from_file_location('check_link',ROOT/'SafeGuard_Software_Stop_20261024/check_link.py')
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
class StartupTests(unittest.TestCase):
 def test_live_stream_no_writes(self):
  s=UwbStartup(0);s.feed(b'dwm> DIST,1,AN0,0CA7,0,0,0,1.2\r\n');self.assertIsNone(s.action(10))
 def test_fragmented_stream(self):
  s=UwbStartup(0);s.feed(b'DI');s.feed(b'ST,');self.assertIsNone(s.action(4))
 def test_silent_prompt_single_lec(self):
  s=UwbStartup(0);self.assertIsNone(s.action(2));self.assertEqual(s.action(3),b'\r\r');s.feed(b'dw');s.feed(b'm> ');self.assertEqual(s.action(6),b'lec\r');self.assertIsNone(s.action(50))
 def test_no_prompt_no_lec(self):
  s=UwbStartup(0);self.assertEqual(s.action(3),b'\r\r');self.assertIsNone(s.action(6))
 def test_unknown_output_no_commands(self):
  s=UwbStartup(0);s.feed(b'garbage');self.assertIsNone(s.action(3))
 def test_stream_after_shell_no_toggle(self):
  s=UwbStartup(0);s.action(3);s.feed(b'dwm> DIST,');self.assertIsNone(s.action(6))
 def test_prompt_at_open(self):
  s=UwbStartup(0);s.feed(b'dwm> ');self.assertEqual(s.action(3),b'lec\r');self.assertIsNone(s.action(6))
class CheckTests(unittest.TestCase):
 def run_check(self,chunks,vid=0x10c4):
  clock=[0.0];box={}
  class Conn:
   def __init__(self,**kw):self.port=None;self.dtr=True;self.rts=True;self.closed=False;box['c']=self
   def open(self):assert self.dtr is False and self.rts is False
   @property
   def in_waiting(self):return 4096
   def read(self,n):clock[0]+=.5;return chunks.pop(0) if chunks else b''
   def close(self):self.closed=True
  serial=types.ModuleType('serial');serial.Serial=Conn
  tools=types.ModuleType('serial.tools');ports=types.ModuleType('serial.tools.list_ports')
  ports.comports=lambda:[types.SimpleNamespace(device='/dev/test',vid=vid,pid=0xea60)]
  tools.list_ports=ports
  with patch.dict(sys.modules,{'serial':serial,'serial.tools':tools,'serial.tools.list_ports':ports}),patch.object(check.time,'monotonic',lambda:clock[0]):
   try:return check.check('/dev/test')
   finally:
    if 'c' in box:self.assertTrue(box['c'].closed)
 def test_fragmented_status(self):
  data=json.dumps({'type':'status','firmware_id':check.FIRMWARE}).encode()+b'\n'
  self.assertEqual(self.run_check([b'boot\r\n',data[:20],data[20:]])['firmware_id'],check.FIRMWARE)
 def test_delayed_status_after_five_seconds(self):
  row=json.dumps({'type':'status','firmware_id':check.FIRMWARE}).encode()+b'\n'
  self.assertEqual(self.run_check([b'']*14+[row])['firmware_id'],check.FIRMWARE)
 def test_wrong_firmware_rejected(self):
  with self.assertRaisesRegex(ValueError,'other'):
   self.run_check([b'{"type":"status","firmware_id":"other"}\n'])
 def test_silence_diagnostic(self):
  with self.assertRaisesRegex(ValueError,'bytes=0'):self.run_check([])
 def test_wrong_device_rejected(self):
  with self.assertRaisesRegex(ValueError,'CP2102'):self.run_check([],vid=1)
class HubTests(unittest.TestCase):
 def test_dead_telemetry_reopens_and_clears_pending(self):
  import queue, threading
  from sensor_hub import SensorHub
  clock=[0]; connections=[]
  class Stop:
   stopped=False
   def is_set(self):return self.stopped
   def wait(self,t):self.stopped=True;return True
  class Conn:
   def __init__(self,**kw):self.closed=False;self.in_waiting=1;connections.append(self)
   def open(self):assert self.dtr is False and self.rts is False
   def read(self,n):
    clock[0]+=13
    hub.esp_outgoing.put({'type':'command','fan':True})
    return b'broken\n'
   def close(self):self.closed=True
  hub=types.SimpleNamespace(esp32_read_only=False,stop=Stop(),clock=lambda:clock[0],esp_outgoing=queue.Queue(),esp_pending={1:'old'},state_lock=threading.Lock(),warn=lambda *a:None)
  serial=types.ModuleType('serial');serial.Serial=Conn
  with patch.dict(sys.modules,{'serial':serial}):SensorHub.serial_worker(hub,'esp32','/dev/test',115200)
  self.assertEqual(len(connections),1);self.assertTrue(connections[0].closed)
  self.assertTrue(hub.esp_outgoing.empty());self.assertEqual(hub.esp_pending,{})
 def test_uwb_retry_stops_on_shutdown(self):
  from sensor_hub import SensorHub
  calls=[]
  class Stop:
   n=0
   def is_set(self):return self.n>=2
   def wait(self,t):self.n+=1;return self.n>=2
  hub=types.SimpleNamespace(stop=Stop(),uwb_session=lambda:calls.append(1))
  SensorHub.uwb_worker(hub);self.assertEqual(len(calls),2)
if __name__=='__main__':unittest.main()
