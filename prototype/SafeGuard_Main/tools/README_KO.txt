SafeGuard 실측 평가 도구

측정값은 포함하지 않았다. measurement_templates의 빈 CSV에 실제 관측을 기록한 뒤 실행한다.
Python 표준 라이브러리만 사용한다. 프로젝트 최상위 폴더에서:

python3 tools/evaluate_measurements.py power measurement_templates/power.csv
python3 tools/evaluate_measurements.py uwb measurement_templates/uwb_distance.csv
python3 tools/evaluate_measurements.py thermal measurement_templates/thermal.csv
python3 tools/evaluate_measurements.py occupancy measurement_templates/occupancy.csv

결과는 JSON이다. 파일에 보관하려면 명령 뒤에 > 결과파일.json을 붙인다.
빈 표 또는 계산할 짝이 없으면 insufficient_data / null이며, 0% 성공률로 만들지 않는다.
입력 오류는 행 번호와 함께 종료 코드 2로 알린다. 오류 행을 조용히 지우지 않는다.

공통 기록 원칙
- mode는 REAL/DEMO/REPLAY/SIMULATED 중 하나. 거리·온도·검출 지표는 REAL만 집계한다.
- 가상값을 REAL로 이름만 바꾸어 넣지 않는다. 이 도구는 센서 출처 자체를 인증하지 않는다.
- 실패·결측 시험도 행을 남긴다. 숫자 nan/inf는 허용하지 않는다.
- condition에는 밝음/어두움/가림/정지 등 조건을, run_id/trial_id에는 식별자를 기록한다.
- 설정이 달라지면 run_id 또는 condition을 구분한다. CSV 수치 셀에는 단위를 넣지 않는다.

1. 전력 power
boundary는 실제 계측 경계(예: Pi_USB, Actuator_12V)를 뜻한다. 서로 다른 실행은 별도 CSV로 저장한다.
time_s는 같은 경계 안에서 반드시 증가하는 초 단위 시각이다. 전압·전류는 소비 방향의 0 이상 값이다.
각 시각의 P=V*I를 다음 표본까지 일정하다고 보는 왼쪽 직사각형 적분 E=ΣP_i*(t_i+1-t_i)을 사용한다.
구간은 시작 표본의 state에 배정한다. 상태가 바뀌는 시각에도 측정 행을 남긴다.
마지막 표본 뒤 시간을 추정하지 않으며, 표본 1개로는 에너지/평균전력을 계산하지 않는다.
경계별·상태별 에너지(J), 지속시간(s), 평균전력(W), 최대 표본간격을 출력한다.
서로 겹치는 계측 경계를 이중 합산할 위험 때문에 전체 전력을 자동 합산하지 않는다.
12V 구동부만 측정했으면 Pi와 보호자 배터리를 포함한 전체 전력이라고 말하면 안 된다.
All-on/Event-driven 비교는 동일 시간·시나리오·출력·측정경계로 수행한다.
이 적분 결과는 표본 사이의 순간 피크 측정값이 아니다. 측정 공백이 길면 평균/에너지 오차가 커질 수 있다.

2. 거리 uwb
reference_m는 실제 안테나 기준 참거리, measured_m는 UWB 측정거리(미터)다. 둘 다 0 이상이다.
수신 실패는 measured_m를 빈칸으로 남기고 해당 시험 행을 보존한다.
condition/run_id별 유효쌍 MAE·bias·RMSE·오차 모집단 표준편차를 계산한다. 오차=측정-참거리.
missing_rate=빈 측정거리 행 수/전체 REAL 행 수. 출력은 0~1 비율이다.
빈 수신을 원래 CSV에 기록하지 않았다면 이 도구가 미관측 실패 수를 복원할 수 없다.
샘플링 횟수/시간을 먼저 정하고 누락된 표본 슬롯도 행으로 남긴다.

3. 온도 thermal
t0_s는 예측 시작 시각, horizon_s는 양수 예측시간, predicted_c는 t0 시점 정보로 만든 미래온도다.
measured_time_s는 실제 비교 온도의 시각이며 t0_s+horizon_s와 일치해야 한다(허용차 0.000001초).
비교 온도는 measured_future_c에 기록한다. 예측 시점의 현재온도를 미래 실측으로 넣지 않는다.
실험에서 고정 시각 측정을 준비한다. 시각 불일치 자료를 단순히 시각만 고쳐 맞추지 않는다.
예측 또는 실측이 없으면 해당 셀은 빈칸으로 남긴다. 실제 실측값이 있으면 실측시각도 필수다.
예측시간별 유효쌍 MAE/RMSE 등을 계산하며 불완전 행 수를 별도 표시한다.
같은 run_id/t0_s/horizon_s의 중복 행은 거부한다. 오차=예측-미래실측.
서로 다른 설정/시험체는 별도 CSV에서 평가한다. 보정용 실험과 평가용 실험도 분리한다.
시각 일치 검사는 미래정보 누출, 파라미터 보정, 실제 센서 측정 여부까지 증명하지 않는다.

4. 탑승자 occupancy
정해 둔 관측시간의 시험 1회를 행 하나로 기록한다. 프레임마다 행을 만들어 시험 수를 부풀리지 않는다.
truth_present는 참값 0/1, predicted_present는 판정 0/1 또는 빈칸(UNKNOWN)이다.
UNKNOWN을 0이나 안전 판정으로 바꾸지 않는다. 같은 condition/trial_id 중복은 거부한다.
TP/FN/FP/TN, 실제 있음의 UNKNOWN_POS, 실제 없음의 UNKNOWN_NEG를 따로 센다.
sensitivity_known_predictions = TP/(TP+FN): 알려진 판정만의 검출률.
false_positive_rate_known_predictions = FP/(FP+TN): 알려진 판정만의 오경보율.
positive/negative_prediction_coverage: 실제 있음/없음 각각에서 UNKNOWN이 아닌 판정의 비율.
detected_fraction_all_positive_trials = TP/(TP+FN+UNKNOWN_POS): 전체 실제 있음 시험에서 검출한 비율.
마지막 지표는 UNKNOWN을 FN으로 재분류하지 않고, 전체 시험을 기준으로 성과를 함께 보여준다.
분모가 없으면 null이다. 알려진 판정만의 좋은 검출률을 UNKNOWN 비율 없이 제시하지 않는다.
