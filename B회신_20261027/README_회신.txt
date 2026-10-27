SafeGuard B블록 → 메인 연동 담당 회신
작성일: 2026-10-27 / 기준 커밋: c6e3f60 (받은 ZIP과 같음)

역할 분담 동의: 메인 연결 코드는 연동 담당이 고친다. B는 hardware/ 시험 코드를 그대로 두고
레이더·카메라 시험 조건과 결과만 맞춘다. B는 메인 파일을 고치지 않는다.

==================================================================
1. 펌웨어 (요청 2)
==================================================================
현재 보드 상태: 기록상 Vital Signs With People Tracking (10/24 02:30경 굽기, 인계서 0절).
  오늘(10/27)은 보드가 노트북·Pi에 연결돼 있지 않아 직접 확인 못 함.
  → 아래 3단계에서 tools/check_radar_firmware.py로 확인하고 결과를 추가로 보내겠음.

정지 착석 시험(A·B·C)에 쓴 조합 — 이걸 그대로 다시 굽는다:
  보드      IWR6843ISK-ODS Rev C, CP2105 serial 01E86213 (Pi by-id if00=CLI, if01=DATA)
  펌웨어    Radar Toolbox 4.00.00.05
            examples/Industrial_and_Personal_Electronics/People_Tracking/
            3D_People_Tracking/prebuilt_binaries/3D_people_track_6843_demo.bin
            sha256 74aece5dcd63f2893df0692c30605d3fbbaf6b7baeb3310f58becb8698448349
            주의: 같은 이름의 3D_People_Tracking_Low_Power 쪽 bin(sha256 d4a83d22...)은 다른 파일. 쓰지 않음.
  cfg       시험 B(채택 후보): cfg/ODS_sedan_est.cfg
            sha256 674fbe92ebb69a17f9b5534b1e7fdec6c3a99f2b8b379c6f4c417a3d4a3582ce
            시험 A·C(비교용 원본): cfg/ODS_6m_staticRetention.cfg (TI 원본, 수정 없음)
            sha256 7b7a30b62b256ae3b3b366e97b48d909ca4e14e99b7f26a37174c1e11b3a3406
  수신      Pi 5, mmwave_reader.py (c6e3f60), 반드시 --cfg 지정. 18.2 fps.

굽기 절차 (노트북, 데스크톱 UniFlash 9.7.0):
  1) S1 Flashing: 1 ON, 2 OFF, 3 ON, 4 ON, 5 OFF → USB 연결 → RST 버튼
  2) UniFlash, COM6(Enhanced)로 위 bin 굽기
  3) S1 Functional: 1만 OFF → USB 뺐다 꽂기
  4) 확인: python check_radar_firmware.py --cli COM6  → "판정: 3D People Tracking" 이어야 함
     (version/help만 보냄. cfg·sensorStart 안 보냄)
  5) Pi로 옮긴 뒤 같은 확인 한 번 더: python3 check_radar_firmware.py

==================================================================
2. TLV 생략 의미 (ZIP README 3-2 D에 대한 답)
==================================================================
TI 원본 소스로 확인함 (원본 바이너리 캡처는 없음 — 리더가 raw를 저장하지 않았음):
  radar_toolbox_4_00_00_05/.../3D_People_Tracking/src/6843/mss/mss_main.c 617~735행
  - 1010 추적 목록: numTargets > 0 일 때만 보냄. → 정상 프레임에서 1010 없음 = 추적 0명.
  - 1011 추적 인덱스: numIndices > 0 이고 numTargets > 0 일 때만.
  - 1012 추적 높이: numTargets > 0 일 때 1010과 함께 (빌드에 HEIGHT_DETECTION_ENABLED 켜짐).
  - 1020 점 구름: 점이 0개면 생략.
  - 1021 재실: presenceDetEnabled면 매 프레임 보냄. cfg에 presenceBoundaryBox가 있고
    boundaryBox가 먼저 와야 켜짐 (tracker_utils.c 583~587행). ODS_sedan_est.cfg는 둘 다 있음.
    → 이 cfg에서는 1021 누락 = 비정상 프레임 (UNKNOWN 처리가 맞음).
  - 추적 레코드: overhead 트래커 구조체(trackerproc_overhead), 리더 선언 112바이트와 같음.
  전제: prebuilt bin이 이 소스로 빌드됐다는 TI 배포 기준. 바이너리 대조는 안 함.

