"""Offline recovery claim checks; real Sigstore verification is a separate hosted gate."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'scripts/cm3-recovery-attestation.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(recovery.MANIFEST.read_text())

    def test_committed_manifest_has_exact_reviewed_scope(self):
        self.assertIs(recovery.validate(self.manifest), self.manifest)
        self.assertEqual(len(self.manifest['subjects']), 6)
        self.assertEqual(self.manifest['retention']['manifestFiles'], 563)
        self.assertFalse(self.manifest['hostedPayloadRehash'])

    def test_no_original_build_or_hardware_pass_may_be_invented(self):
        changes = [('originalBuildAttestationIssued', True), ('hostedPayloadRehash', True),
                   ('hardware', 'PASS'), ('verificationMode', 'hosted-build')]
        for name, value in changes:
            with self.subTest(name=name):
                changed = copy.deepcopy(self.manifest); changed[name] = value
                with self.assertRaises(ValueError):
                    recovery.validate(changed)
        changed = copy.deepcopy(self.manifest); changed['originalProducer']['conclusion'] = 'success'
        with self.assertRaises(ValueError):
            recovery.validate(changed)

    def test_wrong_original_source_run_or_attempt_rejected(self):
        for name, value in [('source', 'a' * 40), ('run', 1), ('attempt', 2)]:
            changed = copy.deepcopy(self.manifest); changed['originalProducer'][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                recovery.validate(changed)

    def test_material_path_digest_size_duplicate_and_missing_rejected(self):
        for name, value in [('name', '../secret'), ('name', '/absolute'),
                            ('sha256', 'abc'), ('bytes', 0), ('bytes', True)]:
            changed = copy.deepcopy(self.manifest); changed['subjects'][0][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                recovery.validate(changed)
        changed = copy.deepcopy(self.manifest); changed['subjects'].append(changed['subjects'][0])
        with self.assertRaises(ValueError):
            recovery.validate(changed)
        changed = copy.deepcopy(self.manifest); changed['subjects'].pop()
        with self.assertRaises(ValueError):
            recovery.validate(changed)

    def test_verification_source_is_not_built_source(self):
        p = recovery.predicate(self.manifest, 'a' * 40)
        self.assertEqual(p['verificationSource'], 'a' * 40)
        self.assertEqual(p['originalProducer']['source'], recovery.BUILT_SOURCE)
        with self.assertRaises(ValueError):
            recovery.predicate(self.manifest, 'main')

    def test_local_manifest_tamper_rejected_without_signature_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'image3-recovery.json').write_text('{}')
            bundle = directory / 'bundle'; bundle.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'manifest differs'):
                recovery.verify(directory, bundle, 'a' * 40)

    def test_digest_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'file'; original.write_text('fixture')
            link = Path(directory) / 'link'; link.symlink_to(original)
            with self.assertRaises(ValueError):
                recovery.digest(link)

    def test_recovery_workflow_cannot_enter_packages_or_assembly(self):
        text = (ROOT / '.github/workflows/build.yaml').read_text()
        packages, rest = text.split('\n  provenance:\n')
        provenance, job = rest.split('\n  recovery:\n')
        self.assertIn("&& !inputs.recovery_only", packages)
        self.assertIn("&& !inputs.recovery_only", provenance)
        self.assertIn('&& inputs.recovery_only', job)
        for forbidden in ['cm3-assemble-image', 'cm3-package-preflight', 'cm3-external-preflight',
                          'contents: write', 'packages: write', 'docker run', 'release create']:
            self.assertNotIn(forbidden, job)
        self.assertIn('predicate-path: recovery-output/recovery-predicate.json', job)
        self.assertIn('push-to-registry: false', job)
        self.assertIn('printf', job)  # Real appended byte mutation, not a possibly unchanged zero.


if __name__ == '__main__':
    unittest.main()
