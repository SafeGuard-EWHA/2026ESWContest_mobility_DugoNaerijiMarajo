# SafeGuard 장치 제어 소스

[구현 구성](../README.md) · [검증 결과](../docs/VALIDATION.md) · [열 예측 방법](../docs/THERMAL_MODEL.md) · [운영 안내](../docs/OPERATIONS.md)

`src/`는 상태기계·열 예측·출력 제어, `scripts/`는 센서 허브·위치/날씨·대시보드·접속 서비스를 구현합니다.

기준 설정은 `configs/real_navigation_control.json`입니다. 위험 온도 35°C, 유효 ETA≤60초 선제 보호, 서보 보호 각도 80°를 사용합니다. 실제 구동 범위는 장치와 기구에 맞춰 확인합니다.

활성 열 모델 `ambient_heat_balance_observer_v2`는 실내·외기온도 이력을 함께 사용합니다. 기존 `thermal.enabled=false / calibrated=false`는 과거 RC 경로 설정이며 활성 관측기의 `predictive_control_enabled`와 구분합니다.

제어기는 정지 유지로 시작하며, 대시보드에서 감시 재개를 요청합니다. 운영 서비스와 인증서·장치 경로의 최초 설정은 [운영 안내](../docs/OPERATIONS.md)를 따릅니다.

현재 제어용 펌웨어는 [SafeGuard_Software_Stop-0.3.0](../SafeGuard_Software_Stop_20261024/firmware/SafeGuard_Software_Stop/)입니다. `README_BASE_20261023.md`, 과거 `docs`, `firmware/esp32_reference`, `real.json`은 해당 버전의 참고 자료로 보존합니다.
