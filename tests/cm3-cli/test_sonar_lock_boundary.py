"""Regression coverage for the CLI source-lock path trust boundary."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/cm3-source-preflight.py'
LOCK = ROOT / 'project/cm3-cli/source-lock.json'
SPEC = importlib.util.spec_from_file_location('lock_boundary_source', SCRIPT)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class SourceLockBoundaryTests(unittest.TestCase):
    def run_check(self, *args, script=SCRIPT):
        return subprocess.run([sys.executable, str(script), '--check-lock', *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, timeout=10)

    def assert_rejected(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('checked-in source lock', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_default_absolute_relative_and_normalized_authority_paths(self):
        for args in [(), ('--lock', LOCK), ('--lock', LOCK.relative_to(ROOT)),
                     ('--lock', 'project/cm3-cli/../cm3-cli/source-lock.json')]:
            with self.subTest(args=args):
                result = self.run_check(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['target']['product'], 'radxa-cm3-rpi-cm4-io')
                self.assertEqual(len(report['packages']), 9)

    def test_cli_rejects_external_valid_lock_and_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / 'source-lock.json'
            shutil.copyfile(LOCK, external)
            for path in [external, Path(os.path.relpath(external, ROOT))]:
                with self.subTest(path=path):
                    self.assert_rejected(self.run_check('--lock', path))

    def test_cli_rejects_missing_directory_and_non_json_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / 'not-json'
            invalid.write_text('not JSON')
            for path in [root, root / 'missing', invalid]:
                with self.subTest(path=path):
                    self.assert_rejected(self.run_check('--lock', path))

    def test_cli_resolves_symlinks_before_authorizing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / 'source-lock.json'
            shutil.copyfile(LOCK, external)
            alias = root / 'alias.json'
            alias.symlink_to(external)
            self.assert_rejected(self.run_check('--lock', alias))
            alias.unlink()
            alias.symlink_to(LOCK)
            result = self.run_check('--lock', alias)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(result.stdout)['packages']), 9)

    def test_default_cannot_be_redirected_to_external_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'scripts/cm3-source-preflight.py'
            script.parent.mkdir()
            shutil.copyfile(SCRIPT, script)
            external = root / 'external.json'
            shutil.copyfile(LOCK, external)
            lock = root / 'project/cm3-cli/source-lock.json'
            lock.parent.mkdir(parents=True)
            lock.symlink_to(external)
            self.assert_rejected(self.run_check(script=script))

    def test_trusted_import_callers_can_validate_fixture_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'lock.json'
            shutil.copyfile(LOCK, fixture)
            lock = source.load_lock(fixture)
            self.assertEqual(lock['target']['product'], 'radxa-cm3-rpi-cm4-io')
            self.assertEqual(len(source.expected_packages(lock)), 9)


if __name__ == '__main__':
    unittest.main()
