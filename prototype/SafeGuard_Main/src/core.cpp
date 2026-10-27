#include "core.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace safeguard {
namespace {
bool recent(double stamp, double now, double ttl) {
    return std::isfinite(stamp) && stamp >= 0 && stamp <= now && now - stamp < ttl;
}
bool allowed_source(const std::string& source, const std::string& mode) {
    return !source.empty() && source != "MISSING" && source != "REPLAY" &&
           (mode == "DEMO" || source != "DEMO");
}
bool binary_valid(const BinarySample& x, const InputSnapshot& s, double now, double ttl) {
    return x.valid && recent(x.timestamp_s, now, ttl) && allowed_source(x.source, s.mode);
}
bool scalar_valid(const ScalarSample& x, const InputSnapshot& s, double now, double ttl) {
    return x.valid && std::isfinite(x.value) && recent(x.timestamp_s, now, ttl) &&
           allowed_source(x.source, s.mode);
}
bool positive(const BinarySample& x, const InputSnapshot& s, double now, const Config& c) {
    if (!binary_valid(x, s, now, c.sensor_timeout_s)) return false;
    const double event = x.positive_timestamp_s >= 0 ? x.positive_timestamp_s : (x.value ? x.timestamp_s : -1);
    return event <= x.timestamp_s && recent(event, now, c.fusion_window_s);
}
void read_number(const nlohmann::json& j, const char* key, double& value) {
    if (!j.contains(key)) return;
    if (!j.at(key).is_number()) throw std::invalid_argument(std::string("numeric config required: ") + key);
    value = j.at(key).get<double>();
    if (!std::isfinite(value)) throw std::invalid_argument(std::string("finite config required: ") + key);
}
void read_bool(const nlohmann::json& j, const char* key, bool& value) {
    if (!j.contains(key)) return;
    if (!j.at(key).is_boolean()) throw std::invalid_argument(std::string("boolean config required: ") + key);
    value = j.at(key).get<bool>();
}
}

