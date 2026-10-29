"""Exercise exact frontend bytes/identity and fail-early workflow ordering."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('bootstrap_tools', ROOT / 'scripts/cm3-bootstrap-tools.py')
tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tools)


class BootstrapTools(unittest.TestCase):
    def test_corrupt_download_rejected_before_package_parsing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'tool.deb'
            path.write_bytes(b'corrupt download')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                tools.verify_package(path)

    def test_real_deb_identity_checked_even_when_digest_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            control = directory / 'root/DEBIAN'
            control.mkdir(parents=True)
            for name, version, arch, valid in [
                    ('bdebstrap', '0.8.1-2', 'all', True),
                    ('other', '0.8.1-2', 'all', False),
                    ('bdebstrap', '0.5.0-1', 'all', False),
                    ('bdebstrap', '0.8.1-2', 'amd64', False)]:
                with self.subTest(name=name, version=version, arch=arch):
                    (control / 'control').write_text(
                        f'Package: {name}\nVersion: {version}\nArchitecture: {arch}\n'
                        'Maintainer: Fixture <fixture@example.invalid>\nDescription: Fixture only\n')
                    path = directory / 'tool.deb'
                    subprocess.run(['dpkg-deb', '--build', '--root-owner-group',
                                    str(directory / 'root'), str(path)], check=True,
                                   stdout=subprocess.DEVNULL)
                    with patch.object(tools, 'SHA256', hashlib.sha256(path.read_bytes()).hexdigest()):
                        if valid:
                            tools.verify_package(path)
                        else:
                            with self.assertRaisesRegex(ValueError, 'identity'):
                                tools.verify_package(path)

    def test_tool_qualification_precedes_compilation_and_does_not_add_sid(self):
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        setup = 'python3 /src/scripts/cm3-bootstrap-tools.py;'
        self.assertIn(setup, workflow)
        self.assertLess(workflow.index(setup),
                        workflow.index('python3 /src/scripts/cm3-source-preflight.py --workdir /work'))
        compile_at = workflow.index('python3 /src/scripts/cm3-source-preflight.py --workdir /work')
        prerequisites = ('apt-get install -y --no-install-recommends python3 ca-certificates '
                         'apt-utils gnupg gpgv mmdebstrap arch-test debian-archive-keyring mount;')
        self.assertLess(workflow.index(prerequisites), workflow.index(setup))
        self.assertLess(workflow.index('command -v jsonnet;'), compile_at)
        for method in ('test_exact_profile_has_no_inherited_trust_or_provisioning_hooks',
                       'test_missing_failed_stale_receipt_and_overrides_fail_closed',
                       'test_shell_paths_are_quoted',
                       'test_receipt_is_json_data_not_a_file_path_or_injected_jsonnet'):
            self.assertLess(workflow.index('test_rsdk_profile.ProfileRendering.' + method), compile_at)
        self.assertNotIn('ProfileRendering.test_legacy', workflow)
        self.assertNotIn('jsonnet bdebstrap', workflow)
        source = (ROOT / 'scripts/cm3-bootstrap-tools.py').read_text()
        self.assertNotIn('/etc/apt/', source)
        self.assertNotIn('allow-unauthenticated', source)
        self.assertNotIn('trusted=yes', source)
        self.assertIn("'jsonnet', str(path)", source)
