SafeGuard C → C++ 메인 입력 연결 예제 v1.0.0
작성 기준: 2026-10-23

목적
현재 Pi에서 실측한 safeguard_uwb_reader.py v1.1.0의 JSON Lines 출력을
C++17 제어 프로그램에서 읽는 연결부입니다. 이탈 판정이나 전체 FSM은
구현하지 않습니다. 5m·10초 기준, PIR/카메라/mmWave/온도, 팬·부저 제어는
팀의 단일 최종 FSM에서 통합해야 합니다.

포함 파일
- safeguard_uwb_input.hpp: 메인 프로그램에서 재사용하는 입력 상태·유효성 검사.
- safeguard_uwb_main_input.cpp: 표준입력 JSONL을 받아 상태를 표시하는 실행 예제.
- test_uwb_input.cpp: 입력 오류와 수신 중단 처리를 확인하는 소프트웨어 검사.
- README_KO.txt: 설치·실행·팀 전달 안내.

현재 성공한 safeguard_uwb_reader.py는 이 ZIP에 넣지 않았습니다.
Pi의 기존 파일을 그대로 사용합니다. 새 예제는 UART에 직접 접속하지 않고
기존 reader의 표준출력만 읽습니다. 시리얼 포트를 동시에 두 번 열지 않습니다.

현재 확인된 연결
- Pi 사용자/호스트: pi@safeguard.local
- Pi 작업 폴더: /home/pi/safeguard_c
- 차량측 UWB: 8809, Pi /dev/ttyACM0, USB 일련번호 000760217939
- 보호자측 UWB: 0CA7, 노트북 USB에서 전원 공급
- 양쪽 PAN ID: 1234
- 차량측 active Tag, 보호자측 Initiator Anchor
- UART: 115200, 8N1, 흐름제어 없음
- 실측 reader JSON: peer_id=0CA7, window=7, timeout_s=2.0

실행 순서
1. Pi SSH 창에서 기존 reader가 실행 중이면 Ctrl+C 한 번으로 종료합니다.
   두 UWB의 USB와 Pi 전원은 그대로 유지합니다.

2. Windows에서 ZIP을 C:\SafeGuard_C\SafeGuard_C_Main_Link.zip으로 저장합니다.
   새 Windows 명령 프롬프트에서 실행합니다(Pi SSH 창에 입력하지 않습니다).

   scp C:\SafeGuard_C\SafeGuard_C_Main_Link.zip pi@safeguard.local:/home/pi/safeguard_c/

3. 기존 Pi SSH 창에서 아래를 한 줄씩 실행합니다.

   cd ~/safeguard_c
   python3 -m zipfile -e SafeGuard_C_Main_Link.zip .
   sudo apt install -y g++ nlohmann-json3-dev
   g++ -std=c++17 -O2 -Wall -Wextra safeguard_uwb_main_input.cpp -o safeguard_uwb_main_input
   set -o pipefail
   python3 safeguard_uwb_reader.py --port /dev/ttyACM0 --anchor-id 0CA7 --json | ./safeguard_uwb_main_input --anchor-id 0CA7

   설치가 패키지 목록 오류로 실패하면 sudo apt update 후 설치를 다시 실행합니다.
   컴파일이 성공하면 대개 출력 없이 Pi 명령 입력 줄로 돌아옵니다.
   코드 실행 전 GPIO 시리얼 설정이나 펌웨어를 다시 변경할 필요는 없습니다.

4. 처음에는 UNAVAILABLE, 7개 샘플을 모으면 다음과 비슷한 문구가 나옵니다.

   [UWB] READY distance_m=0.440 age_s=0.100

   위 숫자는 형식 예시입니다. 실제 출력은 보드의 측정값과 수신 시각에 따라 다릅니다.
   READY는 거리 입력의 형식·수신 신선도·필터 준비 조건을 만족했다는 뜻입니다.
   거리 정확도, 보호자 이탈, 탑승자 존재를 확정하는 표시가 아닙니다.
   reader의 Logs/Listening 안내는 표준오류에서 보일 수 있으며 정상입니다.

