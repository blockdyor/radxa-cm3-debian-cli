"""Explicit synthetic fixtures test packaging only, never OS validation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import package_oci as p


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        for name in p.FILES:
            (self.bundle / name).write_bytes(('SYNTHETIC PACKAGING TEST ONLY: ' + name).encode())
        self.sums()

    def sums(self):
        entries = {name: p.digest(self.bundle / name) for name in p.FILES if name != 'SHA256SUMS'}

        (self.bundle / 'SHA256SUMS').write_text(''.join(f'{sha}  {name}\n' for name, sha in sorted(entries.items())))

    def test_reproducible_and_extracted_bytes(self):
        a = self.root / 'a'
        first = p.build(self.bundle, a, pinned=False)
        for file in self.bundle.iterdir():
            os.utime(file, (123456, 123456))
            file.chmod(0o600)
        b = self.root / 'b'
        self.assertEqual(first, p.build(self.bundle, b, pinned=False))
        files_a = {str(x.relative_to(a)): p.digest(x) for x in a.rglob('*') if x.is_file()}
        files_b = {str(x.relative_to(b)): p.digest(x) for x in b.rglob('*') if x.is_file()}
        self.assertEqual(files_a, files_b)
        self.assertEqual(first, p.verify(a, self.bundle, pinned=False))

    def test_actual_pins_reject_synthetic_payload(self):
        with self.assertRaisesRegex(ValueError, 'wrong retained image'):
            p.build(self.bundle, self.root / 'a')
        self.assertFalse((self.root / 'a').exists())

    def test_extra_input_rejected(self):
        (self.bundle / 'private-evidence.zip').write_text('SYNTHETIC')
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            p.bundle_hashes(self.bundle, False)

    def test_obsolete_raw_checksum_rejected(self):
        path = self.bundle / 'SHA256SUMS'
        path.write_text(path.read_text() + '0' * 64 + '  ' + p.RAW + '\n')
        with self.assertRaisesRegex(ValueError, 'checksum inventory'):
            p.bundle_hashes(self.bundle, False)

    def test_missing_input_rejected(self):
        (self.bundle / 'source-notices.tar.gz').unlink()
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            p.bundle_hashes(self.bundle, False)

    def test_symlink_rejected(self):
        target = self.bundle / 'package-manifest.txt'
        target.unlink()
        target.symlink_to(self.bundle / 'build-manifest.json')
        with self.assertRaisesRegex(ValueError, 'invalid input'):
            p.bundle_hashes(self.bundle, False)

    def test_checksum_tamper_rejected(self):
        (self.bundle / p.IMAGE).write_text('SYNTHETIC TAMPER')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            p.bundle_hashes(self.bundle, False)

    def test_duplicate_checksum_rejected(self):
        path = self.bundle / 'SHA256SUMS'
        path.write_text(path.read_text() + path.read_text().splitlines()[0] + '\n')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            p.bundle_hashes(self.bundle, False)

    def test_traversal_checksum_rejected(self):
        path = self.bundle / 'SHA256SUMS'
        path.write_text('0' * 64 + '  ../secret\n')
        with self.assertRaisesRegex(ValueError, 'invalid checksum'):
            p.bundle_hashes(self.bundle, False)

    def test_blob_corruption_rejected(self):
        layout = self.root / 'a'
        p.build(self.bundle, layout, False)
        index = json.loads((layout / 'index.json').read_text())
        sha = index['manifests'][0]['digest'][7:]
        (layout / 'blobs' / 'sha256' / sha).write_text('SYNTHETIC TAMPER')
        with self.assertRaisesRegex(ValueError, 'integrity failure'):
            p.verify(layout, self.bundle, False)

    def test_existing_output_not_overwritten(self):
        layout = self.root / 'a'
        layout.mkdir()
        (layout / 'sentinel').write_text('keep')
        with self.assertRaises(FileExistsError):
            p.build(self.bundle, layout, False)
        self.assertEqual('keep', (layout / 'sentinel').read_text())

    def test_index_and_tag_tamper_rejected(self):
        layout = self.root / 'a'
        p.build(self.bundle, layout, False)
        path = layout / 'index.json'
        original = path.read_text()
        for field, value in [('schemaVersion', 1), ('mediaType', 'wrong')]:
            with self.subTest(field=field):
                index = json.loads(original)
                index[field] = value
                path.write_text(json.dumps(index))
                with self.assertRaisesRegex(ValueError, 'index schema/type'):
                    p.verify(layout, self.bundle, False)
        for tag in ('latest', None):
            with self.subTest(tag=tag):
                index = json.loads(original)
                index['manifests'][0]['annotations'] = {'org.opencontainers.image.ref.name': tag}
                path.write_text(json.dumps(index))
                with self.assertRaisesRegex(ValueError, 'version reference'):
                    p.verify(layout, self.bundle, False)

    def test_optional_index_media_type(self):
        layout = self.root / 'a'
        expected = p.build(self.bundle, layout, False)
        path = layout / 'index.json'
        index = json.loads(path.read_text())
        del index['mediaType']
        path.write_bytes(p.encode(index))
        self.assertEqual(expected, p.verify(layout, self.bundle, False))

    def test_manifest_schema_tamper_rejected(self):
        layout = self.root / 'a'
        p.build(self.bundle, layout, False)
        index_path = layout / 'index.json'
        index = json.loads(index_path.read_text())
        desc = index['manifests'][0]
        manifest_path = layout / 'blobs' / 'sha256' / desc['digest'][7:]
        manifest = json.loads(manifest_path.read_text())
        manifest['schemaVersion'] = 1
        data = p.encode(manifest)
        sha = hashlib.sha256(data).hexdigest()
        (manifest_path.parent / sha).write_bytes(data)
        desc['digest'] = 'sha256:' + sha
        desc['size'] = len(data)
        index_path.write_bytes(p.encode(index))
        with self.assertRaisesRegex(ValueError, 'manifest schema/type'):
            p.verify(layout, self.bundle, False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
