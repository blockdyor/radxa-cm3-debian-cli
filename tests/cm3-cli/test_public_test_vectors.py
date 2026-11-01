"""Synthetic parser fixtures; real retained/public-source readback is separate evidence."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('public_vectors', ROOT / 'scripts/cm3-public-test-vectors.py')
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture():
    blocks = [b'-----BEGIN PRIVATE KEY-----\nQUFB' + bytes([65 + number]) + b'===\n-----END PRIVATE KEY-----'
              for number in range(8)]
    library = b'fixture-not-an-ELF\0' + b'\0'.join(blocks)
    text = b'\n'.join(('"' + block.decode().replace('\n', '\\n') + '"').encode() for block in blocks)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:xz') as archive:
        member = tarfile.TarInfo(module.MEMBER)
        member.size = len(text)
        archive.addfile(member, io.BytesIO(text))
    return library, output.getvalue(), text


class PublicVectorTests(unittest.TestCase):
    def setUp(self):
        self.library, self.source, text = fixture()
        self.bound = patch.multiple(module, LIBRARY_SHA256=hashlib.sha256(self.library).hexdigest(),
                                    HEADER_COUNT=8,
                                    SOURCE_SHA256=hashlib.sha256(self.source).hexdigest(),
                                    MEMBER_SHA256=hashlib.sha256(text).hexdigest())
        self.bound.start()
        self.addCleanup(self.bound.stop)

    def test_only_exact_bound_path_library_source_and_eight_blocks_are_classified(self):
        report = module.public_vectors(module.LIBRARY, self.library, self.source)
        self.assertEqual(report['blocks'], 8)
        for path, data, source in [(module.LIBRARY, self.library.replace(b'QUFBA', b'QUFBZ'), self.source),
                                   (module.LIBRARY, self.library + b'changed', self.source),
                                   ('tmp/copied-key', self.library, self.source),
                                   (module.LIBRARY, self.library, self.source + b'changed')]:
            with self.subTest(path=path, size=len(data)), self.assertRaises(ValueError):
                module.public_vectors(path, data, source)

    def test_ninth_block_and_incomplete_header_rejected_even_with_fixture_hash_updated(self):
        for data in (self.library + b'\0' + self.library.split(b'\0')[1],
                     self.library + b'-----BEGIN PRIVATE KEY-----'):
            with patch.object(module, 'LIBRARY_SHA256', hashlib.sha256(data).hexdigest()):
                with self.assertRaises(ValueError):
                    module.public_vectors(module.LIBRARY, data, self.source)

    def test_scan_does_not_waive_a_copied_key_or_other_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root / module.LIBRARY
            library.parent.mkdir(parents=True)
            library.write_bytes(self.library)
            self.assertEqual(module.scan(root, self.source)['public_vectors']['blocks'], 8)
            (root / 'extra').write_bytes(self.library)
            with self.assertRaises(ValueError):
                module.scan(root, self.source)
