#!/usr/bin/env python3
"""Prepare exact corresponding sources and preserved notices in the external job only."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('assembly', ROOT / 'scripts/cm3-assemble-image.py')
assembly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembly)
LABEL = 'EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION'


def source_specs(manifest, local_names):
    selected = set()
    for line in manifest.splitlines():
        fields = line.split('\t')
        if len(fields) != 5:
            raise ValueError('incomplete installed source identity')
        name, version, arch, source, source_version = fields
        if name in local_names:
            continue
        if (arch not in ['arm64', 'all'] or
                re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', source) is None or
                re.fullmatch(r'[a-zA-Z0-9.+:~_-]+', source_version) is None):
            raise ValueError('unsafe or missing Debian source identity')
        selected.add(source + '=' + source_version)
    if not selected:
        raise ValueError('empty Debian source closure')
    return sorted(selected)


def archive_checkout(archive, checkout, prefix):
    # Track source files (including local modifications), never .git/config,
    # signing keys or ignored compiled outputs. Gitlinks are archived separately.
    listing = subprocess.check_output(['git', '-c', 'safe.directory=' + str(checkout),
                                      '-C', str(checkout), 'ls-files', '-z', '--cached']).decode().split('\0')
    paths = {name for name in listing if name}
    for name in ['.config', 'src/.config', 'src/arch/arm64/configs/radxa.config',
                 'src/arch/arm64/configs/radxa_custom.config']:
        if (checkout / name).is_file():
            paths.add(name)
    for name in sorted(paths):
        if prefix == 'builder-and-board' and name == 'project/cm3-cli/retention-recipient.pem':
            continue  # Unused internal recovery recipient is not image corresponding source.
        path = checkout / name
        if path.is_symlink() or path.is_file():
            archive.add(path, arcname=prefix + '/' + name, recursive=False)


def build_configs(work):
    kernel = assembly.regular(work / 'linux-rk2410-nocsf/src/.config')
    retained = assembly.regular(work / 'evidence/kernel.config')
    if kernel.read_bytes() != retained.read_bytes():
        raise ValueError('kernel corresponding-source configuration differs from actual build evidence')
    loader = assembly.regular(work / 'u-boot-rk2601/src/.config')
    if not kernel.stat().st_size or not loader.stat().st_size:
        raise ValueError('actual kernel and U-Boot build configurations required')
    return {'kernel.config': kernel, 'u-boot.config': loader}


def download_sources(work, source_dir, specs):
    # Isolate both sources and indexes from the builder's inherited Signed-By policy.
    apt = work / 'delivery-apt'
    (apt / 'lists/partial').mkdir(parents=True)
    sources = apt / 'sources.list'
    with sources.open('x') as stream:
        for mirror in ['https://deb.debian.org/debian trixie',
                       'https://deb.debian.org/debian trixie-updates',
                       'https://security.debian.org/debian-security trixie-security']:
            stream.write('deb-src [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] ' + mirror + ' main non-free-firmware\n')
    options = ['-o', 'Dir::Etc::sourcelist=' + str(sources),
               '-o', 'Dir::Etc::sourceparts=-', '-o', 'Dir::State::lists=' + str(apt / 'lists'),
               '-o', 'APT::Update::Error-Mode=any']
    subprocess.run(['apt-get', *options, 'update'], check=True)
    for spec in specs:
        subprocess.run(['apt-get', *options, '--download-only', '--only-source', 'source', '--', spec],
                       cwd=source_dir, check=True)


def review_notices(work, root):
    overlay = assembly.regular(work / 'radxa-overlays/debian/copyright')
    installed = assembly.regular(root / 'usr/share/doc/radxa-overlays-dkms/copyright')
    if installed.read_bytes() != overlay.read_bytes() or b'GPL-2, unless otherwise noted' not in installed.read_bytes():
        raise ValueError('installed overlay clarification missing or changed')
    firmware = {}
    for package in ['firmware-brcm80211', 'firmware-realtek']:
        version = assembly.profile.probe.chroot(root, 'dpkg-query', '-W', '-f=${Version}', package, capture=True)
        copyright = assembly.regular(root / 'usr/share/doc' / package / 'copyright')
        digest = assembly.profile.probe.digest(copyright)
        if version != '20250410-2' or digest != 'f5d62266d99e91aeae9223a5b4f830ed5e917256672f50470ef868e0378ad6d8':
            raise ValueError('firmware version/notices differ from reviewed payload; review before distribution')
        firmware[package] = dict(version=version, copyright_sha256=digest)
    return dict(overlay_clarification='radxa-pkg/radxa-overlays@0ee073720de7652a6b77ea4be8ae029c4a3e7e4e',
                overlay_copyright_sha256=assembly.profile.probe.digest(installed), firmware=firmware,
                scope='Experimental aggregate only; original component terms apply; no stable/hardware approval')


def prepare(work):
    revision = assembly.boundary(work)
    receipt = assembly.authenticate(work, revision, os.environ['GITHUB_RUN_ID'])
    root = work / 'rsdk-profile-stage/root'
    output = work / 'delivery-inputs'
    output.mkdir()
    lock = assembly.profile.probe.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    configs = build_configs(work)
    notice_review = review_notices(work, root)
    manifest = assembly.profile.probe.chroot(root, 'dpkg-query', '-W',
                '-f=${Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\n', capture=True)
    local_names = set(assembly.profile.probe.source.expected_packages(lock)) | {'cm3-cli-board-support'}
    specs = source_specs(manifest, local_names)
    source_dir = output / 'debian-sources'
    source_dir.mkdir()
    download_sources(work, source_dir, specs)
    if not list(source_dir.glob('*.dsc')):
        raise ValueError('actual authenticated Debian source downloads required')
    with tarfile.open(output / 'modified-bsp-and-builder-sources.tar.gz', 'x:gz') as archive:
        archive_checkout(archive, ROOT, 'builder-and-board')
        for recipe in lock['recipes']:
            checkout = work / recipe['name']
            if subprocess.check_output(['git', '-c', 'safe.directory=' + str(checkout), '-C', str(checkout),
                                        'rev-parse', 'HEAD'], text=True).strip() != recipe['commit']:
                raise ValueError('corresponding source revision drift')
            archive_checkout(archive, checkout, recipe['name'])
            for name, child in recipe['gitlinks'].items():
                child_path = checkout / name
                if subprocess.check_output(['git', '-C', str(child_path), 'rev-parse', 'HEAD'], text=True).strip() != child['commit']:
                    raise ValueError('corresponding gitlink revision drift')
                archive_checkout(archive, child_path, recipe['name'] + '/' + name)
        for path in sorted((work / 'evidence').glob('*.diff')):
            archive.add(path, arcname='local-patches/' + path.name, recursive=False)
        for name, path in configs.items():
            archive.add(path, arcname='generated/' + name, recursive=False)
    # Preserve original per-package notices and full common license texts unchanged.
    with tarfile.open(output / 'installed-notices.tar.gz', 'x:gz') as archive:
        archive.add(root / 'usr/share/doc', arcname='usr/share/doc')
        archive.add(root / 'usr/share/common-licenses', arcname='usr/share/common-licenses')
    firmware = {}
    for package in ['firmware-brcm80211', 'firmware-realtek']:
        files = assembly.profile.probe.chroot(root, 'dpkg-query', '-L', package, capture=True).splitlines()
        hashes = {}
        for name in files:
            if name.startswith(('/lib/firmware/', '/usr/lib/firmware/')):
                kind = assembly.profile.probe.chroot(root, 'stat', '-Lc', '%F', '--', name, capture=True).strip()
                if kind == 'regular file':
                    hashes[name] = assembly.profile.probe.chroot(root, 'sha256sum', '--', name, capture=True).split()[0]
        if not hashes or not (root / 'usr/share/doc' / package / 'copyright').is_file():
            raise ValueError('missing actual firmware payload or preserved Debian copyright')
        firmware[package] = hashes
    shutil.copyfile(ROOT / 'project/cm3-cli/source-lock.json', output / 'source-lock.json')
    shutil.copyfile(assembly.regular(work / 'evidence/loader-inputs.json'), output / 'loader-inputs.json')
    (output / 'installed-source-identities.tsv').write_text(manifest)
    (output / 'firmware-files.json').write_text(json.dumps(firmware, indent=2) + '\n')
    (output / 'notice-review.json').write_text(json.dumps(notice_review, indent=2) + '\n')
    (output / 'builder-packages.tsv').write_text(assembly.profile.probe.command(
        'dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\n', capture=True))
    for name in ['hardware-matrix.tsv', 'gates-consolidated-verbatim.txt', 'gates-validation-verbatim.txt',
                 'build.md', 'provenance.md', 'limitations.md']:
        shutil.copyfile(ROOT / 'docs/cm3-cli' / name, output / name)
    report = dict(label=LABEL, source_revision=revision, run_id=os.environ['GITHUB_RUN_ID'],
                  authenticated_input_receipt=receipt, debian_sources=specs,
                  files={str(path.relative_to(output)): assembly.profile.probe.digest(path)
                         for path in sorted(output.rglob('*')) if path.is_file()},
                  licensing='Original notices preserved; per-file terms control, no relicensing or legal warranty',
                  source_policy='Complete tracked modified BSP source/gitlinks plus applied configs/patches; exact Debian source downloads',
                  runtime='UNTESTED; no stable-release authorization')
    (output / 'delivery-inputs.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    if len(sys.argv) != 1:
        raise SystemExit('no path arguments accepted; fixed external /work only')
    print(json.dumps(prepare(Path('/work')), indent=2))


if __name__ == '__main__':
    main()
