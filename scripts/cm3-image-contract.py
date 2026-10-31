#!/usr/bin/env python3
"""Offline contract for the pinned CM3 RSDK GPT layout; not hardware boot evidence."""
import re

PRODUCT = 'radxa-cm3-rpi-cm4-io'
PLACEHOLDER = '11111111-1111-4111-8111-111111111111'
SERVICE_LINKS = [
    'multi-user.target.wants/cm3-cli-firewall.service',
    'multi-user.target.wants/cm3-cli-enroll.service',
    'multi-user.target.wants/ssh.service',
    'multi-user.target.wants/NetworkManager.service',
    'sysinit.target.wants/systemd-timesyncd.service',
    'sysinit.target.wants/apparmor.service',
    'getty.target.wants/serial-getty@ttyFIQ0.service',
]


def layout(partitions, image_bytes, sector_size, table):
    if sector_size != 512 or table != 'gpt' or image_bytes % 512:
        raise ValueError('CM3 requires 512-byte-sector GPT disk')
    # Pinned RSDK create_partition_table.jsonnet: config16MiB, EFI300MiB, root.
    expected = [(1, 32768 * 512, 65536 * 512 - 1),
                (2, 65536 * 512, 679936 * 512 - 1)]
    if len(partitions) != 3:
        raise ValueError('exact three-partition RSDK layout required')
    for part, (number, start, end) in zip(partitions[:2], expected):
        if (part['part_num'], part['part_start'], part['part_end']) != (number, start, end):
            raise ValueError('config/EFI partition offset mismatch')
    root = partitions[2]
    if (root['part_num'] != 3 or root['part_start'] != 679936 * 512 or
            root['part_end'] >= image_bytes - 33 * 512 or root['part_end'] < root['part_start']):
        raise ValueError('root partition outside expected disk bounds')
    for part in partitions:
        if part['part_size'] != part['part_end'] - part['part_start'] + 1:
            raise ValueError('partition size mismatch')
    return {'layout': 'PASS', 'sector_size': 512, 'partitions': partitions}


def boot(extlinux, cmdline, fstab, uuids):
    if any(re.fullmatch(r'[0-9a-fA-F-]+', value) is None for value in uuids):
        raise ValueError('invalid filesystem UUID')
    if len(set(uuids)) != 3 or PLACEHOLDER in uuids:
        raise ValueError('fresh distinct filesystem UUIDs required')
    rows = [line.split() for line in fstab.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    for uuid, mount, kind in zip(uuids, ['/config', '/boot/efi', '/'], ['vfat', 'vfat', 'ext4']):
        found = [row for row in rows if len(row) >= 6 and row[1] == mount]
        if len(found) != 1 or found[0][0] != 'UUID=' + uuid or found[0][2] != kind:
            raise ValueError('fstab and filesystem UUIDs disagree')
    if len(rows) != 3:
        raise ValueError('unexpected fstab device or mount')
    directives = [line.split(None, 1) for line in extlinux.splitlines() if line.strip()]
    append = [row[1] for row in directives if len(row) == 2 and row[0].lower() == 'append']
    if not append:
        raise ValueError('missing extlinux append')
    for line in append + [cmdline]:
        tokens = line.split()
        roots = [token for token in tokens if token.startswith('root=')]
        if roots != ['root=UUID=' + uuids[2]]:
            raise ValueError('boot root does not match actual root filesystem')
        for token in ['console=ttyFIQ0,1500000n8', 'apparmor=1', 'security=apparmor',
                      'lsm=landlock,lockdown,yama,integrity,apparmor,bpf']:
            if token not in tokens:
                raise ValueError('boot console/security intent missing: ' + token)
    if PLACEHOLDER in extlinux + cmdline + fstab or re.search(r'^\s*fdtoverlays\s', extlinux, re.M | re.I):
        raise ValueError('staging UUID or unreviewed overlays retained')
    paths = {}
    for kind in ['linux', 'initrd', 'fdt']:
        found = [row[1].strip() for row in directives if len(row) == 2 and row[0].lower() == kind]
        if not found or any(not path.startswith('/') or '..' in path.split('/') or '\x00' in path for path in found):
            raise ValueError('missing or unsafe extlinux ' + kind + ' path')
        paths[kind] = sorted(set(found))
    if any('rockchip/rk3566-radxa-cm3-rpi-cm4-io.dtb' not in path for path in paths['fdt']):
        raise ValueError('wrong carrier DTB path')
    return {'boot_contract': 'PASS', 'paths': paths, 'hardware_boot': 'UNTESTED'}
