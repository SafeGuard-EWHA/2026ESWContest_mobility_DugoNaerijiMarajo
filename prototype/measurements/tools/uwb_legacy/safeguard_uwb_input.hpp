#pragma once
// C-block input adapter only. The main program owns all departure/FSM/actuator decisions.
// now_s MUST be CLOCK_MONOTONIC on the SAME Linux host as the Python producer.
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_set>

namespace safeguard {
struct UwbReading {
    bool ready = false;
    std::optional<double> distance_m;
    std::string reason = "waiting";
    double rx_monotonic_s = 0;
};

class UwbInput {
    using Json = nlohmann::json;
    std::string peer_, run_;
    std::unordered_set<std::string> retired_runs_;
    std::uint64_t seq_ = 0;
    double timeout_, active_timeout_;
    UwbReading state_;
    static void require(bool condition, const char* reason) {
        if (!condition) throw std::runtime_error(reason);
    }
    static double number(const Json& j, const char* key) {
        require(j.contains(key) && j.at(key).is_number(), "bad_numeric_field");
        const double value = j.at(key).get<double>();
        require(std::isfinite(value), "nonfinite_number");
        return value;
    }
    static std::uint64_t integer(const Json& j, const char* key) {
        require(j.contains(key) && j.at(key).is_number_integer(), "bad_integer_field");
        require(j.at(key).is_number_unsigned() || j.at(key).get<std::int64_t>() >= 0,
                "negative_integer");
        return j.at(key).get<std::uint64_t>();
    }
    static bool flag(const Json& j, const char* key) {
        require(j.contains(key) && j.at(key).is_boolean(), "bad_boolean_field");
        return j.at(key).get<bool>();
    }
    static std::string text(const Json& j, const char* key) {
        require(j.contains(key) && j.at(key).is_string(), "bad_string_field");
        return j.at(key).get<std::string>();
    }
public:
    explicit UwbInput(std::string peer, double timeout_s = 2.0)
        : peer_(std::move(peer)), timeout_(timeout_s), active_timeout_(timeout_s) {
        require(peer_.size() == 4 && peer_.find_first_not_of("0123456789ABCDEF") == std::string::npos,
                "anchor_id_must_be_four_uppercase_hex_digits");
        require(std::isfinite(timeout_) && timeout_ > 0, "invalid_timeout");
    }
    const UwbReading& state() const { return state_; }
    void invalidate(const std::string& reason) {
        state_ = UwbReading{};
        state_.reason = reason;
    }
    void tick(double now_s) {
        if (!std::isfinite(now_s) || now_s < 0) invalidate("bad_local_clock");
        else if (state_.ready && (now_s < state_.rx_monotonic_s - 0.001 ||
                 now_s - state_.rx_monotonic_s >= active_timeout_))
            invalidate("input_timeout");
    }
    void ingest(const std::string& line, double now_s) {
        try {
            require(line.size() <= 16384, "line_too_long");
            const Json j = Json::parse(line);
            require(j.is_object(), "not_an_object");
            require(text(j, "type") == "uwb" && integer(j, "schema_version") == 1 &&
                    text(j, "source") == "REAL_UWB", "wrong_schema_or_source");
            require(text(j, "peer_id") == peer_, "wrong_peer");
            const auto run = text(j, "run_id"), status = text(j, "status");
            require(!run.empty() && run.size() <= 128, "invalid_run_id");
            const auto seq = integer(j, "seq"), window = integer(j, "window");
            const auto count = integer(j, "sample_count");
            require(seq > 0 && window > 0 && window <= 10000 && count <= window,
                    "invalid_sequence_or_window");
            const bool valid = flag(j, "valid"), ready = flag(j, "filter_ready");
            const bool usable = flag(j, "usable_for_fsm");
            require(usable == (valid && ready), "inconsistent_flags");
            const double source_timeout = number(j, "timeout_s");
            require(source_timeout > 0, "invalid_source_timeout");
            const double limit = std::min(timeout_, source_timeout);
            const double published = number(j, "published_monotonic_s");
            require(std::isfinite(now_s) && now_s >= 0 && published >= 0 &&
                    published <= now_s + 0.001, "future_or_bad_clock");
            require(now_s - published < limit, "queued_old_message");
            require(j.contains("distance_m") && j.contains("rx_monotonic_s") &&
                    j.contains("raw_distance_m") && j.contains("filtered_distance_m"), "missing_field");
            double rx = 0, distance = 0;
            if (valid) {
                require(status == "fresh" && count > 0 && ready == (count == window),
                        "inconsistent_fresh_state");
                rx = number(j, "rx_monotonic_s");
                require(rx >= 0 && rx <= now_s + 0.001 && rx <= published + 0.001,
                        "future_or_bad_rx_clock");
                require(now_s - rx < limit, "stale_source_timestamp");
                const double age = number(j, "age_ms");
                require(age >= 0 && age < 1000 * limit, "stale_source_age");
                require(number(j, "raw_distance_m") >= 0 &&
                        number(j, "filtered_distance_m") >= 0, "negative_distance");
                if (usable) {
                    distance = number(j, "distance_m");
                    require(distance >= 0 && std::abs(distance - number(j, "filtered_distance_m")) <= 1e-9,
                            "inconsistent_distance");
                } else require(j.at("distance_m").is_null(), "warming_distance_must_be_null");
            } else {
                require(!ready && count == 0 && status != "fresh" &&
                        j.at("distance_m").is_null() && j.at("raw_distance_m").is_null() &&
                        j.at("filtered_distance_m").is_null(), "inconsistent_unavailable_state");
            }
            // A different run must introduce itself with the producer's initial waiting record.
            if (run == run_) require(seq > seq_, "duplicate_or_reordered_sequence");
            else if (!run_.empty()) {
                require(!retired_runs_.count(run) && seq == 1 && status == "waiting" && !valid &&
                        j.at("rx_monotonic_s").is_null(), "unexpected_run_change");
                retired_runs_.insert(run_);
            }
            run_ = run; seq_ = seq; active_timeout_ = limit;
            if (usable) state_ = {true, distance, "ready", rx};
            else invalidate(valid ? "warming_up" : "source_" + status);
        } catch (const Json::exception&) { invalidate("malformed_json"); }
          catch (const std::runtime_error& error) { invalidate(error.what()); }
    }
};
}  // namespace safeguard
