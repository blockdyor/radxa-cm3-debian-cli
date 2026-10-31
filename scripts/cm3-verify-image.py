#!/usr/bin/env python3
"""Read-only inspection of the actual external file-backed experimental CM3 image."""
import email.parser
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


assembly = module('cm3_assembly', 'cm3-assemble-image.py')
contract = module('cm3_contract', 'cm3-image-contract.py')
LABEL = 'EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION'


def compressed_digest(path):
    digest = hashlib.sha256()
    size = 0
    with lzma.open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def inventory(status, expected):
    rows = {}
    for paragraph in status.strip().split('\n\n'):
        item = email.parser.Parser().parsestr(paragraph)
        if item.get('Status') != 'install ok installed':
            raise ValueError('unconfigured or removed package in image')
        name = item['Package']
        if name in rows or item['Architecture'] not in ['arm64', 'all']:
            raise ValueError('duplicate or wrong-architecture package')
        if name.startswith(('task-', 'xserver-', 'gdm', 'lightdm', 'casaos', 'yunohost', 'docker')):
            raise ValueError('desktop/application platform package in CLI image')
        rows[name] = [item['Version'], item['Architecture'], 'installed']
    expected_rows = {fields[0]: fields[1:] for fields in (row.split('\t') for row in expected.splitlines())}
    if rows != expected_rows:
        raise ValueError('image inventory differs from authenticated configured rootfs')
    return ''.join(name + '\t' + '\t'.join(fields) + '\n' for name, fields in sorted(rows.items()))


def board_file(metadata, digest, expected, mode):
    if (not stat.S_ISREG(metadata['st_mode']) or metadata['st_uid'] != 0 or
            metadata['st_gid'] != 0 or stat.S_IMODE(metadata['st_mode']) != mode or digest != expected):
        raise ValueError('image board policy bytes, ownership or permissions changed')


def board_payload(guest):
    spec = importlib.util.spec_from_file_location('cm3_board', ROOT / 'packages/cm3-cli-board-support/build.py')
    board = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(board)
    sources = {name: board.HERE / 'root' / name for name in board.PAYLOAD}
    sources['usr/lib/cm3-cli/owner_config.py'] = ROOT / 'scripts/cm3-owner-config.py'
    sources['usr/share/doc/cm3-cli-board-support/README'] = board.HERE / 'README'
    sources['usr/share/doc/cm3-cli-board-support/copyright'] = ROOT / 'LICENSE'
    hashes = {}
    for name, source in sources.items():
        path = '/' + name
        mode = 0o755 if name in ['usr/lib/cm3-cli/enroll.py', 'usr/lib/cm3-cli/boot-update'] else 0o644
        expected = assembly.profile.probe.digest(assembly.regular(source))
        board_file(guest.lstatns(path), guest.checksum('sha256', path), expected, mode)
        hashes[path] = expected
    return hashes


