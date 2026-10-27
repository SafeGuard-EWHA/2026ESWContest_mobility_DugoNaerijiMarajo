#!/usr/bin/env python3
"""Software-only subprocess scenarios. These are NOT hardware performance results."""
import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_case(binary, scenario, profile='simulation'):
    duration = 11 if scenario == 'estop' else (8 if profile == 'simulation' else 2)
    proc = subprocess.run([str(binary), '--config', f'configs/{profile}.json',
                           '--scenario', scenario, '--no-dashboard', '--duration', str(duration)],
                          cwd=ROOT, capture_output=True, text=True, timeout=duration + 10)
    assert proc.returncode == 0, (scenario, proc.stdout, proc.stderr)
    match = re.search(r'Logs: "([^"]+)"', proc.stdout)
    assert match, proc.stdout
    folder = Path(match.group(1))
    rows = [json.loads(x) for x in (folder / 'states.jsonl').read_text().splitlines()]
    raw = [json.loads(x)['payload'] for x in (folder / 'raw_input.jsonl').read_text().splitlines()
           if 'payload' in json.loads(x)]
    assert rows[-1]['stopped'] is True
    assert rows[-1]['inputs']['uwb']['distance_m'] is None
    assert rows[-1]['guardian'] == 'UNKNOWN'
    if profile != 'simulation':
        assert not any(x['occupant'] != 'UNKNOWN' or x['outputs']['fan'] for x in rows)
        assert all(x['outputs']['ack_status'] in ('NOT_SENT_DRY_RUN', 'CONTROLLER_STOPPED') for x in rows)
        for msg in raw:
            if msg.get('source') == 'DEMO':
                assert profile == 'demo' and msg['type'] in ('temperature', 'ambient'), msg
    elif scenario == 'normal':
        assert any(x['state'] == 'PROTECTION' and x['occupant'] == 'CONFIRMED' for x in rows)
        assert not any(x['state'] == 'FAIL_SAFE' for x in rows), 'normal path misclassified as device fault'
    elif scenario == 'mmwave_fault':
        assert any(x['state'] == 'FAIL_SAFE' for x in rows)
        assert any(x['state'] == 'PROTECTION' and x['occupant'] == 'SUSPECTED' for x in rows)
    elif scenario == 'unknown':
        assert any(x['state'] == 'FAIL_SAFE' and x['occupant'] == 'UNKNOWN' for x in rows)
        assert not any(x['outputs']['fan'] or x['occupant'] != 'UNKNOWN' for x in rows)
    elif scenario == 'api_fault':
        assert any(x['state'] == 'PROTECTION' and x['reason'] == 'measured_temperature_at_risk'
                   and not x['thermal']['valid'] for x in rows)
    elif scenario == 'estop':
        estop_rows = [x for x in rows if x['state'] == 'ESTOP']
        assert estop_rows and rows[-1]['state'] == 'ESTOP'
        assert all(not x['outputs']['fan'] and not x['outputs']['buzzer'] for x in estop_rows)
    return {'profile': profile, 'scenario': scenario, 'passed': True,
            'states': sorted({x['state'] for x in rows}), 'run_folder': str(folder)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/safeguard_main')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    cases = [(name, 'simulation') for name in ('normal','mmwave_fault','unknown','api_fault','estop')]
    cases.extend([('normal','real'), ('normal','demo')])
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        futures = [pool.submit(run_case,binary,name,profile) for name,profile in cases]
        results = [f.result() for f in futures]
    report = {'kind': 'SOFTWARE_SIMULATION_NOT_HARDWARE_RESULTS', 'cases': results}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