Config Config::from_json(const nlohmann::json& project) {
    if (!project.is_object()) throw std::invalid_argument("config must be object");
    Config c;
    auto section = [&](const char* key) {
        auto j = project.value(key, nlohmann::json::object());
        if (!j.is_object()) throw std::invalid_argument(std::string("config section must be object: ") + key);
        return j;
    };
    const auto f = section("fsm"), t = section("thermal"), r = section("required");
#define READ_F(name) read_number(f, #name, c.name)
    READ_F(departure_distance_m); READ_F(departure_hold_s); READ_F(return_distance_m); READ_F(return_hold_s);
    READ_F(uwb_timeout_s); READ_F(fusion_window_s); READ_F(sensor_timeout_s); READ_F(mmwave_timeout_s);
    READ_F(evidence_hold_s); READ_F(mmwave_observe_s); READ_F(init_timeout_s);
#undef READ_F
    read_bool(r, "esp32", c.require_esp32); read_bool(r, "camera", c.require_camera);
    read_bool(r, "mmwave", c.require_mmwave);
    read_bool(t, "predictive_control_enabled", c.predictive_control_enabled);
    read_bool(t, "enabled", c.thermal_enabled); read_bool(t, "calibrated", c.thermal_calibrated);
    read_number(t, "R_K_per_W", c.thermal_R); read_number(t, "C_J_per_K", c.thermal_C);
    read_number(t, "Q_in_W", c.thermal_Q);
#define READ_T(name) read_number(t, #name, c.name)
    READ_T(dt_s); READ_T(horizon_s); READ_T(protect_horizon_s); READ_T(risk_temp_c);
    READ_T(ambient_timeout_s); READ_T(temp_timeout_s);
#undef READ_T
    c.validate(); return c;
}
void Config::validate() const {
    for (double v : {departure_distance_m, departure_hold_s, return_distance_m, return_hold_s,
                    uwb_timeout_s, fusion_window_s, sensor_timeout_s, mmwave_timeout_s,
                    evidence_hold_s, mmwave_observe_s, init_timeout_s, ambient_timeout_s, temp_timeout_s})
        if (!std::isfinite(v) || v <= 0) throw std::invalid_argument("FSM thresholds/timeouts must be finite positive");
    if (return_distance_m >= departure_distance_m) throw std::invalid_argument("return threshold must be below departure threshold");
    if (!std::isfinite(risk_temp_c)) throw std::invalid_argument("risk temperature must be finite");
    // Invalid thermal parameters disable prediction, not the already-hot measured reaction.
}
const char* state_name(State s) {
    switch (s) {
#define S(name) case State::name: return #name
        S(INIT); S(STANDBY); S(DEPARTURE_CHECK); S(PRIMARY); S(MMWAVE); S(FAIL_SAFE);
        S(THERMAL); S(PROTECTION); S(FAULT); S(ESTOP);
#undef S
    } return "FAULT";
}
const char* occupant_name(Occupant x) {
    return x == Occupant::CONFIRMED ? "CONFIRMED" : x == Occupant::SUSPECTED ? "SUSPECTED" : "UNKNOWN";
}
const char* guardian_name(Guardian x) {
    return x == Guardian::NEAR ? "NEAR" : x == Guardian::AWAY ? "AWAY" : "UNKNOWN";
}
Core::Core(Config config) : c_(std::move(config)) { c_.validate(); }
void Core::restore_controller_latches(bool protect, bool estop) {
    if (protect && !protection_) {
        protection_ = true; away_ = true; guardian_ = Guardian::UNKNOWN;
        departure_since_.reset(); return_since_.reset();
        // The prior controller's active output is evidence for retaining the
        // protection demand, not new evidence that an occupant was confirmed.
    }
    if (estop) estop_ = true;
}
void Core::enter(State state, double now, const std::string& reason) {
    if (state_ != state) {
        state_ = state; entered_s_ = now;
        if (state == State::MMWAVE) {
            evidence_since_.reset(); empty_since_.reset(); last_mmwave_s_ = -1;
        }
    }
    reason_ = reason;
}
void Core::reset_cycle(double now) {
    away_ = false; protection_ = false; occupant_ = Occupant::UNKNOWN;
    departure_since_.reset(); return_since_.reset(); evidence_since_.reset(); empty_since_.reset();
    enter(State::STANDBY, now, "cycle_cleared");
}
void Core::update_processing(CoreOutput& out, double now) {
    // Required devices must be allowed to produce samples during initialization,
    // including recovery from an initialization fault. Otherwise readiness waits
    // forever for sensors whose processing this same FSM has disabled.
    const bool initializing = state_ == State::INIT ||
                              (state_ == State::FAULT && fault_resume_ == State::INIT);
    out.camera_processing = (initializing && c_.require_camera) ||
                            state_ == State::PRIMARY || state_ == State::MMWAVE || state_ == State::FAIL_SAFE;
    out.mmwave_processing = (initializing && c_.require_mmwave) ||
                            state_ == State::MMWAVE || state_ == State::FAIL_SAFE;
    out.thermal_processing = state_ == State::THERMAL || state_ == State::PROTECTION;
    auto track = [now](bool enabled, std::optional<double>& since) {
        if (!enabled) since.reset();
        else if (!since) since = now;
    };
    track(out.camera_processing, camera_enabled_since_);
    track(out.mmwave_processing, mmwave_enabled_since_);
}
ThermalResult Core::predict(const InputSnapshot& s, double now) const {
    ThermalResult r;
    auto fail = [&](const std::string& reason) { r.reason = reason; return r; };
    if (s.mode != "REAL" && s.mode != "DEMO") return fail("invalid_mode");
    if (!scalar_valid(s.temperature, s, now, c_.temp_timeout_s)) return fail("temperature_invalid");
    r.curve.emplace_back(0, s.temperature.value);
    if (!c_.thermal_enabled) return fail("model_disabled");
    if (s.mode == "REAL" && !c_.thermal_calibrated) return fail("uncalibrated_real_model");
    if (!scalar_valid(s.ambient, s, now, c_.ambient_timeout_s)) return fail("ambient_expired_or_invalid");
    const double rc = c_.thermal_R * c_.thermal_C;
    if (!(std::isfinite(rc) && c_.thermal_R > 0 && c_.thermal_C > 0 &&
          std::isfinite(c_.thermal_Q) && c_.thermal_Q >= 0 && c_.dt_s > 0 &&
          c_.dt_s <= rc && std::isfinite(c_.dt_s) && c_.horizon_s > 0 &&
          std::isfinite(c_.horizon_s) && c_.horizon_s / c_.dt_s <= 10000 &&
          c_.protect_horizon_s >= 0 && std::isfinite(c_.protect_horizon_s))) return fail("invalid_model_parameters");
    double temp = s.temperature.value, elapsed = 0;
    if (temp >= c_.risk_temp_c) r.t35_s = 0;
    while (elapsed < c_.horizon_s) {
        const double step = std::min(c_.dt_s, c_.horizon_s - elapsed);
        temp += step / c_.thermal_C * ((s.ambient.value - temp) / c_.thermal_R + c_.thermal_Q);
        elapsed += step;
        if (!std::isfinite(temp)) return fail("nonfinite_model_result");
        r.curve.emplace_back(elapsed, temp);
        if (!r.t35_s && temp >= c_.risk_temp_c) r.t35_s = elapsed;
    }
    r.valid = true; r.reason = r.t35_s ? "predicted_threshold" : "no_reach_within_horizon";
    return r;
}

