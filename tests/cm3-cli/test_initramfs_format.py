import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('package_preflight', ROOT / 'scripts/cm3-package-preflight.py')
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def newc(name, data=b''):
    name = name.encode() + b'\0'
    fields = [0, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
    record = b'070701' + ''.join(f'{value:08x}' for value in fields).encode() + name
    record += b'\0' * (-len(record) % 4)
    record += data
    return record + b'\0' * (-len(record) % 4)


class InitramfsFormatTests(unittest.TestCase):
    def verify(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'initrd'
            path.write_bytes(data)
            return preflight.verify_gzip_initramfs(path)

    def setUp(self):
        self.main = gzip.compress(newc('init', b'fixture') + newc('TRAILER!!!'), mtime=0)
        self.prefix = newc('usr/lib/modules/fixture.ko.xz', b'already compressed fixture') + newc('TRAILER!!!')
        self.prefix += b'\0' * (-len(self.prefix) % 512)

    def test_plain_gzip_main_archive(self):
        self.assertEqual(self.verify(self.main), {
            'compression': 'gzip', 'main_offset': 0, 'early_archives': 0, 'gzip_integrity': 'PASS'})

    def test_debian_compressed_modules_prefix_then_gzip(self):
        result = self.verify(self.prefix + self.main)
        self.assertEqual(result['main_offset'], len(self.prefix))
        self.assertEqual(result['early_archives'], 1)
        self.assertEqual(result['gzip_integrity'], 'PASS')

    def test_multiple_uncompressed_prefixes(self):
        result = self.verify(self.prefix * 2 + self.main)
        self.assertEqual(result['early_archives'], 2)
        self.assertEqual(result['main_offset'], len(self.prefix) * 2)

    def test_rejects_non_gzip_missing_and_malformed_archives(self):
        damaged = bytearray(self.main)
        damaged[-8] ^= 1
        invalid_header = bytearray(self.prefix)
        invalid_header[94:102] = b'ffffffff'
        invalid_payload = bytearray(self.prefix)
        invalid_payload[54:62] = b'ffffffff'
        invalid_name = bytearray(self.prefix)
        invalid_name[110] = 0
        for data in [b'', self.prefix, b'\0' * 512, self.main[:-1], bytes(damaged),
                     b'\x28\xb5\x2f\xfdnot gzip', self.prefix + b'not gzip',
                     b'random prefix' + self.main, gzip.compress(b'not cpio'),
                     bytes(invalid_header) + self.main, bytes(invalid_payload) + self.main,
                     bytes(invalid_name) + self.main, self.prefix[:110],
                     self.main + b'garbage']:
            with self.subTest(data=data[:12]):
                with self.assertRaises((ValueError, OSError, EOFError)):
                    self.verify(data)


if __name__ == '__main__':
    unittest.main()
