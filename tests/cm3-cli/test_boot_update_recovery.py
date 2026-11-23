"""Isolated boot-update contract tests, not BSP upgrade/recovery validation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / 'packages/cm3-cli-board-support/root/usr/lib/cm3-cli/boot-update'


class BootUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fstab = self.root / 'fstab'
        self.menu = self.root / 'extlinux.conf'
        self.menu.write_text('existing menu\n')
        self.updater = self.root / 'u-boot-update'
        # Only the external updater is doubled: no host /boot or /etc access.
        self.updater.write_text('#!/bin/sh\nexit "${UPDATE_STATUS:-0}"\n')
        self.updater.chmod(0o755)
        self.wrapper = self.root / 'boot-update'
        self.wrapper.write_text(WRAPPER.read_text()
                                .replace('/etc/fstab', str(self.fstab))
                                .replace('/usr/sbin/u-boot-update', str(self.updater)))

    def run_wrapper(self, status=23):
        return subprocess.run(['sh', str(self.wrapper)], capture_output=True, text=True,
                              env={**os.environ, 'UPDATE_STATUS': str(status)})

    def test_indented_root_entry_does_not_silently_skip_update_failure(self):
        # Removing optional leading-whitespace support must fail this regression.
        for prefix in ['', '  ', '\t']:
            with self.subTest(prefix=repr(prefix)):
                self.fstab.write_text(prefix + 'UUID=os / ext4 defaults 0 1\n')
                self.assertEqual(self.run_wrapper().returncode, 23)
                self.assertEqual(self.menu.read_text(), 'existing menu\n')

    def test_initial_rootfs_and_nonroot_entries_defer_without_running_updater(self):
        # The updater fails if called: success proves that deferral bypassed it.
        for contents in [None, '', '# UUID=os / ext4 defaults 0 1\n',
                         '  # UUID=os / ext4 defaults 0 1\n',
                         'UUID=data /data ext4 defaults 0 2\n']:
            with self.subTest(contents=contents):
                if contents is not None:
                    self.fstab.write_text(contents)
                self.assertEqual(self.run_wrapper().returncode, 0)
                self.assertEqual(self.menu.read_text(), 'existing menu\n')

    def test_updater_success_is_propagated(self):
        self.fstab.write_text('  UUID=os / ext4 defaults 0 1\n')
        # Make invocation observable without allowing any real boot-file writes.
        self.updater.write_text('#!/bin/sh\nprintf "updated\\n" > "' + str(self.menu) + '"\n')
        self.assertEqual(self.run_wrapper(status=0).returncode, 0)
        self.assertEqual(self.menu.read_text(), 'updated\n')


if __name__ == '__main__':
    unittest.main()
