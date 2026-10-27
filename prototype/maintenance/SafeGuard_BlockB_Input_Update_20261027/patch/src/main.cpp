#include "core.hpp"
#include "uwb_input.hpp"
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <poll.h>
#include <sstream>
#include <stdexcept>
#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>

using Json = nlohmann::json;
namespace fs = std::filesystem;
namespace {
constexpr const char* VERSION = "0.2.0-software-stop";
volatile std::sig_atomic_t stopping = 0;
void on_signal(int) { stopping = 1; }
double mono() {
    timespec t{};
    if (clock_gettime(CLOCK_MONOTONIC, &t)) throw std::runtime_error("monotonic clock failed");
    return t.tv_sec + t.tv_nsec / 1e9;
}
std::string utc_id() {
    const auto now = std::chrono::system_clock::now();
    const auto sec = std::chrono::system_clock::to_time_t(now);
    std::tm tm{}; gmtime_r(&sec, &tm);
    std::ostringstream out;
    out << std::put_time(&tm, "%Y%m%dT%H%M%S") << '_'
        << std::setw(6) << std::setfill('0')
        << std::chrono::duration_cast<std::chrono::microseconds>(now.time_since_epoch()).count() % 1000000 << 'Z';
    return out.str();
}
bool truth(const Json& j, const char* key) {
    return j.contains(key) && j[key].is_boolean() && j[key].get<bool>();
}
bool is_number(const Json& j, const char* key) {
    return j.contains(key) && j[key].is_number() && std::isfinite(j[key].get<double>());
}
std::string string_field(const Json& j, const char* key, const std::string& fallback = "") {
    return j.contains(key) && j[key].is_string() ? j[key].get<std::string>() : fallback;
}
Json nullable(bool valid, double value) { return valid && std::isfinite(value) ? Json(value) : Json(nullptr); }

struct HubProcess {
    pid_t pid = -1;
    int input = -1, control = -1;
    void launch(const fs::path& config, const fs::path& state) {
        int up[2], down[2];
        if (pipe(up) || pipe(down)) throw std::runtime_error("cannot create hub pipes");
        pid = fork();
        if (pid < 0) throw std::runtime_error("cannot start hub");
        if (pid == 0) {
            dup2(down[0], STDIN_FILENO); dup2(up[1], STDOUT_FILENO);
            close(up[0]); close(up[1]); close(down[0]); close(down[1]);
            execlp("python3", "python3", "scripts/sensor_hub.py", "--config", config.c_str(),
                   "--state-file", state.c_str(), static_cast<char*>(nullptr));
            _exit(127);
        }
        close(up[1]); close(down[0]); input = up[0]; control = down[1];
        fcntl(control, F_SETFL, fcntl(control, F_GETFL) | O_NONBLOCK);
    }
    bool send(const Json& j) {
        if (control < 0) return false;
        const std::string line = j.dump() + '\n';
        // Every control message is smaller than PIPE_BUF, so nonblocking writes are atomic.
        return line.size() < 4096 && write(control, line.data(), line.size()) == static_cast<ssize_t>(line.size());
    }
    ~HubProcess() {
        if (control >= 0) close(control);
        if (input >= 0) close(input);
        if (pid > 0) {
            kill(pid, SIGTERM);
            for (int i = 0; i < 40; ++i) {
                if (waitpid(pid, nullptr, WNOHANG) == pid) return;
                usleep(50000);
            }
            kill(pid, SIGKILL); waitpid(pid, nullptr, 0);
        }
    }
};

struct ControllerFeedback {
    bool valid = false, fan = false, buzzer = false, estop_latched = false;
    bool actuators_enabled = false, heartbeat_fault = true;
    double timestamp_s = -1;
    std::string boot_id, active_run, producer_run;
    std::uint64_t seq = 0;
    bool software_valid = false, software_latched = true, servo_ready = false;
    int servo = -1;
    unsigned stop_generation = 0;
    std::string stop_nonce;
};
struct ControllerRestore { bool protection = false, estop = false; };

struct InputStore {
    safeguard::InputSnapshot data;
    safeguard::ScalarSample measured;
    ControllerFeedback controller;
    std::string board_boot;
    std::optional<std::uint64_t> board_uptime;
    safeguard::UwbInput uwb;
    safeguard::Config config;
    std::string mode, profile, last_error;
    bool override_temp = false;
    bool clear_requested = false, rearm_requested = false;
    bool manual_stop_requested = false, manual_resume_requested = false;
    std::string manual_resume_stop_nonce;
    std::string operator_run;
    std::uint64_t operator_seq = 0;
    std::map<std::string, std::pair<std::string, std::uint64_t>> ordering;
    std::map<std::string,std::set<std::string>> retired_runs;
    std::map<std::string,double> last_rx;
    explicit InputStore(const Json& project, const safeguard::Config& c)
        : uwb(project.at("hardware").value("anchor_id", "0CA7"), c.uwb_timeout_s), config(c),
          mode(project.value("mode", "REAL")), profile(project.value("profile", "REAL")),
          override_temp(mode == "DEMO" && project.at("demo").value("override_temperature", false)) {
        data.mode = mode;
    }
    bool fresh(double t, double now, double timeout) const {
        return t >= 0 && t <= now + 0.001 && now - t < timeout;
    }
    bool source_allowed(const std::string& kind, const std::string& source) const {
        const std::map<std::string,std::string> actual = {{"uwb","REAL_UWB"},{"telemetry","REAL_ESP32"},
            {"camera","REAL_CAMERA"},{"mmwave","REAL_MMWAVE"},{"ambient","REAL_AMBIENT"}};
        const auto found = actual.find(kind);
        if (found != actual.end() && source == found->second) return true;
        if (mode != "DEMO" || source != "DEMO") return false;
        if (profile == "SIMULATION") return true;
        return profile == "HARDWARE_DEMO" && override_temp && (kind == "temperature" || kind == "ambient");
    }
    void invalidate_kind(const std::string& kind) {
        if (kind == "uwb") { uwb.invalidate("protocol_error"); data.uwb.ready = false; data.uwb.distance_m.reset(); }
        else if (kind == "camera") { data.camera.valid = false; data.camera.positive_timestamp_s=-1; }
        else if (kind == "mmwave") data.mmwave.valid = false;
        else if (kind == "ambient") data.ambient.valid = false;
        else if (kind == "temperature") data.temperature.valid = false;
        else if (kind == "telemetry") {
            data.pir.valid = data.esp32.valid = data.estop.valid = measured.valid = controller.valid = false;
            data.pir.positive_timestamp_s=data.estop.positive_timestamp_s=-1;
            if (!override_temp) data.temperature.valid = false;
        }
    }
    void binary(safeguard::BinarySample& s, bool valid, bool value, double t, const std::string& source) {
        if (!valid) s.positive_timestamp_s = -1;
        else if (value) s.positive_timestamp_s = t;
        s.valid = valid; s.value = value; s.timestamp_s = t; s.source = source;
    }
    void refresh(double now) {
        for (auto* sample : {&data.pir,&data.camera,&data.estop,&data.esp32}) {
            if (!fresh(sample->timestamp_s,now,config.sensor_timeout_s)) {
                sample->valid=false; sample->positive_timestamp_s=-1;
            }
        }
        uwb.tick(now);
        const auto& s = uwb.state();
        data.uwb.ready = s.ready; data.uwb.distance_m = s.distance_m;
        data.uwb.timestamp_s = s.ready ? s.rx_monotonic_s : -1;
    }
    void ingest(const Json& j, double now) {
        const auto kind = string_field(j, "type");
        try {
            if (kind == "operator") {
                if (string_field(j,"source") != "LOCAL_OPERATOR" || !is_number(j,"rx_monotonic_s") ||
                    !fresh(j["rx_monotonic_s"].get<double>(),now,2.0) ||
                    !j.contains("schema_version") || j["schema_version"] != 1)
                    throw std::runtime_error("invalid_local_operator_envelope");
                const auto action = string_field(j, "action");
                if (action == "manual_stop" || action == "manual_resume") {
                    const auto run = string_field(j, "run_id");
                    if (run.empty() || !j.contains("seq") || !j["seq"].is_number_unsigned() ||
                        (run == operator_run && j["seq"].get<std::uint64_t>() <= operator_seq))
                        throw std::runtime_error("invalid_operator_sequence");
                    operator_run = run; operator_seq = j["seq"].get<std::uint64_t>();
                    if (action == "manual_stop") manual_stop_requested = true;
                    else {
                        manual_resume_requested = true;
                        manual_resume_stop_nonce = string_field(j,"stop_request_id");
                    }
                }
                else if (action == "clear") clear_requested = true;
                else if (action == "rearm") rearm_requested = true;
                else throw std::runtime_error("unknown_operator_action");
                return;
            }
            if (kind == "ack") return;
            const auto source = string_field(j, "source");
            if (!source_allowed(kind,source)) throw std::runtime_error("source_not_allowed_in_mode");
            if (kind == "uwb") {
                Json normalized = j;
                if (source == "DEMO" && mode == "DEMO") normalized["source"] = "REAL_UWB";
                uwb.ingest(normalized.dump(), now); data.uwb.source = source; refresh(now); return;
            }
            if (!j.contains("schema_version") || !j["schema_version"].is_number_integer() || j["schema_version"] != 1)
                throw std::runtime_error("bad_sensor_schema");
            const auto run = string_field(j, "run_id");
            if (run.empty() || !j.contains("seq") || !j["seq"].is_number_unsigned())
                throw std::runtime_error("missing_sensor_sequence");
            const auto seq = j["seq"].get<std::uint64_t>();
            auto& previous = ordering[kind];
            if (seq == 0 || (previous.first == run && seq <= previous.second))
                throw std::runtime_error("duplicate_or_old_sensor_frame");
            if (previous.first != run && retired_runs[kind].count(run))
                throw std::runtime_error("retired_sensor_run");
            if (!is_number(j, "rx_monotonic_s")) throw std::runtime_error("missing_rx_clock");
            const double t = j["rx_monotonic_s"].get<double>();
            const double timeout = kind == "ambient" ? config.ambient_timeout_s :
                                   kind == "mmwave" ? config.mmwave_timeout_s : config.sensor_timeout_s;
            if (!fresh(t, now, timeout)) throw std::runtime_error("stale_or_future_sensor_frame");
            if (previous.first == run && last_rx.count(kind) && t < last_rx[kind])
                throw std::runtime_error("sensor_rx_clock_regressed");
            if (previous.first != run && kind == "telemetry") {
                data.pir.positive_timestamp_s = data.estop.positive_timestamp_s = -1;
            }
            if (previous.first != run && kind == "camera") data.camera.positive_timestamp_s=-1;
            if (previous.first != run && !previous.first.empty()) retired_runs[kind].insert(previous.first);
            previous = {run, seq};
            last_rx[kind]=t;
            if (kind == "telemetry") {
                const bool link = j.contains("uptime_ms") && j["uptime_ms"].is_number_integer() && j["uptime_ms"] >= 0;
                const auto boot = string_field(j,"boot_id");
                if (source == "REAL_ESP32" && link && !boot.empty()) {
                    const auto uptime=j["uptime_ms"].get<std::uint64_t>();
                    if (boot != board_boot) {
                        data.pir.positive_timestamp_s=data.estop.positive_timestamp_s=-1;
                        board_boot=boot; board_uptime=uptime;
                    } else if (board_uptime && uptime < *board_uptime) {
                        throw std::runtime_error("board_uptime_regressed");
                    } else board_uptime=uptime;
                }
                controller.valid=false;
                if (source == "REAL_ESP32") {
                    const bool complete=truth(j,"controller_feedback_valid") && link && !boot.empty() &&
                        string_field(j,"status") == "ok" && j.contains("active_run") && j["active_run"].is_string() &&
                        j.contains("fan_cmd") && j["fan_cmd"].is_boolean() &&
                        j.contains("buzzer_cmd") && j["buzzer_cmd"].is_boolean() &&
                        j.contains("estop_latched") && j["estop_latched"].is_boolean() &&
                        j.contains("actuators_enabled") && j["actuators_enabled"].is_boolean() &&
                        j.contains("heartbeat_fault") && j["heartbeat_fault"].is_boolean();
                    controller={complete,truth(j,"fan_cmd"),truth(j,"buzzer_cmd"),truth(j,"estop_latched"),
                        truth(j,"actuators_enabled"),truth(j,"heartbeat_fault"),t,boot,
                        string_field(j,"active_run"),run,seq,false,true,false,-1,0,""};
                    controller.software_valid = complete && truth(j,"software_control_valid");
                    if (controller.software_valid) {
                        controller.software_latched = truth(j,"software_stop_latched");
                        controller.servo_ready = truth(j,"servo_ready");
                        controller.servo = j["servo_cmd"].is_number_integer() ? j["servo_cmd"].get<int>() : -1;
                        controller.stop_generation = j.at("stop_generation").get<unsigned>();
                        controller.stop_nonce = j.at("stop_nonce").get<std::string>();
                    }
                }
                binary(data.esp32, link, link, t, source);
                binary(data.pir, truth(j,"pir_valid") && j.contains("pir") && j["pir"].is_boolean(), truth(j,"pir"), t, source);
                binary(data.estop, truth(j,"estop_valid") && j.contains("estop") && j["estop"].is_boolean(), truth(j,"estop"), t, source);
                const bool temp_ok = truth(j,"temp_valid") && is_number(j,"temp_c");
                safeguard::ScalarSample value{temp_ok, temp_ok ? j["temp_c"].get<double>() : 0, t, source};
                if (source == "REAL_ESP32") measured = value;
                if (!override_temp) data.temperature = value;
            } else if (kind == "camera") {
                binary(data.camera, truth(j,"valid") && j.contains("motion") && j["motion"].is_boolean(), truth(j,"motion"), t, source);
            } else if (kind == "mmwave") {
                data.mmwave = {truth(j,"valid"), string_field(j,"health") == "ok", truth(j,"evidence"),
                               truth(j,"validated"), t, string_field(j,"evidence_kind","presence"), source};
                data.mmwave.health=string_field(j,"health","unknown");
                data.mmwave.continuity_run = run;
                if (j.contains("adapter_version")) {
                    if (j.at("adapter_version") != 1 || !j.contains("continuity_epoch") ||
                        !j.at("continuity_epoch").is_number_unsigned())
                        throw std::runtime_error("invalid_radar_continuity");
                    data.mmwave.continuity_epoch = j.at("continuity_epoch").get<std::uint64_t>();
                }
                if (!j.contains("evidence") || !j["evidence"].is_boolean()) data.mmwave.valid = false;
            } else if (kind == "ambient" || kind == "temperature") {
                const bool ok = truth(j,"valid") && is_number(j,"temp_c");
                safeguard::ScalarSample value{ok, ok ? j["temp_c"].get<double>() : 0, t, source};
                if (kind == "ambient") data.ambient = value;
                else if (mode == "DEMO" && override_temp && source == "DEMO") data.temperature = value;
                else throw std::runtime_error("unexpected_temperature_override");
            } else throw std::runtime_error("unknown_sensor_type");
            last_error.clear();
        } catch (const std::exception& error) {
            invalidate_kind(kind); last_error = error.what();
        }
    }
};

struct ActuatorLink {
    bool enabled, simulation, have = false, fan = false, buzzer = false, pending = false;
    int servo = -1, protect_servo = -1;
    bool servo_protocol = false;
    unsigned id = 0, retries = 0, limit;
    double last_send = -1, timeout, ack_at = -1;
    std::string run, status = "NOT_SENT_DRY_RUN", source = "NONE", fault;
    Json command;
    bool rearm_pending = false, rearm_confirmed = false;
    unsigned rearm_id = 0, rearm_retries = 0;
    double rearm_sent = -1, rearm_ack_at = -1;
    bool controller_ready = false, recovery_needed = true;
    double controller_timeout = 2.0;
    std::string controller_boot, feedback_run;
    std::uint64_t feedback_seq = 0;
    std::string rearm_status = "NONE";
    Json rearm_command;
    HubProcess& hub;
    ActuatorLink(const Json& p, std::string run_id, HubProcess& process)
        : enabled(p.at("actuation").value("enabled",false)), simulation(p.value("profile","") == "SIMULATION"),
          limit(p.at("actuation").value("retry_limit",2u)), timeout(p.at("actuation").value("ack_timeout_s",0.5)),
          run(std::move(run_id)), hub(process) {
        if (!std::isfinite(timeout) || timeout <= 0 || limit > 20) throw std::runtime_error("invalid ACK settings");
        servo_protocol = p.value("manual_control",Json::object()).value("enabled",false);
        const auto angle = p.at("actuation").value("servo_protect_deg",Json(nullptr));
        if (!angle.is_null()) {
            if (!servo_protocol || !angle.is_number_integer() || angle.get<int>() < 45 || angle.get<int>() > 135)
                throw std::runtime_error("servo_protect_deg needs software control and integer 45..135");
            protect_servo = angle.get<int>();
        }
    }
    void lose_controller(const std::string& why) {
        if (rearm_pending) rearm_status="CONTROLLER_LOST_RETRY_MANUALLY";
        pending=rearm_pending=rearm_confirmed=false;
        controller_ready=false; recovery_needed=true; have=false;
        ack_at=-1; source="NONE"; status="WAITING_CONTROLLER"; fault=why;
    }
    ControllerRestore synchronize(const ControllerFeedback& observed, double now) {
        ControllerRestore restore;
        if (!enabled || simulation) return restore;
        if (!observed.valid || observed.timestamp_s < 0 || observed.timestamp_s > now+0.001 ||
            now-observed.timestamp_s >= controller_timeout) {
            lose_controller("controller_feedback_unavailable"); return restore;
        }
        const bool advanced=observed.producer_run != feedback_run || observed.seq > feedback_seq;
        if (!advanced) return restore;
        feedback_run=observed.producer_run; feedback_seq=observed.seq;
        const bool boot_changed=!controller_boot.empty() && controller_boot != observed.boot_id;
        if (boot_changed) lose_controller("controller_restarted");
        controller_boot=observed.boot_id;
        // MCU's latched emergency stop survives a press/release between telemetry frames.
        restore.estop=observed.estop_latched && observed.timestamp_s > rearm_ack_at;
        if (recovery_needed && (observed.fan || observed.buzzer)) restore.protection=true;
        if (!observed.actuators_enabled || observed.heartbeat_fault || observed.active_run != run) {
            lose_controller(!observed.actuators_enabled ? "controller_actuation_disabled" : "controller_session_not_ready");
            return restore;
        }
        if (recovery_needed) {
            have=false; pending=false; ack_at=-1; source="NONE";
            status="CONTROLLER_READY_RESYNC"; fault.clear(); recovery_needed=false;
        } else if (have && !pending && !rearm_pending && observed.timestamp_s > ack_at &&
                   (observed.fan != fan || observed.buzzer != buzzer)) {
            // Unexpected ON must not be erased by an automatic OFF command.
            restore.protection=observed.fan || observed.buzzer;
            have=false; ack_at=-1; source="NONE"; status="CONTROLLER_STATE_CHANGED";
            fault="controller_output_state_changed";
        }
        controller_ready=true;
        return restore;
    }
    void update(bool want_fan, bool want_buzzer, double now) {
        if (rearm_pending || (enabled && !simulation && !controller_ready)) return;
        const int want_servo = want_fan ? protect_servo : -1;
        if (!have || fan != want_fan || buzzer != want_buzzer || servo != want_servo) {
            have = true; fan = want_fan; buzzer = want_buzzer; ++id; retries = 0; fault.clear(); ack_at = -1;
            servo = want_servo;
            command = {{"type","command"},{"run_id",run},{"id",id},{"fan",fan},{"buzzer",buzzer}};
            if (servo_protocol) command["servo_deg"] = servo < 0 ? Json(nullptr) : Json(servo);
            if (enabled || simulation) {
                pending = true; last_send = now; status = "WAITING_ACK";
                if (!hub.send(command)) fault = "command_transport_error";
            } else { pending = false; status = "NOT_SENT_DRY_RUN"; source = "NONE"; }
        } else if (pending && now - last_send >= timeout) {
            if (retries < limit) { ++retries; last_send = now; hub.send(command); }
            else { pending = false; status = "ACK_TIMEOUT"; fault = "actuator_ack_timeout"; }
        }
    }
    void request_rearm(double now) {
        if (rearm_pending || (enabled && !simulation && !controller_ready)) return;
        pending = false; rearm_confirmed = false; rearm_retries = 0;
        if (!enabled && !simulation) {
            rearm_confirmed = true; rearm_status = "LOGICAL_REARM_DRY_RUN"; return;
        }
        rearm_id = ++id; rearm_sent = now; rearm_pending = true;
        rearm_status = "WAITING_REARM_ACK";
        rearm_command = {{"type","rearm"},{"run_id",run},{"id",rearm_id}};
        hub.send(rearm_command);
    }
    void tick_rearm(double now) {
        if (rearm_pending && now-rearm_sent >= timeout) {
            if (rearm_retries++ < limit) { rearm_sent=now; hub.send(rearm_command); }
            else { rearm_pending=false; rearm_status="REARM_ACK_TIMEOUT_RETRY_MANUALLY"; fault="rearm_ack_timeout"; }
        }
    }
    void ack(const Json& j, double now) {
        if (enabled && !simulation && (!controller_ready || string_field(j,"boot_id") != controller_boot)) return;
        if (rearm_pending && string_field(j,"run_id") == run && j.contains("id") &&
            j["id"].is_number_integer() && j["id"] == rearm_id) {
            const auto origin = string_field(j,"source");
            if ((simulation && origin != "DEMO") || (!simulation && origin != "REAL_ESP32") ||
                !is_number(j,"rx_monotonic_s") || now-j["rx_monotonic_s"].get<double>() > timeout ||
                j["rx_monotonic_s"].get<double>() > now+0.001) return;
            rearm_pending=false;
            rearm_confirmed=truth(j,"accepted") && j.contains("fan_cmd") && j["fan_cmd"].is_boolean() &&
                j.contains("buzzer_cmd") && j["buzzer_cmd"].is_boolean() && !truth(j,"fan_cmd") && !truth(j,"buzzer_cmd");
            rearm_status=rearm_confirmed ? "REARM_ACK_RECEIVED" : "REARM_REJECTED_RETRY_MANUALLY";
            if (!rearm_confirmed) fault="rearm_rejected";
            else { fault.clear(); rearm_ack_at=now; }
            return;
        }
        if (!pending || string_field(j,"run_id") != run || !j.contains("id") || !j["id"].is_number_integer() || j["id"] != id) return;
        const auto origin = string_field(j,"source");
        if ((simulation && origin != "DEMO") || (!simulation && origin != "REAL_ESP32")) return;
        if (!j.contains("accepted") || !j["accepted"].is_boolean() ||
            !j.contains("fan_cmd") || !j["fan_cmd"].is_boolean() || !j.contains("buzzer_cmd") || !j["buzzer_cmd"].is_boolean()) return;
        if (!is_number(j,"rx_monotonic_s") || now - j["rx_monotonic_s"].get<double>() > timeout || j["rx_monotonic_s"].get<double>() > now + 0.001) return;
        source = origin;
        const bool servo_ok = !servo_protocol || (j.contains("servo_cmd") &&
            (servo < 0 ? j["servo_cmd"].is_null() : j["servo_cmd"] == servo));
        if (!truth(j,"accepted") || truth(j,"fan_cmd") != fan || truth(j,"buzzer_cmd") != buzzer || !servo_ok) {
            status = "ACK_REJECTED"; fault = "actuator_command_rejected"; return;
        }
        pending = false; ack_at = now; fault.clear(); status = simulation ? "SIMULATED_ACK" : "ACK_RECEIVED_NOT_PHYSICAL_FEEDBACK";
    }
};

#include "manual_control.hpp"

Json input_json(const InputStore& store, double now) {
    const auto& d = store.data; const auto& c = store.config;
    auto binary = [&](const safeguard::BinarySample& s) {
        const bool valid = s.valid && store.fresh(s.timestamp_s,now,c.sensor_timeout_s);
        return Json{{"valid",valid},{"value",valid ? Json(s.value) : Json(nullptr)},{"source",s.source}};
    };
    const bool temp = d.temperature.valid && store.fresh(d.temperature.timestamp_s,now,c.temp_timeout_s);
    const bool measured = store.measured.valid && store.fresh(store.measured.timestamp_s,now,c.temp_timeout_s);
    const bool ambient = d.ambient.valid && store.fresh(d.ambient.timestamp_s,now,c.ambient_timeout_s);
    Json camera = binary(d.camera); camera["motion"] = camera["value"];
    Json estop = binary(d.estop); estop["active"] = estop["value"];
    return {{"uwb",{{"ready",d.uwb.ready},{"distance_m",d.uwb.distance_m ? Json(*d.uwb.distance_m) : Json(nullptr)},
                     {"age_s",d.uwb.ready ? Json(now-d.uwb.timestamp_s) : Json(nullptr)},{"source",d.uwb.source}}},
            {"pir",binary(d.pir)},{"camera",camera},{"esp32",binary(d.esp32)},{"estop",estop},
            {"mmwave",{{"valid",d.mmwave.valid && store.fresh(d.mmwave.timestamp_s,now,c.mmwave_timeout_s)},
                        {"health",store.fresh(d.mmwave.timestamp_s,now,c.mmwave_timeout_s) ? d.mmwave.health : "unknown"},{"evidence",d.mmwave.evidence},
                        {"evidence_kind",d.mmwave.evidence_kind},{"validated",d.mmwave.validated},{"source",d.mmwave.source}}},
            {"temperature",{{"valid",temp},{"temp_c",nullable(temp,d.temperature.value)},{"source",d.temperature.source},
                            {"measured_valid",measured},{"measured_c",nullable(measured,store.measured.value)}}},
            {"ambient",{{"valid",ambient},{"temp_c",nullable(ambient,d.ambient.value)},{"source",d.ambient.source}}}};
}
void atomic_json(const fs::path& path, const Json& value) {
    const auto temporary = path.string() + ".tmp";
    { std::ofstream out(temporary); out << value.dump(2) << '\n'; if (!out) throw std::runtime_error("state file write failed"); }
    fs::rename(temporary,path);
}
std::string csv_cell(const Json& j) {
    if (j.is_null()) return "";
    std::string s = j.is_string() ? j.get<std::string>() : j.dump();
    std::string quoted = "\"";
    for (char c : s) { if (c == '"') quoted += '"'; quoted += c; }
    return quoted + '"';
}
} // namespace

