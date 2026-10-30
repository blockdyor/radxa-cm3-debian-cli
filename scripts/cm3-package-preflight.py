#!/usr/bin/env python3
"""Signed BSP install/DKMS probe in an external disposable ARM64 chroot, not an image."""

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('source_preflight', ROOT / 'scripts/cm3-source-preflight.py')
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
DTB = 'rk3566-radxa-cm3-rpi-cm4-io.dtb'
# Original 33 seeds, except the standalone vendor ttyFIQ0 configuration package.
# The separately verified board package supplies boot/security policy.
SEEDS = '''apt debian-archive-keyring ca-certificates systemd-sysv udev dbus kmod
initramfs-tools u-boot-menu openssh-server sudo adduser passwd iproute2 iputils-ping
network-manager wpasupplicant iw wireless-regdb systemd-timesyncd nftables e2fsprogs
dosfstools util-linux tzdata locales less nano pciutils usbutils radxa-bootutils
radxa-udev'''.split()
TOOLS = '''apparmor apparmor-profiles firmware-brcm80211 firmware-realtek dkms gcc
make libc6-dev libssl-dev libelf-dev device-tree-compiler file python3 gzip'''.split()


def command(*args, cwd=None, capture=False):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_manifest(manifest, expected):
    if set(manifest) != set(expected):
        raise ValueError('exact package manifest required')
    for name, (version, arch) in expected.items():
        item = manifest[name]
        if ((item['version'], item['architecture']) != (version, arch) or
                re.fullmatch(r'[0-9a-f]{64}', item['sha256']) is None):
            raise ValueError('package manifest identity/hash mismatch')


def inspect_inputs(work, lock):
    expected = source.expected_packages(lock)
    manifest = json.loads((work / 'evidence/bsp-manifest.json').read_text())
    verify_manifest(manifest, expected)
    found = {}
    files = sorted((work / 'selected-debs').iterdir())
    for path in files:
        if path.is_symlink() or not path.is_file() or path.suffix != '.deb':
            raise ValueError('only regular selected debs allowed')
        fields = command('dpkg-deb', '--show', '--showformat=${Package}\t${Version}\t${Architecture}',
                         path, capture=True).split('\t')
        name, version, arch = fields
        if name not in expected or (version, arch) != expected[name] or name in found:
            raise ValueError('unreviewed or duplicate package input')
        if digest(path) != manifest[name]['sha256']:
            raise ValueError('selected package hash changed')
        found[name] = path
    if set(found) != set(expected):
        raise ValueError('incomplete selected package closure')
    return found


def inspect_board_input(work, revision):
    """Admit the configuration package separately; never widen the BSP lock."""
    manifest = json.loads((work / 'evidence/board-manifest.json').read_text())
    expected = {'cm3-cli-board-support': ('0.1.0', 'all')}
    verify_manifest(manifest['packages'], expected)
    if (re.fullmatch('[0-9a-f]{40}', revision) is None or
            manifest['source_revision'] != revision or
            manifest['source_lock_sha256'] != digest(ROOT / 'project/cm3-cli/source-lock.json') or
            type(manifest['source_date_epoch']) is not int or manifest['source_date_epoch'] < 0):
        raise ValueError('board source provenance mismatch')
    files = list((work / 'board-debs').iterdir())
    if (len(files) != 1 or files[0].is_symlink() or not files[0].is_file() or
            files[0].name != 'cm3-cli-board-support_0.1.0_all.deb'):
        raise ValueError('exact regular board package required')
    path = files[0]
    identity = command('dpkg-deb', '--show', '--showformat=${Package}\t${Version}\t${Architecture}',
                       path, capture=True)
    if (identity != 'cm3-cli-board-support\t0.1.0\tall' or
            digest(path) != manifest['packages']['cm3-cli-board-support']['sha256']):
        raise ValueError('board package identity/hash mismatch')
    with tempfile.TemporaryDirectory(prefix='cm3-board-inspect-') as directory:
        command('dpkg-deb', '--extract', path, directory)
        provenance = json.loads((Path(directory) / 'usr/share/doc/cm3-cli-board-support/source.json').read_text())
    for field in ['source_revision', 'source_date_epoch', 'source_lock_sha256']:
        if provenance[field] != manifest[field]:
            raise ValueError('embedded board provenance mismatch')
    if provenance['target'] != 'radxa-cm3-rpi-cm4-io':
        raise ValueError('board target mismatch')
    return {'cm3-cli-board-support': path}


