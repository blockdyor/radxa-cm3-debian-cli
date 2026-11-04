#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Grow only this image's running MMC root partition3; default is a read-only plan."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess


def plan(state):
    disk, root, table = state['disk'], state['root'], state['partitiontable']
    if (re.fullmatch(r'/dev/mmcblk\d+', disk) is None or root != disk + 'p3' or
            re.fullmatch(r'[1-9]\d{0,19}', state['disk_generation']) is None or
            type(state['disk_bytes']) is not int or state['disk_bytes'] % 512 or
            state['readonly'] is not False or table['label'] != 'gpt' or
            table['device'] != disk or table['unit'] != 'sectors' or
            table['sectorsize'] != 512 or len(table['partitions']) != 3):
        raise ValueError('only the exact writable MMC GPT OS layout is supported')
    for number, start, size in [(1, 32768, 32768), (2, 65536, 614400), (3, 679936, None)]:
        part = table['partitions'][number - 1]
        if (part['node'] != disk + 'p' + str(number) or part['start'] != start or
                type(part['size']) is not int or part['size'] < 1 or
                (size is not None and part['size'] != size)):
            raise ValueError('protected config/EFI or root geometry differs')
    expected = [('/', root, 'ext4'), ('/config', disk + 'p1', 'vfat'), ('/boot/efi', disk + 'p2', 'vfat')]
    for target, source, kind in expected:
        matches = [row for row in state['mounts'] if row['source'] == source]
        if len(matches) != 1 or (matches[0]['target'], matches[0]['fstype']) != (target, kind):
            raise ValueError('missing, bound or aliased OS filesystem mount')
        selected = matches[0]
        if (selected['fsroot'] != '/' or
                sum(row['device'] == selected['device'] for row in state['mounts']) != 1 or
                (target == '/' and 'rw' not in selected['options'].split(','))):
            raise ValueError('OS filesystem root, mount aliases or write policy differs')
    roots = [row for row in state['mounts'] if row['target'] == '/']
    dev = state['root_device']
    if (os.major(dev) != 179 or len(roots) != 1 or
            roots[0]['device'] != f'{os.major(dev)}:{os.minor(dev)}' or
            any(row['source'].startswith(disk) and row['source'] not in {item[1] for item in expected}
                for row in state['mounts'])):
        raise ValueError('unexpected OS backing-device identity')
    end = table['partitions'][2]['start'] + table['partitions'][2]['size'] - 1
    maximum = state['disk_bytes'] // 512 - 34
    if not 679936 <= end <= maximum:
        raise ValueError('root partition is outside actual OS disk capacity')
    return dict(status='PLAN_ONLY', disk=disk, root=root, needs_growth=maximum - end > 2048)


def grow(inspect, command, execute=False):
    before = inspect()
    result = plan(before)
    if not execute:
        return result
    if inspect() != before:
        raise ValueError('OS disk identity changed before mutation')
    if result['needs_growth']:
        command('/usr/bin/growpart', '--fudge', '0', result['disk'], '3')
        after = inspect()
        enlarged = plan(after)
        allowed = copy.deepcopy(before)
        allowed['partitiontable']['lastlba'] = after['partitiontable']['lastlba']
        allowed['partitiontable']['partitions'][2]['size'] = after['partitiontable']['partitions'][2]['size']
        if after != allowed or enlarged['needs_growth']:
            raise ValueError('partition readback changed protected identity or failed to grow only root')
    # Always repeat this idempotent step after an interruption between GPT and ext4 growth.
    command('/usr/sbin/resize2fs', result['root'])
    final = inspect()
    if plan(final)['needs_growth'] or final != (after if result['needs_growth'] else before):
        raise ValueError('OS disk changed during filesystem resize')
    return dict(result, status='COMMANDS_COMPLETED_REBOOT_UNVERIFIED')


def query(*args):
    data = subprocess.check_output(args, text=True, stdin=subprocess.DEVNULL,
                                   timeout=15, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})
    if len(data) > 2 * 1024 * 1024:
        raise ValueError('oversized OS topology')
    return json.loads(data)


