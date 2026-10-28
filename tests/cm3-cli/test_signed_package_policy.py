import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('package_preflight', ROOT / 'scripts/cm3-package-preflight.py')
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class SignedPackagePolicyTests(unittest.TestCase):
    def setUp(self):
        lock = preflight.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
        self.expected = preflight.source.expected_packages(lock)
        self.manifest = {name: {'version': version, 'architecture': arch, 'sha256': 'a' * 64}
                         for name, (version, arch) in self.expected.items()}

    def test_exact_manifest_identity_and_sha256_validation(self):
        preflight.verify_manifest(self.manifest, self.expected)
        for field, value in [('version', '6.1.84-18'), ('architecture', 'amd64'),
                             ('sha256', 'not-a-digest')]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.manifest)
                data[next(iter(data))][field] = value
                with self.assertRaises(ValueError):
                    preflight.verify_manifest(data, self.expected)

    def test_missing_and_extra_packages_rejected(self):
        data = copy.deepcopy(self.manifest)
        del data[next(iter(data))]
        with self.assertRaises(ValueError):
            preflight.verify_manifest(data, self.expected)
        data = copy.deepcopy(self.manifest)
        data['linux-libc-dev'] = next(iter(data.values()))
        with self.assertRaises(ValueError):
            preflight.verify_manifest(data, self.expected)

    def test_digest_and_fixture_write_are_real_and_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            preflight.put(root, 'etc/test.conf', 'fixture-only\n')
            self.assertEqual(preflight.digest(root / 'etc/test.conf'),
                             hashlib.sha256(b'fixture-only\n').hexdigest())
            self.assertEqual((root / 'etc/test.conf').stat().st_mode & 0o777, 0o644)

    def test_local_execution_refused_before_any_install(self):
        result = subprocess.run(['python3', str(ROOT / 'scripts/cm3-package-preflight.py'),
                                 '--workdir', '/work'], capture_output=True, text=True,
                                env={'PATH': '/usr/local/bin:/usr/bin:/bin'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('restricted to external disposable AMD64 CI container', result.stderr)

    def test_preserved_userspace_seeds_and_deliberate_target_toolchain(self):
        self.assertEqual(len(preflight.SEEDS), 32)
        self.assertEqual(len(set(preflight.SEEDS)), 32)
        self.assertNotIn('radxa-system-config-kernel-cmdline-ttyfiq0', preflight.SEEDS)
        for name in ['apt', 'openssh-server', 'network-manager', 'systemd-timesyncd',
                     'nftables', 'radxa-bootutils', 'radxa-udev']:
            self.assertIn(name, preflight.SEEDS)
        for name in ['gcc', 'make', 'dkms', 'device-tree-compiler', 'apparmor',
                     'firmware-brcm80211', 'firmware-realtek']:
            self.assertIn(name, preflight.TOOLS)

    def test_foreign_bootstrap_dependency_is_explicit_without_recommends(self):
        tree = ast.parse((ROOT / 'scripts/cm3-package-preflight.py').read_text())
        installs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'command':
                args = [value.value for value in node.args if isinstance(value, ast.Constant)]
                if args[:2] == ['apt-get', 'install']:
                    installs.append(args)
        self.assertEqual(len(installs), 1)
        self.assertIn('--no-install-recommends', installs[0])
        self.assertIn('arch-test', installs[0])
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        container_command = workflow.split("sh -ec '", 1)[1].split("' \\", 1)[0]
        self.assertIn('apt-get install -y --no-install-recommends python3', container_command)
        self.assertIn('python3 ca-certificates arch-test;', container_command)
        self.assertLess(container_command.index('arch-test arm64;'),
                        container_command.index('python3 /src/scripts/cm3-source-preflight.py'))

    def test_boot_fixture_uses_supported_dropin_not_package_conffile(self):
        text = (ROOT / 'scripts/cm3-package-preflight.py').read_text()
        tree = ast.parse(text)
        puts = {node.args[1].value: node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'put' and isinstance(node.args[1], ast.Constant)}
        self.assertNotIn('etc/default/u-boot', puts)
        fragment = 'etc/u-boot-menu/conf.d/99-cm3-preflight.conf'
        self.assertIn(fragment, puts)
        content = ast.get_source_segment(text, puts[fragment].args[2])
        assert content is not None
        self.assertIn('console=ttyFIQ0,1500000n8 apparmor=1 security=apparmor', content)
        self.assertIn('rockchip/{DTB}', content)
        self.assertNotIn('--force-conf', text)

    def test_probe_is_not_image_or_update_trust_pass(self):
        text = (ROOT / 'scripts/cm3-package-preflight.py').read_text()
        for prohibited in ['trusted=yes', 'allow-unauthenticated', 'allow-insecure',
                           'allow-downgrades', 'bookworm', 'parted', 'mkfs', 'resize2fs']:
            self.assertNotIn(prohibited, text)
        for required in ['NOT COMPLETE', 'NOT IMPLEMENTED: boot configuration is a test fixture',
                         'NOT TESTED: chroot is not a target kernel boot',
                         'NOT TESTED: reinstall only', '--variant=minbase',
                         '--sign', 'signed-by=/usr/share/keyrings/cm3-preflight.gpg']:
            if required == '--sign':
                self.assertIn("'--clearsign'", text)
            else:
                self.assertIn(required, text)
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        self.assertIn('scripts/cm3-package-preflight.py --workdir /work', workflow)
        self.assertNotIn('package-work/signed-repository/', workflow)
        self.assertNotIn('package-work/arm64-root/', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertNotIn('id-token: write', workflow)


if __name__ == '__main__':
    unittest.main()
