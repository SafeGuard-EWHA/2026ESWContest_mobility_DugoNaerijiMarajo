#include "thermal_observer.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace safeguard;
InputSnapshot sample(double t,double temperature=25) {
    InputSnapshot s; s.mode="REAL";
    s.temperature={true,temperature,t,"REAL_ESP32"};
    s.ambient={true,25,t,"REAL_AMBIENT"}; return s;
}
int main() {
    Config c; ThermalObserver o;
    auto cold=o.step(sample(0),0,c,false);
    assert(!cold["valid"] && cold["reason"]=="warming_up" && cold["scenario"]["valid"]);
    assert(cold["scenario"]["curve"].size()==31 && cold["curve"].empty());
    // Analytic crossing: a slope selected to reach 35 C exactly at 120 s.
    const double slope=1/(ThermalObserver::tau_s*(-std::expm1(-120/ThermalObserver::tau_s)));
    assert(std::abs(*ThermalObserver::crossing(34,slope,35)-120)<1e-8);
    assert(std::abs(ThermalObserver::forecast(34,slope,120)-35)<1e-10);
    assert(!ThermalObserver::crossing(20,0,35));
    assert(!ThermalObserver::crossing(20,-0.01,35));
    assert(!ThermalObserver::crossing(20,0.001,35));
    assert(*ThermalObserver::crossing(35,0,35)==0);
    // Regular live input, observed linear history, independent future formula.
    nlohmann::json r; o.reset();
    for(int t=0;t<=600;++t) r=o.step(sample(t,28+0.01*t),t,c,false);
    assert(r["valid"] && r["samples"]==121 && !r["control_eligible"]);
    assert(std::abs(r["slope_c_min"].get<double>()-.6)<1e-10);
    assert(r["curve"][30]["temp_c"].get<double>()>34 && r["curve"][30]["temp_c"].get<double>()<37);
    assert(!r["t35_s"].is_null());
    // Repeated timestamp never manufactures history.
    ThermalObserver dup;
    for(int i=0;i<100;++i) r=dup.step(sample(0),.01*i,c,false);
    assert(r["samples"]==1 && !r["valid"]);
    // Any dropout discards the old history. Source changes, reverse time also reset.
    r=o.step(sample(600),603,c,false); assert(!r["valid"] && r["reason"]=="temperature_invalid");
    r=o.step(sample(604),604,c,false); assert(r["history_s"]==0);
    auto bad=sample(605); bad.temperature.value=std::numeric_limits<double>::quiet_NaN();
    assert(o.step(bad,605,c,false)["reason"]=="temperature_invalid");
    bad=sample(606);bad.temperature.source="DEMO";
    assert(o.step(bad,606,c,false)["reason"]=="temperature_invalid");
    assert(o.step(sample(1),1,c,false)["reason"]=="clock_invalid");
    assert(o.step(sample(2),2,c,true)["reason"]=="fan_active_or_feedback_unknown");
    r=o.step(sample(3),3,c,false);assert(r["history_s"]==0);
    // Both cabin and ambient are mandatory for the operational heat-balance forecast.
    ThermalObserver winter;
    for(int t=0;t<=600;++t) { auto s=sample(t,20);s.ambient.value=5;r=winter.step(s,t,c,false); }
    assert(r["valid"] && !r["scenario"]["valid"] && !r["ambient_in_study_range"]);
    assert(r["t35_s"].is_null());
    auto s=sample(601,20);s.ambient.valid=false;
    r=winter.step(s,601,c,false); assert(!r["valid"] && r["reason"]=="ambient_invalid");
    // Excessively rapid heating and abrupt steps are withheld, never called confident.
    ThermalObserver unstable;
    for(int t=0;t<=600;++t) r=unstable.step(sample(t,t<300?20:40),t,c,false);
    assert(!r["valid"] && r["reason"]=="trend_unstable");
    // Controller can stay in STANDBY although the observer estimates an early crossing.
    Core core(c); ThermalObserver parallel;
    for(int t=0;t<=600;++t) {
        auto a=sample(t,28+.01*t);a.uwb={true,1.,double(t),"REAL_UWB"};
        auto control=core.step(a,t);auto observed=parallel.step(a,t,c,false);
        assert(!control.demand_fan && !control.demand_buzzer);
        assert(!observed["control_eligible"]);
    }
    std::cout<<"PASS: analytic ETA, live regression, cold start, duplicates, stale/NaN/source/clock, fan, winter, unstable trend, control isolation\n";
}
