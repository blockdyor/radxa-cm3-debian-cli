#!/usr/bin/env python3
"""Stage verified experimental delivery or explicitly selected build-only diagnostics."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('assembly', ROOT / 'scripts/cm3-assemble-image.py')
assembly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembly)
LABEL = 'EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION'


def checked_security(directory, delivery):
    chain = json.loads(assembly.regular(directory / 'package-chain-verification.json').read_text())
    vectors = json.loads(assembly.regular(directory / 'public-test-vectors.json').read_text())
    for report in [chain, vectors]:
        if (not isinstance(report, dict) or
                any(report.get(key) != delivery.get(key) for key in ['source_revision', 'run_id'])):
            raise ValueError('exact-run security evidence required')
    fingerprint = delivery['authenticated_input_receipt']['signing_fingerprint']
    if (chain.get('status') != 'PASS' or chain.get('local_fingerprint') != fingerprint or
            type(chain.get('installed')) is not int or chain['installed'] < 1 or
            len(chain.get('packages', [])) != chain['installed']):
        raise ValueError('complete authenticated package chain required')
    spec = importlib.util.spec_from_file_location('cm3_vectors', ROOT / 'scripts/cm3-public-test-vectors.py')
    assert spec is not None and spec.loader is not None
    public = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(public)
    bound = vectors.get('public_vectors', {})
    if (bound.get('path') != public.LIBRARY or bound.get('blocks') != 8 or
            bound.get('library_sha256') != public.LIBRARY_SHA256 or
            bound.get('source_archive_sha256') != public.SOURCE_SHA256 or
            bound.get('source_member_sha256') != public.MEMBER_SHA256 or
            vectors.get('literal_zero_private_key_bytes') is not False):
        raise ValueError('exact public-vector disposition required')
    expected = chain.get('files_sha256')
    if not isinstance(expected, dict) or not expected or expected.get('debian-archive-keyring.gpg') != chain.get('debian_keyring_sha256'):
        raise ValueError('package-chain inventory/trust binding required')
    found = {}
    with tarfile.open(assembly.regular(directory / 'package-chain.tar.gz'), 'r:gz') as archive:
        for member in archive:
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'package-chain':
                raise ValueError('unsafe package-chain archive path')
            name = str(path.relative_to('package-chain'))
            if member.isdir() and name in ['.', 'releases', 'indexes', 'packages']:
                continue
            if not member.isfile() or name not in expected or name in found:
                raise ValueError('unexpected package-chain archive member')
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError('unreadable package-chain archive member')
            found[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    if found != expected:
        raise ValueError('package-chain archive differs from verified inventory')


def checked_materials(directory, manifest):
    expected = manifest['files']
    actual = {str(path.relative_to(directory)) for path in directory.rglob('*') if path.is_file()}
    if actual != set(expected) | {'delivery-inputs.json'}:
        raise ValueError('source/notice delivery set changed')
    for name, digest in expected.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('unsafe delivery material path')
        if assembly.profile.probe.digest(assembly.regular(directory / path)) != digest:
            raise ValueError('source/notice material hash mismatch')
    if not {'modified-bsp-and-builder-sources.tar.gz', 'installed-notices.tar.gz',
            'firmware-files.json', 'installed-source-identities.tsv', 'source-lock.json',
            'loader-inputs.json', 'package-chain.tar.gz', 'package-chain-verification.json',
            'public-test-vectors.json'} <= set(expected):
        raise ValueError('corresponding source/notices incomplete')
    if not any(name.startswith('debian-sources/') and name.endswith('.dsc') for name in expected):
        raise ValueError('exact Debian source delivery absent')
    return sorted(actual)


def stage(work):
    revision = assembly.boundary(work)
    run_id = os.environ['GITHUB_RUN_ID']
    image_dir = work / 'image-output'
    delivery_dir = work / 'delivery-inputs'
    result = json.loads(assembly.regular(image_dir / 'verification.json').read_text())
    delivery = json.loads(assembly.regular(delivery_dir / 'delivery-inputs.json').read_text())
    for report in [result, delivery]:
        if report.get('source_revision') != revision or report.get('run_id') != run_id or report.get('label') != LABEL:
            raise ValueError('exact-run classified image/source delivery required')
    if result.get('status') != 'PASS' or result.get('hardware') != 'UNTESTED' or result.get('stable_release') != 'BLOCKED':
        raise ValueError('independent offline verification required; no hardware/release qualification')
    materials = checked_materials(delivery_dir, delivery)
    checked_security(delivery_dir, delivery)
    if 'notice-review.json' not in materials:
        raise ValueError('payload-specific notice review required')
    review = json.loads((delivery_dir / 'notice-review.json').read_text())
    if review.get('overlay_clarification') != 'radxa-pkg/radxa-overlays@0ee073720de7652a6b77ea4be8ae029c4a3e7e4e':
        raise ValueError('official overlay clarification required')
    image = assembly.regular(image_dir / (assembly.NAME + '.xz'))
    raw = assembly.regular(image_dir / assembly.NAME)
    for path, digest, size in [(image, result['compressed_sha256'], result['compressed_bytes']),
                               (raw, result['image_sha256'], result['image_bytes'])]:
        if path.stat().st_size != size or assembly.profile.probe.digest(path) != digest:
            raise ValueError('verified image changed before upload')
    destination = work / 'public-image'
    destination.mkdir()
    shutil.copyfile(image, destination / image.name)
    for name in ['packages.tsv', 'verification.json']:
        shutil.copyfile(assembly.regular(image_dir / name), destination / name)
    for name in ['image-stage-a.json', 'image-admission.json', 'image-offline-tests.json']:
        shutil.copyfile(assembly.regular(work / 'evidence' / name), destination / name)
    for name in materials:
        target = destination / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(assembly.regular(delivery_dir / name), target)
    (destination / 'README.txt').write_text(
        LABEL + '\nSource: ' + revision + '\nRun: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/' + run_id +
        '\n14-day GitHub Actions development artifact; no release or hardware authority.\n'
        'Original component licenses apply. Sources/notices accompany these exact bytes in sources/.\n'
        'Rockchip and radio firmware are proprietary; retain their notices and restrictions.\n'
        'Guarded MMC OS-root expansion is implemented; physical expansion remains UNTESTED.\n'
        'All physical tests remain UNTESTED. Obtain separate hardware authorization before use.\n')
    (destination / 'RAW-SHA256SUMS').write_text(result['image_sha256'] + '  ' + assembly.NAME + '\n')
    (destination / 'IMAGE-XZ-SHA256SUMS').write_text(result['compressed_sha256'] + '  ' + image.name + '\n')
    record = dict(label=LABEL, source_revision=revision, run_id=run_id, hardware='UNTESTED',
                  image_sha256=result['image_sha256'], compressed_sha256=result['compressed_sha256'],
                  image_bytes=result['image_bytes'], compressed_bytes=result['compressed_bytes'],
                  files={str(path.relative_to(destination)): assembly.profile.probe.digest(path)
                         for path in sorted(destination.rglob('*')) if path.is_file()})
    (destination / 'delivery-result.json').write_text(json.dumps(record, indent=2) + '\n')
    with (destination / 'SHA256SUMS').open('x') as stream:
        for path in sorted(destination.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                stream.write(assembly.profile.probe.digest(path) + '  ' + str(path.relative_to(destination)) + '\n')
    print('Verified experimental image and corresponding materials:', destination)


def diagnostics(work):
    revision = assembly.boundary(work)
    run_id = os.environ['GITHUB_RUN_ID']
    image_dir = work / 'image-output'
    result = json.loads(assembly.regular(image_dir / 'verification.json').read_text())
    delivery_dir = work / 'delivery-inputs'
    delivery = json.loads(assembly.regular(delivery_dir / 'delivery-inputs.json').read_text())
    for report in [result, delivery]:
        if report.get('source_revision') != revision or report.get('run_id') != run_id or report.get('label') != LABEL:
            raise ValueError('exact-run classified image/source delivery required')
    if result.get('status') != 'PASS' or result.get('hardware') != 'UNTESTED' or result.get('stable_release') != 'BLOCKED':
        raise ValueError('independent offline verification required; no hardware/release qualification')
    image = assembly.regular(image_dir / (assembly.NAME + '.xz'))
    if assembly.profile.probe.digest(image) != result['compressed_sha256']:
        raise ValueError('verified image changed before upload')
    checked_materials(delivery_dir, delivery)
    checked_security(delivery_dir, delivery)
    destination = work / 'public-diagnostics'
    destination.mkdir()
    for name in ['packages.tsv', 'verification.json']:
        shutil.copyfile(assembly.regular(image_dir / name), destination / name)
    for name in ['image-stage-a.json', 'image-admission.json', 'image-offline-tests.json']:
        shutil.copyfile(assembly.regular(work / 'evidence' / name), destination / name)
    notes = (LABEL + '\n\nDebian Trixie / ARM64 / CLI / radxa-cm3-rpi-cm4-io / 512-byte sectors.\n'
             'Source: ' + revision + '\nRun: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/' + run_id + '\n'
             'Raw image SHA256: ' + result['image_sha256'] + '\nRaw image bytes: ' + str(result['image_bytes']) + '\n'
             'Compressed image SHA256: ' + result['compressed_sha256'] + '\nCompressed bytes: ' + str(result['compressed_bytes']) + '\n\n'
             'BUILD-ONLY: no public payload upload; allowlisted producer outputs have encrypted internal recovery.\n'
             'Diagnostics-only mode; no payload or corresponding sources delivered.\n'
             'No default owner, passwords, SSH host keys or private credentials are supplied.\n'
             'Owner document schema/validation: scripts/cm3-owner-config.py in corresponding builder sources.\n'
             'See the preserved board README and build/provenance/limitations records for offline preparation.\n'
             'This delivery does not authorize flashing or testing physical/production hardware.\n'
             'Obtain separate disposable-device test approval before first use; keep a known-good recovery medium.\n'
             'Physical firstboot, enrollment, services, active LSM, update/rollback, compatibility and sustained performance remain UNTESTED.\n'
             'Neither source/package checks nor read-only image inspection prove boot success.\n'
             'Original G0-G7 criteria and hardware matrix remain unchanged; stable release BLOCKED.\n'
             'Source materials and original notices remain runner-local; no relicensing.\n'
             'Rockchip proprietary DDR/BL31/helper terms prohibit reverse engineering; see original rkbin LICENSE.\n')
    (destination / 'README.txt').write_text(notes)
    (destination / 'RAW-SHA256SUMS').write_text(result['image_sha256'] + '  ' + assembly.NAME + '\n')
    (destination / 'IMAGE-XZ-SHA256SUMS').write_text(result['compressed_sha256'] + '  ' + assembly.NAME + '.xz\n')
    engineering = dict(label=LABEL, source_revision=revision, run_id=run_id,
                       engineering='PASS', redistribution='NOT REQUESTED: diagnostics only',
                       payload='No public payload; allowlisted producer outputs retained by encrypted internal recovery',
                       image_sha256=result['image_sha256'], compressed_sha256=result['compressed_sha256'],
                       image_bytes=result['image_bytes'], compressed_bytes=result['compressed_bytes'],
                       hardware='UNTESTED',
                       files={path.name: assembly.profile.probe.digest(assembly.regular(path))
                              for path in sorted(destination.iterdir())})
    (destination / 'engineering-result.json').write_text(json.dumps(engineering, indent=2) + '\n')
    with (destination / 'SHA256SUMS').open('x') as stream:
        for path in sorted(destination.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                stream.write(assembly.profile.probe.digest(assembly.regular(path)) + '  ' + str(path.relative_to(destination)) + '\n')
    print('Verified build-only engineering diagnostics; no payload publication:', destination)


def main():
    if sys.argv[1:] == ['--diagnostics']:
        diagnostics(Path('/work'))
    elif len(sys.argv) == 1:
        stage(Path('/work'))
    else:
        raise SystemExit('usage: cm3-publish-image.py [--diagnostics]; fixed external /work only')


if __name__ == '__main__':
    main()
