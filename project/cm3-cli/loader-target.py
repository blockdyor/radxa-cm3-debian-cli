#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read-only admission for explicit CM3 loader targets; never opens for writing."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def layout(table, capacity):
    if (table['label'] != 'gpt' or table['unit'] != 'sectors' or table['sectorsize'] != 512 or
            len(table['partitions']) != 3 or type(capacity) is not int or capacity % 512):
        raise ValueError('exact 512-byte-sector CM3 GPT layout required')
    for part, (start, size) in zip(table['partitions'], [(32768, 32768), (65536, 614400), (679936, None)]):
        if (part['start'] != start or type(part['size']) is not int or part['size'] <= 0 or
                (size is not None and part['size'] != size)):
            raise ValueError('loader reserved layout differs')
    root = table['partitions'][2]
    if root['start'] + root['size'] > capacity // 512 - 33:
        raise ValueError('partition exceeds media capacity')
    if (table['partitions'][1]['type'].lower() != 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b' or
            root['type'].lower() != '0fc63daf-8483-4772-8e79-3d69d8477de4'):
        raise ValueError('unexpected EFI/root partition type')


def validate(state, role):
    disk = state['disk']
    if re.fullmatch(r'/dev/mmcblk\d+', disk) is None or state['transport'] not in ('SD', 'MMC'):
        raise ValueError('whole native SD/eMMC only; NVMe/USB/aliases refused')
    layout(state['table'], state['capacity'])
    if state['readonly'] or state['holders'] or state['swap']:
        raise ValueError('readonly, stacked or active-swap media refused')
    if state['filesystems'] != ['vfat', 'vfat', 'ext4']:
        raise ValueError('expected image filesystems required')
    mounts = state['mounts']
    if role == 'provisioning':
        if mounts:
            raise ValueError('provisioning media must be unmounted')
    elif role == 'os':
        expected = {('/', 3, 'ext4'), ('/config', 1, 'vfat'), ('/boot/efi', 2, 'vfat')}
        actual = {(row['target'], row['partition'], row['fstype']) for row in mounts}
        if (len(mounts) != 3 or actual != expected or not state['board'] or
                state['running_root'] != state['devices'][3] or not state['fstab_matches'] or
                any(row['fsroot'] != '/' for row in mounts)):
            raise ValueError('only the verified selected CM3 OS parent may be mounted')
    else:
        raise ValueError('explicit OS or provisioning role required')


def query(*args):
    result = subprocess.check_output(args, text=True, stdin=subprocess.DEVNULL, timeout=15,
                                     env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
    if len(result) > 2 * 1024 * 1024:
        raise ValueError('oversized target topology')
    return json.loads(result)


def inspect_device(path):
    if re.fullmatch(r'/dev/mmcblk\d+', str(path)) is None or path.resolve() != path:
        raise ValueError('not an explicit canonical MMC disk')
    nodes = [path, *[Path(str(path) + 'p' + str(number)) for number in (1, 2, 3)]]
    devices, holders, readonly = [], False, False
    for node in nodes:
        info = node.lstat()
        if not stat.S_ISBLK(info.st_mode) or os.major(info.st_rdev) != 179:
            raise ValueError('not a native MMC block node')
        devices.append(f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}')
        kernel = Path('/sys/class/block') / node.name
        if kernel.joinpath('dev').read_text().strip() != devices[-1]:
            raise ValueError('node and kernel identity disagree')
        if node != path and kernel.resolve().parent != (Path('/sys/class/block') / path.name).resolve():
            raise ValueError('partition ancestry differs')
        holders |= bool(list(kernel.joinpath('holders').iterdir()))
        readonly |= kernel.joinpath('ro').read_text().strip() != '0'
    table = query('/usr/sbin/sfdisk', '--json', str(path))['partitiontable']
    if table['device'] != str(path) or [row['node'] for row in table['partitions']] != list(map(str, nodes[1:])):
        raise ValueError('partition enumeration differs')
    rows = query('/usr/bin/findmnt', '--json', '--list', '--output', 'TARGET,SOURCE,FSTYPE,MAJ:MIN,UUID,FSROOT')['filesystems']
    mounts = [dict(row, partition=devices.index(row['maj:min'])) for row in rows if row['maj:min'] in devices]
    swaps = Path('/proc/swaps').read_text().splitlines()[1:]
    active_swap = any(os.stat(row.split()[0]).st_dev in [node.stat().st_rdev for node in nodes] or
                      os.stat(row.split()[0]).st_rdev in [node.stat().st_rdev for node in nodes] for row in swaps)
    fstab = [row.split() for row in Path('/etc/fstab').read_text().splitlines()
             if row.strip() and not row.lstrip().startswith('#')]
    matches = len(fstab) == 3 and all(any(len(entry) >= 6 and entry[1] == row['target'] and
                entry[0] == 'UUID=' + str(row['uuid']) and entry[2] == row['fstype'] for entry in fstab) for row in mounts)
    compatible = Path('/proc/device-tree/compatible')
    board = compatible.read_bytes().split(b'\0') if compatible.exists() else []
    root_dev = os.stat('/').st_dev
    return dict(disk=str(path), table=table,
                capacity=int(subprocess.check_output(['/usr/sbin/blockdev', '--getsize64', str(path)], timeout=15)),
                devices=devices, transport=(Path('/sys/class/block') / path.name / 'device/type').read_text().strip(),
                holders=holders, readonly=readonly, swap=active_swap, mounts=mounts,
                filesystems=[subprocess.check_output(['/usr/sbin/blkid', '-p', '-s', 'TYPE', '-o', 'value', str(node)],
                             timeout=15, text=True).strip() for node in nodes[1:]],
                running_root=f'{os.major(root_dev)}:{os.minor(root_dev)}',
                board=b'radxa,cm3-rpi-cm4-io' in board and b'rockchip,rk3566' in board,
                fstab_matches=matches)


def inspect_image(path):
    if path.resolve() != path or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('image path must be canonical and unredirected')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
        raise ValueError('existing owned single-link image required')
    table = query('/usr/sbin/sfdisk', '--json', str(path))['partitiontable']
    layout(table, info.st_size)


def main():
    try:
        if len(sys.argv) != 3 or sys.argv[1] not in ('os', 'provisioning', 'image'):
            raise ValueError('explicit role and one target required')
        role, path = sys.argv[1], Path(sys.argv[2])
        if role == 'image':
            inspect_image(path)
        else:
            validate(inspect_device(path), role)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        sys.exit('CM3 loader target refused; verify explicit role, image layout and protected media.')


if __name__ == '__main__':
    main()
