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
    def test_jsonnet_only_reuses_verified_archive_without_frontend_or_apt(self):
        import io
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def isolated_path(value):
                path = Path(value)
                return root / path.relative_to('/usr/local') if str(path).startswith('/usr/local/') else path
            (root / 'bin').mkdir()
            with patch.object(tools, 'Path', side_effect=isolated_path), \
                    patch.object(tools.os, 'geteuid', return_value=0), \
                    patch.dict('os.environ', GITHUB_ACTIONS='true', GITHUB_REPOSITORY='blockdyor/radxa-cm3-debian-cli'), \
                    patch.object(tools.urllib.request, 'urlopen', return_value=io.BytesIO(b'archive fixture')) as download, \
                    patch.object(tools, 'verified_jsonnet', return_value={'jsonnet': b'binary fixture', 'LICENSE': b'notice fixture'}) as verify, \
                    patch.object(tools.subprocess, 'run') as runner:
                tools.main(jsonnet_only=True)
            self.assertEqual(download.call_args.args[0], tools.JSONNET_URL)
            self.assertEqual(download.call_count, 1)
            self.assertEqual(verify.call_count, 1)
            self.assertEqual([call.args[0] for call in runner.call_args_list], [['jsonnet', '--version']])
            self.assertEqual((root / 'bin/jsonnet').read_bytes(), b'binary fixture')
            self.assertEqual((root / 'share/doc/go-jsonnet/LICENSE').read_bytes(), b'notice fixture')

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
        self.assertIn('sh /src/scripts/cm3-external-preflight.sh', workflow)
        workflow = (ROOT / 'scripts/cm3-external-preflight.sh').read_text()
        setup = 'python3 /src/scripts/cm3-bootstrap-tools.py'
        compile_at = workflow.index('python3 /src/scripts/cm3-source-preflight.py --workdir /work')
        self.assertLess(workflow.index(setup), compile_at)
        prerequisites = ('apt-get install -y --no-install-recommends python3 ca-certificates '
                         'apt-utils gnupg gpgv mmdebstrap arch-test debian-archive-keyring mount')
        self.assertLess(workflow.index(prerequisites), workflow.index(setup))
        self.assertLess(workflow.index('command -v jsonnet'), compile_at)
        self.assertIn('binutils libc6-dev openssh-client', workflow)
        self.assertLess(workflow.index('cm3-image-stage-a.py tests'), compile_at)
        stage = (ROOT / 'scripts/cm3-image-stage-a.py').read_text()
        self.assertIn("discover(str(ROOT / 'tests/cm3-cli'))", stage)
        self.assertIn('not result.skipped', stage)
        self.assertNotIn('ProfileRendering.test_legacy', workflow)
        self.assertNotIn('jsonnet bdebstrap', workflow)
        source = (ROOT / 'scripts/cm3-bootstrap-tools.py').read_text()
        self.assertNotIn('/etc/apt/', source)
        self.assertNotIn('allow-unauthenticated', source)
        self.assertNotIn('trusted=yes', source)
        self.assertIn("'jsonnet', str(path)", source)

    def test_pinned_jsonnet_archive_rejects_tamper_and_symlink_member(self):
        import hashlib
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'tool.tar.gz'
            for symlink in [False, True]:
                with tarfile.open(path, 'w:gz') as archive:
                    for name in ['jsonnet', 'LICENSE']:
                        item = tarfile.TarInfo(name)
                        data = b'test fixture'
                        item.size = len(data)
                        if symlink and name == 'jsonnet':
                            item.type = tarfile.SYMTYPE
                            item.linkname = '/outside'
                            archive.addfile(item)
                        else:
                            archive.addfile(item, io.BytesIO(data))
                with patch.object(tools, 'JSONNET_SHA256', hashlib.sha256(path.read_bytes()).hexdigest()):
                    if symlink:
                        with self.assertRaises(ValueError):
                            tools.verified_jsonnet(path)
                    else:
                        self.assertEqual(tools.verified_jsonnet(path)['jsonnet'], b'test fixture')
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    tools.verified_jsonnet(path)
