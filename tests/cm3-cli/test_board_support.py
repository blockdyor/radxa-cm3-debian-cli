import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'packages/cm3-cli-board-support'
OWNER_SPEC = importlib.util.spec_from_file_location('owner_config', ROOT / 'scripts/cm3-owner-config.py')
owner = importlib.util.module_from_spec(OWNER_SPEC)
OWNER_SPEC.loader.exec_module(owner)
sys.modules['owner_config'] = owner
SPEC = importlib.util.spec_from_file_location('cm3_enroll', PACKAGE / 'root/usr/lib/cm3-cli/enroll.py')
enrollment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enrollment)
SPEC = importlib.util.spec_from_file_location('cm3_board_build', PACKAGE / 'build.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
KEY = 'ssh-ed25519 ' + base64.b64encode(struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + PUBLIC).decode()


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ['etc/cm3-cli', 'etc/sudoers.d', 'proc/device-tree', 'sys/kernel/security',
                     'run/cm3-cli', 'var/lib/cm3-cli', 'etc/ssh']:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.put('proc/device-tree/compatible', b'radxa,cm3-rpi-cm4-io\0rockchip,rk3566\0')
        self.put('etc/passwd', 'root:x:0:0:root:/root:/bin/bash\n')
        self.put('etc/shadow', 'root:!:1:0:99999:7:::\n', 0o600)
        self.put('etc/group', 'root:x:0:\n')
        self.put('etc/machine-id', '1234567890abcdef1234567890abcdef\n')
        self.put('sys/kernel/security/lsm', 'capability,landlock,lockdown,yama,integrity,apparmor,bpf\n')
        self.config = {'version': 1, 'username': 'alice', 'authorized_key': KEY}
        self.owner()
        self.calls = []

    def put(self, relative, data, mode=0o644):
        path = self.root / relative
        if path.exists():
            path.chmod(0o600)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        path.chmod(mode)

    def owner(self):
        self.put('etc/cm3-cli/owner.json', json.dumps(self.config), 0o600)

    def command(self, *args):
        # Account commands are simulated in isolated text fixtures, NEVER run on host.
        # Real SSH identity generation below uses OpenSSH's fixture-root prefix.
        self.calls.append(args)
        if args[0].endswith('/adduser'):
            with (self.root / 'etc/passwd').open('a') as stream:
                stream.write('alice:x:1000:1000::/home/alice:/bin/bash\n')
            with (self.root / 'etc/shadow').open('a') as stream:
                stream.write('alice:!:1:0:99999:7:::\n')
        elif args[0].endswith('/groupadd'):
            self.put('etc/group', 'root:x:0:\ncm3-cli-owner:x:999:\n')
        elif args[0].endswith('/usermod'):
            self.put('etc/group', 'root:x:0:\ncm3-cli-owner:x:999:alice\n')
        elif args[0].endswith('/ssh-keygen'):
            subprocess.run(['ssh-keygen', '-A', '-f', str(self.root)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def test_missing_invalid_and_wrong_board_have_no_account_or_identity_side_effect(self):
        for path, data in [('etc/cm3-cli/owner.json', b'{}'),
                           ('proc/device-tree/compatible', b'rockchip,rk3568\0')]:
            with self.subTest(path=path):
                self.put(path, data, 0o600)
                before = (self.root / 'etc/passwd').read_bytes()
                with self.assertRaises(ValueError):
                    enrollment.enroll(self.root, self.command)
                self.assertEqual(self.calls, [])
                self.assertEqual((self.root / 'etc/passwd').read_bytes(), before)
                self.assertFalse((self.root / enrollment.STATE).exists())
                self.assertFalse((self.root / enrollment.READY).exists())
                self.owner()

    def test_enrollment_is_idempotent_and_does_not_regenerate_keys(self):
        enrollment.enroll(self.root, self.command)
        enrollment.check(self.root)
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (self.root / 'etc/ssh').glob('ssh_host_*')}
        state = (self.root / enrollment.STATE).read_bytes()
        enrollment.enroll(self.root, self.command)
        enrollment.check(self.root)
        self.assertEqual(sum(call[0].endswith('/adduser') for call in self.calls), 1)
        self.assertEqual((self.root / enrollment.STATE).read_bytes(), state)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (self.root / 'etc/ssh').glob('ssh_host_*')})
        self.assertEqual((self.root / 'etc/cm3-cli/authorized_keys/alice').stat().st_mode & 0o777, 0o644)

    def test_interrupted_account_creation_resumes_without_duplicating_account(self):
        def interrupt(*args):
            self.command(*args)
            if args[0].endswith('/adduser'):
                raise OSError('simulated interruption after account creation')
        with self.assertRaises(OSError):
            enrollment.enroll(self.root, interrupt)
        self.assertFalse((self.root / enrollment.READY).exists())
        self.assertEqual(json.loads((self.root / enrollment.STATE).read_text())['status'], 'pending')
        enrollment.enroll(self.root, self.command)
        enrollment.check(self.root)
        self.assertEqual(sum(call[0].endswith('/adduser') for call in self.calls), 1)

    def test_unapproved_existing_account_and_changed_document_rejected(self):
        self.command('/usr/sbin/adduser', 'alice')
        with self.assertRaisesRegex(ValueError, 'existing account'):
            enrollment.enroll(self.root, self.command)
        self.assertFalse((self.root / enrollment.STATE).exists())

    def test_partial_account_database_requires_explicit_offline_recovery(self):
        def interrupt(*args):
            self.command(*args)
            if args[0].endswith('/adduser'):
                self.put('etc/shadow', 'root:!:1:0:99999:7:::\n', 0o600)
                raise OSError('simulated partial system account transaction')
        with self.assertRaises(OSError):
            enrollment.enroll(self.root, interrupt)
        self.calls.clear()
        with self.assertRaisesRegex(ValueError, 'offline account recovery'):
            enrollment.enroll(self.root, self.command)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / enrollment.READY).exists())

    def test_changed_key_and_inactive_lsm_remove_readiness(self):
        enrollment.enroll(self.root, self.command)
        self.put('sys/kernel/security/lsm', 'capability\n')
        with self.assertRaisesRegex(ValueError, 'AppArmor'):
            enrollment.enroll(self.root, self.command)
        self.assertFalse((self.root / enrollment.READY).exists())
        self.config['username'] = 'bob'
        self.owner()
        with self.assertRaisesRegex(ValueError, 'differs'):
            enrollment.enroll(self.root, self.command)
        self.assertFalse((self.root / enrollment.READY).exists())

    def test_private_input_permissions_symlinks_and_hardlinks_rejected(self):
        path = self.root / 'etc/cm3-cli/owner.json'
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            enrollment.document(self.root)
        path.chmod(0o600)
        copy = path.with_name('copy.json')
        path.rename(copy)
        path.symlink_to(copy.name)
        with self.assertRaises(OSError):
            enrollment.document(self.root)
        path.unlink()
        os.link(copy, path)
        with self.assertRaises(ValueError):
            enrollment.document(self.root)

    def test_tampered_state_key_sudo_group_and_password_fail_gate(self):
        enrollment.enroll(self.root, self.command)
        for name, data, mode in [('etc/cm3-cli/authorized_keys/alice', 'changed\n', 0o644),
                                 ('etc/sudoers.d/cm3-cli-owner', 'root ALL=ALL\n', 0o440),
                                 ('etc/group', 'cm3-cli-owner:x:999:alice,bob\n', 0o644),
                                 ('etc/shadow', 'root::1:0:99999:7:::\nalice:!:1:0:99999:7:::\n', 0o600),
                                 (enrollment.READY, '{}', 0o600)]:
            path = self.root / name
            previous = path.read_bytes()
            self.put(name, data, mode)
            with self.subTest(name=name), self.assertRaises(ValueError):
                enrollment.check(self.root)
            self.put(name, previous, mode)
        enrollment.check(self.root)

    def test_two_fresh_fixture_identities_have_distinct_ssh_keys(self):
        enrollment.enroll(self.root, self.command)
        before = (self.root / 'etc/ssh/ssh_host_ed25519_key.pub').read_bytes()
        other = self.root / 'second'
        (other / 'etc/ssh').mkdir(parents=True)
        subprocess.run(['ssh-keygen', '-A', '-f', str(other)], check=True, stdout=subprocess.DEVNULL)
        self.assertNotEqual(before, (other / 'etc/ssh/ssh_host_ed25519_key.pub').read_bytes())
        # This is OpenSSH identity generation, not systemd machine-id or hardware boot validation.


