# SafeGuard TwinLab Agent — 심사 발표용 1분 데모 스크립트

사전 준비: `bash scripts/run_dashboard.sh` 로 대시보드를 미리 켜두고,
사이드바가 "시나리오 초기화(defaults)" 상태인지 확인한다.

| 시간 | 화면 조작 | 발표 멘트 |
|---|---|---|
| 0:00–0:08 | (화면 전체) | "차량에 아이가 혼자 남겨지는 사고, SafeGuard는 보호자가 멀어진 순간부터 UWB→PIR/Camera→mmWave→온도예측→액추에이터까지 **단계적으로만** 센서를 깨우는 Cascading Wake-up 시스템입니다." |
| 0:08–0:20 | 사이드바 **Demo Mode → "Normal Risk Scenario"** 클릭 | "지금 보호자가 이탈하고 아이가 남아있는 위험 시나리오를 한 번에 적용했습니다. State Machine Event Log를 보시면 UWB 이탈 판정, mmWave 탑승자 확인, 온도 임계값 초과가 순서대로 자동 기록됩니다." |
| 0:20–0:32 | **Model Comparison** 섹션으로 스크롤, **"Duty-cycle Optimized Scenario"** 클릭 | "같은 위험 상황에서 액추에이터만 continuous에서 duty-cycle로 바꾸면, All-on 대비 절감률이 즉시 재계산됩니다. 저희는 유리한 쪽만 보여주지 않고 continuous·duty-cycle 결과를 **항상 함께** 표시합니다." |
| 0:32–0:45 | **Demo Mode → "mmWave Timeout Fail-safe Scenario"** 클릭 | "이번엔 mmWave 센서가 아예 응답하지 않는 고장 상황입니다. SafeGuard는 무작정 액추에이터를 구동하지 않고, 6초 무응답을 감지해 **FAIL_SAFE**로 안전하게 전환합니다 — 이게 저희가 edge case를 버튼 하나로 시연할 수 있는 이유입니다." |
| 0:45–0:53 | 화면 상단 **Evidence Panel** 가리키기 | "이 모든 결과는 데이터 소스(Dummy/실측), 센서가 Virtual인지, 전력이 Estimated인지를 항상 투명하게 표시합니다. 과장 없이 '추정 모델 기반' 결과라는 걸 스스로 명시합니다." |
| 0:53–0:58 | **"Paper-ready 자동 생성"** 버튼 클릭 | "버튼 한 번이면 표 3종, 그림 4종, 해석문·캡션·한계·심사위원 Q&A까지 11개 파일이 그대로 논문 부록으로 저장됩니다." |
| 0:58–1:00 | (정면) | "SafeGuard TwinLab Agent, 감사합니다." |

## 백업 멘트 (질문 대비 한 줄 요약)

- **"전력 측정한 건가요?"** → "아니요, datasheet 기반 추정 모델입니다. 실측 로그와 교차 검증하는 경로도 이미 구현되어 있습니다."
- **"UWB/mmWave 진짜 센서인가요?"** → "output-level virtual sensor simulation입니다. raw radar 신호까지는 재현하지 않습니다."
- **"재현 가능한가요?"** → "random seed가 고정되어 있고, pytest 43개가 상태 전이와 전력 계산을 자동 검증합니다."
