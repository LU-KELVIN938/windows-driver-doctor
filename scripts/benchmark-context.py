#!/usr/bin/env python3
"""Reproducible synthetic payload benchmark; no PC inspection or model calls."""
import argparse
import hashlib
import json
from pathlib import Path
from analysis import analyze
from context import compact


def benchmark(lang='en', budget=2400):
    base = json.loads((Path(__file__).resolve().parents[1] / 'examples/demo-snapshot.json').read_text(encoding='utf-8'))
    base['collection']['note'] = 'Synthetic payload-size benchmark, not a diagnosis or model accuracy benchmark.'
    for index in range(400):
        key = hashlib.sha256(f'synthetic-{index}'.encode()).hexdigest()[:16]
        base['sections']['devices']['data'].append({'device_key': key, 'name': f'Synthetic device {index}', 'class': 'System', 'present': True, 'problem_code': 0, 'status': 'OK'})
        base['sections']['drivers']['data'].append({'device_key': key, 'device_name': f'Synthetic device {index}', 'version': f'10.0.{index}.1', 'provider': 'Synthetic OEM', 'date': '2006-06-21', 'inf': f'oem{index + 100}.inf', 'signed': True, 'driver_file': f'synthetic{index}.sys'})
    for index in range(600):
        base['sections']['events']['data'].append({'log': 'Application', 'provider': 'Windows Error Reporting', 'id': 1001, 'record_id': 10000 + index, 'time': '2026-10-03T12:00:00+00:00', 'level': 4, 'bugcheck_code': None})
    report = analyze(base)
    brief = compact(report, lang, 'crash', budget)
    raw = json.dumps(base, ensure_ascii=False, separators=(',', ':'))
    reduced = json.dumps(brief, ensure_ascii=False, separators=(',', ':'))
    return {'synthetic': True, 'comparison': 'Entire compact-serialized snapshot vs one crash-focused compact handoff',
            'language': lang, 'budget_chars': budget, 'snapshot_chars': len(raw), 'summary_chars': len(reduced),
            'character_reduction_percent': round(100 * (1 - len(reduced) / len(raw)), 2),
            'summary_truncated': brief['truncated'],
            'limitations': 'Character payload comparison only. No actual model tokens, bill, accuracy, total-session saving or plain-Codex baseline measured.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', choices=('en', 'zh'), default='en')
    parser.add_argument('--max-chars', type=int, default=2400)
    parser.add_argument('--out', help='Optional results JSON path.')
    args = parser.parse_args()
    result = benchmark(args.lang, args.max_chars)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(output + '\n', encoding='utf-8')
    print(output)
