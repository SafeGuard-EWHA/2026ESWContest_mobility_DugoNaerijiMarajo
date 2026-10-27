# SafeGuard 아이폰 차량 위치 연동 0.1.0

아이폰이 알아낸 실제 위치를 Pi에 자동 전달하고, Pi가 그 좌표로 Open-Meteo 외기 온도를 조회하는 추가 패키지입니다. 기존 SafeGuard_Main 0.1.1 + Ambient Update가 설치된 Pi용입니다.

## 무엇을 연결하나

- 팀원 아이폰 A: 기존 핫스팟 제공. 그 폰의 설정은 그대로 둡니다.
- 내 아이폰 B: 차량 내비게이션 대용. A의 핫스팟에 연결하고 Pi와 함께 둡니다.
- Pi + 노트북: 같은 A의 핫스팟에 연결합니다.
- 아이폰 B 위치 → Pi의 전용 HTTPS 수신기 → 실제 기상 API → 기존 메인 프로그램의 외기 온도 입력.

아이폰 B와 Pi가 함께 움직이면 위치가 갱신됩니다. 보호자 역할의 사람이 떠날 때는 아이폰 B를 차량 역할의 Pi 옆에 남겨둡니다. 아이폰 B를 보호자가 가져가면 보호자의 위치를 보내게 됩니다.

처음 한 번 연결 설정 후에는 위도·경도를 직접 입력하지 않습니다. 이번 버전은 Safari 화면을 켜놓는 시연용입니다. 화면 잠금·앱 전환 후 자동 백그라운드 동작은 지원하지 않습니다.

## 1. 파일을 Pi로 보내기 — Windows 검은 창

다운로드한 ZIP을 `C:\SafeGuard_C\SafeGuard_Navigation_Update.zip`에 넣으세요. 이름에 `(1)` 등이 붙지 않았는지 확인합니다.

Windows 창의 `C:\Users\shinh>` 또는 `C:\SafeGuard_C>` 뒤에 실행합니다.

```cmd
scp C:\SafeGuard_C\SafeGuard_Navigation_Update.zip pi@safeguard.local:/home/pi/
ssh pi@safeguard.local
```

암호를 입력할 때 화면에 글자가 나타나지 않는 것은 정상입니다. `pi@safeguard:~ $`가 나오면 이제 Pi의 창입니다. `scp` 후에는 ZIP만 전송된 것이므로 반드시 `ssh`로 접속해야 합니다.

## 2. 설치와 수신기 시작 — Pi 창 1

기존 메인 프로그램이 실행 중이라면 그 프로그램 창에서 Ctrl+C로 먼저 종료합니다. 아래 명령을 차례로 실행하세요. 앞 명령에서 오류가 나면 뒤 명령을 계속 실행하지 말고 출력 내용을 확인합니다.

```bash
unzip -n ~/SafeGuard_Navigation_Update.zip -d ~
python3 ~/SafeGuard_Navigation_Update/install_navigation.py --project ~/SafeGuard_Main
python3 ~/SafeGuard_Navigation_Update/start_navigation.py --project ~/SafeGuard_Main
```

설치는 기존 하드웨어 설정을 보존하고 `configs/real_navigation.json`을 따로 만듭니다. 이 설정의 팬·부저 실제 제어와 보정 전 온도 예측은 비활성입니다. 기존 설정 파일과 C++ 실행 파일은 바꾸지 않습니다. 교체할 원본 코드는 `~/SafeGuard_Main/backups/navigation_...`에 보관합니다.

마지막 명령은 종료되지 않고 아래 항목을 출력한 채 기다립니다.

- `Setup: http://실제-Pi-IP:8081/` — 처음 설정하는 아이폰용 주소
- `Phone: https://실제-Pi-IP:8443/` — 위치 전송 화면 주소
- `CA SHA-256: ...` — 인증서 확인용 지문
- `PAIRING CODE ...: 8자리숫자` — 연결 코드

**창 1은 켜두세요.** 위에 적힌 `실제-Pi-IP`를 그대로 입력하는 것이 아니라, 프로그램이 출력한 숫자 주소 전체를 사용합니다. 수신기를 다시 실행하면 연결 코드가 바뀝니다. 코드 유효시간은 10분이며 한 대만 연결합니다.