def inspect(work):
    revision = assembly.boundary(work)
    assembly.experimental_admission(work, revision, os.environ['GITHUB_RUN_ID'])
    assembly.authenticate(work, revision, os.environ['GITHUB_RUN_ID'])
    result = json.loads(assembly.regular(work / 'evidence/image-assembly-result.json').read_text())
    raw = assembly.regular(work / 'image-output' / assembly.NAME)
    compressed = assembly.regular(Path(str(raw) + '.xz'))
    raw_hash = assembly.profile.probe.digest(raw)
    xz_hash = assembly.profile.probe.digest(compressed)
    if (result.get('status') != 'PASS' or result.get('source_revision') != revision or
            result.get('run_id') != os.environ['GITHUB_RUN_ID'] or
            result.get('image_sha256') != raw_hash or result.get('compressed_sha256') != xz_hash or
            result.get('image_bytes') != raw.stat().st_size or
            result.get('compressed_bytes') != compressed.stat().st_size or
            compressed_digest(compressed) != (raw_hash, raw.stat().st_size)):
        raise ValueError('actual raw/compressed bytes disagree with assembly identity')
    # --verify is file-only, not a repair command; require the positive diagnostic too.
    check = subprocess.check_output(['sgdisk', '--verify', str(raw)], text=True, stderr=subprocess.STDOUT)
    if 'No problems found.' not in check:
        raise ValueError('GPT verification did not pass: ' + check)
    import guestfs
    guest = guestfs.GuestFS(python_return_dict=True)
    guest.set_backend('direct')
    guest.set_backend_settings(['force_tcg'])
    guest.add_drive_opts(str(raw), readonly=1, format='raw')
    try:
        guest.launch()
        layout = contract.layout(guest.part_list('/dev/sda'), raw.stat().st_size,
                                 guest.blockdev_getss('/dev/sda'), guest.part_get_parttype('/dev/sda'))
        for part, kind in zip([1, 2, 3], ['vfat', 'vfat', 'ext4']):
            if guest.vfs_type('/dev/sda' + str(part)) != kind:
                raise ValueError('unexpected partition filesystem')
        uuids = [guest.vfs_uuid('/dev/sda' + str(part)) for part in [1, 2, 3]]
        guest.mount_ro('/dev/sda3', '/')
        def text(path):
            return guest.read_file(path).decode()
        boot = contract.boot(text('/boot/extlinux/extlinux.conf'), text('/etc/kernel/cmdline'),
                             text('/etc/fstab'), uuids)
        root = work / 'rsdk-profile-stage/root'
        hashes = {}
        for paths in boot['paths'].values():
            for path in paths:
                local = assembly.regular(root / path.lstrip('/'))
                digest = assembly.profile.probe.digest(local)
                if guest.checksum('sha256', path) != digest:
                    raise ValueError('image boot file differs from verified rootfs: ' + path)
                hashes[path] = digest
        if 'ID=debian' not in text('/etc/os-release').splitlines() or 'VERSION_CODENAME=trixie' not in text('/etc/os-release').splitlines():
            raise ValueError('image is not Debian Trixie')
        for path in ['/etc/machine-id', '/var/lib/dbus/machine-id', '/etc/cm3-cli/owner.json',
                     '/etc/apt/sources.list.d/cm3-build.list', '/usr/share/keyrings/cm3-build.gpg',
                     '/opt/cm3-repo', '/root/.ssh', '/usr/sbin/policy-rc.d']:
            if guest.exists(path):
                raise ValueError('image contains builder/owner identity, temporary trust or service-start mask: ' + path)
        for pattern in ['/etc/ssh/ssh_host_*', '/root/*key*', '/etc/apt/sources.list.d/*cm3*']:
            if guest.glob_expand(pattern):
                raise ValueError('image retained forbidden builder material')
        for row in text('/etc/shadow').splitlines():
            fields = row.split(':')
            if len(fields) < 2 or not fields[1].startswith(('!', '*')):
                raise ValueError('image contains an unlocked or password-bearing account')
        if guest.readlink('/etc/systemd/system/default.target') != '/usr/lib/systemd/system/multi-user.target':
            raise ValueError('CLI default target changed')
        for service in contract.SERVICE_LINKS:
            if not guest.is_symlink('/etc/systemd/system/' + service):
                raise ValueError('required service not enabled: ' + service)
        policy_hashes = board_payload(guest)
        packages = inventory(text('/var/lib/dpkg/status'),
                             (work / 'evidence/rsdk-profile-packages.tsv').read_text())
        # Loader offsets come from the actual pinned package's setup.sh, checked in tests.
        placements = [('idblock.img', 64 * 512), ('idblock.img', 136 * 4096),
                      ('u-boot.itb', 16384 * 512)]
        with raw.open('rb') as stream:
            for name, offset in placements:
                path = root / 'usr/lib/u-boot' / contract.PRODUCT / name
                payload = assembly.regular(path).read_bytes()
                if offset + len(payload) > 32768 * 512:
                    raise ValueError('loader overlaps first partition')
                stream.seek(offset)
                if stream.read(len(payload)) != payload:
                    raise ValueError('loader placement differs from exact pinned payload')
        guest.umount_all()
    finally:
        guest.close()
    output = raw.parent
    with (output / 'packages.tsv').open('x') as stream:
        stream.write(packages)
    report = dict(label=LABEL, status='PASS', source_revision=revision, run_id=os.environ['GITHUB_RUN_ID'],
                  image_sha256=raw_hash, compressed_sha256=xz_hash,
                  image_bytes=raw.stat().st_size, compressed_bytes=compressed.stat().st_size,
                  layout=layout, boot=boot, boot_file_sha256=hashes, board_policy_sha256=policy_hashes,
                  hardware='UNTESTED', services='UNTESTED', active_lsm='UNTESTED', stable_release='BLOCKED')
    with (output / 'verification.json').open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    with (output / 'SHA256SUMS').open('x') as stream:
        for path in [raw, compressed, output / 'packages.tsv', output / 'verification.json']:
            stream.write(assembly.profile.probe.digest(path) + '  ' + path.name + '\n')
    return report


def main():
    if len(sys.argv) != 1:
        raise SystemExit('no path arguments accepted; fixed external /work only')
    print(json.dumps(inspect(Path('/work')), indent=2))


if __name__ == '__main__':
    main()
