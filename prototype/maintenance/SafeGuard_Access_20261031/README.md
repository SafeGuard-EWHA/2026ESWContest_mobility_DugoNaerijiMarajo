# 2026-10-31 팀 Pi 접속 서비스 설치 기록

`activate_access.py`는 기존 팀 Pi의 `/home/pi/SafeGuard_Operational_20261031`에 대해 실제 사용한 접속 전용 설치기 원본입니다. navigation drop-in과 portal 서비스를 설정하며 제어 main을 실행하지 않습니다. 고정 경로·기존 TLS·위치 runner·사전 비밀번호 설정을 전제로 합니다.

기존 대상 unit/drop-in 파일이 있으면 덮어쓰지 않고 중단합니다. 이미 적용된 팀 Pi에 다시 실행하는 일반 업데이트 도구가 아닙니다. 기존 서비스 상태 백업 및 `--rollback` 경로를 제공하지만 rollback 실행은 이번 검증에 포함하지 않았습니다.

소스 준비 도구는 `../../stage_on_pi.py`, 서비스 정의 생성은 `../../prepare_services.py`입니다. 현재 동작과 남은 실물 단계는 [운영 안내](../../docs/OPERATIONS.md)를 참고하세요. 비밀번호·인증서·실행 시 생성된 백업은 이 보관 폴더에 포함하지 않습니다.
