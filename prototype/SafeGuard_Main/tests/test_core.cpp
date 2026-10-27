#include "../src/core.hpp"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
using namespace safeguard;

Config fast() {
    Config c; c.departure_hold_s = c.return_hold_s = c.evidence_hold_s = c.mmwave_observe_s = 0.5;
    c.init_timeout_s = 1; return c;
}
InputSnapshot sample(double time, double distance = 6, const std::string& mode = "DEMO") {
    InputSnapshot s; s.mode = mode;
    const auto source = mode == "DEMO" ? "DEMO" : "REAL";
    s.uwb = {true,distance,time,source};
    s.pir = s.camera = s.estop = {true,false,time,-1,source};
    s.esp32 = {true,true,time,time,source};
    s.mmwave = {true,true,false,true,time,"presence",source};
    s.temperature = {true,25,time,source}; s.ambient = {true,30,time,source};
    return s;
}
void primary(Core& c, const std::string& mode = "DEMO") {
    assert(c.step(sample(0,3,mode),0).state == State::STANDBY);
    assert(c.step(sample(0.1,6,mode),0.1).state == State::DEPARTURE_CHECK);
    assert(c.step(sample(0.7,6,mode),0.7).state == State::PRIMARY);
}
CoreOutput thermal(Core& c, double temp = 25, const std::string& mode = "DEMO") {
    primary(c,mode);
    auto s = sample(0.8,6,mode); s.pir.value=true;
    assert(c.step(s,0.8).state == State::MMWAVE);
    s = sample(0.9,6,mode); s.mmwave.evidence=true; s.temperature.value=temp;
    assert(c.step(s,0.9).state == State::MMWAVE);
    s = sample(1.5,6,mode); s.mmwave.evidence=true; s.temperature.value=temp;
    return c.step(s,1.5);
}