## 3. 내 아이폰 B에서 최초 연결 설정

Safari가 위치 정보를 읽으려면 신뢰할 수 있는 HTTPS 연결이 필요합니다. Pi가 이번 시연용 인증서를 직접 만들며, 내 아이폰에 최초 1회 설치·신뢰하는 방식입니다. 앱스토어 앱 구매나 새 GPS 장비는 필요하지 않습니다.

1. 내 아이폰 B를 팀원 아이폰 A의 핫스팟에 연결합니다.
2. **Safari 주소창**에 Pi 창의 `Setup:` 주소를 입력합니다. `http://`와 `:8081`까지 포함합니다.
3. 페이지에 표시된 인증서 SHA-256 지문과 Pi 터미널의 지문이 같은지 확인합니다.
4. **1. SafeGuard 공개 인증서 다운로드**를 누릅니다. 프로파일 다운로드를 허용합니다.
5. 아이폰 **설정 → 일반 → VPN 및 기기 관리**에서 `SafeGuard Local Navigation Demo` 프로파일을 열고 **설치**합니다. ‘프로파일이 다운로드됨’ 메뉴로 들어가도 됩니다. 프로파일에는 이 인증서 1개만 있어야 합니다.
6. **설정 → 일반 → 정보 → 인증서 신뢰 설정**에서 해당 SafeGuard 인증서의 전체 신뢰를 켭니다.
7. Safari로 돌아와 **2. 위치 전달 화면 열기**를 누릅니다. Pi 창의 `Phone:` 주소를 직접 입력해도 됩니다. 이번에는 `https://`와 `:8443`입니다.
8. 화면에 Pi의 **8자리 연결 코드**를 입력하고 **연결하기**를 누릅니다.
9. **시연 시작**을 누르고 위치 접근을 **허용**합니다. 정확한 위치 옵션이 있으면 켭니다.
10. `위치 자동 전달 중`과 실제 위도·경도가 표시되고, `Pi 수신 확인 횟수`가 증가하는지 확인합니다.

이 프로파일은 인증서만 포함하고 MDM·VPN·프록시 설정은 포함하지 않습니다. 인증서는 해당 Pi 주소와 `safeguard.local` 범위로 제한하며 유효기간은 30일입니다. 인증서 서명용 개인 키는 생성 후 삭제하고 서버 개인 키는 Pi 안에 둡니다. HTTPS 경고가 남아 있으면 경고를 우회하지 말고 주소·인증서 설치·신뢰 설정을 확인합니다.

위치 권한이 거부된 경우: 설정 → 개인정보 보호 및 보안 → 위치 서비스가 켜져 있는지, Safari 웹 사이트의 위치 접근이 허용됐는지 확인합니다. 해당 Safari 웹 사이트의 위치 권한도 허용으로 변경한 뒤 다시 시연 시작을 누릅니다. 메뉴 이름은 iOS 버전에 따라 조금 다를 수 있습니다.

## 4. 메인 프로그램으로 온도 받기 — Pi 창 2

창 1을 그대로 둔 채 **Windows에서 새 검은 창**을 엽니다. 다음을 실행합니다.

```cmd
ssh pi@safeguard.local
```

Pi에 접속된 뒤:

```bash
cd ~/SafeGuard_Main
./build/safeguard_main --config configs/real_navigation.json --duration 60
```

아이폰의 Safari 위치 화면을 계속 켜두세요. 약 60초 후 메인이 자동 종료됩니다. 그러면 같은 창 2에서 실행합니다.

```bash
python3 ~/SafeGuard_Navigation_Update/check_navigation.py --project ~/SafeGuard_Main
```

출력에서 확인할 내용:

- `PHONE_WEATHER_RECORD_FOUND: true`: 이번 실행에서 아이폰 위치 방식의 입력이 들어왔습니다.
- `MAIN_VALID_RECORDS`가 0보다 큼: 메인이 유효한 외기 입력을 받았습니다.
- `LAST_VALID_PHONE_WEATHER.temp_c`: 실제 API가 반환한 기온.
- `navigation_location.latitude / longitude`: 아이폰이 보낸 위치.
- `latitude / longitude`: 그 기온을 조회할 때 사용한 좌표.
- `provider_time_utc`: 날씨 값의 기준 시각. 모델 발표 시각이라는 뜻은 아닙니다.

