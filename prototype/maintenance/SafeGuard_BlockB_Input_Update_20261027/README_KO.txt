SafeGuard B블록 레이더 메인 연결 준비 — 2026-10-27

지금 혼자 할 수 있는 작업을 코드로 진행한 결과입니다.
ESP32에 올리는 파일이 아닙니다. Arduino IDE로 열거나 재업로드하지 않습니다.
Pi 없이 데이터 해석·끊김 처리·메인 상태 전환을 검사했습니다.
실제 레이더 사람 감지, 물리 출력, 전체 시연을 완료했다는 뜻은 아닙니다.

1. 지금 할 일
ZIP을 C:\SafeGuard_C에 보관하고 압축을 풀면 됩니다.
ESP32 온습도/PIR 수신과 소프트웨어 정지 명령 수신은 이미 사용자 실물 로그로 확인했습니다.
현재 컴퓨터 검사는 개발 환경에서 끝냈으므로 사용자가 같은 검사를 반복할 필요는 없습니다.
담당자가 없을 때 빠진 빵판 배선을 추측해서 꽂지 마세요. 센서 시험을 끝냈으면
시리얼 모니터를 닫고 ESP32 USB를 빼두어도 됩니다.

2. 무엇을 구현했나
- CP2105 01E86213의 두 UART를 정확히 구분해서 사용하는 People Tracking 입력 어댑터.
- TLV 길이, 대상 레코드, 중복/이전 프레임, 비정상 숫자, 부분 수신 검사.
- 대상 1개 이상 또는 presence=1을 긍정 근거로 전달.
- tracks TLV가 명시적으로 0개이고 presence=0일 때만 부정 근거로 전달.
- 빠진 TLV, 깨진 패킷, 오래된 측정을 사람 없음으로 만들지 않음.
- 5초 연속 부정 근거의 최종 처리는 C++ 메인이 담당. 어댑터에서 같은 대기를 중복하지 않음.
- 한꺼번에 수신한 줄 중간의 감지/오류가 마지막 줄에 가려져도 연속 관측 시간은 끊기도록 수정.
- FSM이 레이더 판단을 쉬는 동안에도 UART 수신 유지. 측정 중지/재시작의 절전 기능은 구현하지 않음.
- 앱 종료 시 sensorStop 1회 전송. 이 전송만으로 실제 정지를 확인했다고 표시하지 않음.
- 기존 설정은 수정하지 않음. 새 입력을 활성화하지 않으면 기존 입력 경로를 유지.

3. 현재 펌웨어와 호환성 — 중요
B 인계 문서의 마지막 기록은 VitalSigns With PeopleTracking입니다.
이 새 어댑터의 대상은 3D People Tracking ODS입니다.
따라서 지금 연결한 보드에 바로 실행하지 않습니다.
firmware_confirmed=false, enabled=false, validated=false가 기본 준비 값입니다.
호흡 TLV 1040이 들어오면 지원하지 않는 펌웨어로 거부합니다. 1040이 안 나왔다고
People Tracking 펌웨어라고 자동 확정하지도 않습니다.
B담당자가 최종 사용할 펌웨어/ODS cfg와 실제 빈 좌석·정지 재실 결과를 확인한 뒤
설정을 합쳐야 합니다. 기존 OOB 검사 명령이나 설정으로 되돌리지 않습니다.
카메라는 현재 메인의 구현을 유지하며 B담당자의 별도 카메라 구현과 통합한 것은 아닙니다.

4. Pi를 사용할 수 있게 되었을 때
현재 ESP32에 업로드한 Software Stop 펌웨어와 별개로, Pi에도 기존
SafeGuard_Software_Stop_20261024 패키지 설치가 먼저 필요합니다.
이 패키지 설치기는 해당 소스 버전이 맞는지 확인하며 다른 수정은 덮어쓰지 않습니다.

먼저 메인 프로그램이 실행 중이 아닌 Pi 터미널에서 호환성만 확인:
python3 ~/SafeGuard_BlockB_Input_Update_20261027/install.py --project ~/SafeGuard_Main

호환성이 맞으면 코드 설치:
python3 ~/SafeGuard_BlockB_Input_Update_20261027/install.py --project ~/SafeGuard_Main --apply

설치기는 임시 공간에서 C++ 빌드 및 검사를 끝낸 뒤 백업하고 적용합니다.
실행 중인 메인이 있거나 다른 수정본이면 중단합니다. navigation 서비스는 건드리지 않습니다.
configs는 변경하지 않으며 레이더/ESP32/카메라를 시작하지 않습니다.
main binary는 설치 시 Pi에서 직접 빌드합니다. 개발 환경의 다른 CPU 바이너리는 포함하지 않습니다.
설치 완료와 실제 레이더 연결 완료는 별개입니다.

5. 후속 통합 설정 (사용자가 지금 수동으로 켜지 말 것)
configuration_fragment.json은 기존 real_navigation_control.json에 나중에 합칠 항목의 예시입니다.
전체 실행 설정이 아닙니다. 기존 파일을 이 조각으로 교체하면 안 됩니다.
- 실제 보드 펌웨어 확인 -> profile/firmware_confirmed 설정
- 실제 설치 높이·각도·좌석에 맞는 cfg 선택 -> 절대경로와 SHA256 기록
- B 단독 점유/빈 좌석/잠깐 가림/USB 끊김 확인 -> 결과로 validated 설정
- tracks=0일 때 TLV 생략 규약은 실물 패킷으로 확인하기 전까지 false 유지
- 기본은 configure_on_start=false. 나중에 한 프로그램만 cfg를 보내고 포트를 소유하도록 구성
- UWB·카메라·위치/외기 설정과 manual_control 설정 유지
- 외기 온도는 API의 model_estimate이며 차량 외부 실측 센서 값이라고 설명하지 않음
- 열 예측 보정 완료 여부도 별도. 이번 변경에서 enabled/calibrated를 바꾸지 않음

6. 혼자 준비한 뒤 남는 실제 작업
A: 빠진 배선 복원/확인, ESP32와 Pi 연결, 실제 팬·부저·서보 및 전체 정지/감시 재개.
B: 최종 펌웨어/cfg 확정, 빈 좌석·정지 재실·거리/각도/조명에 따른 검증, 카메라 방식 정리.
통합: UWB 이탈 -> 1차 감지 -> 레이더 확인 -> 온도 위험 -> 출력 -> 전체 정지 시나리오.
재시작: 전원을 껐다 켜고 같은 시연을 재현, 통신 끊김과 복구도 확인.
소프트웨어 전체 정지는 통신을 사용하는 제어이며 물리 전원 차단 장치가 아닙니다.

7. 개발자가 다시 검사할 때
Windows에서도 가능한 새 어댑터 자체 검사 (장치 연결 불필요):
py C:\SafeGuard_C\SafeGuard_BlockB_Input_Update_20261027\self_check.py

개발 환경 검증 상세는 VALIDATION_KO.txt.

8. 근거
B 인계 소스: https://github.com/yoontf0/safeguard-mmwave-simulator
확인한 커밋: c6e3f60bdb8966a66c2cf349b3847bde8ba7fdf2
hardware/HANDOFF_BLOCK_B.md 및 hardware/mmwave/mmwave_reader.py의 형식을 기준으로 작성.
reference_configs의 두 파일은 해당 커밋의 B담당자 설정을 그대로 보관한 참고본입니다.
실제 센서 좌표계/장착 위치에 맞는 검증 없이 '확정 설정'으로 취급하지 않습니다.
