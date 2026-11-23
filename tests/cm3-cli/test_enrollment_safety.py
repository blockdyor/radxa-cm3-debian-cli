"""Readiness regressions; account commands doubled, keys generated in fixtures."""
import errno
import importlib.util
import os
from pathlib import Path
import stat
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_board_support as fixtures

if os.environ.get('CM3_TEST_ENROLL'):
    spec = importlib.util.spec_from_file_location('old_enroll', os.environ['CM3_TEST_ENROLL'])
    fixtures.enrollment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures.enrollment)
E = fixtures.enrollment


class EnrollmentSafetyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EnrollmentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def enroll(self):
        E.enroll(self.root, self.fixture.command)

    def test_invalid_machine_identity_precedes_account_mutation(self):
        for value in ('', '0' * 32, 'not-an-id', 'f' * 31, '\uff46' * 32):
            with self.subTest(value=value):
                self.fixture.put('etc/machine-id', value)
                with self.assertRaises((ValueError, UnicodeError)):
                    self.enroll()
                self.assertEqual(self.fixture.calls, [])
                self.assertFalse((self.root / E.READY).exists())

    def test_invalid_nonempty_private_key_fails_check_and_same_owner_retry(self):
        self.enroll()
        name = 'etc/ssh/ssh_host_ed25519_key'
        original = (self.root / name).read_bytes()
        self.fixture.put(name, 'not-a-private-key', 0o600)
        with self.assertRaises((ValueError, subprocess.SubprocessError)):
            E.check(self.root)
        self.fixture.calls.clear()
        with self.assertRaises((ValueError, subprocess.SubprocessError)):
            self.enroll()
        self.assertFalse((self.root / E.READY).exists())
        self.assertEqual(self.fixture.calls, [])
        self.fixture.put(name, original, 0o600)
        self.enroll()
        E.check(self.root)
        self.assertEqual((self.root / name).read_bytes(), original)

    def test_wrong_kind_public_companion_and_encrypted_key_fail_closed(self):
        self.enroll()
        private = self.root / 'etc/ssh/ssh_host_ed25519_key'
        public = private.with_suffix('.pub')
        original = private.read_bytes()
        companion = public.read_bytes()
        private.write_bytes((self.root / 'etc/ssh/ssh_host_rsa_key').read_bytes())
        with self.assertRaises((ValueError, subprocess.SubprocessError)):
            E.check(self.root)
        private.write_bytes(original)
        public.write_bytes((self.root / 'etc/ssh/ssh_host_rsa_key.pub').read_bytes())
        with self.assertRaises((ValueError, subprocess.SubprocessError)):
            E.check(self.root)
        public.write_bytes(companion)
        subprocess.run(['ssh-keygen', '-p', '-P', '', '-N', 'fixture-passphrase', '-f', str(private)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        with self.assertRaises((ValueError, subprocess.SubprocessError)):
            E.check(self.root)
        private.write_bytes(original)
        E.check(self.root)

    def test_final_ready_directory_fsync_enospc_cleans_published_marker_and_retry(self):
        real_fsync = os.fsync
        failed = False
        def fail(fd):
            nonlocal failed
            if not failed and stat.S_ISDIR(os.fstat(fd).st_mode) and (self.root / E.READY).exists():
                failed = True
                raise OSError(errno.ENOSPC, 'after READY replace, before directory fsync')
            return real_fsync(fd)
        with patch.object(E.os, 'fsync', side_effect=fail):
            with self.assertRaises(OSError):
                self.enroll()
        self.assertTrue(failed, 'must exercise actual post-replace directory-fsync edge')
        self.assertFalse((self.root / E.READY).exists())
        before = {p.name: p.read_bytes() for p in (self.root / 'etc/ssh').glob('ssh_host_*')}
        self.enroll()
        E.check(self.root)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / 'etc/ssh').glob('ssh_host_*')})
        self.assertEqual(sum(c[0].endswith('/adduser') for c in self.fixture.calls), 1)

    def test_each_atomic_entry_enospc_keeps_gate_closed_and_same_owner_retry(self):
        real_atomic = E.atomic
        for point in range(1, 6):
            with self.subTest(point=point):
                count = 0
                def fail(root, relative, data, mode=0o600):
                    nonlocal count
                    count += 1
                    if count == point:
                        raise OSError(errno.ENOSPC, 'fixture full')
                    return real_atomic(root, relative, data, mode)
                with patch.object(E, 'atomic', side_effect=fail):
                    with self.assertRaises(OSError):
                        self.enroll()
                self.assertFalse((self.root / E.READY).exists())
                self.enroll()
                E.check(self.root)

    @unittest.skipUnless(shutil.which('systemd-machine-id-setup'), 'actual systemd identity initializer required')
    def test_fresh_systemd_machine_ids_and_keys_differ_then_persist(self):
        # This is initialization on separate fixture roots, not global clone detection.
        first = self.root / 'etc/machine-id'
        first.write_bytes(b'')
        subprocess.run(['systemd-machine-id-setup', '--root=' + str(self.root)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.enroll()
        identity = first.read_bytes()
        key = (self.root / 'etc/ssh/ssh_host_ed25519_key.pub').read_bytes()
        other = fixtures.EnrollmentTests()
        other.setUp()
        self.addCleanup(other.doCleanups)
        (other.root / 'etc/machine-id').write_bytes(b'')
        subprocess.run(['systemd-machine-id-setup', '--root=' + str(other.root)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        E.enroll(other.root, other.command)
        self.assertNotEqual(identity, (other.root / 'etc/machine-id').read_bytes())
        self.assertNotEqual(key, (other.root / 'etc/ssh/ssh_host_ed25519_key.pub').read_bytes())
        self.enroll()
        self.assertEqual(identity, first.read_bytes())
        self.assertEqual(key, (self.root / 'etc/ssh/ssh_host_ed25519_key.pub').read_bytes())
