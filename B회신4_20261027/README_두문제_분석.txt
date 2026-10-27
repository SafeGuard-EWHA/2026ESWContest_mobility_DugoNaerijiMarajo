SafeGuard B블록 → 메인: 레이더 두 문제 분석과 비교 시험안
작성 2026-10-27 / 받은 로그(시험 3 raw.bin·CSV)와 TI Radar Toolbox 4.00.00.05 소스·문서로만 분석함.
레이더 실물은 이번에 쓰지 않음. 아래 시험은 시간 맞춘 뒤 진행.
기존 ODS_sedan_est.cfg는 그대로 두고(SHA256 674fbe92…82ce, 변경 없음) 후보는 별도 파일로 만듦.

==================================================================
문제 1. 퇴장 후 빈 좌석인데 감지가 73초 이상 남음
==================================================================
1-1. stateParam 각 칸의 뜻 (펌웨어에 실제 들어간 트래커 헤더 기준)
  출처: radar_toolbox_4_00_00_05/source/ti/custom_sdk_files/sdk3/dpu/trackerproc_overhead/
        packages/ti/alg/gtrack/gtrack.h 495~510행 (3D People Tracking projectspec이 이 trackerproc_overhead를 씀)
        + software_docs/Tuning_Guides/tracker_tuning/Tracker_Tuning_Guide.html "Track State Parameters"
  stateParam det2act det2free active2free static2free exit2free sleep2free  (단위: 프레임, 55 ms)
  - active2free: 일반 상황에서 점을 연속으로 못 받은 프레임 수. 정지점·움직임점 어느 쪽이든 받으면 리셋.
  - static2free: "정지 상태 + 정지 영역(staticBoundaryBox) 안" 추적이 점을 연속으로 못 받은 프레임 수.
  - exit2free  : 정지 영역 밖 추적이 점을 연속으로 못 받은 프레임 수.
  - sleep2free : 정지 영역 안 정지 추적의 최대 유지 시간. 이 카운터는 "움직이는 점"을 받을 때만 리셋.
                 즉 정지점(의자 등)만 계속 받는 추적은 이 시간 뒤 지워짐.

  현재 cfg: stateParam 3 3 12 3000 5 6000
    static2free 3000 = 약 165초,  sleep2free 6000 = 약 330초
  원본 ODS_6m_staticRetention.cfg: 3 3 12 500 5 600  (약 27.5초 / 33초)
  TI ODS_6m_default.cfg:            3 3 12 500 5 6000 (약 27.5초 / 330초)
  ※ 지난 인계서에는 sleep2free만 적었지만, 실제로는 static2free도 500 → 3000으로 함께 늘려 둔 상태였음.

1-2. 시험 3 데이터로 본 원인  (analyze_test3_tracks.py, 결과 analyze_test3_tracks_output.txt)
  퇴장 후 빈자리 60초(1,090 프레임) 동안 고정된 두 추적(id0: x -0.01 y 0.81, id4: x -0.37 y 1.11) 반경 0.5 m 안의
  점(정지점·움직임점 모두): 0개.
  → 점을 하나도 못 받는 정지 추적이므로 sleep2free가 아니라 static2free(3000, 약 165초)가 지우는 시간을 정함.
    예상 소거 시간 약 165초 > 관찰 73초 이상 — 모순 없음 (기록이 그 전에 끝남).
  참고: 원본 cfg 시험 C에서 일어난 뒤 약 33초 뒤 사라진 것도 static2free 500(27.5초)과 맞음.
        시험 B(같은 sedan cfg)에서 6초 만에 사라진 것은 추적이 사람을 따라 정지 영역 밖으로 나가
        exit2free(5프레임)로 지워진 경우로 보임 (raw가 없어 확인 불가). 즉 나가는 방식에 따라
        "추적이 따라 나가면 수 초", "의자 자리에 남겨지면 static2free 시간"이 됨.
  presence(1021)도 같은 시간 1이었음: 재실 판정은 영역 안에 추적이 있으면 1이라서 고정 추적과 같이 남음.

  앉아 있는 사람 쪽 여유 (같은 데이터):
    정지 2분 동안 사람 추적 주변 점이 끊긴 최장 0.55초, 재착석 30초 동안 최장 1.93초.
    움직이는 점이 끊긴 최장도 1.93초 → sleep2free(6000)는 이번 시험에서는 전혀 문제 안 됨.
  한계: 성인 1명, 1회, 의자 1개 배치. 아이·잠든 자세·담요 등은 미확인.

