SafeGuard 아이폰 핫스팟 IPv6 접속 수정

확인된 상황
아이폰에서 Pi의 2001:... 주소에 연 임시 8082 시험 페이지는 열렸습니다.
기존 위치 수신기는 IPv4와 fe80:... 주소에서만 접속을 받았습니다.
이번 수정은 wlan0의 사용 가능한 global IPv6 주소도 자동으로 찾아 접속을 받습니다.
외부 IPv6 주소에서는 해당 Wi-Fi 주소의 동일 서브넷에서 오는 클라이언트만 허용합니다.
기존 인증서, 이름 검증, 연결코드, 토큰, Host/Origin 검사, 위치 신선도 검사를 유지합니다.
프로젝트의 navigation_bridge.py와 navigation_phone.html 두 파일만 백업 후 교체합니다.
CA/개인키를 새로 만들지 않으며 UWB, ESP32, 메인, 네트워크 설정을 수정하지 않습니다.

설치
1. ZIP을 Windows C:\SafeGuard_C\SafeGuard_Navigation_Hotspot_Fix.zip에 저장합니다.
2. Windows 명령 프롬프트:
   scp C:\SafeGuard_C\SafeGuard_Navigation_Hotspot_Fix.zip pi@172.20.10.8:/home/pi/
3. Pi의 기존 start_ipv6.py 창에서 Ctrl+C 한 번으로 위치 수신기를 중지합니다.
   임시 IPv6 test ready 창에서도 Ctrl+C 한 번으로 시험 서버를 중지합니다.
   Pi 자체나 다른 팀원 프로그램은 종료하지 않습니다.
4. Pi에서 다음 명령을 한 줄씩 실행합니다. 오류가 나오면 다음 줄을 실행하지 않습니다.
   unzip -n ~/SafeGuard_Navigation_Hotspot_Fix.zip -d ~
   python3 ~/SafeGuard_Navigation_Hotspot_Fix/install_fix.py --project ~/SafeGuard_Main
   python3 ~/SafeGuard_Navigation_Hotspot_Fix/start_fix.py --project ~/SafeGuard_Main
5. IPv6 listening: 2001:... 줄과 새 PAIRING CODE가 나오는지 확인합니다.
6. 아이폰 Safari의 기존 탭을 닫고 새 탭에서 https://safeguard.local:8443/ 를 엽니다.
   새 코드 입력 → 연결 → 시연 시작. 위치 권한은 기존 허용을 사용합니다.
7. Pi 응답 확인됨과 위치 수신 시각/횟수가 갱신되는지 확인합니다.

이번에는 수동으로 위치 수신기를 실행합니다. 실행 창을 유지하세요.
Ctrl+C는 이 위치 수신기만 중지합니다. 네트워크 주소가 바뀌면 프로그램이 중지되므로 start_fix.py를 다시 실행합니다.
재부팅 뒤에도 실행하려면 Pi의 IPv6가 활성화되어 있어야 합니다.
자동 시작은 아직 적용하지 않았습니다. 이전 SafeGuard_Navigation_Demo_Update는 설치하지 마세요.
접속 복구 확인 뒤 이번 변경을 포함한 자동 실행 설정을 적용해야 합니다.
기존 인증서 30일 유효기간은 그대로이며 시작 출력의 Certificate notAfter 날짜를 확인하세요.
숫자 IPv6 주소로 HTTPS에 접속하면 인증서 이름이 맞지 않으므로 safeguard.local 주소를 사용합니다.

오류
Local changes found: 팀원 변경 보호를 위한 중단. 강제 덮어쓰지 말고 출력 공유.
Stop the old navigation receiver: 기존 위치 수신기 창에서 Ctrl+C 후 설치 재실행.
TLS CONFIG ERROR: 기존 인증서 검증 실패. 출력 공유; 인증서를 임의 삭제하지 않습니다.
Safari가 여전히 안 열림: Safari 오류 화면과 수정 수신기의 IPv6 listening 줄을 공유합니다.

검증
Python 자동 테스트 20개 통과: IPv6 HTTPS 루프백, 인증/위치 유효성,
주소 선택, 동일 서브넷 접근 제한, 파일 변경 보호, 인증서 유지 등.
JavaScript 모의 브라우저 시험 통과: 위치 전달, 숨김 시 중지, 연결 응답 상태 표시.
실제 사용자 아이폰에서 수정 위치 페이지 접속/전송은 설치 후 확인해야 합니다.
