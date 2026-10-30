"""Actual rendering/crypto fixtures; bootstrap executes only in the admitted external job."""
import hashlib
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
SPEC = importlib.util.spec_from_file_location('rsdk_profile', ROOT / 'scripts/cm3-rsdk-profile.py')
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


def receipt():
    lock = profile.probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    expected = profile.probe.source.expected_packages(lock)
    expected['cm3-cli-board-support'] = ('0.1.0', 'all')
    specs = [f'{name}={version}' for name, (version, _) in sorted(expected.items())]
    return {'status': 'PASS', 'source_revision': 'a' * 40, 'source_lock_sha256': 'b' * 64,
            'packages': specs, 'headers': [s for s in specs if s.startswith('linux-headers-')],
            'board_sha256': 'c' * 64}


@unittest.skipUnless(shutil.which('jsonnet'), 'Jsonnet executable required for actual rendering')
class ProfileRendering(unittest.TestCase):
    def test_exact_profile_has_no_inherited_trust_or_provisioning_hooks(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'rootfs.json'
            config = profile.render(Path(temporary), receipt(), output)
        self.assertEqual(config['mmdebstrap']['architectures'], ['arm64'])
        self.assertEqual(config['mmdebstrap']['suite'], 'trixie')
        self.assertEqual(config['metadata']['product'], 'radxa-cm3-rpi-cm4-io')
        self.assertIn('HELD', config['metadata']['image_assembly'])
        text = json.dumps(config)
        for forbidden in ['trusted=yes', 'allow-unauthenticated', 'allow-downgrades', '1999',
                          'pkgs.json', 'rsetup', 'task-', 'bookworm', 'backports', 'r8125',
                          'cloud-initramfs-growroot', 'force-confnew', 'radxa-repo.github.io']:
            self.assertNotIn(forbidden, text)
        mirrors = config['mmdebstrap']['mirrors']
        self.assertEqual(len(mirrors), 3)
        self.assertTrue(all('signed-by=/usr/share/keyrings/debian-archive-keyring.gpg' in m for m in mirrors))
        self.assertIn('trixie-updates main non-free-firmware', mirrors[1])
        self.assertIn('trixie-security main non-free-firmware', mirrors[2])
        self.assertIn('APT::Install-Recommends "false"', config['mmdebstrap']['aptopts'])
        self.assertNotIn('aptopt', config['mmdebstrap'])
        self.assertEqual(config['mmdebstrap'].get('essential-hooks', []), [])
        self.assertIn('ca-certificates', config['mmdebstrap']['packages'])
        self.assertIn('debian-archive-keyring', config['mmdebstrap']['packages'])
        hook = config['mmdebstrap']['customize-hooks'][0]
        for seed in profile.probe.SEEDS + profile.probe.TOOLS:
            self.assertIn(seed, hook.split())
        self.assertLess(hook.index('sha256sum -c'), hook.index('dpkg --unpack'))
        self.assertLess(hook.index('dpkg --unpack'), hook.index('test "$(readlink'))
        self.assertLess(hook.index('test "$(readlink'), hook.index('linux-image-radxa-cm3-rpi-cm4-io='))
        self.assertIn('rm -f "$1"/etc/ssh/ssh_host_*', config['mmdebstrap']['customize-hooks'][1])
        self.assertIn('rm -f "$1/etc/apt/sources.list.d/cm3-build.list"',
                      config['mmdebstrap']['customize-hooks'][1])
        self.assertTrue(any('machine-id' in s for s in config['mmdebstrap']['cleanup-hooks']))

    def evaluate(self, **changes):
        args = dict(product='radxa-cm3-rpi-cm4-io', suite='trixie', edition='cli',
                    temp_dir='/unused', output_dir='/unused', build_date='', rsdk_rev='a' * 40,
                    cm3_preflight=receipt())
        args.update(changes)
        command = ['jsonnet', '--ext-code', 'sdboot=false']
        for key, value in args.items():
            command += ['--tla-code', key + '=' + json.dumps(value)]
        return subprocess.run(command + [str(ROOT / 'src/share/rsdk/build/rootfs.jsonnet')],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_missing_failed_stale_receipt_and_overrides_fail_closed(self):
        for change in [dict(cm3_preflight=None), dict(cm3_preflight=dict(receipt(), status='FAIL')),
                       dict(rsdk_rev='d' * 40), dict(architecture='amd64'), dict(mode='unshare'),
                       dict(distro_mirror='https://example.org'), dict(snapshot_timestamp='20260101T000000Z'),
                       dict(radxa_mirror='https://example.org'), dict(radxa_repo_suffix='-test'),
                       dict(linux_override='other'), dict(firmware_override='other'), dict(install_vscodium=True),
                       dict(cm3_preflight=dict(receipt(), packages=[]))]:
            with self.subTest(change=change):
                self.assertNotEqual(self.evaluate(**change).returncode, 0)

    def test_sibling_and_legacy_routes_unchanged(self):
        # Compare full rendered configs, not a substring of the modified source.
        old = subprocess.check_output(['git', 'show', 'd58c5db:src/share/rsdk/build/rootfs.jsonnet'],
                                      cwd=ROOT, text=True)
        build = ROOT / 'src/share/rsdk/build'
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary) / 'original.jsonnet'
            original.write_text(old)
            for product, suite, edition in [('radxa-cm3-io', 'bookworm', 'kde'),
                                            ('radxa-cm3-rpi-cm4-io', 'bookworm', 'kde'),
                                            ('rock-3c', 'trixie', 'cli')]:
                args = ['jsonnet', '-J', str(build), '--ext-code', 'sdboot=false']
                for key, value in dict(product=product, suite=suite, edition=edition,
                                       temp_dir='/unused', output_dir='/unused', build_date='fixed').items():
                    args += ['--tla-str', key + '=' + value]
                before = subprocess.check_output(args + [str(original)], text=True)
                after = subprocess.check_output(args + [str(build / 'rootfs.jsonnet')], text=True)
                self.assertEqual(json.loads(before), json.loads(after))

    def test_shell_paths_are_quoted(self):
        with tempfile.TemporaryDirectory(prefix="cm3-profile-' $(false) ") as temporary:
            config = profile.render(Path(temporary), receipt(), Path(temporary) / 'config.json')
            hook = config['mmdebstrap']['customize-hooks'][0]
            self.assertIn("'\"'\"'", hook)

    def test_only_exact_product_defaults_change_and_image_hold_stays(self):
        current = json.loads((ROOT / 'src/share/rsdk/configs/products.json').read_text())
        original = json.loads(subprocess.check_output(['git', 'show', 'd58c5db:src/share/rsdk/configs/products.json'], cwd=ROOT))
        different = [(a, b) for a, b in zip(original, current) if a != b]
        self.assertEqual(len(original), len(current))
        self.assertEqual(len(different), 1)
        a, b = different[0]
        self.assertEqual(a['product'], 'radxa-cm3-rpi-cm4-io')
        self.assertEqual(b, dict(a, supported_suite=['trixie'], supported_edition=['cli']))
        entry = (ROOT / 'src/libexec/rsdk/rsdk-build').read_text()
        self.assertIn('CM3 Trixie CLI image assembly is disabled', entry)

    def test_receipt_is_json_data_not_a_file_path_or_injected_jsonnet(self):
        data = receipt()
        data['scope'] = '\" + (error "injected") + \" $(false) ../untrusted'
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            output = stage / 'config.json'
            with patch.object(profile.subprocess, 'check_output', wraps=subprocess.check_output) as invoke:
                config = profile.render(stage, data, output)
                args = invoke.call_args.args[0]
                self.assertIn('--tla-code', args)
                self.assertNotIn('--tla-code-file', args)
            self.assertEqual(config['metadata']['signed_package_preflight']['scope'], data['scope'])
            self.assertEqual(list(stage.iterdir()), [output])


class ReceiptBoundary(unittest.TestCase):
    def test_only_empty_root_ssh_directory_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / 'root'
            home.mkdir()
            directory = home / '.ssh'
            profile.remove_empty_root_ssh(root)
            directory.mkdir(mode=0o700)
            profile.remove_empty_root_ssh(root)
            self.assertFalse(directory.exists())
            directory.mkdir()
            marker = directory / 'authorized_keys'
            marker.write_text('test-only marker, not a key')
            with self.assertRaisesRegex(ValueError, 'not an empty directory'):
                profile.remove_empty_root_ssh(root)
            self.assertEqual(marker.read_text(), 'test-only marker, not a key')
            marker.unlink()
            directory.rmdir()
            directory.write_text('unexpected file')
            with self.assertRaisesRegex(ValueError, 'not an empty directory'):
                profile.remove_empty_root_ssh(root)
            self.assertEqual(directory.read_text(), 'unexpected file')
            directory.unlink()
            for destination in [home / 'missing', home]:
                directory.symlink_to(destination, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'redirected'):
                    profile.remove_empty_root_ssh(root)
                self.assertTrue(directory.is_symlink())
                directory.unlink()
            home.rmdir()
            home.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'redirected'):
                profile.remove_empty_root_ssh(root)

    def test_wrong_admission_or_failed_probe_stops_before_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            evidence = work / 'evidence'
            evidence.mkdir()
            root = work / 'source'
            admission_dir = root / 'preflight-work/evidence'
            admission_dir.mkdir(parents=True)
            admission_path = admission_dir / 'package-admission.json'
            admission_path.write_text(json.dumps({
                'status': 'ADMITTED', 'commit': 'a' * 40, 'run_id': 10, 'maximum_attempts': None,
                'cumulative_attempts': 10, 'authorization': 'owner-2026-10-29-evidence-based-development',
            }))
            with patch.object(profile, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'same-job admission'):
                    profile.verified_receipt(work, 'a' * 40, 11)
                (evidence / 'result.json').write_text(json.dumps({'status': 'FAIL', 'image_build': 'NOT RUN'}))
                with self.assertRaisesRegex(ValueError, 'signed ARM64'):
                    profile.verified_receipt(work, 'a' * 40, 10)

    def test_repository_rejects_unreviewed_files_before_crypto(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'signing fingerprint'):
                profile.verify_repository(repo, {}, 'bad')
            (repo / 'private-key').write_text('not an actual key')
            with self.assertRaisesRegex(ValueError, 'repository contents'):
                profile.verify_repository(repo, {}, 'A' * 40)


