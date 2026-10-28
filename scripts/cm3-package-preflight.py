#!/usr/bin/env python3
"""Signed BSP install/DKMS probe in an external disposable ARM64 chroot, not an image."""

import argparse
from contextlib import contextmanager
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
# Its replacement board-support package is a later gate, not faked by this fixture.
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
        raise ValueError('exact nine-package manifest required')
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
        # Use u-boot-menu's supported fragment; do not pre-create its dpkg conffile.
        put(root, 'etc/u-boot-menu/conf.d/99-cm3-preflight.conf',
            'U_BOOT_PARAMETERS="ro console=ttyFIQ0,1500000n8 apparmor=1 security=apparmor"\n'
            f'U_BOOT_FDT="rockchip/{DTB}"\nU_BOOT_FDT_DIR="/usr/lib/linux-image-"\n'
            'U_BOOT_FDT_OVERLAYS_DIR="/boot/cm3-no-enabled-overlays/"\n')
        put(root, 'etc/initramfs-tools/conf.d/cm3-gzip', 'COMPRESS=gzip\n')
        # Avoid running-host board detection and systemd-boot entry mutation in this fixture.
        # The final board-support package must own this override before image enablement.
        put(root, 'etc/kernel/install.d/99-update-overlay.install', '#!/bin/sh\nexit 0\n', 0o755)
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


def test_target(root, lock, evidence):
    expected = source.expected_packages(lock)
    kernel = next(name.removeprefix('linux-image-') for name, (_, arch) in expected.items()
                  if name.startswith('linux-image-') and arch == 'arm64')
    apt(root, 'install', '-y', *SEEDS, *TOOLS)
    headers = [f'{name}={version}' for name, (version, _) in expected.items()
               if name.startswith('linux-headers-')]
    apt(root, 'install', '-y', *headers)
    apt(root, 'install', '-y', *[f'{name}={version}' for name, (version, _) in expected.items()])
    for name, (version, arch) in expected.items():
        actual = chroot(root, 'dpkg-query', '-W', '-f=${Version}\t${Architecture}\t${db:Status-Status}',
                        name, capture=True).strip()
        if actual != f'{version}\t{arch}\tinstalled':
            raise ValueError('package not fully configured: ' + name)
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
    with (root / f'boot/initrd.img-{kernel}').open('rb') as stream:
        if stream.read(2) != b'\x1f\x8b':
            raise ValueError('initramfs is not gzip compressed')
    config = (root / f'boot/config-{kernel}').read_text()
    for setting in ['CONFIG_BLK_DEV_INITRD=y', 'CONFIG_SECURITY_APPARMOR=y', 'CONFIG_MODULES=y']:
        if setting not in config.splitlines():
            raise ValueError('required kernel support absent: ' + setting)
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
        'board_support': 'NOT IMPLEMENTED: boot configuration is a test fixture',
    }, indent=2) + '\n')
    for path in (root / 'var/lib/apt/lists').glob('*InRelease'):
        shutil.copyfile(path, evidence / ('target-' + path.name))
    # Exercise DKMS removal and reinstall, without running loader/media scripts.
    apt(root, 'remove', '-y', 'radxa-overlays-dkms')
    # Removal also removes the dependent image alias; restore the entire whitelist.
    apt(root, 'install', '-y', *[f'{name}={version}' for name, (version, _) in expected.items()])
    chroot(root, 'dkms', 'autoinstall', '-k', kernel)
    if chroot(root, 'dpkg', '--audit', capture=True).strip():
        raise ValueError('dpkg audit after removal/reinstall is not clean')
    for name, (version, arch) in expected.items():
        actual = chroot(root, 'dpkg-query', '-W', '-f=${Version}\t${Architecture}\t${db:Status-Status}',
                        name, capture=True).strip()
        if actual != f'{version}\t{arch}\tinstalled':
            raise ValueError('whitelist not restored after removal: ' + name)
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
    if (admission['status'] != 'ADMITTED' or admission['maximum_attempts'] != 6 or
            admission['cumulative_attempts'] > 6 or
            str(admission['run_id']) != os.environ.get('GITHUB_RUN_ID') or
            admission['commit'] != os.environ.get('GITHUB_SHA')):
        parser.error('missing matching cumulative package admission')
    evidence = work / 'evidence'
    started = time.time()
    status = {'stage': 'signed-arm64-install-dkms', 'status': 'FAIL',
              'full_package_preflight': 'NOT COMPLETE', 'image_build': 'NOT RUN'}
    try:
        packages = inspect_inputs(work, lock)
        command('apt-get', 'install', '--no-install-recommends', '-y', 'apt-utils', 'gnupg',
                'gpgv', 'mmdebstrap', 'arch-test', 'debian-archive-keyring', 'mount')
        # Private key lives outside /work and all upload paths, and is always deleted.
        with tempfile.TemporaryDirectory(prefix='cm3-key-') as keydir:
            Path(keydir).chmod(0o700)
            signed_repo(packages, work / 'signed-repository', keydir, evidence)
        with prepare_target(work, evidence) as root:
            test_target(root, lock, evidence)
        status['status'] = 'PASS'
    finally:
        status['elapsed_seconds'] = round(time.time() - started, 2)
        (evidence / 'arm64-result.json').write_text(json.dumps(status, indent=2) + '\n')


if __name__ == '__main__':
    main()
