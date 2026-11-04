#!/usr/bin/env python3
"""Retain and independently replay APT signer/index/exact installed-package closure."""
import argparse
import email.parser
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError('redirected or missing chain input: ' + str(path))
    return path


def paragraphs(text):
    return [email.parser.Parser().parsestr(part) for part in text.strip().split('\n\n') if part.strip()]


def apt_list_input(root, path):
    if path.parent != root / 'var/lib/apt/lists':
        raise ValueError('unexpected APT list directory')
    if path.is_symlink():
        for name in ['Packages', 'InRelease']:
            if path.name == '_opt_cm3-repo_._' + name:
                # APT's file-method alias is guest-absolute, not a host path.
                if Path(os.readlink(path)) != Path('/opt/cm3-repo') / name:
                    raise ValueError('redirected local repository alias')
                return regular(root / 'opt/cm3-repo' / name)
    return regular(path)


def identities(text):
    found = set()
    for line in text.splitlines():
        fields = line.split('\t')
        if (len(fields) != 4 or fields[3] != 'installed' or
                re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', fields[0]) is None or
                re.fullmatch(r'[A-Za-z0-9.+:~_-]+', fields[1]) is None or
                fields[2] not in ['arm64', 'all']):
            raise ValueError('invalid installed package identity')
        identity = tuple(fields[:3])
        if identity in found:
            raise ValueError('duplicate installed package identity')
        found.add(identity)
    if not found:
        raise ValueError('empty installed package set')
    return found


def verify(directory, debian_keyring_sha256, local_fingerprint):
    """The Debian trust anchor must be supplied from the pinned builder, not this bundle."""
    names = {'debian-archive-keyring.gpg', 'local-archive-key.gpg', 'installed.tsv',
             'releases', 'indexes', 'packages'}
    if {path.name for path in directory.iterdir()} != names:
        raise ValueError('unexpected package-chain contents')
    for path in directory.rglob('*'):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise ValueError('redirected or special package-chain input')
        if path.is_dir() and path.parent != directory:
            raise ValueError('nested package-chain directory')
    keyring = regular(directory / 'debian-archive-keyring.gpg')
    if digest(keyring) != debian_keyring_sha256 or re.fullmatch('[0-9A-F]{40}', local_fingerprint) is None:
        raise ValueError('package-chain trust anchor mismatch')
    local_keyring = regular(directory / 'local-archive-key.gpg')
    releases = []
    with tempfile.TemporaryDirectory(prefix='cm3-chain-gpg-') as home:
        for path in sorted((directory / 'releases').iterdir()):
            regular(path)
            signed_bytes = path.read_bytes()
            if (not signed_bytes.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----\n') or
                    not signed_bytes.endswith(b'-----END PGP SIGNATURE-----\n')):
                raise ValueError('unexpected unsigned repository material')
            verified = None
            for kind, anchor in [('debian', keyring), ('local', local_keyring)]:
                result = subprocess.run(['gpgv', '--homedir', home, '--status-fd=2',
                                         '--keyring', str(anchor), '--output', '-', str(path)],
                                        text=True, capture_output=True)
                signers = re.findall(r'^\[GNUPG:\] VALIDSIG ([0-9A-F]{40}) ', result.stderr, re.M)
                if result.returncode == 0 and signers:
                    if kind == 'local' and signers != [local_fingerprint]:
                        raise ValueError('unexpected local repository signer')
                    release = email.parser.Parser().parsestr(result.stdout)
                    if kind == 'debian' and (release.get('Origin') != 'Debian' or
                            release.get('Codename') not in ['trixie', 'trixie-updates', 'trixie-security']):
                        raise ValueError('unexpected Debian repository')
                    verified = dict(kind=kind, signers=signers, sha256=digest(path), release=release)
                    break
            if verified is None:
                raise ValueError('unverified repository InRelease: ' + path.name)
            releases.append(verified)
    if {item['kind'] for item in releases} != {'local', 'debian'}:
        raise ValueError('both Debian and same-run local repository signatures required')
    authenticated = set()
    for item in releases:
        for line in item['release'].get('SHA256', '').splitlines():
            fields = line.split()
            if len(fields) == 3 and (fields[2] == 'Packages' or fields[2].endswith('/Packages')):
                authenticated.add((fields[0], fields[1]))
    entries = {}
    indexes = []
    for path in sorted((directory / 'indexes').iterdir()):
        regular(path)
        if (digest(path), str(path.stat().st_size)) not in authenticated:
            raise ValueError('Packages index not bound to a verified Release')
        indexes.append(dict(file=path.name, sha256=digest(path)))
        for item in paragraphs(path.read_text()):
            identity = (item.get('Package'), item.get('Version'), item.get('Architecture'))
            entries.setdefault(identity, set()).add((item.get('SHA256'), item.get('Size')))
    expected = identities(regular(directory / 'installed.tsv').read_text())
    found = {}
    for path in sorted((directory / 'packages').iterdir()):
        regular(path)
        identity = tuple(subprocess.check_output(
            ['dpkg-deb', '--show', '--showformat=${Package}\t${Version}\t${Architecture}', '--', str(path)],
            text=True).split('\t'))
        if identity not in expected or identity in found:
            raise ValueError('unexpected or duplicate retained package')
        sha256 = digest(path)
        if (sha256, str(path.stat().st_size)) not in entries.get(identity, set()):
            raise ValueError('package not authenticated by signed index: ' + str(identity))
        found[identity] = dict(file=path.name, sha256=sha256, bytes=path.stat().st_size)
    if set(found) != expected:
        raise ValueError('incomplete all-installed-package closure')
    return dict(status='PASS', scope='signer -> Release -> Packages -> exact installed identities/payloads; '
                'installed-file transformations checked separately by assembly.authenticate',
                debian_keyring_sha256=debian_keyring_sha256, local_fingerprint=local_fingerprint,
                releases=[{key: value for key, value in item.items() if key != 'release'} for item in releases],
                indexes=indexes, installed=len(expected),
                files_sha256={str(path.relative_to(directory)): digest(path)
                              for path in sorted(directory.rglob('*')) if path.is_file()},
                packages=[dict(identity=list(identity), **value) for identity, value in sorted(found.items())])