@unittest.skipUnless(all(shutil.which(tool) for tool in ['gpg', 'gpg-agent', 'gpgv', 'dpkg-deb']),
                     'GnuPG and dpkg-deb required for real signed fixture checks')
class SignedRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='gpg-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        home = cls.base / 'g'
        home.mkdir(mode=0o700)
        cls.gpg = ['gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback',
                   '--passphrase', '', '--agent-program', shutil.which('gpg-agent')]
        subprocess.run(cls.gpg + ['--quick-generate-key', 'CM3 TEST FIXTURE', 'ed25519', 'sign', '1d'],
                       check=True, capture_output=True)
        listing = subprocess.check_output(cls.gpg + ['--with-colons', '--fingerprint'], text=True)
        cls.fingerprint = next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
        package = cls.base / 'package'
        (package / 'DEBIAN').mkdir(parents=True)
        (package / 'DEBIAN/control').write_text(
            'Package: cm3-test-fixture\nVersion: 1\nArchitecture: all\n'
            'Maintainer: CM3 Test\nDescription: disposable test fixture, never installed\n')
        cls.deb = cls.base / 'cm3-test-fixture_1_all.deb'
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', '--', str(package), str(cls.deb)],
                       check=True, capture_output=True)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='cm3-repository-test-')
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        (self.repo / 'pool').mkdir()
        shutil.copyfile(self.deb, self.repo / 'pool' / self.deb.name)
        self.packages = {'cm3-test-fixture': self.deb}
        self.index = (
            'Package: cm3-test-fixture\nVersion: 1\nArchitecture: all\n'
            f'Filename: pool/{self.deb.name}\nSize: {self.deb.stat().st_size}\n'
            f'SHA256: {profile.probe.digest(self.deb)}\n\n')
        subprocess.run(self.gpg + ['--output', str(self.repo / 'archive-key.gpg'),
                                  '--export', self.fingerprint], check=True, capture_output=True)
        self.sign(self.index)

    def sign(self, index):
        (self.repo / 'Packages').write_text(index)
        release = self.repo / 'Release'
        release.write_text('Origin: CM3-TEST-FIXTURE\nSHA256:\n '
                           + profile.probe.digest(self.repo / 'Packages') + ' '
                           + str((self.repo / 'Packages').stat().st_size) + ' Packages\n')
        for name, mode in [('InRelease', '--clearsign'), ('Release.gpg', '--detach-sign')]:
            subprocess.run(self.gpg + ['--yes', '--output', str(self.repo / name), mode, str(release)],
                           check=True, capture_output=True)

    def test_real_signature_index_and_payload_closure(self):
        profile.verify_repository(self.repo, self.packages, self.fingerprint)

    def test_bad_signature_signer_index_release_and_payload_rejected(self):
        for name in ['InRelease', 'Release', 'Packages', 'pool/' + self.deb.name]:
            with self.subTest(name=name):
                path = self.repo / name
                original = path.read_bytes()
                path.write_bytes(original.replace(b'CM3-TEST-FIXTURE', b'CM3-BAD--FIXTURE', 1)
                                 if name in ['InRelease', 'Release'] else original + b'bad')
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    profile.verify_repository(self.repo, self.packages, self.fingerprint)
                path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'signer'):
            profile.verify_repository(self.repo, self.packages, '0' * 40)

    def test_signed_wrong_identity_traversal_duplicate_and_missing_rejected(self):
        for index in [self.index.replace('Version: 1', 'Version: 2'),
                      self.index.replace('Architecture: all', 'Architecture: amd64'),
                      self.index.replace('Filename: pool/', 'Filename: ../'),
                      self.index.replace('Size: ', 'Size: 0'), self.index + self.index, '']:
            with self.subTest(index=index):
                self.sign(index)
                with self.assertRaises(ValueError):
                    profile.verify_repository(self.repo, self.packages, self.fingerprint)

    def test_extra_and_symlinked_payloads_rejected(self):
        extra = self.repo / 'pool/extra.deb'
        extra.write_text('extra')
        with self.assertRaises(ValueError):
            profile.verify_repository(self.repo, self.packages, self.fingerprint)
        extra.unlink()
        payload = self.repo / 'pool' / self.deb.name
        payload.unlink()
        payload.symlink_to(self.deb)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            profile.verify_repository(self.repo, self.packages, self.fingerprint)


