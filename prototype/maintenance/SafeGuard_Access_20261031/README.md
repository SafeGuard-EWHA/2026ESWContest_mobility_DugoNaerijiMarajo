# HTTPS 접속 서비스 설치 도구

`activate_access.py`는 `/home/pi/SafeGuard_Operational_20261031`을 대상으로 navigation drop-in과 portal 서비스를 설정합니다. 제어 main은 별도로 구성합니다. 고정 경로·기존 TLS·위치 runner·사전 비밀번호 설정을 전제로 합니다.

기존 대상 unit/drop-in 파일이 있으면 덮어쓰지 않고 중단합니다. 반복 실행하는 일반 업데이트 도구가 아니므로 대상 경로와 기존 서비스를 먼저 확인합니다. 서비스 상태 백업과 `--rollback` 기능이 포함되어 있으며, rollback 실행은 공개 검증 결과에 포함하지 않습니다.

소스 준비는 `../../stage_on_pi.py`, 서비스 정의 생성은 `../../prepare_services.py`를 사용합니다. [운영 안내](../../docs/OPERATIONS.md)에 최초 설정과 사용 순서를 정리했습니다. 비밀번호·인증서·실행 중 생성되는 백업은 저장소에 포함하지 않습니다.
