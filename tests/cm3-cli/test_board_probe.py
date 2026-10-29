import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('board_probe', ROOT / 'scripts/cm3-package-preflight.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
SPEC = importlib.util.spec_from_file_location('board_builder', ROOT / 'packages/cm3-cli-board-support/build.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class BoardProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)
        (self.work / 'evidence').mkdir()
        self.deb = self.work / 'board-debs/cm3-cli-board-support_0.1.0_all.deb'
        self.revision = 'a' * 40  # Synthetic provenance, never a target-run claim.
        builder.build(self.deb, self.revision, 1700000000)
        self.manifest = {
            'source_revision': self.revision, 'source_date_epoch': 1700000000,
            'source_lock_sha256': probe.digest(ROOT / 'project/cm3-cli/source-lock.json'),
            'packages': {'cm3-cli-board-support': {'version': '0.1.0', 'architecture': 'all',
                                                  'sha256': probe.digest(self.deb)}},
        }
        self.write_manifest(self.manifest)

    def write_manifest(self, data):
        (self.work / 'evidence/board-manifest.json').write_text(json.dumps(data))

    def test_real_deb_separate_identity_hash_and_embedded_provenance(self):
        self.assertEqual(probe.inspect_board_input(self.work, self.revision),
                         {'cm3-cli-board-support': self.deb})
        lock = probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
        self.assertEqual(len(probe.source.expected_packages(lock)), 9)
        self.assertNotIn('cm3-cli-board-support', probe.source.expected_packages(lock))

    def test_wrong_revision_epoch_lock_and_identity_rejected(self):
        for field, value in [('source_revision', 'b' * 40), ('source_date_epoch', 1700000001),
                             ('source_date_epoch', True), ('source_lock_sha256', '0' * 64)]:
            data = copy.deepcopy(self.manifest)
            data[field] = value
            self.write_manifest(data)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                probe.inspect_board_input(self.work, self.revision)
        for field, value in [('version', '0.2.0'), ('architecture', 'arm64'), ('sha256', 'f' * 64)]:
            data = copy.deepcopy(self.manifest)
            data['packages']['cm3-cli-board-support'][field] = value
            self.write_manifest(data)
            with self.subTest(field=field), self.assertRaises(ValueError):
                probe.inspect_board_input(self.work, self.revision)

    def test_extra_missing_and_symlinked_board_inputs_rejected(self):
        extra = self.deb.with_name('extra.deb')
        shutil.copyfile(self.deb, extra)
        with self.assertRaises(ValueError):
            probe.inspect_board_input(self.work, self.revision)
        extra.unlink()
        self.deb.rename(self.work / 'outside.deb')
        with self.assertRaises(ValueError):
            probe.inspect_board_input(self.work, self.revision)
        self.deb.symlink_to(self.work / 'outside.deb')
        with self.assertRaises(ValueError):
            probe.inspect_board_input(self.work, self.revision)

    def test_tampered_bytes_and_relabelled_embedded_provenance_rejected(self):
        with self.deb.open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'hash'):
            probe.inspect_board_input(self.work, self.revision)
        # Matching outer claims cannot relabel a package built from another revision.
        self.deb.unlink()
        builder.build(self.deb, 'b' * 40, 1700000000)
        self.manifest['packages']['cm3-cli-board-support']['sha256'] = probe.digest(self.deb)
        self.write_manifest(self.manifest)
        with self.assertRaisesRegex(ValueError, 'embedded'):
            probe.inspect_board_input(self.work, self.revision)

    def test_download_hash_precedes_unpack_and_kernel_mask_is_required(self):
        root = self.work / 'root'
        cache = root / 'var/cache/apt/archives'
        cache.mkdir(parents=True)
        cached = cache / self.deb.name
        shutil.copyfile(self.deb, cached)
        mask = root / 'etc/kernel/install.d/99-update-overlay.install'
        mask.parent.mkdir(parents=True)
        calls = []

        def chroot(_root, *args, **kwargs):
            calls.append(args)
            if args[:2] == ('dpkg', '--unpack'):
                mask.symlink_to('/dev/null')

        with patch.object(probe, 'chroot', chroot):
            probe.install_board_policy(root, self.deb)
        self.assertIn('apt-get download cm3-cli-board-support=0.1.0', calls[0][2])
        self.assertEqual(calls[1][:2], ('dpkg', '--unpack'))
        self.assertEqual(os.readlink(mask), '/dev/null')
        cached.write_bytes(b'tampered')
        calls.clear()
        with patch.object(probe, 'chroot', chroot), self.assertRaisesRegex(ValueError, 'download'):
            probe.install_board_policy(root, self.deb)
        self.assertEqual(len(calls), 1)  # No unpack of unauthenticated/different bytes.

    def test_workflow_builds_separate_package_after_admission_without_stale_source_reuse(self):
        text = (ROOT / '.github/workflows/build.yaml').read_text()
        self.assertLess(text.index('scripts/cm3-package-budget.py'),
                        text.index('packages/cm3-cli-board-support/build.py'))
        self.assertIn('--revision "$EXPECTED_SHA" --epoch "$(git show -s --format=%ct HEAD)"', text)
        self.assertIn('--manifest preflight-work/board-manifest.json', text)
        self.assertLess(text.index('python3 /src/scripts/cm3-source-preflight.py --workdir /work;'),
                        text.index('mkdir /work/board-debs;'))
        self.assertNotIn('path: preflight-work/board-input', text)

    def test_builder_rejects_wrong_commit_timestamp(self):
        revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        output = self.work / 'wrong-epoch.deb'
        result = subprocess.run(['python3', str(ROOT / 'packages/cm3-cli-board-support/build.py'),
                                 '--output', str(output), '--revision', revision, '--epoch', '0'],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('timestamp', result.stderr)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
