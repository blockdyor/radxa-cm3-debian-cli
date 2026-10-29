#!/usr/bin/env python3
"""Install the pinned builder-only RSDK frontend, absent from Debian Trixie."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

# Debian sid InRelease -> Packages SHA256 verified 2026-10-29; no sid APT source.
URL = 'https://deb.debian.org/debian/pool/main/b/bdebstrap/bdebstrap_0.8.1-2_all.deb'
SHA256 = '43631e6a5628654e9be4407287c3c385f034818d1d6fe5bb2b5509a8894722e9'


def verify_package(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError('builder frontend SHA256 mismatch')
    identity = subprocess.check_output(
        ['dpkg-deb', '--show', '--showformat=${Package}\t${Version}\t${Architecture}',
         '--', str(path)], text=True)
    if identity != 'bdebstrap\t0.8.1-2\tall':
        raise ValueError('unexpected builder frontend identity')


def main():
    if (os.geteuid() != 0 or os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'blockdyor/radxa-cm3-debian-cli'):
        raise ValueError('only the disposable external builder is supported')
    with tempfile.TemporaryDirectory(prefix='cm3-bootstrap-tools-') as temporary:
        path = Path(temporary) / 'bdebstrap.deb'
        with urllib.request.urlopen(URL, timeout=60) as response, path.open('xb') as output:
            shutil.copyfileobj(response, output)
        verify_package(path)
        # Dependencies resolve only from the builder's existing signed Trixie sources.
        subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends',
                        'jsonnet', str(path)], check=True)
        subprocess.run(['bdebstrap', '--help'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['jsonnet', '--version'], check=True)
        print('Pinned builder frontend verified:', SHA256, flush=True)


if __name__ == '__main__':
    main()
