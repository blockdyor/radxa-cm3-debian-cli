#!/usr/bin/env python3
"""External source-package probe. Never assembles an image or touches media."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = {
    'product': 'radxa-cm3-rpi-cm4-io', 'soc': 'rk3566', 'suite': 'trixie',
    'edition': 'cli', 'architecture': 'arm64', 'sector_size': 512,
}
RECIPES = {'linux-rk2410-nocsf', 'u-boot-rk2601', 'radxa-overlays',
           'radxa-bootutils', 'radxa-udev'}


def load_lock(path):
    lock = json.loads(Path(path).read_text())
    if lock['schema_version'] != 1 or lock['target'] != TARGET:
        raise ValueError('not the exact CM3/Trixie/CLI/ARM64/512 target')
    if len(lock['recipes']) != 5 or {r['name'] for r in lock['recipes']} != RECIPES:
        raise ValueError('expected the five audited recipe projects')
    for recipe in [*lock['recipes'], lock['configuration_reference']]:
        for source in [recipe, *recipe.get('gitlinks', {}).values()]:
            if not re.fullmatch(r'[0-9a-f]{40}', source['commit']):
                raise ValueError('source must use a full lowercase commit ID')
            if not re.fullmatch(r'radxa(?:-pkg)?/[a-zA-Z0-9_.-]+', source['repository']):
                raise ValueError('unexpected source repository')
    for field in ['builder_image', 'binfmt_image']:
        if not re.fullmatch(r'[a-z0-9/.-]+@sha256:[0-9a-f]{64}', lock[field]):
            raise ValueError('OCI inputs must be digest-pinned')
    if lock['packaging_suffix'] != '+cm3cli1':
        raise ValueError('unexpected packaging version policy')
    return lock


def expected_packages(lock):
    versions = {r['name']: r['version'] + lock['packaging_suffix'] for r in lock['recipes']}
    kernel = versions['linux-rk2410-nocsf']
    loader = versions['u-boot-rk2601']
    return {
        'linux-image-radxa-cm3-rpi-cm4-io': (kernel, 'all'),
        'linux-headers-radxa-cm3-rpi-cm4-io': (kernel, 'all'),
        f'linux-image-{kernel}-rk2410-nocsf': (kernel, 'arm64'),
        f'linux-headers-{kernel}-rk2410-nocsf': (kernel, 'arm64'),
        'u-boot-radxa-cm3-rpi-cm4-io': (loader, 'all'),
        'u-boot-rk2601': (loader, 'all'),
        'radxa-overlays-dkms': (versions['radxa-overlays'], 'all'),
        'radxa-bootutils': (versions['radxa-bootutils'], 'all'),
        'radxa-udev': (versions['radxa-udev'], 'all'),
    }


def run(*args, cwd=None, capture=False):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def checkout(source, destination):
    destination.mkdir()
    run('git', 'init', '--quiet', destination)
    run('git', '-C', destination, 'remote', 'add', 'origin',
        'https://github.com/' + source['repository'] + '.git')
    run('git', '-C', destination, 'fetch', '--depth=1', '--no-tags', 'origin', source['commit'])
    run('git', '-C', destination, 'checkout', '--detach', 'FETCH_HEAD')
    actual = run('git', '-C', destination, 'rev-parse', 'HEAD', capture=True).strip()
    if actual != source['commit']:
        raise ValueError('source checkout drift')
    tree = run('git', '-C', destination, 'ls-tree', '-r', 'HEAD', capture=True)
    actual_links = {}
    for line in tree.splitlines():
        metadata, path = line.split('\t', 1)
        mode, _, revision = metadata.split()
        if mode == '160000':
            actual_links[path] = revision
    links = source.get('gitlinks', {})
    if actual_links != {name: item['commit'] for name, item in links.items()}:
        raise ValueError(f'unreviewed gitlink closure: {actual_links}')
    for name, item in links.items():
        path = destination / name
        if path.is_dir():
            path.rmdir()  # Git creates empty gitlink directories.
        checkout(item, path)


def local_patch(recipe, name, before, after):
    path = recipe / name
    text = path.read_text()
    if text.count(before) != 1:
        raise ValueError(f'patch context drift: {path}')
    path.write_text(text.replace(before, after))


def build_recipe(recipe, lock, work, evidence):
    source = work / recipe['name']
    checkout(recipe, source)
    version = run('dpkg-parsechangelog', '-S', 'Version', cwd=source, capture=True).strip()
    if version != recipe['version']:
        raise ValueError(f'upstream package version drift: {version}')
    # Install and check declared Build-Depends; never use upstream's default -d.
    run('apt-get', 'build-dep', '--no-install-recommends', '-y', '.', cwd=source)
    run('dpkg-checkbuilddeps', cwd=source)
    run('dch', '--newversion', version + lock['packaging_suffix'], '--distribution', 'trixie',
        '--force-distribution', 'Exact-carrier experimental rebuild; source pins in source-lock.json.',
        cwd=source)
    if recipe['name'] == 'linux-rk2410-nocsf':
        local_patch(source, 'Makefile.extra', 'DPKG_FLAGS ?= -d', 'DPKG_FLAGS ?=')
        local_patch(source, 'Makefile.extra', '-j$(shell nproc)', '-j2')
        # dpkg-source applies the two recorded config patches before dh_auto_build.
        run('dpkg-source', '--before-build', '.', cwd=source)
        for name in ['radxa.config', 'radxa_custom.config']:
            if not (source / 'src/arch/arm64/configs' / name).is_file():
                raise ValueError('required kernel configuration patch not applied')
    if recipe['name'] == 'u-boot-rk2601':
        # The first successful fuel-gauge poll still gates display/boot decisions.
        # Explicit zero defaults let GCC 14 prove the cached diagnostic values safe.
        local_patch(source, 'src/drivers/power/charge_animation.c',
                    '\tint soc, voltage, current, key_state;',
                    '\tint soc = 0, voltage, current = 0, key_state;')
        path = source / '.github/local/Makefile.local'
        text = path.read_text()
        _, separator, rest = text.partition('PACKING_VARIANTS :=')
        if not separator:
            raise ValueError('loader recipe shape changed')
        path.write_text('UBOOT_PRODUCTS := radxa-cm3-rpi-cm4-io\n\nPACKING_VARIANTS :=' + rest)
        local_patch(source, 'Makefile.extra', '-j$(shell nproc)', '-j2')
        run('file', source / 'rkbin/tools/boot_merger')
        run('readelf', '-l', source / 'rkbin/tools/boot_merger')
    (evidence / (recipe['name'] + '-local.diff')).write_text(
        run('git', '-C', source, 'diff', '--binary', capture=True))
    for name in recipe.get('gitlinks', {}):
        (evidence / (recipe['name'] + '-' + name + '-local.diff')).write_text(
            run('git', '-C', source / name, 'diff', '--binary', capture=True))
    run('dpkg-buildpackage', '--no-sign', '-b', '-j2', cwd=source)
    if recipe['name'] == 'linux-rk2410-nocsf':
        shutil.copyfile(source / 'src/.config', evidence / 'kernel.config')
    for suffix in ['*.buildinfo', '*.changes']:
        for path in work.glob(suffix):
            shutil.copyfile(path, evidence / path.name)


def inspect_packages(lock, work, evidence):
    expected = expected_packages(lock)
    found = {}
    output = work / 'selected-debs'
    output.mkdir()
    for deb in sorted(work.glob('*.deb')):
        fields = run('dpkg-deb', '--show', '--showformat=${Package}\t${Version}\t${Architecture}\n',
                     deb, capture=True).strip().split('\t')
        name, version, arch = fields
        if name not in expected:
            continue
        if (version, arch) != expected[name] or name in found:
            raise ValueError(f'package identity mismatch: {fields}')
        with deb.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        found[name] = {'version': version, 'architecture': arch, 'sha256': digest}
        shutil.copyfile(deb, output / deb.name)
    if set(found) != set(expected):
        raise ValueError(f'missing exact packages: {sorted(set(expected) - set(found))}')
    (evidence / 'bsp-manifest.json').write_text(json.dumps(found, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=ROOT / 'project/cm3-cli/source-lock.json')
    parser.add_argument('--workdir', type=Path)
    parser.add_argument('--check-lock', action='store_true')
    args = parser.parse_args()
    lock = load_lock(args.lock)
    if args.check_lock:
        print(json.dumps({'target': lock['target'], 'packages': expected_packages(lock)}, indent=2))
        return
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'blockdyor/radxa-cm3-debian-cli' or
            platform.machine() != 'x86_64' or os.geteuid() != 0):
        parser.error('package builds are restricted to the external AMD64 CI container')
    if args.workdir is None or not args.workdir.is_absolute():
        parser.error('an explicit absolute, empty workdir is required')
    work = args.workdir
    if not work.is_dir() or any(work.iterdir()):
        parser.error('workdir must exist and be empty; no stale artifact reuse')
    evidence = work / 'evidence'
    evidence.mkdir()
    os.environ.update(DEBIAN_FRONTEND='noninteractive', DEBFULLNAME='CM3 CLI project',
                      DEBEMAIL='noreply@users.noreply.github.com', DEB_BUILD_OPTIONS='parallel=2')
    started = time.time()
    result = {'stage': 'source-package-build', 'status': 'FAIL',
              'full_package_preflight': 'NOT RUN', 'image_build': 'NOT RUN'}
    shutil.copyfile(args.lock, evidence / 'source-lock.json')
    try:
        sources = Path('/etc/apt/sources.list.d/debian.sources')
        if not sources.is_file() or 'trixie' not in sources.read_text():
            raise ValueError('builder is not the expected Trixie container')
        run('dpkg', '--add-architecture', 'arm64')
        run('apt-get', '-o', 'APT::Update::Error-Mode=any', '-o', 'Debug::Acquire::gpgv=true', 'update')
        run('apt-get', 'install', '--no-install-recommends', '-y',
            'ca-certificates', 'git', 'build-essential', 'devscripts', 'debhelper', 'fakeroot',
            'crossbuild-essential-arm64', 'qemu-user-static', 'binutils', 'file',
            'libssl-dev:arm64', 'libelf-dev:arm64', 'libncurses-dev:arm64', 'libyaml-dev:arm64',
            'bc', 'cpio', 'kmod', 'flex', 'bison', 'libelf-dev', 'dwarves', 'rsync')
        hello = work / 'arm64-probe.c'
        hello.write_text('int main(void) { return 0; }\n')
        run('aarch64-linux-gnu-gcc', hello, '-o', work / 'arm64-probe')
        run(work / 'arm64-probe')
        for recipe in lock['recipes']:
            build_recipe(recipe, lock, work, evidence)
        inspect_packages(lock, work, evidence)
        result['status'] = 'PASS'
    finally:
        (evidence / 'builder-packages.tsv').write_text(run(
            'dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n',
            capture=True))
        result['elapsed_seconds'] = round(time.time() - started, 2)
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        shutil.copyfile('/etc/apt/sources.list.d/debian.sources', evidence / 'builder-debian.sources')
        for path in Path('/var/lib/apt/lists').glob('*InRelease'):
            shutil.copyfile(path, evidence / path.name)


if __name__ == '__main__':
    main()