int main() {
    auto has_fault = [](const CoreOutput& o, const std::string& name) {
        return std::find(o.faults.begin(),o.faults.end(),name)!=o.faults.end();
    };
    // Close the loop through processing flags as the hub does: required camera
    // and radar must be enabled in INIT and while recovering an INIT fault.
    for (int mask=1;mask<4;++mask) {
        auto config=fast();config.require_camera=mask&1;config.require_mmwave=mask&2;
        Core c(config);CoreOutput prior;
        for (int i=0;i<3;++i) {
            auto s=sample(i*.25,3);s.camera.valid=prior.camera_processing;
            s.mmwave.valid=s.mmwave.healthy=prior.mmwave_processing;
            prior=c.step(s,i*.25);
            if(i==0){
                assert(prior.state==State::INIT);
                assert(prior.camera_processing==config.require_camera);
                assert(prior.mmwave_processing==config.require_mmwave);
            }
        }
        assert(prior.state==State::STANDBY);
        Core late(config);prior={};
        for(int i=0;i<8;++i){
            const double t=i*.5;auto s=sample(t,3);
            const bool recovered=t>=3;
            s.camera.valid=recovered&&prior.camera_processing;
            s.mmwave.valid=s.mmwave.healthy=recovered&&prior.mmwave_processing;
            prior=late.step(s,t);
            if(t==2){
                assert(prior.state==State::FAULT);
                assert(prior.camera_processing==config.require_camera);
                assert(prior.mmwave_processing==config.require_mmwave);
                assert(has_fault(prior,"CAMERA_UNAVAILABLE")==config.require_camera);
                assert(has_fault(prior,"MMWAVE_UNAVAILABLE")==config.require_mmwave);
            }
        }
        assert(prior.state==State::STANDBY);
    }
    // A healthy staged flow intentionally disables unused detectors. Missing
    // samples from those disabled workers must not be reported as device faults.
    {
        Core c(fast());CoreOutput prior;
        for(int i=0;i<12;++i){
            const double t=i*.5;auto s=sample(t);
            s.pir.value=true;s.camera.valid=prior.camera_processing;s.camera.value=true;
            s.mmwave.valid=s.mmwave.healthy=prior.mmwave_processing;
            s.mmwave.evidence=prior.mmwave_processing;s.mmwave.health=prior.mmwave_processing?"ok":"unknown";
            s.temperature.value=36;
            prior=c.step(s,t);
            assert(!has_fault(prior,"CAMERA_UNAVAILABLE"));
            assert(!has_fault(prior,"MMWAVE_UNAVAILABLE"));
        }
        assert(prior.state==State::PROTECTION && prior.demand_fan);
        assert(!prior.camera_processing && !prior.mmwave_processing);
        Core missing(fast());primary(missing);auto s=sample(.8);s.camera.valid=false;
        auto o=missing.step(s,.8);assert(o.state==State::PRIMARY&&!has_fault(o,"CAMERA_UNAVAILABLE"));
        s=sample(2.8);s.camera.valid=false;o=missing.step(s,2.8);
        assert(o.state==State::PRIMARY&&has_fault(o,"CAMERA_UNAVAILABLE"));
        assert(!has_fault(o,"MMWAVE_UNAVAILABLE"));
    }
    // MCU feedback survives a main-process restart. Restoring outputs does not
    // invent occupant confirmation and still requires stable return + manual
    // clear; a brief, already-released ESTOP remains latched until manual rearm.
    {
        Core c(fast());c.restore_controller_latches(true,false);
        auto o=c.step(sample(0,3),0);
        assert(o.state==State::PROTECTION&&o.demand_fan&&o.occupant==Occupant::UNKNOWN);
        c.restore_controller_latches(false,false);
        assert(c.step(sample(.3,3),.3,true).demand_fan);
        // Repeated positive feedback must not reset the stable-return timer.
        c.restore_controller_latches(true,false);
        o=c.step(sample(.6,3),.6,true);assert(o.state==State::STANDBY&&!o.demand_fan);
        Core stopped(fast());stopped.restore_controller_latches(true,true);
        o=stopped.step(sample(0,3),0);
        assert(o.state==State::ESTOP&&!o.demand_fan);
        stopped.restore_controller_latches(false,false);
        assert(stopped.step(sample(.5,3),.5).state==State::ESTOP);
        o=stopped.step(sample(.6,3),.6,false,true);
        assert(o.state==State::INIT&&!o.demand_fan);
    }
    // Report's normal OR and fault AND truth tables.
    for (int mask=0;mask<4;++mask) {
        Core c(fast()); primary(c);
        auto s=sample(0.8); s.pir.value=mask&1; s.camera.value=mask&2;
        const auto o=c.step(s,0.8);
        assert(o.state==(mask ? State::MMWAVE : State::PRIMARY));
    }
    for (int mask=0;mask<4;++mask) {
        Core c(fast()); primary(c);
        auto s=sample(0.8); s.pir.value=true; c.step(s,0.8);
        s=sample(0.9); s.mmwave.valid=false; s.mmwave.health="fault";
        assert(c.step(s,0.9).state==State::FAIL_SAFE);
        s=sample(1.0); s.mmwave.valid=false; s.pir.value=mask&1; s.camera.value=mask&2;
        const auto o=c.step(s,1.0);
        assert(o.occupant==(mask==3 ? Occupant::SUSPECTED : Occupant::UNKNOWN));
        assert(o.state==(mask==3 ? State::THERMAL : State::FAIL_SAFE));
    }
    // A recovered radar plus fresh primary OR re-enters verification, never instant confirmation.
    {
        Core c(fast()); primary(c); auto s=sample(0.8);s.pir.value=true;c.step(s,0.8);
        s=sample(0.9);s.mmwave.valid=false;s.mmwave.health="fault";
        assert(c.step(s,0.9).state==State::FAIL_SAFE);
        s=sample(1.0);s.pir.value=true;s.mmwave.evidence=true;
        auto o=c.step(s,1.0);assert(o.state==State::MMWAVE && o.occupant==Occupant::UNKNOWN);
        s=sample(1.1);s.mmwave.evidence=true;assert(c.step(s,1.1).state==State::MMWAVE);
        s=sample(1.7);s.mmwave.evidence=true;assert(c.step(s,1.7).occupant==Occupant::CONFIRMED);
    }
    // Strict >5m, uninterrupted holds, stale never means guardian returned.
    {
        Core c(fast()); assert(c.step(sample(0,5),0).state==State::STANDBY);
        assert(c.step(sample(0.1,5),0.1).state==State::STANDBY);
        assert(c.step(sample(0.2,5.01),0.2).state==State::DEPARTURE_CHECK);
        auto lost=sample(0.4); lost.uwb.ready=false;
        auto o=c.step(lost,0.4); assert(o.state==State::STANDBY && o.guardian==Guardian::UNKNOWN);
        c.step(sample(0.5),0.5);
        assert(c.step(sample(0.8),0.8).state==State::DEPARTURE_CHECK);
        assert(c.step(sample(1.1),1.1).state==State::PRIMARY);
        o=c.step(lost,1.2); assert(o.guardian==Guardian::UNKNOWN && o.occupant==Occupant::UNKNOWN);
    }
    // A stale positive or an invalid sensor cannot satisfy AND; no OR-negative radar timer.
    {
        Core c(fast()); primary(c);
        assert(c.step(sample(10),10).state==State::PRIMARY);
        auto s=sample(10.1); s.pir.value=true; c.step(s,10.1);
        s=sample(10.2); s.mmwave.valid=false; s.mmwave.health="fault"; c.step(s,10.2);
        s=sample(12.2); s.mmwave.valid=false; s.pir.value=s.camera.value=true;
        s.pir.timestamp_s=s.camera.timestamp_s=10.2;
        auto o=c.step(s,12.2); assert(o.state==State::FAIL_SAFE && o.occupant==Occupant::UNKNOWN);
        s=sample(12.3); s.pir.value=s.camera.value=true; s.camera.valid=false;
        assert(c.step(s,12.3).occupant==Occupant::UNKNOWN);
        Core hot_without_evidence(fast()); primary(hot_without_evidence);
        s=sample(1); s.temperature.value=40;
        const auto h=hot_without_evidence.step(s,1);
        assert(h.state==State::PRIMARY && !h.demand_fan);
    }
    // Reusing one radar frame does not meet evidence hold. Healthy empty != fault.
    {
        Core c(fast()); primary(c); auto s=sample(0.8); s.pir.value=true; c.step(s,0.8);
        s=sample(0.9); s.mmwave.evidence=true; c.step(s,0.9);
        assert(c.step(s,1.5).state==State::MMWAVE);
        s=sample(1.6); s.mmwave.evidence=true;
        assert(c.step(s,1.6).occupant==Occupant::CONFIRMED);
        Core empty(fast()); primary(empty); s=sample(0.8); s.pir.value=true; empty.step(s,0.8);
        empty.step(sample(0.9),0.9);
        assert(empty.step(sample(1.5),1.5).state==State::PRIMARY);
        Core timeout(fast()); primary(timeout); s=sample(0.8); s.pir.value=true; timeout.step(s,0.8);
        s=sample(0.9); s.mmwave.evidence=true; timeout.step(s,0.9);
        assert(timeout.step(s,3.0).state==State::FAIL_SAFE);
    }
    // The last disabled/unknown frame is not a new hardware fault when processing starts.
    {
        Core c(fast()); primary(c); auto s=sample(0.8);s.pir.value=true;
        s.mmwave.valid=false;s.mmwave.healthy=false;s.mmwave.timestamp_s=0.7;
        assert(c.step(s,0.8).state==State::MMWAVE);
        assert(c.step(s,0.9).state==State::MMWAVE);
        s=sample(1.0);s.mmwave.evidence=true;
        assert(c.step(s,1.0).state==State::MMWAVE);
        s=sample(1.6);s.mmwave.evidence=true;
        assert(c.step(s,1.6).occupant==Occupant::CONFIRMED);
        Core missing(fast());primary(missing);s=sample(0.8);s.pir.value=true;
        s.mmwave.valid=false;s.mmwave.healthy=false;s.mmwave.timestamp_s=0.7;
        missing.step(s,0.8);
        assert(missing.step(s,2.81).state==State::FAIL_SAFE);
    }
    // REAL requires validated presence/micro-motion evidence, not point-count/serial traffic.
    for (const bool arbitrary_points : {false,true}) {
        Core c(fast()); primary(c,"REAL"); auto s=sample(0.8,6,"REAL"); s.pir.value=true; c.step(s,0.8);
        s=sample(0.9,6,"REAL"); s.mmwave.evidence=true;
        s.mmwave.validated=arbitrary_points; if(arbitrary_points)s.mmwave.evidence_kind="point_cloud";
        assert(c.step(s,0.9).state==State::FAIL_SAFE);
        s.pir.value=s.camera.value=true; s.pir.timestamp_s=s.camera.timestamp_s=s.mmwave.timestamp_s=1.0;
        auto o=c.step(s,1.0);
        assert(o.state==State::THERMAL && o.occupant==Occupant::SUSPECTED);
    }
    {
        Core demo(fast()); primary(demo); auto s=sample(0.8);s.pir.value=true;demo.step(s,0.8);
        s=sample(0.9);s.mmwave.evidence=true;s.mmwave.validated=false;s.mmwave.evidence_kind="demo";
        demo.step(s,0.9);s.mmwave.timestamp_s=1.5;
        assert(demo.step(s,1.5).occupant==Occupant::CONFIRMED);
    }
    // Measured hot input bypasses disabled/invalid model; protection survives all dropout.
    {
        Config config=fast(); config.thermal_enabled=true; config.thermal_R=0;
        Core c(config); auto o=thermal(c,35);
        assert(o.state==State::PROTECTION && o.demand_fan && o.demand_buzzer && !o.thermal.valid);
        InputSnapshot missing; o=c.step(missing,5);
        assert(o.state==State::PROTECTION && o.demand_fan && o.guardian==Guardian::UNKNOWN);
        assert(c.step(missing,5.1,true).demand_fan);
        c.step(sample(5.2,4),5.2); o=c.step(sample(5.8,4),5.8);
        assert(o.state==State::PROTECTION && o.guardian==Guardian::NEAR);
        o=c.step(sample(5.9,4),5.9,true); assert(o.state==State::STANDBY && !o.demand_fan);
    }
    // ESTOP takes precedence and requires release plus manual rearm; no immediate restart.
    {
        Core c(fast()); thermal(c,36); auto s=sample(2); s.estop.value=true;
        auto o=c.step(s,2); assert(o.state==State::ESTOP && !o.demand_fan && !o.demand_buzzer);
        o=c.step(s,1.9); assert(o.state==State::ESTOP && !o.demand_fan);
        s=sample(2.1); assert(c.step(s,2.1).state==State::ESTOP);
        s.estop.valid=false; assert(c.step(s,2.2,false,true).state==State::ESTOP);
        s=sample(2.3); o=c.step(s,2.3,false,true); assert(o.state==State::INIT && !o.demand_fan);
        assert(c.step(sample(2.4),2.4).state==State::STANDBY);
        Core clock_fault(fast()); thermal(clock_fault,36);
        s=sample(1.5);s.estop.value=true;
        o=clock_fault.step(s,1.4);
        assert(o.state==State::ESTOP && !o.demand_fan && !o.demand_buzzer);
    }
    // Euler hand calculation: 25 + 1/1000*((30-25)/.2 + 80) = 25.105.
    {
        Config config=fast(); config.thermal_enabled=true;
        Core c(config); auto o=thermal(c);
        assert(o.thermal.valid && o.thermal.curve.size()==301);
        assert(std::abs(o.thermal.curve[1].second-25.105)<1e-10);
        assert(o.thermal.t35_s && *o.thermal.t35_s>0);
        auto s=sample(1.6); s.ambient.timestamp_s=-1;
        o=c.step(s,1.6); assert(o.state==State::THERMAL && !o.thermal.valid && !o.demand_fan);
        s=sample(1.7); s.ambient.valid=false; s.temperature.value=35;
        assert(c.step(s,1.7).state==State::PROTECTION);
        Core real(config); o=thermal(real,25,"REAL");
        assert(!o.thermal.valid && o.thermal.reason=="uncalibrated_real_model");
        config.dt_s=201; Core unstable(config); o=thermal(unstable);
        assert(!o.thermal.valid && o.thermal.reason=="invalid_model_parameters");
        config.dt_s=1; Core early(config); o=thermal(early,34);
        assert(o.state==State::PROTECTION && o.thermal.valid && o.thermal.t35_s && *o.thermal.t35_s<=60);
    }
    // Current-temperature loss is FAULT, recovery re-evaluates instead of inventing a value.
    {
        Core c(fast()); thermal(c); auto s=sample(1.6); s.temperature.valid=false;
        assert(c.step(s,1.6).state==State::FAULT);
        s=sample(1.7); assert(c.step(s,1.7).state==State::THERMAL);
    }
    {
        auto config=Config::from_json({{"fsm",{{"departure_hold_s",1}}},{"required",{{"esp32",true}}},
                                      {"thermal",{{"enabled",true},{"R_K_per_W",0.2}}}});
        assert(config.departure_hold_s==1 && config.require_esp32 && config.thermal_enabled);
        Core c(config); auto s=sample(0); s.esp32.valid=false;
        assert(c.step(s,0).state==State::INIT); s=sample(6);s.esp32.valid=false;
        assert(c.step(s,6).state==State::FAULT);
        auto j=to_json(c.step(sample(6.1),6.1)); assert(j.at("state")=="INIT" && j.at("thermal").at("t35_s").is_null());
    }
    std::cout << "PASS: OR/AND, freshness/holds, validated presence, healthy-empty/fault, thermal Euler, protection latch, ESTOP/rearm, config.\n";
}
