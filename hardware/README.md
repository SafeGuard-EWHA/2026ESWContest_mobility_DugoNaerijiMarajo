# hardware/ — 실제 Raspberry Pi 전용 코드

이 폴더의 코드는 **실제 Raspberry Pi 하드웨어에서만** 실행된다.
`app/streamlit_app.py`와 `src/` 이하 모든 모듈은 이 폴더를 import하지
않으므로, Streamlit Community Cloud처럼 GPIO가 없는 환경에서도 대시보드는
항상 정상 동작한다.

- `pi_hardware_logger.py`: PIR/DHT22/relay 상태를 읽어
  `data_loader.HARDWARE_LOG_COLUMNS` 스키마에 맞는 `hardware_log.csv`를
  기록하는 데이터 수집 스크립트. `gpiozero`, `RPi.GPIO`, `adafruit_dht`,
  `board`를 사용한다.
- `requirements-pi.txt`: 위 하드웨어 전용 패키지 목록. 웹 배포용
  `requirements.txt`(저장소 루트)에는 포함되지 않는다.

## 사용법 (Raspberry Pi에서만)

```bash
python -m pip install -r hardware/requirements-pi.txt
python hardware/pi_hardware_logger.py --duration 900 --out data/hardware_log.csv
```

수집된 `hardware_log.csv`는 대시보드의 "hardware_log.csv 업로드"에
그대로 사용하거나, `scripts/generate_paper_outputs.py --hardware-csv
data/hardware_log.csv`로 CLI에서 바로 처리할 수 있다.