1-3. 조정 후보 (cfg/ 폴더, stateParam 한 줄만 다름, 다른 줄은 ODS_sedan_est.cfg와 같음)
  파일                  stateParam              점 없는 정지 추적 소거  1.93초 대비 여유  SHA256
  ODS_sedan_est.cfg     3 3 12 3000 5 6000      약 165초 (현재)          -                674fbe92…82ce
  ODS_sedan_s2f500.cfg  3 3 12 500 5 6000       약 27.5초 (TI 기본값)    14배             c840867e…65cb
  ODS_sedan_s2f200.cfg  3 3 12 200 5 6000       약 11초                  5.7배            24c085bf…e8fc
  ODS_sedan_s2f100.cfg  3 3 12 100 5 6000       약 5.5초                 2.8배            f9beec9d…befed
  sleep2free 6000은 셋 다 그대로 (정지점만 있는 추적의 최대 유지, 잠든 아이 대비).
  메인의 "5초 연속 음성이면 EMPTY" 규칙과 합치면 퇴장 후 EMPTY까지 약 (소거 시간 + 5초).
  카메라 움직임 없음으로 사람 없음 처리하지 않는다는 방침과 무관하게 레이더만으로 줄이는 방법임.

1-4. 비교 시험안 (레이더 시간 맞춘 뒤, 같은 배치, 영역 안에 다른 사람 없음)
  순서: s2f100 → s2f200 → s2f500, 세 값 모두 시험한다 (100에서 사람이 누락돼도 200·500에서는 유지될 수 있으므로
        어느 값도 생략하지 않음. 필요하면 기준값 3000도 같은 순서로 다시 측정해 비교)
  cfg마다 1회 약 9분, 시작 전 레이더 USB 재연결 필수 (문제 2: cfg를 바꾸려면 장치 재시작 필요):
    0:00 빈 좌석 60초
    1:00 착석 → 가만히 3분 (마지막 1분은 등받이에 기대고 최대한 움직이지 않기 — 잠든 자세 흉내)
    4:10 보통 속도로 일어나 나감 (퇴장 1) → 빈 좌석 90초
    5:55 재착석 → 가만히 60초
    7:05 빠르게 일어나 나감 (퇴장 2) → 빈 좌석 90초 → 끝
  기록: mmwave_reader.py --csv --raw (원본 바이트), 카메라는 행동 시각 확인용으로만 동시 기록, 음성 안내 시각.
  측정·판정:
    정지 유지  : 양성(추적>0 또는 presence=1) 비율, 최장 음성 구간 → 5초 미만이어야 함 (메인 5초 규칙에서 거짓 EMPTY 0)
    퇴장 소거  : 실제 일어난 시각(카메라)부터 마지막 양성 프레임까지 → 소거 시간 + 수 초 안이어야 함
                 퇴장 1·2 각각, 추적이 따라 나갔는지/남겨졌는지는 raw 좌표로 구분
    재착석     : 첫 추적까지 시간
    빈 좌석     : 유령 추적 0
  선택 기준: 정지 유지 통과한 값 중 소거가 가장 빠른 것. 단 아이·잠든 자세를 못 해봤으므로
             통과한 최소값보다 한 단계 큰 값을 권장할 수 있음 (같이 결정).

==================================================================
문제 2. sensorStop 뒤 sensorStart가 응답하지 않음
==================================================================
2-1. 펌웨어 소스와 TI 문서
  출처: 3D_People_Tracking/src/6843/mss/pcount3D_cli.c 137~345행
  - 멈춘 뒤 다시 시작하는 길은 두 가지로 코드에 있음:
      (a) "sensorStart 0"  : 설정을 다시 보내지 않고 같은 설정으로 재시작
      (b) 전체 cfg 다시 전송 + "sensorStart" : 재설정 후 시작.
          이때 channelCfg·lowPower·adcCfg가 처음과 다르면 "Exception: ..." 출력 (같은 cfg면 해당 없음)
  - "sensorStart 1"은 "Error: Reconfig is not supported" 로 거부.
  - TI 3D People Tracking 사용자 가이드(docs/3d_people_tracking_user_guide.html):
      "Device must be restarted before sending a new configuration."
    → (b)처럼 멈춘 뒤 cfg를 다시 보내는 방식은 TI가 장치 재시작을 요구하는 경우.

