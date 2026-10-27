#!/usr/bin/env python3
"""Evaluate real SafeGuard measurements without generating sample values."""
import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


class DataError(ValueError):
    pass


HEADERS = {
    "power": "boundary,time_s,voltage_v,current_a,state",
    "uwb": "mode,condition,run_id,reference_m,measured_m",
    "thermal": "mode,run_id,t0_s,horizon_s,predicted_c,measured_time_s,measured_future_c",
    "occupancy": "mode,condition,trial_id,truth_present,predicted_present",
}


def field(row, key):
    value = row.get(key, "").strip()
    if not value:
        raise DataError(f"line {row['_line']}: {key} is required")
    return value


def number(row, key, *, optional=False, nonnegative=False):
    value = row.get(key, "").strip()
    if optional and not value:
        return None
    try:
        result = float(value)
    except ValueError:
        raise DataError(f"line {row['_line']}: {key} must be a finite number")
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise DataError(f"line {row['_line']}: invalid {key}={value!r}")
    return result


def read_rows(path, kind):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise DataError("duplicate CSV header")
        missing = set(HEADERS[kind].split(",")) - set(headers)
        if missing:
            raise DataError("missing columns: " + ", ".join(sorted(missing)))
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise DataError(f"line {reader.line_num}: wrong number of CSV fields")
            row["_line"] = reader.line_num
            rows.append(row)
    return rows


def real_rows(rows):
    included, excluded = [], Counter()
    for row in rows:
        mode = field(row, "mode")
        if mode == "REAL":
            included.append(row)
        elif mode in {"DEMO", "REPLAY", "SIMULATED"}:
            excluded[mode] += 1
        else:
            raise DataError(f"line {row['_line']}: unsupported mode {mode!r}")
    return included, dict(excluded)


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def errors_summary(errors):
    return {
        "paired_count": len(errors),
        "mae": statistics.fmean(abs(error) for error in errors) if errors else None,
        "bias": statistics.fmean(errors) if errors else None,
        "rmse": math.sqrt(statistics.fmean(error * error for error in errors)) if errors else None,
        "error_std_population": statistics.pstdev(errors) if errors else None,
    }


def power(rows):
    groups = defaultdict(list)
    for row in rows:
        boundary, state = field(row, "boundary"), field(row, "state")
        t = number(row, "time_s", nonnegative=True)
        volts = number(row, "voltage_v", nonnegative=True)
        amps = number(row, "current_a", nonnegative=True)
        watts = volts * amps
        if not math.isfinite(watts):
            raise DataError(f"line {row['_line']}: V*I overflow")
        if groups[boundary] and t <= groups[boundary][-1][0]:
            raise DataError(f"line {row['_line']}: time_s must strictly increase within {boundary!r}")
        groups[boundary].append((t, watts, state))
    output = []
    for boundary, samples in sorted(groups.items()):
        states = defaultdict(lambda: {"duration_s": 0.0, "energy_j": 0.0})
        intervals = []
        for previous, following in zip(samples, samples[1:]):
            dt = following[0] - previous[0]
            states[previous[2]]["duration_s"] += dt
            states[previous[2]]["energy_j"] += previous[1] * dt
            intervals.append(dt)
        duration = sum(value["duration_s"] for value in states.values())
        energy = sum(value["energy_j"] for value in states.values())
        for value in states.values():
            value["mean_power_w"] = value["energy_j"] / value["duration_s"]
        output.append({
            "boundary": boundary, "sample_count": len(samples),
            "status": "ok" if intervals else "insufficient_data",
            "duration_s": duration, "energy_j": energy if intervals else None,
            "mean_power_w": ratio(energy, duration),
            "max_sample_interval_s": max(intervals) if intervals else None,
            "states": dict(states),
        })
    return {"boundaries": output, "method": "left_rectangle_VI_dt", "combined_total": None,
            "note": "No cross-boundary sum: boundaries may overlap. Last sample has no inferred duration."}


def uwb(rows):
    groups = defaultdict(lambda: {"rows": 0, "missing": 0, "errors": []})
    for row in rows:
        key = (field(row, "condition"), field(row, "run_id"))
        reference = number(row, "reference_m", nonnegative=True)
        measured = number(row, "measured_m", optional=True, nonnegative=True)
        group = groups[key]
        group["rows"] += 1
        if measured is None:
            group["missing"] += 1
        else:
            group["errors"].append(measured - reference)
    return {"unit": "m", "error": "measured-reference", "groups": [
        {"condition": key[0], "run_id": key[1], "sample_count": g["rows"],
         "missing_count": g["missing"], "missing_rate": ratio(g["missing"], g["rows"]),
         "status": "ok" if g["errors"] else "insufficient_data", **errors_summary(g["errors"])}
        for key, g in sorted(groups.items())]}


