#!/usr/bin/env python3
"""Seal successful compilation for internal recovery, never publish plaintext BSPs."""
import argparse
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('packages', ROOT / 'scripts/cm3-package-preflight.py')
packages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packages)
SPEC = importlib.util.spec_from_file_location('profile', ROOT / 'scripts/cm3-rsdk-profile.py')
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


def image_files(work):
    """Allowlisted producer deliverables only, including failed final-image bytes."""
    spec = importlib.util.spec_from_file_location('cm3_publish', ROOT / 'scripts/cm3-publish-image.py')
    assert spec is not None and spec.loader is not None
    publish = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publish)
    directory = work / 'delivery-inputs'
    manifest = directory / 'delivery-inputs.json'
    if not manifest.is_file():
        return []  # Assembly cannot start before completed source/notices preparation.
    names = publish.checked_materials(directory, json.loads(manifest.read_text()))
    files = [directory / name for name in names]
    image_dir = work / 'image-output'
    raw = image_dir / 'cm3-trixie-arm64-cli.img'
    compressed = image_dir / 'cm3-trixie-arm64-cli.img.xz'
    for path in [raw, compressed]:
        if path.is_symlink():
            raise ValueError('redirected retained image')
    retain_raw = raw.is_file()
    if compressed.is_file():
        files.append(compressed)
        if retain_raw:
            try:
                with lzma.open(compressed, 'rb') as stream:
                    uncompressed = hashlib.file_digest(stream, 'sha256').hexdigest()
                retain_raw = uncompressed != packages.digest(raw)
            except (OSError, EOFError, lzma.LZMAError):
                pass
    if retain_raw:
        files.append(raw)
    for name in ['verification.json', 'packages.tsv']:
        if (image_dir / name).is_file():
            files.append(image_dir / name)
    return files


def seal(work, recipient, output, provenance, retain_image=False):
    lock = packages.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    if json.loads((work / 'evidence/result.json').read_text())['status'] != 'PASS':
        raise ValueError('only a complete verified source build can be retained')
    inputs = packages.inspect_inputs(work, lock)
    # Historical nine-BSP bundles remain readable; new runs retain board input too.
    if (work / 'evidence/board-manifest.json').exists():
        inputs.update(packages.inspect_board_input(work, provenance['GITHUB_SHA']))
    # Explicit allowlist: no target roots, private keys, logs or arbitrary trees.
    files = list(inputs.values())
    if retain_image:
        files.extend(image_files(work))
    repository = work / 'signed-repository'
    if repository.is_symlink():
        raise ValueError('repository symlinks prohibited')
    if repository.exists():
        signing = json.loads((work / 'evidence/local-repository.json').read_text())
        profile.verify_repository(repository, inputs, signing['fingerprint'])
        files.extend(sorted(p for p in repository.rglob('*') if p.is_file()))
    for pattern in ['*.json', '*.diff', '*.config', '*.buildinfo', '*.changes']:
        files.extend(sorted((work / 'evidence').glob(pattern)))
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('retention requires regular non-symlink files')
    metadata = json.dumps({'label': 'EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION',
                           'provenance': provenance,
                           'raw_image_sha256': packages.digest(work / 'image-output/cm3-trixie-arm64-cli.img')
                           if retain_image and (work / 'image-output/cm3-trixie-arm64-cli.img').is_file() else None,
                           'files': {str(p.relative_to(work)): packages.digest(p) for p in files}},
                          indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('refuse to overwrite retained output')
    # Plain archive exists only in this disposable directory and is always deleted.
    with tempfile.TemporaryDirectory(prefix='cm3-retention-', dir=work) as temporary:
        archive = Path(temporary) / 'payload.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for path in files:
                tar.add(path, arcname=str(path.relative_to(work)), recursive=False)
            info = tarfile.TarInfo('retention-manifest.json')
            info.size = len(metadata)
            tar.addfile(info, io.BytesIO(metadata))
        encrypted = Path(temporary) / 'payload.cms'
        subprocess.run(['openssl', 'cms', '-encrypt', '-binary', '-aes-256-gcm',
                        '-in', str(archive), '-outform', 'DER', '-out', str(encrypted),
                        str(recipient)], check=True)
        encrypted.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    work = ROOT / 'package-work'
    output = ROOT / 'preflight-work/cm3-recovery.cms'
    if args.workdir.resolve() != work or args.output.resolve() != output:
        parser.error('retention CLI requires the checked-out package-work and preflight-work paths')
    result = work / 'evidence/result.json'
    if not result.is_file() or json.loads(result.read_text())['status'] != 'PASS':
        print('No complete source build to retain')
        return
    provenance = {k: os.environ[k] for k in ['GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_RUN_ID']}
    seal(work, ROOT / 'project/cm3-cli/retention-recipient.pem', output, provenance,
         retain_image=os.environ.get('EXPERIMENTAL_IMAGE') == 'true')
    print('Encrypted recovery output SHA256:', packages.digest(output))


if __name__ == '__main__':
    main()
