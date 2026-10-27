#include "safeguard_uwb_input.hpp"
#include <cassert>
#include <iostream>

using nlohmann::json;
json frame(std::uint64_t seq, double rx = 100, std::string run = "run-A") {
    return {{"type","uwb"},{"schema_version",1},{"source","REAL_UWB"},{"peer_id","0CA7"},
            {"run_id",run},{"seq",seq},{"status","fresh"},{"valid",true},{"filter_ready",true},
            {"usable_for_fsm",true},{"sample_count",7},{"window",7},{"timeout_s",2.0},
            {"published_monotonic_s",rx},{"rx_monotonic_s",rx},{"age_ms",0.0},
            {"raw_distance_m",1.4},{"filtered_distance_m",1.5},{"distance_m",1.5}};
}
json waiting(std::string run, double now) {
    auto j = frame(1,now,run); j["status"]="waiting";
    for (const auto* key : {"valid","filter_ready","usable_for_fsm"}) j[key]=false;
    for (const auto* key : {"distance_m","raw_distance_m","filtered_distance_m","rx_monotonic_s","age_ms"}) j[key]=nullptr;
    j["sample_count"]=0; return j;
}
int main() {
    safeguard::UwbInput input("0CA7",2);
    input.ingest(frame(2).dump(),100.1); assert(input.state().ready);
    input.tick(101.999); assert(input.state().ready);
    input.tick(102.0); assert(!input.state().ready && !input.state().distance_m);
    input.ingest(frame(3,103).dump(),103); assert(input.state().ready);
    input.ingest(frame(3,103).dump(),103); assert(!input.state().ready); // Duplicate.
    input.ingest(frame(2,103).dump(),103); assert(!input.state().ready); // Reordered.
    input.ingest(frame(4,100).dump(),103); assert(!input.state().ready); // Queued old frame.
    auto stale_rx=frame(4,103); stale_rx["rx_monotonic_s"]=100;
    input.ingest(stale_rx.dump(),103); assert(!input.state().ready);
    input.ingest(frame(4,104).dump(),103); assert(!input.state().ready); // Future/different clock.
    auto warm=frame(4,103); warm["sample_count"]=1; warm["filter_ready"]=false;
    warm["usable_for_fsm"]=false; warm["distance_m"]=nullptr;
    input.ingest(warm.dump(),103); assert(!input.state().ready && input.state().reason=="warming_up");
    for (const auto& mutation : {json{{"peer_id","8809"}},json{{"source","SIMULATED"}},
         json{{"schema_version",2}},json{{"valid",1}},json{{"distance_m",-1}},
         json{{"distance_m","1.5"}},json{{"sample_count",6}},json{{"age_ms",2000}}}) {
        auto bad=frame(5,103); bad.update(mutation);
        input.ingest(bad.dump(),103); assert(!input.state().ready && !input.state().distance_m);
    }
    input.ingest("{broken",103); assert(!input.state().ready);
    auto null=frame(5,103); null["distance_m"]=nullptr;
    input.ingest(null.dump(),103); assert(!input.state().ready);
    input.ingest(frame(5,103).dump(),103); assert(input.state().ready);
    input.ingest(frame(1,103,"run-B").dump(),103); assert(!input.state().ready); // No restart marker.
    input.ingest(waiting("run-B",103).dump(),103); assert(!input.state().ready);
    input.ingest(frame(2,103,"run-B").dump(),103); assert(input.state().ready);
    input.ingest(waiting("run-A",103).dump(),103); assert(!input.state().ready); // Retired run.
    input.ingest(frame(3,103,"run-B").dump(),103); assert(input.state().ready);
    input.invalidate("eof"); assert(!input.state().ready && !input.state().distance_m);
    std::cout << "PASS: schema/types, peer, warm-up, independent timeout, late frames, ordering, restart, EOF.\n";
}
