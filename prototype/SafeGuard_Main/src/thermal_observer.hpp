#pragma once
// Research estimator. Deliberately has no actuator or FSM interface.
#include "core.hpp"
#include <algorithm>
#include <cmath>
#include <deque>
#include <optional>

namespace safeguard {
class ThermalObserver {
    struct Point { double t, temp, ambient; };
    std::deque<Point> history_;
    double last_stamp_ = -1, last_now_ = -1;
    std::string source_, ambient_source_;
    double last_ambient_stamp_ = -1;
public:
    // Fit to approximate readings of McLaren 2005 Fig.3, NOT a paper-reported constant.
    static constexpr double tau_s = 19.02282116945982 * 60;
    static constexpr double scenario_rise_c = 23.026876705577994;
    static constexpr double history_s = 600, horizon_s = 300;
    static double forecast(double current, double slope_c_s, double seconds) {
        return current + slope_c_s * tau_s * (-std::expm1(-seconds / tau_s));
    }
    static std::optional<double> crossing(double current, double slope, double risk) {
        if (current >= risk) return 0;
        const double rise = slope * tau_s;
        if (!(rise > risk-current)) return {};
        const double eta = -tau_s * std::log1p(-(risk-current)/rise);
        if (!std::isfinite(eta) || eta > horizon_s) return {};
        return eta;
    }
    void reset() { history_.clear(); last_stamp_=-1; source_.clear(); ambient_source_.clear(); last_ambient_stamp_=-1; }
    nlohmann::json step(const InputSnapshot& s, double now, const Config& cfg,
                        bool fan_or_unknown) {
        using J = nlohmann::json;
        J out={{"enabled",true},{"valid",false},{"control_eligible",false},
          {"model","ambient_heat_balance_observer_v2"},{"validation","research_only"},
          {"source_doi","10.1542/peds.2004-2368"},{"reason","warming_up"},
          {"t35_s",nullptr},{"curve",J::array()},{"history_s",0},
          {"required_history_s",history_s},{"horizon_s",horizon_s},
          {"tau_s",tau_s},{"risk_temp_c",cfg.risk_temp_c},
          {"ambient_used_in_adaptive_forecast",true},
          {"parameter_status","literature_tau_prior_unvalidated_vehicle"},
          {"measured_threshold_reached",false},{"candidate_early_warning",false}};
        auto fail=[&](const char* why) { reset(); out["reason"]=why; return out; };
        if (!std::isfinite(now) || now<0 || (last_now_>=0 && now<last_now_)) {
            last_now_=-1; return fail("clock_invalid");
        }
        last_now_=now;
        if (s.mode!="REAL" && s.mode!="DEMO") return fail("mode_invalid");
        const auto& x=s.temperature;
        if (!x.valid || !std::isfinite(x.value) || x.value < -40 || x.value>100 ||
            !std::isfinite(x.timestamp_s) || x.timestamp_s<0 || x.timestamp_s>now ||
            now-x.timestamp_s>=cfg.temp_timeout_s || x.source.empty() ||
            x.source=="MISSING" || x.source=="REPLAY" ||
            (s.mode=="REAL" && x.source=="DEMO")) return fail("temperature_invalid");
        out["measured_threshold_reached"]=x.value>=cfg.risk_temp_c;
        // A heating-only fit cannot estimate cooling after commanded ventilation.
        if (fan_or_unknown) return fail("fan_active_or_feedback_unknown");
        const auto& ambient=s.ambient;
        if (!ambient.valid || !std::isfinite(ambient.value) || ambient.value < -40 || ambient.value>60 ||
            !std::isfinite(ambient.timestamp_s) || ambient.timestamp_s<0 || ambient.timestamp_s>now ||
            now-ambient.timestamp_s>=cfg.ambient_timeout_s || ambient.source.empty() ||
            ambient.source=="MISSING" || ambient.source=="REPLAY" ||
            (s.mode=="REAL" && ambient.source!="REAL_AMBIENT")) return fail("ambient_invalid");
        if ((!source_.empty() && source_!=x.source) ||
            (!ambient_source_.empty() && ambient_source_!=ambient.source) ||
            (last_stamp_>=0 && (x.timestamp_s<last_stamp_ ||
                               x.timestamp_s-last_stamp_>=cfg.temp_timeout_s)) ||
            (last_ambient_stamp_>=0 && (ambient.timestamp_s<last_ambient_stamp_ ||
               ambient.timestamp_s-last_ambient_stamp_>=cfg.ambient_timeout_s))) reset();
        source_=x.source; ambient_source_=ambient.source;
        last_ambient_stamp_=ambient.timestamp_s;
        if (x.timestamp_s>last_stamp_) {
            last_stamp_=x.timestamp_s;
            if (history_.empty() || x.timestamp_s-history_.back().t>=5.0)
                history_.push_back({x.timestamp_s,x.value,ambient.value});
        }
        while (history_.size()>1 && history_[1].t < x.timestamp_s-history_s)
            history_.pop_front();
        const double span=history_.empty()?0:x.timestamp_s-history_.front().t;
        out["history_s"]=span; out["samples"]=history_.size();
        out["ambient_c"]=ambient.value; out["ambient_source"]=ambient.source;
        // Optional sunny-parked scenario: separate from the live forecast and ETA.
        const auto& a=s.ambient;
        const bool ambient_ok=a.valid && std::isfinite(a.value) &&
            std::isfinite(a.timestamp_s) && a.timestamp_s>=0 && a.timestamp_s<=now &&
            now-a.timestamp_s<cfg.ambient_timeout_s && !a.source.empty() &&
            a.source!="MISSING" && a.source!="REPLAY" && !(s.mode=="REAL" && a.source=="DEMO");
        const bool in_domain=ambient_ok && a.value>=22.222222 && a.value<=35.555556;
        out["ambient_in_study_range"]=ambient_ok?J(in_domain):J(nullptr);
        J scenario={{"valid",in_domain},{"kind","conditional_sunny_parked_scenario"},
                    {"control_eligible",false},{"curve",J::array()},
                    {"note","Assumes sunny parked vehicle; not a forecast of current conditions."}};
        if (in_domain) {
            const double eq=a.value+scenario_rise_c;
            for(int t=0;t<=300;t+=10)
                scenario["curve"].push_back({{"t_s",t},{"temp_c",eq+(x.value-eq)*std::exp(-t/tau_s)}});
        }
        out["scenario"]=scenario;
        if (span<history_s || history_.size()<3) return out;
        // Centered least squares prevents cancellation for host monotonic uptime.
        double mt=0, my=0;
        for(const auto& p:history_) { mt+=p.t-x.timestamp_s; my+=p.temp; }
        mt/=history_.size(); my/=history_.size();
        double xx=0, xy=0;
        for(const auto& p:history_) { const double dt=p.t-x.timestamp_s-mt;
            xx+=dt*dt; xy+=dt*(p.temp-my); }
        if (!(xx>0)) return fail("history_invalid");
        const double slope=xy/xx;
        double error=0;
        for(const auto& p:history_) { const double e=p.temp-(my+slope*(p.t-x.timestamp_s-mt)); error+=e*e; }
        const double rmse=std::sqrt(error/history_.size());
        out["slope_c_min"]=slope*60; out["history_fit_rmse_c"]=rmse;
        // Engineering rejection criteria, not statistical confidence bounds.
        if (!std::isfinite(slope) || std::abs(slope*60)>3 || rmse>2) {
            out["reason"]="trend_unstable"; return out;
        }
        // One-node heat balance: dT/dt=(Ta-T)/tau + q. Identify q=Q/C,
        // not R,C,Q separately. Fit exact interval transitions over paired history.
        double numerator=0, denominator=0;
        for (std::size_t i=1;i<history_.size();++i) {
            const auto& prev=history_[i-1]; const auto& next=history_[i];
            const double loss=-std::expm1(-(next.t-prev.t)/tau_s);
            const double gain=tau_s*loss, ta=(prev.ambient+next.ambient)*0.5;
            numerator+=gain*(next.temp-(1-loss)*prev.temp-loss*ta);
            denominator+=gain*gain;
        }
        if (!(denominator>0)) return fail("history_invalid");
        const double heat=numerator/denominator;
        double replay=history_.front().temp, squared=0;
        for (std::size_t i=1;i<history_.size();++i) {
            const auto& prev=history_[i-1]; const auto& next=history_[i];
            const double loss=-std::expm1(-(next.t-prev.t)/tau_s);
            replay+=( (prev.ambient+next.ambient)*0.5+tau_s*heat-replay)*loss;
            squared+=(replay-next.temp)*(replay-next.temp);
        }
        const double model_rmse=std::sqrt(squared/(history_.size()-1));
        const double effective_slope=(ambient.value-x.value)/tau_s+heat;
        out["heat_rate_c_min"]=heat*60;
        out["model_fit_rmse_c"]=model_rmse;
        out["forecast_initial_rate_c_min"]=effective_slope*60;
        out["equilibrium_c"]=ambient.value+tau_s*heat;
        if (!std::isfinite(heat) || !std::isfinite(effective_slope) ||
            std::abs(effective_slope*60)>3 || model_rmse>2) {
            out["reason"]="heat_balance_unstable"; return out;
        }
        for(int t=0;t<=300;t+=10) {
            const double value=forecast(x.value,effective_slope,t);
            if (!std::isfinite(value) || value < -40 || value>100) {
                out["curve"]=J::array(); out["reason"]="forecast_out_of_range"; return out;
            }
            out["curve"].push_back({{"t_s",t},{"temp_c",value}});
        }
        const auto eta=crossing(x.value,effective_slope,cfg.risk_temp_c);
        out["valid"]=true; out["t35_s"]=eta?J(*eta):J(nullptr);
        out["candidate_early_warning"]=x.value<cfg.risk_temp_c && eta && *eta<=cfg.protect_horizon_s;
        out["reason"]=x.value>=cfg.risk_temp_c?"measured_threshold_reached":
                      eta?"estimated_crossing":"no_crossing_within_5min";
        return out;
    }
};
}
