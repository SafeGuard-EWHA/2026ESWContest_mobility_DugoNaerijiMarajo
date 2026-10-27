SafeGuard 위치 수신기 자동 실행 V2

적용 대상: SafeGuard_Navigation_Hotspot_Fix 설치 후 실제 아이폰 위치 전송에 성공한 Pi.
구형 SafeGuard_Navigation_Demo_Update 대신 이 패키지를 사용합니다.

무엇이 달라지나
- 오늘 성공한 navigation_bridge.py와 navigation_phone.html을 그대로 유지합니다.
- Pi 부팅 때 위치 수신기를 pi 계정으로 자동 실행합니다.
- wlan0에서 IPv6와 주소 자동 설정, 공유기의 IPv6 광고 수신을 활성화합니다.
- 실제 접속에 필요한 Wi-Fi global IPv6 주소가 생길 때까지 기다립니다.
- 네트워크 주소 변경/프로그램 종료 시 위치 수신기를 자동으로 재시작합니다.
- SSH 창을 닫아도 수신기가 실행됩니다.
- Wi-Fi 연결을 재시작하거나 저장된 Wi-Fi 프로파일, IPv4, ESP32, UWB, C++ 메인을 변경하지 않습니다.
- 기존 인증서를 유지합니다. 이름 주소는 https://safeguard.local:8443/ 입니다.
- 위치 수신기만 자동 실행합니다. 아이폰 Safari의 위치 공유와 C++ 메인 실행은 별도입니다.

1회 설치 순서
1. ZIP을 노트북 C:\SafeGuard_C\SafeGuard_Navigation_Autostart_V2.zip에 저장합니다.
2. Windows 명령 프롬프트:
   scp C:\SafeGuard_C\SafeGuard_Navigation_Autostart_V2.zip pi@172.20.10.8:/home/pi/
3. 아이폰에서 위치 공유를 중지합니다.
4. Pi의 start_fix.py 실행 창에서 Ctrl+C 한 번으로 수신기를 중지합니다.
   다른 팀원 프로그램과 Pi 전원은 그대로 둡니다.
5. Pi 터미널에서 한 줄씩 실행합니다. 오류가 나오면 다음 줄로 넘어가지 않습니다.
   unzip -n ~/SafeGuard_Navigation_Autostart_V2.zip -d ~
   sudo python3 ~/SafeGuard_Navigation_Autostart_V2/install_demo.py --project ~/SafeGuard_Main
   sudo python3 ~/SafeGuard_Navigation_Autostart_V2/show_status.py --new-code
6. SERVICE: active와 새 PAIRING CODE를 확인합니다.
   활성 상태만으로 아이폰 접속이 증명되지는 않습니다.
7. 아이폰에서 https://safeguard.local:8443/ 를 새로 열고 새 연결코드 → 연결 → 시연 시작.
   수신 시각과 횟수가 계속 갱신되는지 확인합니다.
8. Pi에서 자동 시작 등록 여부 확인:
   systemctl is-enabled safeguard-navigation.service
   systemctl is-active safeguard-navigation.service
   각각 enabled / active가 정상입니다.

설치 후 예전 start_fix.py 또는 start_ipv6.py를 동시에 실행하지 마세요.
인증서를 다시 설치할 필요는 없습니다. 기존 인증서 만료일은 상태 출력의 Certificate notAfter로 확인하세요.
기존 인증서는 발급일부터 30일이며, 이 패키지가 유효기간을 연장하지는 않습니다.

시연 당일
1. 기존 팀원 핫스팟을 켜고 Pi 전원을 연결합니다.
2. 아이폰도 같은 핫스팟에 연결합니다. Pi의 인터넷 연결은 날씨 API에 필요합니다.
3. Pi가 주소를 받으면 위치 수신기가 자동 시작합니다.
4. Pi에 SSH로 접속한 뒤 다음 명령으로 새 연결코드를 받습니다.
   sudo python3 ~/SafeGuard_Navigation_Autostart_V2/show_status.py --new-code
5. 아이폰에서 같은 이름 주소로 접속, 새 코드로 연결하고 시연 시작을 누릅니다.
   Safari 화면을 켜둡니다. 차량 내비게이션 대용 폰은 Pi 옆에 둡니다.
6. 팀의 C++ 메인 프로그램은 별도로 실행합니다.

--new-code는 위치 수신기만 재시작하여 기존 연결을 무효화합니다. 위치 전달 중에는 필요 없이 실행하지 마세요.
연결코드는 수신기 시작 후 10분간 유효합니다. 만료되면 --new-code를 사용합니다.
네트워크가 끊겼다가 복구되어 수신기가 재시작된 경우에도 새 코드로 다시 연결합니다.
숫자 IP와 IPv6 주소는 바뀔 수 있습니다. 아이폰은 이름 주소를 사용하므로 주소를 매번 입력하지 않습니다.
다른 Wi-Fi를 사용할 경우 Pi의 해당 네트워크 접속 설정은 별도로 필요합니다.

실제 재부팅 검증
지금 팀원이 Pi를 사용 중이면 재부팅하지 마세요.
모든 팀원 작업이 끝난 뒤 저장하고 정상 종료/재부팅하여 시연 당일 순서를 한 번 검증합니다.
부팅 후 enabled/active 확인과 실제 아이폰 위치 수신까지 성공해야 재부팅 검증 완료입니다.
현재 패키지는 개발 환경에서만 자동 테스트했습니다. 사용자 Pi의 실제 부팅 성공을 아직 보장하지 않습니다.

오류 확인
sudo journalctl -u safeguard-navigation -b -n 40 --no-pager
NETWORK WAIT: IPv4와 global IPv6 주소 수신 대기. 핫스팟이 켜졌는지 확인합니다.
TLS CONFIG ERROR: 인증서 검증/만료 문제. 자동 재발급하지 않으므로 오류 내용을 공유합니다.
Manual receiver still running: start_fix.py 창에서 Ctrl+C 후 설치 명령만 다시 실행합니다.
Local changes found: 팀원이 수정한 파일을 보호하기 위한 중단. 강제로 덮어쓰지 않습니다.
Different service runtime / different service file: 다른 버전이 이미 설치됨. 출력 공유 후 확인합니다.

중지 및 복구
위치 수신기만 중지: sudo systemctl stop safeguard-navigation.service
다시 시작: sudo systemctl start safeguard-navigation.service
자동 실행 해제:
sudo python3 ~/SafeGuard_Navigation_Autostart_V2/install_demo.py --project ~/SafeGuard_Main --remove
해제 시 서비스가 변경한 wlan0 IPv6 설정값만 원래 값으로 복원합니다.
다른 프로그램이 그 설정을 변경했다면 자동 복원을 중단합니다. 네트워크 주소/라우트의 즉시 원복까지 보장하지 않습니다.
프로젝트 파일과 인증서는 삭제하지 않습니다. 다른 프로그램을 종료하지 않습니다.

검증 결과 (2026-10-23)
Python 테스트 28개 통과, 모의 브라우저 JavaScript 시험 통과.
systemd-analyze verify 단위 파일 정적 검증 통과.
오늘 성공한 Hotspot_Fix의 프로젝트 두 파일이 바이트 단위로 동일함을 확인했습니다.
IPv6 활성화/복원/변경 보호, 주소 대기, 수신기 재시작 요청, 인증서 유지, HTTPS/토큰/위치 무효화 등을 검증했습니다.
실제 Pi의 systemd 실행 및 재부팅과 아이폰 재연결은 설치 후 확인해야 합니다.
