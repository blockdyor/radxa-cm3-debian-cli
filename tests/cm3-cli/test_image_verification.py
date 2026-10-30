import importlib.util
import lzma
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('image_verify', ROOT / 'scripts/cm3-verify-image.py')
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class ImageContract(unittest.TestCase):
    def partitions(self):
        return [dict(part_num=n, part_start=start * 512, part_end=end * 512 - 1,
                     part_size=(end - start) * 512)
                for n, start, end in [(1, 32768, 65536), (2, 65536, 679936), (3, 679936, 999966)]]

    def test_layout_offsets_sizes_sector_and_table(self):
        self.assertEqual(verify.contract.layout(self.partitions(), 1000000 * 512, 512, 'gpt')['layout'], 'PASS')
        for sector, table in [(4096, 'gpt'), (512, 'msdos')]:
            with self.assertRaises(ValueError):
                verify.contract.layout(self.partitions(), 1000000 * 512, sector, table)
        for field, value in [('part_start', 512), ('part_end', 1000000 * 512), ('part_size', 42)]:
            parts = self.partitions()
            parts[2][field] = value
            with self.assertRaises(ValueError):
                verify.contract.layout(parts, 1000000 * 512, 512, 'gpt')
        with self.assertRaises(ValueError):
            verify.contract.layout(self.partitions()[:2], 1000000 * 512, 512, 'gpt')

    def boot_inputs(self):
        uuids = ['A123-B456', 'C123-D456', '12345678-1234-4321-8123-123456789abc']
        cmdline = ('root=UUID=' + uuids[2] + ' ro console=ttyFIQ0,1500000n8 apparmor=1 security=apparmor '
                   'lsm=landlock,lockdown,yama,integrity,apparmor,bpf')
        menu = ('label l0\n linux /boot/vmlinuz-test\n initrd /boot/initrd.img-test\n'
                ' fdt /usr/lib/linux-image-test/rockchip/rk3566-radxa-cm3-rpi-cm4-io.dtb\n append ' + cmdline)
        fstab = ''.join('UUID=' + uuid + ' ' + mount + ' ' + kind + ' defaults 0 1\n'
                        for uuid, mount, kind in zip(uuids, ['/config', '/boot/efi', '/'], ['vfat', 'vfat', 'ext4']))
        return menu, cmdline, fstab, uuids

    def test_boot_agreement_and_untested_hardware(self):
        result = verify.contract.boot(*self.boot_inputs())
        self.assertEqual(result['hardware_boot'], 'UNTESTED')
        self.assertEqual(result['paths']['linux'], ['/boot/vmlinuz-test'])

    def test_wrong_root_security_console_dtb_or_extra_mount_fails(self):
        menu, cmdline, fstab, uuids = self.boot_inputs()
        for changed in [menu.replace('root=UUID=', 'root=PARTUUID='),
                        menu.replace('apparmor=1', 'apparmor=0'),
                        menu.replace('ttyFIQ0', 'ttyS0'), menu.replace('rpi-cm4-io', 'io'),
                        menu + '\n fdtoverlays /boot/unreviewed.dtbo',
                        menu.replace('/boot/vmlinuz-test', '/boot/../other')]:
            with self.subTest(menu=changed), self.assertRaises(ValueError):
                verify.contract.boot(changed, cmdline, fstab, uuids)
        with self.assertRaises(ValueError):
            verify.contract.boot(menu, cmdline, fstab + '/dev/sda /extra ext4 defaults 0 1\n', uuids)
        with self.assertRaises(ValueError):
            verify.contract.boot(menu, cmdline, fstab, [uuids[0], uuids[0], uuids[2]])

    def test_actual_decompression_is_hashed_and_truncation_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'image.xz'
            path.write_bytes(lzma.compress(b'actual fixture bytes'))
            import hashlib
            self.assertEqual(verify.compressed_digest(path), (hashlib.sha256(b'actual fixture bytes').hexdigest(), 20))
            path.write_bytes(path.read_bytes()[:-10])
            with self.assertRaises((EOFError, lzma.LZMAError)):
                verify.compressed_digest(path)

    def test_inventory_requires_exact_package_configuration_and_architecture(self):
        status = 'Package: base\nStatus: install ok installed\nVersion: 1\nArchitecture: arm64\n'
        expected = 'base\t1\tarm64\tinstalled\n'
        self.assertEqual(verify.inventory(status, expected), expected)
        for bad in [status.replace('arm64', 'amd64'), status.replace('installed', 'unpacked'),
                    status.replace('Version: 1', 'Version: 2'), status + '\n' + status,
                    status.replace('base', 'docker.io')]:
            with self.assertRaises(ValueError):
                verify.inventory(bad, expected)
