"""Regression for audit F02: no live storage writes without volume safety."""
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/cm3-toolkit'))
import bench


class LiveStorageRefusalTests(unittest.TestCase):
    def test_arbitrary_approved_directory_cannot_create_even_an_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'live storage.*disabled'):
                with bench.storage_file(directory, 1024, 'must-not-exist'):
                    pass
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_storage_executor_refuses_before_runner_or_file_creation(self):
        args = bench.parser().parse_args(['storage', '--execute', '--allow-load',
                                         '--allow-write', '--duration-s', '1'])
        with tempfile.TemporaryDirectory() as directory:
            args.approved_dir = directory
            with patch.object(bench, 'run_process', return_value=('{}', '')) as runner:
                with self.assertRaisesRegex(ValueError, 'live storage.*disabled'):
                    bench.execute_live(args, {}, runner=runner)
                runner.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_live_build_reports_storage_disabled_before_dispatch(self):
        conditions = Path(__file__).parent / 'fixtures/bench/conditions.json'
        args = bench.parser().parse_args(['storage', '--execute', '--allow-load',
            '--allow-write', '--approved-dir', '/not-a-volume-approval',
            '--conditions', str(conditions)])
        with patch.object(bench, 'execute_live') as live:
            with self.assertRaisesRegex(ValueError, 'live storage.*disabled'):
                bench.build(args)
            live.assert_not_called()

    def test_cli_refuses_before_output_reservation_with_clear_safe_reason(self):
        conditions = Path(__file__).parent / 'fixtures/bench/conditions.json'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'no-result.json'
            run = subprocess.run([sys.executable, str(bench.__file__), 'storage',
                '--execute', '--allow-load', '--allow-write', '--approved-dir', directory,
                '--conditions', str(conditions), '--output', str(output)],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 2)
            self.assertIn('live storage execution disabled', run.stderr)
            self.assertFalse(output.exists())
            self.assertEqual(run.stdout, '')

    def test_refusal_preserves_existing_data_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / 'existing'
            existing.write_bytes(b'untouched fixture')
            link = Path(directory) / 'alias'
            link.symlink_to(directory, target_is_directory=True)
            for path, name in ((directory, 'existing'), (str(link), 'new')):
                with self.assertRaisesRegex(ValueError, 'live storage.*disabled'):
                    bench.storage_file(path, 1024, name)
            self.assertEqual(existing.read_bytes(), b'untouched fixture')
            self.assertEqual(set(Path(directory).iterdir()), {existing, link})

    def test_refusal_does_not_inspect_or_open_the_claimed_volume(self):
        for directory in ('/', '/boot', '/home/user-data', '/mnt/alias', '/dev/sda'):
            with self.subTest(directory=directory), patch.object(os, 'open') as opened:
                with self.assertRaisesRegex(ValueError, 'live storage.*disabled'):
                    bench.storage_file(directory, 1024)
                opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
