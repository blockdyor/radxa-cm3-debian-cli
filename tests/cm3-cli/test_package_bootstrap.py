"""Real isolated APT solver regression; never installs packages or touches host state."""
import ast
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('bootstrap_probe', ROOT / 'scripts/cm3-package-preflight.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class PackageBootstrapTests(unittest.TestCase):
    def test_growth_dependencies_precede_board_unpack(self):
        self.assertTrue({'fdisk', 'cloud-guest-utils'} <= set(probe.SEEDS + probe.TOOLS))
        tree = ast.parse((ROOT / 'scripts/cm3-package-preflight.py').read_text())
        target = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'test_target')
        calls = [node.value for node in target.body if isinstance(node, ast.Expr)
                 and isinstance(node.value, ast.Call)]
        self.assertEqual(ast.unparse(calls[0]), "apt(root, 'install', '-y', *SEEDS, *TOOLS)")
        self.assertEqual(ast.unparse(calls[2]), 'install_board_policy(root, board)')
        self.assertEqual(calls[3].func.id, 'apt')

    @unittest.skipUnless(shutil.which('apt-get'), 'APT solver required')
    def test_real_solver_unpacked_board_requires_preinstalled_growth_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['lists/partial', 'cache/archives/partial', 'sourceparts', 'preferences.d', 'apt.conf.d']:
                (root / name).mkdir(parents=True)
            (root / 'sources.list').write_text('deb http://fixture.invalid/debian trixie main\n')
            packages = ''.join(
                f'Package: {name}\nVersion: 1\nArchitecture: arm64\n'
                f'Filename: pool/{name}.deb\nSize: 1\nSHA256: {"a" * 64}\nDescription: solver fixture\n\n'
                for name in ['fdisk', 'cloud-guest-utils'])
            (root / 'lists/fixture.invalid_debian_dists_trixie_main_binary-arm64_Packages').write_text(packages)
            board = ('Package: cm3-cli-board-support\nStatus: install ok unpacked\n'
                     'Architecture: all\nVersion: 0.1.0\nDepends: fdisk, cloud-guest-utils\n'
                     'Description: unpacked board fixture\n\n')
            options = {
                'Dir::State::status': root / 'status', 'Dir::State::lists': root / 'lists',
                'Dir::Cache': root / 'cache', 'Dir::Etc::sourcelist': root / 'sources.list',
                'Dir::Etc::sourceparts': root / 'sourceparts', 'Dir::Etc::main': root / 'apt.conf',
                'Dir::Etc::parts': root / 'apt.conf.d', 'Dir::Etc::preferences': root / 'preferences',
                'Dir::Etc::preferencesparts': root / 'preferences.d',
                'APT::Architecture': 'arm64', 'APT::Architectures::': 'arm64',
                'Debug::NoLocking': 'true', 'APT::Install-Recommends': 'false',
                'APT::Install-Suggests': 'false',
            }
            command = ['apt-get']
            for name, value in options.items():
                command.extend(['-o', f'{name}={value}'])
            command.extend(['--simulate', 'install', 'cm3-cli-board-support=0.1.0'])
            for installed in [False, True]:
                status = board
                if installed:
                    for name in ['fdisk', 'cloud-guest-utils']:
                        status += (f'Package: {name}\nStatus: install ok installed\n'
                                   'Architecture: arm64\nVersion: 1\nDescription: fixture\n\n')
                (root / 'status').write_text(status)
                result = subprocess.run(command, text=True, capture_output=True, timeout=20,
                                        env=dict(os.environ, LC_ALL='C', APT_CONFIG='/dev/null'))
                with self.subTest(dependencies_preinstalled=installed):
                    if installed:
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn('Conf cm3-cli-board-support', result.stdout)
                    else:
                        self.assertEqual(result.returncode, 100, result.stdout + result.stderr)
                        self.assertIn('Unmet dependencies', result.stderr)


if __name__ == '__main__':
    unittest.main()
