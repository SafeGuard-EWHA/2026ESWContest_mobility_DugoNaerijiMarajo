# 장치 제어 소스

[현재 상태](../docs/STATUS.md) · [Pi 사용 순서](../docs/OPERATIONS.md) · [열 예측 방법](../docs/THERMAL_MODEL.md)

- 기준 설정: `configs/real_navigation_control.json`. 위험 온도 35°C, 서보 보호 각도 80°, 유효한 ETA≤60초 선제 보호.
- 활성 모델: `ambient_heat_balance_observer_v2`. 실제 실내온도와 유효한 위치 기반 외기온 600초 이력을 사용합니다. 기존 `thermal.enabled=false / calibrated=false`는 과거 RC 경로 설정이며 예측 전체가 꺼졌다는 뜻이 아닙니다.
- 팀 Pi에는 새 폴더로 빌드했으며 웹·위치 서비스만 자동 시작합니다. 현재 접속 점검 모드로 실내 입력·예측·출력은 비활성입니다.
- 센서 연결 후 실제 제어 서비스를 활성화하는 최초 설정과 실물 검증이 필요합니다. 이후에는 부팅 시 정지 유지 → 대시보드 감시 재개로 사용합니다.
- GitHub 소스 갱신·Pi 서비스 설정·ESP32 펌웨어 업로드는 각각 별도 작업입니다. 기존 Main·촬영본을 덮어쓰지 않습니다.
- `README_BASE_20261023.md`, 기존 `docs`, `firmware/esp32_reference`, `real.json`은 과거 기본 프로젝트 자료입니다. 현재 제어용 펌웨어는 [SafeGuard_Software_Stop-0.3.0](../SafeGuard_Software_Stop_20261024/firmware/SafeGuard_Software_Stop/)이며 연결 시 실제 버전을 확인합니다.
