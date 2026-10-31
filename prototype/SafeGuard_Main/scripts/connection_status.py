"""Phone/weather-only inspection. No sensor, serial, camera or controller imports."""
import json
from pathlib import Path
import secrets
import threading
import time
from navigation_ambient import PhoneAmbientProvider


class ConnectionStatus:
    def __init__(self, project, provider=None, clock=time.monotonic):
        self.clock=clock;self.started=clock();self.run_id='connection-check-'+secrets.token_hex(8)
        config=json.loads((Path(project)/'configs/real_navigation_control.json').read_text())
        settings=dict(config['ambient_provider'])
        settings['location_file']=str(Path(project).resolve()/'runtime/navigation_location.json')
        self.provider=provider if provider is not None else PhoneAmbientProvider(settings)
        self.thresholds={k:config['fsm'][k] for k in ('departure_distance_m','departure_hold_s')}
        self.thresholds['risk_temp_c']=config['thermal']['risk_temp_c']
        self.stop=threading.Event();self.worker=None

    def start(self):
        def work():
            while not self.stop.is_set():
                self.provider.refresh()
                self.stop.wait(1)
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=10)

    def snapshot(self):
        weather=self.provider.snapshot()
        valid=weather.get('valid') is True
        return {'state':'CONNECTION_CHECK','reason':'hardware_not_connected_connection_only',
            'mode':'CONNECTION_CHECK','profile':'CONNECTION_CHECK','read_only':True,
            'run_id':self.run_id,'elapsed_s':round(self.clock()-self.started,3),
            'guardian':'UNKNOWN','occupant':'UNKNOWN','thresholds':self.thresholds,
            'inputs':{'temperature':{'valid':False,'temp_c':None,'source':'MISSING'},
                'ambient':{'valid':valid,'temp_c':weather.get('temp_c') if valid else None,'source':'REAL_AMBIENT'},
                **{name:{'valid':False,'source':'MISSING'} for name in ('uwb','pir','camera','mmwave','esp32','estop')}},
            'ambient_provider':weather,
            'thermal_observer':{'enabled':True,'model':'ambient_heat_balance_observer_v2','valid':False,
                'control_enabled':False,'reason':'hardware_not_connected','history_s':0,'t35_s':None,'curve':[]},
            'outputs':{'actuation_enabled':False,'fan':None,'buzzer':None,'ack_status':'NOT_SENT_DRY_RUN'},
            'manual_control':{'enabled':False,'held':True,'resume_available':False},
            'faults':['접속 점검 모드 · 실내 센서와 제어기는 사용하지 않습니다.']}