class BoardPackageTests(unittest.TestCase):
    def test_real_deb_build_extract_and_repeatability(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            first, second = directory / 'first.deb', directory / 'second.deb'
            for output in [first, second]:
                builder.build(output, 'a' * 40, 1700000000)  # explicit synthetic provenance fixture
            self.assertEqual(first.read_bytes(), second.read_bytes())
            identity = subprocess.check_output(['dpkg-deb', '-f', str(first), 'Package', 'Version', 'Architecture'], text=True)
            self.assertIn('cm3-cli-board-support', identity)
            self.assertIn('0.1.0', identity)
            self.assertIn('all', identity)
            root = directory / 'extracted'
            subprocess.run(['dpkg-deb', '-R', str(first), str(root)], check=True)
            self.assertEqual((root / 'usr/lib/cm3-cli/owner_config.py').read_bytes(),
                             (ROOT / 'scripts/cm3-owner-config.py').read_bytes())
            for name in ['ssh.socket', 'systemd-networkd.service', 'systemd-networkd.socket']:
                self.assertEqual(os.readlink(root / 'etc/systemd/system' / name), '/dev/null')
            self.assertEqual(os.readlink(root / 'etc/kernel/install.d/99-update-overlay.install'), '/dev/null')
            self.assertEqual((root / 'usr/share/doc/cm3-cli-board-support/copyright').read_bytes(), (ROOT / 'LICENSE').read_bytes())
            for script in [root / 'DEBIAN' / name for name in ['postinst', 'prerm', 'postrm']] + [root / 'usr/lib/cm3-cli/boot-update']:
                subprocess.run(['sh', '-n', str(script)], check=True)
                self.assertTrue(script.stat().st_mode & 0o111)
            for name in ['etc/cm3-cli/owner.json', 'etc/shadow', 'etc/machine-id']:
                self.assertFalse((root / name).exists())
            self.assertEqual(list((root / 'etc/ssh').glob('ssh_host_*')), [])
            self.assertNotIn('Provides:', (root / 'DEBIAN/control').read_text())
            self.assertNotIn('NetworkManager', (root / 'DEBIAN/conffiles').read_text())
            self.assertTrue((root / 'usr/lib/systemd/system/NetworkManager.service.d/cm3-cli.conf').is_file())
            self.assertEqual(list(root.rglob('__pycache__')), [])
            allowed = set(builder.PAYLOAD) | {'usr/lib/cm3-cli/owner_config.py',
                'usr/share/doc/cm3-cli-board-support/copyright',
                'usr/share/doc/cm3-cli-board-support/README',
                'usr/share/doc/cm3-cli-board-support/source.json'}
            actual = {str(p.relative_to(root)) for p in root.rglob('*')
                      if p.is_file() and not p.is_symlink() and 'DEBIAN' not in p.parts}
            self.assertEqual(actual, allowed)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                builder.build(first, 'a' * 40, 1700000000)

    def test_cli_rejects_false_revision_before_writing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-built.deb'
            result = subprocess.run(['python3', str(PACKAGE / 'build.py'), '--output', str(output),
                                     '--revision', 'a' * 40, '--epoch', '1700000000'],
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('match the exact checked-out commit', result.stderr)
            self.assertFalse(output.exists())

    def test_fail_closed_service_and_boot_policy(self):
        root = PACKAGE / 'root'
        ssh = (root / 'etc/ssh/sshd_config.d/00-cm3-cli.conf').read_text()
        for item in ['PermitRootLogin no', 'PasswordAuthentication no', 'KbdInteractiveAuthentication no',
                     'AuthenticationMethods publickey', 'AllowGroups cm3-cli-owner']:
            self.assertIn(item, ssh)
        gate = (root / 'etc/systemd/system/ssh.service.d/cm3-cli.conf').read_text()
        self.assertIn('ExecStartPre=/usr/bin/python3 /usr/lib/cm3-cli/enroll.py --check', gate)
        boot = (root / 'etc/u-boot-menu/conf.d/99-cm3-cli.conf').read_text()
        for value in ['rk3566-radxa-cm3-rpi-cm4-io.dtb', 'console=ttyFIQ0,1500000n8', 'lsm=', 'apparmor=1']:
            self.assertIn(value, boot)
        for value in ['quiet', 'splash', 'kasan=off', 'governor']:
            self.assertNotIn(value, boot)
        firewall = (root / 'usr/share/cm3-cli/firewall.nft').read_text()
        self.assertNotIn('flush ruleset', firewall)
        self.assertEqual(firewall.count('policy drop'), 2)
        self.assertIn('ipv6-icmp accept', firewall)
        for path in root.rglob('*'):
            if path.is_file():
                text = path.read_text()
                for prohibited in ['resize2fs', 'mkfs', '/dev/nvme', 'setup.sh', 'eval ', 'shell=True']:
                    self.assertNotIn(prohibited, text)


if __name__ == '__main__':
    unittest.main()
