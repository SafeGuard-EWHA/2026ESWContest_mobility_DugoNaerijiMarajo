// Exercise the production parser/link directly, without launching a sensor or MCU.
#define main safeguard_main_entry
#include "../src/main.cpp"
#undef main

namespace {
void check(bool condition, const char* expression, int line) {
    if (!condition) throw std::runtime_error("line " + std::to_string(line) + ": " + expression);
}
#define CHECK(expression) check(static_cast<bool>(expression), #expression, __LINE__)

Json project_config(const std::string& profile = "REAL", bool enabled = false,
                    bool override_temperature = false) {
    return {{"mode", profile == "REAL" ? "REAL" : "DEMO"}, {"profile", profile},
            {"hardware", {{"anchor_id", "0CA7"}}},
            {"demo", {{"override_temperature", override_temperature}}},
            {"actuation", {{"enabled", enabled}, {"ack_timeout_s", 0.5}, {"retry_limit", 1u}}}};
}

Json frame(const std::string& kind, const std::string& source, std::uint64_t seq,
           double time, const std::string& run = "run-A") {
    return {{"type", kind}, {"source", source}, {"schema_version", 1},
            {"run_id", run}, {"seq", seq}, {"rx_monotonic_s", time}};
}
Json camera(std::uint64_t seq, double time, bool positive = false,
            const std::string& run = "run-A", const std::string& source = "REAL_CAMERA") {
    auto j = frame("camera", source, seq, time, run);
    j["valid"] = true; j["motion"] = positive; return j;
}
Json telemetry(std::uint64_t seq, double time, bool positive = false,
               const std::string& run = "run-A", const std::string& source = "REAL_ESP32") {
    auto j = frame("telemetry", source, seq, time, run);
    j.update({{"pir_valid", true}, {"pir", positive}, {"temp_valid", true}, {"temp_c", 23.5},
              {"estop_valid", true}, {"estop", false}, {"uptime_ms", 1000}});
    return j;
}
Json ack(const ActuatorLink& link, unsigned id, double time, bool accepted,
         bool fan = false, bool buzzer = false, const std::string& origin = "REAL_ESP32") {
    return {{"type", "ack"}, {"schema_version", 1}, {"run_id", link.run}, {"id", id},
            {"source", origin}, {"rx_monotonic_s", time}, {"accepted", accepted},
            {"fan_cmd", fan}, {"buzzer_cmd", buzzer}, {"boot_id", "boot-A"}};
}

ControllerFeedback feedback(const ActuatorLink& link, double time, std::uint64_t seq=1,
                            bool fan=false, bool buzzer=false, const std::string& boot="boot-A") {
    return {true,fan,buzzer,false,true,false,time,boot,link.run,"hub-A",seq};
}

void test_sources_and_overrides() {
    safeguard::Config config;
    InputStore real(project_config(), config);
    real.ingest(camera(1,100,true,"run-A","DEMO"),100);
    CHECK(!real.data.camera.valid && real.last_error == "source_not_allowed_in_mode");
    real.ingest(camera(1,100,true,"run-A","REAL_ESP32"),100);
    CHECK(!real.data.camera.valid && real.last_error == "source_not_allowed_in_mode");
    real.ingest(camera(1,100,true),100);
    CHECK(real.data.camera.valid && real.data.camera.value && real.last_error.empty());

    InputStore hardware(project_config("HARDWARE_DEMO",false,true),config);
    for (const std::string kind : {"camera", "telemetry", "mmwave", "uwb"}) {
        hardware.ingest(frame(kind,"DEMO",1,100),100);
        CHECK(hardware.last_error == "source_not_allowed_in_mode");
    }
    auto temperature = frame("temperature","DEMO",1,100);
    temperature.update({{"valid",true},{"temp_c",34.0}});
    hardware.ingest(temperature,100);
    CHECK(hardware.data.temperature.valid && hardware.data.temperature.value == 34.0);
    hardware.ingest(telemetry(1,100),100);
    CHECK(hardware.measured.valid && hardware.measured.value == 23.5);
    CHECK(hardware.data.temperature.value == 34.0 && hardware.data.temperature.source == "DEMO");
    auto ambient = frame("ambient","DEMO",1,100);
    ambient.update({{"valid",true},{"temp_c",45.0}}); hardware.ingest(ambient,100);
    CHECK(hardware.data.ambient.valid && hardware.data.ambient.value == 45.0);
    InputStore no_override(project_config("HARDWARE_DEMO"),config);
    no_override.ingest(temperature,100);
    CHECK(!no_override.data.temperature.valid && no_override.last_error == "source_not_allowed_in_mode");
    real.ingest(temperature,100);
    CHECK(!real.data.temperature.valid && real.last_error == "source_not_allowed_in_mode");

    InputStore simulation(project_config("SIMULATION"),config);
    simulation.ingest(camera(1,100,true,"run-A","DEMO"),100);
    simulation.ingest(telemetry(1,100,true,"run-A","DEMO"),100);
    CHECK(simulation.data.camera.valid && simulation.data.pir.valid);
    CHECK(simulation.data.temperature.valid && !simulation.measured.valid);
}

void test_schema_clocks_and_replay() {
    safeguard::Config config;
    InputStore store(project_config(),config);
    store.ingest(camera(1,100,true),100);
    CHECK(store.data.camera.valid);
    store.ingest(camera(1,100.1,true),100.1);
    CHECK(!store.data.camera.valid && store.last_error == "duplicate_or_old_sensor_frame");
    store.ingest(camera(2,99.9,true),100.1);
    CHECK(!store.data.camera.valid && store.last_error == "sensor_rx_clock_regressed");
    store.ingest(camera(2,100.2,false),100.2);
    CHECK(store.data.camera.valid && !store.data.camera.value);
    store.ingest(camera(1,100.3,false,"run-B"),100.3);
    CHECK(store.data.camera.valid);
    store.ingest(camera(100,100.4,true,"run-A"),100.4);
    CHECK(!store.data.camera.valid && store.last_error == "retired_sensor_run");

    for (int variant=0;variant<7;++variant) {
        InputStore current(project_config(),config);
        auto j=camera(1,100,true);
        switch (variant) {
        case 0: j.erase("rx_monotonic_s"); break;
        case 1: j["rx_monotonic_s"]=98.0; break; // Exact TTL is expired.
        case 2: j["rx_monotonic_s"]=101.0; break;
        case 3: j["schema_version"]="1"; break;
        case 4: j["schema_version"]=2; break;
        case 5: j.erase("run_id"); break;
        case 6: j["seq"]=0u; break;
        }
        current.ingest(j,100);
        CHECK(!current.data.camera.valid && !current.last_error.empty());
    }
    for (const Json& bad_boolean : {Json("true"),Json(1),Json(nullptr)}) {
        InputStore current(project_config(),config);
        auto j=camera(1,100,true); j["valid"]=bad_boolean;
        current.ingest(j,100); CHECK(!current.data.camera.valid);
        j=camera(2,100.1,true); j["motion"]=bad_boolean;
        current.ingest(j,100.1); CHECK(!current.data.camera.valid);
    }
    InputStore missing(project_config(),config);
    auto j=telemetry(1,100,true); j.erase("pir"); j.erase("estop_valid"); j.erase("temp_valid");
    missing.ingest(j,100);
    CHECK(!missing.data.pir.valid && !missing.data.estop.valid && !missing.data.temperature.valid);
}

void test_positive_cache_invalidations() {
    safeguard::Config config; config.fusion_window_s=10; config.sensor_timeout_s=2;
    InputStore store(project_config(),config);
    store.ingest(camera(1,100,true),100);
    CHECK(store.data.camera.positive_timestamp_s == 100);
    store.ingest(camera(2,100.1,false,"run-A","REAL_ESP32"),100.1);
    store.ingest(camera(2,100.2,false),100.2);
    CHECK(store.data.camera.valid && store.data.camera.positive_timestamp_s < 0);
    store.ingest(telemetry(1,100,true),100);
    auto bad=telemetry(2,100.1,false); bad.erase("rx_monotonic_s");
    store.ingest(bad,100.1); store.ingest(telemetry(2,100.2,false),100.2);
    CHECK(store.data.pir.valid && store.data.pir.positive_timestamp_s < 0);

    InputStore restarted(project_config(),config);
    restarted.ingest(camera(1,100,true),100);
    restarted.ingest(camera(1,100.1,false,"run-B"),100.1);
    CHECK(restarted.data.camera.positive_timestamp_s < 0);
    restarted.ingest(telemetry(1,100,true),100);
    restarted.ingest(telemetry(1,100.1,false,"run-B"),100.1);
    CHECK(restarted.data.pir.positive_timestamp_s < 0);

    InputStore expired(project_config(),config);
    expired.ingest(camera(1,100,true),100); expired.ingest(telemetry(1,100,true),100);
    expired.refresh(102.01);
    CHECK(!expired.data.camera.valid && !expired.data.pir.valid);
    expired.ingest(camera(2,102.1,false),102.1); expired.ingest(telemetry(2,102.1,false),102.1);
    CHECK(expired.data.camera.positive_timestamp_s < 0 && expired.data.pir.positive_timestamp_s < 0);
}

void test_real_ack_and_dry_run() {
    HubProcess hub; // pid/input/control remain -1; no actual transport or process.
    ActuatorLink dry(project_config(),"main-dry",hub);
    dry.update(true,true,100);
    CHECK(!dry.pending && dry.status == "NOT_SENT_DRY_RUN" && dry.source == "NONE");
    dry.ack(ack(dry,dry.id,100,true,true,true),100);
    CHECK(dry.status == "NOT_SENT_DRY_RUN");
    dry.request_rearm(100.1);
    CHECK(dry.rearm_confirmed && !dry.rearm_pending && dry.rearm_status == "LOGICAL_REARM_DRY_RUN");

    ActuatorLink real(project_config("REAL",true),"main-real",hub);
    real.synchronize(feedback(real,99.9),99.9);
    real.update(true,true,100);
    real.ack(ack(real,real.id,100,true,true,true,"DEMO"),100);
    CHECK(real.pending && real.status != "SIMULATED_ACK");
    auto wrong_run=ack(real,real.id,100,true,true,true); wrong_run["run_id"]="old-main";
    real.ack(wrong_run,100); CHECK(real.pending);
    real.ack(ack(real,real.id,99,true,true,true),100); CHECK(real.pending);
    auto wrong_type=ack(real,real.id,100,true,true,true); wrong_type["accepted"]="true";
    real.ack(wrong_type,100); CHECK(real.pending);
    real.ack(ack(real,real.id,100,true,true,true),100);
    CHECK(!real.pending && real.status == "ACK_RECEIVED_NOT_PHYSICAL_FEEDBACK");
    CHECK(real.source == "REAL_ESP32");
}

void test_two_phase_rearm() {
    HubProcess hub;
    ActuatorLink link(project_config("REAL",true),"main-real",hub);
    link.synchronize(feedback(link,99.9),99.9);
    link.update(false,false,100);
    const unsigned old_command=link.id;
    link.request_rearm(100.1);
    CHECK(link.rearm_pending && !link.rearm_confirmed && !link.pending);
    const unsigned first_rearm=link.rearm_id;
    link.update(true,true,100.2);
    CHECK(link.id == first_rearm && !link.fan && !link.buzzer); // Commands wait for the ACK.
    link.ack(ack(link,old_command,100.2,true),100.2);
    link.ack(ack(link,first_rearm,100.2,true,false,false,"DEMO"),100.2);
    link.ack(ack(link,first_rearm,99.0,true),100.2);
    link.ack(ack(link,first_rearm,101.0,true),100.2);
    CHECK(link.rearm_pending && !link.rearm_confirmed);
    link.ack(ack(link,first_rearm,100.2,true),100.2);
    CHECK(!link.rearm_pending && link.rearm_confirmed && link.rearm_status == "REARM_ACK_RECEIVED");

    link.rearm_confirmed=false; link.request_rearm(101);
    const unsigned rejected_id=link.rearm_id;
    link.ack(ack(link,rejected_id,101,false),101);
    CHECK(!link.rearm_confirmed && !link.rearm_pending && link.rearm_status == "REARM_REJECTED_RETRY_MANUALLY");
    link.request_rearm(101.1);
    CHECK(link.rearm_id > rejected_id && link.rearm_pending);
    link.ack(ack(link,rejected_id,101.1,true),101.1);
    CHECK(link.rearm_pending && !link.rearm_confirmed);
    link.ack(ack(link,link.rearm_id,101.1,true,true,false),101.1);
    CHECK(!link.rearm_confirmed && link.rearm_status == "REARM_REJECTED_RETRY_MANUALLY");

    link.request_rearm(102);
    const unsigned timed_id=link.rearm_id;
    link.tick_rearm(102.51); CHECK(link.rearm_pending && link.rearm_id == timed_id);
    link.tick_rearm(103.02);
    CHECK(!link.rearm_pending && !link.rearm_confirmed && link.rearm_status == "REARM_ACK_TIMEOUT_RETRY_MANUALLY");
    link.request_rearm(103.1); CHECK(link.rearm_id > timed_id && link.rearm_pending);
    link.ack(ack(link,link.rearm_id,103.1,true),103.1);
    CHECK(link.rearm_confirmed && link.fault.empty());

    ActuatorLink simulation(project_config("SIMULATION"),"main-sim",hub);
    simulation.request_rearm(100);
    simulation.ack(ack(simulation,simulation.rearm_id,100,true),100);
    CHECK(simulation.rearm_pending && !simulation.rearm_confirmed);
    simulation.ack(ack(simulation,simulation.rearm_id,100,true,false,false,"DEMO"),100);
    CHECK(simulation.rearm_confirmed && !simulation.rearm_pending);
}
void test_controller_recovery() {
    HubProcess hub;
    ActuatorLink link(project_config("REAL",true),"main-real",hub);
    link.update(false,false,100);
    CHECK(!link.have && link.id == 0 && !link.pending); // No blind startup OFF.
    auto old=feedback(link,100,1,true,true); old.active_run="old-main";
    auto restore=link.synchronize(old,100);
    CHECK(restore.protection && !link.controller_ready && link.id == 0);
    link.update(false,false,100); CHECK(link.id == 0);
    auto active=feedback(link,103,2,true,true);
    restore=link.synchronize(active,103);
    CHECK(restore.protection && link.controller_ready);
    link.update(true,true,103);
    CHECK(link.pending && link.id == 1);
    auto old_ack=ack(link,link.id,103.1,true,true,true); old_ack["boot_id"]="old-boot";
    link.ack(old_ack,103.1); CHECK(link.pending);
    link.ack(ack(link,link.id,103.1,true,true,true),103.1);
    CHECK(!link.pending && link.ack_at == 103.1);
    link.synchronize(active,105.0);
    CHECK(!link.controller_ready && link.ack_at < 0 && link.source == "NONE");
    CHECK(link.status == "WAITING_CONTROLLER");
    auto rebooted=feedback(link,106,3,false,false,"boot-B");
    restore=link.synchronize(rebooted,106);
    CHECK(!restore.protection && link.controller_ready && !link.have);
    link.update(true,true,106); CHECK(link.pending && link.id == 2);
    auto reboot_ack=ack(link,link.id,106.1,true,true,true); reboot_ack["boot_id"]="boot-B";
    link.ack(reboot_ack,106.1); CHECK(!link.pending);
    // A real manual clear requests OFF. Pre-OFF telemetry must not restore protection.
    link.update(false,false,107);
    restore=link.synchronize(feedback(link,107.1,4,true,true,"boot-B"),107.1);
    CHECK(!restore.protection && link.pending);
    auto off_ack=ack(link,link.id,107.2,true); off_ack["boot_id"]="boot-B";
    link.ack(off_ack,107.2); CHECK(!link.pending);
    auto latched=feedback(link,108,5,false,false,"boot-B"); latched.estop_latched=true;
    restore=link.synchronize(latched,108); CHECK(restore.estop);
    link.request_rearm(108.1);
    auto rearm_ack=ack(link,link.rearm_id,108.2,true); rearm_ack["boot_id"]="boot-B";
    link.ack(rearm_ack,108.2); CHECK(link.rearm_confirmed);
    // A queued pre-ACK snapshot cannot re-latch the software after successful rearm.
    latched.seq=6; latched.timestamp_s=108.15;
    restore=link.synchronize(latched,108.3); CHECK(!restore.estop);
}

void test_board_boot_resets_positive_cache() {
    safeguard::Config config;
    InputStore store(project_config(),config);
    auto a=telemetry(1,100,true); a["boot_id"]="boot-A";
    store.ingest(a,100); CHECK(store.data.pir.positive_timestamp_s == 100);
    auto b=telemetry(2,100.1,false); b["boot_id"]="boot-B"; b["uptime_ms"]=10;
    store.ingest(b,100.1); CHECK(store.data.pir.positive_timestamp_s < 0);
    b=telemetry(3,100.2,true); b["boot_id"]="boot-B"; b["uptime_ms"]=20;
    store.ingest(b,100.2); CHECK(store.data.pir.positive_timestamp_s == 100.2);
    b=telemetry(4,100.3,false); b["boot_id"]="boot-B"; b["uptime_ms"]=1;
    store.ingest(b,100.3);
    CHECK(!store.data.pir.valid && store.data.pir.positive_timestamp_s < 0);
    CHECK(store.last_error == "board_uptime_regressed");
}

}

int main() {
    try {
        test_sources_and_overrides(); test_schema_clocks_and_replay();
        test_positive_cache_invalidations(); test_real_ack_and_dry_run(); test_two_phase_rearm();
        test_controller_recovery(); test_board_boot_resets_positive_cache();
        std::cout << "PASS: input sources/schema/clocks/replay/positive-cache and real/dry-run/two-phase rearm ACKs\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
