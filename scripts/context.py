"""Bounded model handoffs: keep full evidence on disk, fetch only needed rows."""
from __future__ import annotations

import json
from analysis import rows, sanitize

FOCUS_SECTIONS = {
    'drivers': {'devices', 'drivers', 'gpu', 'audio', 'usb', 'network', 'driver_events'},
    'crash': {'events', 'dumps', 'disks', 'disk_reliability', 'resource', 'drivers', 'devices'},
    'boot': {'boot', 'boot_components', 'services', 'startup', 'tasks', 'events', 'resource'},
    'all': None,
}


def compact(report, lang='en', focus='all', max_chars=2400):
    if max_chars < 800:
        raise ValueError('Context limit must be at least 800 characters.')
    selected = FOCUS_SECTIONS[focus]
    def relevant(item):
        if focus == 'all' or item['id'] in ('missing-evidence', 'empty-evidence', 'no-rule-findings', 'incident-timeline'):
            return True
        groups = {'drivers': ('device', 'driver', 'advisory', 'display'),
                  'crash': ('bugcheck', 'restart', 'debugger', 'whea', 'display', 'disk', 'commit'),
                  'boot': ('boot', 'service', 'commit')}
        return any(prefix in item['id'] for prefix in groups[focus])
    candidates = [item for item in report['findings'] if relevant(item)]
    # Fixed metadata and bounded item strings. Detailed evidence is fetched by ID/section.
    result = {'schema_version': 1, 'synthetic': report.get('synthetic', False), 'captured_at': str(report.get('captured_at') or '')[:80],
              'focus': focus, 'findings_count': len(candidates), 'findings': [],
              'not_fully_verified': [name for name, section in report['sections'].items() if section['status'] != 'ok' and (selected is None or name in selected)],
              'limits': 'Evidence summary, not a root-cause verdict. Fetch targeted evidence only.' if lang == 'en' else '这是证据摘要，不是根因结论；按需读取相关证据。',
              'truncated': False}
    result['not_fully_verified'] = result['not_fully_verified'][:12]
    comparison = report.get('comparison')
    if comparison is not None:
        result['comparison_counts'] = {key: len(comparison[key]) for key in ('driver_changes', 'device_changes', 'new_events')}
        result['boot_comparison_status'] = comparison['boot']['status']
    for item in candidates:
        # Keep a small factual anchor, not just prose and an opaque finding ID.
        facts = []
        fact_keys = ('device_key', 'name', 'problem_code', 'present', 'version', 'inf', 'id', 'time', 'bugcheck_code')
        for record in item.get('evidence', [])[:2]:
            facts.append({key: str(record[key])[:100] if isinstance(record[key], str) else record[key]
                          for key in fact_keys if key in record})
        facts = [fact for fact in facts if fact]
        short = {'id': item['id'], 'severity': item['severity'], 'confidence': item['confidence'],
                 'title': item['title'][lang][:100], 'detail': item['detail'][lang][:180],
                 'next_step': item['next_step'][lang][:140], 'evidence_count': len(item.get('evidence', []))}
        if facts:
            short['facts'] = facts
        result['findings'].append(short)
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))) > max_chars:
            # Prefer a compact factual anchor over dropping the whole finding.
            short.pop('detail')
            short.pop('next_step')
            if len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))) > max_chars:
                result['findings'].pop()
                result['truncated'] = True
                break
    result['truncated'] = result['truncated'] or len(result['findings']) < len(candidates)
    if len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))) > max_chars:
        result['not_fully_verified'] = []
    return result


def evidence(snapshot, section, device_key=None, limit=10, max_chars=4000):
    if limit < 1 or limit > 200 or max_chars < 800:
        raise ValueError('Evidence limit must be 1..200 rows and at least 800 characters.')
    snapshot = sanitize(snapshot)
    source = snapshot['sections'].get(section)
    if source is None:
        raise ValueError('Section not found in this snapshot.')
    selected = rows(snapshot, section)
    if device_key:
        selected = [row for row in selected if row.get('device_key') == device_key]
    result = {'section': section, 'status': source['status'], 'reason': str(source.get('reason', ''))[:300],
              'matched_rows': len(selected), 'data': [], 'truncated': False}
    for row in selected[:limit]:
        result['data'].append(row)
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))) > max_chars:
            result['data'].pop()
            break
    result['truncated'] = len(result['data']) < len(selected)
    return result
