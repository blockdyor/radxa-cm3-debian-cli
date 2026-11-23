import base64
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('owner_config', ROOT / 'scripts/cm3-owner-config.py')
owner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owner)
# RFC 8032 test-vector public key; no private key is created or used.
PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
BLOB = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + PUBLIC
KEY = 'ssh-ed25519 ' + base64.b64encode(BLOB).decode()


class OwnerConfigTests(unittest.TestCase):
    def config(self, **changes):
        data = {'version': 1, 'username': 'alice', 'authorized_key': KEY}
        data.update(changes)
        return json.dumps(data).encode()

    def test_canonical_key_and_comment_stripping(self):
        value = owner.validate_owner(self.config(authorized_key=KEY + ' owner@example.invalid'))
        self.assertEqual(value, {'version': 1, 'username': 'alice', 'authorized_key': KEY})

    def test_fail_closed_schema_and_duplicate_fields(self):
        invalid = [b'{}', b'[]', b'null', b'\xff', b'{', b'{}' * 5000,
                   b'{"version":1,"version":1,"username":"alice","authorized_key":"x"}',
                   self.config(version=True), self.config(version=2),
                   self.config(password='not-allowed'), self.config(on_boot='touch /unwanted')]
        for data in invalid:
            with self.subTest(data=data[:50]):
                with self.assertRaises(ValueError):
                    owner.validate_owner(data)

    def test_reject_root_system_and_shell_names(self):
        for name in ['root', 'daemon', '_apt', 'nobody', '-admin', 'Alice', 'a' * 32,
                     'alice;id', '../alice', 'alice\nroot', 42, None]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    owner.validate_owner(self.config(username=name))

    def test_reject_options_multiline_other_types_and_malformed_wire(self):
        malformed = [KEY.replace('ssh-ed25519', 'ssh-rsa', 1), 'command="id" ' + KEY,
                     KEY + '\n' + KEY, KEY + '\tcomment', 'ssh-ed25519 !!!',
                     'ssh-ed25519 ' + base64.b64encode(BLOB + b'extra').decode(),
                     'ssh-ed25519 ' + base64.b64encode(BLOB[:-1]).decode(),
                     'ssh-ed25519 ' + base64.b64encode(BLOB[:-32] + bytes(32)).decode(),
                     'ssh-ed25519 ' + base64.b64encode(BLOB.replace(b'ssh-ed25519', b'ssh-ed25518')).decode(),
                     None, 1]
        for key in malformed:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    owner.validate_owner(self.config(authorized_key=key))

    def test_cli_has_no_mutation_or_key_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'owner.json'
            path.write_bytes(self.config())
            before = path.read_bytes()
            result = subprocess.run(['python3', str(ROOT / 'scripts/cm3-owner-config.py'), str(path)],
                                    check=True, capture_output=True, text=True)
            self.assertIn('no account or system changes', result.stdout)
            self.assertNotIn('alice', result.stdout)
            self.assertNotIn(KEY, result.stdout)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['owner.json'])
            # OpenSSH independently accepts the public-key wire format in the fixture.
            public_path = Path(directory) / 'fixture.pub'
            public_path.write_text(KEY + '\n')
            result = subprocess.run(['ssh-keygen', '-l', '-f', str(public_path)],
                                    check=True, capture_output=True, text=True)
            self.assertIn('ED25519', result.stdout)


if __name__ == '__main__':
    unittest.main()
