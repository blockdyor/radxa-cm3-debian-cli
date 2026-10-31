import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[2] / 'tools/cm3-toolkit'
sys.path.insert(0, str(TOOLS))
import bench
import report
from common import validate_result

FIXTURES = Path(__file__).parent/'fixtures/bench'


class ReportTests(unittest.TestCase):
    def pair(self, controlled=False):
        args = bench.parser().parse_args(['cpu', '--execute', '--allow-load',
            '--conditions', str(FIXTURES/'conditions.json'), '--fixture-root', str(FIXTURES)])
        baseline, code = bench.build(args)
        self.assertEqual(code, 0)
        if controlled:
            for key in report.ESSENTIAL:
                if baseline['conditions'].get(key) is None:
                    baseline['conditions'][key] = 'SYNTHETIC-CONTROL'
            baseline['conditions'].update(image_hash='synthetic-image', failures=[], exclusions=[])
            baseline['conditions'].update(thermal_zone=0, thermal_abort_degc=70, thermal_observer_ref='synthetic-observer')
        candidate = copy.deepcopy(baseline)
        candidate['run_id'] = 'synthetic-candidate'
        candidate['conditions']['role'] = 'candidate'
        candidate['records'][0]['value'] *= 2
        raw = next(r['value'] for r in candidate['records'] if r['name'] == 'cpu.raw')
        raw['operations'] *= 2
        candidate['sources'][0]['sha256'] = hashlib.sha256(json.dumps(raw, allow_nan=False, sort_keys=True).encode()).hexdigest()
        return baseline, candidate

    def summary(self, result):
        return next(r['value'] for r in result['records'] if r['name']=='comparison.summary')

    def test_synthetic_unknown_controls(self):
        result = report.compare(*self.pair())
        validate_result(result)
        text = self.summary(result)
        self.assertTrue(text.startswith(report.BANNER))
        self.assertIn('INCONCLUSIVE', text)
        self.assertIn('UNTESTED', text)
        self.assertIn('NOT EVALUATED', text)
        self.assertTrue(result['provenance']['synthetic'])
        self.assertEqual(len(result['provenance']['input_run_ids']), 2)
        self.assertIsNone(result['records'][1]['value']['delta'])

    def test_descriptive_only(self):
        result = report.compare(*self.pair(True))
        self.assertIn('DESCRIPTIVE ONLY', self.summary(result))
        metric = next(r for r in result['records'] if r['name']=='cpu.throughput')
        self.assertEqual(metric['value']['percent'], 100)

    def test_mismatches_and_failures(self):
        for mutation in ('unit', 'protocol', 'failure', 'unavailable', 'error', 'role'):
            b, c = self.pair(True)
            if mutation == 'unit':
                c['records'][0]['unit'] = 'seconds'
            elif mutation == 'protocol':
                c['conditions']['protocol_id'] = 'other'
            elif mutation == 'failure':
                c['conditions']['failures'] = ['synthetic-interruption']
            elif mutation == 'role':
                c['conditions']['role'] = 'baseline'
            else:
                c['records'][0].update(status=mutation, value=None, reason='fixture')
            result = report.compare(b, c)
            self.assertIn('INCONCLUSIVE', self.summary(result))
            validate_result(result)

    def test_either_input_synthetic(self):
        b, c = self.pair()
        b['provenance'].update(synthetic=False, fixture_id=None, origin='approved-test')
        for r in b['records']:
            r['source']='procedure'
        self.assertTrue(report.compare(b, c)['provenance']['synthetic'])

    def test_reject_relabel_malformed_nonfinite(self):
        for mutation in ('live', 'nan', 'duplicate', 'version', 'path'):
            b, c = self.pair()
            if mutation=='live':
                b['provenance']['synthetic']=False
            elif mutation=='nan':
                b['records'][0]['value']=float('nan')
            elif mutation=='duplicate':
                b['records'].append(copy.deepcopy(b['records'][0]))
            elif mutation=='version':
                b['schema_version']='wrong'
            else:
                b['sources'][0]['path_or_ref']='../escape'
            with self.assertRaises(ValueError):
                report.compare(b,c)

    def test_bounded_read_and_special_files(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'input.json'
            p.write_text('{"x":1}')
            self.assertEqual(bench.read_json(p), {'x':1})
            with self.assertRaises(ValueError):
                bench.read_json(p, 1)
            p.write_text('{"x":NaN}')
            with self.assertRaises(ValueError):
                bench.read_json(p)
            link = Path(td)/'link'
            link.symlink_to(p)
            with self.assertRaises(OSError):
                bench.read_json(link)
            fifo = Path(td)/'fifo'
            import os
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                bench.read_json(fifo)

    def test_boot_method_mismatch_is_inconclusive(self):
        b, c = self.pair(True)
        for result in (b, c):
            for r in result['records']:
                r['name'] = r['name'].replace('cpu.', 'boot-ssh.')
        c['conditions']['boot_events']['start_event'] = 'warm-reset'
        result = report.compare(b, c)
        self.assertIn('INCONCLUSIVE', self.summary(result))
        self.assertIn('boot method start_event', self.summary(result))


if __name__ == '__main__':
    unittest.main()