def capture(root, output):
    """Run before cleanup while exact authenticated indexes and local feed still exist."""
    if (root != Path('/work/rsdk-profile-stage/root') or
            output != Path('/work/rsdk-profile-stage/package-chain') or
            os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'blockdyor/radxa-cm3-debian-cli' or
            os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted' or
            platform.machine() != 'x86_64' or os.geteuid() != 0 or
            not Path('/.dockerenv').is_file()):
        raise ValueError('capture only in the fixed external disposable builder')
    # Use literal producer paths, never agent-supplied chroot/command arguments.
    root = Path('/work/rsdk-profile-stage/root')
    output = Path('/work/rsdk-profile-stage/package-chain')
    if root.resolve() != root or output.parent.resolve() != output.parent:
        raise ValueError('redirected capture stage')
    output.mkdir()
    installed = subprocess.check_output(['chroot', str(root), 'dpkg-query', '-W',
                                         '-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n'], text=True)
    expected = identities(installed)
    (output / 'installed.tsv').write_text(installed)
    shutil.copyfile('/trusted-builder/debian-archive-keyring.gpg', output / 'debian-archive-keyring.gpg')
    local = root / 'opt/cm3-repo/archive-key.gpg'
    shutil.copyfile(regular(local), output / 'local-archive-key.gpg')
    for name in ['releases', 'indexes', 'packages']:
        (output / name).mkdir()
    lists = root / 'var/lib/apt/lists'
    for path in sorted(lists.iterdir()):
        if path.name.endswith('_InRelease'):
            shutil.copyfile(apt_list_input(root, path), output / 'releases' / path.name)
        elif re.search(r'_Packages(?:\.(?:lz4|gz|xz))?$', path.name):
            data = subprocess.check_output(['/usr/lib/apt/apt-helper', 'cat-file', str(apt_list_input(root, path))])
            (output / 'indexes' / (path.name + '.decoded')).write_bytes(data)
    with tempfile.TemporaryDirectory(prefix='cm3-chain-', dir=root / 'var/tmp') as temporary:
        target = Path(temporary)
        # Download-only: no installation, configuration, resolver refresh or insecure flags.
        subprocess.run(['chroot', str(root), 'sh', '-ec', 'cd "$1"; shift; exec apt-get download -- "$@"',
                        'cm3-chain', '/' + str(target.relative_to(root)),
                        *[name + ':' + arch + '=' + version for name, version, arch in sorted(expected)]], check=True)
        for path in sorted(target.iterdir()):
            if path.name == 'partial' and path.is_dir() and not list(path.iterdir()):
                continue
            shutil.copyfile(regular(path), output / 'packages' / path.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['capture', 'verify'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--debian-keyring-sha256')
    parser.add_argument('--local-fingerprint')
    args = parser.parse_args()
    if args.action == 'capture':
        if args.root is None:
            parser.error('--root required for capture')
        capture(args.root, args.directory)
    else:
        if args.debian_keyring_sha256 is None or args.local_fingerprint is None:
            parser.error('explicit independently anchored keyring hash and local fingerprint required')
        print(json.dumps(verify(args.directory, args.debian_keyring_sha256, args.local_fingerprint), indent=2))


if __name__ == '__main__':
    main()
