"""Loader chains with every mutator doubled; independent pure target-policy tests."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SUBJECT = Path(os.environ.get('CM3_TEST_LOADER', ROOT / 'project/cm3-cli/loader-setup.sh'))
SPEC = importlib.util.spec_from_file_location('loader_target', ROOT / 'project/cm3-cli/loader-target.py')
assert SPEC is not None and SPEC.loader is not None
target_policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target_policy)
MOCKS = r'''
export PATH=/nonexistent
COUNT=0
function dd {
    COUNT=$((COUNT+1)); printf 'DD'; printf ' <%s>' "$@"; printf '\n'
    [[ $COUNT == "${FAIL_WRITE:-0}" ]] && return 30
    return 0
}
function sync { printf 'SYNC\n'; return "${SYNC_STATUS:-0}"; }
function rkdeveloptool {
    printf 'RK %s\n' "$1"
    if [[ $1 == db ]]; then return "${DB_STATUS:-0}"; fi
    if [[ $1 == rd ]]; then return "${RESET_STATUS:-0}"; fi
    COUNT=$((COUNT+1)); [[ $COUNT == "${FAIL_WRITE:-0}" ]] && return 30
    return 0
}
function sleep { :; }
function stat {
    if [[ $2 == '%h:%u' ]]; then printf '1:%s\n' "$EUID";
    elif [[ $4 == "$TARGET" ]]; then printf '1073741824\n'; else printf '16\n'; fi
}
# This double controls only admission/command chaining. The real target policy is
# independently exercised below; it is never substituted as evidence of live topology.
function python3 { return "${GUARD_STATUS:-0}"; }
source "$SUBJECT"
SCRIPT_DIR="$PAYLOAD"
if [[ ${CONTEXT:-sourced} == strict ]]; then set -euo pipefail; fi
if [[ ${CONTEXT:-sourced} == conditional ]]; then
    "$ACTION" "$TARGET" "${ROLE:-os}" || exit $?
else
    "$ACTION" "$TARGET" "${ROLE:-os}"
fi
'''


def topology() -> dict:
    return dict(disk='/dev/mmcblk1', transport='MMC', capacity=1073741824,
                readonly=False, holders=False, swap=False, mounts=[], board=True,
                devices=['179:8', '179:9', '179:10', '179:11'], running_root='179:11',
                fstab_matches=True, filesystems=['vfat', 'vfat', 'ext4'],
                table=dict(label='gpt', unit='sectors', sectorsize=512,
                    partitions=[dict(start=32768, size=32768),
                                dict(start=65536, size=614400, type='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'),
                                dict(start=679936, size=1000000, type='0fc63daf-8483-4772-8e79-3d69d8477de4')]))


def os_topology() -> dict:
    state = topology()
    state['mounts'] = [dict(target=mount, partition=number, fstype=kind, fsroot='/')
                       for mount, number, kind in [('/', 3, 'ext4'), ('/config', 1, 'vfat'), ('/boot/efi', 2, 'vfat')]]
    return state


class TargetPolicyTests(unittest.TestCase):
    def test_exact_provisioning_layout_and_verified_os_parent_allowed(self):
        target_policy.validate(topology(), 'provisioning')
        target_policy.validate(os_topology(), 'os')

    def test_unrelated_unmounted_mmc_overlapping_layout_and_wrong_transports_refused(self):
        cases = []
        for field, value in [('disk', '/dev/nvme0n1'), ('disk', '/dev/mmcblk1p3'),
                             ('disk', '/dev/disk/by-id/example'), ('transport', 'USB'),
                             ('readonly', True), ('holders', True), ('swap', True),
                             ('filesystems', ['ext4', 'vfat', 'ext4'])]:
            cases.append(dict(topology(), **{field: value}))
        bad = topology()
        bad['table']['partitions'][0]['start'] = 2048
        cases.append(bad)
        for state in cases:
            with self.subTest(state=state), self.assertRaises(ValueError):
                target_policy.validate(state, 'provisioning')
        with self.assertRaises(ValueError):
            target_policy.validate(topology(), 'os')

    def test_unrelated_mounted_data_alias_missing_mount_wrong_board_uuid_or_root_refused(self):
        for change in ('data', 'alias', 'missing', 'board', 'uuid', 'root', 'subroot'):
            state = os_topology()
            if change == 'data':
                state['mounts'][0]['target'] = '/data'
            elif change == 'alias':
                state['mounts'].append(dict(state['mounts'][0], target='/data-alias'))
            elif change == 'missing':
                state['mounts'].pop()
            elif change == 'board':
                state['board'] = False
            elif change == 'uuid':
                state['fstab_matches'] = False
            elif change == 'root':
                state['running_root'] = '259:3'
            else:
                state['mounts'][0]['fsroot'] = '/data'
            with self.subTest(change=change), self.assertRaises(ValueError):
                target_policy.validate(state, 'os')
        with self.assertRaises(ValueError):
            target_policy.validate(os_topology(), 'provisioning')

    def test_real_inspector_rejects_regular_missing_and_redirected_images_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.img'
            path.write_bytes(b'not-an-image')
            with self.assertRaises(ValueError):
                target_policy.inspect_device(path)
            with patch.object(target_policy, 'query', return_value={'partitiontable': topology()['table']}):
                with self.assertRaises(ValueError):
                    target_policy.inspect_image(path)
            alias = path.with_name('alias.img')
            alias.symlink_to(path)
            with self.assertRaises(ValueError):
                target_policy.inspect_image(alias)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                target_policy.inspect_image(path)


class LoaderSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.payload = self.root / 'payload'
        self.payload.mkdir()
        for name in ('idblock.img', 'u-boot.itb', 'rkboot.bin', 'loader-target.py'):
            (self.payload / name).write_bytes(b'fixture-only')

    def action(self, action='update_bootloader', target='/dev/mmcblk1', **values):
        return subprocess.run(['/usr/bin/bash', '--noprofile', '--norc'], input=MOCKS,
                              capture_output=True, text=True, timeout=10,
                              env={'SUBJECT': str(SUBJECT), 'PAYLOAD': str(self.payload),
                                   'ACTION': action, 'TARGET': target, **values})

    def no_write(self, **values):
        result = self.action(**values)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for forbidden in ('DD', 'RK wl', 'RK rd', 'SYNC'):
            self.assertNotIn(forbidden, result.stdout)
        return result

    def test_every_direct_writer_honors_target_admission_before_write(self):
        for action in ('update_bootloader', 'update_idblock', 'erase_bootloader'):
            for context in ('strict', 'sourced', 'conditional'):
                with self.subTest(action=action, context=context):
                    self.no_write(action=action, GUARD_STATUS='17', CONTEXT=context)

    def test_missing_payload_precedes_any_write_or_maskrom_download(self):
        for name in ('idblock.img', 'u-boot.itb', 'rkboot.bin'):
            path = self.payload / name
            data = path.read_bytes()
            path.unlink()
            for action in ('update_bootloader', 'update_idblock', 'maskrom_autoupdate_bootloader', 'maskrom_update_bootloader'):
                if name == 'rkboot.bin' and action != 'maskrom_autoupdate_bootloader':
                    continue
                with self.subTest(name=name, action=action):
                    result = self.no_write(action=action)
                    self.assertNotIn('RK db', result.stdout)
            path.write_bytes(data)

    def test_empty_and_symlink_payload_refused(self):
        path = self.payload / 'u-boot.itb'
        path.write_bytes(b'')
        self.no_write()
        path.unlink()
        path.symlink_to('idblock.img')
        self.no_write()

    def test_db_each_write_sync_and_reset_failure_propagates_in_all_contexts(self):
        for context in ('strict', 'sourced', 'conditional'):
            result = self.no_write(action='maskrom_autoupdate_bootloader', DB_STATUS='19', CONTEXT=context)
            self.assertEqual(result.returncode, 19)
            for action in ('update_bootloader', 'maskrom_autoupdate_bootloader'):
                for number in ('1', '2'):
                    result = self.action(action=action, FAIL_WRITE=number, CONTEXT=context)
                    self.assertEqual(result.returncode, 30)
                    self.assertNotIn('SYNC', result.stdout)
                    self.assertNotIn('RK rd', result.stdout)
            self.assertEqual(self.action(SYNC_STATUS='31', CONTEXT=context).returncode, 31)
            self.assertEqual(self.action(action='maskrom_autoupdate_bootloader', RESET_STATUS='32', CONTEXT=context).returncode, 32)

    def test_offsets_target_and_explicit_regular_image_mode(self):
        for action, role, target in [('update_bootloader', 'os', '/dev/mmcblk1'),
                                     ('update_bootloader', 'provisioning', '/dev/mmcblk1'),
                                     ('update_image', '512', str(self.root / 'fixture.img'))]:
            if action == 'update_image':
                Path(target).write_bytes(b'fixture-file-only')
            result = self.action(action=action, target=target, ROLE=role)
            self.assertEqual(result.returncode, 0, result.stderr)
            writes = [line for line in result.stdout.splitlines() if line.startswith('DD')]
            self.assertEqual(len(writes), 2)
            self.assertTrue(all('<of=' + target + '>' in row for row in writes))
            self.assertIn('<bs=512> <seek=64>', writes[0])
            self.assertIn('<bs=512> <seek=16384>', writes[1])
            self.assertNotIn('seek=136', result.stdout)
        self.no_write(action='update_image', target=str(self.root / 'missing.img'), ROLE='512')
