#!/usr/bin/env python3
"""Windows Driver Doctor — English-first CLI, local evidence, bilingual reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from analysis import MAX_INPUT, analyze, compare, load_json, redact_text, sanitize, validate_snapshot
from context import compact, evidence
from reporting import render_html, render_markdown

VERSION = '0.1.0'
REPORT_FILES = ('snapshot.json', 'findings.json', 'summary.json', 'report.md', 'report.html', 'manifest.json')


def output_directory(path, overwrite=False, extra=()):
    directory = Path(path).resolve()
    if directory.exists() and not directory.is_dir():
        raise ValueError('Output path must be a directory.')
    existing = [name for name in (*REPORT_FILES, *extra) if (directory / name).exists()]
    if existing and not overwrite:
        raise ValueError('Output files already exist; choose a new directory or pass --overwrite.')
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_text(path, text):
    target = Path(path)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=target.parent, delete=False, suffix='.tmp') as stream:
        name = stream.name
        try:
            stream.write(text)
        except BaseException:
            stream.close()
            Path(name).unlink(missing_ok=True)
            raise
    try:
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def source_hash():
    hasher = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*')):
        if path.suffix in ('.py', '.ps1'):
            hasher.update(path.name.encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def save_report(directory, snapshot, report, args, input_hashes, extra_files=()):
    snapshot = sanitize(snapshot)
    summary = compact(report, args.lang, args.focus, args.max_chars)
    write_json(directory / 'snapshot.json', snapshot)
    write_json(directory / 'findings.json', report)
    write_json(directory / 'summary.json', summary)
    write_text(directory / 'report.md', render_markdown(report, args.lang))
    write_text(directory / 'report.html', render_html(report, args.lang))
    files = (*REPORT_FILES[:-1], *extra_files)
    raw_chars = len(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')))
    summary_chars = len(json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    manifest = {'tool': 'windows-driver-doctor', 'version': VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
                'command': args.command, 'settings': {'lang': args.lang, 'focus': args.focus, 'max_chars': args.max_chars,
                                                     'days': getattr(args, 'days', None), 'max_events': getattr(args, 'max_events', None),
                                                     'incident_time': getattr(args, 'incident_time', None), 'timeout': getattr(args, 'timeout', None)},
                'source_sha256': source_hash(), 'inputs_sha256': input_hashes,
                'outputs_sha256': {name: hash_bytes((directory / name).read_bytes()) for name in files if (directory / name).is_file()},
                'context': {'snapshot_chars': raw_chars, 'summary_chars': summary_chars,
                            'summary_to_snapshot_ratio': round(summary_chars / raw_chars, 4) if raw_chars else None,
                            'measurement': 'Character counts only; not actual model tokens or billed cost.'},
                'synthetic': bool(snapshot.get('synthetic'))}
    write_json(directory / 'manifest.json', manifest)
    # Bounded output, not the whole report. Agents should read summary.json first.
    print(json.dumps({'report_directory': str(directory), 'summary_file': 'summary.json', 'findings': len(report['findings']),
                      'needs_review': sum(f['severity'] == 'warning' for f in report['findings']),
                      'summary_chars': summary_chars, 'synthetic': bool(snapshot.get('synthetic'))}, ensure_ascii=False))


def read_text(path):
    source = Path(path)
    if source.stat().st_size > MAX_INPUT:
        raise ValueError('Debugger log exceeds the 20 MiB limit.')
    # Saved debugger logs are often UTF-16; inspect BOM rather than guessing ANSI.
    data = source.read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig', errors='replace')


def run_collect(args):
    if os.name != 'nt':
        raise ValueError('Live collection requires Windows; analyze and compare work offline on other platforms.')
    directory = output_directory(args.out, args.overwrite)
    shell = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
    if not shell:
        raise ValueError('Windows PowerShell 5.1 or PowerShell 7 was not found.')
    script = Path(__file__).with_name('collect-diagnostics.ps1')
    result = subprocess.run([shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                             str(script), '-Days', str(args.days), '-MaxEvents', str(args.max_events)],
                            capture_output=True, timeout=args.timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        message = result.stderr.decode('utf-8', errors='replace')[:1200]
        raise ValueError('Collector failed: ' + redact_text(message))
    raw = result.stdout.decode('utf-8-sig')
    if len(result.stdout) > MAX_INPUT:
        raise ValueError('Collector output exceeds the 20 MiB limit; reduce the event window.')
    snapshot = validate_snapshot(json.loads(raw))
    advisories = load_json(args.advisories) if args.advisories else None
    report = analyze(snapshot, advisories=advisories, incident_time=args.incident_time)
    hashes = {'collector_output': hash_bytes(result.stdout)}
    if args.advisories:
        hashes['advisories'] = hash_bytes(Path(args.advisories).read_bytes())
    save_report(directory, snapshot, report, args, hashes)


def run_analyze(args):
    snapshot = validate_snapshot(load_json(args.input))
    text = read_text(args.debugger_log) if args.debugger_log else None
    advisories = load_json(args.advisories) if args.advisories else None
    report = analyze(snapshot, text, advisories, args.incident_time)
    directory = output_directory(args.out, args.overwrite)
    hashes = {'snapshot': hash_bytes(Path(args.input).read_bytes())}
    for key, path in [('debugger_log', args.debugger_log), ('advisories', args.advisories)]:
        if path:
            hashes[key] = hash_bytes(Path(path).read_bytes())
    save_report(directory, snapshot, report, args, hashes)


def run_compare(args):
    before, after = load_json(args.before), load_json(args.after)
    comparison = compare(before, after)
    report = analyze(after)
    report['comparison'] = comparison
    directory = output_directory(args.out, args.overwrite, ('comparison.json',))
    write_json(directory / 'comparison.json', comparison)
    save_report(directory, after, report, args,
                {'before': hash_bytes(Path(args.before).read_bytes()), 'after': hash_bytes(Path(args.after).read_bytes())},
                ('comparison.json',))


def run_dump(args):
    if os.name != 'nt':
        raise ValueError('Headless CDB execution requires Windows.')
    debugger, dump = Path(args.debugger).resolve(), Path(args.dump).resolve()
    if debugger.name.lower() != 'cdb.exe' or not debugger.is_file():
        raise ValueError('Provide the path to an existing Microsoft Debugging Tools cdb.exe.')
    if not dump.is_file() or dump.suffix.lower() not in ('.dmp', '.mdmp'):
        raise ValueError('Provide an existing local .dmp or .mdmp file.')
    directory = output_directory(args.out, args.overwrite, ('debugger.txt',))
    symbols = directory / 'symbols'
    symbols.mkdir(exist_ok=True)
    try:
        result = subprocess.run([str(debugger), '-z', str(dump), '-y', f'srv*{symbols}*https://msdl.microsoft.com/download/symbols',
                                 '-c', '!analyze -v; lm; q'], capture_output=True, timeout=args.timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or b'').decode('utf-8', errors='replace')
        write_text(directory / 'debugger.txt', redact_text(partial))
        raise ValueError('Debugger timed out; partial sanitized text saved. Analysis is incomplete.') from None
    text = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    write_text(directory / 'debugger.txt', redact_text(text))
    if result.returncode:
        raise ValueError('Debugger failed; sanitized text saved. No diagnosis is established.')
    snapshot = {'schema_version': 1, 'captured_at': datetime.now(timezone.utc).isoformat(), 'machine_id': 'offline-dump',
                'synthetic': False, 'collection': {'mode': 'provided dump; timestamp is analysis time, not crash time'},
                'sections': {'dumps': {'status': 'ok', 'reason': '', 'data': [{'name': dump.name, 'kind': 'provided', 'bytes': dump.stat().st_size}]}}}
    report = analyze(snapshot, text)
    save_report(directory, snapshot, report, args, {'debugger_text': hash_bytes(text.encode())}, ('debugger.txt',))


def parser():
    root = argparse.ArgumentParser(description='Windows Driver Doctor: local evidence, bounded context, bilingual reports.')
    root.add_argument('--version', action='version', version=VERSION)
    commands = root.add_subparsers(dest='command', required=True)
    def common(command):
        command.add_argument('--out', required=True, help='Local output directory; no browser is opened.')
        command.add_argument('--lang', choices=('en', 'zh'), default='en', help='Initial report language (default: en).')
        command.add_argument('--focus', choices=('all', 'drivers', 'crash', 'boot'), default='all', help='Limit the model summary to the relevant symptom.')
        command.add_argument('--max-chars', type=int, default=2400, help='Compact model-summary character budget, minimum 800.')
        command.add_argument('--overwrite', action='store_true', help='Explicitly allow replacement of existing report files.')
    collect = commands.add_parser('collect', help='Read-only live Windows collection; no elevation or repairs.')
    common(collect)
    collect.add_argument('--days', type=int, choices=range(1, 91), metavar='1..90', default=14)
    collect.add_argument('--max-events', type=int, choices=range(1, 2001), metavar='1..2000', default=200)
    collect.add_argument('--timeout', type=int, default=180)
    collect.add_argument('--advisories', help='Optional local vendor-advisory JSON; no network lookup.')
    collect.add_argument('--incident-time', help='ISO-8601 symptom time with timezone offset, for bounded correlation.')
    collect.set_defaults(handler=run_collect)
    offline = commands.add_parser('analyze', help='Analyze an existing snapshot without inspecting a live computer.')
    common(offline)
    offline.add_argument('--input', required=True)
    offline.add_argument('--debugger-log', help='Optional saved WinDbg/CDB text.')
    offline.add_argument('--advisories', help='Optional local vendor-advisory JSON.')
    offline.add_argument('--incident-time', help='ISO-8601 symptom time with timezone offset.')
    offline.set_defaults(handler=run_analyze)
    comparison = commands.add_parser('compare', help='Compare later evidence from the same computer.')
    common(comparison)
    comparison.add_argument('--before', required=True)
    comparison.add_argument('--after', required=True)
    comparison.set_defaults(handler=run_compare)
    dump = commands.add_parser('dump', help='Run an existing headless CDB; writes a symbol cache and uses Microsoft symbols.')
    common(dump)
    dump.add_argument('--dump', required=True)
    dump.add_argument('--debugger', required=True)
    dump.add_argument('--timeout', type=int, default=300)
    dump.set_defaults(handler=run_dump)
    brief = commands.add_parser('brief', help='Print a bounded model handoff from findings.json.')
    brief.add_argument('--input', required=True)
    brief.add_argument('--lang', choices=('en', 'zh'), default='en')
    brief.add_argument('--focus', choices=('all', 'drivers', 'crash', 'boot'), default='all')
    brief.add_argument('--max-chars', type=int, default=2400)
    brief.set_defaults(handler=lambda args: print(json.dumps(compact(load_json(args.input), args.lang, args.focus, args.max_chars), ensure_ascii=False, separators=(',', ':'))))
    drill = commands.add_parser('evidence', help='Print bounded rows from a selected snapshot section.')
    drill.add_argument('--input', required=True)
    drill.add_argument('--section', required=True)
    drill.add_argument('--device-key', help='Only rows associated with this hashed device identity.')
    drill.add_argument('--limit', type=int, default=10)
    drill.add_argument('--max-chars', type=int, default=4000)
    drill.set_defaults(handler=lambda args: print(json.dumps(evidence(validate_snapshot(load_json(args.input)), args.section, args.device_key, args.limit, args.max_chars), ensure_ascii=False, separators=(',', ':'))))
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if hasattr(args, 'max_chars') and not 800 <= args.max_chars <= 100000:
            raise ValueError('--max-chars must be 800..100000.')
        if hasattr(args, 'timeout') and not 1 <= args.timeout <= 3600:
            raise ValueError('--timeout must be 1..3600 seconds.')
        args.handler(args)
        return 0
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired, UnicodeError, KeyError, TypeError) as exc:
        print('Error: ' + redact_text(str(exc)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
