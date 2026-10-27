#pragma once
#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace safeguard {
// All times are receiver-host monotonic seconds, never wall-clock/MCU uptime.
struct BinarySample {
    bool valid = false, value = false;
    double timestamp_s = -1, positive_timestamp_s = -1;
    std::string source = "MISSING";
};
struct ScalarSample {
    bool valid = false;
    double value = 0, timestamp_s = -1;
    std::string source = "MISSING";
};
struct UwbSample {
    bool ready = false;
    std::optional<double> distance_m;
    double timestamp_s = -1;
    std::string source = "MISSING";
};
struct MmwaveSample {
    bool valid = false, healthy = false, evidence = false, validated = false;
    double timestamp_s = -1;
    std::string evidence_kind = "presence", source = "MISSING";
    std::string health = "unknown"; // unknown while disabled/starting; explicit fault is distinct.
};
struct InputSnapshot {
    std::string mode = "REAL";
    UwbSample uwb;
    BinarySample pir, camera, estop, esp32;
    MmwaveSample mmwave;
    ScalarSample temperature, ambient;
};

struct Config {
    double departure_distance_m = 5, departure_hold_s = 10;
    double return_distance_m = 4, return_hold_s = 3, uwb_timeout_s = 2;
    double fusion_window_s = 2, sensor_timeout_s = 2, mmwave_timeout_s = 2;
    double evidence_hold_s = 0.5, mmwave_observe_s = 2, init_timeout_s = 5;
    bool require_esp32 = false, require_camera = false, require_mmwave = false;
    bool thermal_enabled = false, thermal_calibrated = false;
    bool predictive_control_enabled = false;
    double thermal_R = 0.2, thermal_C = 1000, thermal_Q = 80;
    double dt_s = 1, horizon_s = 300, protect_horizon_s = 60, risk_temp_c = 35;
    double ambient_timeout_s = 3600, temp_timeout_s = 2;
    static Config from_json(const nlohmann::json& project);
    void validate() const;
};

enum class State { INIT, STANDBY, DEPARTURE_CHECK, PRIMARY, MMWAVE,
                   FAIL_SAFE, THERMAL, PROTECTION, FAULT, ESTOP };
enum class Occupant { UNKNOWN, CONFIRMED, SUSPECTED };
enum class Guardian { UNKNOWN, NEAR, AWAY };
const char* state_name(State);
const char* occupant_name(Occupant);
const char* guardian_name(Guardian);

struct ThermalResult {
    bool valid = false;
    std::string reason = "not_requested";
    std::optional<double> t35_s;
    std::vector<std::pair<double, double>> curve;
};
// Internal, receiver-timestamped result. Never accepted from UART JSON.
struct LivePrediction {
    ThermalResult result;
    double timestamp_s = -1, temperature_c = 0;
};
struct CoreOutput {
    State state = State::INIT;
    Occupant occupant = Occupant::UNKNOWN;
    Guardian guardian = Guardian::UNKNOWN;
    bool demand_fan = false, demand_buzzer = false, alert = false;
    bool camera_processing = false, mmwave_processing = false, thermal_processing = false;
    std::string reason = "initializing", mode = "REAL";
    std::vector<std::string> faults;
    ThermalResult thermal;
    double departure_elapsed_s = 0, return_elapsed_s = 0;
};
nlohmann::json to_json(const CoreOutput& output);

class Core {
public:
    explicit Core(Config config = {});
    CoreOutput step(const InputSnapshot&, double now_s,
                    bool manual_clear = false, bool manual_rearm = false,
                    const LivePrediction* prediction = nullptr);
    // Only the validated MCU feedback path may restore these persistent latches.
    // False values never release them; normal clear/rearm rules still apply.
    void restore_controller_latches(bool protect, bool estop);
private:
    Config c_;
    State state_ = State::INIT, fault_resume_ = State::INIT;
    Occupant occupant_ = Occupant::UNKNOWN;
    Guardian guardian_ = Guardian::UNKNOWN;
    bool away_ = false, protection_ = false, estop_ = false;
    double last_now_ = -1, entered_s_ = -1, last_uwb_s_ = -1, last_mmwave_s_ = -1;
    std::optional<double> departure_since_, return_since_, evidence_since_, empty_since_;
    std::optional<double> camera_enabled_since_, mmwave_enabled_since_;
    std::string reason_ = "initializing";
    void enter(State state, double now, const std::string& reason);
    void reset_cycle(double now);
    void update_processing(CoreOutput& output, double now);
    ThermalResult predict(const InputSnapshot&, double now) const;
};
} // namespace safeguard
