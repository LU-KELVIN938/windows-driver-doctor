import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analysis import analyze, compare, match_advisories, parse_debugger, sanitize, validate_snapshot
from context import compact, evidence
from reporting import render_html, render_markdown


def section(data, status='ok', reason=''):
    return {'status': status, 'reason': reason, 'data': data}


def fixture():
    return json.loads((ROOT / 'examples/demo-snapshot.json').read_text(encoding='utf-8'))


def ids(report):
    return {item['id'] for item in report['findings']}


class EvidenceTests(unittest.TestCase):
    def test_detached_device_not_active_error(self):
        data = fixture()
        data['sections']['devices']['data'] = [data['sections']['devices']['data'][1]]
        report = analyze(data)
        self.assertNotIn('device-problems', ids(report))
        self.assertIn('detached-devices', ids(report))

    def test_problem_code_associates_driver_and_configuration(self):
        report = analyze(fixture())
        problem = next(f for f in report['findings'] if f['id'] == 'device-problems')
        self.assertEqual(problem['confidence'], 'observed')
        self.assertEqual(problem['evidence'][0]['matching_drivers'][0]['inf'], 'oem42.inf')
        self.assertEqual(problem['evidence'][0]['configuration_events'][0]['id'], 400)

    def test_unknown_presence_not_confirmed_present(self):
        data = fixture()
        data['sections']['devices']['data'][0]['present'] = None
        report = analyze(data)
        self.assertNotIn('device-problems', ids(report))
        self.assertIn('device-presence-unknown', ids(report))

    def test_event41_without_code_does_not_prove_bsod(self):
        data = fixture()
        data['sections']['events']['data'] = [{**data['sections']['events']['data'][1], 'bugcheck_code': 0}]
        report = analyze(data)
        self.assertIn('unexpected-restart', ids(report))
        self.assertNotIn('bugcheck-recorded', ids(report))

    def test_nonzero_event41_is_bugcheck_evidence(self):
        data = fixture()
        data['sections']['events']['data'] = [data['sections']['events']['data'][1]]
        self.assertIn('bugcheck-recorded', ids(analyze(data)))

    def test_application1001_is_not_kernel_bugcheck(self):
        data = fixture()
        data['sections']['events']['data'] = [{'id': 1001, 'log': 'Application', 'provider': 'Windows Error Reporting'}]
        self.assertNotIn('bugcheck-recorded', ids(analyze(data)))

    def test_wrong_provider4101_is_not_display_recovery(self):
        data = fixture()
        data['sections']['events']['data'] = [{'id': 4101, 'log': 'System', 'provider': 'OtherProvider'}]
        self.assertNotIn('display-recovery', ids(analyze(data)))

    def test_inaccessible_checks_are_not_passes(self):
        report = analyze(fixture())
        missing = next(f for f in report['findings'] if f['id'] == 'missing-evidence')
        self.assertEqual(missing['confidence'], 'incomplete')
        self.assertEqual(missing['evidence'][0]['section'], 'dumps')

    def test_old_driver_date_is_not_outdated_alarm(self):
        data = fixture()
        data['sections']['drivers']['data'][0]['date'] = '2006-06-21'
        self.assertFalse(any('outdated' in f['id'] for f in analyze(data)['findings']))

    def test_named_debugger_module_remains_hypothesis(self):
        report = analyze(fixture(), 'BUGCHECK_CODE: 9f\nIMAGE_NAME: pci.sys\nFAILURE_BUCKET_ID: example')
        item = next(f for f in report['findings'] if f['id'] == 'debugger-lead')
        self.assertEqual(item['confidence'], 'hypothesis')
        self.assertIn('leads', item['detail']['en'])

    def test_symbol_failure_reduces_confidence(self):
        result = parse_debugger('BUGCHECK_CODE: 9f\nIMAGE_NAME: pci.sys\nSymbol file could not be found')
        self.assertTrue(result['symbol_warnings'])

    def test_incident_time_is_explicit_and_bounded(self):
        report = analyze(fixture(), incident_time='2026-10-04T09:00:00+00:00')
        item = next(f for f in report['findings'] if f['id'] == 'incident-timeline')
        self.assertEqual(len(item['evidence'][0]['nearby_events']), 2)
        self.assertEqual(len(item['evidence'][0]['prior_configuration_events']), 1)
        with self.assertRaises(ValueError):
            analyze(fixture(), incident_time='2026-10-04T09:00:00')

    def test_empty_snapshot_not_healthy_verdict(self):
        data = fixture()
        data['sections'] = {}
        self.assertIn('empty-evidence', ids(analyze(data)))

    def test_malformed_section_rejected(self):
        data = fixture()
        data['sections']['events']['data'] = {'id': 41}
        with self.assertRaises(ValueError):
            validate_snapshot(data)