CoreOutput Core::step(const InputSnapshot& s, double now, bool manual_clear, bool manual_rearm, const LivePrediction* prediction) {
    CoreOutput out; out.mode = s.mode;
    auto fault = [&](const std::string& name) { out.faults.push_back(name); };
    if (!std::isfinite(now) || now < 0 || (last_now_ >= 0 && now < last_now_)) {
        // With a broken clock, conservatively accept an asserted emergency stop;
        // never use this branch to release it or restart outputs.
        if ((s.mode == "REAL" || s.mode == "DEMO") && s.estop.valid && s.estop.value &&
            std::isfinite(s.estop.timestamp_s) && s.estop.timestamp_s >= 0 &&
            allowed_source(s.estop.source, s.mode)) estop_ = true;
        enter(estop_ ? State::ESTOP : (protection_ ? State::PROTECTION : State::FAULT),
              last_now_ < 0 ? 0 : last_now_, "invalid_monotonic_clock");
        fault("CLOCK_INVALID");
        out.state = state_; out.occupant = occupant_; out.guardian = Guardian::UNKNOWN;
        out.demand_fan = out.demand_buzzer = protection_ && !estop_; out.alert = true; out.reason = reason_;
        camera_enabled_since_.reset(); mmwave_enabled_since_.reset();
        return out;
    }
    last_now_ = now; if (entered_s_ < 0) entered_s_ = now;
    if (s.mode != "REAL" && s.mode != "DEMO") {
        fault("MODE_INVALID"); enter(protection_ ? State::PROTECTION : State::FAULT, now, "invalid_mode");
    }
    const bool mode_ok = s.mode == "REAL" || s.mode == "DEMO";
    const bool uwb_ok = mode_ok && s.uwb.ready && s.uwb.distance_m && std::isfinite(*s.uwb.distance_m) &&
                        *s.uwb.distance_m >= 0 && recent(s.uwb.timestamp_s, now, c_.uwb_timeout_s) &&
                        allowed_source(s.uwb.source, s.mode);
    const bool pir_ok = mode_ok && binary_valid(s.pir, s, now, c_.sensor_timeout_s);
    const bool cam_ok = mode_ok && binary_valid(s.camera, s, now, c_.sensor_timeout_s);
    const bool pir = positive(s.pir, s, now, c_), camera = positive(s.camera, s, now, c_);
    const bool esp_ok = binary_valid(s.esp32, s, now, c_.sensor_timeout_s) && s.esp32.value;
    const bool estop_ok = binary_valid(s.estop, s, now, c_.sensor_timeout_s);
    const bool temp_ok = scalar_valid(s.temperature, s, now, c_.temp_timeout_s);
    const bool mm_recent = recent(s.mmwave.timestamp_s, now, c_.mmwave_timeout_s);
    const bool mm_ok = mode_ok && s.mmwave.valid && s.mmwave.healthy && s.mmwave.health != "fault" && mm_recent &&
                       allowed_source(s.mmwave.source, s.mode);
    const bool evidence_kind = s.mmwave.evidence_kind == "presence" || s.mmwave.evidence_kind == "micro_motion" ||
                               s.mmwave.evidence_kind == "vital_signs";
    const bool mm_trusted = mm_ok && ((s.mmwave.validated && evidence_kind) ||
                                    (s.mode == "DEMO" && s.mmwave.source == "DEMO"));
    if (!uwb_ok) fault("UWB_UNAVAILABLE");
    if (away_) {
        if (!pir_ok) fault("PIR_UNAVAILABLE");
        if (!temp_ok) fault("TEMPERATURE_UNAVAILABLE");
    }
    if (c_.require_esp32 && !esp_ok) fault("ESP32_UNAVAILABLE");
    if (c_.require_esp32 && !estop_ok) fault("ESTOP_STATUS_UNAVAILABLE");
    if (estop_ok && s.estop.value) { estop_ = true; enter(State::ESTOP, now, "emergency_stop_asserted"); }
    if (estop_) {
        if (estop_ok && !s.estop.value && manual_rearm) {
            estop_ = false; protection_ = false; away_ = false; occupant_ = Occupant::UNKNOWN;
            guardian_ = Guardian::UNKNOWN; departure_since_.reset(); return_since_.reset();
            enter(State::INIT, now, "manual_rearm_requires_initialization");
        } else enter(State::ESTOP, now, "await_estop_release_and_manual_rearm");
        out.state = state_; out.occupant = occupant_; out.guardian = guardian_;
        update_processing(out, now);
        out.reason = reason_; out.alert = true; return out; // Always OFF, including the rearm step.
    }

    // A fresh resumed stream cannot bridge an unobserved gap in either hold timer.
    if (uwb_ok && last_uwb_s_ >= 0 && s.uwb.timestamp_s - last_uwb_s_ >= c_.uwb_timeout_s) {
        departure_since_.reset(); return_since_.reset();
    }
    if (uwb_ok) last_uwb_s_ = s.uwb.timestamp_s;
    if (!uwb_ok) {
        guardian_ = Guardian::UNKNOWN; departure_since_.reset(); return_since_.reset();
    } else if (away_) {
        if (*s.uwb.distance_m <= c_.return_distance_m) {
            if (!return_since_) return_since_ = s.uwb.timestamp_s;
            guardian_ = s.uwb.timestamp_s - *return_since_ >= c_.return_hold_s ? Guardian::NEAR : Guardian::AWAY;
        } else { return_since_.reset(); guardian_ = Guardian::AWAY; }
    } else guardian_ = *s.uwb.distance_m <= c_.return_distance_m ? Guardian::NEAR : Guardian::UNKNOWN;
    const bool returned = uwb_ok && away_ && guardian_ == Guardian::NEAR;
    if (protection_) {
        enter(State::PROTECTION, now, "protection_latched");
        if (manual_clear && returned) reset_cycle(now);
    } else if (returned) reset_cycle(now);

    const bool required_ready = mode_ok && uwb_ok && (!c_.require_esp32 || (esp_ok && estop_ok)) &&
                                (!c_.require_camera || cam_ok) && (!c_.require_mmwave || mm_ok);
    if (!mode_ok) { /* The mode fault above cannot be bypassed by sensor evidence. */ }
    else switch (state_) {
    case State::INIT:
        if (required_ready) enter(State::STANDBY, now, "required_inputs_ready");
        else if (now - entered_s_ >= c_.init_timeout_s) {
            fault_resume_ = State::INIT; enter(State::FAULT, now, "required_inputs_not_ready");
        } else reason_ = "waiting_required_inputs";
        break;
    case State::STANDBY:
        occupant_ = Occupant::UNKNOWN;
        if (uwb_ok && *s.uwb.distance_m > c_.departure_distance_m) {
            departure_since_ = s.uwb.timestamp_s; enter(State::DEPARTURE_CHECK, now, "distance_above_departure_threshold");
        } else reason_ = uwb_ok ? "guardian_not_departed" : "guardian_unknown";
        break;
    case State::DEPARTURE_CHECK:
        if (!uwb_ok || *s.uwb.distance_m <= c_.departure_distance_m) {
            departure_since_.reset(); enter(State::STANDBY, now, "departure_hold_reset");
        } else {
            if (!departure_since_) departure_since_ = s.uwb.timestamp_s;
            if (s.uwb.timestamp_s - *departure_since_ >= c_.departure_hold_s) {
                away_ = true; guardian_ = Guardian::AWAY; enter(State::PRIMARY, now, "guardian_departure_confirmed");
            }
        }
        break;
    case State::PRIMARY:
        occupant_ = Occupant::UNKNOWN;
        if (pir || camera) enter(State::MMWAVE, now, "valid_primary_OR");
        else reason_ = (pir_ok && cam_ok) ? "primary_no_recent_detection" : "primary_inputs_unknown";
        break;
    case State::MMWAVE:
        if (!mm_ok) {
            evidence_since_.reset(); empty_since_.reset();
            if ((s.mmwave.health == "fault" && s.mmwave.timestamp_s >= entered_s_) ||
                now - entered_s_ >= c_.mmwave_timeout_s)
                enter(State::FAIL_SAFE, now, "mmwave_fault_or_timeout");
            else reason_ = "awaiting_mmwave_active_frame";
        } else {
            if (last_mmwave_s_ >= 0 && s.mmwave.timestamp_s - last_mmwave_s_ >= c_.mmwave_timeout_s) {
                evidence_since_.reset(); empty_since_.reset();
            }
            last_mmwave_s_ = s.mmwave.timestamp_s;
            if (s.mmwave.evidence) {
                empty_since_.reset();
                if (!mm_trusted) {
                    evidence_since_.reset(); enter(State::FAIL_SAFE, now, "mmwave_evidence_not_validated");
                } else {
                    if (!evidence_since_) evidence_since_ = s.mmwave.timestamp_s;
                    if (s.mmwave.timestamp_s - *evidence_since_ >= c_.evidence_hold_s) {
                        occupant_ = Occupant::CONFIRMED; enter(State::THERMAL, now, "validated_mmwave_evidence_stable");
                    } else reason_ = "mmwave_evidence_hold";
                }
            } else {
                evidence_since_.reset();
                if (!empty_since_) empty_since_ = s.mmwave.timestamp_s;
                if (s.mmwave.timestamp_s - *empty_since_ >= c_.mmwave_observe_s)
                    enter(State::PRIMARY, now, "healthy_mmwave_no_detection");
                else reason_ = "observing_healthy_empty_frames";
            }
        }
        break;
    case State::FAIL_SAFE:
        if (mm_ok && (!s.mmwave.evidence || mm_trusted) && (pir || camera)) {
            occupant_ = Occupant::UNKNOWN;
            enter(State::MMWAVE, now, "mmwave_recovered_reverify");
        } else if (pir && camera) {
            occupant_ = Occupant::SUSPECTED; enter(State::THERMAL, now, "valid_primary_AND_during_mmwave_fault");
        } else { occupant_ = Occupant::UNKNOWN; reason_ = "failsafe_unknown_recheck"; }
        break;
    case State::THERMAL:
        break; // Measured reaction and model run below, including immediately on entry.
    case State::PROTECTION:
        break; // Faults/dropouts never clear this latch.
    case State::FAULT:
        if (fault_resume_ == State::THERMAL && temp_ok) enter(State::THERMAL, now, "temperature_recovered_recheck");
        else if (fault_resume_ == State::INIT && required_ready) enter(State::INIT, now, "inputs_recovered_reinitialize");
        break;
    case State::ESTOP: break;
    }

    if (state_ == State::THERMAL || state_ == State::PROTECTION) {
        const bool measured_risk = temp_ok && occupant_ != Occupant::UNKNOWN && s.temperature.value >= c_.risk_temp_c;
        if (measured_risk) {
            // Do not run even a bounded prediction job before an already-hot protection demand.
            protection_ = true; enter(State::PROTECTION, now, "measured_temperature_at_risk");
            out.thermal.reason = "measured_threshold_no_prediction_needed";
            out.thermal.curve.emplace_back(0, s.temperature.value);
        } else {
            if (c_.predictive_control_enabled) {
                out.thermal.reason = "live_prediction_unavailable";
                if (temp_ok && prediction && prediction->result.valid &&
                    recent(prediction->timestamp_s,now,c_.temp_timeout_s) &&
                    prediction->timestamp_s == s.temperature.timestamp_s &&
                    std::isfinite(prediction->temperature_c) &&
                    prediction->temperature_c == s.temperature.value &&
                    (!prediction->result.t35_s || (std::isfinite(*prediction->result.t35_s) &&
                        *prediction->result.t35_s >= 0 && *prediction->result.t35_s <= 300))) {
                    out.thermal = prediction->result;
                }
            } else out.thermal = predict(s, now);
            if (!out.thermal.valid) fault("THERMAL_" + out.thermal.reason);
        }
        if (state_ == State::THERMAL) {
            if (!temp_ok) { fault_resume_ = State::THERMAL; enter(State::FAULT, now, "temperature_invalid_no_prediction"); }
            else if (occupant_ != Occupant::UNKNOWN &&
                     out.thermal.valid && out.thermal.t35_s && *out.thermal.t35_s <= c_.protect_horizon_s) {
                protection_ = true;
                enter(State::PROTECTION, now, "predicted_temperature_at_risk");
            } else reason_ = out.thermal.valid ? "thermal_monitoring" : "measured_temperature_only";
        }
    }
    out.state = state_; out.occupant = occupant_; out.guardian = guardian_; out.reason = reason_;
    out.demand_fan = out.demand_buzzer = protection_;
    update_processing(out, now);
    // An intentionally disabled detector has no current detection sample. That
    // is not a device failure. Allow a newly enabled worker its startup interval,
    // but continue reporting actual missing data while processing is required.
    if (out.camera_processing && !cam_ok && camera_enabled_since_ &&
        now - *camera_enabled_since_ >= c_.sensor_timeout_s) fault("CAMERA_UNAVAILABLE");
    if (out.mmwave_processing) {
        const bool explicit_mm_fault = mm_recent && s.mmwave.health == "fault" &&
                                       mmwave_enabled_since_ && s.mmwave.timestamp_s >= *mmwave_enabled_since_;
        if (!mm_ok && (explicit_mm_fault || (mmwave_enabled_since_ &&
                       now - *mmwave_enabled_since_ >= c_.mmwave_timeout_s))) fault("MMWAVE_UNAVAILABLE");
        else if (mm_ok && !mm_trusted) fault("MMWAVE_EVIDENCE_UNVALIDATED");
    }
    out.alert = state_ == State::FAIL_SAFE || state_ == State::FAULT || !out.faults.empty();
    if (departure_since_ && uwb_ok) out.departure_elapsed_s = std::max(0.0, s.uwb.timestamp_s - *departure_since_);
    if (return_since_ && uwb_ok) out.return_elapsed_s = std::max(0.0, s.uwb.timestamp_s - *return_since_);
    return out;
}

nlohmann::json to_json(const CoreOutput& o) {
    auto curve = nlohmann::json::array();
    for (const auto& point : o.thermal.curve) curve.push_back({{"t_s",point.first},{"temp_c",point.second}});
    return {{"state",state_name(o.state)},{"occupant",occupant_name(o.occupant)},
            {"guardian",guardian_name(o.guardian)},{"mode",o.mode},{"reason",o.reason},{"faults",o.faults},
            {"demand_fan",o.demand_fan},{"demand_buzzer",o.demand_buzzer},{"alert",o.alert},
            {"processing",{{"camera",o.camera_processing},{"mmwave",o.mmwave_processing},{"thermal",o.thermal_processing}}},
            {"departure_elapsed_s",o.departure_elapsed_s},{"return_elapsed_s",o.return_elapsed_s},
            {"thermal",{{"valid",o.thermal.valid},{"reason",o.thermal.reason},
                        {"t35_s",o.thermal.t35_s ? nlohmann::json(*o.thermal.t35_s) : nlohmann::json(nullptr)},
                        {"curve",curve}}}};
}
} // namespace safeguard
