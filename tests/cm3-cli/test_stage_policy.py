import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/cm3-stage-policy.py'
SPEC = importlib.util.spec_from_file_location('stage_policy', SCRIPT)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class StagePolicyTests(unittest.TestCase):
    def setUp(self):
        # Synthetic policy inputs, not receipts from an actual preflight.
        self.stage_a = {name: 'PASS' for name in policy.REQUIRED}
        self.expected = dict(experimental_assembly='ALLOWED',
                             stable_release='BLOCKED', hardware='UNTESTED')

    def test_only_experimental_assembly_allowed_without_runtime_evidence(self):
        original = self.stage_a.copy()
        self.assertEqual(policy.admit(self.stage_a), self.expected)
        self.assertEqual(self.stage_a, original)

    def test_every_required_receipt_must_be_literal_pass(self):
        for name in policy.REQUIRED:
            for value in [None, True, False, 1, 'pass', 'PASS ', 'FAIL',
                          'UNTESTED', 'BLOCKED', [], {}, {'status': 'PASS'}]:
                with self.subTest(name=name, value=value):
                    invalid = dict(self.stage_a, **{name: value})
                    with self.assertRaisesRegex(ValueError, name):
                        policy.admit(invalid)
            missing = self.stage_a.copy()
            del missing[name]
            with self.assertRaisesRegex(ValueError, name):
                policy.admit(missing)

    def test_non_objects_rejected(self):
        for value in [None, [], 'PASS', True, 1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.admit(value)

    def test_extra_claims_cannot_qualify_release_or_hardware(self):
        self.stage_a.update(stable_release='ALLOWED', hardware='PASS',
                            runtime='PASS', experimental_assembly='BLOCKED')
        self.assertEqual(policy.admit(self.stage_a), self.expected)

    def run_cli(self, content, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=content,
                              capture_output=True, text=True)

    def test_cli_reads_data_and_prints_exact_decision(self):
        result = self.run_cli(json.dumps(self.stage_a))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.expected)

    def test_cli_bad_evidence_never_prints_decision(self):
        for content in ['{', '{}', 'null', '[]', '',
                        json.dumps(dict(self.stage_a, exact_head_sonar='FAIL'))]:
            with self.subTest(content=content):
                result = self.run_cli(content)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_agent_supplied_paths_cannot_be_read_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'sentinel'
            sentinel.write_text('not JSON; never open this path')
            for name in [str(sentinel), '../outside.json', '/etc/shadow']:
                with self.subTest(name=name):
                    result = self.run_cli(json.dumps(self.stage_a), '--evidence', name,
                                          '--output', str(sentinel))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')
                    self.assertIn('no filesystem arguments', result.stderr)
                    self.assertEqual(sentinel.read_text(), 'not JSON; never open this path')


if __name__ == '__main__':
    unittest.main()
