"""Offline enrollment boundaries; no host accounts, services, or firewall changes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import test_board_support as fixtures


def identities(root):
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / 'etc/ssh').glob('ssh_host_*')}


class FirstbootBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EnrollmentTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root

    def test_interrupted_host_key_generation_preserves_identity_on_retry(self):
        def interrupt(*args):
            self.fixture.command(*args)
            if args[0].endswith('/ssh-keygen'):
                raise OSError('interrupted after host identity generation')

        with self.assertRaisesRegex(OSError, 'host identity'):
            fixtures.enrollment.enroll(self.root, interrupt)
        self.assertFalse((self.root / fixtures.enrollment.READY).exists())
        self.assertEqual(json.loads((self.root / fixtures.enrollment.STATE).read_text())['status'],
                         'pending')
        before = identities(self.root)
        self.assertEqual(len(before), 6)
        fixtures.enrollment.enroll(self.root, self.fixture.command)
        fixtures.enrollment.check(self.root)
        self.assertEqual(identities(self.root), before)

    def test_ssh_gate_rejects_account_writable_or_symlinked_key_directory(self):
        fixtures.enrollment.enroll(self.root, self.fixture.command)
        keydir = self.root / 'etc/cm3-cli/authorized_keys'
        keydir.chmod(0o777)
        with self.assertRaises(ValueError):
            fixtures.enrollment.check(self.root)
        keydir.chmod(0o755)
        fixtures.enrollment.check(self.root)
        moved = keydir.with_name('saved-keys')
        keydir.rename(moved)
        keydir.symlink_to(moved.name, target_is_directory=True)
        with self.assertRaises(ValueError):
            fixtures.enrollment.check(self.root)
        keydir.unlink()
        moved.rename(keydir)
        fixtures.enrollment.check(self.root)

    def test_writable_state_ancestor_is_rejected_before_writes_or_commands(self):
        (self.root / 'var/lib').chmod(0o777)
        with self.assertRaises(ValueError):
            fixtures.enrollment.enroll(self.root, self.fixture.command)
        self.assertEqual(self.fixture.calls, [])
        self.assertFalse((self.root / fixtures.enrollment.STATE).exists())

    def test_symlinked_runtime_ancestor_is_rejected_before_unlink(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            marker = outside / 'enrolled.json'
            marker.write_text('must remain untouched')
            (self.root / 'run/cm3-cli').rmdir()
            (self.root / 'run/cm3-cli').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                fixtures.enrollment.enroll(self.root, self.fixture.command)
            self.assertEqual(marker.read_text(), 'must remain untouched')
            self.assertEqual(self.fixture.calls, [])
            self.assertFalse((self.root / fixtures.enrollment.STATE).exists())

    def test_atomic_writer_rejects_symlinked_ancestor_before_mkdir(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            (self.root / 'var/lib/cm3-cli').rmdir()
            (self.root / 'var/lib').rmdir()
            (self.root / 'var/lib').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                fixtures.enrollment.atomic(self.root, fixtures.enrollment.STATE, b'{}')
            self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_state_ancestor_is_rejected_before_writes_or_commands(self):
        # A missing state file must not bypass the ancestor trust checks on reads.
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            (self.root / 'var/lib/cm3-cli').rmdir()
            (self.root / 'var/lib').rmdir()
            (self.root / 'var/lib').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                fixtures.enrollment.enroll(self.root, self.fixture.command)
            self.assertEqual(list(outside.iterdir()), [],
                             'enrollment wrote through an untrusted state ancestor')
            self.assertEqual(self.fixture.calls, [])
            self.assertFalse((self.root / fixtures.enrollment.READY).exists())


if __name__ == '__main__':
    unittest.main()
