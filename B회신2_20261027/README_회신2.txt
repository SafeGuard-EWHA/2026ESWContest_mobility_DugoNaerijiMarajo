SafeGuard B블록 → 메인 연동 담당 회신 2 (1 펌웨어, 2 Pi 수신, 3 추가 실측, 4 사진, 5 카메라)
작성: 2026-10-27 / B 저장소 기준 c6e3f60 + 리더 원본 저장 기능 추가(미커밋, 아래 2-3)

==================================================================
1. 펌웨어 확인과 교체  (1_firmware/)
==================================================================
1-1. 교체 전 (18:22 KST, Pi)  fw_check_before.txt
  version: Platform xWR68xx, mmWave SDK 03.05.00.04
  help 목록에 vitalsign, VSRangeIdxCfg 있음
  → 판정: Vital Signs With People Tracking (인계서 기록과 같음)

1-2. 교체 (18:30~18:32 KST, 노트북 UniFlash 9.7.0, COM6)  uniflash_log.txt
  파일: C:/ti/radar_toolbox_4_00_00_05/source/ti/examples/Industrial_and_Personal_Electronics/
        People_Tracking/3D_People_Tracking/prebuilt_binaries/3D_people_track_6843_demo.bin
  SHA256 74aece5dcd63f2893df0692c30605d3fbbaf6b7baeb3310f58becb8698448349, 625,668 바이트
  Low Power 버전과 구분: 3D_People_Tracking_Low_Power/prebuilt_binaries/ 의 같은 이름 파일은
    SHA256 d4a83d22…5d85 로 다른 파일. 사용하지 않음.
  UniFlash 로그: SFLASH 지움 성공 → META_IMAGE1 625668 바이트 다운로드 성공 →
    "Program Load completed successfully." (다운로드 크기 = 위 파일 크기)

1-3. 교체 후 (18:36 KST, Pi, S1 Functional 1 OFF/2 OFF/3 ON/4 ON/5 OFF)  fw_check_after.txt
  version: xWR68xx, SDK 03.05.00.04 (펌웨어가 SDK 3.5 기반이라 버전 문자열은 같음)
  help 목록에 trackingCfg, presenceBoundaryBox 있고 vitalsign/VSRangeIdxCfg 없음
  → 판정: 3D People Tracking

  확인 명령 (cfg·sensorStart 안 보냄, version/help만):
    python3 check_radar_firmware.py            # Pi, CP2105 01E86213 if00 자동 선택
    python check_radar_firmware.py --cli COM6  # 노트북

==================================================================
2. 최종 설정으로 Pi 1분 수신  (2_pi_receive/)
==================================================================
2-1. 조건
  Pi 5, 레이더 USB 재연결 직후, cfg = hardware/mmwave/people_tracking/ODS_sedan_est.cfg
  (수정 없음, SHA256 674fbe92…82ce)
  레이더 배치는 시험 배치가 아님(책상 위, 주변에 사람 있음). 이번 1분은 수신 확인용이고
  점유 판정 정확도 자료가 아님.
  같은 시각 Pi에서 메인(safeguard_main, sensor_hub, UWB 리더)이 실행 중이었음.
  메인 설정은 mmwave_json_port 비어 있음 → 레이더 포트와 충돌 없음 확인 (fuser).

2-2. 실행 명령 (rx60_command.txt)
  cd ~/safeguard-mmwave-simulator
  python3 -u hardware/mmwave/mmwave_reader.py \
    --cli  /dev/serial/by-id/usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_01E86213-if00-port0 \
    --data /dev/serial/by-id/usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_01E86213-if01-port0 \
    --cfg hardware/mmwave/people_tracking/ODS_sedan_est.cfg \
    --duration 60 --csv ~/b_reply_20261027/rx60.csv --raw ~/b_reply_20261027/rx60_raw.bin

2-3. 결과 (rx60.log)
  cfg 34줄 전송 성공 → sensorStart → 1초 안에 첫 프레임
  총 1,091 프레임 / 60초, 누락 0, 깨짐 0, 17.7~18.3 fps
  원본 바이트 875,777 B 저장 (rx60_raw.bin)

  raw.bin을 같은 리더 파서로 노트북에서 다시 해석해 CSV와 대조:
    프레임 1,091 = CSV 1,091행, 프레임 번호·추적 수·재실 불일치 0, 깨짐 0
    TLV 1021(재실) 없는 프레임 0 / TLV 1010(추적) 없는 프레임 1 (그 프레임은 추적 0명)
    → 회신 1의 TI 소스 규칙(1021 매 프레임, 1010은 추적 있을 때만)과 맞음
  참고(배치 무관): 추적 수 분포 0:1, 1:76, 2:315, 3:620, 4:79 / 재실 1: 1,091

