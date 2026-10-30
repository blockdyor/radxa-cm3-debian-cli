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

    def run_cli(self, evidence, output):
        return subprocess.run([sys.executable, str(SCRIPT), '--evidence',
                               str(evidence), '--output', str(output)],
                              capture_output=True, text=True)

    def test_cli_writes_exact_decision_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / 'evidence.json'
            output = Path(directory) / 'decision.json'
            evidence.write_text(json.dumps(self.stage_a))
            result = self.run_cli(evidence, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), self.expected)
            before = output.read_bytes()
            self.assertNotEqual(self.run_cli(evidence, output).returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            self.assertNotEqual(self.run_cli(evidence, evidence).returncode, 0)
            self.assertEqual(json.loads(evidence.read_text()), self.stage_a)

    def test_cli_bad_evidence_never_writes_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / 'evidence.json'
            output = Path(directory) / 'decision.json'
            for content in ['{', '{}', 'null', '[]',
                            json.dumps(dict(self.stage_a, exact_head_sonar='FAIL'))]:
                with self.subTest(content=content):
                    evidence.write_text(content)
                    self.assertNotEqual(self.run_cli(evidence, output).returncode, 0)
                    self.assertFalse(output.exists())
            evidence.unlink()
            self.assertNotEqual(self.run_cli(evidence, output).returncode, 0)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
