// Host-only protocol/FSM test. No UART, camera, network or actuator opened.
#define main safeguard_main_entry
#include "../patch/src/main.cpp"
#undef main
#include <cassert>
using namespace safeguard;
InputSnapshot input(double t, std::uint64_t epoch=1) {
 InputSnapshot s;s.mode="REAL";s.uwb={true,6,t,"REAL"};
 s.pir=s.camera=s.estop={true,false,t,-1,"REAL"};
 s.esp32={true,true,t,t,"REAL"};s.temperature={true,25,t,"REAL"};
 s.mmwave={true,true,false,true,t,"presence","REAL","ok"};
 s.mmwave.continuity_run="hub";s.mmwave.continuity_epoch=epoch;return s;
}
void start(Core& core) {
 auto s=input(0);s.uwb.distance_m=3;assert(core.step(s,0).state==State::STANDBY);
 assert(core.step(input(.1),.1).state==State::DEPARTURE_CHECK);
 assert(core.step(input(.7),.7).state==State::PRIMARY);
 s=input(.8);s.pir.value=true;assert(core.step(s,.8).state==State::MMWAVE);
}
int main() {
 Config cfg;cfg.departure_hold_s=.5;cfg.mmwave_observe_s=5;
 Core core(cfg);start(core);
 for(int i=9;i<=48;++i)assert(core.step(input(i*.1),i*.1).state==State::MMWAVE);
 // A brief positive/error occurred between polls; final frame is negative again.
 assert(core.step(input(4.9,3),4.9).state==State::MMWAVE);
 for(int i=50;i<=98;++i)assert(core.step(input(i*.1,3),i*.1).state==State::MMWAVE);
 assert(core.step(input(10,3),10).state==State::PRIMARY);
 Core positive(cfg);start(positive);
 auto s=input(.9);s.mmwave.evidence=true;positive.step(s,.9);
 s=input(1.3,3);s.mmwave.evidence=true;
 assert(positive.step(s,1.3).occupant!=Occupant::CONFIRMED);
 s=input(1.5,3);s.mmwave.evidence=true;
 assert(positive.step(s,1.5).occupant!=Occupant::CONFIRMED);
 s=input(1.9,3);s.mmwave.evidence=true;
 assert(positive.step(s,1.9).occupant==Occupant::CONFIRMED);
 auto project=Json{{"mode","REAL"},{"profile","REAL"},{"hardware",{{"anchor_id","0CA7"}}}};
 InputStore store(project,cfg);
 auto j=Json{{"type","mmwave"},{"source","REAL_MMWAVE"},{"schema_version",1},
 {"run_id","hub"},{"seq",1u},{"rx_monotonic_s",20.0},{"valid",true},
 {"health","ok"},{"evidence",false},{"validated",true},{"evidence_kind","presence"},
 {"adapter_version",1},{"continuity_epoch",3u}};
 store.ingest(j,20.0);assert(store.data.mmwave.valid);assert(store.data.mmwave.continuity_epoch==3);
 j["seq"]=2u;j.erase("continuity_epoch");store.ingest(j,20.0);assert(!store.data.mmwave.valid);
 j["seq"]=3u;j["continuity_epoch"]=4u;store.ingest(j,20.0);assert(store.data.mmwave.valid);
 assert(store.data.mmwave.continuity_epoch==4);assert(store.data.mmwave.continuity_run=="hub");
 std::cout<<"PASS: 5s uninterrupted negatives; hidden transition resets both holds; native continuity required.\n";
}
