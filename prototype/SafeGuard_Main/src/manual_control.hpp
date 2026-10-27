// Included inside main.cpp's anonymous namespace; shares its checked JSON helpers.
// Always start held. MCU boots held too: stopping survives power/process restarts
// without writing flash and without silently restarting a previous output.
struct ManualControl {
    bool enabled = false, hold = true, confirmed = false, resuming = false;
    bool resume_ack = false, ever_fresh = false, was_fresh = false;
    unsigned stop_counter = 0, resume_id = 0, generation = 0, resume_retries = 0;
    double last_stop = -100, resume_sent = -1, resume_begin = -1;
    std::string nonce, boot, resume_boot, status = "WAITING_CONTROLLER";
    Json resume_command;
    ActuatorLink& link;
    ManualControl(const Json& project, ActuatorLink& actuator) : link(actuator) {
        const auto cfg = project.value("manual_control",Json::object());
        enabled = cfg.value("enabled",false);
        if (enabled && (!link.enabled || link.simulation ||
            project.at("hardware").value("esp32_protocol", "link") != "link"))
            throw std::runtime_error("manual_control requires real enabled LINK actuation");
        begin_stop("STARTUP_STOP_PENDING");
    }
    bool holding() const { return enabled && hold; }
    void begin_stop(const std::string& reason) {
        hold = true; confirmed = resuming = resume_ack = false;
        nonce = link.run + ":stop:" + std::to_string(++stop_counter);
        last_stop = -100; status = reason;
        if (enabled) {
            link.pending = link.rearm_pending = link.rearm_confirmed = false;
            link.have = false; link.ack_at = -1; link.source = "NONE";
        }
    }
    bool fresh(const ControllerFeedback& f,double now) const {
        return f.valid && f.software_valid && f.timestamp_s >= 0 &&
            f.timestamp_s <= now+.001 && now-f.timestamp_s < link.controller_timeout;
    }
    bool off(const ControllerFeedback& f) const { return !f.fan && !f.buzzer && f.servo < 0; }
    void ack(const Json& j,double now) {
        if (!enabled || !resuming || string_field(j,"run_id") != link.run ||
            !j.contains("id") || j["id"] != resume_id || string_field(j,"source") != "REAL_ESP32" ||
            string_field(j,"boot_id") != resume_boot || !is_number(j,"rx_monotonic_s")) return;
        const double t = j["rx_monotonic_s"].get<double>();
        if (t < resume_begin || t > now+.001 || now-t > 2.0) return;
        resume_ack = truth(j,"accepted") && j.value("stop_generation",Json(nullptr)) == generation &&
            j.value("software_stop_latched",Json(nullptr)) == false &&
            j.value("fan_cmd",Json(nullptr)) == false && j.value("buzzer_cmd",Json(nullptr)) == false &&
            j.contains("servo_cmd") && j["servo_cmd"].is_null();
        if (!resume_ack) begin_stop("RESUME_REJECTED_STOP_PENDING");
    }
    bool tick(InputStore& store,double now) {
        const bool stop = store.manual_stop_requested;
        const bool resume = store.manual_resume_requested && store.manual_resume_stop_nonce == nonce;
        store.manual_stop_requested = store.manual_resume_requested = false;
        store.manual_resume_stop_nonce.clear();
        if (!enabled) return false;
        const auto& f = store.controller;
        const bool live = fresh(f,now);
        if (stop) begin_stop("OPERATOR_STOP_PENDING");  // STOP wins within a single batch
        if (live && !boot.empty() && boot != f.boot_id) begin_stop("MCU_RESTART_STOP_PENDING");
        if (!live && was_fresh) begin_stop("CONTROLLER_LOST_STOP_UNCONFIRMED");
        was_fresh = live;
        if (live) { boot = f.boot_id; ever_fresh = true; }
        if (!hold && live && (f.software_latched || f.heartbeat_fault || f.active_run != link.run))
            begin_stop("CONTROLLER_CHANGED_STOP_PENDING");
        confirmed = live && f.software_latched && f.stop_nonce == nonce && off(f);
        if (hold && resume && !stop && confirmed && !resuming &&
            !f.heartbeat_fault && f.active_run == link.run) {
            resuming = true; resume_ack = false; confirmed = false;
            resume_id = ++link.id; generation = f.stop_generation; resume_boot = f.boot_id;
            resume_begin = resume_sent = now; resume_retries = 0;
            resume_command = {{"type","rearm"},{"run_id",link.run},{"id",resume_id},
                {"boot_id",resume_boot},{"stop_generation",generation}};
            link.hub.send(resume_command);
        }
        if (resuming) {
            status = "RESUME_PENDING_OUTPUTS_BLOCKED";
            if (resume_ack && live && f.timestamp_s >= resume_begin &&
                f.boot_id == resume_boot && f.stop_generation == generation &&
                !f.software_latched && !f.heartbeat_fault && f.active_run == link.run && off(f)) {
                hold = resuming = confirmed = false;
                status = "MONITORING"; link.have = false;
                return true;  // caller resets FSM; never restores prior outputs
            }
            if (now-resume_begin > 3.0) begin_stop("RESUME_TIMEOUT_STOP_PENDING");
            else if (!resume_ack && now-resume_sent > .6 && resume_retries < 3) {
                ++resume_retries; resume_sent = now; link.hub.send(resume_command);
            }
        }
        if (hold && !resuming) {
            if (confirmed) status = "STOPPED_CONTROLLER_CONFIRMED";
            else {
                status = live ? "STOP_PENDING" : "CONTROLLER_UNAVAILABLE_STOP_UNCONFIRMED";
                if (now-last_stop >= .5) {
                    link.hub.send({{"type","manual_stop"},{"run_id",link.run},{"stop_nonce",nonce}});
                    last_stop = now;
                }
            }
        }
        if (!hold) status = "MONITORING";
        return false;
    }
    Json snapshot(const ControllerFeedback& f,double now) const {
        const bool live = fresh(f,now);
        return {{"enabled",enabled},{"held",holding()},{"status",enabled ? status : "DISABLED"},
            {"stop_request_id",nonce},
            {"stop_confirmed",enabled && confirmed && live && !resuming},
            {"resume_available",enabled && confirmed && live && !resuming &&
                !f.heartbeat_fault && f.active_run == link.run},
            {"controller_online",live},{"physical_estop_installed",false},
            {"servo_cmd",live && f.servo >= 0 ? Json(f.servo) : Json(nullptr)},
            {"fan_cmd",live ? Json(f.fan) : Json(nullptr)},
            {"buzzer_cmd",live ? Json(f.buzzer) : Json(nullptr)},
            {"physical_motion_verified",false}};
    }
};