class ProfileIntegration(unittest.TestCase):
    def test_bootstrap_rejects_existing_or_symlinked_root_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            root = stage / 'root'
            root.mkdir()
            with patch.object(profile.probe, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'fresh profile'):
                    profile.bootstrap(stage, stage / 'config.json', receipt(), stage)
                command.assert_not_called()
            root.rmdir()
            root.symlink_to(stage / 'missing')
            with patch.object(profile.probe, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'fresh profile'):
                    profile.bootstrap(stage, stage / 'config.json', receipt(), stage)
                command.assert_not_called()

    def test_bootstrap_failure_propagates_without_success_or_package_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            failure = subprocess.CalledProcessError(1, ['bdebstrap'])
            with patch.object(profile.probe, 'command', side_effect=failure) as command, \
                    patch.object(profile.probe, 'chroot') as chroot:
                with self.assertRaises(subprocess.CalledProcessError):
                    profile.bootstrap(stage, stage / 'config.json', receipt(), stage)
                command.assert_called_once_with('bdebstrap', '--config', stage / 'config.json',
                                                '--name', 'cm3-profile-fixture',
                                                '--output', stage / 'bootstrap-log')
                chroot.assert_not_called()
            self.assertFalse((stage / 'rsdk-profile-packages.tsv').exists())

    def test_profile_only_follows_signed_probe_and_never_assembles_an_image(self):
        text = (ROOT / '.github/workflows/build.yaml').read_text()
        self.assertIn('sh /src/scripts/cm3-external-preflight.sh', text)
        text = (ROOT / 'scripts/cm3-external-preflight.sh').read_text()
        self.assertLess(text.index('python3 /src/scripts/cm3-package-preflight.py --workdir /work'),
                        text.index('python3 /src/scripts/cm3-rsdk-profile.py --workdir /work'))
        entry = (ROOT / 'scripts/cm3-rsdk-profile.py').read_text()
        self.assertNotIn("['mmdebstrap',", entry)
        self.assertNotIn('rsdk-build', entry)
        self.assertIn("probe.command('bdebstrap', '--config', output", entry)
        self.assertNotIn("'--force'", entry)
        self.assertIn("'rootfs=' + str(stage / 'root')", entry)
