"""Exact rkbin byte pins and preservation of its redistribution notice."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('source', ROOT / 'scripts/cm3-source-preflight.py')
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class LoaderInputsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.recipe = self.root / 'recipe'
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        (self.recipe / 'debian').mkdir(parents=True)
        self.pins = {}
        for name in source.RKBIN_INPUTS:
            path = self.recipe / 'rkbin' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = ('synthetic fixture ' + name).encode()
            path.write_bytes(data)
            self.pins[name] = hashlib.sha256(data).hexdigest()
        (self.recipe / 'rkbin/bin/rk35/rk3566_bl31_v1.46.elf').symlink_to('rk3568_bl31_v1.46.elf')
        self.patch = patch.object(source, 'RKBIN_INPUTS', self.pins)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_verified_inputs_record_hashes_notice_and_exact_bl31_alias(self):
        source.verify_loader_inputs(self.recipe, self.evidence)
        report = json.loads((self.evidence / 'loader-inputs.json').read_text())
        self.assertEqual(report['sha256'], self.pins)
        self.assertEqual(report['bl31_alias'], 'rk3568_bl31_v1.46.elf')
        self.assertEqual(report['license_text'], (self.recipe / 'rkbin/LICENSE').read_text())
        self.assertEqual((self.recipe / 'debian/u-boot-rk2601.docs').read_text(), 'rkbin/LICENSE\n')
        self.assertEqual(report['distribution_review'], 'INCOMPLETE: full corresponding-source and payload review required')
        subprocess.run(['git', 'init', '-q', str(self.recipe)], check=True)
        subprocess.run(['git', '-C', str(self.recipe), 'add', '--intent-to-add',
                        'debian/u-boot-rk2601.docs'], check=True)
        diff = subprocess.check_output(['git', '-C', str(self.recipe), 'diff', '--binary'], text=True)
        self.assertIn('new file mode 100644', diff)
        self.assertIn('+rkbin/LICENSE', diff)

    def test_changed_missing_and_symlinked_input_rejected_before_notice_write(self):
        for name in self.pins:
            with self.subTest(name=name):
                path = self.recipe / 'rkbin' / name
                data = path.read_bytes()
                for mode in ['changed', 'missing', 'symlink']:
                    with self.subTest(mode=mode):
                        path.unlink()
                        if mode == 'changed':
                            path.write_bytes(data + b'changed')
                        elif mode == 'symlink':
                            target = self.root / 'outside'
                            target.write_bytes(data)
                            path.symlink_to(target)
                        with self.assertRaises(ValueError):
                            source.verify_loader_inputs(self.recipe, self.evidence)
                        self.assertFalse((self.recipe / 'debian/u-boot-rk2601.docs').exists())
                        if path.exists() or path.is_symlink():
                            path.unlink()
                        path.write_bytes(data)

    def test_bl31_alias_cannot_escape_or_change_target(self):
        path = self.recipe / 'rkbin/bin/rk35/rk3566_bl31_v1.46.elf'
        for target in ['../../../../outside', 'rk3568_bl31_v1.45.elf']:
            path.unlink()
            path.symlink_to(target)
            with self.assertRaises(ValueError):
                source.verify_loader_inputs(self.recipe, self.evidence)
        path.unlink()
        path.write_text('not the upstream alias')
        with self.assertRaises(ValueError):
            source.verify_loader_inputs(self.recipe, self.evidence)

    def test_parent_symlink_and_existing_docs_are_not_followed_or_overwritten(self):
        path = self.recipe / 'rkbin/tools'
        path.rename(self.recipe / 'rkbin/moved-tools')
        path.symlink_to('moved-tools')
        with self.assertRaises(ValueError):
            source.verify_loader_inputs(self.recipe, self.evidence)
        path.unlink()
        (self.recipe / 'rkbin/moved-tools').rename(path)
        docs = self.recipe / 'debian/u-boot-rk2601.docs'
        docs.write_text('upstream docs changed\n')
        with self.assertRaises(FileExistsError):
            source.verify_loader_inputs(self.recipe, self.evidence)
        self.assertEqual(docs.read_text(), 'upstream docs changed\n')


if __name__ == '__main__':
    unittest.main()
