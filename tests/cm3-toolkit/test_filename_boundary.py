"""Explicit filename policy at untrusted CLI/input filesystem sinks."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/cm3-toolkit'))
import bench
from common import emit_result, make_result, safe_filename


class FilenameBoundaryTests(unittest.TestCase):
    def test_read_refuses_hidden_or_encoded_filenames(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('.private.json', 'escaped%2finput.json', 'line\nbreak.json'):
                path = Path(directory) / name
                path.write_text('{"fixture":true}')
                with self.subTest(name=name), self.assertRaises(ValueError):
                    bench.read_json(path)

    def test_cli_rejects_hidden_output_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / '.unexpected.json'
            run = subprocess.run([sys.executable, str(bench.__file__), 'cpu',
                                  '--output', str(output)],
                                 capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(output.exists())

    def test_shared_output_rejects_hidden_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / '.hidden.json'
            with self.assertRaises(ValueError):
                emit_result(make_result('plan', synthetic=False), output)
            self.assertFalse(output.exists())

    def test_safe_filename_refuses_separators_and_special_names(self):
        for name in ('', '.', '..', '../escape', '/absolute', 'a/b', 'a\\b',
                     '.hidden', 'a%2fb', 'a\nname', 'a'*129):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_filename(name)
        self.assertEqual(safe_filename('result-1.json'), 'result-1.json')

    def test_normal_json_and_no_clobber_output_still_work(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source-1.json'
            source.write_text('{"fixture":true}')
            self.assertEqual(bench.read_json(source), {'fixture': True})
            output = Path(directory) / 'plan-1.json'
            command = [sys.executable, str(bench.__file__), 'cpu', '--output', str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=5).returncode, 0)
            before = output.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=5).returncode, 2)
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
