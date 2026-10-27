"""Synthetic UART bytes only: no serial port or physical output is opened."""
import hashlib
import importlib.util
import math
from pathlib import Path
import struct
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('radar',ROOT/'patch/scripts/mmwave_input.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def packet(number=1,tlvs=(),padding=True):
 body=b''.join(struct.pack('<II',k,len(v))+v for k,v in tlvs)
 size=40+len(body)
 if padding:size=(size+31)//32*32
 return m.MAGIC+struct.pack('<8I',0x3060200,size,0xa6843,number,0,0,len(tlvs),0)+body+b'\0'*(size-40-len(body))
def frame(number=1,tracks=0,presence=0):
 tlvs=[]
 if tracks is not None:tlvs.append((1010,b''.join(struct.pack('<I27f',i,*([1.0]*27)) for i in range(tracks))))
 if presence is not None:tlvs.append((1021,struct.pack('<I',presence)))
 return packet(number,tlvs)
def settings():return dict(enabled=True,profile='people_tracking_ods',firmware_confirmed=True,usb_serial='01E86213',configure_on_start=False,allow_omitted_empty_tracks=False,validated=True)
class ParserTests(unittest.TestCase):
 def test_fragments_noise_and_multiple_frames(self):
  stream=m.Stream();wire=b'noise'+frame(1)+frame(2,1)+frame(3,None,1)
  got=[]
  for i in range(0,len(wire),7):got.extend(stream.feed(wire[i:i+7]))
  self.assertEqual([f['frame_number'] for f,e in got],[1,2,3]);self.assertTrue(all(e is None for f,e in got))
 def test_track_truncation_is_not_zero_tracks(self):
  for n in (1,111,113):
   with self.assertRaisesRegex(ValueError,'track'):m.parse_packet(packet(tlvs=[(1010,b'\0'*n)]))
 def test_missing_track_is_distinct_from_zero(self):
  self.assertIsNone(m.parse_packet(frame(tracks=None))['num_tracks'])
  self.assertEqual(m.parse_packet(frame())['num_tracks'],0)
 def test_wrong_firmware_and_duplicate_tlv(self):
  for tlvs in ([(1040,b'\0'*136)],[(1021,b'\0'*4)]*2,[(9999,b'')]):
   with self.assertRaises(ValueError):m.parse_packet(packet(tlvs=tlvs))
 def test_nan_track_and_bad_presence(self):
  for tlvs in ([(1010,struct.pack('<I27f',0,*([float('nan')]+[0.0]*26)))],[(1021,b'\0')],[(1021,struct.pack('<I',2))]):
   with self.assertRaises(ValueError):m.parse_packet(packet(tlvs=tlvs))
 def test_compressed_length_and_finite_units(self):
  units=struct.pack('<5f',.1,.1,.1,.1,.1)
  m.parse_packet(packet(tlvs=[(1020,units+b'\0'*8)]))
  for data in (units+b'\0',b'\0'*20):
   with self.assertRaises(ValueError):m.parse_packet(packet(tlvs=[(1020,data)]))
 def test_bad_length_resynchronizes(self):
  bad=bytearray(frame());struct.pack_into('<I',bad,12,70000)
  events=m.Stream().feed(bad+frame(2));self.assertEqual(events[-1][0]['frame_number'],2)
  self.assertTrue(any(e for f,e in events))
 def test_packet_and_padding_integrity(self):
  original=frame()
  for data in (original[:-1],original+b'\0',b'bad',original[:8]+b'\0'*32):
   with self.assertRaises(ValueError):m.parse_packet(data)
 def test_noise_buffer_bounded(self):
  stream=m.Stream();stream.feed(b'x'*100000);self.assertLessEqual(len(stream.buffer),7)
class EvidenceTests(unittest.TestCase):
 def test_truth_table(self):
  for tracks,presence,expected in [(1,0,True),(0,1,True),(None,1,True),(0,0,False),(None,0,None),(0,None,None),(None,None,None)]:
   state=m.Evidence();state.accept(m.parse_packet(frame(1,tracks,presence)),1)
   self.assertEqual(state.evidence,expected);self.assertEqual(state.snapshot(1)['valid'],expected is not None)
 def test_omission_requires_explicit_contract(self):
  state=m.Evidence(allow_omitted_empty_tracks=True);state.accept(m.parse_packet(frame(1,None,0)),1)
  self.assertTrue(state.snapshot(1)['valid']);self.assertFalse(state.evidence)
 def test_exact_timeout_not_fresh_and_recovery(self):
  state=m.Evidence();state.accept(m.parse_packet(frame()),1)
  self.assertTrue(state.snapshot(2.99)['valid']);self.assertFalse(state.snapshot(3)['valid'])
  self.assertEqual(state.snapshot(3)['status'],'frame_timeout')
  state.invalidate('frame_timeout');old=state.epoch;state.accept(m.parse_packet(frame(2)),4)
  self.assertTrue(state.snapshot(4)['valid']);self.assertGreater(state.epoch,old)
 def test_duplicate_does_not_refresh(self):
  state=m.Evidence();f=m.parse_packet(frame());state.accept(f,1);state.accept(f,2)
  self.assertEqual(state.last_rx,1);self.assertFalse(state.snapshot(2)['valid'])
 def test_restart_latches_but_wrap_works(self):
  state=m.Evidence();state.accept(m.parse_packet(frame(20)),1);state.accept(m.parse_packet(frame(1)),2)
  state.accept(m.parse_packet(frame(21)),3);self.assertTrue(state.restart_required);self.assertFalse(state.snapshot(3)['valid'])
  state=m.Evidence();state.accept(m.parse_packet(frame(0xffffffff)),1);state.accept(m.parse_packet(frame(0)),2)
  self.assertTrue(state.snapshot(2)['valid'])
 def test_hidden_transitions_change_continuity(self):
  state=m.Evidence();state.accept(m.parse_packet(frame(1)),1);old=state.epoch
  state.accept(m.parse_packet(frame(2,1)),1.1);state.accept(m.parse_packet(frame(3)),1.2)
  self.assertGreater(state.epoch,old);self.assertFalse(state.evidence)
  old=state.epoch;state.invalidate('bad_packet');state.accept(m.parse_packet(frame(4)),1.3)
  self.assertGreater(state.epoch,old)
class ConfigurationTests(unittest.TestCase):
 def test_guards(self):
  cfg=settings();fsm={'mmwave_observe_s':5};self.assertEqual(m.checked_settings(cfg,{},fsm),2)
  for key,value in [('firmware_confirmed',False),('profile','vitals'),('usb_serial','0001'),('validated','true')]:
   with self.assertRaises(ValueError):m.checked_settings(dict(cfg,**{key:value}),{},fsm)
  with self.assertRaises(ValueError):m.checked_settings(cfg,{'mmwave_json_port':'COM5'},fsm)
  for key,values in [('mmwave_timeout_s',[0,True,float('nan')]),('mmwave_observe_s',[2,float('inf'),'5'])]:
   for value in values:
    with self.assertRaises(ValueError):m.checked_settings(cfg,{},dict(fsm,**{key:value}))
 def test_cfg_hash_and_profile(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.cfg';p.write_text('sensorStop\ntrackingCfg 1\npresenceBoundaryBox 0\nantGeometry0 0\nantGeometry1 0\nsensorPosition 0\nsensorStart\n')
   cfg={'cfg_path':str(p),'cfg_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
   self.assertEqual(m.cfg_lines(cfg)[-1],'sensorStart')
   p.write_text(p.read_text()+'\nchanged')
   with self.assertRaises(ValueError):m.cfg_lines(cfg)
 def test_cfg_fail_fast(self):
  class Port:
   in_waiting=1
   def __init__(self,response):self.response=response;self.sent=[]
   def reset_input_buffer(self):pass
   def write(self,b):self.sent.append(b)
   def read(self,n):return self.response
  for response in (b'Error -1\n',b'Ignored\nDone\n'):
   port=Port(response)
   with self.assertRaises(RuntimeError):m.send_cfg(port,['flushCfg','sensorStart'],threading.Event())
   self.assertEqual(port.sent,[b'flushCfg\n'])
  port=Port(b'Done\n');m.send_cfg(port,['flushCfg','sensorStart'],threading.Event());self.assertEqual(len(port.sent),2)
class WorkerTests(unittest.TestCase):
 def run_worker(self,validated=True,processing=True):
  class Hub:
   def __init__(self):
    self.stop=threading.Event();self.t=10.;self.messages=[];self.config={'fsm':{'mmwave_observe_s':5}}
    self.hardware={'mmwave_validated':validated};self.seq=0
   def clock(self):return self.t
   def flags(self):return {'mmwave':processing}
   def envelope(self,kind,source,t):self.seq+=1;return dict(type=kind,source=source,rx_monotonic_s=t,seq=self.seq,run_id='fixture')
   def emit(self,msg):self.messages.append(msg)
   def remember(self,*args):pass
   def warn(self,*args):raise AssertionError(args)
  hub=Hub();chunks=[frame(1),frame(2,1),frame(3)]+[b'']*23+[frame(4)[:12],frame(4)[12:]]
  class Port:
   in_waiting=1
   def __init__(self,is_data):self.data=is_data;self.sent=[]
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def reset_input_buffer(self):pass
   def write(self,b):self.sent.append(b)
   def read(self,n):
    hub.t+=.1
    if not chunks:hub.stop.set();return b''
    return chunks.pop(0)
  cli=Port(False);data=Port(True)
  fake=types.SimpleNamespace(Serial=lambda path,*a,**k:data if path=='data' else cli)
  with patch.dict(sys.modules,{'serial':fake}),patch.object(m,'checked_ports',return_value=('cli','data')):
   m.run(hub,settings())
  self.assertEqual(cli.sent,[b'sensorStop\n']);return hub.messages
 def test_timeout_and_fragmented_recovery(self):
  messages=self.run_worker();self.assertTrue(any(x['status']=='frame_timeout' and not x['valid'] for x in messages))
  self.assertTrue(any(x.get('frame_number')==4 and x['valid'] for x in messages))
  self.assertTrue(any(x['evidence'] for x in messages));self.assertTrue(all('continuity_epoch' in x for x in messages))
 def test_unvalidated_and_disabled_cannot_be_valid(self):
  for messages in (self.run_worker(False),self.run_worker(True,False)):
   self.assertTrue(messages);self.assertFalse(any(x['valid'] or x['evidence'] for x in messages))
if __name__=='__main__':unittest.main()
