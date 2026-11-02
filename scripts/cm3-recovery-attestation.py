#!/usr/bin/env python3
"""Sign/verify reviewed image3 recovery evidence, never recreate build provenance.

The hosted job validates committed review evidence and original GitHub metadata.
Actual payload hashing was local and independently reviewed, not hosted execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'project/cm3-cli/image3-recovery.json'
REPOSITORY = 'blockdyor/radxa-cm3-debian-cli'
REF = 'refs/heads/dev/cm3-debian-cli'
WORKFLOW = 'https://github.com/' + REPOSITORY + '/.github/workflows/build.yaml@' + REF
PREDICATE = 'https://github.com/' + REPOSITORY + '/attestations/image-recovery/v1'
BUILT_SOURCE = 'b71152296933808f99d7dc169fc6811861a9001b'
RUN = 41331537371


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular non-symlink file required: ' + str(path))
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate(manifest):
    if (manifest['schema'] != 1 or manifest['repository'] != REPOSITORY or
            manifest['verificationMode'] != 'independently-reviewed-local-evidence' or
            manifest['hostedPayloadRehash'] is not False or
            manifest['originalBuildAttestationIssued'] is not False or
            manifest['hardware'] != 'UNTESTED' or
            manifest['originalProducer'] != dict(run=RUN, attempt=1, source=BUILT_SOURCE,
                conclusion='failure', assembly='success', provenance='skipped') or
            manifest['independentReview']['verdict'] != 'SCOPED PASS; F1 source packaging corrected separately'):
        raise ValueError('recovery claim/scope does not match reviewed image3')
    names = set()
    for item in manifest['subjects']:
        name = item['name']
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) or name in names or
                not re.fullmatch('[0-9a-f]{64}', item['sha256']) or
                type(item['bytes']) is not int or item['bytes'] <= 0):
            raise ValueError('invalid/duplicate recovery subject')
        names.add(name)
    required = {'radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img',
                'radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz',
                'source-notices.tar.gz', 'package-manifest.txt',
                'independent-payload-review.txt', 'source-repack.json'}
    if names != required:
        raise ValueError('complete exact recovery subject set required')
    image = 'radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img'
    fixed = {image: ('d514bf7be20e45771eb043e2e620b22e5d584df0f10afe343d6ae47b28b2beca', 1866085376),
             image + '.xz': ('e189249e76a527b1680b4c1667ca58c923ab59d7567e1792b8019cc537c72e57', 207029824)}
    for item in manifest['subjects']:
        if item['name'] in fixed and (item['sha256'], item['bytes']) != fixed[item['name']]:
            raise ValueError('reviewed image3 identity mismatch')
    retention = manifest['retention']
    if (retention['apiCiphertextZipSha256'] != 'ce21e4b76f2d6de82dd8780486a21d121c8e857159d242702d37d4d9d08719f8' or
            retention['apiCiphertextZipBytes'] != 1771517207 or retention['manifestFiles'] != 563 or
            retention['cmsAuthentication'] != 'PASS; recorded authenticated local recovery' or
            retention['retentionManifestSha256'] != '3801816d71da7f89682049b6557f2d2ee741cf0e8e3cd2114cea4927415a09eb' or
            retention['cmsMemberSha256'] != 'f4278cc0473fd67ced3ec059f1dd99cf36795fcff644b413786d716b045114d2'):
        raise ValueError('original authenticated recovery identity mismatch')
    return manifest


def predicate(manifest, revision):
    if re.fullmatch('[0-9a-f]{40}', revision) is None:
        raise ValueError('full verification source commit required')
    return dict(validate(manifest), verificationSource=revision)


def gh_json(*args):
    result = subprocess.run(['gh', *args], check=True, capture_output=True, text=True, timeout=120)
    return json.loads(result.stdout)


def prepare(revision, output):
    if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or
            os.environ.get('GITHUB_REF') != REF or os.environ.get('GITHUB_SHA') != revision or
            os.environ.get('GITHUB_RUN_ATTEMPT') != '1' or
            os.environ.get('EXPERIMENTAL_IMAGE') != 'false' or
            os.environ.get('PUBLIC_DISTRIBUTION') != 'false'):
        raise ValueError('recovery-only canonical hosted first attempt required')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if actual != revision:
        raise ValueError('checkout source mismatch')
    manifest = validate(json.loads(MANIFEST.read_text()))
    original = gh_json('api', f'repos/{REPOSITORY}/actions/runs/{RUN}')
    if (original['head_sha'] != BUILT_SOURCE or original['run_attempt'] != 1 or
            original['status'] != 'completed' or original['conclusion'] != 'failure'):
        raise ValueError('original run identity/conclusion mismatch')
    jobs = gh_json('api', f'repos/{REPOSITORY}/actions/runs/{RUN}/attempts/1/jobs?per_page=100')
    if jobs['total_count'] != len(jobs['jobs']):
        raise ValueError('incomplete original job metadata')
    assembly = [s for j in jobs['jobs'] for s in j.get('steps', [])
                if s['name'] == 'Assemble experimental CM3 disk image']
    provenance = [j for j in jobs['jobs'] if j['name'] == 'provenance']
    if (len(assembly) != 1 or assembly[0]['conclusion'] != 'success' or
            len(provenance) != 1 or provenance[0]['conclusion'] != 'skipped'):
        raise ValueError('original assembly/provenance evidence mismatch')
    artifact = gh_json('api', f'repos/{REPOSITORY}/actions/artifacts/13098325406')
    retention = manifest['retention']
    if (artifact['workflow_run']['id'] != RUN or artifact['workflow_run']['head_sha'] != BUILT_SOURCE or
            artifact['digest'] != 'sha256:' + retention['apiCiphertextZipSha256'] or
            artifact['size_in_bytes'] != retention['apiCiphertextZipBytes']):
        raise ValueError('original API artifact identity mismatch')
    output.mkdir(exist_ok=False)
    (output / 'recovery-predicate.json').write_text(json.dumps(predicate(manifest, revision), sort_keys=True) + '\n')
    # Also attest the immutable review manifest; do not make it self-referential.
    (output / 'image3-recovery.json').write_bytes(MANIFEST.read_bytes())
    subjects = list(manifest['subjects']) + [dict(name='image3-recovery.json', sha256=digest(MANIFEST))]
    (output / 'recovery-subjects.sha256').write_text(''.join(i['sha256'] + '  ' + i['name'] + '\n' for i in subjects))


def verify(directory, bundle, revision):
    # Snapshot small trusted-policy inputs; payload files are rehashed by gh itself.
    with tempfile.TemporaryDirectory(prefix='cm3-recovery-verify-') as temporary:
        snapshot = Path(temporary) / 'bundle.jsonl'
        if bundle.is_symlink() or not bundle.is_file():
            raise ValueError('regular attestation bundle required')
        snapshot.write_bytes(bundle.read_bytes())
        manifest_file = directory / 'image3-recovery.json'
        if digest(manifest_file) != digest(MANIFEST):
            raise ValueError('manifest differs from approved checkout')
        manifest = validate(json.loads(manifest_file.read_text()))
        expected = predicate(manifest, revision)
        subjects = list(manifest['subjects']) + [dict(name='image3-recovery.json', sha256=digest(manifest_file), bytes=manifest_file.stat().st_size)]
        # Raw need not be distributed twice; its digest is checked on XZ expansion.
        raw = next(i for i in subjects if i['name'].endswith('.img'))
        import lzma
        compressed = directory / (raw['name'] + '.xz')
        h = hashlib.sha256(); size = 0
        with lzma.open(compressed, 'rb') as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > raw['bytes']:
                    raise ValueError('raw decompression size exceeded')
                h.update(chunk)
        if size != raw['bytes'] or h.hexdigest() != raw['sha256']:
            raise ValueError('expanded raw subject mismatch')
        for item in subjects:
            if item is raw:
                continue
            path = directory / item['name']
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('material digest/size mismatch: ' + item['name'])
            results = gh_json('attestation', 'verify', str(path), '--bundle', str(snapshot),
                '--repo', REPOSITORY, '--hostname', 'github.com', '--cert-identity', WORKFLOW,
                '--signer-digest', revision, '--source-digest', revision, '--source-ref', REF,
                '--cert-oidc-issuer', 'https://token.actions.githubusercontent.com',
                '--predicate-type', PREDICATE, '--deny-self-hosted-runners', '--format', 'json')
            statements = [r['verificationResult']['statement'] for r in results]
            if not statements or any(s['predicateType'] != PREDICATE or s['predicate'] != expected for s in statements):
                raise ValueError('authenticated recovery predicate differs from approved policy')
            # Each verified signature must bind the whole approved set, including raw.
            approved = {(i['name'], i['sha256']) for i in subjects}
            if any({(i['name'], i['digest']['sha256']) for i in s['subject']} != approved for s in statements):
                raise ValueError('authenticated recovery subject set mismatch')
    return dict(status='PASS', type=PREDICATE, verification_source=revision,
                subjects=len(subjects), raw_sha256=raw['sha256'], hardware='UNTESTED',
                scope='new reviewed-local recovery attestation; NOT original build provenance')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'verify'])
    parser.add_argument('--approved-sha', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            prepare(args.approved_sha, args.directory)
        else:
            if args.bundle is None:
                raise ValueError('public attestation bundle required')
            print(json.dumps(verify(args.directory, args.bundle, args.approved_sha), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('recovery refused: ' + str(error)[:1000], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
