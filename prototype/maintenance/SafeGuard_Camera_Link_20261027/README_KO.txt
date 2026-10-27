SafeGuard B 카메라 메인 연동 — 2026-10-27

대상: Pi 5 + Camera Module 3, 사용자가 보낸 SafeGuard_Main_Current.zip.
ESP32 펌웨어 파일이 아닙니다. Arduino 재업로드는 하지 않습니다.

설치하는 내용
- B의 camera_motion.py를 block_b_camera_motion.py라는 이름으로 원본 그대로 보관.
- numpy Y 밝기 차분, 320x240, 10fps, 픽셀 변화 >25, 비율 >1%, 연속 3프레임,
  움직임 2초 유지, 전체 변화 >60%이면 조명 변화, 이후 1초 안정화.
- 기존 sensor_hub.camera_worker에 새 backend 선택 분기만 추가.
- adapter가 기존 REAL_CAMERA 입력 형식으로 결과를 보냅니다.
- 조명 변화/안정화 중 새 움직임 근거가 없으면 입력 무효(UNKNOWN)로 보냅니다.
  이미 확인한 움직임의 짧은 유지 시간은 보존합니다.
- 처리 비활성화·수신 간격 초과 시 이전 프레임/움직임 유지 상태를 초기화.
- real_navigation_control.json의 카메라 backend/전용 설정만 추가합니다.

변경하지 않는 항목
ESP32 코드·제어, UWB, 레이더 설정, C++ FSM, 열 예측 설정, 아이폰 위치 서비스,
인증서, Wi-Fi, 기존 OpenCV 카메라 경로(다른 설정으로 실행할 때).
사진/동영상을 자동 저장하지 않습니다. 전용 검사에는 숫자 상태 로그만 저장합니다.

준비
Windows C:\SafeGuard_C에 ZIP 저장.
Windows 명령 프롬프트:
scp C:\SafeGuard_C\SafeGuard_Camera_Link_20261027.zip pi@172.20.10.5:/home/pi/
172.20.10.5는 오늘 확인된 Pi 주소입니다. 추후 바뀌면 현재 Pi 주소를 사용하세요.

설치 전
대시보드에서 '정지 확인됨' 확인 → 대시보드 탭 닫기 → 메인 실행 창에서 Ctrl+C.
pi@safeguard:~ $가 돌아오면 아래를 순서대로 실행합니다.
B의 독립 카메라 시험 프로그램도 종료돼 있어야 합니다.

unzip -n ~/SafeGuard_Camera_Link_20261027.zip -d ~
python3 ~/SafeGuard_Camera_Link_20261027/install_camera.py --project ~/SafeGuard_Main --apply

설치기는 소스 버전/패키지 해시 확인, 기존 허브 22개+새 카메라 9개 검사,
백업 후 변경을 수행합니다. 검사 실패나 다른 수정본이면 덮어쓰지 않습니다.
백업: ~/SafeGuard_Main/backups/camera_link_...
--apply를 빼면 호환성만 확인합니다. 서비스 재시작이나 장치 실행은 하지 않습니다.
Pi에서 numpy가 없으면 설치 검사에서 중단합니다. B 시험에 사용한 기본 python3 환경을 사용하세요.

카메라만 확인 (메인을 계속 꺼 둔 상태)
python3 ~/SafeGuard_Camera_Link_20261027/check_camera.py --project ~/SafeGuard_Main --duration 30

약 30초 동안 처음 5초는 장면을 가만히 두고, 카메라 앞에서 손/몸을 움직인 뒤 다시 멈추세요.
CAMERA valid=True motion=True가 움직일 때 보이는지 확인합니다.
정지 후에는 hold 2초가 지나면 motion=False가 될 수 있습니다.
조명 변화는 valid=False status=lighting_uncertain이 될 수 있습니다.
결과 camera_input_received=true는 유효한 카메라 입력 수신만 뜻합니다.
motion_frames>0은 움직임 판정이 관측됐다는 뜻이며 검출 정확도 인증이 아닙니다.
검사 로그: ~/SafeGuard_Main/camera_checks/<시각>/camera.jsonl 및 result.json.
이 명령은 설치된 실제 sensor_hub.camera_worker를 직접 사용하지만 C++ 메인은 실행하지 않습니다.
ESP32/UWB/레이더 포트를 열거나 팬·부저·서보에 명령하지 않습니다.

검사 이후
결과를 확인한 다음 기존 run_control.py로 메인을 다시 켤 수 있습니다.
메인은 수동 정지 상태로 시작합니다. 메인 FSM에서 카메라 처리가 꺼져 있으면
대시보드 카메라 WAITING은 정상일 수 있습니다. 이를 없애려고 감시 재개를 누르지 마세요.
물리 배선 확인 및 다음 통합 단계에서 감시 재개를 진행합니다.

제약
- 움직임 없음은 빈 좌석 판정이 아닙니다. 가만히 있는 사람을 카메라로 확정하지 않습니다.
- 렌즈 가림/카메라 흔들림을 고장으로 자동 구분하는 기능은 없습니다.
- B 시험(한 배치, 천장 조명) 이외의 실차/야간/사람과 조명 동시 변화는 미검증입니다.
- 새 연결 경로의 실제 Pi 동작은 설치 후 전용 검사에서 확인해야 합니다.
- 레이더 퇴장 후 잔류 감지와 sensorStop 후 재시작 문제는 이번 파일로 해결하지 않습니다.
- 기존 SafeGuard_BlockB_Input_Update_20261027을 이 설치 후 바로 덮어쓰지 마세요.
  그 패키지는 예전 sensor_hub를 기준으로 하므로 후속 레이더 통합본에서 함께 병합합니다.
