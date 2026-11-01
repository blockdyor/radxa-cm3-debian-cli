#!/usr/bin/env python3
"""Bounded PEM scan with one exact public GnuTLS self-test-vector disposition."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

LIBRARY = 'usr/lib/aarch64-linux-gnu/libgnutls.so.30.40.3'
LIBRARY_SHA256 = '560c04722d04d0331b0eeda8a249491139ba46bf0e294897ebceb04993380596'
SOURCE_SHA256 = '69e113d802d1670c4d5ac1b99040b1f2d5c7c05daec5003813c049b5184820ed'
MEMBER = 'gnutls-3.8.9/lib/crypto-selftests-pk.c'
MEMBER_SHA256 = 'fce9355507865b53ba0b5c5587932b9d8519be2cd195650b0d9ff69ac2c335c7'
HEADER_COUNT = 12  # Eight complete blocks plus four parser/template markers in this exact library.
BLOCK = rb'-----BEGIN ((?:RSA |DSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----\r?\n[A-Za-z0-9+/=\r\n]+-----END \1-----'
HEADER = rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'


def public_vectors(relative, data, source):
    if relative != LIBRARY or hashlib.sha256(data).hexdigest() != LIBRARY_SHA256:
        raise ValueError('unapproved PEM-bearing object')
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('public source archive drift')
    with tarfile.open(fileobj=io.BytesIO(source), mode='r:xz') as archive:
        member = archive.getmember(MEMBER)
        if not member.isfile() or member.size > 8 * 1024 * 1024:
            raise ValueError('unsafe public source member')
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError('missing public source member')
        text = stream.read()
    if hashlib.sha256(text).hexdigest() != MEMBER_SHA256:
        raise ValueError('public source member drift')
    literals = []
    for token in re.findall(rb'"(?:[^"\\]|\\.)*"', text):
        value = ast.literal_eval(token.decode('ascii'))
        if not isinstance(value, str):
            raise ValueError('unexpected C literal')
        literals.append(value.encode())
    decoded = b''.join(literals)
    blocks = [match.group() for match in re.finditer(BLOCK, data)]
    if len(blocks) != 8 or len(re.findall(HEADER, data)) != HEADER_COUNT or not all(block in decoded for block in blocks):
        raise ValueError('changed, incomplete or additional private-key material')
    return dict(classification='exact public upstream crypto-selftest vectors; NOT deployed credentials',
                path=relative, blocks=8, library_sha256=LIBRARY_SHA256,
                source_archive_sha256=SOURCE_SHA256, source_member=MEMBER, source_member_sha256=MEMBER_SHA256)


def scan(root, source):
    disposition = None
    markers = []
    files = 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        files += 1
        data = path.read_bytes()
        if re.search(BLOCK, data):
            # No blanket package, ELF, source-tree or directory exemptions.
            disposition = public_vectors(str(path.relative_to(root)), data, source)
        elif re.search(HEADER, data):
            markers.append(dict(path=str(path.relative_to(root)),
                                headers=len(re.findall(HEADER, data)), complete_pem_blocks=0))
    if disposition is None:
        raise ValueError('expected pinned GnuTLS library/public-vector disposition absent')
    return dict(scope='allocated regular-file PEM scan only; no arbitrary secret/free-space certification',
                files_scanned=files, public_vectors=disposition,
                header_only_candidates=markers,
                literal_zero_private_key_bytes=False, hardware='UNTESTED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--public-source', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.root, args.public_source.read_bytes()), indent=2))


if __name__ == '__main__':
    main()