class ComparisonTests(unittest.TestCase):
    def test_later_snapshot_same_boot_not_improvement(self):
        before, after = fixture(), fixture()
        after['captured_at'] = '2026-10-04T11:00:00+00:00'
        self.assertEqual(compare(before, after)['boot']['status'], 'same_or_unconfirmed_boot')

    def test_new_boot_remains_mode_unverified(self):
        before, after = fixture(), fixture()
        after['captured_at'] = '2026-10-04T11:00:00+00:00'
        after['sections']['boot']['data'].insert(0, {'record_id': 202, 'time': '2026-10-04T10:30:00+00:00', 'boot_ms': 20000})
        result = compare(before, after)
        self.assertEqual(result['boot']['status'], 'distinct_records_mode_unverified')
        self.assertEqual(result['boot']['delta_seconds'], -25)

    def test_driver_version_change_and_new_event(self):
        before, after = fixture(), fixture()
        after['captured_at'] = '2026-10-04T11:00:00+00:00'
        after['sections']['drivers']['data'][0]['version'] = '1.2.4.0'
        after['sections']['events']['data'].append({'log': 'System', 'provider': 'Display', 'id': 4101, 'record_id': 999, 'time': '2026-10-04T10:30:00+00:00'})
        result = compare(before, after)
        self.assertEqual(result['driver_changes'][0]['change'], 'changed')
        self.assertEqual(len(result['new_events']), 1)

    def test_previous_events_not_counted_as_new_incidents(self):
        before, after = fixture(), fixture()
        before['sections']['events']['data'] = []
        after['captured_at'] = '2026-10-04T11:00:00+00:00'
        self.assertEqual(compare(before, after)['new_events'], [])

    def test_cross_machine_comparison_rejected(self):
        before, after = fixture(), fixture()
        after['machine_id'] = 'different-computer'
        after['captured_at'] = '2026-10-04T11:00:00+00:00'
        with self.assertRaises(ValueError):
            compare(before, after)

    def test_reversed_snapshot_order_rejected(self):
        with self.assertRaises(ValueError):
            compare(fixture(), fixture())

    def test_unavailable_inventory_not_driver_removal(self):
        before, after = fixture(), fixture()
        after['captured_at'] = '2026-10-04T11:00:00+00:00'
        after['sections']['drivers'] = section([], 'not_verified', 'denied')
        result = compare(before, after)
        self.assertEqual(result['driver_changes'], [])
        self.assertIn('drivers', result['unavailable'])


