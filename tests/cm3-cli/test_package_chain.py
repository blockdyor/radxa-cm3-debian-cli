"""Real signed, disposable repository fixtures; no installation or storage writes."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('package_chain', ROOT / 'scripts/cm3-package-chain.py')
assert SPEC is not None and SPEC.loader is not None
chain = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chain)


class IdentityTests(unittest.TestCase):
    def test_capture_refuses_agent_supplied_paths_before_any_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'fixed external'):
                chain.capture(directory, directory / 'output')
            self.assertEqual(list(directory.iterdir()), [])

    def test_invalid_empty_duplicate_or_unconfigured_identities_rejected(self):
        for value in ['', 'a\t1\tarm64\tunpacked\n', 'a;bad\t1\tarm64\tinstalled\n',
                      'a\t1\tamd64\tinstalled\n', 'a\t1\tall\tinstalled\n' * 2]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                chain.identities(value)
        self.assertEqual(chain.identities('a\t1:2+3~4\tall\tinstalled\n'), {('a', '1:2+3~4', 'all')})


@unittest.skipUnless(all(shutil.which(tool) for tool in ['gpg', 'gpg-agent', 'gpgv', 'dpkg-deb']),
                     'GnuPG and dpkg-deb required for real signature fixtures')
class SignedChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='cm3-chain-fixtures-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        cls.home = cls.base / 'g'
        cls.home.mkdir(mode=0o700)
        cls.gpg = ['gpg', '--homedir', str(cls.home), '--batch', '--pinentry-mode', 'loopback',
                   '--passphrase', '', '--agent-program', shutil.which('gpg-agent')]
        for name in ['Debian TEST FIXTURE', 'Local TEST FIXTURE']:
            subprocess.run(cls.gpg + ['--quick-generate-key', name, 'ed25519', 'sign', '1d'],
                           check=True, capture_output=True)
        listing = subprocess.check_output(cls.gpg + ['--with-colons', '--fingerprint'], text=True)
        cls.fingerprints = [line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')]
        cls.package = cls.base / 'package'
        (cls.package / 'DEBIAN').mkdir(parents=True)
        (cls.package / 'DEBIAN/control').write_text('Package: cm3-chain-fixture\nVersion: 1\nArchitecture: all\n'
                                                   'Maintainer: Test\nDescription: never installed\n')
        cls.deb = cls.base / 'fixture.deb'
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(cls.package), str(cls.deb)],
                       check=True, capture_output=True)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='cm3-chain-test-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for name in ['releases', 'indexes', 'packages']:
            (self.directory / name).mkdir()
        self.payload = self.directory / 'packages/fixture.deb'
        shutil.copyfile(self.deb, self.payload)
        self.index = self.directory / 'indexes/Packages'
        self.index.write_text('Package: cm3-chain-fixture\nVersion: 1\nArchitecture: all\n'
                              'Filename: packages/fixture.deb\n'
                              'SHA256: ' + chain.digest(self.payload) + '\nSize: ' + str(self.payload.stat().st_size) + '\n\n')
        (self.directory / 'installed.tsv').write_text('cm3-chain-fixture\t1\tall\tinstalled\n')
        for index, filename in enumerate(['debian-archive-keyring.gpg', 'local-archive-key.gpg']):
            (self.directory / filename).write_bytes(subprocess.check_output(
                self.gpg + ['--export', self.fingerprints[index]]))
        self.anchor = chain.digest(self.directory / 'debian-archive-keyring.gpg')
        self.sign_releases()

    def sign_releases(self, codename='trixie'):
        for index, name in enumerate(['debian', 'local']):
            release = self.directory / (name + '.txt')
            release.write_text(('Origin: Debian\nCodename: ' + codename + '\n' if index == 0 else 'Origin: CM3\n') +
                               'SHA256:\n ' + chain.digest(self.index) + ' ' + str(self.index.stat().st_size) + ' Packages\n')
            subprocess.run(self.gpg + ['--yes', '--local-user', self.fingerprints[index], '--output',
                                       str(self.directory / 'releases' / name), '--clearsign', str(release)],
                           check=True, capture_output=True)
            release.unlink()

    def verify(self):
        return chain.verify(self.directory, self.anchor, self.fingerprints[1])

    def test_complete_signature_to_payload_closure_and_identity(self):
        result = self.verify()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['installed'], 1)
        self.assertEqual(len(result['releases']), 2)
        self.assertEqual(result['packages'][0]['sha256'], chain.digest(self.deb))

    def test_unreviewed_top_level_extra_directory_and_symlink_rejected(self):
        extra = self.directory / 'secret.key'
        extra.write_bytes(b'not a key')
        with self.assertRaisesRegex(ValueError, 'contents'):
            self.verify()
        extra.unlink()
        extra.mkdir()
        with self.assertRaisesRegex(ValueError, 'contents'):
            self.verify()
        extra.rmdir()
        extra.symlink_to(self.deb)
        with self.assertRaisesRegex(ValueError, 'contents'):
            self.verify()

    @unittest.skipUnless(shutil.which('apt-get'), 'actual isolated APT required')
    def test_real_apt_exact_all_arch_download_and_index_decode_without_install(self):
        # Same specification shape as capture(); no network, install or host APT state.
        with tempfile.TemporaryDirectory(prefix='cm3-chain-apt-') as temporary:
            apt = Path(temporary)
            repository = apt / 'repository'
            (repository / 'packages').mkdir(parents=True)
            shutil.copyfile(self.payload, repository / 'packages/fixture.deb')
            shutil.copyfile(self.index, repository / 'Packages')
            shutil.copyfile(self.directory / 'releases/local', repository / 'InRelease')
            sources = apt / 'sources.list'
            sources.write_text('deb [signed-by=' + str(self.directory / 'local-archive-key.gpg') +
                               '] file:' + str(repository) + ' ./\n')
            (apt / 'lists/partial').mkdir(parents=True)
            options = ['-o', 'Dir::Etc::sourcelist=' + str(sources), '-o', 'Dir::Etc::sourceparts=-',
                       '-o', 'Dir::State::lists=' + str(apt / 'lists'), '-o', 'Dir::Cache=' + str(apt / 'cache'),
                       '-o', 'APT::Update::Error-Mode=any']
            subprocess.run(['apt-get', *options, 'update'], check=True, capture_output=True)
            download = apt / 'download'
            download.mkdir()
            subprocess.run(['apt-get', *options, 'download', '--', 'cm3-chain-fixture:all=1'],
                           cwd=download, check=True, capture_output=True)
            payloads = list(download.glob('*.deb'))
            self.assertEqual(len(payloads), 1)
            self.assertEqual(chain.digest(payloads[0]), chain.digest(self.deb))
            indexes = [path for path in (apt / 'lists').iterdir() if '_Packages' in path.name]
            self.assertEqual(len(indexes), 1)
            decoded = subprocess.check_output(['/usr/lib/apt/apt-helper', 'cat-file', str(indexes[0])])
            self.assertEqual(decoded, self.index.read_bytes())

    def test_modified_package_index_release_and_anchor_rejected(self):
        for path in [self.payload, self.index, self.directory / 'releases/debian',
                     self.directory / 'debian-archive-keyring.gpg']:
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.subTest(path=path.name), self.assertRaises((ValueError, subprocess.SubprocessError)):
                self.verify()
            path.write_bytes(original)

    def test_missing_extra_duplicate_and_redirected_package_rejected(self):
        original = self.payload.read_bytes()
        self.payload.unlink()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.verify()
        self.payload.write_bytes(original)
        extra = self.payload.with_name('duplicate.deb')
        extra.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.verify()
        extra.unlink()
        self.payload.unlink()
        self.payload.symlink_to(self.deb)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            self.verify()

    def test_wrong_suite_and_unexpected_local_signer_rejected(self):
        self.sign_releases(codename='bookworm')
        with self.assertRaisesRegex(ValueError, 'repository'):
            self.verify()
        self.sign_releases()
        with self.assertRaisesRegex(ValueError, 'signer'):
            chain.verify(self.directory, self.anchor, 'A' * 40)

    def test_absent_signature_and_unmatched_installed_identity_rejected(self):
        (self.directory / 'releases/local').unlink()
        with self.assertRaisesRegex(ValueError, 'both'):
            self.verify()
        self.sign_releases()
        (self.directory / 'installed.tsv').write_text('cm3-chain-fixture\t2\tall\tinstalled\n')
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            self.verify()
