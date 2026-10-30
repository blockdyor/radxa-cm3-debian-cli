#!/usr/bin/env python3
"""Stage build-only diagnostics; public payload delivery is held for OVERLAY-1."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('assembly', ROOT / 'scripts/cm3-assemble-image.py')
assembly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembly)
LABEL = 'EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION'


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
            'loader-inputs.json'} <= set(expected):
        raise ValueError('corresponding source/notices incomplete')
    if not any(name.startswith('debian-sources/') and name.endswith('.dsc') for name in expected):
        raise ValueError('exact Debian source delivery absent')
    return sorted(actual)


def stage(work):
    # An owner build-only approval is not a copyright-holder distribution grant.
    raise ValueError('OVERLAY-1 unresolved: public payload distribution blocked')


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
             'BUILD-ONLY: payloads are not uploaded or retained; discarded with the disposable runner.\n'
             'Redistribution clearance: BLOCKED (OVERLAY-1); upstream radxa-pkg/radxa-overlays#606.\n'
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
                       engineering='PASS', redistribution='BLOCKED: OVERLAY-1',
                       payload='NOT RETAINED; discarded with disposable runner',
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
