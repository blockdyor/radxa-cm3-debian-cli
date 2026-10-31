import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

source = load('overlay_source', 'cm3-source-preflight.py')
delivery = load('notice_delivery', 'cm3-image-delivery.py')


class NoticeAdmission(unittest.TestCase):
    def test_official_metadata_backport_applies_without_source_changes_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary)
            subprocess.run(['git', 'init', '--quiet', str(checkout)], check=True)
            copyright = checkout / 'debian/copyright'
            copyright.parent.mkdir()
            original = ('Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n'
                        'Upstream-Name: radxa-overlays\nSource: https://github.com/radxa-pkg/radxa-overlays\n\n'
                        'Files: *\nCopyright: © 2025 Radxa Computer Co., Ltd\nLicense: GPL-3+\n')
            copyright.write_text(original)
            source_file = checkout / 'source.c'
            source_file.write_text('/* source fixture unchanged */\n')
            source.prepare_overlay_license(checkout)
            self.assertIn('Files: debian/radxa-overlays.c\nCopyright: © 2025 Radxa Computer Co., Ltd\nLicense: GPL-2', copyright.read_text())
            self.assertEqual(source_file.read_text(), '/* source fixture unchanged */\n')
            with self.assertRaises(subprocess.CalledProcessError):
                source.prepare_overlay_license(checkout)
            copyright.write_text(original.replace('radxa-pkg/radxa-overlays', 'unexpected/source'))
            with self.assertRaises(subprocess.CalledProcessError):
                source.prepare_overlay_license(checkout)

    def test_review_requires_installed_clarification_and_reviewed_firmware_version_and_notices(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            root = work / 'root'
            original = work / 'radxa-overlays/debian/copyright'
            installed = root / 'usr/share/doc/radxa-overlays-dkms/copyright'
            for path in [original, installed]:
                path.parent.mkdir(parents=True)
                path.write_text('fixture: GPL-2, unless otherwise noted\n')
            for package in ['firmware-brcm80211', 'firmware-realtek']:
                path = root / 'usr/share/doc' / package / 'copyright'
                path.parent.mkdir(parents=True)
                path.write_text('fixture notice bytes')
            digest = 'f5d62266d99e91aeae9223a5b4f830ed5e917256672f50470ef868e0378ad6d8'
            with patch.object(delivery.assembly.profile.probe, 'chroot', return_value='20250410-2'), \
                    patch.object(delivery.assembly.profile.probe, 'digest', return_value=digest):
                self.assertEqual(len(delivery.review_notices(work, root)['firmware']), 2)
                installed.write_text('missing official clarification')
                with self.assertRaisesRegex(ValueError, 'overlay'):
                    delivery.review_notices(work, root)
                installed.write_bytes(original.read_bytes())
            for version, fingerprint in [('new-version', digest), ('20250410-2', '0' * 64)]:
                with patch.object(delivery.assembly.profile.probe, 'chroot', return_value=version), \
                        patch.object(delivery.assembly.profile.probe, 'digest', return_value=fingerprint):
                    with self.assertRaisesRegex(ValueError, 'firmware version/notices'):
                        delivery.review_notices(work, root)
