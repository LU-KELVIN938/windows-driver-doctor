"""Deterministic evidence summaries; never a root-cause oracle."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median

MAX_INPUT = 20 * 1024 * 1024
SENSITIVE_KEYS = {'username', 'computername', 'hostname', 'serial', 'serialnumber', 'uuid',
                  'macaddress', 'ipaddress', 'password', 'token', 'recoverykey', 'instanceid',
                  'pnpdeviceid', 'hardwareid', 'hardwareids', 'deviceid'}


def redact_text(text: str) -> str:
    text = re.sub(r'(?i)[a-z]:[\\/]Users[\\/][^\\/\s\"<>]+', '<user>', text)
    text = re.sub(r'(?i)/home/[^/\s\"<>]+', '<user>', text)
    text = re.sub(r'(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}', '<email>', text)
    def address(match):
        try:
            ip = ipaddress.ip_address(match.group())
            return '<private-ip>' if ip.is_private or ip.is_loopback or ip.is_link_local else match.group()
        except ValueError:
            return match.group()
    # Do not interpret a dot-separated driver version as an IP address.
    text = re.sub(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', address, text)
    return text


def sanitize(value, key=''):
    normalized = re.sub(r'[^a-z]', '', key.lower())
    if normalized in SENSITIVE_KEYS:
        return '<redacted>'
    if isinstance(value, dict):
        return {str(k): sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, key) for v in value]
    if isinstance(value, str):
        if key == 'version' or key.endswith('_version') or key in ('min_version', 'max_version'):
            return value
        if key in ('device_key', 'machine_id'):
            return value if re.fullmatch(r'[0-9a-f]{16,64}', value) else hashlib.sha256(value.encode()).hexdigest()[:16]
        return redact_text(value)
    return value


def load_json(path):
    source = Path(path)
    if source.stat().st_size > MAX_INPUT:
        raise ValueError('Input exceeds the 20 MiB limit.')
    with source.open(encoding='utf-8-sig') as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    return data


def validate_snapshot(snapshot):
    if snapshot.get('schema_version') != 1 or not isinstance(snapshot.get('sections'), dict):
        raise ValueError('Expected snapshot schema_version 1 and a sections object.')
    for name, section in snapshot['sections'].items():
        if not isinstance(section, dict) or section.get('status') not in ('ok', 'partial', 'not_verified'):
            raise ValueError(f'Invalid section status: {name}')
        if not isinstance(section.get('data'), list) or any(not isinstance(item, dict) for item in section['data']):
            raise ValueError(f'Section data must be a list of objects: {name}')
    return snapshot


def rows(snapshot, name):
    section = snapshot['sections'].get(name, {})
    return section.get('data', []) if section.get('status') in ('ok', 'partial') else []


def integer(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, str) and value.lower().startswith('0x'):
            return int(value, 16)
        number = int(value)
        return number if number == float(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def pair(en, zh):
    return {'en': en, 'zh': zh}


def finding(key, severity, confidence, title, detail, next_step, evidence=None):
    return {'id': key, 'severity': severity, 'confidence': confidence,
            'title': pair(*title), 'detail': pair(*detail), 'next_step': pair(*next_step),
            'evidence': evidence or []}


def parse_debugger(text):
    result = {}
    for field in ('BUGCHECK_CODE', 'IMAGE_NAME', 'MODULE_NAME', 'SYMBOL_NAME', 'FAILURE_BUCKET_ID', 'PROCESS_NAME'):
        match = re.search(r'^\s*' + field + r'\s*:\s*([^\r\n]+)', text, re.M | re.I)
        if match:
            result[field.lower()] = redact_text(match.group(1).strip())
    result['symbol_warnings'] = bool(re.search(r'symbols? could not|wrong symbols|unable to load image|symbol file could not|could not be loaded', text, re.I))
    result['analysis_present'] = bool(result.get('bugcheck_code') or result.get('failure_bucket_id'))
    result['interpretation'] = pair('Named modules are investigative leads, not proven culprits.', '出现的模块是调查线索，不等于已证实的元凶。')
    return result


def numeric_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){0,7}', value):
        return None
    parts = tuple(int(part) for part in value.split('.'))
    return parts + (0,) * (8 - len(parts))


def match_advisories(snapshot, source):
    if source.get('schema_version') != 1 or not isinstance(source.get('advisories'), list):
        raise ValueError('Invalid advisory list schema.')
    findings = []
    for index, advisory in enumerate(source['advisories']):
        if not isinstance(advisory, dict):
            raise ValueError('Advisory entries must be objects.')
        driver_file = advisory.get('driver_file', '')
        if not isinstance(driver_file, str) or not re.fullmatch(r'[\w.-]+\.sys', driver_file, re.I):
            raise ValueError('Advisory driver_file must be a .sys basename.')
        url = advisory.get('source_url', '')
        if not isinstance(url, str) or not re.fullmatch(r'https://[^\s/]+(?:/[^\s]*)?', url):
            raise ValueError('Advisory source_url must be an HTTPS URL.')
        low, high = numeric_version(advisory.get('min_version')), numeric_version(advisory.get('max_version'))
        if low is None or high is None or low > high:
            raise ValueError('Advisory requires an ordered numeric version range.')
        provider = advisory.get('provider_contains', '')
        if not isinstance(provider, str):
            raise ValueError('provider_contains must be a string.')
        for driver in rows(snapshot, 'drivers'):
            if str(driver.get('driver_file', '')).casefold() != driver_file.casefold():
                continue
            if provider.casefold() not in str(driver.get('provider', '')).casefold():
                continue
            version = numeric_version(driver.get('version'))
            if version is not None and not low <= version <= high:
                continue
            uncertain = version is None
            findings.append(finding(f'advisory-{index}-{driver.get("device_key", "unknown")}', 'info', 'incomplete' if uncertain else 'hypothesis',
                ('Vendor advisory candidate', '厂商公告候选线索'),
                ('Version could not be matched. Validate this local advisory with the vendor.' if uncertain else 'Installed version falls within a user-supplied range. Source applicability is not verified.',
                 '无法匹配版本，需向厂商核实本地公告。' if uncertain else '已安装版本落入用户提供的区间；公告真实性与适用性尚未验证。'),
                ('Verify the exact hardware, bulletin and affected version range before changing a driver.', '先核实硬件、官方公告及受影响版本，再考虑修改驱动。'),
                [{**driver, 'source_url': url, 'reviewed_on': advisory.get('reviewed_on'), 'advisory_id': advisory.get('id')}]))
    return findings


def analyze(snapshot, debugger_text=None, advisories=None, incident_time=None):
    validate_snapshot(snapshot)
    snapshot = sanitize(snapshot)
    findings = []
    unavailable = [{'section': name, 'status': section['status'], 'reason': section.get('reason', '')}
                   for name, section in snapshot['sections'].items() if section['status'] != 'ok']
    if unavailable:
        findings.append(finding('missing-evidence', 'info', 'incomplete',
            ('Some checks were not fully verified', '部分检查未完整验证'),
            ('Unavailable evidence is not a healthy result.', '无法读取的证据不能解释成正常。'),
            ('Request only the specific missing evidence needed to answer the symptom.', '仅在影响判断时申请补充相关证据。'), unavailable))
    if not snapshot['sections']:
        findings.append(finding('empty-evidence', 'info', 'incomplete', ('No evidence sections', '没有证据数据'),
            ('This snapshot contains no diagnostic sections.', '此快照没有可供诊断的检查数据。'),
            ('Collect a bounded snapshot before drawing conclusions.', '先采集有边界的快照再下结论。')))

    active, uncertain, detached = [], [], []
    for device in rows(snapshot, 'devices'):
        code = integer(device.get('problem_code'))
        if code == 45 or device.get('present') is False:
            detached.append(device)
        elif code is not None and code != 0:
            linked = dict(device)
            linked['matching_drivers'] = [d for d in rows(snapshot, 'drivers') if device.get('device_key') and d.get('device_key') == device['device_key']][:4]
            linked['configuration_events'] = [e for e in rows(snapshot, 'driver_events') if device.get('device_key') and e.get('device_key') == device['device_key']][:5]
            (active if device.get('present') is True else uncertain).append(linked)
    for key, evidence, confidence in [('device-problems', active, 'observed'), ('device-presence-unknown', uncertain, 'incomplete')]:
        if evidence:
            findings.append(finding(key, 'warning', confidence, ('PnP problem codes need review', 'PnP 故障代码需要检查'),
                ('A device reports a nonzero problem code. Verify presence and the affected function.', '设备报告非零故障代码，需核实连接状态与受影响功能。'),
                ('Identify the exact device and OEM package; do not bulk-remove devices.', '核实具体设备和 OEM 驱动包，不要批量删除设备。'), evidence))
    if detached:
        findings.append(finding('detached-devices', 'info', 'observed', ('Detached devices kept separate', '已断开设备单独记录'),
            (f'{len(detached)} detached/code-45 devices are not classified as active failures.', f'{len(detached)} 个已断开或代码 45 的设备未被归类为当前故障。'),
            ('Investigate only if the user expected the device to be connected.', '仅在该设备本应连接时进一步检查。'), detached[:20]))

    unsigned = [d for d in rows(snapshot, 'drivers') if d.get('signed') is False]
    if unsigned:
        findings.append(finding('unsigned-driver-metadata', 'info', 'hypothesis', ('Unsigned-driver metadata', '驱动签名元数据'),
            ('The inventory reports unsigned entries; this does not establish maliciousness or a crash cause.', '清单中存在未签名条目，不代表恶意软件或蓝屏原因。'),
            ('Verify the file signature and vendor package for the affected device.', '核实相关文件签名及厂商驱动包。'), unsigned))

    events = rows(snapshot, 'events')
    if incident_time is not None:
        incident = timestamp(incident_time)
        if incident is None:
            raise ValueError('Incident time must be ISO-8601 with an explicit timezone offset.')
        nearby = [e for e in events if timestamp(e.get('time')) and abs(timestamp(e['time']) - incident) <= timedelta(minutes=30)]
        configuration = [e for e in rows(snapshot, 'driver_events') if timestamp(e.get('time')) and incident - timedelta(days=7) <= timestamp(e['time']) <= incident]
        findings.append(finding('incident-timeline', 'info', 'hypothesis' if nearby or configuration else 'incomplete',
            ('Incident-centered timeline', '以事故时间为中心的时间线'),
            ('Events within ±30 minutes and device configuration records from the preceding seven days are candidates for correlation, not proof of causality.', '前后 30 分钟事件与之前七天的设备配置记录属于关联候选，不代表因果关系。'),
            ('Confirm the affected device/workload and cross-check event and dump timestamps.', '确认受影响设备或负载，并核对事件及转储时间。'),
            [{'incident_time': incident_time, 'nearby_events': nearby[:20], 'prior_configuration_events': configuration[:20]}]))
    crashes = [e for e in events if str(e.get('log', '')).lower() == 'system' and integer(e.get('id')) == 1001
               and str(e.get('provider', '')).lower() == 'microsoft-windows-wer-systemerrorreporting']
    abrupt = [e for e in events if str(e.get('log', '')).lower() == 'system' and integer(e.get('id')) == 41
              and str(e.get('provider', '')).lower() == 'microsoft-windows-kernel-power']
    bugcheck_power = [e for e in abrupt if (integer(e.get('bugcheck_code')) or 0) > 0]
    if crashes or bugcheck_power:
        findings.append(finding('bugcheck-recorded', 'warning', 'observed', ('Bugcheck evidence recorded', '存在蓝屏错误检查证据'),
            ('A provider-specific bugcheck event or nonzero Kernel-Power bugcheck code was captured. Cause remains unproven.', '采集到对应提供程序的错误检查事件或非零蓝屏代码，原因仍未证实。'),
            ('Correlate the incident time with a matching dump and analyze it with Microsoft symbols.', '对应事故时间查找转储并使用微软符号分析。'), crashes + bugcheck_power))
    no_code = [e for e in abrupt if not (integer(e.get('bugcheck_code')) or 0)]
    if no_code:
        findings.append(finding('unexpected-restart', 'warning', 'incomplete', ('Unexpected-restart evidence', '存在异常重启证据'),
            ('Event 41 without a nonzero bugcheck code cannot prove a BSOD, driver fault or failed power supply.', '事件 41 未带非零蓝屏代码，不能据此确认蓝屏、驱动故障或电源损坏。'),
            ('Check for forced shutdown, power interruption and matching crash artifacts.', '检查强制关机、供电中断以及对应崩溃记录。'), no_code))

    for key, selected, title, detail, next_step in [
        ('display-recovery', [e for e in events if integer(e.get('id')) == 4101 and str(e.get('provider', '')).lower() == 'display'],
         ('Display recovery events', '显示恢复事件'), ('Windows recorded display-driver recovery; it does not identify a definitive cause.', 'Windows 记录了显示驱动恢复，尚不能确定根本原因。'),
         ('Correlate workload, exact GPU driver version, power and hardware telemetry.', '对应负载、具体显卡驱动版本、供电与硬件观测数据。')),
        ('whea-events', [e for e in events if str(e.get('provider', '')).lower() == 'microsoft-windows-whea-logger'],
         ('WHEA hardware-error telemetry', 'WHEA 硬件错误遥测'), ('Hardware-error events require severity and payload review; a component is not proven failed.', '需进一步检查硬件错误事件的严重程度与内容，尚未证实某部件损坏。'),
         ('Review the matching WHEA record and corroborating diagnostics before replacing hardware.', '检查对应 WHEA 记录和其他诊断证据，再考虑更换硬件。')),
        ('service-events', [e for e in events if integer(e.get('id')) in (7000, 7009, 7011, 7023, 7031) and str(e.get('provider', '')).lower() == 'service control manager'],
         ('Service errors or timeouts', '服务错误或超时'), ('Service failures can delay startup; a service event alone does not establish a driver fault.', '服务异常可能延迟启动，单条服务事件不能确定驱动故障。'),
         ('Inspect the exact service and dependency timeline; preserve security and device services.', '检查具体服务及依赖时间线，保留安全和设备服务。')),
    ]:
        if selected:
            findings.append(finding(key, 'info', 'observed', title, detail, next_step, selected))

    bad_disks = [d for d in rows(snapshot, 'disks') if str(d.get('health', '')).lower() not in ('', 'healthy', 'unknown', '0')]
    if bad_disks:
        findings.append(finding('disk-health', 'warning', 'observed', ('Storage health needs review', '存储健康状态需要检查'),
            ('The storage provider reports a non-healthy state. This is separate from driver causality.', '存储提供程序报告非健康状态；这与驱动是否导致故障是不同问题。'),
            ('Confirm backups and inspect storage evidence before repair or stress testing.', '先确认备份，再检查存储证据；不要立即修复或压力测试。'), bad_disks))
    for resource in rows(snapshot, 'resource'):
        commit = integer(resource.get('commit_percent'))
        if commit is not None and commit >= 85:
            findings.append(finding('commit-pressure', 'warning', 'observed', ('High commit-memory pressure', '较高的提交内存压力'),
                (f'Captured commit usage is {commit}%; this is a momentary observation, not proof of a driver leak.', f'采集时提交内存使用率为 {commit}%；这是瞬时观测，不代表已证实驱动泄漏。'),
                ('Correlate the workload and repeated samples before blaming drivers.', '结合负载和多次采样，再判断是否与驱动有关。'), [resource]))

    boots = [b for b in rows(snapshot, 'boot') if integer(b.get('boot_ms')) is not None and integer(b['boot_ms']) >= 0 and timestamp(b.get('time'))]
    boots.sort(key=lambda b: timestamp(b['time']), reverse=True)
    if boots:
        seconds = integer(boots[0]['boot_ms']) / 1000
        prior = [integer(b['boot_ms']) / 1000 for b in boots[1:20]]
        baseline = f'; earlier median {median(prior):.1f}s across {len(prior)} records' if prior else '; no earlier valid baseline'
        findings.append(finding('boot-baseline', 'info', 'observed', ('Recorded boot timing', '已记录的开机耗时'),
            (f'Latest Event 100: {seconds:.1f}s{baseline}. Restart versus hybrid boot mode is not established.', f'最近 Event 100：{seconds:.1f} 秒；先前有效记录 {len(prior)} 条。尚未确定是完整重启还是混合启动。'),
            ('Compare the same metric after a genuine restart and account for updates or hybrid startup.', '在真实重启后对比相同指标，并考虑系统更新与混合启动。'), boots[:20]))

    if advisories is not None:
        findings.extend(match_advisories(snapshot, advisories))
    debugger = parse_debugger(debugger_text) if debugger_text is not None else None
    if debugger is not None:
        findings.append(finding('debugger-lead', 'info', 'incomplete' if debugger['symbol_warnings'] or not debugger['analysis_present'] else 'hypothesis',
            ('Saved debugger evidence', '已保存的调试器证据'),
            ('Debugger fields are leads; symbol problems, truncated dumps and corruption can misidentify the visible module.', '调试字段属于线索；符号问题、转储不完整或内存损坏可能使可见模块被误判。'),
            ('Review the stack, device association and alternative causes before declaring a culprit.', '核实调用栈、设备关联及其他可能原因，再确定责任模块。'), [debugger]))
    if not findings:
        findings.append(finding('no-rule-findings', 'info', 'incomplete', ('No findings from the bounded rules', '有限规则未产生异常条目'),
            ('This does not establish a fault-free PC or exclude an intermittent driver problem.', '这不能证明电脑没有问题，也不能排除间歇性驱动故障。'),
            ('Use the actual symptom and occurrence time to target further evidence.', '结合实际症状和发生时间补充针对性证据。')))
    findings.sort(key=lambda item: (item['severity'] != 'warning', item['id']))
    return {'schema_version': 1, 'captured_at': snapshot.get('captured_at'), 'synthetic': bool(snapshot.get('synthetic')),
            'machine_id': snapshot.get('machine_id'), 'findings': findings, 'debugger': debugger,
            'sections': snapshot['sections'], 'collection': snapshot.get('collection', {})}


def compare(before, after):
    validate_snapshot(before)
    validate_snapshot(after)
    before, after = sanitize(before), sanitize(after)
    if not before.get('machine_id') or before.get('machine_id') != after.get('machine_id'):
        raise ValueError('Snapshot comparison requires the same nonempty machine_id.')
    start, end = timestamp(before.get('captured_at')), timestamp(after.get('captured_at'))
    if start is None or end is None or end <= start:
        raise ValueError('After snapshot must have a later timezone-aware captured_at.')
    result = {'before': before['captured_at'], 'after': after['captured_at'], 'driver_changes': [],
              'device_changes': [], 'new_events': [], 'boot': {'status': 'not_verified'}, 'unavailable': []}
    for section_name, output_name, fields in [('drivers', 'driver_changes', ('version', 'provider', 'inf')),
                                               ('devices', 'device_changes', ('present', 'problem_code', 'status'))]:
        if any(s['sections'].get(section_name, {}).get('status') != 'ok' for s in (before, after)):
            result['unavailable'].append(section_name)
            continue
        # Some devices have multiple signed-driver entries; package identity matters.
        def identity(item):
            key = item.get('device_key')
            return (key, item.get('inf', '')) if section_name == 'drivers' and key else key
        old = {identity(item): item for item in rows(before, section_name) if identity(item)}
        new = {identity(item): item for item in rows(after, section_name) if identity(item)}
        for key in sorted(old.keys() | new.keys(), key=str):
            a, b = old.get(key), new.get(key)
            if a is None or b is None or any(a.get(f) != b.get(f) for f in fields):
                result[output_name].append({'change': 'added' if a is None else 'removed' if b is None else 'changed', 'before': a, 'after': b})
    if any(s['sections'].get('events', {}).get('status') != 'ok' for s in (before, after)):
        result['unavailable'].append('events')
    else:
        def event_key(event):
            return tuple(event.get(k) for k in ('log', 'provider', 'id', 'record_id', 'time'))
        known = {event_key(event) for event in rows(before, 'events')}
        result['new_events'] = [e for e in rows(after, 'events') if event_key(e) not in known and timestamp(e.get('time')) and start < timestamp(e['time']) <= end]
    valid_boots = []
    for snapshot in (before, after):
        boots = [b for b in rows(snapshot, 'boot') if timestamp(b.get('time')) and integer(b.get('boot_ms')) is not None]
        valid_boots.append(max(boots, key=lambda b: timestamp(b['time'])) if boots else None)
    old, new = valid_boots
    if old and new:
        new_time = timestamp(new['time'])
        if (old.get('record_id'), old.get('time')) == (new.get('record_id'), new.get('time')) or not start < new_time <= end:
            result['boot'] = {'status': 'same_or_unconfirmed_boot', 'note': 'No distinct post-baseline Event 100 was confirmed.'}
        else:
            result['boot'] = {'status': 'distinct_records_mode_unverified', 'before_seconds': integer(old['boot_ms']) / 1000,
                              'after_seconds': integer(new['boot_ms']) / 1000,
                              'delta_seconds': (integer(new['boot_ms']) - integer(old['boot_ms'])) / 1000,
                              'note': 'Different records; full restart versus hybrid/resume and servicing effects remain unverified.'}
    return result