def thermal(rows):
    groups = defaultdict(lambda: {"rows": 0, "missing": 0, "errors": []})
    seen = set()
    for row in rows:
        run = field(row, "run_id")
        t0 = number(row, "t0_s", nonnegative=True)
        horizon = number(row, "horizon_s", nonnegative=True)
        if horizon <= 0:
            raise DataError(f"line {row['_line']}: horizon_s must be > 0")
        identity = (run, t0, horizon)
        if identity in seen:
            raise DataError(f"line {row['_line']}: duplicate forecast {identity}")
        seen.add(identity)
        predicted = number(row, "predicted_c", optional=True)
        measured = number(row, "measured_future_c", optional=True)
        measured_time = number(row, "measured_time_s", optional=True, nonnegative=True)
        if measured is not None and measured_time is None:
            raise DataError(f"line {row['_line']}: measured_time_s required with measured_future_c")
        if measured_time is not None and not math.isclose(measured_time, t0 + horizon, rel_tol=0, abs_tol=1e-6):
            raise DataError(f"line {row['_line']}: measured_time_s must match t0_s+horizon_s")
        group = groups[horizon]
        group["rows"] += 1
        if predicted is None or measured is None:
            group["missing"] += 1
        else:
            group["errors"].append(predicted - measured)
    return {"unit": "degC", "error": "prediction_at_t0_minus_measurement_at_t0_plus_horizon",
            "groups": [{"horizon_s": horizon, "sample_count": g["rows"],
                        "incomplete_count": g["missing"],
                        "status": "ok" if g["errors"] else "insufficient_data",
                        **errors_summary(g["errors"])} for horizon, g in sorted(groups.items())]}


def occupancy(rows):
    groups, seen = defaultdict(Counter), set()
    for row in rows:
        condition, trial = field(row, "condition"), field(row, "trial_id")
        if (condition, trial) in seen:
            raise DataError(f"line {row['_line']}: duplicate trial {condition!r}/{trial!r}")
        seen.add((condition, trial))
        truth = field(row, "truth_present")
        prediction = row["predicted_present"].strip()
        if truth not in {"0", "1"} or prediction not in {"", "0", "1"}:
            raise DataError(f"line {row['_line']}: truth must be 0/1; prediction 0/1 or blank")
        outcome = ("UNKNOWN_POS" if truth == "1" else "UNKNOWN_NEG") if not prediction else {
            ("1", "1"): "TP", ("1", "0"): "FN", ("0", "1"): "FP", ("0", "0"): "TN"
        }[(truth, prediction)]
        groups[condition][outcome] += 1
    output = []
    for condition, c in sorted(groups.items()):
        counts = {key: c[key] for key in ("TP", "FN", "FP", "TN", "UNKNOWN_POS", "UNKNOWN_NEG")}
        known_positive, known_negative = c["TP"] + c["FN"], c["FP"] + c["TN"]
        positive, negative = known_positive + c["UNKNOWN_POS"], known_negative + c["UNKNOWN_NEG"]
        output.append({"condition": condition, "trial_count": positive + negative, **counts,
                       "sensitivity_known_predictions": ratio(c["TP"], known_positive),
                       "false_positive_rate_known_predictions": ratio(c["FP"], known_negative),
                       "positive_prediction_coverage": ratio(known_positive, positive),
                       "negative_prediction_coverage": ratio(known_negative, negative),
                       "detected_fraction_all_positive_trials": ratio(c["TP"], positive)})
    return {"groups": output, "note": "UNKNOWN is not a negative or a safe result; known-only rates exclude it and coverage reports it."}


def evaluate(kind, path):
    rows = read_rows(path, kind)
    input_count = len(rows)
    excluded = {}
    if kind != "power":
        rows, excluded = real_rows(rows)
    result = {"analysis": kind, "input_rows": input_count, "evaluated_rows": len(rows),
              "excluded_modes": excluded, "status": "ok" if rows else "insufficient_data"}
    result.update({"power": power, "uwb": uwb, "thermal": thermal, "occupancy": occupancy}[kind](rows))
    if kind == "power":
        available = any(group["duration_s"] > 0 for group in result["boundaries"])
    elif kind in {"uwb", "thermal"}:
        available = any(group["paired_count"] > 0 for group in result["groups"])
    else:
        available = any(sum(group[key] for key in ("TP", "FN", "FP", "TN")) for group in result["groups"])
    result["metrics_available"] = bool(available)
    if not available:
        result["status"] = "insufficient_data"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", choices=HEADERS)
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    try:
        encoded = json.dumps(evaluate(args.analysis, args.csv_path), ensure_ascii=False, indent=2, allow_nan=False)
    except (OSError, UnicodeError, csv.Error, ValueError, OverflowError) as exc:
        print(f"Measurement error: {exc}", file=sys.stderr)
        return 2
    print(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
