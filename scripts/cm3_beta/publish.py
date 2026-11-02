#!/usr/bin/env python3
"""Publish only the independently reviewed beta1 OCI data artifact; never build an OS."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

import package_oci as recipe

REPO = 'blockdyor/radxa-cm3-debian-cli'
TAG = 'v0.1.0-beta.1'
DIGEST = 'sha256:c73e39347a86a6def34eec67eb637c6712bbfab4e2da0aa266551b377eb0b344'
API = 'https://api.github.com'
REGISTRY = 'https://ghcr.io'
INVENTORY = Path(__file__).with_name('approved-inventory.json')


def request(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=120) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def api(path, token):
    status, body, _ = request(API + path, {'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
    return status, json.loads(body)


def existing_digest(status, body):
    if status == 404:
        errors = json.loads(body).get('errors', [])
        if not errors or any(e.get('code') not in ('NAME_UNKNOWN', 'MANIFEST_UNKNOWN') for e in errors):
            raise ValueError('registry absence not proven by authenticated response')
        return None
    if status != 200:
        raise ValueError(f'authenticated registry lookup failed: HTTP {status}')
    actual = 'sha256:' + hashlib.sha256(body).hexdigest()
    if actual != DIGEST:
        raise ValueError('refusing conflicting existing version: ' + actual)
    return actual


def registry(path, token, actor):
    # Registry bearer tokens can expire while multi-gigabyte inputs transfer.
    basic = base64.b64encode((actor + ':' + token).encode()).decode()
    status, body, _ = request(REGISTRY + '/token?service=ghcr.io&scope=repository:' + REPO + ':pull,push',
                              {'Authorization': 'Basic ' + basic})
    if status != 200:
        raise ValueError(f'namespace token authorization HTTP {status}')
    bearer = json.loads(body)['token']
    return request(REGISTRY + '/v2/' + REPO + path,
                   {'Authorization': 'Bearer ' + bearer,
                    'Accept': 'application/vnd.oci.image.manifest.v1+json'})


def main():
    if (os.environ.get('GITHUB_REPOSITORY') != REPO or
            os.environ.get('GITHUB_REF') != 'refs/heads/main' or
            os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch' or
            os.environ.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('canonical first-attempt manual main workflow required')
    token = os.environ['GITHUB_TOKEN']
    actor = os.environ['GITHUB_ACTOR']
    status, release = api(f'/repos/{REPO}/releases/tags/{TAG}', token)
    if status != 200 or release['draft'] or not release['prerelease']:
        raise ValueError('published prerelease required')
    status, ref = api(f'/repos/{REPO}/git/ref/tags/{TAG}', token)
    if status != 200 or ref['object'] != {'sha': recipe.REVISION, 'type': 'commit',
            'url': f'{API}/repos/{REPO}/git/commits/{recipe.REVISION}'}:
        raise ValueError('release tag must point directly at reviewed built source')
    approved = json.loads(INVENTORY.read_text())['inventory']
    assets = release['assets']
    if len(assets) != len(approved) or {a['name'] for a in assets} != set(approved):
        raise ValueError('release asset inventory differs')
    for asset in assets:
        expected = approved[asset['name']]
        if asset['size'] != expected['bytes'] or asset.get('digest') != 'sha256:' + expected['sha256']:
            raise ValueError('release asset identity differs: ' + asset['name'])

    # The scoped token must authorize the namespace before treating a 404 as absence.
    package_path = '/users/blockdyor/packages/container/radxa-cm3-debian-cli'
    package_status, package = api(package_path, token)
    if package_status not in (200, 404):
        raise ValueError(f'package namespace API HTTP {package_status}: {package.get("message")}')
    if package_status == 200 and package.get('repository', {}).get('full_name') != REPO:
        raise ValueError('existing package is not associated with this repository')
    status, body, _ = registry('/tags/list', token, actor)
    if status == 404:
        errors = json.loads(body).get('errors', [])
        if package_status != 404 or not errors or any(e.get('code') != 'NAME_UNKNOWN' for e in errors):
            raise ValueError('namespace absence ambiguous')
    elif status != 200:
        raise ValueError(f'authenticated namespace inspection HTTP {status}')
    status, body, _ = registry('/manifests/' + recipe.VERSION, token, actor)
    prior = existing_digest(status, body)
    print(json.dumps({'namespace_api': package_status, 'version_lookup': status, 'existing_digest': prior}), flush=True)

    with tempfile.TemporaryDirectory(prefix='cm3-beta-', dir=os.environ['RUNNER_TEMP']) as temporary:
        root = Path(temporary)
        bundle = root / 'bundle'
        bundle.mkdir()
        for asset in assets:
            name = asset['name']
            url = asset['browser_download_url']
            if url != f'https://github.com/{REPO}/releases/download/{TAG}/{name}':
                raise ValueError('unexpected public input URL')
            # No credential is sent to public release storage or redirect targets.
            with urllib.request.urlopen(url, timeout=120) as source, (bundle / name).open('xb') as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            expected = approved[name]
            if (bundle / name).stat().st_size != expected['bytes'] or recipe.digest(bundle / name) != expected['sha256']:
                raise ValueError('download integrity failure: ' + name)
        layout = root / 'layout'
        if recipe.build(bundle, layout) != DIGEST or recipe.verify(layout, bundle) != DIGEST:
            raise ValueError('reviewed OCI digest mismatch')
        auth = root / 'registry-auth.json'
        subprocess.run(['skopeo', 'login', '--authfile', str(auth), '--username', actor,
                        '--password-stdin', 'ghcr.io'], input=token.encode(), check=True)
        auth.chmod(0o600)
        # Single authorized publisher; recheck immediately before writing.
        status, body, _ = registry('/manifests/' + recipe.VERSION, token, actor)
        if existing_digest(status, body) is None:
            subprocess.run(['skopeo', 'copy', '--authfile', str(auth), '--preserve-digests',
                'oci:' + str(layout) + ':' + recipe.VERSION,
                'docker://ghcr.io/' + REPO + ':' + recipe.VERSION], check=True)
        status, body, _ = registry('/manifests/' + recipe.VERSION, token, actor)
        if existing_digest(status, body) != DIGEST:
            raise ValueError('remote post-push digest missing')
        pulled = root / 'pulled'
        subprocess.run(['skopeo', 'copy', '--authfile', str(auth), '--preserve-digests',
            'docker://ghcr.io/' + REPO + '@' + DIGEST,
            'oci:' + str(pulled) + ':' + recipe.VERSION], check=True)
        if recipe.verify(pulled, bundle) != DIGEST:
            raise ValueError('remote roundtrip mismatch')
        status, package = api(package_path, token)
        if status != 200 or package.get('repository', {}).get('full_name') != REPO:
            raise ValueError('post-push package/repository association unverified')
        print(json.dumps({'manifest': DIGEST, 'roundtrip': 'PASS', 'files': len(approved),
                          'visibility': package['visibility'], 'repository': REPO,
                          'package_url': package['html_url'], 'hardware': 'UNTESTED'}), flush=True)


if __name__ == '__main__':
    main()
