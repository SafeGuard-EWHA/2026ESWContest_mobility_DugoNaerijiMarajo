#include "thermal_observer.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace safeguard;
InputSnapshot sample(double t,double temp,double ambient=5) {
    InputSnapshot s;s.mode="REAL";s.temperature={true,temp,t,"REAL_ESP32"};
    s.ambient={true,ambient,t,"REAL_AMBIENT"};return s;
}
double heating(double t) { return 50+(34.5-50)*std::exp((600-t)/ThermalObserver::tau_s); }
int main(){
    Config c;c.ambient_timeout_s=3; ThermalObserver model;nlohmann::json r;
    for(int t=0;t<=600;++t)r=model.step(sample(t,heating(t)),t,c,false);
    assert(r["valid"] && r["ambient_used_in_adaptive_forecast"]);
    const double expected=-ThermalObserver::tau_s*std::log((50.-35)/(50.-34.5));
    assert(std::abs(r["t35_s"].get<double>()-expected)<1e-7 && expected<60);
    assert(r["model_fit_rmse_c"].get<double>()<1e-8);
    assert(std::abs(r["curve"][30]["temp_c"].get<double>()-(50+(34.5-50)*std::exp(-300/ThermalObserver::tau_s)))<1e-8);
    // Same measured cabin history, different newly received outside temperature.
    // Outside warming must shorten ETA, cooling can remove the crossing.
    auto hot=model, cold=model;
    auto warm=hot.step(sample(601,heating(601),15),601,c,false);
    auto cool=cold.step(sample(601,heating(601),-20),601,c,false);
    assert(warm["valid"] && warm["t35_s"].get<double>()<r["t35_s"].get<double>());
    assert(cool["valid"] && cool["t35_s"].is_null());
    auto stale=sample(601,heating(601));stale.ambient.timestamp_s=598;
    assert(model.step(stale,601,c,false)["reason"]=="ambient_invalid");
    assert(!model.step(sample(602,heating(602)),602,c,false)["valid"]);
    auto spoof=sample(603,30);spoof.ambient.source="DEMO";
    assert(model.step(spoof,603,c,false)["reason"]=="ambient_invalid");
    spoof=sample(604,30);spoof.temperature.value=std::numeric_limits<double>::quiet_NaN();
    assert(model.step(spoof,604,c,false)["reason"]=="temperature_invalid");
    assert(model.step(sample(605,30),605,c,true)["reason"]=="fan_active_or_feedback_unknown");
    assert(model.step(sample(1,30),1,c,false)["reason"]=="clock_invalid");
    ThermalObserver dup;for(int i=0;i<100;++i)r=dup.step(sample(0,25),i*.01,c,false);
    assert(r["samples"]==1 && !r["valid"]);
    ThermalObserver steady;for(int t=0;t<=600;++t)r=steady.step(sample(t,20,3),t,c,false);
    assert(r["valid"] && r["t35_s"].is_null());
    auto change=sample(601,20);change.mode="DEMO";change.ambient.source="DEMO";
    r=steady.step(change,601,c,false);assert(!r["valid"] && r["history_s"]==0);
    ThermalObserver unstable;for(int t=0;t<=600;++t)r=unstable.step(sample(t,t<300?20:40),t,c,false);
    assert(!r["valid"]);
    std::cout<<"PASS ambient heat balance: independent analytic forecast, ambient sensitivity, missing/stale/source/clock/fan guards, warmup and instability\n";
}