2-2. 우리 리더가 한 일과 당시 기록
  mmwave_reader.py는 시작할 때마다 cfg 전체(sensorStop, flushCfg, … , sensorStart)를 보내고,
  끝날 때 항상 sensorStop을 보냄 → 다음 실행은 늘 (b) 경로 → TI가 지원하지 않는 경로를 매번 탐.
  (a) "sensorStart 0"은 한 번도 시도하지 않았음.
  남아 있는 기록 (10/24, Pi, 다른 세션 출력):
    설정 전송: ODS_6m_staticRetention.cfg (34줄)
    [CFG 실패] sensorStart -> sensorStart
    설정 전송 실패. S1이 Functional 모드인지, 보드를 다시 꽂았는지 확인하세요.
  뜻: 보드가 "sensorStart"를 되돌려 보냈지만(에코) 리더 대기 3초 안에 Done/Error가 오지 않음.
  한계: 리더가 그 뒤 출력을 저장하지 않아서 "멈춤"인지 "3초보다 늦은 응답"인지, Exception 문구가 있었는지 모름.
        다른 CLI 오류 로그는 남아 있지 않음 (Pi ~/*.log에 해당 문구 없음 확인).

2-3. 원인 판단
  확정: 멈춘 뒤 cfg를 다시 보내는 방식은 TI 문서상 장치 재시작이 필요한 경로이고, 우리가 매번 그 경로를 썼음.
  미확정: 그때 보드가 정확히 어떤 상태였는지(멈춤/지연/예외) — 아래 진단으로 확인.

2-4. 복구 방법 후보
  ① (권장) 전원 켠 뒤 한 번만 cfg 전송·시작하고 계속 측정. 프로그램을 다시 띄울 때는 cfg를 보내지 않고
     데이터만 읽기(리더의 --no-cfg). 프로그램 종료 때 sensorStop을 보내지 않기.
     → 메인 계획(시연 중 계속 수신, FSM 전이마다 stop/start 안 함)과 같음.
     주의: 장치에 지금 어떤 cfg가 들어가 있는지 장치에서 읽을 방법은 없음 → 시작한 cfg의 해시를 Pi 파일에 기록해 두고 대조.
  ② 일시정지/재개가 필요하면 sensorStop → "sensorStart 0". 소스상 지원, 미시험 → 아래 진단 1.
  ③ cfg를 바꿔야 하면 장치 재시작이 필요. 지금은 USB 재연결(수동)만 확인됨.
     소프트웨어로 전원을 끊는 방법(Pi USB 포트 전원 제어 등)은 Pi 5에서 ESP32·UWB 포트까지 같이 끊길 수 있어 권장 안 함, 미시험.
     보드 리셋 핀(NRST, 60핀 커넥터)을 GPIO로 제어하는 방법은 배선 변경 필요, 미시험.

2-5. 진단 시험안 (약 5분, 레이더만 사용, 카메라·ESP32·UWB 무관)
  scripts/restart_check.py: CLI로 오가는 바이트를 전부 시각과 함께 로그로 남김. 포트는 by-id만 받음.
  1) 레이더 USB 재연결 →
     python3 -u hardware/mmwave/restart_check.py --mode start0 --cli <if00> --data <if01> \
       --cfg hardware/mmwave/people_tracking/ODS_sedan_est.cfg --log ~/restart_start0.log
     (처음 시작 → 프레임 확인 → sensorStop → 멈춤 확인 → "sensorStart 0" → 15초 응답 기록 → 프레임 확인)
  2) 레이더 USB 재연결 →
     같은 명령에 --mode fullcfg --log ~/restart_fullcfg.log
     (멈춘 뒤 cfg 전체 재전송 → sensorStart 응답을 3초가 아니라 15초까지 기다리며 기록)
  결과로 알 수 있는 것: (a) 경로가 되는지 / (b) 경로가 늦게라도 되는지, 멈추는지, Exception이 나오는지.
  하드웨어 없이 가짜 장치로 스크립트 흐름만 확인함 (성공·무응답 두 경우 모두 올바르게 판정).

==================================================================
파일
==================================================================
cfg/ODS_sedan_est.cfg                 기존 cfg (변경 없음, 비교용 사본)
cfg/ODS_sedan_s2f500|200|100.cfg      문제 1 후보 (B 저장소 hardware/mmwave/people_tracking/에도 같은 파일, 미커밋)
scripts/restart_check.py              문제 2 진단 (B 저장소 hardware/mmwave/restart_check.py, 미커밋)
scripts/mmwave_reader.py              restart_check.py가 import하는 리더 (--raw 추가본, 같은 폴더에 둬야 함)
analyze_test3_tracks.py / _output.txt  1-2의 수치 재현용 (시험 3 폴더와 B 저장소 hardware/mmwave 경로를 인자로 받음)
Pi에는 아직 아무것도 복사하지 않음. 레이더도 계속 정지 상태.
