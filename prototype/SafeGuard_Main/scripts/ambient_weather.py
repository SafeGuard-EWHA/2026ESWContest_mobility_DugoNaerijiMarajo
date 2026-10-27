#!/usr/bin/env python3
"""Open-Meteo model-derived ambient temperature, with bounded cache freshness.

This is a weather-model estimate for the configured location, NOT an on-site
temperature measurement. The API's current.time is its valid time, not a model
publication time. No forecast issue time is invented.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import threading
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


ENDPOINT = "https://api.open-meteo.com/v1/forecast"
MAX_RESPONSE_BYTES = 1024 * 1024


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject(value):
        raise ValueError("non-finite JSON value: " + value)

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite JSON number")
        return parsed

    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                        parse_constant=reject, parse_float=number)
    if not isinstance(result, dict):
        raise ValueError("API response must be one JSON object")
    return result


def setting(config, name, default, minimum, maximum):
    value = config.get(name, default)
    if not finite(value) or not minimum <= value <= maximum:
        raise ValueError(f"ambient_provider.{name} must be {minimum}..{maximum}")
    return float(value)


class AmbientProvider:
    def __init__(self, config, *, clock=time.monotonic, wall_clock=time.time,
                 opener=urlopen):
        if not isinstance(config, dict):
            raise ValueError("ambient_provider must be an object")
        self.enabled = config.get("enabled", False)
        if type(self.enabled) is not bool:
            raise ValueError("ambient_provider.enabled must be boolean")
        self.provider = config.get("provider", "open_meteo")
        if self.provider != "open_meteo":
            raise ValueError("Only ambient_provider.provider=open_meteo is supported")
        self.latitude, self.longitude = config.get("latitude"), config.get("longitude")
        self.location_label = config.get("location_label", "")
        if not isinstance(self.location_label, str) or len(self.location_label) > 200:
            raise ValueError("ambient_provider.location_label must be text up to 200 characters")
        if self.enabled:
            if not finite(self.latitude) or not -90 <= self.latitude <= 90:
                raise ValueError("Set ambient_provider.latitude (-90..90)")
            if not finite(self.longitude) or not -180 <= self.longitude <= 180:
                raise ValueError("Set ambient_provider.longitude (-180..180)")
        self.poll_interval_s = setting(config, "poll_interval_s", 300, 60, 86400)
        self.max_sample_age_s = setting(config, "max_sample_age_s", 1800, 60, 86400)
        self.request_timeout_s = setting(config, "request_timeout_s", 8, 0.5, 30)
        self.future_tolerance_s = setting(config, "future_tolerance_s", 120, 0, 300)
        self.clock, self.wall_clock, self.opener = clock, wall_clock, opener
        self._lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._sample = None
        self._last_error = None
        self._last_attempt_utc = None
        self.source_url = None
        if self.enabled:
            self.source_url = ENDPOINT + "?" + urlencode({
                "latitude": self.latitude, "longitude": self.longitude,
                "current": "temperature_2m", "temperature_unit": "celsius",
                "timezone": "GMT", "timeformat": "unixtime"})

    def _parse(self, payload, wall, mono):
        if payload.get("error"):
            raise ValueError("API error: " + str(payload.get("reason", "unspecified"))[:160])
        units, current = payload.get("current_units"), payload.get("current")
        if not isinstance(units, dict) or not isinstance(current, dict):
            raise ValueError("API response lacks current/current_units")
        if units.get("temperature_2m") != "°C" or units.get("time") != "unixtime":
            raise ValueError("Unexpected temperature/time units")
        if payload.get("utc_offset_seconds", 0) != 0:
            raise ValueError("Expected UTC response")
        temp, epoch, interval = current.get("temperature_2m"), current.get("time"), current.get("interval")
        if not finite(temp) or not -100 <= temp <= 70:
            raise ValueError("Invalid temperature_2m")
        if type(epoch) is not int or epoch <= 0:
            raise ValueError("Invalid current.time")
        if type(interval) is not int or not 1 <= interval <= 3600:
            raise ValueError("Invalid current.interval")
        valid_time, expires = utc(epoch), utc(epoch + self.max_sample_age_s)
        age = wall - epoch
        if age < -self.future_tolerance_s:
            raise ValueError("Provider time is in the future; check Pi UTC clock")
        if age >= self.max_sample_age_s:
            raise ValueError("Provider sample already expired")
        grid_latitude, grid_longitude, elevation = (payload.get("latitude"),
                                                   payload.get("longitude"), payload.get("elevation"))
        return {"temp_c": float(temp), "epoch": epoch, "interval_s": interval,
                "provider_time_utc": valid_time, "expires_utc": expires,
                "received_utc": utc(wall), "accepted_mono": mono,
                "age_at_accept": age,
                "grid_latitude": grid_latitude if finite(grid_latitude) and -90 <= grid_latitude <= 90 else None,
                "grid_longitude": grid_longitude if finite(grid_longitude) and -180 <= grid_longitude <= 180 else None,
                "elevation_m": elevation if finite(elevation) else None,
                "raw_current": dict(current), "raw_units": dict(units)}

    def refresh(self):
        """Attempt one request; network/parse errors preserve only unexpired cache."""
        if not self.enabled:
            return False
        # Only one request may commit a result at a time, but snapshot() never
        # waits on network I/O. The hub runs this method in a separate worker.
        with self._fetch_lock:
            try:
                request = Request(self.source_url, headers={
                    "User-Agent": "SafeGuard-ambient/0.1.0", "Accept": "application/json"})
                with self.opener(request, timeout=self.request_timeout_s) as response:
                    if hasattr(response, "geturl"):
                        final = urlsplit(response.geturl())
                        if final.scheme != "https" or final.hostname != "api.open-meteo.com":
                            raise ValueError("Unexpected API redirect")
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("API response exceeds size limit")
                wall, mono = self.wall_clock(), self.clock()
                if not finite(wall) or wall <= 0 or not finite(mono) or mono < 0:
                    raise ValueError("Invalid local clock")
                candidate = self._parse(strict_json(raw), wall, mono)
                with self._lock:
                    old = self._sample
                    if old:
                        if mono < old["accepted_mono"]:
                            raise ValueError("Monotonic clock regressed")
                        if candidate["epoch"] < old["epoch"]:
                            raise ValueError("Provider sample time regressed")
                        if candidate["epoch"] == old["epoch"]:
                            # An unchanged API valid time cannot renew sample age,
                            # including if the Pi wall clock was moved backwards.
                            candidate["age_at_accept"] = max(candidate["age_at_accept"],
                                old["age_at_accept"] + mono - old["accepted_mono"])
                            if candidate["age_at_accept"] >= self.max_sample_age_s:
                                raise ValueError("Repeated provider sample already expired")
                    self._sample = candidate
                    self._last_error = None
                    self._last_attempt_utc = utc(wall)
                return True
            except Exception as error:
                with self._lock:
                    self._last_error = (type(error).__name__ + ": " + str(error))[:300]
                    try:
                        self._last_attempt_utc = utc(self.wall_clock())
                    except (ValueError, OverflowError, OSError, TypeError):
                        self._last_attempt_utc = None
                return False

    def snapshot(self, now=None):
        mono = self.clock() if now is None else now
        wall = self.wall_clock()
        with self._lock:
            sample = dict(self._sample) if self._sample is not None else None
            error, attempt = self._last_error, self._last_attempt_utc
        result = {"valid": False, "temp_c": None, "status": "awaiting_api",
                  "provider": self.provider, "data_kind": "model_estimate",
                  "onsite_measurement": False, "source_url": self.source_url,
                  "provider_time_utc": None, "source_issued_utc": None,
                  "received_utc": None, "expires_utc": None,
                  "sample_age_s": None, "last_error": error,
                  "last_attempt_utc": attempt,
                  "latitude": self.latitude if finite(self.latitude) else None,
                  "longitude": self.longitude if finite(self.longitude) else None,
                  "location_label": self.location_label,
                  "grid_latitude": None, "grid_longitude": None, "elevation_m": None,
                  "max_sample_age_s": self.max_sample_age_s,
                  "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)"}
        if not self.enabled:
            result["status"] = "ambient_provider_not_configured"
            return result
        if sample is None:
            if error:
                result["status"] = "api_unavailable"
            return result
        for key in ("provider_time_utc", "received_utc", "expires_utc", "interval_s",
                    "grid_latitude", "grid_longitude", "elevation_m"):
            result[key] = sample[key]
        if not finite(mono) or mono < sample["accepted_mono"] or not finite(wall) or wall <= 0:
            result["status"] = "local_clock_invalid"
            return result
        age = max(wall - sample["epoch"],
                  sample["age_at_accept"] + mono - sample["accepted_mono"])
        result["sample_age_s"] = round(max(0.0, age), 3)
        if age < -self.future_tolerance_s:
            result["status"] = "local_clock_invalid"
        elif age >= self.max_sample_age_s:
            result["status"] = "sample_expired"
        else:
            result.update(valid=True, temp_c=sample["temp_c"],
                          status="cached_after_error" if error else "api_sample_available")
        return result

    def audit_record(self):
        result = self.snapshot()
        with self._lock:
            sample = self._sample
            result["api_current"] = dict(sample["raw_current"]) if sample else None
            result["api_current_units"] = dict(sample["raw_units"]) if sample else None
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument("--output", type=Path, help="save one JSON audit record")
    args = parser.parse_args()
    try:
        provider = AmbientProvider({"enabled": True, "latitude": args.latitude,
                                    "longitude": args.longitude})
        provider.refresh()
        record = provider.audit_record()
        text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            # Refuse to silently overwrite an earlier measurement record.
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(text + "\n")
        print(text)
        return 0 if record["valid"] else 1
    except (OSError, ValueError) as error:
        parser.exit(2, "Ambient check failed: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
