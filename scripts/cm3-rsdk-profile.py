#!/usr/bin/env python3
"""Test the exact signed CM3 RSDK profile in a disposable directory, never a disk image."""
import argparse
import email.parser
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('package_probe', ROOT / 'scripts/cm3-package-preflight.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def verify_repository(repo, packages, fingerprint):
    """Check authenticated index-to-payload closure before staging the signed bytes."""
    if re.fullmatch('[0-9A-F]{40}', fingerprint) is None:
        raise ValueError('exact signing fingerprint required')
    expected_names = {'pool', 'Packages', 'Release', 'InRelease', 'Release.gpg', 'archive-key.gpg'}
    if {p.name for p in repo.iterdir()} != expected_names:
        raise ValueError('unexpected signed repository contents')
    if any(p.is_symlink() for p in repo.rglob('*')):
        raise ValueError('repository symlinks prohibited')
    with tempfile.TemporaryDirectory(prefix='cm3-verify-') as home:
        signed = subprocess.run(['gpgv', '--homedir', home, '--status-fd=2',
                                 '--keyring', str(repo / 'archive-key.gpg'),
                                 '--output', '-', str(repo / 'InRelease')], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not re.search(r'^\[GNUPG:\] VALIDSIG ' + fingerprint + r' ', signed.stderr, re.M):
        raise ValueError('unexpected repository signer')
    if signed.stdout != (repo / 'Release').read_text():
        raise ValueError('signed release differs from retained release')
    release = email.parser.Parser().parsestr(signed.stdout)
    hashes = [line.split() for line in release.get('SHA256', '').splitlines() if line.strip()]
    indexes = [row for row in hashes if len(row) == 3 and row[2] == 'Packages']
    if indexes != [[probe.digest(repo / 'Packages'), str((repo / 'Packages').stat().st_size), 'Packages']]:
        raise ValueError('authenticated Packages hash mismatch')
    found = {}
    for paragraph in (repo / 'Packages').read_text().strip().split('\n\n'):
        item = email.parser.Parser().parsestr(paragraph)
        name = item['Package']
        if name not in packages or name in found:
            raise ValueError('unexpected or duplicate repository package')
        path = packages[name]
        expected = probe.command('dpkg-deb', '--show', '--showformat=${Version}\t${Architecture}',
                                 '--', path, capture=True).split('\t')
        if ([item['Version'], item['Architecture']] != expected or
                item['Filename'] != 'pool/' + path.name or
                item['SHA256'] != probe.digest(path) or
                item['Size'] != str(path.stat().st_size)):
            raise ValueError('repository package identity/hash mismatch')
        if probe.digest(repo / item['Filename']) != item['SHA256']:
            raise ValueError('repository payload hash mismatch')
        found[name] = path.name
    if set(found) != set(packages) or {p.name for p in (repo / 'pool').iterdir()} != set(found.values()):
        raise ValueError('incomplete repository closure')


def verified_receipt(work, revision, run_id):
    admission = json.loads((ROOT / 'preflight-work/evidence/package-admission.json').read_text())
    if (re.fullmatch('[0-9a-f]{40}', revision) is None or not str(run_id).isdecimal() or
            admission['status'] != 'ADMITTED' or admission['commit'] != revision or
            admission['maximum_attempts'] is not None or admission['cumulative_attempts'] < 1 or
            admission.get('authorization') != 'owner-2026-10-29-evidence-based-development' or
            str(admission['run_id']) != str(run_id)):
        raise ValueError('same-job admission required')
    for name in ['result.json', 'arm64-result.json']:
        result = json.loads((work / 'evidence' / name).read_text())
        if result['status'] != 'PASS' or result['image_build'] != 'NOT RUN':
            raise ValueError('same-job source and signed ARM64 checks must pass')
    lifecycle = json.loads((work / 'evidence/board-lifecycle.json').read_text())
    if lifecycle['configure_reinstall_remove_purge_restore'] != 'PASS':
        raise ValueError('board lifecycle preflight required')
    lock = probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    packages = probe.inspect_inputs(work, lock)
    board = probe.inspect_board_input(work, revision)
    packages.update(board)
    signing = json.loads((work / 'evidence/local-repository.json').read_text())
    verify_repository(work / 'signed-repository', packages, signing['fingerprint'])
    if (signing['inrelease_sha256'] != probe.digest(work / 'signed-repository/InRelease') or
            signing['packages_sha256'] != probe.digest(work / 'signed-repository/Packages')):
        raise ValueError('repository preflight evidence changed')
    expected = probe.source.expected_packages(lock)
    expected['cm3-cli-board-support'] = ('0.1.0', 'all')
    specs = [f'{name}={version}' for name, (version, _) in sorted(expected.items())]
    if any(re.fullmatch(r'[a-z0-9][a-z0-9+.-]*=[a-zA-Z0-9.+:~_-]+', s) is None for s in specs):
        raise ValueError('unsafe package specification')
    return {'status': 'PASS', 'source_revision': revision, 'run_id': str(run_id),
            'source_lock_sha256': probe.digest(ROOT / 'project/cm3-cli/source-lock.json'),
            'signing_fingerprint': signing['fingerprint'], 'packages': specs,
            'headers': [s for s in specs if s.startswith('linux-headers-')],
            'board_sha256': probe.digest(board['cm3-cli-board-support']),
            'scope': 'same-job configuration input only; no enduring trust or image authorization'}


def render(stage, receipt, output):
    args = ['jsonnet', '--ext-code', 'sdboot=false',
            '--tla-str', 'product=radxa-cm3-rpi-cm4-io', '--tla-str', 'suite=trixie',
            '--tla-str', 'edition=cli', '--tla-str', 'build_date=',
            '--tla-str', 'rootfs=' + str(stage / 'root'),
            '--tla-str', 'rsdk_rev=' + receipt['source_revision'],
            '--tla-str', 'temp_dir=' + str(stage), '--tla-str', 'output_dir=' + str(stage),
            '--tla-code', 'cm3_preflight=' + json.dumps(receipt),
            str(ROOT / 'src/share/rsdk/build/rootfs.jsonnet')]
    config = subprocess.check_output(args, text=True)
    parsed = json.loads(config)
    for key in ['essential-hooks', 'customize-hooks', 'cleanup-hooks']:
        for hook in parsed['mmdebstrap'].get(key, []):
            subprocess.run(['sh', '-n'], input=hook, check=True, text=True)
    with output.open('x') as stream:
        stream.write(config)
    return parsed


def bootstrap(stage, output, receipt, evidence):
    root = stage / 'root'
    if root.exists() or root.is_symlink():
        raise ValueError('fresh profile directory required')
    # Use the existing RSDK frontend without --force, disk/image tools or service starts.
    probe.command('bdebstrap', '--config', output, '--name', 'cm3-profile-fixture',
                  '--output', stage / 'bootstrap-log')
    installed = probe.chroot(root, 'dpkg-query', '-W',
                             '-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n',
                             capture=True)
    rows = {fields[0]: fields[1:] for fields in (line.split('\t') for line in installed.splitlines())}
    lock = probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    expected = probe.source.expected_packages(lock)
    expected['cm3-cli-board-support'] = ('0.1.0', 'all')
    for name, (version, arch) in expected.items():
        if rows.get(name) != [version, arch, 'installed']:
            raise ValueError('profile package identity/configuration mismatch')
    if probe.chroot(root, 'dpkg', '--audit', capture=True).strip():
        raise ValueError('profile package audit failed')
    for name in ['etc/machine-id', 'var/lib/dbus/machine-id', 'etc/cm3-cli/owner.json',
                 'etc/apt/sources.list.d/cm3-build.list', 'usr/share/keyrings/cm3-build.gpg',
                 'opt/cm3-repo']:
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError('profile retained a builder identity, owner or build feed')
    if list((root / 'etc/ssh').glob('ssh_host_*')):
        raise ValueError('profile retained builder SSH host keys')
    if os.readlink(root / 'etc/kernel/install.d/99-update-overlay.install') != '/dev/null':
        raise ValueError('profile lost board kernel hook policy')
    (evidence / 'rsdk-profile-packages.tsv').write_text(installed)
    return {'bootstrap': 'PASS', 'installed_packages': len(rows), 'services': 'NOT STARTED',
            'owner_enrollment': 'NOT RUN', 'active_target_lsm': 'NOT TESTED',
            'source_revision': receipt['source_revision']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', required=True, type=Path)
    args = parser.parse_args()
    work = Path('/work')
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'blockdyor/radxa-cm3-debian-cli' or
            platform.machine() != 'x86_64' or os.geteuid() != 0 or
            args.workdir != work or work.resolve() != work):
        parser.error('only the existing external same-job /work stage is supported')
    status = {'stage': 'rsdk-profile-bootstrap', 'status': 'FAIL', 'image_build': 'NOT RUN',
              'bootstrap': 'NOT RUN', 'full_package_preflight': 'NOT COMPLETE'}
    try:
        receipt = verified_receipt(work, os.environ['GITHUB_SHA'], os.environ['GITHUB_RUN_ID'])
        stage = work / 'rsdk-profile-stage'
        stage.mkdir()
        shutil.copytree(work / 'signed-repository', stage / 'cm3-repository')
        output = work / 'evidence/rsdk-profile.json'
        render(stage, receipt, output)
        status['bootstrap'] = 'FAIL'
        status.update(bootstrap(stage, output, receipt, work / 'evidence'))
        status.update(status='PASS', config_sha256=probe.digest(output), receipt=receipt)
        print('Held RSDK configuration rendered:', output, status['config_sha256'])
    finally:
        with (work / 'evidence/rsdk-profile-result.json').open('x') as stream:
            stream.write(json.dumps(status, indent=2) + '\n')


if __name__ == '__main__':
    main()
