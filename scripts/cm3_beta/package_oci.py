#!/usr/bin/env python3
"""Local-only OCI distribution recipe. Never authenticates or publishes."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import tarfile

VERSION = '0.1.0-beta.1'
REVISION = 'b71152296933808f99d7dc169fc6811861a9001b'
IMAGE = 'radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz'
RAW = IMAGE.removesuffix('.xz')
IMAGE_SHA = 'e189249e76a527b1680b4c1667ca58c923ab59d7567e1792b8019cc537c72e57'
RAW_SHA = 'd514bf7be20e45771eb043e2e620b22e5d584df0f10afe343d6ae47b28b2beca'
SOURCE_SHA = '2088afb25921bc54a8df60e26d2453e8f6f58617ed55727188f61717c1d4c7fd'
SUMS_SHA = '817d42c2bdf2d7e779d4965134e52d9e4359ea35c3b945ca78ef870ba447e17f'
METADATA = ('SHA256SUMS', 'package-manifest.txt', 'build-manifest.json',
            'validation-report.txt', 'virtual-validation-report.txt',
            'hardware-matrix.txt', 'KNOWN-LIMITATIONS.txt', 'GATE-DECISION.txt',
            'OCI-CONTRACT.json', 'OCI-USAGE.txt', 'PUBLISHER-HANDOFF.txt',
            'RAW-SHA256SUMS', 'README.md', 'RECOVERY-VERIFICATION.txt',
            'image3-recovery.json', 'independent-payload-review.txt',
            'recovery-actual-verification.json', 'recovery-attestation.jsonl',
            'recovery-policy-tests.json', 'recovery-predicate.json',
            'recovery-signature-verification.json', 'source-repack.json')
FILES = {IMAGE: 'image/' + IMAGE,
         **{name: 'metadata/' + name for name in METADATA},
         'source-notices.tar.gz': 'notices/source-notices.tar.gz'}
PREFIX = 'application/vnd.oci.image.'
LABELS = {
    'org.opencontainers.image.title': 'Radxa CM3 Debian 13 Trixie CLI — Beta 1',
    'org.opencontainers.image.description': 'Experimental OS image distribution artifact, not runnable. Scoped software/virtual checks passed; physical CM3 hardware UNTESTED.',
    'org.opencontainers.image.version': VERSION,
    'org.opencontainers.image.revision': REVISION,
    'org.opencontainers.image.source': 'https://github.com/blockdyor/radxa-cm3-debian-cli',
    'org.opencontainers.image.licenses': 'NOASSERTION',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def bundle_hashes(bundle, pinned=True):
    require(not bundle.is_symlink() and bundle.is_dir(), 'bundle must be a real directory')
    require({p.name for p in bundle.iterdir()} == set(FILES), 'bundle inventory differs from exact allowlist')
    for name in FILES:
        p = bundle / name
        require(not p.is_symlink() and p.is_file() and p.stat().st_size > 0, 'invalid input: ' + name)
    sums = {}
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
        require(match is not None, 'invalid checksum line')
        sha, name = match.groups()
        require(name not in sums, 'duplicate checksum')
        sums[name] = sha
    require(set(sums) == set(FILES) - {'SHA256SUMS'}, 'checksum inventory differs')
    for name in set(FILES) - {'SHA256SUMS'}:
        require(digest(bundle / name) == sums[name], 'checksum mismatch: ' + name)
    if pinned:
        require(sums[IMAGE] == IMAGE_SHA, 'wrong retained image lineage')
        require(sums['source-notices.tar.gz'] == SOURCE_SHA, 'wrong retained source lineage')
        require(digest(bundle / 'SHA256SUMS') == SUMS_SHA, 'wrong finalized metadata inventory')
        require((bundle / 'RAW-SHA256SUMS').read_text() == f'{RAW_SHA}  {RAW}\n', 'wrong raw identity')
        contract = json.loads((bundle / 'OCI-CONTRACT.json').read_text())
        require(contract['inputs'] == FILES and contract['labels'] == LABELS, 'wrong OCI contract')
    return {name: digest(bundle / name) for name in FILES}


def build(bundle, output, pinned=True):
    before = bundle_hashes(bundle, pinned)
    if pinned:
        with lzma.open(bundle / IMAGE, 'rb') as raw:
            require(hashlib.file_digest(raw, 'sha256').hexdigest() == RAW_SHA, 'decompressed image mismatch')
    output.mkdir(parents=True, exist_ok=False)
    blobs = output / 'blobs' / 'sha256'
    blobs.mkdir(parents=True)
    layer_path = output / 'layer.tar'
    try:
        with tarfile.open(layer_path, 'w', format=tarfile.USTAR_FORMAT) as tar:
            for name, target in sorted(FILES.items(), key=lambda item: item[1]):
                p = bundle / name
                info = tarfile.TarInfo(target)
                info.size = p.stat().st_size
                info.mode = 0o644
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                with p.open('rb') as f:
                    tar.addfile(info, f)
        require(before == bundle_hashes(bundle, pinned), 'inputs changed while packaging')
        sha = digest(layer_path)
        layer = {'mediaType': PREFIX + 'layer.v1.tar', 'digest': 'sha256:' + sha, 'size': layer_path.stat().st_size}
        layer_path.rename(blobs / sha)

        def blob(value, media_type):
            data = encode(value)
            sha = hashlib.sha256(data).hexdigest()
            (blobs / sha).write_bytes(data)
            return {'mediaType': media_type, 'digest': 'sha256:' + sha, 'size': len(data)}

        config = blob({'architecture': 'arm64', 'os': 'linux',
                       'config': {'Labels': LABELS},
                       'rootfs': {'type': 'layers', 'diff_ids': [layer['digest']]}}, PREFIX + 'config.v1+json')
        manifest = blob({'schemaVersion': 2, 'mediaType': PREFIX + 'manifest.v1+json',
                         'config': config, 'layers': [layer], 'annotations': LABELS}, PREFIX + 'manifest.v1+json')
        manifest['annotations'] = {'org.opencontainers.image.ref.name': VERSION}
        (output / 'index.json').write_bytes(encode({'schemaVersion': 2, 'mediaType': PREFIX + 'index.v1+json', 'manifests': [manifest]}))
        (output / 'oci-layout').write_bytes(encode({'imageLayoutVersion': '1.0.0'}))
        verify(output, bundle, pinned)
        return manifest['digest']
    except BaseException:
        shutil.rmtree(output)
        raise


def verify(layout, bundle, pinned=True):
    expected = bundle_hashes(bundle, pinned)
    require(json.loads((layout / 'oci-layout').read_text()) == {'imageLayoutVersion': '1.0.0'}, 'wrong layout version')

    def load(desc):
        require(re.fullmatch(r'sha256:[0-9a-f]{64}', desc['digest']) is not None, 'invalid blob digest')
        p = layout / 'blobs' / 'sha256' / desc['digest'].split(':')[1]
        require(p.stat().st_size == desc['size'] and digest(p) == desc['digest'][7:], 'blob integrity failure')
        return p

    index = json.loads((layout / 'index.json').read_text())
    # OCI index mediaType is optional; skopeo 1.9 omits it on local copies.
    require(index['schemaVersion'] == 2 and index.get('mediaType', PREFIX + 'index.v1+json') == PREFIX + 'index.v1+json', 'wrong index schema/type')
    require(len(index['manifests']) == 1, 'expected one manifest')
    desc = index['manifests'][0]
    require(desc.get('annotations') == {'org.opencontainers.image.ref.name': VERSION}, 'wrong version reference')
    require(desc['mediaType'] == PREFIX + 'manifest.v1+json', 'wrong manifest type')
    manifest = json.loads(load(desc).read_text())
    require(manifest['schemaVersion'] == 2 and manifest['mediaType'] == PREFIX + 'manifest.v1+json', 'wrong manifest schema/type')
    require(manifest['annotations'] == LABELS, 'wrong annotations')
    require(manifest['config']['mediaType'] == PREFIX + 'config.v1+json', 'wrong config type')
    config = json.loads(load(manifest['config']).read_text())
    require(config['config'] == {'Labels': LABELS}, 'unexpected runtime configuration or labels')
    require(config['architecture'] == 'arm64' and config['os'] == 'linux', 'wrong platform')
    require(len(manifest['layers']) == 1, 'expected one layer')
    layer = manifest['layers'][0]
    require(layer['mediaType'] == PREFIX + 'layer.v1.tar', 'wrong layer type')
    require(config['rootfs'] == {'type': 'layers', 'diff_ids': [layer['digest']]}, 'wrong diff id')
    with tarfile.open(load(layer), 'r:') as tar:
        members = tar.getmembers()
        require([m.name for m in members] == sorted(FILES.values()), 'unexpected/duplicate layer paths')
        reverse = {target: name for name, target in FILES.items()}
        for m in members:
            require(m.isfile() and m.mode == 0o644 and m.uid == m.gid == m.mtime == 0 and not m.uname and not m.gname, 'unsafe or non-normalized member')
            with tar.extractfile(m) as f:
                require(hashlib.file_digest(f, 'sha256').hexdigest() == expected[reverse[m.name]], 'extracted bytes mismatch')
    return desc['digest']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'verify'))
    parser.add_argument('bundle', type=Path)
    parser.add_argument('layout', type=Path)
    args = parser.parse_args()
    try:
        result = build(args.bundle, args.layout) if args.action == 'build' else verify(args.layout, args.bundle)
        print(result)
        print('LOCAL VERIFICATION ONLY. Publication belongs to t_b25bb59f; hardware UNTESTED.')
    except (ValueError, OSError, KeyError, tarfile.TarError) as error:
        parser.exit(1, str(error) + '\n')
