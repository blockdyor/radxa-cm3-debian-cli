"""Publication schema/inventory fixtures, separate from real crypto-chain replay."""
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


publish = load('publish_security_tests', 'cm3-publish-image.py')
public = load('public_vector_constants', 'cm3-public-test-vectors.py')


def security_fixture(directory, identity):
    chain_dir = directory / 'package-chain'
    chain_dir.mkdir()
    (chain_dir / 'debian-archive-keyring.gpg').write_bytes(b'public keyring fixture')
    anchor = publish.assembly.profile.probe.digest(chain_dir / 'debian-archive-keyring.gpg')
    with tarfile.open(directory / 'package-chain.tar.gz', 'w:gz') as archive:
        archive.add(chain_dir, arcname='package-chain')
    shutil.rmtree(chain_dir)
    chain = dict(identity, status='PASS', local_fingerprint='A' * 40,
                 debian_keyring_sha256=anchor, installed=1, packages=[{}],
                 files_sha256={'debian-archive-keyring.gpg': anchor})
    vectors = dict(identity, literal_zero_private_key_bytes=False,
                   public_vectors=dict(path=public.LIBRARY, blocks=8, library_sha256=public.LIBRARY_SHA256,
                                       source_archive_sha256=public.SOURCE_SHA256,
                                       source_member_sha256=public.MEMBER_SHA256))
    (directory / 'package-chain-verification.json').write_text(json.dumps(chain))
    (directory / 'public-test-vectors.json').write_text(json.dumps(vectors))


class SecurityDelivery(unittest.TestCase):
    def test_malformed_wrong_run_and_unbound_archive_rejected(self):
        identity = dict(source_revision='a' * 40, run_id='123')
        delivery = dict(identity, authenticated_input_receipt=dict(signing_fingerprint='A' * 40))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            security_fixture(directory, identity)
            publish.checked_security(directory, delivery)
            chain = directory / 'package-chain-verification.json'
            original = chain.read_text()
            for value in ['not JSON', '[]', json.dumps(dict(json.loads(original), run_id='other')),
                          json.dumps(dict(json.loads(original), status='FAIL'))]:
                chain.write_text(value)
                with self.assertRaises(ValueError):
                    publish.checked_security(directory, delivery)
            chain.write_text(original)
            vectors = directory / 'public-test-vectors.json'
            original_vectors = vectors.read_text()
            vectors.write_text(json.dumps(dict(json.loads(original_vectors), public_vectors={})))
            with self.assertRaisesRegex(ValueError, 'public-vector'):
                publish.checked_security(directory, delivery)
            vectors.write_text(original_vectors)
            with tarfile.open(directory / 'package-chain.tar.gz', 'w:gz') as archive:
                info = tarfile.TarInfo('package-chain/secret.key')
                info.size = 0
                archive.addfile(info)
            with self.assertRaisesRegex(ValueError, 'archive member'):
                publish.checked_security(directory, delivery)
