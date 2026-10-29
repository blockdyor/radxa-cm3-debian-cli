#!/usr/bin/env python3
"""Seal successful compilation for internal recovery, never publish plaintext BSPs."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('packages', ROOT / 'scripts/cm3-package-preflight.py')
packages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packages)


def seal(work, recipient, output, provenance):
    lock = packages.source.load_lock(ROOT / 'project/cm3-cli/source-lock.json')
    if json.loads((work / 'evidence/result.json').read_text())['status'] != 'PASS':
        raise ValueError('only a complete verified source build can be retained')
    inputs = packages.inspect_inputs(work, lock)
    # Historical nine-BSP bundles remain readable; new runs retain board input too.
    if (work / 'evidence/board-manifest.json').exists():
        inputs.update(packages.inspect_board_input(work, provenance['GITHUB_SHA']))
    # Explicit allowlist: no target roots, repository keys, logs or arbitrary trees.
    files = list(inputs.values())
    for pattern in ['*.json', '*.diff', '*.config', '*.buildinfo', '*.changes']:
        files.extend(sorted((work / 'evidence').glob(pattern)))
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('retention requires regular non-symlink files')
    metadata = json.dumps({'label': 'EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION',
                           'provenance': provenance,
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
    result = args.workdir / 'evidence/result.json'
    if not result.is_file() or json.loads(result.read_text())['status'] != 'PASS':
        print('No complete source build to retain')
        return
    provenance = {k: os.environ[k] for k in ['GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_RUN_ID']}
    seal(args.workdir, ROOT / 'project/cm3-cli/retention-recipient.pem', args.output, provenance)
    print('Encrypted recovery output SHA256:', packages.digest(args.output))


if __name__ == '__main__':
    main()