==================================================================
3. 실측 원본 CSV (요청 3)
==================================================================
2026-10-24 과방, Pi, 각 300초, 5,455프레임, 누락 0, 깨짐 0 (오늘 다시 계산해 확인).
타임라인 공통: 0~60초 빈 자리(사람은 보드 대각선 뒤) → 60~78초 앉기 → 240초까지 가만히 → 240초 일어나 나감 → 300초 종료.
열: wall_time, frame_number, num_points, nearest_range_m, num_tracks, presence, bad_frame
  wall_time은 Pi 벽시계(time.time). 시험 간 비교용이고 monotonic 아님.
  num_tracks=0은 리더가 1010 없음을 0으로 적은 값 (위 2절에 따르면 정상 프레임에선 같은 뜻).

  파일                                          cfg                인원  빈자리0~60s  정지85~240s 추적>0  둘다0   나간 뒤 260~300s 추적>0
  csv/testA_origcfg_3people_still_orig.csv      staticRetention     3     추적0 100%   100%               0%     53.9% (3명 퇴장)
  csv/testB_sedancfg_1person_still_car.csv      ODS_sedan_est       1     추적0 100%   95.7%              1.3%   0%  (246.5s에 소거)
  csv/testC_origcfg_1person_still_orig1.csv     staticRetention     1     추적0 98.2%* 100%(1명 정확 0%)  0%     32.0% (유령, 272.9s 소거)
  * 시험 C 빈 자리 구간의 나머지 1.8%는 재실=1만 뜬 프레임.
  sha256: A 88bb0015...7e65 / B 5b34a065...ac7 / C 08262d87...71
  (전체 해시는 SHA256SUMS.txt)

없는 것:
  - 따로 하는 "빈 좌석 3분" 시험은 아직 안 함. 빈 자리 근거는 위 각 파일의 0~60초, 나간 뒤 구간뿐.
  - 원본 바이너리 캡처 없음.
  - 시험 B는 성인 1명, 방(실차·전동차 아님). 5초 규칙은 이 1.3초 공백 기준 제안값.

==================================================================
4. 설치 방향 (요청 3)
==================================================================
시험 배치: 선반 위 약 1.2 m, 안테나 면이 의자를 향하게 살짝 아래(cfg sensorPosition 1.2 0 15 = 높이 1.2 m, 아래 15°),
의자는 보드 정면 1.5 m. 앞 약 4 m에 벽.
차량용 cfg 영역(보드 바닥 기준, m): 추적 X ±0.8 / Y 0.3~2.4 / Z 0~1.3,
  정지·재실 X ±0.65 / Y 0.5~2.3 / Z 0.2~1.2.
시야 ±70°라 보드 바로 뒤·옆뒤 사람도 잡힌 적 있음.
사진: 아직 없음. 다음 보드 연결 때 같은 배치로 다시 놓고 찍어서 보냄
  (① 옆에서 보드·의자 거리 보이게 ② 보드 뒤에서 의자 쪽 ③ 안테나 면 정면 각도).

==================================================================
5. B가 다음에 할 것
==================================================================
  [ ] 보드 연결 → check_radar_firmware.py 결과 전달 (현재 펌웨어 실물 확인)
  [ ] 3D People Tracking 재굽기 → 다시 확인 → Pi에서 ODS_sedan_est.cfg 1분 수신 확인
  [ ] 배치 사진 3장
  [ ] (요청 있으면) 빈 좌석 3분 + 재착석 시험, 이번엔 raw 바이트도 같이 저장