class PrivacyContextTests(unittest.TestCase):
    def test_redaction_preserves_driver_versions(self):
        result = sanitize({'path': r'C:\Users\Alice\Minidump\dump.dmp', 'message': 'IP 192.168.1.5, alice@example.com', 'SerialNumber': 'secret', 'version': '192.168.1.5'})
        self.assertNotIn('Alice', json.dumps(result))
        self.assertNotIn('alice@example.com', json.dumps(result))
        self.assertEqual(result['SerialNumber'], '<redacted>')
        self.assertEqual(result['version'], '192.168.1.5')

    def test_html_injection_escaped_and_no_network_assets(self):
        data = fixture()
        data['sections']['devices']['data'][0]['name'] = '</script><img src=x onerror=alert(1)>'
        document = render_html(analyze(data))
        self.assertNotIn('<img src=x', document)
        self.assertIn('&lt;img', document)
        self.assertNotIn('<script src=', document)
        self.assertNotIn('<link ', document)

    def test_both_report_languages_and_synthetic_label(self):
        report = analyze(fixture())
        document = render_html(report)
        self.assertIn('data-lang="en"', document)
        self.assertIn('data-lang="zh" hidden', document)
        self.assertIn('SYNTHETIC DEMO', document)
        self.assertIn('模拟数据', render_markdown(report, 'zh'))

    def test_summary_respects_context_budget(self):
        report = analyze(fixture())
        for lang in ('en', 'zh'):
            for budget in (800, 1200, 1800, 2400):
                result = compact(report, lang, 'all', budget)
                self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))), budget)
                self.assertTrue(result['synthetic'])

    def test_focus_and_drilldown_are_bounded(self):
        report = analyze(fixture())
        brief = compact(report, focus='crash')
        self.assertNotIn('boot-baseline', [item['id'] for item in brief['findings']])
        result = evidence(fixture(), 'drivers', 'aabbccdd00112233', limit=1, max_chars=800)
        self.assertEqual(result['matched_rows'], 1)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, separators=(',', ':'))), 800)


class AdvisoryTests(unittest.TestCase):
    def advisories(self, low='1.0', high='1.2.3.4'):
        return {'schema_version': 1, 'advisories': [{'id': 'demo', 'driver_file': 'examplewifi.sys', 'provider_contains': 'Example', 'min_version': low, 'max_version': high, 'source_url': 'https://vendor.example/bulletin'}]}

    def test_inclusive_version_endpoint(self):
        result = match_advisories(fixture(), self.advisories())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['confidence'], 'hypothesis')

    def test_version_outside_range_does_not_match(self):
        self.assertEqual(match_advisories(fixture(), self.advisories('1.2.3.5', '2.0')), [])

    def test_invalid_version_is_incomplete_candidate(self):
        data = fixture()
        data['sections']['drivers']['data'][0]['version'] = 'vendor-beta'
        result = match_advisories(data, self.advisories())
        self.assertEqual(result[0]['confidence'], 'incomplete')

    def test_executable_advisory_url_rejected(self):
        data = self.advisories()
        data['advisories'][0]['source_url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            match_advisories(fixture(), data)


class CliTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Synthetic PowerShell smoke test requires Windows PowerShell')
    def test_collector_with_synthetic_providers(self):
        result = subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'tests/collector-smoke.ps1')], capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        snapshot = json.loads(result.stdout.decode('utf-8-sig'))
        validate_snapshot(snapshot)
        self.assertTrue(snapshot['synthetic'])
        self.assertEqual(snapshot['sections']['devices']['data'][0]['problem_code'], 10)
        self.assertEqual(snapshot['sections']['events']['data'][0]['bugcheck_code'], 159)
        self.assertEqual(snapshot['sections']['battery_health']['data'][0]['full_to_design_percent'], 90)
        self.assertEqual(snapshot['sections']['boot']['data'][0]['boot_ms'], 40000)
        self.assertEqual(snapshot['sections']['security']['status'], 'partial')

    def test_offline_pipeline_provenance_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            cmd = [sys.executable, str(ROOT / 'scripts/doctor.py'), 'analyze', '--input', str(ROOT / 'examples/demo-snapshot.json'), '--out', temp]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((Path(temp) / 'manifest.json').read_text(encoding='utf-8'))
            for name, digest in manifest['outputs_sha256'].items():
                self.assertEqual(hashlib.sha256((Path(temp) / name).read_bytes()).hexdigest(), digest)
            second = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(second.returncode, 2)
            self.assertIn('--overwrite', second.stderr)

    def test_malformed_json_returns_readable_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            path.write_text('not json', encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/doctor.py'), 'analyze', '--input', str(path), '--out', str(Path(temp) / 'out')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Error:', result.stderr)


if __name__ == '__main__':
    unittest.main()
