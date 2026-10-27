#define main safeguard_main_entry
#include "../src/main.cpp"
#undef main
#include <cassert>
int main(){
 Json p={{"mode","REAL"},{"profile","REAL"},{"hardware",{{"esp32_protocol","link"}}},
 {"actuation",{{"enabled",true},{"servo_protect_deg",80}}},{"manual_control",{{"enabled",true}}}};
 HubProcess hub;ActuatorLink link(p,"predictive-test",hub);ManualControl manual(p,link);
 assert(manual.holding());
 link.controller_ready=true;manual.hold=false;
 // Same existing output route used for measured and predicted protection.
 link.update(true,true,600);
 assert(link.command["fan"]==true&&link.command["buzzer"]==true&&link.command["servo_deg"]==80);
 const auto id=link.id;InputStore store(p,safeguard::Config{});
 store.manual_stop_requested=true;store.manual_resume_requested=true;store.manual_resume_stop_nonce=manual.nonce;
 manual.tick(store,601);
 assert(manual.holding()&&!manual.resuming&&!link.pending);
 if(!manual.holding())link.update(true,true,601);
 assert(link.id==id);
 std::cout<<"PASS: existing output path fan+buzzer+servo80; STOP wins over simultaneous resume and blocks output update\n";
}
