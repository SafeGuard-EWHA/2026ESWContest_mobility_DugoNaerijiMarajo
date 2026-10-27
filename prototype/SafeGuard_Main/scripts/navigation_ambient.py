#!/usr/bin/env python3
"""Use a paired iPhone's recent vehicle-location sample for weather requests.

The receiver runs on the same Pi and writes an atomic local state file. Browser
location services are not asserted to be a satellite-only GNSS measurement.
Requested coordinates remain attached to each weather sample; location updates
never relabel a previous area's weather. No fixed-location fallback is used.
"""
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import threading
import time
from urllib.request import urlopen

from ambient_weather import AmbientProvider, finite, setting, strict_json, utc


MAX_LOCATION_BYTES = 16 * 1024


def distance_m(first, second):
    """Great-circle distance sufficient for regional weather cache selection."""
    lat1, lat2 = math.radians(first[0]), math.radians(second[0])
    dlat, dlon = lat2 - lat1, math.radians(second[1] - first[1])
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, value))))


class PhoneAmbientProvider:
    worker_poll_interval_s = 1.0

    def __init__(self, config, *, clock=time.monotonic, wall_clock=time.time,
                 opener=urlopen):
        if not isinstance(config, dict) or config.get("location_mode") != "phone":
            raise ValueError("Phone weather requires location_mode=phone")
        self.clock, self.wall_clock, self.opener = clock, wall_clock, opener
        self._weather_config = dict(config)
        # Even an old static config accidentally containing coordinates cannot
        # become a fallback location in phone mode.
        self._weather_config.pop("latitude", None)
        self._weather_config.pop("longitude", None)
        self._weather_config["enabled"] = False
        self._empty = AmbientProvider(self._weather_config, clock=clock,
                                      wall_clock=wall_clock, opener=opener)
        self.enabled = config.get("enabled", False)
        if type(self.enabled) is not bool:
            raise ValueError("ambient_provider.enabled must be boolean")
        self.poll_interval_s = self._empty.poll_interval_s
        self.location_label = config.get("location_label", "iPhone vehicle location")
        self.location_timeout_s = setting(config, "location_timeout_s", 15, 1, 15)
        self.max_accuracy_m = setting(config, "max_location_accuracy_m", 200, 1, 10000)
        self.future_tolerance_s = setting(config, "location_future_tolerance_s", 5, 0, 30)
        self.movement_refresh_m = setting(config, "movement_refresh_m", 100, 1, 50000)
        self.max_cache_distance_m = setting(config, "max_weather_distance_m", 1000, 1, 50000)
        self.min_request_interval_s = setting(config, "min_request_interval_s", 60, 60, 3600)
        if self.max_cache_distance_m < self.movement_refresh_m:
            raise ValueError("max_weather_distance_m must be >= movement_refresh_m")
        if self.poll_interval_s < self.min_request_interval_s:
            raise ValueError("poll_interval_s must be >= min_request_interval_s")
        path = config.get("location_file")
        if self.enabled and (not isinstance(path, str) or not Path(path).is_absolute()):
            raise ValueError("Phone weather requires an absolute location_file path")
        self.location_file = Path(path) if isinstance(path, str) else None
        self._lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._active = None
        self._last_attempt_mono = None
        self._last_attempt_utc = None
        self._last_error = None
        self._last_requested_location = None
        self._sample_epoch = None
        self._sample_age_anchor = None
        self._sample_mono_anchor = None

    def _location(self, now=None):
        result = {"valid": False, "source": "IPHONE_NAVIGATION",
                  "method": "device_location_services", "status": "await_location",
                  "latitude": None, "longitude": None, "accuracy_m": None,
                  "location_age_s": None, "age_s": None, "error": None}
        if not self.enabled:
            result["status"] = "location_disabled"
            return result
        try:
            mono = self.clock() if now is None else now
            wall = self.wall_clock()
            if not finite(mono) or mono < 0 or not finite(wall) or wall <= 0:
                raise ValueError("invalid local clock")
            with self.location_file.open("rb") as handle:
                raw = handle.read(MAX_LOCATION_BYTES + 1)
            if len(raw) > MAX_LOCATION_BYTES:
                raise ValueError("location file exceeds size limit")
            value = strict_json(raw)
            if (type(value.get("schema_version")) is not int or value["schema_version"] != 1 or
                    value.get("source") != "IPHONE_NAVIGATION" or type(value.get("valid")) is not bool):
                raise ValueError("unexpected location schema/source")
            if not value["valid"]:
                result.update(status="location_unavailable", error=str(value.get("status", "receiver_unavailable"))[:160])
                return result
            lat, lon, accuracy = value.get("latitude"), value.get("longitude"), value.get("accuracy_m")
            if not finite(lat) or not -90 <= lat <= 90 or not finite(lon) or not -180 <= lon <= 180:
                raise ValueError("invalid coordinates")
            if not finite(accuracy) or not 0 <= accuracy <= self.max_accuracy_m:
                raise ValueError("location accuracy outside allowed range")
            seq, session = value.get("seq"), value.get("receiver_session")
            if (type(seq) is not int or seq < 0 or not isinstance(session, str) or
                    not re.fullmatch(r"[0-9a-fA-F]{16,128}", session)):
                raise ValueError("invalid receiver sequence/session")
            timestamp, received, rx, source_age = (value.get("position_timestamp_ms"),
                value.get("received_wall_s"), value.get("rx_monotonic_s"), value.get("source_age_at_receive_s"))
            if any(not finite(v) for v in (timestamp, received, rx, source_age)):
                raise ValueError("invalid location timestamps")
            position_s = timestamp / 1000.0
            if position_s <= 0 or received <= 0 or rx < 0 or source_age < 0 or mono < rx:
                raise ValueError("invalid/regressed location clock")
            at_receive = received - position_s
            if (at_receive < -self.future_tolerance_s or at_receive >= self.location_timeout_s or
                    abs(source_age - max(0.0, at_receive)) > 0.5 or
                    wall - position_s < -self.future_tolerance_s or wall < received - self.future_tolerance_s):
                raise ValueError("inconsistent or future location timestamps")
            age = max(0.0, wall - position_s, source_age + mono - rx)
            result.update(latitude=float(lat), longitude=float(lon), accuracy_m=float(accuracy),
                          location_age_s=round(age, 3), age_s=round(age, 3), receiver_session=session, seq=seq,
                          position_time_utc=utc(position_s), received_utc=utc(received))
            if age >= self.location_timeout_s:
                result["status"] = "location_stale"
            else:
                result.update(valid=True, status="location_fresh")
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, OverflowError) as error:
            result.update(status="location_invalid", error=(type(error).__name__ + ": " + str(error))[:200])
        return result

    @staticmethod
    def _point(location):
        return location["latitude"], location["longitude"]

    def refresh(self):
        """Called once/sec by hub; actual network requests are rate limited."""
        if not self.enabled:
            return False
        with self._fetch_lock:
            now = self.clock()
            location = self._location(now)
            if not location["valid"]:
                return False
            point = self._point(location)
            with self._lock:
                active = self._active
                previous = self._last_attempt_mono
                error = self._last_error
            if previous is not None:
                elapsed = now - previous
                if elapsed < self.min_request_interval_s:
                    return False
                moved = active is None or distance_m(point, (active.latitude, active.longitude)) >= self.movement_refresh_m
                if not moved and error is None and elapsed < self.poll_interval_s:
                    return False
            config = dict(self._weather_config, enabled=True, latitude=point[0], longitude=point[1],
                          location_label=self.location_label)
            candidate = AmbientProvider(config, clock=self.clock, wall_clock=self.wall_clock, opener=self.opener)
            with self._lock:
                self._last_attempt_mono = now
                self._last_attempt_utc = utc(self.wall_clock())
                self._last_requested_location = {"latitude": point[0], "longitude": point[1]}
            success = candidate.refresh()
            sample = candidate.snapshot()
            accepted_mono = self.clock()
            with self._lock:
                if success:
                    epoch = datetime.fromisoformat(sample["provider_time_utc"]).timestamp()
                    age = sample["sample_age_s"]
                    if self._sample_epoch is not None:
                        if epoch < self._sample_epoch or accepted_mono < self._sample_mono_anchor:
                            success = False
                            self._last_error = "Weather sample time or local clock regressed"
                        elif epoch == self._sample_epoch:
                            age = max(age, self._sample_age_anchor + accepted_mono - self._sample_mono_anchor)
                    if success and age >= candidate.max_sample_age_s:
                        success = False
                        self._last_error = "Repeated weather sample expired"
                    if success:
                        self._active = candidate
                        self._sample_epoch, self._sample_age_anchor, self._sample_mono_anchor = epoch, age, accepted_mono
                        self._last_error = None
                elif not success:
                    self._last_error = candidate.snapshot().get("last_error") or "weather request failed"
            # A successful HTTP fetch is not necessarily currently usable: the
            # phone may have moved or stopped sending while the request ran.
            return success and self.snapshot()["valid"]

    def snapshot(self, now=None):
        mono = self.clock() if now is None else now
        location = self._location(mono)
        with self._lock:
            active, error = self._active, self._last_error
            attempt, attempt_mono = self._last_attempt_utc, self._last_attempt_mono
            requested = dict(self._last_requested_location) if self._last_requested_location else None
            age_anchor, mono_anchor = self._sample_age_anchor, self._sample_mono_anchor
        result = active.snapshot(mono) if active is not None else self._empty.snapshot(mono)
        result.update(location_mode="phone", location_label=self.location_label,
                      navigation_location=location, location_timeout_s=self.location_timeout_s,
                      max_location_accuracy_m=self.max_accuracy_m,
                      max_weather_distance_m=self.max_cache_distance_m,
                      query_distance_m=None, last_requested_location=requested,
                      last_attempt_utc=attempt, last_error=error or result.get("last_error"))
        if not self.enabled:
            result.update(valid=False, temp_c=None, status="ambient_provider_not_configured")
            return result
        if not location["valid"]:
            result.update(valid=False, temp_c=None, status=location["status"])
            return result
        if attempt_mono is not None and mono < attempt_mono:
            result.update(valid=False, temp_c=None, status="local_clock_invalid")
            return result
        if active is None:
            result.update(valid=False, temp_c=None,
                          status="api_unavailable" if error else "awaiting_weather_for_location")
            return result
        if mono_anchor is not None:
            if mono < mono_anchor:
                result.update(valid=False, temp_c=None, status="local_clock_invalid")
                return result
            age = max(result.get("sample_age_s") or 0, age_anchor + mono - mono_anchor)
            result["sample_age_s"] = round(age, 3)
            if age >= active.max_sample_age_s:
                result.update(valid=False, temp_c=None, status="sample_expired")
        separation = distance_m(self._point(location), (active.latitude, active.longitude))
        result["query_distance_m"] = round(separation, 1)
        if separation > self.max_cache_distance_m:
            result.update(valid=False, temp_c=None, status="awaiting_weather_for_location")
        elif result["valid"] and error:
            result["status"] = "cached_after_error"
        return result

    def audit_record(self):
        result = self.snapshot()
        with self._lock:
            active = self._active
        if active is not None:
            audit = active.audit_record()
            result.update(api_current=audit.get("api_current"), api_current_units=audit.get("api_current_units"))
        else:
            result.update(api_current=None, api_current_units=None)
        return result
