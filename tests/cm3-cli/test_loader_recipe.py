"""Pinned recipe drift + real fixture.deb helper-byte readback (not a BSP build)."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('source_loader_safety', ROOT / 'scripts/cm3-source-preflight.py')
assert SPEC is not None and SPEC.loader is not None
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class LoaderRecipeTests(unittest.TestCase):
    def test_pinned_script_replacement_drift_and_actual_deb_bytes(self):
        packet = ROOT / 'docs/cm3-cli/evidence/retained-image2/lifecycle/cm3-lifecycle-safety-evidence.zip'
        with zipfile.ZipFile(packet) as archive:
            original = archive.read('subject/usr/lib/u-boot/radxa-cm3-rpi-cm4-io/setup.sh')
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            recipe = base / 'recipe'
            (recipe / 'setup').mkdir(parents=True)
            script = recipe / 'setup/u-boot_setup-rockchip.sh'
            script.write_bytes(original)
            (recipe / 'debian').mkdir()
            (recipe / 'debian/u-boot-rk2601.docs').write_text('rkbin/LICENSE\n')
            (recipe / 'debian/control').write_text('Depends: ${misc:Depends},\nProvides: u-boot-rk2410\n')
            local_make = recipe / '.github/local/Makefile.local'
            local_make.parent.mkdir(parents=True)
            local_make.write_text('define install_uboot\n\tcp setup/u-boot_setup-rockchip.sh out/$@/setup.sh\nendef\n')
            subprocess.run(['git', 'init', '-q', str(recipe)], check=True)
            subprocess.run(['git', '-C', str(recipe), 'add', '.'], check=True)
            source.prepare_loader_safety(recipe)
            self.assertEqual(script.read_bytes(), (ROOT / 'project/cm3-cli/loader-setup.sh').read_bytes())
            self.assertIn('cp setup/loader-target.py out/$@/loader-target.py', local_make.read_text())
            with self.assertRaises(ValueError):
                source.prepare_loader_safety(recipe)
            diff = subprocess.check_output(['git', '-C', str(recipe), 'diff', '--binary'], text=True)
            self.assertIn('loader-target.py', diff)
            self.assertIn('u-boot_setup-rockchip.sh', diff)
            stage = base / 'stage'
            installed = stage / 'usr/lib/u-boot/radxa-cm3-rpi-cm4-io'
            installed.mkdir(parents=True)
            shutil.copyfile(script, installed / 'setup.sh')
            shutil.copyfile(recipe / 'setup/loader-target.py', installed / 'loader-target.py')
            (stage / 'DEBIAN').mkdir()
            (stage / 'DEBIAN/control').write_text('Package: fixture-loader\nVersion: 1\nArchitecture: all\n'
                                                 'Maintainer: Test <test@example.invalid>\nDescription: fixture only\n')
            package = base / 'fixture.deb'
            subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(stage), str(package)],
                           check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(set(source.verify_loader_package(package)), {'setup.sh', 'loader-target.py'})
            (installed / 'setup.sh').write_bytes(original)
            subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(stage), str(package)],
                           check=True, stdout=subprocess.DEVNULL)
            with self.assertRaisesRegex(ValueError, 'differs'):
                source.verify_loader_package(package)
