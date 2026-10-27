#!/usr/bin/env python3
"""Summarize the latest main run, distinguishing past valid data from final status."""
import argparse
import json
from pathlib import Path


def inspect(project):
    candidates=list((project/'runs').glob('*/states.jsonl'))
    if not candidates:
        raise ValueError('No main run found. Run real_navigation.json first.')
    states=max(candidates,key=lambda p:p.stat().st_mtime_ns)
    count=0;last_valid=None
    with states.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():continue
            row=json.loads(line).get('inputs',{}).get('ambient',{})
            if row.get('valid') is True and row.get('source')=='REAL_AMBIENT':
                count+=1;last_valid=row
    latest=None;last_navigation_valid=None
    raw=states.with_name('raw_input.jsonl')
    if raw.exists():
        with raw.open(encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():continue
                record=json.loads(line)
                row=record.get('payload',record)
                if row.get('type')=='ambient' and row.get('location_mode')=='phone':
                    latest=row
                    if row.get('valid') is True:last_navigation_valid=row
    return {'LOG':str(states),'MAIN_VALID_RECORDS':count,'LAST_VALID_MAIN_INPUT':last_valid,
            'PHONE_WEATHER_RECORD_FOUND':latest is not None,
            'LAST_PHONE_WEATHER_STATUS':latest.get('status') if latest else None,
            'LAST_VALID_PHONE_WEATHER': {key:last_navigation_valid.get(key) for key in (
                'temp_c','navigation_location','latitude','longitude','provider_time_utc','received_utc','data_kind')}
                if last_navigation_valid else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path.home()/'SafeGuard_Main')
    args=parser.parse_args()
    try:result=inspect(args.project.resolve())
    except (OSError,ValueError,TypeError) as exc:parser.exit(2,'Check stopped: '+str(exc)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('This summarizes saved records, not current live phone connectivity.')

if __name__=='__main__':main()