검사 결과는 저장된 실행 기록 요약입니다. 과거의 마지막 유효 값이 현재도 유효하다는 뜻은 아닙니다. 실제 연결 상태는 아이폰 화면 또는 실행 중 대시보드에서 확인합니다.

UWB를 빼둔 상태라면 메인에서 `FAULT` 또는 필수 입력 대기가 나올 수 있습니다. 이것만으로 날씨 연동 실패는 아닙니다. 이번 날씨 연결 확인 때문에 UWB·mmWave·ESP32를 다시 연결할 필요는 없습니다.

## 5. 이동 시연

기본 확인을 마치면 창 2에서 다시 실행합니다. 아래는 5분 시연입니다.

```bash
cd ~/SafeGuard_Main
./build/safeguard_main --config configs/real_navigation.json --duration 300
```

- 내 아이폰 B와 Pi를 차량 한 대라고 생각하고 함께 둡니다. 이동 시 전원과 기존 핫스팟 연결도 유지돼야 합니다.
- 위치 좌표는 자동 갱신됩니다. 방 안에서 몇 걸음 움직이는 정도는 위치 오차 범위 안일 수 있습니다.
- 날씨는 위치가 달라져도 같은 기상 격자·비슷한 기온 때문에 숫자가 같을 수 있습니다. **좌표, 조회 좌표, 수신 시각도 함께 확인**합니다.
- 첫 유효 위치에서 바로 API를 조회합니다. 이후 100m 이상 이동하면 다음 조회 대상이 됩니다. API 요청 사이에는 최소 60초를 둡니다. 제자리에 있으면 기본 5분마다 갱신합니다.
- 마지막 조회 위치에서 1km를 넘게 벗어나면 새 날씨를 받을 때까지 기존 기온은 무효입니다. 1km 이내에서는 유효기간 안의 같은 주변 지역 기온을 쓸 수 있으며, 조회 좌표를 현재 위치로 바꿔 표시하지 않습니다.
- 아이폰 위치가 15초 이상 갱신되지 않거나 정지를 누르면 외기 입력도 무효 처리합니다. 0°C나 과거 고정 좌표로 대체하지 않습니다.
- API 통신 실패 시에는 가까운 위치의 아직 유효한 캐시만 사용할 수 있습니다. 날씨 기준 시각으로 30분이 지나면 만료합니다.

## 6. 종료와 다음 실행

종료:

1. 아이폰 화면에서 **정지**.
2. 메인 프로그램 창 2가 아직 실행 중이면 **Ctrl+C**.
3. 수신기 창 1에서 **Ctrl+C**.
4. Pi 전원까지 끌 때는 Pi에서 `sudo shutdown -h now` 실행 후 종료될 때까지 기다립니다.

다음 실행:

- 같은 핫스팟에 다시 연결합니다.
- 창 1에서 `python3 ~/SafeGuard_Navigation_Update/start_navigation.py --project ~/SafeGuard_Main`.
- 아이폰에서 출력된 Phone 주소를 열고 새 연결 코드로 연결한 뒤 시연 시작.
- 창 2에서 메인 실행.
- Pi 주소와 인증서가 그대로라면 인증서 설치를 반복할 필요는 없습니다.

Pi의 IP가 바뀌었거나 인증서가 만료되어 실행기가 중단되면, 수신기를 종료한 상태에서 아래로 새 인증서를 만듭니다.

```bash
python3 ~/SafeGuard_Navigation_Update/setup_navigation.py --project ~/SafeGuard_Main --regenerate
python3 ~/SafeGuard_Navigation_Update/start_navigation.py --project ~/SafeGuard_Main
```

아이폰에서 예전 SafeGuard 프로파일을 제거하고 새 Setup 주소로 3번의 인증서 설치·신뢰를 다시 진행합니다. 시연을 완전히 마친 뒤에는 설정 → 일반 → VPN 및 기기 관리에서 이 SafeGuard 프로파일을 제거할 수 있습니다.

