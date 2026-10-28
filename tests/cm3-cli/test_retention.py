import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('retention', ROOT / 'scripts/cm3-retain-packages.py')
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.work = self.root / 'work'
        (self.work / 'selected-debs').mkdir(parents=True)
        evidence = self.work / 'evidence'
        evidence.mkdir()
        (evidence / 'result.json').write_text('{"status":"PASS"}')
        lock = retention.packages.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
        self.manifest = {}
        for name, (version, arch) in retention.packages.source.expected_packages(lock).items():
            staging = self.root / name
            (staging / 'DEBIAN').mkdir(parents=True)
            (staging / 'DEBIAN/control').write_text(
                f'Package: {name}\nVersion: {version}\nArchitecture: {arch}\n'
                'Maintainer: Test <test@example.invalid>\nDescription: synthetic test fixture only\n')
            deb = self.work / 'selected-debs' / (name + '.deb')
            subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(staging), str(deb)],
                           check=True, stdout=subprocess.DEVNULL)
            self.manifest[name] = {'version': version, 'architecture': arch,
                                   'sha256': retention.packages.digest(deb)}
        (evidence / 'bsp-manifest.json').write_text(json.dumps(self.manifest))
        # These must never enter the recovery archive.
        (self.work / 'private-key').write_text('synthetic non-secret sentinel')
        (evidence / 'unreviewed.log').write_text('synthetic log sentinel')
        self.certificate = self.root / 'recipient.pem'
        self.key = self.root / 'test.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-noenc',
                        '-keyout', str(self.key), '-out', str(self.certificate),
                        '-days', '1', '-subj', '/CN=fixture'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_real_authenticated_roundtrip_allowlist_and_tamper_rejection(self):
        output = self.root / 'recovery.cms'
        retention.seal(self.work, self.certificate, output, {'commit': 'a' * 40})
        plain = self.root / 'recovered.tar.gz'
        command = ['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
                   '-in', str(output), '-recip', str(self.certificate), '-inkey', str(self.key),
                   '-out', str(plain)]
        subprocess.run(command, check=True)
        with tarfile.open(plain) as archive:
            names = archive.getnames()
            self.assertEqual(len([n for n in names if n.startswith('selected-debs/')]), 9)
            self.assertNotIn('private-key', names)
            self.assertNotIn('evidence/unreviewed.log', names)
            manifest = json.load(archive.extractfile('retention-manifest.json'))
            self.assertEqual(manifest['provenance'], {'commit': 'a' * 40})
            for name, digest in manifest['files'].items():
                import hashlib
                self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(), digest)
        data = bytearray(output.read_bytes())
        data[-1] ^= 1
        output.write_bytes(data)
        self.assertNotEqual(subprocess.run(command, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL).returncode, 0)
        self.assertFalse(list(self.work.glob('cm3-retention-*')))

    def test_changed_package_and_evidence_symlink_rejected(self):
        deb = next((self.work / 'selected-debs').iterdir())
        original = deb.read_bytes()
        deb.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            retention.seal(self.work, self.certificate, self.root / 'recovery.cms', {})
        deb.write_bytes(original)
        (self.work / 'evidence/unsafe.json').symlink_to(self.work / 'private-key')
        with self.assertRaisesRegex(ValueError, 'non-symlink'):
            retention.seal(self.work, self.certificate, self.root / 'recovery.cms', {})


if __name__ == '__main__':
    unittest.main()
