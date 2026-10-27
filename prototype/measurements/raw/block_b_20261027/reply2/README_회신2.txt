SafeGuard B블록 → 메인 연동 담당 회신 2 (1번 펌웨어 + 2번 Pi 수신)
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
3~5 진행 예정
==================================================================
  [ ] 3. 같은 배치에서 빈자리 3분 → 착석 정지 2분 → 퇴장 후 빈자리 1분 → 재착석 30초
        (CSV + raw.bin + 행동 시각 기록)
  [ ] 4. 설치 사진 3장
  [ ] 5. 카메라 코드·설정·실행 명령, 움직임 대 조명 구분 결과
        주의: 지금 메인 sensor_hub가 카메라를 쓰고 있어서(camera_enabled=true),
        B 카메라 시험은 메인을 멈춘 시간에 해야 함. 시간 맞춰 줘.
