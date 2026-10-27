"""Small exact-context changes. Does not change FSM, UART, firmware or actuator code."""
from pathlib import Path
import shutil

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('지원되지 않는 소스 또는 이미 적용된 패치: '+old[:80])
    return text.replace(old, new, 1)

def patch(root):
    root=Path(root)
    main=root/'src/main.cpp'
    s=main.read_text()
    s=replace_once(s, '#include "core.hpp"', '#include "core.hpp"\n#include "thermal_observer.hpp"')
    s=replace_once(s, 'safeguard::Core core(core_config);',
      'safeguard::ThermalObserver thermal_observer;\n        safeguard::Core core(core_config);')
    anchor='            if (!actuator.fault.empty()) snapshot["faults"].push_back(actuator.fault);'
    s=replace_once(s, anchor, '''            // Observation only: this object is never passed to Core or ActuatorLink.
            if (project.value("thermal",Json::object()).value("literature_observer_enabled",false)) {
                const bool fan_or_unknown = output.demand_fan || feedback.fan ||
                    (mode == "REAL" && !(feedback.valid &&
                     store.fresh(feedback.timestamp_s,now,core_config.sensor_timeout_s)));
                snapshot["thermal_observer"] = thermal_observer.step(store.data,now,core_config,fan_or_unknown);
            }
'''+anchor)
    s=replace_once(s, '            snapshot["stopped"]=true;', '''            snapshot["thermal_observer"]={{"enabled",false},{"valid",false},
                {"reason","controller_stopped"},{"curve",Json::array()},{"t35_s",nullptr}};
            snapshot["stopped"]=true;''')
    main.write_text(s)
    shutil.copy2(Path(__file__).parent/'payload/thermal_observer.hpp',root/'src/thermal_observer.hpp')
    page=root/'scripts/dashboard.html'; s=page.read_text()
    s=replace_once(s, '      <div class="item"><h3 id="riskThresholdTitle">',
      '      <p class="note" id="thermalResearchNote" hidden></p>\n      <div class="item"><h3 id="riskThresholdTitle">')
    s=replace_once(s, 'thermal=object(s.thermal),',
      'thermal=object(s.thermal_observer?.enabled===true ? s.thermal_observer : s.thermal),')
    anchor='  drawCurve(thermal,riskTemperature);'
    s=replace_once(s,anchor,'''  const research=thermal.model==="literature_tau_observed_trend_v1";
  $("thermalResearchNote").hidden=!research;
  if(research) {
    const reasons={warming_up:"실측 이력 수집 중",temperature_invalid:"온도 입력 끊김 · 이력 초기화",
      fan_active_or_feedback_unknown:"팬 작동 또는 출력 상태 확인 불가 · 예측 중단",
      trend_unstable:"온도 추세 급변 · 예측 보류",forecast_out_of_range:"예측 범위 초과",
      clock_invalid:"시각 오류",mode_invalid:"입력 모드 오류",history_invalid:"이력 부족"};
    const elapsed=finite(thermal.history_s)?Math.min(600,Math.floor(thermal.history_s)):0;
    tag("thermalReady",thermal.valid===true?"연구용 추정 · 제어 미사용":"연구용 추정 대기");
    put("riskThresholdTitle",riskTemperature+"°C 도달 추정 · 향후 5분");
    put("thermalResearchNote","논문 기반 시간상수 + 최근 10분 실측 추세. 차량 정확도 미검증 · 자동 출력에 사용하지 않음. "+
      (thermal.ambient_in_study_range===false?"현재 외기는 원 연구 범위 밖입니다. ":"")+
      "미도달 표시는 안전 판정이 아닙니다.");
    if(thermal.measured_threshold_reached===true) put("t35","실측 온도 기준 도달");
    else if(thermal.valid!==true) put("t35",(reasons[thermal.reason]||"예측 대기")+
       (thermal.reason==="warming_up"?" · "+elapsed+" / 600초":""));
    else if(thermal.t35_s===null) put("t35","향후 5분 내 도달 추정 없음");
    else put("t35",(thermal.t35_s/60).toFixed(1)+"분 · 연구용 추정");
  }
  if(research && thermal.reason==="warming_up" && thermal.scenario?.valid===true) {
    put("riskThresholdTitle","일사 노출 주차 가정 · 참고 시나리오 (현재 환경 예측 아님)");
    drawCurve(thermal.scenario,riskTemperature);
  } else drawCurve(thermal,riskTemperature);
''')
    page.write_text(s)

if __name__=='__main__':
    import sys
    patch(sys.argv[1])