## 문제가 생기면

| 표시/증상 | 확인 |
|---|---|
| `Could not resolve hostname` | 노트북과 Pi가 같은 핫스팟인지 확인. Pi의 현재 IP를 알면 `safeguard.local` 대신 사용. 예전 IP를 그대로 가정하지 않기. |
| `unzip`이 Windows에서 안 됨 | 먼저 `ssh pi@safeguard.local`. `pi@safeguard:... $`에서 unzip 실행. |
| `Local code differs` 또는 `Ambient dependency differs` | 팀원 수정본을 보호하려고 설치를 중단한 것. 강제 덮어쓰기하지 말고 해당 파일과 오류 공유. |
| `No unambiguous LAN IP` | Pi에서 `hostname -I`로 주소 확인. 시작 명령 끝에 `--ip 실제IPv4` 추가. |
| Safari Setup 페이지가 안 열림 | 내 폰과 Pi의 핫스팟, 프로그램이 출력한 주소, 수신기 실행 여부 확인. 환경에 따라 핫스팟의 기기 간 접속 가능 여부 확인 필요. |
| Safari HTTPS 인증서 경고 | IP 변경 여부, 프로파일 설치, 전체 신뢰 설정 확인. |
| 연결 코드 만료/사용됨 | 창 1 Ctrl+C 후 다시 시작하여 새 코드 사용. |
| `location_stale` / 위치 대기 | Safari를 화면에 띄우고 시연 시작. 위치 서비스 권한 확인. 실내 정확도가 낮으면 창가 등에서 확인. |
| `api_unavailable` | Pi 인터넷 연결과 시간 확인. 임의 기온으로 대체되지 않음. |
| 기온 숫자가 안 바뀜 | 이동 거리가 작거나 같은 날씨 격자일 수 있음. 위치·조회 좌표·기준 시각으로 확인. |

## 데이터 의미와 범위

기온은 Open-Meteo의 `current.temperature_2m`을 실제 HTTPS로 요청한 값입니다. **외부 기상 모델 기반 추정값**이며 차량 옆 온도센서의 실측값이 아닙니다. 앞서 사용한 고정 좌표의 14.9°C를 코드에 넣거나 재사용하지 않습니다. 온도센서가 제공할 차량 실내 온도와도 구분합니다.

아이폰 위치는 운영체제 위치 서비스가 제공하는 실제 좌표입니다. GPS·Wi-Fi·이동통신 등 여러 방법을 쓸 수 있으므로 원시 GPS만 측정했다는 뜻은 아닙니다. 아이폰이 보고한 오차 반경이 200m를 넘으면 입력을 인정하지 않습니다.

위치는 Pi에 전달되고 날씨 조회 좌표는 Open-Meteo로 전송됩니다. 실행 로그에는 좌표와 기온의 출처가 기록됩니다. 별도 클라우드 위치 중계는 사용하지 않습니다. 실행된 수신기에 연결한 한 대만 위치를 보낼 수 있습니다.

검증 범위: 개발 환경의 자동 검사와 합성 위치·기상 응답을 사용한 통신/만료 검사, 실제 TLS 인증서 검증을 켠 로컬 HTTPS 통신, 브라우저 API 모의 동작. **실제 아이폰 17 및 사용자 Pi에서의 최초 연결은 아직 수행하지 않았습니다.** 이 패키지는 기존 시스템의 위치·외기 입력 확장이며, 전체 차량 안전장치의 검증 완료를 뜻하지 않습니다.

## 검증 및 참고 문서

기존 프로젝트에 설치한 후 이 패키지의 Python 검사를 실행하려면:

```bash
SAFEGUARD_TEST_PROJECT="$HOME/SafeGuard_Main" python3 -m unittest discover -s ~/SafeGuard_Navigation_Update/tests -v
```

- Apple 인증서 신뢰 안내: https://support.apple.com/ko-kr/102390
- Apple 위치 서비스 설명: https://support.apple.com/ko-kr/102515
- 웹 위치 API 표준: https://www.w3.org/TR/geolocation/
- Open-Meteo API: https://open-meteo.com/en/docs
- 기상 데이터 표기: Weather data by Open-Meteo.com (CC BY 4.0)
