# 논문/포스터 삽입용 링크 문구 & QR 코드 안내

배포된 Streamlit 앱의 실제 URL은 다음과 같다:
**https://safeguard-mmwave-simulator.streamlit.app**

GitHub 저장소: **https://github.com/yoontf0/safeguard-mmwave-simulator**

아래 문장은 이미 실제 URL로 채워져 있으므로 그대로 논문/포스터에 복사해서
사용하면 된다.

## 1) 논문 본문 삽입용 문장

**국문 (본문/각주)**

> 본 논문에서 제안한 SafeGuard 시스템의 시뮬레이션 결과는 아래 웹
> 데모에서 별도 설치 없이 직접 확인할 수 있다:
> https://safeguard-mmwave-simulator.streamlit.app
> (본 데모는 output-level virtual sensor simulation과 추정 전력 모델
> 기반이며, 실측값이 아님에 유의한다.)

**국문 (각주/부록, 짧은 버전)**

> Live demo: https://safeguard-mmwave-simulator.streamlit.app

**영문 (International submission 대비)**

> An interactive web demo of the SafeGuard TwinLab Agent simulator
> (no installation required) is available at:
> https://safeguard-mmwave-simulator.streamlit.app. Note that sensor
> signals are output-level virtual simulations and power values are
> estimates, not hardware measurements.

## 2) Figure/QR 캡션 문구

**국문**

> Figure N. SafeGuard TwinLab Agent 웹 데모 QR 코드. 스캔 시
> https://safeguard-mmwave-simulator.streamlit.app 으로 연결되며, 별도
> 설치 없이 브라우저에서 시뮬레이션을 직접 조작할 수 있다.

**영문**

> Figure N. QR code linking to the SafeGuard TwinLab Agent interactive
> web demo (https://safeguard-mmwave-simulator.streamlit.app). No local
> installation is required to explore the simulator.

## 3) QR 코드 생성 방법

배포가 이미 완료되었으므로 아래 명령을 바로 실행해 실제 QR 코드 PNG를
생성할 수 있다.

```bash
python -m pip install "qrcode[pil]"
python scripts/generate_qr_code.py https://safeguard-mmwave-simulator.streamlit.app --out docs/qr_code.png
```

생성된 `docs/qr_code.png`를 논문/포스터에 삽입하면 된다.

## 4) 체크리스트

- [x] Streamlit Cloud 배포 완료, 실제 URL 확보
      (https://safeguard-mmwave-simulator.streamlit.app)
- [x] 위 1)~2)의 링크 문구에 실제 URL 반영 완료
- [ ] `python scripts/generate_qr_code.py https://safeguard-mmwave-simulator.streamlit.app`로
      `docs/qr_code.png` 생성 (로컬에서 `qrcode` 패키지 설치 후 1회 실행 필요)
- [ ] 논문/포스터에 QR 코드 이미지와 캡션 삽입
- [x] README.md 상단 배지, `docs/index.md`의 Live Demo 링크에도 동일 URL 반영 완료