5. 종료는 Ctrl+C 한 번입니다. reader는 로그를 저장하고 시리얼을 닫습니다.
   USB를 뽑지 않았다면 lec를 다시 입력하지 않습니다.
   차량측 USB를 재연결했다면 포트와 lec 출력 상태부터 다시 확인해야 합니다.

입력 연결부의 중요한 동작
- 지정 보호자 ID, type=uwb, schema_version=1, source=REAL_UWB를 확인합니다.
- fresh/valid/filter_ready/usable_for_fsm과 거리·샘플 정보를 확인합니다.
- 거리 사용 불가 상태에서는 distance_m을 비웁니다. 0m로 대체하지 않습니다.
- 입력이 끊기거나 reader가 멈춰도 소비자 자신의 타이머로 유효성을 만료시킵니다.
- 이미 오래된 JSON을 늦게 읽은 경우 수신 시각을 검사하여 사용하지 않습니다.
- 표준입력 EOF/오류/종료에서도 마지막 거리를 계속 유효하게 보관하지 않습니다.
- 신선도 제한 기본값 2초는 현재 설정값이며 최종 성능을 보증하는 값이 아닙니다.

시간·통신 조건
이 예제는 reader와 C++ 프로그램이 같은 Linux 호스트와 같은 부팅 세션에서
파이프로 연결되는 경우를 대상으로 합니다. Python time.monotonic과 Linux
CLOCK_MONOTONIC 기준을 사용합니다. 다른 컴퓨터의 monotonic 값을 직접
비교하거나 옛날 로그를 실시간 입력으로 연결하면 안 됩니다.
원격 전송이나 로그 재생을 추가할 때에는 별도의 시계/재생 프로토콜이 필요합니다.

팀 메인 프로그램으로 옮길 부분
  safeguard::UwbInput input("0CA7", 2.0);
  input.ingest(json_line, now_monotonic_s);  // 새 한 줄이 들어온 경우
  input.tick(now_monotonic_s);               // 새 입력이 없어도 제어 주기마다 호출
  const auto &s = input.state();
  if (s.ready && s.distance_m.has_value()) {
      // *s.distance_m을 최종 FSM의 거리 입력으로 전달
  } else {
      // UWB 입력 사용 불가/UNKNOWN으로 전달
  }

위 코드는 연결 위치 설명용 조각이며 완성된 main 함수가 아닙니다.
실제 메인에서는 입력 읽기가 다른 센서와 제어 주기를 막지 않게 해야 합니다.
예제 .cpp의 poll/read 루프를 참고하고, EOF 때 input.invalidate("eof")를 호출합니다.
입력 객체를 여러 스레드에서 공유한다면 mutex 등으로 접근을 보호해야 합니다.
최종 FSM만 이탈 유지시간과 보호 동작을 결정하도록 합니다.

검증 범위와 남은 작업
- 사용자가 Windows와 Pi에서 v1.1.0 reader의 실제 JSON 출력을 확인했습니다.
- 사용자가 Pi에서 보호자 전원 차단 후 무효화, 재연결 후 복구를 확인했습니다.
- 이 ZIP의 C++ 연결 예제는 개발 환경에서 C++17 경고 없는 컴파일과
  형식·타입·노드ID·샘플 준비·수신시각·순서·재시작 검사에 통과했습니다.
  기존 Python reader의 JSON 생성 함수를 실제 C++ 표준입력에 연결하여
  준비/무효화/복구, 무개행 부분 입력 중 watchdog, EOF 무효화도 확인했습니다.
  사용자의 Pi에서 컴파일·실행되는지는 위 절차의 READY 출력으로 확인합니다.
- 전체 A/B/C 통합 메인 코드는 아직 제공되지 않았으며 연결 완료로 간주하지 않습니다.
- 보호자 휴대용 독립전원, 거리 정확도 및 최종 이탈 기준 검증은 별도 작업입니다.

참고한 공식 문서
https://json.nlohmann.me/integration/package_managers/
https://packages.debian.org/trixie/nlohmann-json3-dev
https://docs.python.org/3/library/time.html#time.monotonic
https://docs.python.org/3/library/zipfile.html#command-line-interface
