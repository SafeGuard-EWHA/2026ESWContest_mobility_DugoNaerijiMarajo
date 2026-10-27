#include "thermal_observer.hpp"
#include <cassert>
#include <iostream>
#include <limits>
using namespace safeguard;
InputSnapshot sample(double t,double temp=34.5,double distance=6) {
 InputSnapshot s;s.mode="REAL";
 s.uwb={true,distance,t,"REAL_UWB"};s.temperature={true,temp,t,"REAL_ESP32"};
 s.ambient={true,3,t,"REAL_AMBIENT"};
 s.esp32={true,true,t,t,"REAL_ESP32"};s.estop={true,false,t,-1,"REAL_ESP32"};
 s.pir={true,false,t,-1,"REAL_ESP32"};s.camera={true,false,t,-1,"REAL_CAMERA"};
 s.mmwave={true,true,false,true,t,"presence","REAL_MMWAVE"};return s;
}
Config cfg(){Config c;c.predictive_control_enabled=true;c.departure_hold_s=.5;c.evidence_hold_s=.5;c.mmwave_observe_s=.5;return c;}
void ready(Core& c){c.step(sample(0,30,3),0);c.step(sample(.1),.1);c.step(sample(.7),.7);
 auto s=sample(.8);s.pir.value=true;c.step(s,.8);s=sample(.9);s.mmwave.evidence=true;c.step(s,.9);
 s=sample(1.5);s.mmwave.evidence=true;auto o=c.step(s,1.5);assert(o.state==State::THERMAL&&!o.demand_fan);}
int main(){
 auto c=cfg(); ThermalObserver observer;nlohmann::json r;
 for(int t=0;t<=600;++t) r=observer.step(sample(t,28.5+.01*t),t,c,false);
 assert(r["valid"] && r["t35_s"].get<double>()<60);
 LivePrediction p;p.timestamp_s=600;p.temperature_c=34.5;p.result.valid=true;
 p.result.t35_s=r["t35_s"].get<double>();p.result.reason="estimated_crossing";
 Core early(c);ready(early);auto s=sample(600);auto o=early.step(s,600,false,false,&p);
 assert(s.temperature.value<35&&o.state==State::PROTECTION&&o.demand_fan&&o.demand_buzzer);
 assert(o.reason=="predicted_temperature_at_risk");
 s=sample(601);s.temperature.valid=false;o=early.step(s,601);assert(o.demand_fan&&o.state==State::PROTECTION);
 s=sample(602);s.estop.value=true;o=early.step(s,602,false,false,&p);assert(o.state==State::ESTOP&&!o.demand_fan&&!o.demand_buzzer);
 for(int scenario=0;scenario<7;++scenario){Core blocked(c);ready(blocked);auto q=p;s=sample(600);
  if(scenario==0)q.result.t35_s=61;
  if(scenario==1)q.result.valid=false;
  if(scenario==2)q.timestamp_s=590;
  if(scenario==3)q.temperature_c=32;
  if(scenario==4)q.result.t35_s=std::numeric_limits<double>::quiet_NaN();
  if(scenario==5)q.result.t35_s=-1;
  if(scenario==6)s.temperature.valid=false;
  o=blocked.step(s,600,false,false,&q);assert(!o.demand_fan&&!o.demand_buzzer);
 }
 Core missing(c);ready(missing);assert(!missing.step(sample(600),600).demand_fan);
 Core hot(c);ready(hot);assert(hot.step(sample(600,35),600).demand_fan);
 Core near(c);o=near.step(sample(600,34.5,1),600,false,false,&p);assert(!o.demand_fan);
 auto disabled=c;disabled.predictive_control_enabled=false;Core off(disabled);ready(off);
 assert(!off.step(sample(600),600,false,false,&p).demand_fan);
 Core boundary(c);ready(boundary);p.result.t35_s=60;
 assert(boundary.step(sample(600),600,false,false,&p).demand_fan);
 std::cout<<"PASS: live 34.5C/51s -> protection, 60s boundary, >60 withheld, invalid/stale/mismatch/NaN rejected, hot fallback, near withheld, disabled withheld, latch and estop\n";
}
