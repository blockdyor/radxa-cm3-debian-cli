"""OS-only growth policy/command fixtures; never invokes a real storage tool."""
import copy
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('grow_os', ROOT / 'packages/cm3-cli-board-support/root/usr/lib/cm3-cli/grow_os.py')
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture() -> dict:
    return dict(disk='/dev/mmcblk0', root='/dev/mmcblk0p3', disk_generation='7', readonly=False,
                disk_bytes=8 * 1024**3, root_device=os.makedev(179, 3),
                mounts=[dict(target=target, source='/dev/mmcblk0p' + str(number), fstype=kind,
                             device='179:' + str(number), fsroot='/', options='rw')
                        for target, number, kind in [('/', 3, 'ext4'), ('/config', 1, 'vfat'), ('/boot/efi', 2, 'vfat')]],
                partitiontable=dict(label='gpt', device='/dev/mmcblk0', unit='sectors', sectorsize=512,
                    id='fixture-disk', lastlba=4000000,
                    partitions=[dict(node='/dev/mmcblk0p1', start=32768, size=32768, uuid='config'),
                                dict(node='/dev/mmcblk0p2', start=65536, size=614400, uuid='efi'),
                                dict(node='/dev/mmcblk0p3', start=679936, size=3300000, uuid='root')]))


class GrowOsTests(unittest.TestCase):
    def test_plan_default_executes_no_commands(self):
        calls = []
        result = module.grow(fixture, lambda *args: calls.append(args))
        self.assertEqual(result['status'], 'PLAN_ONLY')
        self.assertEqual(result['root'], '/dev/mmcblk0p3')
        self.assertEqual(calls, [])

    def test_nvme_usb_wrong_device_geometry_readonly_and_alias_rejected(self):
        cases = [dict(fixture(), **{key: value}) for key, value in
                 [('disk', '/dev/nvme0n1'), ('disk', '/dev/sda'), ('root', '/dev/mmcblk1p3'),
                  ('disk_generation', ''), ('disk_bytes', 1024), ('readonly', True)]]
        for number, field, value in [(0, 'start', 2048), (1, 'size', 100), (2, 'start', 680000)]:
            state = fixture()
            state['partitiontable']['partitions'][number][field] = value
            cases.append(state)
        for change in ('alias', 'subroot', 'readonly', 'major'):
            state = fixture()
            if change == 'alias':
                state['mounts'].append(dict(state['mounts'][0], target='/data'))
            elif change == 'subroot':
                state['mounts'][0]['fsroot'] = '/data'
            elif change == 'readonly':
                state['mounts'][0]['options'] = 'ro'
            else:
                state['root_device'] = os.makedev(259, 3)
            cases.append(state)
        for state in cases:
            calls = []
            with self.subTest(state=state), self.assertRaises(ValueError):
                module.grow(lambda: state, lambda *args: calls.append(args), execute=True)
            self.assertEqual(calls, [])

    def test_only_root_grows_and_interrupted_after_gpt_resumes_ext4_step(self):
        state, calls = fixture(), []
        original = copy.deepcopy(state)
        def command(*args):
            calls.append(args)
            if args[0].endswith('growpart'):
                state['partitiontable']['lastlba'] = state['disk_bytes'] // 512 - 34
                state['partitiontable']['partitions'][2]['size'] = state['partitiontable']['lastlba'] - 679936 + 1
        module.grow(lambda: copy.deepcopy(state), command, execute=True)
        self.assertEqual(calls, [('/usr/bin/growpart', '--fudge', '0', '/dev/mmcblk0', '3'),
                                 ('/usr/sbin/resize2fs', '/dev/mmcblk0p3')])
        self.assertEqual(state['partitiontable']['partitions'][:2], original['partitiontable']['partitions'][:2])
        calls.clear()
        module.grow(lambda: copy.deepcopy(state), command, execute=True)
        self.assertEqual(calls, [('/usr/sbin/resize2fs', '/dev/mmcblk0p3')])

    def test_identity_drift_and_failed_partition_growth_never_run_resize(self):
        first, changed = fixture(), fixture()
        changed['disk_generation'] = '8'
        snapshots, calls = iter([first, changed]), []
        with self.assertRaises(ValueError):
            module.grow(lambda: next(snapshots), lambda *args: calls.append(args), execute=True)
        self.assertEqual(calls, [])
        def fail(*args):
            calls.append(args)
            raise OSError('fixture interruption')
        with self.assertRaises(OSError):
            module.grow(fixture, fail, execute=True)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].endswith('growpart'))

    def test_protected_readback_drift_never_runs_filesystem_resize(self):
        state, calls = fixture(), []
        def change(*args):
            calls.append(args)
            state['partitiontable']['partitions'][0]['uuid'] = 'changed'
        with self.assertRaises(ValueError):
            module.grow(lambda: copy.deepcopy(state), change, execute=True)
        self.assertEqual(len(calls), 1)

    def test_service_sees_real_topology_and_package_gates_enrollment(self):
        base = ROOT / 'packages/cm3-cli-board-support'
        unit = (base / 'root/usr/lib/systemd/system/cm3-cli-grow-os.service').read_text()
        for forbidden in ('ProtectSystem=', 'ProtectHome=', 'PrivateTmp='):
            self.assertNotIn(forbidden, unit, 'namespace bind mounts conflict with exact device alias policy')
        self.assertIn('DeviceAllow=block-mmc rw', unit)
        self.assertIn('cm3-cli-grow-os.service', (base / 'root/usr/lib/systemd/system/cm3-cli-enroll.service').read_text())
        self.assertIn('cloud-guest-utils', (base / 'control/control').read_text())
