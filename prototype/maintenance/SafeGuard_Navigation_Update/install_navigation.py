#!/usr/bin/env python3
"""Install iPhone navigation input over SafeGuard Main + Ambient Update 0.1.0."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root, relative):
    original = root / relative
    if original.is_symlink():
        raise ValueError("Symlink is not an install target: " + str(original))
    resolved = original.resolve()
    if root not in resolved.parents:
        raise ValueError("Path is outside project: " + str(original))
    return resolved


def navigation_config(base, project):
    if base.get("mode") != "REAL" or base.get("profile") != "REAL":
        raise ValueError("Base config must be REAL / REAL")
    for key in ("hardware", "thermal", "actuation"):
        if not isinstance(base.get(key), dict):
            raise ValueError("Missing config object: " + key)
    result = json.loads(json.dumps(base, allow_nan=False))
    result["navigation_extension_version"] = "0.1.0"
    result["ambient_provider"] = {
        "enabled": True, "provider": "open_meteo", "location_mode": "phone",
        "location_label": "iPhone vehicle navigation surrogate",
        "location_file": str(project / "runtime/navigation_location.json"),
        "poll_interval_s": 300, "max_sample_age_s": 1800,
        "request_timeout_s": 8, "future_tolerance_s": 120,
        "location_timeout_s": 15, "max_location_accuracy_m": 200,
        "movement_refresh_m": 100, "min_request_interval_s": 60,
        "max_weather_distance_m": 1000,
    }
    result["actuation"]["enabled"] = False
    result["thermal"]["enabled"] = False
    result["thermal"]["ambient_timeout_s"] = 3.0
    return result


def install(project, *, base_config="configs/real_ambient.json",
            output_config="configs/real_navigation.json", package=ROOT):
    project, package = Path(project).resolve(), Path(package).resolve()
    hashes = json.loads((package / "base_hashes.json").read_text())
    plans = []
    # Dependencies must be the known Ambient Update implementation.
    for rel, expected in hashes["dependencies"].items():
        path = contained(project, rel)
        if not path.is_file() or digest(path) != expected:
            raise ValueError("Ambient dependency differs or missing; share for merging: " + str(path))
    for rel in hashes["files"]:
        src = contained(package, "patch/" + rel)
        dst = contained(project, rel)
        if not src.is_file():
            raise ValueError("Package file missing: " + rel)
        if src.suffix == ".py":
            ast.parse(src.read_text(encoding="utf-8"), filename=rel)
        expected = hashes["files"][rel]
        if dst.exists() and digest(dst) not in {digest(src), expected}:
            raise ValueError("Local code differs; do not overwrite. Share for merging: " + str(dst))
        if expected is not None and not dst.exists():
            raise ValueError("Required existing file missing: " + rel)
        plans.append((src, dst, rel))
    base = contained(project, base_config)
    target = contained(project, output_config)
    if base == target:
        raise ValueError("Original config must not be overwritten")
    config = navigation_config(json.loads(base.read_text(encoding="utf-8")), project)
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != config:
        raise ValueError("Output config differs; choose a new --output-config name")
    if not target.parent.is_dir():
        raise ValueError("Config directory missing")
    runtime = contained(project, "runtime")
    if runtime.exists() and not runtime.is_dir():
        raise ValueError("runtime is not a directory")
    changes = [(s, d, r) for s, d, r in plans if not d.exists() or digest(s) != digest(d)]
    backup = None
    if changes:
        name = datetime.now(timezone.utc).strftime("navigation_%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
        backup = contained(project, "backups/" + name)
        backup.mkdir(parents=True)
        for src, dst, rel in changes:
            if dst.exists():
                old = backup / rel
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, old)
        (backup / "receipt.json").write_text(json.dumps({
            "version": "0.1.0", "files": {r: digest(s) for s,d,r in plans},
            "new_files": [r for s,d,r in changes if not d.exists()],
        }, indent=2) + "\n")
        for src, dst, rel in changes:
            temp = dst.with_name(dst.name + ".navigation-" + uuid.uuid4().hex[:8])
            shutil.copyfile(src, temp)
            temp.replace(dst)
    runtime.mkdir(mode=0o700, exist_ok=True)
    if not target.exists():
        with target.open("x", encoding="utf-8") as out:
            json.dump(config, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write("\n")
    return {"changed_files": len(changes), "backup": str(backup) if backup else None,
            "config": str(target), "location_file": config["ambient_provider"]["location_file"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", type=Path, default=Path.home()/"SafeGuard_Main")
    p.add_argument("--base-config", default="configs/real_ambient.json")
    p.add_argument("--output-config", default="configs/real_navigation.json")
    args = p.parse_args()
    try:
        result = install(args.project, base_config=args.base_config, output_config=args.output_config)
    except (OSError, ValueError, TypeError) as exc:
        p.exit(2, "Install stopped: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Navigation files installed. Phone pairing and actual iPhone test are next.")
    print("Existing configs kept; separate REAL navigation config has actuation and prediction disabled.")


if __name__ == "__main__":
    main()