def signed_repo(packages, destination, keyhome, evidence):
    destination.mkdir()
    pool = destination / 'pool'
    pool.mkdir()
    for path in packages.values():
        shutil.copyfile(path, pool / path.name)
    (destination / 'Packages').write_text(command('apt-ftparchive', 'packages', 'pool',
                                                cwd=destination, capture=True))
    release = command('apt-ftparchive', '-o', 'APT::FTPArchive::Release::Origin=CM3-CLI-Experiment',
                      '-o', 'APT::FTPArchive::Release::Label=CM3-CLI-Experiment',
                      '-o', 'APT::FTPArchive::Release::Architectures=arm64 all',
                      'release', '.', cwd=destination, capture=True)
    (destination / 'Release').write_text(release)
    command('gpg', '--homedir', keyhome, '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
            '--quick-generate-key', 'CM3 disposable preflight <noreply@users.noreply.github.com>',
            'ed25519', 'sign', '1d')
    listing = command('gpg', '--homedir', keyhome, '--batch', '--with-colons', '--fingerprint',
                      capture=True)
    fingerprints = [line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')]
    if len(fingerprints) != 1 or re.fullmatch(r'[0-9A-F]{40}', fingerprints[0]) is None:
        raise ValueError('unexpected disposable signing key')
    fingerprint = fingerprints[0]
    command('gpg', '--homedir', keyhome, '--batch', '--output', destination / 'archive-key.gpg',
            '--export', fingerprint)
    for output, mode in [('InRelease', '--clearsign'), ('Release.gpg', '--detach-sign')]:
        command('gpg', '--homedir', keyhome, '--batch', '--local-user', fingerprint,
                '--output', destination / output, mode, destination / 'Release')
    command('gpgv', '--keyring', destination / 'archive-key.gpg', destination / 'InRelease')
    (evidence / 'local-repository.json').write_text(json.dumps({
        'origin': 'CM3-CLI-Experiment', 'fingerprint': fingerprint,
        'trust': 'ephemeral job-only key; no cross-job update trust asserted',
        'inrelease_sha256': digest(destination / 'InRelease'),
        'packages_sha256': digest(destination / 'Packages'),
        'private_key_retained': False,
    }, indent=2) + '\n')


def put(root, relative, text, mode=0o644):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def chroot(root, *args, capture=False):
    return command('chroot', root, 'env', 'DEBIAN_FRONTEND=noninteractive', *args, capture=capture)


def apt(root, *args, capture=False):
    return chroot(root, 'apt-get', '-o', 'APT::Update::Error-Mode=any',
                  '-o', 'APT::Install-Recommends=false', '-o', 'APT::Install-Suggests=false',
                  *args, capture=capture)


@contextmanager
def prepare_target(work, evidence):
    root = work / 'arm64-root'
    command('mmdebstrap', '--architectures=arm64', '--variant=minbase', '--include=ca-certificates',
            '--aptopt=APT::Install-Recommends "false"',
            '--aptopt=APT::Install-Suggests "false"',
            'trixie', root,
            'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main non-free-firmware',
            'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie-updates main non-free-firmware',
            'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://security.debian.org/debian-security trixie-security main non-free-firmware')
    # mmdebstrap does not leave pseudo-filesystems mounted after returning.
    # These mounts exist only in the disposable container; never bind host /dev.
    mounts = []
    try:
        for name, kind in [('proc', 'proc'), ('sys', 'sysfs'), ('dev', 'tmpfs')]:
            path = root / name
            command('mount', '-t', kind, kind, path)
            mounts.append(path)
        for name, major, minor in [('null', 1, 3), ('zero', 1, 5), ('random', 1, 8), ('urandom', 1, 9)]:
            command('mknod', '-m', '666', root / 'dev' / name, 'c', major, minor)
        put(root, 'usr/sbin/policy-rc.d', '#!/bin/sh\nexit 101\n', 0o755)
        put(root, 'etc/apt/apt.conf.d/99cm3-preflight',
            'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n')
        if chroot(root, 'dpkg', '--print-architecture', capture=True).strip() != 'arm64':
            raise ValueError('target is not ARM64')
        # A fixture OS root, never a real disk or the builder root from /proc/cmdline.
        put(root, 'etc/fstab', 'UUID=11111111-1111-4111-8111-111111111111 / ext4 defaults 0 1\n')

        repo = root / 'opt/cm3-repo'
        shutil.copytree(work / 'signed-repository', repo)
        shutil.copyfile(repo / 'archive-key.gpg', root / 'usr/share/keyrings/cm3-preflight.gpg')
        put(root, 'etc/apt/sources.list.d/cm3-preflight.list',
            'deb [signed-by=/usr/share/keyrings/cm3-preflight.gpg] file:/opt/cm3-repo ./\n')
        apt(root, 'update')
        good = (repo / 'InRelease').read_bytes()
        (repo / 'InRelease').write_bytes(good.replace(b'CM3-CLI-Experiment', b'CM3-CLI-Tampered!!', 1))
        if (repo / 'InRelease').read_bytes() == good:
            raise ValueError('tamper fixture did not modify signed metadata')
        # Force verification rather than an unchanged-size/mtime cache hit.
        for path in (root / 'var/lib/apt/lists').glob('*cm3-repo*'):
            if path.is_file():
                path.unlink()
        failed = subprocess.run(['chroot', str(root), 'apt-get', '-o', 'APT::Update::Error-Mode=any',
                                 'update'], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (evidence / 'tampered-apt-update.txt').write_text(failed.stdout)
        if failed.returncode == 0 or not re.search(r'BADSIG|bad signature|signature.*(?:invalid|failed)|not signed',
                                                  failed.stdout, re.I):
            raise ValueError('tampered local repository was not rejected for its signature')
        (repo / 'InRelease').write_bytes(good)
        apt(root, 'update')
        yield root
    finally:
        for path in reversed(mounts):
            command('umount', path)


def verify_gzip_initramfs(path):
    """Check compression/integrity and main newc magic, not complete cpio contents."""
    # Debian 0.148.4 prepends newc archives for already-compressed modules/firmware.
    with path.open('rb') as stream:
        size = path.stat().st_size
        early_archives = 0
        while True:
            start = stream.tell()
            magic = stream.read(6)
            stream.seek(start)
            if magic.startswith(b'\x1f\x8b'):
                break
            if magic != b'070701':
                raise ValueError('initramfs requires newc prefixes followed by gzip')
            while True:
                header = stream.read(110)
                if (len(header) != 110 or header[:6] != b'070701' or
                        re.fullmatch(b'[0-9a-fA-F]{104}', header[6:]) is None):
                    raise ValueError('invalid early initramfs newc header')
                length = int(header[94:102], 16)
                payload = int(header[54:62], 16)
                if not 1 <= length <= 4096:
                    raise ValueError('invalid early initramfs name length')
                name = stream.read(length)
                if len(name) != length or name[-1:] != b'\0' or b'\0' in name[:-1]:
                    raise ValueError('invalid early initramfs name')
                end = (stream.tell() + 3) & ~3
                end = (end + payload + 3) & ~3
                if end > size:
                    raise ValueError('truncated early initramfs payload')
                stream.seek(end)
                if name == b'TRAILER!!!\0':
                    if payload:
                        raise ValueError('invalid early initramfs trailer')
                    break
            early_archives += 1
            # cpio may pad archives to a block boundary before the next archive.
            while True:
                byte = stream.read(1)
                if not byte:
                    raise ValueError('initramfs has no gzip main archive')
                if byte != b'\0':
                    stream.seek(-1, os.SEEK_CUR)
                    break
        offset = stream.tell()
        with gzip.GzipFile(fileobj=stream) as compressed:
            if compressed.read(6) != b'070701':
                raise ValueError('gzip initramfs main archive is not newc')
            while compressed.read(1024 * 1024):
                pass  # Read through EOF to validate gzip CRC and truncation.
    return {'compression': 'gzip', 'main_offset': offset,
            'early_archives': early_archives, 'gzip_integrity': 'PASS'}


def install_board_policy(root, board):
    # APT authenticates and copies even file:// inputs; no dependency configure yet.
    chroot(root, 'sh', '-ec', 'cd /var/cache/apt/archives; exec apt-get download cm3-cli-board-support=0.1.0')
    cached = root / 'var/cache/apt/archives/cm3-cli-board-support_0.1.0_all.deb'
    if not cached.is_file() or cached.is_symlink() or digest(cached) != digest(board):
        raise ValueError('authenticated board download differs from admitted input')
    chroot(root, 'dpkg', '--unpack', '/' + str(cached.relative_to(root)))
    mask = root / 'etc/kernel/install.d/99-update-overlay.install'
    if not mask.is_symlink() or os.readlink(mask) != '/dev/null':
        raise ValueError('board-owned overlay mask missing before kernel configuration')
    chroot(root, 'dpkg-query', '-S', '/etc/kernel/install.d/99-update-overlay.install')


def verify_ssh_policy(root, host_key=None):
    (root / 'run/sshd').mkdir(mode=0o755, exist_ok=True)
    options = ['-h', host_key] if host_key is not None else []
    chroot(root, 'sshd', '-t', *options)
    ssh = chroot(root, 'sshd', '-T', *options, capture=True)
    for setting in ['permitrootlogin no', 'passwordauthentication no',
                    'kbdinteractiveauthentication no', 'authenticationmethods publickey',
                    'allowgroups cm3-cli-owner']:
        if setting not in ssh.splitlines():
            raise ValueError('effective SSH policy mismatch: ' + setting)


def test_target(root, lock, evidence, board):
    expected = source.expected_packages(lock)
    kernel = next(name.removeprefix('linux-image-') for name, (_, arch) in expected.items()
                  if name.startswith('linux-image-') and arch == 'arm64')
    apt(root, 'install', '-y', *SEEDS, *TOOLS)
    headers = [f'{name}={version}' for name, (version, _) in expected.items()
               if name.startswith('linux-headers-')]
    apt(root, 'install', '-y', *headers)
    install_board_policy(root, board)
    expected = dict(expected, **{'cm3-cli-board-support': ('0.1.0', 'all')})
    apt(root, 'install', '-y', *[f'{name}={version}' for name, (version, _) in expected.items()])
    for name, (version, arch) in expected.items():
        actual = chroot(root, 'dpkg-query', '-W', '-f=${Version}\t${Architecture}\t${db:Status-Status}',
                        name, capture=True).strip()
        if actual != f'{version}\t{arch}\tinstalled':
            raise ValueError('package not fully configured: ' + name)
    verify_ssh_policy(root)
    (evidence / 'ssh-policy.json').write_text(json.dumps({
        'effective_sshd_policy': 'PASS', 'service_started': False,
    }, indent=2) + '\n')
    dtb = root / f'usr/lib/linux-image-{kernel}/rockchip/{DTB}'
    if not dtb.is_file():
        raise ValueError('missing exact-carrier DTB')
    compatible = chroot(root, 'fdtget', '/' + str(dtb.relative_to(root)), '/', 'compatible', capture=True)
    if 'radxa,cm3-rpi-cm4-io' not in compatible or 'rockchip,rk3566' not in compatible:
        raise ValueError('wrong carrier/SoC DTB compatible')
    loader = root / 'usr/lib/u-boot/radxa-cm3-rpi-cm4-io/setup.sh'
    if not loader.is_file():
        raise ValueError('missing exact-carrier loader setup (never executed)')
    helper = root / f'usr/src/linux-headers-{kernel}/scripts/basic/fixdep'
    elf = command('readelf', '-h', helper, capture=True)
    if not re.search(r'Machine:\s+AArch64', elf):
        raise ValueError('installed header helper is not native ARM64')
    (evidence / 'header-helper-elf.txt').write_text(elf)
    overlay_version = expected['radxa-overlays-dkms'][0]
    chroot(root, 'dkms', 'autoinstall', '-k', kernel)
    status = chroot(root, 'dkms', 'status', '-m', 'radxa-overlays', '-v', overlay_version,
                    '-k', kernel, capture=True)
    (evidence / 'dkms-status.txt').write_text(status)
    if 'installed' not in status:
        raise ValueError('real overlay dummy module not installed by DKMS')
    modules = list((root / f'lib/modules/{kernel}/updates/dkms').glob('radxa-overlays.ko*'))
    overlays = list((root / f'var/lib/dkms/radxa-overlays/{overlay_version}').rglob('*.dtbo'))
    if len(modules) != 1 or not overlays:
        raise ValueError('missing real dummy kernel module or DTBO output')
    chroot(root, 'modinfo', '-k', kernel, 'radxa-overlays')
    chroot(root, 'update-initramfs', '-u', '-k', kernel)
    initramfs = verify_gzip_initramfs(root / f'boot/initrd.img-{kernel}')
    (evidence / 'initramfs-format.json').write_text(json.dumps(initramfs, indent=2) + '\n')
    config = (root / f'boot/config-{kernel}').read_text()
    source.verify_kernel_config(config)
    chroot(root, 'u-boot-update')
    menu = root / 'boot/extlinux/extlinux.conf'
    before = menu.read_bytes()
    text = before.decode()
    for required in [f'linux-image-{kernel}/rockchip/{DTB}', 'console=ttyFIQ0,1500000n8',
                     'apparmor=1', 'security=apparmor', '11111111-1111-4111-8111-111111111111',
                     f'initrd.img-{kernel}', f'vmlinuz-{kernel}']:
        if required not in text:
            raise ValueError('missing expected boot fixture input: ' + required)
    if 'fdtoverlays' in text:
        raise ValueError('unexpected enabled overlay')
    chroot(root, 'u-boot-update')
    if menu.read_bytes() != before:
        raise ValueError('unchanged boot fixture generation is not idempotent')
    # Reconfiguration/reinstallation is not claimed as a distinct-version BSP upgrade.
    apt(root, 'install', '--reinstall', '-y', *[f'{name}={version}' for name, (version, _) in expected.items()])
    apt(root, 'upgrade', '-y')
    chroot(root, 'dpkg', '--configure', '-a')
    audit = chroot(root, 'dpkg', '--audit', capture=True)
    if audit.strip():
        raise ValueError('dpkg audit is not clean: ' + audit)
    (evidence / 'target-packages.tsv').write_text(chroot(
        root, 'dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\t${Essential}\t${db:Status-Status}\n', capture=True))
    (evidence / 'target-origins.txt').write_text(chroot(root, 'apt-cache', 'policy', *SEEDS, *TOOLS,
                                                      *expected, capture=True))
    (evidence / 'extlinux-fixture.conf').write_text(menu.read_text())
    (evidence / 'dtb-loader.json').write_text(json.dumps({
        'kernel': kernel, 'compatible': compatible.strip(), 'dtb_sha256': digest(dtb),
        'loader_setup_sha256': digest(loader), 'loader_executed': False,
        'dummy_module_count': len(modules), 'dtbo_count': len(overlays),
        'active_lsm': 'NOT TESTED: chroot is not a target kernel boot',
        'distinct_version_bsp_upgrade': 'NOT TESTED: reinstall only',
        'board_support': 'authenticated package configuration; services/boot NOT TESTED',
    }, indent=2) + '\n')
    for path in (root / 'var/lib/apt/lists').glob('*InRelease'):
        shutil.copyfile(path, evidence / ('target-' + path.name))
    # Exercise DKMS removal and reinstall, without running loader/media scripts.
    apt(root, 'remove', '-y', 'radxa-overlays-dkms')
    # Removal also removes the dependent image alias; restore the entire whitelist.
    install_board_policy(root, board)
    apt(root, 'install', '-y', *[f'{name}={version}' for name, (version, _) in expected.items()])
    chroot(root, 'dkms', 'autoinstall', '-k', kernel)
    if chroot(root, 'dpkg', '--audit', capture=True).strip():
        raise ValueError('dpkg audit after removal/reinstall is not clean')
    for name, (version, arch) in expected.items():
        actual = chroot(root, 'dpkg-query', '-W', '-f=${Version}\t${Architecture}\t${db:Status-Status}',
                        name, capture=True).strip()
        if actual != f'{version}\t{arch}\tinstalled':
            raise ValueError('whitelist not restored after removal: ' + name)
    # Exercise the real removal fail-closed policy and purge, without starting SSH.
    apt(root, 'remove', '-y', 'cm3-cli-board-support')
    denial = root / 'etc/ssh/sshd_config.d/00-cm3-cli-removed.conf'
    if denial.read_text() != 'DenyUsers *\n':
        raise ValueError('board removal did not leave SSH closed')
    apt(root, 'purge', '-y', 'cm3-cli-board-support')
    if not denial.is_file() or (root / 'etc/sudoers.d/cm3-cli-owner').exists():
        raise ValueError('board purge did not preserve fail-closed SSH policy')
    install_board_policy(root, board)
    apt(root, 'install', '-y', 'cm3-cli-board-support=0.1.0')
    if denial.exists() or chroot(root, 'dpkg', '--audit', capture=True).strip():
        raise ValueError('board package not cleanly restored after purge')
    if chroot(root, 'dpkg-query', '-W', '-f=${Version}\t${Architecture}\t${db:Status-Status}',
              'cm3-cli-board-support', capture=True).strip() != '0.1.0\tall\tinstalled':
        raise ValueError('board package not configured after purge/restore')
    verify_ssh_policy(root)
    chroot(root, 'u-boot-update')
    if menu.read_bytes() != before:
        raise ValueError('boot policy changed after board purge/restore')
    verify_gzip_initramfs(root / f'boot/initrd.img-{kernel}')
    (evidence / 'board-lifecycle.json').write_text(json.dumps({
        'package': 'cm3-cli-board-support', 'version': '0.1.0',
        'configure_reinstall_remove_purge_restore': 'PASS',
        'service_execution': 'NOT TESTED: policy-rc.d denies starts; no target boot',
        'owner_enrollment': 'NOT TESTED: no owner credentials in this fixture',
    }, indent=2) + '\n')
    (root / 'etc/apt/sources.list.d/cm3-preflight.list').unlink()
    (root / 'usr/share/keyrings/cm3-preflight.gpg').unlink()
    apt(root, 'update')
    (evidence / 'target-packages.tsv').write_text(chroot(
        root, 'dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\t${Essential}\t${db:Status-Status}\n', capture=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'blockdyor/radxa-cm3-debian-cli' or
            platform.machine() != 'x86_64' or os.geteuid() != 0):
        parser.error('restricted to external disposable AMD64 CI container')
    work = args.workdir
    if not work.is_absolute() or work.resolve() != Path('/work'):
        parser.error('only the existing disposable /work package directory is allowed')
    lock = source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    result = json.loads((work / 'evidence/result.json').read_text())
    if result['status'] != 'PASS':
        parser.error('successful source build in this job is required')
    admission = json.loads((ROOT / 'preflight-work/evidence/package-admission.json').read_text())
    if (admission['status'] != 'ADMITTED' or admission['maximum_attempts'] is not None or
            admission.get('authorization') != 'owner-2026-10-29-evidence-based-development' or
            admission['cumulative_attempts'] < 1 or
            str(admission['run_id']) != os.environ.get('GITHUB_RUN_ID') or
            admission['commit'] != os.environ.get('GITHUB_SHA')):
        parser.error('missing matching cumulative package admission')
    evidence = work / 'evidence'
    started = time.time()
    status = {'stage': 'signed-arm64-install-dkms', 'status': 'FAIL',
              'full_package_preflight': 'NOT COMPLETE', 'image_build': 'NOT RUN'}
    try:
        packages = inspect_inputs(work, lock)
        board = inspect_board_input(work, os.environ['GITHUB_SHA'])
        packages.update(board)
        command('apt-get', 'install', '--no-install-recommends', '-y', 'apt-utils', 'gnupg',
                'gpgv', 'mmdebstrap', 'arch-test', 'debian-archive-keyring', 'mount')
        # Private key lives outside /work and all upload paths, and is always deleted.
        with tempfile.TemporaryDirectory(prefix='cm3-key-') as keydir:
            Path(keydir).chmod(0o700)
            signed_repo(packages, work / 'signed-repository', keydir, evidence)
        with prepare_target(work, evidence) as root:
            test_target(root, lock, evidence, board['cm3-cli-board-support'])
        status['status'] = 'PASS'
    finally:
        status['elapsed_seconds'] = round(time.time() - started, 2)
        (evidence / 'arm64-result.json').write_text(json.dumps(status, indent=2) + '\n')


if __name__ == '__main__':
    main()
