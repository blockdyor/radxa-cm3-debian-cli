import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import package_oci
import publish


class PublicationPolicyTests(unittest.TestCase):
    def test_verified_registry_absence(self):
        for code in ('MANIFEST_UNKNOWN', 'NAME_UNKNOWN'):
            self.assertIsNone(publish.existing_digest(404, json.dumps({'errors': [{'code': code}]}).encode()))

    def test_auth_errors_and_ambiguous_absence_fail_closed(self):
        for status, body in ((401, b'{}'), (403, b'{}'), (500, b'{}'),
                             (404, b'{}'), (404, b'{"errors":[{"code":"DENIED"}]}')):
            with self.subTest(status=status, body=body), self.assertRaises(ValueError):
                publish.existing_digest(status, body)

    def test_conflicting_version_refused(self):
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            publish.existing_digest(200, b'conflicting manifest')

    def test_exact_matching_version_reusable(self):
        # Test digest comparison without credentials or a registry.
        body = b'exact manifest bytes'
        digest = 'sha256:' + hashlib.sha256(body).hexdigest()
        with patch.object(publish, 'DIGEST', digest):
            self.assertEqual(publish.existing_digest(200, body), digest)

    def test_noncanonical_invocation_rejected_before_network(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'canonical'):
            publish.main()

    def test_approved_inventory_and_recipe_are_bound(self):
        self.assertEqual(package_oci.digest(publish.INVENTORY),
                         '9f840370539f5cf4b02a03b2668b234ed358cf5cd360dc641ea56b4bc7f565fe')
        inventory = json.loads(publish.INVENTORY.read_text())['inventory']
        self.assertEqual(set(inventory), set(package_oci.FILES))
        self.assertEqual(len(inventory), 24)
        self.assertEqual(inventory['SHA256SUMS']['sha256'], package_oci.SUMS_SHA)
        self.assertEqual(package_oci.digest(Path(__file__).with_name('package_oci.py')),
                         '54b038bed38fd4990c48d8e5bd63ef42dae4ec164638eaa7beec3693af557eb0')


if __name__ == '__main__':
    unittest.main()
