#!/usr/bin/env python3
"""EXPERIMENTAL: assemble the admitted CM3 profile with RSDK's existing guestfish route.

Only a disposable GitHub-hosted x86_64 root container may execute this entry point.
No host mounts/loop devices are used: /dev/sda in the generated recipe is the
libguestfs appliance's file-backed disk, not the runner's disk. Services, active
LSM, hardware boot and distinct-version rollback remain UNTESTED.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cm3_profile', ROOT / 'scripts/cm3-rsdk-profile.py')
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)
POLICY_SPEC = importlib.util.spec_from_file_location('cm3_stage_policy', ROOT / 'scripts/cm3-stage-policy.py')
policy = importlib.util.module_from_spec(POLICY_SPEC)
POLICY_SPEC.loader.exec_module(policy)
CONTRACT_SPEC = importlib.util.spec_from_file_location('cm3_contract', ROOT / 'scripts/cm3-image-contract.py')
contract = importlib.util.module_from_spec(CONTRACT_SPEC)
CONTRACT_SPEC.loader.exec_module(contract)
PRODUCT = 'radxa-cm3-rpi-cm4-io'
NAME = 'cm3-trixie-arm64-cli.img'


def command(*args, **kwargs):
    return subprocess.check_output([str(a) for a in args], text=True, **kwargs)


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode) or path.resolve() != path:
        raise ValueError('non-regular or redirected file: ' + str(path))
    return path


def boundary(work):
    if (work != Path('/work') or work.resolve() != work or
            os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'blockdyor/radxa-cm3-debian-cli' or
            os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted' or
            not Path('/.dockerenv').is_file() or platform.machine() != 'x86_64' or os.geteuid() != 0):
        raise ValueError('external GitHub-hosted x86_64 disposable root container /work only')
    revision = os.environ.get('GITHUB_SHA', '')
    if (re.fullmatch('[0-9a-f]{40}', revision) is None or
            os.environ.get('EXPECTED_SHA') != revision or
            not os.environ.get('GITHUB_RUN_ID', '').isdecimal()):
        raise ValueError('exact expected head and run required')
    git = ['git', '-c', 'safe.directory=' + str(ROOT), '-C', ROOT]
    if command(*git, 'rev-parse', 'HEAD').strip() != revision:
        raise ValueError('checkout differs from admitted head')
    subprocess.run([str(a) for a in git + ['diff', '--quiet', 'HEAD', '--']], check=True)
    return revision


def experimental_admission(work, revision, run_id):
    """Require same-run policy and budget receipts before touching the image."""
    admission = json.loads(regular(work / 'evidence/image-admission.json').read_text())
    if (admission.get('status') != 'ADMITTED' or
            admission.get('commit') != revision or str(admission.get('run_id')) != str(run_id) or
            admission.get('run_attempt') != 1 or admission.get('maximum_attempts') != 3 or
            type(admission.get('cumulative_attempts')) is not int or
            not 1 <= admission['cumulative_attempts'] <= 3):
        raise ValueError('same-run cumulative image admission required')
    stage = json.loads(regular(work / 'evidence/image-stage-a.json').read_text())
    if (stage.get('source_revision') != revision or str(stage.get('run_id')) != str(run_id) or
            stage.get('source_lock_sha256') != profile.probe.digest(ROOT / 'project/cm3-cli/source-lock.json')):
        raise ValueError('exact-head stage A evidence required')
    return policy.admit(stage.get('checks'))


def verify_installed_files(root, package, kernel):
    differences = profile.probe.chroot(root, 'dpkg', '--verify', capture=True)
    # The pinned bootutils hook decompresses only this kernel for Rockchip U-Boot.
    expected = ['??5??????', '/boot/vmlinuz-' + kernel]
    rows = [line.split() for line in differences.splitlines() if line.strip()]
    if rows not in [[], [expected]]:
        raise ValueError('profile installed file verification failed:\n' + differences)
    installed = regular(root / ('boot/vmlinuz-' + kernel))
    payload = None
    with subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(regular(package))],
                          stdout=subprocess.PIPE) as process:
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for member in archive:
                    if member.name.removeprefix('./') == 'boot/vmlinuz-' + kernel:
                        if payload is not None or not member.isfile() or not 0 < member.size <= 128 * 1024 * 1024:
                            raise ValueError('invalid authenticated kernel payload')
                        payload = archive.extractfile(member).read()
        except (ValueError, OSError, tarfile.TarError):
            process.kill()
            process.wait()
            raise
        if process.wait() != 0:
            raise ValueError('cannot inspect authenticated kernel package')
    if payload is None:
        raise ValueError('authenticated kernel payload absent')
    if payload.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
            payload = stream.read(128 * 1024 * 1024 + 1)
    if (len(payload) > 128 * 1024 * 1024 or payload[56:60] != b'ARMd' or
            profile.probe.digest(installed) != hashlib.sha256(payload).hexdigest()):
        raise ValueError('installed kernel differs from authenticated ARM64 Image transformation')


def authenticate(work, revision, run_id):
    # Re-run signature/index/payload/source/admission closure; a PASS label alone
    # is never sufficient. The original rootfs is reused, not bootstrapped again.
    receipt = profile.verified_receipt(work, revision, run_id)
    result_path = regular(work / 'evidence/rsdk-profile-result.json')
    result = json.loads(result_path.read_text())
    if (result.get('status') != 'PASS' or result.get('bootstrap') != 'PASS' or
            result.get('source_revision') != revision or result.get('receipt') != receipt or
            result.get('config_sha256') != profile.probe.digest(regular(work / 'evidence/rsdk-profile.json'))):
        raise ValueError('exact same-job authenticated RSDK profile PASS required')
    root = work / 'rsdk-profile-stage/root'
    if not root.is_dir() or root.resolve() != root:
        raise ValueError('unredirected existing RSDK root required')
    installed = profile.probe.chroot(root, 'dpkg-query', '-W',
                                     '-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n',
                                     capture=True)
    if installed != regular(work / 'evidence/rsdk-profile-packages.tsv').read_text():
        raise ValueError('profile package state changed')
    lock = profile.probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    kernel_package = next(name for name, (_, arch) in
                          profile.probe.source.expected_packages(lock).items()
                          if name.startswith('linux-image-') and arch == 'arm64')
    kernel = kernel_package.removeprefix('linux-image-')
    packages = profile.probe.inspect_inputs(work, lock)
    verify_installed_files(root, packages[kernel_package], kernel)
    if profile.probe.chroot(root, 'dpkg', '--audit', capture=True).strip():
        raise ValueError('profile package audit failed')
    # The distributable root has no host keys. A temporary explicit check key
    # permits sshd's offline parser checks without reintroducing builder identity.
    with tempfile.TemporaryDirectory(prefix='cm3-ssh-check-', dir=root / 'run') as temporary:
        key = '/' + str((Path(temporary) / 'key').relative_to(root))
        profile.probe.chroot(root, 'ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', key)
        profile.probe.verify_ssh_policy(root, host_key=key)

    profile.probe.source.verify_kernel_config(regular(root / ('boot/config-' + kernel)).read_text())
    profile.probe.verify_gzip_initramfs(regular(root / ('boot/initrd.img-' + kernel)))
    menu = regular(root / 'boot/extlinux/extlinux.conf').read_text()
    for required in ['console=ttyFIQ0,1500000n8', 'security=apparmor', 'apparmor=1',
                     'rockchip/rk3566-radxa-cm3-rpi-cm4-io.dtb',
                     'vmlinuz-' + kernel, 'initrd.img-' + kernel]:
        if required not in menu:
            raise ValueError('profile missing boot input: ' + required)
    for service in contract.SERVICE_LINKS:
        if not (root / 'etc/systemd/system' / service).is_symlink():
            raise ValueError('profile service not enabled: ' + service)
    for name in ['etc/machine-id', 'var/lib/dbus/machine-id', 'etc/cm3-cli/owner.json',
                 'etc/apt/sources.list.d/cm3-build.list', 'usr/share/keyrings/cm3-build.gpg',
                 'opt/cm3-repo', 'root/.ssh', 'usr/sbin/policy-rc.d']:
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError('profile retained builder identity/trust/start mask: ' + name)
    if list((root / 'etc/ssh').glob('ssh_host_*')):
        raise ValueError('profile retained builder SSH host keys')
    lock = profile.probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    if lock['target'] != dict(product=PRODUCT, soc='rk3566', suite='trixie', edition='cli',
                              architecture='arm64', sector_size=512):
        raise ValueError('exact locked image target required')
    return receipt


def render(work):
    output = work / 'image-output' / NAME
    temp = work / 'image-assembly-temp'
    if any(p.exists() or p.is_symlink() for p in [output.parent, temp]):
        raise ValueError('fresh output and assembly temp required')
    output.parent.mkdir()
    temp.mkdir()
    recipe = work / 'evidence/image-assembly.guestfish'
    args = ['jsonnet', '-S']
    for key, value in dict(product=PRODUCT, suite='trixie', output=str(output),
                           rootfs=str(work / 'rsdk-profile-stage/root'), temp_dir=str(temp)).items():
        args += ['--tla-str', key + '=' + value]
    # Keep the upstream partition/filesystem/loader implementation. No second
    # builder, tarball conversion, host mount or loop-device attachment.
    args += ['--tla-code', 'sector_size=512', '--tla-str', 'rootfs_type=ext4',
             str(ROOT / 'src/share/rsdk/build/image-ng.jsonnet')]
    text = command(*args)
    if ('disk-create "' + str(output) + '" raw ' not in text or
            'add-drive "' + str(output) + '" format:raw' not in text):
        raise ValueError('RSDK did not render the exact file-backed image')
    with recipe.open('x') as stream:
        stream.write(text)
    return output, temp, recipe


def assemble(work):
    revision = boundary(work)
    decision = experimental_admission(work, revision, os.environ['GITHUB_RUN_ID'])
    receipt = authenticate(work, revision, os.environ['GITHUB_RUN_ID'])
    evidence = work / 'evidence/image-assembly-result.json'
    # Reserve result before work: reruns must not overwrite earlier evidence.
    with evidence.open('x') as stream:
        status = dict(status='FAIL', stage='image-assembly', classification='EXPERIMENTAL',
                      source_revision=revision, run_id=os.environ['GITHUB_RUN_ID'],
                      services='UNTESTED', active_target_lsm='UNTESTED', hardware_boot='UNTESTED',
                      hardware_rollback='UNTESTED', receipt=receipt, admission=decision)
        output = None
        try:
            output, temp, recipe = render(work)
            env = dict(os.environ, LIBGUESTFS_BACKEND='direct',
                       LIBGUESTFS_BACKEND_SETTINGS='force_tcg')
            with (work / 'evidence/image-assembly.log').open('x') as log:
                subprocess.run(['guestfish', '-f', str(recipe)], env=env, check=True,
                               stdout=log, stderr=subprocess.STDOUT)
            regular(output)
            if output.stat().st_size <= 512 or output.stat().st_size % 512:
                raise ValueError('invalid raw image length')
            with output.open('rb') as image:
                image.seek(510)
                if image.read(2) != b'\x55\xaa':
                    raise ValueError('missing raw disk partition-table signature')
            subprocess.run(['xz', '--threads=2', '--keep', '--', str(output)], check=True)
            compressed = regular(Path(str(output) + '.xz'))
            subprocess.run(['xz', '--test', '--', str(compressed)], check=True)
            status.update(status='PASS', image_build='PASS',
                          image=str(output), image_sha256=profile.probe.digest(output),
                          compressed_image=str(compressed), compressed_sha256=profile.probe.digest(compressed),
                          image_bytes=output.stat().st_size, compressed_bytes=compressed.stat().st_size,
                          recipe_sha256=profile.probe.digest(recipe),
                          validation='partition signature and xz integrity only; independent validator required')
        finally:
            # guestfish owns/tears down its appliance on exit; it never attaches a
            # host loop device. Preserve failed bytes/logs for diagnosis, never PASS.
            stream.write(json.dumps(status, indent=2) + '\n')
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    try:
        status = assemble(args.workdir)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
