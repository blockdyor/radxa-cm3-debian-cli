"""Command-policy tests are NOT evidence of cryptographic verification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/cm3-verify-bundle.py'


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'encrypted-bundle admission verifier missing')
        spec = importlib.util.spec_from_file_location('admission', SCRIPT)
        self.admission = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.admission)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.artifact = Path(self.tmp.name) / 'cm3-recovery.cms'
        self.artifact.write_bytes(b'unit fixture, not real ciphertext')
        self.bundle = Path(self.tmp.name) / 'bundle.jsonl'
        self.bundle.write_text('{}')
        self.digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.sha = 'a' * 40

    def verify(self):
        return self.admission.verify(self.artifact, self.bundle, self.sha, self.digest)

    def test_policy_command_and_bounded_receipt_only(self):
        # A stubbed process tests the command contract, never signature validity.
        with patch.object(self.admission.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0)
            receipt = self.verify()
        cmd = run.call_args.args[0]
        for flag, value in {
            '--repo': 'blockdyor/radxa-cm3-debian-cli',
            '--cert-identity': 'https://github.com/blockdyor/radxa-cm3-debian-cli/.github/workflows/build.yaml@refs/heads/dev/cm3-debian-cli',
            '--source-digest': self.sha, '--signer-digest': self.sha,
            '--source-ref': 'refs/heads/dev/cm3-debian-cli',
            '--cert-oidc-issuer': 'https://token.actions.githubusercontent.com',
            '--predicate-type': 'https://slsa.dev/provenance/v1',
        }.items():
            self.assertIn(flag, cmd)
            self.assertEqual(cmd[cmd.index(flag) + 1], value)
        self.assertIn('--deny-self-hosted-runners', cmd)
        self.assertNotIn('--signer-workflow', cmd)  # gh forbids combining SAN selectors.
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertEqual(receipt['ciphertext_sha256'], self.digest)
        self.assertEqual(receipt['scope'], 'ciphertext-only; no decryption, APT-key approval or import')
        self.assertLess(len(json.dumps(receipt)), 2048)

    def test_official_policy_rejections_never_emit_receipt(self):
        # Reason labels describe gh failures; these are propagation tests only.
        for reason in ['wrong repository', 'wrong workflow', 'wrong source digest',
                       'wrong signer digest', 'invalid signature', 'missing attestation',
                       'workflow prefix build.yaml.other']:
            with self.subTest(reason=reason), patch.object(
                self.admission.subprocess, 'run',
                side_effect=subprocess.CalledProcessError(1, ['gh'], stderr=reason)):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.verify()

    def test_wrong_ciphertext_digest_rejected_before_verifier(self):
        self.artifact.write_bytes(b'tampered')
        with patch.object(self.admission.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'ciphertext digest'):
                self.verify()
            run.assert_not_called()

    def test_missing_attestation_rejected_before_verifier(self):
        self.bundle.unlink()
        with self.assertRaises(OSError):
            self.verify()

    def test_malformed_commit_and_digest_rejected(self):
        for sha, digest in [('main', self.digest), (self.sha, 'abc')]:
            with self.subTest(sha=sha, digest=digest), self.assertRaises(ValueError):
                self.admission.verify(self.artifact, self.bundle, sha, digest)

    def test_unavailable_official_verifier_fails_closed(self):
        with patch.object(self.admission.subprocess, 'run', side_effect=FileNotFoundError('gh')):
            with self.assertRaises(FileNotFoundError):
                self.verify()

    def test_real_gh_rejects_invalid_signature_bundle(self):
        import shutil
        if shutil.which('gh') is None:
            self.skipTest('official gh unavailable; no cryptographic verification claimed')
        result = subprocess.run([
            'python3', str(SCRIPT), str(self.artifact), '--attestation', str(self.bundle),
            '--approved-sha', self.sha, '--expected-sha256', self.digest,
        ], capture_output=True, text=True, timeout=150)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('admission refused', result.stderr)


if __name__ == '__main__':
    unittest.main()