int main(int argc, char** argv) {
    try {
        std::string config_name = "configs/simulation.json", scenario, input_name;
        double duration = 0; bool no_dashboard = false;
        for (int i=1;i<argc;++i) {
            std::string arg = argv[i];
            if (arg == "--help") {
                std::cout << "SafeGuard main 0.1.1\n--config FILE --scenario NAME --duration SECONDS --no-dashboard --input JSONL_FILE_OR_-\n";
                return 0;
            }
            if (arg == "--no-dashboard") { no_dashboard = true; continue; }
            if (++i >= argc) throw std::runtime_error("option needs a value: " + arg);
            if (arg == "--config") config_name = argv[i];
            else if (arg == "--scenario") scenario = argv[i];
            else if (arg == "--input") input_name = argv[i];
            else if (arg == "--duration") { std::size_t used; duration = std::stod(argv[i],&used); if (used != std::string(argv[i]).size() || !std::isfinite(duration) || duration < 0) throw std::runtime_error("invalid duration"); }
            else throw std::runtime_error("unknown option: " + arg);
        }
        Json project; { std::ifstream in(config_name); if (!in) throw std::runtime_error("config not found: " + config_name); in >> project; }
        if (!scenario.empty()) project["scenario"] = scenario;
        if (no_dashboard) project["dashboard"]["enabled"] = false;
        const auto mode = project.value("mode","REAL"), profile = project.value("profile","REAL");
        if (!((mode == "REAL" && profile == "REAL") ||
              (mode == "DEMO" && (profile == "SIMULATION" || profile == "HARDWARE_DEMO"))))
            throw std::runtime_error("invalid mode/profile combination");
        const auto core_config = safeguard::Config::from_json(project);
        const auto run_id = utc_id();
        const fs::path folder = fs::absolute(fs::path("runs")/run_id);
        fs::create_directories(folder);
        atomic_json(folder/"config_used.json",project);
        atomic_json(folder/"metadata.json",{{"version",VERSION},{"run_id",run_id},{"mode",mode},{"profile",profile},
                    {"scenario",project.value("scenario","normal")},{"hardware_validation","pending_for_this_main_build"},
                    {"note","SIMULATION is software verification; ACK is not physical actuator feedback; candidate settings require calibration"}});
        std::ofstream raw(folder/"raw_input.jsonl"), states(folder/"states.jsonl"), csv(folder/"telemetry.csv");
        if (!raw || !states || !csv) throw std::runtime_error("cannot create run logs");
        csv << "elapsed_s,mode,profile,state,guardian,occupant,uwb_distance_m,temp_input_c,t35_s,fan_requested,buzzer_requested,ack_status,ack_source,reason\n";
        std::signal(SIGINT,on_signal); std::signal(SIGTERM,on_signal); std::signal(SIGPIPE,SIG_IGN);
        HubProcess hub;
        int input = STDIN_FILENO; bool close_input = false;
        if (input_name.empty()) { hub.launch(folder/"config_used.json",folder/"current_state.json"); input = hub.input; }
        else if (input_name != "-") { input = open(input_name.c_str(),O_RDONLY); close_input = true; if (input < 0) throw std::runtime_error("cannot open input file"); }
        if (!input_name.empty() && project.at("actuation").value("enabled",false)) throw std::runtime_error("file-input mode cannot enable hardware actuation");
        safeguard::Core core(core_config); InputStore store(project,core_config); ActuatorLink actuator(project,run_id,hub);
        ManualControl manual(project,actuator);
        const double start = mono(); double last_log = -1, last_display = -1, last_heartbeat = -1;
        std::uint64_t heartbeat_seq = 0; std::string pending, processing_key, previous_state;
        bool dropping = false, eof = false; Json snapshot;
        std::cout << "SafeGuard " << VERSION << " | " << mode << " / " << profile << "\nLogs: " << folder << '\n';
        if (profile == "SIMULATION") std::cout << "SOFTWARE SIMULATION: virtual sensor data; no physical actuation.\n";
        while (!stopping && !eof) {
            pollfd fd{input,POLLIN,0};
            const int result = poll(&fd,1,50);
            if (result < 0 && errno == EINTR) continue;
            if (result < 0 || (fd.revents & (POLLERR|POLLNVAL))) { store.last_error = "sensor_hub_pipe_error"; eof = true; }
            if (fd.revents & (POLLIN|POLLHUP)) {
                char buffer[4096]; const auto n = read(input,buffer,sizeof buffer);
                if (n == 0) eof = true;
                else if (n < 0) { if (errno != EINTR) { eof = true; store.last_error = "sensor_input_read_error"; } }
                else for (ssize_t i=0;i<n;++i) {
                    if (buffer[i]=='\n') {
                        if (!dropping && !pending.empty()) {
                            const double received = mono();
                            try {
                                const auto j = Json::parse(pending);
                                if (!j.is_object()) throw std::runtime_error("not an object");
                                raw << Json{{"arrival_monotonic_s",received},{"payload",j}}.dump() << '\n'; raw.flush();
                                if (string_field(j,"type") == "ack") { manual.ack(j,received); actuator.ack(j,received); }
                                else store.ingest(j,received);
                            } catch (const std::exception& error) {
                                store.last_error = "malformed_input";
                                raw << Json{{"arrival_monotonic_s",received},{"parse_error",error.what()},{"line",pending}}.dump() << '\n';
                            }
                        }
                        pending.clear(); dropping = false;
                    } else if (!dropping) {
                        pending += buffer[i];
                        if (pending.size()>65536) { pending.clear(); dropping=true; store.last_error="input_line_too_long"; }
                    }
                }
            }
            const double now = mono(); store.refresh(now);
            actuator.controller_timeout=core_config.sensor_timeout_s;
            const auto restored=actuator.synchronize(store.controller,now);
            if (!manual.holding()) core.restore_controller_latches(restored.protection,restored.estop);
            if (manual.tick(store,now)) {
                core = safeguard::Core(core_config);
                store.data.pir.positive_timestamp_s = store.data.camera.positive_timestamp_s = -1;
                actuator.have = false;
            }
            if (!manual.enabled && store.rearm_requested && previous_state == "ESTOP" &&
                store.data.estop.valid && !store.data.estop.value &&
                store.fresh(store.data.estop.timestamp_s,now,core_config.sensor_timeout_s)) actuator.request_rearm(now);
            actuator.tick_rearm(now);
            const bool rearm = actuator.rearm_confirmed;
            auto output = core.step(store.data,now,store.clear_requested,rearm);
            if (manual.holding()) {
                output.demand_fan = output.demand_buzzer = false;
                output.reason = "manual_stop_held";
            }
            store.clear_requested = store.rearm_requested = false;
            Json control{{"type","processing"},{"run_id",run_id},{"camera",output.camera_processing},{"mmwave",output.mmwave_processing},{"state",safeguard::state_name(output.state)}};
            const std::string key = control.dump();
            if (key != processing_key) { hub.send(control); processing_key=key; }
            if (now-last_heartbeat >= 0.5) { hub.send({{"type","heartbeat"},{"run_id",run_id},{"seq",++heartbeat_seq}}); last_heartbeat=now; }
            if (rearm && previous_state == "ESTOP" && output.state == safeguard::State::INIT) {
                actuator.have = false; // Rearm requires a new explicit, ordered OFF command.
            }
            actuator.rearm_confirmed=false;
            if (!manual.holding()) actuator.update(output.demand_fan,output.demand_buzzer,now);
            snapshot = safeguard::to_json(output);
            snapshot["version"]=VERSION; snapshot["run_id"]=run_id; snapshot["profile"]=profile;
            snapshot["elapsed_s"]=now-start; snapshot["rx_monotonic_s"]=now;
            snapshot["inputs"]=input_json(store,now);
            snapshot["outputs"]={{"fan",output.demand_fan},{"buzzer",output.demand_buzzer},
                                 {"actuation_enabled",actuator.enabled && !actuator.simulation},{"ack_status",actuator.status},
                                 {"ack_source",actuator.source},{"command_id",actuator.id},
                                 {"rearm_status",actuator.rearm_status},
                                 {"ack_monotonic_s",actuator.ack_at>=0 ? Json(actuator.ack_at):Json(nullptr)},
                                 {"physical_feedback_verified",false}};
            snapshot["manual_control"] = manual.snapshot(store.controller,now);
            if (manual.holding()) {
                snapshot["state"] = "MANUAL_STOP";
                snapshot["outputs"]["ack_status"] = manual.confirmed && !manual.resuming ?
                    "STOP_CONFIRMED_BY_CONTROLLER_REPORT" : "STOP_NOT_YET_CONFIRMED";
                snapshot["outputs"]["ack_source"] = manual.confirmed && !manual.resuming ? "REAL_ESP32" : "NONE";
                snapshot["outputs"]["ack_monotonic_s"] = nullptr;
            }
            snapshot["outputs"]["servo_deg"] = manual.holding() || actuator.servo < 0 ? Json(nullptr) : Json(actuator.servo);
            snapshot["thresholds"]={{"departure_distance_m",core_config.departure_distance_m},{"departure_hold_s",core_config.departure_hold_s},
                                    {"risk_temp_c",core_config.risk_temp_c}};
            const auto& feedback=store.controller;
            snapshot["controller"]={{"feedback_valid",feedback.valid && store.fresh(feedback.timestamp_s,now,core_config.sensor_timeout_s)},
                {"session_ready",actuator.controller_ready},{"boot_id",feedback.boot_id},{"active_run",feedback.active_run},
                {"fan_cmd",feedback.valid ? Json(feedback.fan):Json(nullptr)},
                {"buzzer_cmd",feedback.valid ? Json(feedback.buzzer):Json(nullptr)},
                {"estop_latched",feedback.valid ? Json(feedback.estop_latched):Json(nullptr)},
                {"physical_feedback_verified",false}};
            if (!actuator.fault.empty()) snapshot["faults"].push_back(actuator.fault);
            if (!store.last_error.empty()) snapshot["faults"].push_back(store.last_error);
            const auto state = manual.holding() ? std::string("MANUAL_STOP") : std::string(safeguard::state_name(output.state));
            if (now-last_log>=0.2 || state!=previous_state) {
                snapshot["state_from"]=previous_state; snapshot["state_to"]=state;
                states << snapshot.dump() << '\n'; states.flush();
                atomic_json(folder/"current_state.json",snapshot);
                const std::vector<Json> cells={now-start,mode,profile,state,snapshot["guardian"],snapshot["occupant"],
                    snapshot["inputs"]["uwb"]["distance_m"],snapshot["inputs"]["temperature"]["temp_c"],snapshot["thermal"]["t35_s"],
                    output.demand_fan,output.demand_buzzer,snapshot["outputs"]["ack_status"],snapshot["outputs"]["ack_source"],output.reason};
                for (std::size_t k=0;k<cells.size();++k) { if(k) csv << ','; csv << csv_cell(cells[k]); }
                csv << '\n'; csv.flush(); last_log=now;
            }
            if (state!=previous_state || now-last_display>=1) {
                std::cout << '[' << mode << '/' << profile << "] " << state << " | " << output.reason
                          << " | guardian=" << snapshot["guardian"] << " occupant=" << snapshot["occupant"]
                          << " distance=" << snapshot["inputs"]["uwb"]["distance_m"]
                          << " fan_requested=" << output.demand_fan << " ACK=" << snapshot["outputs"]["ack_status"] << '\n' << std::flush;
                last_display=now;
            }
            previous_state=state;
            if (duration>0 && now-start>=duration) break;
        }
        if (!snapshot.is_null()) {
            snapshot["stopped"]=true; snapshot["stop_reason"]=eof ? "sensor_input_eof" : "operator_or_duration_stop";
            snapshot["guardian"]="UNKNOWN";
            snapshot["inputs"]["uwb"]["ready"]=false; snapshot["inputs"]["uwb"]["distance_m"]=nullptr;
            for (const auto* key : {"pir","camera","mmwave","temperature","ambient","estop","esp32"})
                snapshot["inputs"][key]["valid"]=false;
            snapshot["faults"].push_back("CONTROLLER_STOPPED");
            snapshot["outputs"]["ack_status"]="CONTROLLER_STOPPED";
            states << snapshot.dump() << '\n'; states.flush(); atomic_json(folder/"current_state.json",snapshot);
        }
        if (close_input) close(input);
        std::cout << "Stopped. Logs saved.\n";
        if (actuator.enabled && !actuator.simulation && (actuator.fan || actuator.buzzer))
            std::cout << "Protection output was requested; release it through the verified controller/physical ESTOP.\n";
        return eof ? 1 : 0;
    } catch (const std::exception& error) {
        std::cerr << "SafeGuard error: " << error.what() << '\n'; return 1;
    }
}
