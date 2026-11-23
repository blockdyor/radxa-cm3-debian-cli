#!/usr/bin/env python3
"""Reserve one cumulative experimental image entry under exclusive CI concurrency."""
import json
import os
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'blockdyor/radxa-cm3-debian-cli'
ASSEMBLY_STEP = 'Assemble experimental CM3 disk image'


def admit(ledger, attempts, run_id, revision, hypothesis):
    if ledger.get('maximum_full_image_attempts') != 3 or ledger.get('maximum_concurrent_full_images') != 1:
        raise ValueError('unchanged cumulative three-image limit required')
    if re.fullmatch('[0-9a-f]{40}', revision) is None or not hypothesis.strip():
        raise ValueError('exact revision and specific hypothesis required')
    identities = [(a['run_id'], a['run_attempt']) for a in attempts]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate image history')
    history = {(a['run_id'], a['run_attempt']): a for a in attempts}
    records = ledger.get('full_image_attempts', [])
    recorded = set()
    for record in records:
        key = (int(record['run_url'].rsplit('/', 1)[1]), record['run_attempt'])
        if key in recorded or key not in history or history[key]['commit'] != record['commit']:
            raise ValueError('image ledger/history mismatch; no reset allowed')
        recorded.add(key)
    if set(history) != recorded:
        raise ValueError('reconcile previous image entries before another reservation')
    if any(a['run_id'] == run_id or a['status'] != 'completed' for a in attempts):
        raise ValueError('current run already entered assembly or previous entry still active')
    if len(attempts) >= 3:
        raise ValueError('cumulative image budget exhausted')
    if hypothesis in {r['hypothesis'] for r in records}:
        raise ValueError('unchanged image hypothesis prohibited')
    return dict(status='ADMITTED', commit=revision, run_id=run_id, run_attempt=1,
                cumulative_attempts=len(attempts) + 1, maximum_attempts=3,
                hypothesis=hypothesis, history=attempts)


def fetch(path):
    request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + path,
                                    headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                                             'Accept': 'application/vnd.github+json',
                                             'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pages(path, field):
    items = []
    total = None
    for page in range(1, 101):
        data = fetch(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        if total is not None and total != data['total_count']:
            raise ValueError('history changed during pagination')
        total = data['total_count']
        items.extend(data[field])
        if len(items) >= total:
            break
    if len(items) != total:
        raise ValueError('incomplete image history')
    return items


def main(check_only=False):
    if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or
            os.environ.get('GITHUB_RUN_ATTEMPT') != '1' or
            os.environ.get('GITHUB_REF') != 'refs/heads/dev/cm3-debian-cli'):
        raise ValueError('canonical development branch and first workflow attempt required')
    run_id = int(os.environ['GITHUB_RUN_ID'])
    revision = os.environ['GITHUB_SHA']
    attempts = []
    runs = pages('/actions/runs', 'workflow_runs')
    current = next((r for r in runs if r['id'] == run_id), None)
    if current is None or current['head_sha'] != revision or current['run_attempt'] != 1:
        raise ValueError('current run identity mismatch')
    for run in runs:
        for number in range(1, run['run_attempt'] + 1):
            jobs = pages(f'/actions/runs/{run["id"]}/attempts/{number}/jobs', 'jobs')
            entered = [step for job in jobs for step in job.get('steps', [])
                       if step['name'] == ASSEMBLY_STEP and step.get('started_at') and
                       step.get('conclusion') != 'skipped']
            if len(entered) > 1:
                raise ValueError('multiple assembly entries in one workflow attempt')
            if entered:
                attempts.append(dict(run_id=run['id'], run_attempt=number,
                                     commit=run['head_sha'], status=run['status']))
    ledger = json.loads((ROOT / 'docs/cm3-cli/attempts.json').read_text())
    result = admit(ledger, attempts, run_id, revision, os.environ['HYPOTHESIS'])
    if check_only:
        print(json.dumps(dict(result, status='PRECHECK; NOT A RESERVATION'), indent=2))
        return
    # The host runner owns preflight-work; the root builder owns package-work.
    destination = ROOT / 'preflight-work/evidence/image-admission.json'
    with destination.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    main(parser.parse_args().check_only)
