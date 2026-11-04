"""Real CLI regressions for board-builder argument and output boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('git') and shutil.which('dpkg-deb'), 'git and dpkg-deb required')
class BoardBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        for name in ('packages/cm3-cli-board-support', 'scripts/cm3-owner-config.py',
                     'project/cm3-cli/source-lock.json', 'LICENSE'):
            source, target = ROOT / name, self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                shutil.copyfile(source, target)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Boundary Test', '-c', 'user.email=boundary@example.invalid',
                 'commit', '-qm', 'synthetic board fixture')
        self.revision = self.git('rev-parse', 'HEAD').strip()
        self.epoch = self.git('show', '-s', '--format=%ct', 'HEAD').strip()
        self.script = self.repo / 'packages/cm3-cli-board-support/build.py'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def cli(self, output, manifest=None, revision=None, epoch=None):
        command = ['python3', str(self.script), '--output=' + str(output),
                   '--revision', revision or self.revision, '--epoch', epoch or self.epoch]
        if manifest is not None:
            command.append('--manifest=' + str(manifest))
        return subprocess.run(command, cwd=self.repo, text=True, capture_output=True)

    def test_option_shaped_output_is_not_a_dpkg_option(self):
        result = self.cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.repo / '--help'
        self.assertTrue(output.is_file())
        self.assertEqual(subprocess.check_output(['dpkg-deb', '-f', str(output), 'Package'],
                                                text=True).strip(), 'cm3-cli-board-support')

    def test_output_traversal_and_absolute_escape_fail_before_writes(self):
        for output in ('../escaped.deb', self.base / 'absolute.deb'):
            with self.subTest(output=output):
                result = self.cli(output)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.repo / output).exists())

    def test_manifest_traversal_and_absolute_escape_fail_before_package_build(self):
        for manifest in ('../escaped.json', self.base / 'absolute.json'):
            with self.subTest(manifest=manifest):
                result = self.cli('board.deb', manifest)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.repo / 'board.deb').exists())
                self.assertFalse((self.repo / manifest).exists())
            (self.repo / 'board.deb').unlink(missing_ok=True)
            (self.repo / manifest).unlink(missing_ok=True)

    def test_symlinked_parent_and_dangling_outputs_are_rejected(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (self.repo / 'link').symlink_to(outside, target_is_directory=True)
        (self.repo / 'dangling').symlink_to(outside / 'target')
        for field in ('output', 'manifest'):
            for path in ('link/new', 'dangling'):
                with self.subTest(field=field, path=path):
                    result = self.cli(path if field == 'output' else 'board.deb',
                                      path if field == 'manifest' else None)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(list(outside.iterdir()), [])
                    self.assertFalse((self.repo / 'board.deb').exists())
                for artifact in outside.iterdir():
                    artifact.unlink()
                (self.repo / 'board.deb').unlink(missing_ok=True)

    def test_output_and_manifest_must_be_distinct(self):
        result = self.cli('same', 'same')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.repo / 'same').exists())

    def test_nested_absolute_and_relative_outputs_preserve_hash_binding(self):
        for index, absolute in enumerate((False, True)):
            output = Path(f'preflight-{index}/board-input/board.deb')
            manifest = Path(f'preflight-{index}/board-manifest.json')
            result = self.cli(self.repo / output if absolute else output, manifest)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((self.repo / manifest).read_text())
            self.assertEqual(data['source_revision'], self.revision)
            self.assertEqual(data['source_date_epoch'], int(self.epoch))
            self.assertEqual(data['source_lock_sha256'], hashlib.sha256(
                (self.repo / 'project/cm3-cli/source-lock.json').read_bytes()).hexdigest())
            self.assertEqual(data['packages']['cm3-cli-board-support']['sha256'],
                             hashlib.sha256((self.repo / output).read_bytes()).hexdigest())

    def test_existing_outputs_and_source_mismatch_remain_rejected(self):
        (self.repo / 'existing').write_text('sentinel')
        for output, manifest in [('existing', None), ('new.deb', 'existing')]:
            result = self.cli(output, manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((self.repo / 'existing').read_text(), 'sentinel')
            self.assertFalse((self.repo / 'new.deb').exists())
        for revision, epoch in [('a' * 40, self.epoch), (self.revision, '0')]:
            result = self.cli('new.deb', revision=revision, epoch=epoch)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.repo / 'new.deb').exists())
        (self.repo / 'LICENSE').write_text('dirty fixture')
        result = self.cli('new.deb')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.repo / 'new.deb').exists())

    def test_imported_builder_keeps_absolute_scratch_outputs(self):
        spec = importlib.util.spec_from_file_location('boundary_builder', self.script)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        destination = self.base / 'scratch/board.deb'
        self.assertEqual(builder.build(destination, 'a' * 40, 1700000000), destination)
        self.assertTrue(destination.is_file())


if __name__ == '__main__':
    unittest.main()
