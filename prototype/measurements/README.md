# 측정 원본과 PPT용 그래프

2026-10-28 정리. **현재 전달받은 원본 88개**를 바이트 변경 없이 보관했습니다. 출처·크기·SHA256은 [MANIFEST.json](MANIFEST.json)에 있습니다. Pi의 `/home/pi/safeguard_c` 폴더 전체를 받은 것은 아니므로 그 폴더에만 있는 추가 측정 파일은 아직 포함되지 않았습니다.

## 바로 사용할 자료

| 자료 | PPT용 그림 | 측정 원본 |
|---|---|---|
| UWB 두 세션: 원시 거리와 필터 거리 | [PNG](figures/uwb_sessions.png) · [SVG](figures/uwb_sessions.svg) | [CSV·원시 로그](raw/uwb_20261016/) |
| 레이더 Test3와 동시 카메라 | [PNG](figures/radar_test3_timeline.png) · [SVG](figures/radar_test3_timeline.svg) | [CSV·행동시각·바이너리·사진](raw/block_b_20261027/reply3/1_radar_test3/) |
| 카메라 움직임·조명 변화 | [PNG](figures/camera_light_timeline.png) · [SVG](figures/camera_light_timeline.svg) | [CSV·안내시각·스냅샷](raw/block_b_20261027/reply3/2_camera/) |
| 실험 배치 사진 | [원본 사진 6장](raw/block_b_20261027/reply3/5_photos/) | 같은 폴더의 촬영 설명 |
| 수치 요약 | [JSON](derived/summary.json) · [레이더 구간 CSV](derived/radar_interval_summary.csv) | 아래 재생성 도구로 계산 |

SVG는 확대 편집용, PNG는 슬라이드 삽입용입니다. 그래프는 제공된 CSV 전체를 그렸으며 시간축은 각 CSV 또는 안내 시각을 기준으로 합니다. 그래프 점선은 레이더에서는 기록된 실제 행동 시각, 카메라 조명 시험에서는 안내 시각입니다.

## PPT에 쓸 수 있는 해석과 범위

- UWB: 1차 1,109행/약 602.5초, 2차 114행/58초. 필터 전후 거리 변화를 보여줍니다. 참조 거리의 시간별 정답이 없으므로 정확도·거리 오차 개선률로 표현하지 않습니다.
- 레이더 Test3: 총 8,363프레임, CSV의 bad_frame=0. 원본 행동 기록을 기준으로 초기 빈자리 [0,170)초 0/3,090프레임, 착석 정지 [180,300)초 2,182/2,182프레임에서 존재 증거가 표시됩니다. 하지만 퇴장 후 빈자리 [315,375)초에도 1,090/1,090프레임에서 표시됩니다. **이탈 후 잔류 트랙 문제를 포함한 한 차례 실험**이며 일반적인 검출 정확도 100%가 아닙니다. 존재 증거는 `num_tracks > 0 OR presence == 1`입니다.
- 카메라: 움직임과 조명 변화 시 입력 반응을 보여줍니다. 정지한 사람의 존재·호흡을 검증한 그래프가 아닙니다. 조명 변화 구간의 큰 픽셀 변화와 motion_active 결과는 구분해서 읽습니다.
- 팀원 회신4는 Test3의 재분석과 수정 후보입니다. 새 측정이 아닙니다. 회신3의 원인 추정은 회신4에서 `static2free=3000` 관련 분석으로 정정되었고, 500/200/100 후보 설정의 실기 성공은 아직 확인되지 않았습니다.
- 열 예측 자료의 문헌 그래프 약독·합성 입력 테스트는 이 측정 원본과 별개입니다. [선제 보호 구현/검증](../maintenance/SafeGuard_Predictive_Control_20261028/)과 [문헌 방법](../maintenance/SafeGuard_Thermal_20261028/METHOD.md)을 참고하세요. 실제 선제 보호 구동 성공 로그는 아직 제출되지 않았습니다.

## 원본 묶음 전체

- [회신1](raw/block_b_20261027/reply1/): 비교 CSV 3개, 설정·점검 도구·설명.
- [회신2](raw/block_b_20261027/reply2/): 펌웨어 점검, 60초 수신 CSV/RAW/인덱스·진단 로그.
- [회신3](raw/block_b_20261027/reply3/): 레이더 Test3, 카메라 조명 실험, 동시 기록, 원본 사진, 최종 전달 도구.
- [회신4](raw/block_b_20261027/reply4/): 문제 분석, 재시작 도구, 미시험 설정 후보.
- [A블록 과거 직렬 출력](raw/block_a_20261024/observed_serial.txt).
- [과거 UWB 리더·C++ 연동 전달 코드](tools/uwb_legacy/): 참고 이력이며 현재 실행 코드에 자동 적용하지 않습니다.

ZIP 안의 Windows 경로 구분자만 `/`로 정규화했습니다. 원본 파일 내용은 유지했습니다. 각 묶음 내부 SHA256SUMS는 당시 묶음 기준이며, 이번 전체 목록은 MANIFEST 기준입니다. 사진·측정 로그는 팀의 프로젝트 자료로 보관합니다.

## 그래프 재생성

저장소 루트에서 Python 3와 Matplotlib이 있는 환경으로 실행합니다.

```bash
python3 -m pip install matplotlib
python3 prototype/measurements/tools/plot_measurements.py
```

현재 생성 환경은 Python 3 / Matplotlib입니다. 실행 시 figures와 derived만 갱신하며 raw는 수정하지 않습니다. 저장소 루트의 TwinLab `sample_data`는 시뮬레이션 예시이므로 위 실측 원본과 혼합해 실측이라고 발표하지 않습니다.
