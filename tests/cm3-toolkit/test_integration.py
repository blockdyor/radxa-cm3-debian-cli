"""Offline CLI integration; never run target workloads or network probes."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools/cm3-toolkit'
sys.path.insert(0, str(TOOLS))
import bench
import report
from common import validate_result
import test_report

FIXTURES = ROOT / 'tests/cm3-toolkit/fixtures'


class IntegrationTests(unittest.TestCase):
    def cli(self, script, *args, expected=0):
        result = subprocess.run([sys.executable, str(TOOLS/script), *map(str, args)],
                                capture_output=True, text=True, timeout=10,
                                cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, expected, result.stderr)
        return json.loads(result.stdout) if result.stdout else None

    def fixture_args(self, procedure):
        return [procedure, '--fixture-root', FIXTURES/'bench', '--conditions',
                FIXTURES/'bench/conditions.json', '--execute', '--allow-load',
                '--allow-write', '--allow-network', '--approved-dir', '/synthetic-not-touched',
                '--peer', '192.0.2.1']

    def test_all_plan_and_fixture_clis(self):
        for procedure in bench.PROCEDURES:
            with self.subTest(procedure=procedure):
                plan = self.cli('bench.py', procedure)
                self.assertEqual(plan['kind'], 'plan')
                self.assertFalse(plan['authorization']['execute'])
                value = self.cli('bench.py', *self.fixture_args(procedure))
                validate_result(value)
                self.assertTrue(value['provenance']['synthetic'])
                self.assertEqual(value['provenance']['fixture_id'], 'bench-v1')

    def test_collector_cli_missing_and_private_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = json.loads((FIXTURES/'collector/basic.json').read_text())
            for name, value in template.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
            secret = root/'etc/machine-id'
            secret.write_text('PRIVATE-SENTINEL-MUST-NOT-APPEAR')
            result = self.cli('collect.py', '--fixture-root', root, expected=3)
            validate_result(result)
            self.assertTrue(result['provenance']['synthetic'])
            self.assertNotIn('PRIVATE-SENTINEL', json.dumps(result))
            self.assertTrue(any(r['status'] == 'unavailable' for r in result['records']))

    def test_cli_no_clobber_and_raw_device_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)/'existing.json'
            output.write_text('untouched')
            self.cli('bench.py', *self.fixture_args('cpu'), '--output', output, expected=2)
            self.assertEqual(output.read_text(), 'untouched')
        self.cli('bench.py', *self.fixture_args('storage'), '--output', '/dev/null', expected=2)
        self.cli('report.py', '--baseline', '/dev/null', '--candidate', '/dev/null', expected=2)

    def test_invalid_output_prevents_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)/'exists'
            output.write_text('keep')
            for path in (output, Path('/dev/null'), Path(td)/'missing/result.json'):
                with patch.object(sys, 'argv', ['bench.py', 'cpu', '--output', str(path)]), patch.object(bench, 'build') as build, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(bench.main(), 2)
                    build.assert_not_called()
            self.assertEqual(output.read_text(), 'keep')

    def test_report_rejects_unexecuted_and_missing_authority(self):
        pair = test_report.ReportTests().pair(True)
        for field in ('execute', 'load'):
            baseline, candidate = copy.deepcopy(pair)
            baseline['authorization'][field] = False
            with self.assertRaises(ValueError):
                report.compare(baseline, candidate)

    def test_raw_integrity_mismatch_suppresses_deltas(self):
        for mutation in ('metric', 'digest', 'raw'):
            baseline, candidate = test_report.ReportTests().pair(True)
            if mutation == 'metric':
                candidate['records'][0]['value'] *= 3
            elif mutation == 'digest':
                candidate['sources'][0]['sha256'] = '0'*64
            else:
                next(r for r in candidate['records'] if r['name'] == 'cpu.raw')['value']['operations'] *= 3
            result = report.compare(baseline, candidate)
            self.assertIn('INCONCLUSIVE', test_report.ReportTests().summary(result))
            for record in result['records']:
                if isinstance(record['value'], dict) and 'delta' in record['value']:
                    self.assertIsNone(record['value']['delta'])

    def test_report_cli_roundtrip_and_malformed(self):
        baseline, candidate = test_report.ReportTests().pair()
        with tempfile.TemporaryDirectory() as td:
            b, c = Path(td)/'b.json', Path(td)/'c.json'
            b.write_text(json.dumps(baseline))
            c.write_text(json.dumps(candidate))
            result = self.cli('report.py', '--baseline', b, '--candidate', c)
            validate_result(result)
            self.assertTrue(test_report.ReportTests().summary(result).startswith(report.BANNER))
            self.assertEqual(result['provenance']['input_run_ids'], [baseline['run_id'], candidate['run_id']])
            b.write_text('{"bad":NaN}')
            self.cli('report.py', '--baseline', b, '--candidate', c, expected=2)


if __name__ == '__main__':
    unittest.main()