def inspect_os():
    from enroll import target
    target(Path('/'))
    rows = query('/usr/bin/findmnt', '--json', '--list', '--output', 'TARGET,SOURCE,FSTYPE,MAJ:MIN,UUID,FSROOT,OPTIONS')['filesystems']
    mounts = [dict(target=row['target'], source=row['source'], fstype=row['fstype'],
                   device=row['maj:min'], fsroot=row['fsroot'], options=row['options']) for row in rows]
    roots = [row for row in rows if row['target'] == '/']
    if len(roots) != 1 or re.fullmatch(r'/dev/mmcblk\d+p3', roots[0]['source']) is None:
        raise ValueError('running root is not the supported MMC OS partition')
    root = roots[0]['source']
    disk = root.removesuffix('p3')
    root_info, disk_info = os.lstat(root), os.lstat(disk)
    if (not stat.S_ISBLK(root_info.st_mode) or not stat.S_ISBLK(disk_info.st_mode) or
            root_info.st_rdev != os.stat('/').st_dev):
        raise ValueError('running root and block node identity disagree')
    fstab = [row.split() for row in Path('/etc/fstab').read_text().splitlines()
             if row.strip() and not row.lstrip().startswith('#')]
    if len(fstab) != 3:
        raise ValueError('unexpected configured filesystem')
    for mount in ('/', '/config', '/boot/efi'):
        actual = [row for row in rows if row['target'] == mount]
        configured = [row for row in fstab if len(row) >= 6 and row[1] == mount]
        if (len(actual) != 1 or len(configured) != 1 or not actual[0]['uuid'] or
                configured[0][0] != 'UUID=' + actual[0]['uuid']):
            raise ValueError('OS filesystem UUID does not match image mount configuration')
    name = disk.removeprefix('/dev/')
    disk_sys = Path('/sys/class/block') / name
    root_sys = Path('/sys/class/block') / (name + 'p3')
    if (disk_sys.joinpath('dev').read_text().strip() != f'{os.major(disk_info.st_rdev)}:{os.minor(disk_info.st_rdev)}' or
            root_sys.joinpath('dev').read_text().strip() != f'{os.major(root_info.st_rdev)}:{os.minor(root_info.st_rdev)}' or
            root_sys.resolve().parent != disk_sys.resolve()):
        raise ValueError('MMC nodes and kernel ancestry disagree')
    if (disk_sys.joinpath('device/type').read_text().strip() not in ('MMC', 'SD') or
            list(disk_sys.joinpath('slaves').iterdir())):
        raise ValueError('unsupported MMC ancestry')
    for node in (disk_sys, root_sys):
        if node.joinpath('ro').read_text().strip() != '0' or list(node.joinpath('holders').iterdir()):
            raise ValueError('readonly or stacked OS storage')
    fd = os.open(disk, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if os.fstat(fd).st_rdev != disk_info.st_rdev:
            raise ValueError('OS disk changed while opening')
        size = bytearray(8)
        fcntl.ioctl(fd, 0x80081272, size, True)  # Linux BLKGETSIZE64: read-only.
    finally:
        os.close(fd)
    return dict(disk=disk, root=root, root_device=root_info.st_rdev, readonly=False,
                disk_generation=disk_sys.joinpath('diskseq').read_text().strip(),
                disk_bytes=struct.unpack('=Q', size)[0], mounts=mounts,
                partitiontable=query('/usr/sbin/sfdisk', '--json', disk)['partitiontable'])


def command(*args):
    subprocess.run(args, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   timeout=180, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'OS-only growth requires root on the exact target.\n')
    try:
        from enroll import trusted_parents
        directory = Path('/run/cm3-cli')
        trusted_parents(Path('/'), 'run/cm3-cli/grow.lock', allow_missing=True)
        directory.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(directory / 'grow.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(json.dumps(grow(inspect_os, command, execute=args.execute), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        parser.exit(1, 'OS growth refused or interrupted. Do not reformat or shrink; use serial/offline recovery.\n')


if __name__ == '__main__':
    main()