2-4. 리더 수정 (mmwave_reader.py, mmwave_reader_raw.diff)
  --raw PATH 옵션 추가. 다른 동작은 바꾸지 않음.
  - PATH: 데이터 포트에서 읽은 바이트를 해석 전 그대로 이어 붙여 저장
  - PATH.idx.csv: 읽은 묶음마다 monotonic_s, wall_time, byte_offset, num_bytes
    (CSV wall_time과 같은 Pi 시계라서 raw 위치 ↔ CSV 행을 시각으로 맞출 수 있음)
  - 수정본 SHA256 945c2f40904af9866619c3836e8721f265b1c264fc7cefb1671672a13ce7d565 (Pi와 같음)
  - 회신 1의 지적(--cfg 기본값 OOB, ttyUSB 대체 경로 등)은 고치지 않았음. 그래서 항상 --cfg와 by-id를 명시해서 실행함.
    참고: 오늘 USB를 다시 꽂은 뒤 레이더가 ttyUSB0/1, ESP32가 ttyUSB2로 바뀌었음. 번호는 꽂는 순서에 따라 바뀜.

==================================================================
3. 추가 실측  (3_test3/README_시험3.txt)
==================================================================
  배치가 시험 B와 다름: 레이더 높이 약 1.05 m, 아래 5~10°, 의자 정면 약 0.95 m (방이 좁음).
  cfg는 그대로 사용 (이유는 README_시험3.txt 1절). 시험 중 과방에 다른 사람 있었음.
  수신 8,363 프레임, 누락 0, 깨짐 0, raw.bin 재해석 = CSV 일치.
  - 가만히 있는 동안 끊김: 0초 (2분 내내 추적·재실 유지)
  - 퇴장 후 사라지는 시간: 1분 빈자리 동안 사라지지 않음(73초 이상). 추적 2개가 좌표 고정 상태로 남음.
    카메라는 같은 시간 변화 0% → 트래커가 붙잡은 추적으로 판단. 원인 추정: stateParam sleep2free 6000.
    이 cfg로는 하차 후 EMPTY가 수 분 늦어질 수 있음. 5초 규칙만으로는 해결 안 됨 → 같이 정해야 함.
  - 재착석 후 다시 감지: 실제 착석 순간 새 추적 생성, 남은 추적도 다시 움직임 (사람은 다시 잡음)
  - 앉은 사람 추적 z가 0.0~0.15 m로 낮음 (원인 미확인) → z는 판단에 쓰지 말 것 권장

==================================================================
4. 설치 사진  (4_photos/)
==================================================================
  옆모습 3장(기울기), 보드 뒤에서 의자 1장, 보드·의자 전체 2장. 안테나 면 정면 사진은 없음.

==================================================================
5. 카메라  (5_camera/README_카메라.txt)
==================================================================
  코드·설정: 변경 없음 (camera_motion.py SHA256 bdb1c0e7…e3, 모두 기본값)
  천장 조명 끄기·켜기 4번 → 모두 조명 변화로 무시, 가짜 움직임 0. 사람 움직임 3번 모두 검출.
  빈 화면 오경보 0. 가만히 앉은 사람은 못 잡음 (지난 시험과 같음).
  사람이 있는 동안의 조명 변화, 차 실내등, 렌즈 가림 등은 미확인.

==================================================================
6. 종료 상태 (2026-10-27 20:00 KST 확인)
==================================================================
  Pi에서 B 시험 프로그램(mmwave_reader, camera_motion) 모두 종료. 메인 프로그램도 꺼진 상태.
  ESP32·UWB USB는 건드리지 않음. 레이더 USB는 시험 3 직전에 같은 포트로 1번 다시 꽂음.
  레이더는 마지막 시험 끝에 sensorStop 된 상태 → 메인에서 레이더를 쓰기 전에 레이더 USB를 다시 꽂아야
  sensorStart가 응답함 (인계서 0절 2번과 같은 현상).
  Pi 파일: ~/b_reply_20261027/ (이 ZIP과 같은 원본), ~/safeguard-mmwave-simulator 의
  hardware/mmwave/mmwave_reader.py는 --raw 추가본(미커밋 수정) 상태.

==================================================================
도구 (tools/)
==================================================================
  run_cues.ps1 + plan_*.csv  혼자 시험할 때 노트북이 정해진 시각에 한국어 음성으로 안내하고 시각 기록
  mark_events.py             Enter로 행동 시각을 직접 기록하는 대안 (이번에는 사용 안 함)
