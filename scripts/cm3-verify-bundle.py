#!/usr/bin/env python3
"""Verify producer-attested ciphertext; never decrypt or install an APT key/source.

Requires the producer's public attestation bundle and independently approved
commit and ciphertext SHA256. The JSON receipt is not signed import authority.
Signature, certificate identity and provenance policy are enforced by official
`gh attestation verify`, not by parsing untrusted statement metadata here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = 'blockdyor/radxa-cm3-debian-cli'
WORKFLOW = REPOSITORY + '/.github/workflows/build.yaml'
SOURCE_REF = 'refs/heads/dev/cm3-debian-cli'


def verify(artifact, attestation, approved_sha, expected_sha256):
    if re.fullmatch('[0-9a-f]{40}', approved_sha) is None:
        raise ValueError('approved SHA must be a full lowercase Git commit')
    if re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('expected SHA256 must be a full lowercase digest')
    for path in (artifact, attestation):
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError('regular non-symlink input required: ' + str(path))
    # Verify private snapshots, so gh and the receipt always refer to the same bytes.
    with tempfile.TemporaryDirectory(prefix='cm3-admission-') as temporary:
        subject = Path(temporary) / 'cm3-recovery.cms'
        bundle = Path(temporary) / 'attestation.jsonl'
        shutil.copyfile(artifact, subject)
        shutil.copyfile(attestation, bundle)
        with subject.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected_sha256:
            raise ValueError('ciphertext digest does not match independent approval')
        with bundle.open('rb') as stream:
            bundle_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        subprocess.run([
            'gh', 'attestation', 'verify', str(subject), '--bundle', str(bundle),
            '--hostname', 'github.com', '--repo', REPOSITORY,
            '--signer-digest', approved_sha,
            '--cert-identity', 'https://github.com/' + WORKFLOW + '@' + SOURCE_REF,
            '--source-digest', approved_sha, '--source-ref', SOURCE_REF,
            '--cert-oidc-issuer', 'https://token.actions.githubusercontent.com',
            '--predicate-type', 'https://slsa.dev/provenance/v1',
            '--deny-self-hosted-runners',
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, timeout=120)
    return {
        'scope': 'ciphertext-only; no decryption, APT-key approval or import',
        'ciphertext_sha256': digest, 'attestation_sha256': bundle_digest,
        'repository': REPOSITORY, 'signer_workflow': WORKFLOW,
        'source_digest': approved_sha, 'signer_digest': approved_sha,
        'source_ref': SOURCE_REF,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--attestation', type=Path, required=True)
    parser.add_argument('--approved-sha', required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    try:
        receipt = verify(args.artifact, args.attestation, args.approved_sha, args.expected_sha256)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('admission refused: ' + str(error)[:1000], file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
