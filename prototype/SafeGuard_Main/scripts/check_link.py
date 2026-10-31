"""Identify the firmware without UART payload writes. Opening USB can reset ESP32."""
import argparse, json, os, time
from pathlib import Path
FIRMWARE='SafeGuard_Software_Stop-0.3.0'
def check(port):
 import serial
 from serial.tools import list_ports
 matches=[p for p in list_ports.comports() if os.path.realpath(p.device)==os.path.realpath(port)]
 if len(matches)!=1 or (matches[0].vid,matches[0].pid)!=(0x10c4,0xea60):
  raise ValueError('Expected the A-block CP2102 USB port; check --list. Do not use the mmWave CP2105 ports.')
 conn=serial.Serial(port=None,baudrate=115200,timeout=.2,write_timeout=1,exclusive=True)
 conn.dtr=False;conn.rts=False;conn.port=port
 try:
  conn.open();buffer=bytearray();end=time.monotonic()+15
  received=invalid=0; observed=set()
  while time.monotonic()<end:
   chunk=conn.read(min(max(conn.in_waiting,1),4096));received+=len(chunk);buffer.extend(chunk)
   if len(buffer)>16384:buffer.clear()
   while b'\n' in buffer:
    line,_,tail=buffer.partition(b'\n');buffer[:]=tail
    try:row=json.loads(line)
    except (ValueError,UnicodeError):
     invalid+=1;continue
    if isinstance(row,dict) and row.get("type")=="status":observed.add(str(row.get("firmware_id")))
    if isinstance(row,dict) and row.get('type')=='status' and row.get('firmware_id')==FIRMWARE:
     print('FIRMWARE_OK:',FIRMWARE,flush=True);return row
  raise ValueError('Firmware check timed out after 15s: bytes=%d, invalid_lines=%d, status_ids=%s. '
                   'No automatic upload or bypass. Check USB/power and captured status first.'
                   % (received,invalid,sorted(observed)))
 finally:conn.close()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--list',action='store_true');p.add_argument('--port');a=p.parse_args()
 try:
  if a.list:
   from serial.tools import list_ports
   for port in list_ports.comports():print(port.device,port.description,port.hwid)
  elif a.port:print(json.dumps(check(a.port),ensure_ascii=False,indent=2))
  else:p.error('Use --list or --port')
 except (OSError,ValueError,ImportError) as e:p.exit(2,str(e)+'\n')
