#!/usr/bin/env python3
"""Read-only source-package admission; run under cm3-phase-b-exclusive concurrency."""
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'blockdyor/radxa-cm3-debian-cli'
WORKFLOW = 396827381


def admit(ledger, runs, run_id, sha):
    if ledger['maximum_package_attempts'] != 6:
        raise ValueError('expected the cumulative owner-authorized six-attempt limit')
    by_id = {r['id']: r for r in runs}
    if len(by_id) != len(runs) or run_id not in by_id:
        raise ValueError('duplicate or missing current workflow run')
    for item in ledger['package_attempts']:
        observed = by_id.get(int(item['run_url'].rsplit('/', 1)[1]))
        if (observed is None or observed['head_sha'] != item['commit'] or
                observed['run_attempt'] != item['run_attempt']):
            raise ValueError('historical ledger/run mismatch; no reset or deleted history allowed')
    current = by_id[run_id]
    if (current['head_sha'] != sha or current['run_attempt'] != 1 or
            any(r['event'] != 'workflow_dispatch' or r['workflow_id'] != WORKFLOW for r in runs)):
        raise ValueError('wrong revision/workflow or prohibited rerun')
    used = sum(r['run_attempt'] for r in runs)
    if used > ledger['maximum_package_attempts']:
        raise ValueError('package attempt budget exhausted; seventh attempt prohibited')
    if any(r['id'] != run_id and r['status'] == 'in_progress' for r in runs):
        raise ValueError('another package attempt is running')
    return {'status': 'ADMITTED', 'run_id': run_id, 'commit': sha,
            'workflow_id': WORKFLOW, 'cumulative_attempts': used, 'maximum_attempts': 6,
            'runs': [{k: r[k] for k in ['id', 'head_sha', 'run_attempt', 'status', 'conclusion']}
                     for r in runs]}


def main():
    if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or
            os.environ.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('canonical repository, first run only; reruns prohibited')
    token = os.environ['GH_TOKEN']
    runs = []
    total = None
    for page in range(1, 101):
        request = urllib.request.Request(
            f'https://api.github.com/repos/{REPOSITORY}/actions/workflows/{WORKFLOW}/runs'
            f'?per_page=100&page={page}',
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        if total is not None and total != data['total_count']:
            raise ValueError('run history changed during pagination; retry inspection, not build')
        total = data['total_count']
        runs.extend(data['workflow_runs'])
        if len(runs) >= total:
            break
    if len(runs) != total:
        raise ValueError('incomplete run history')
    ledger = json.loads((ROOT / 'docs/cm3-cli/attempts.json').read_text())
    result = admit(ledger, runs, int(os.environ['GITHUB_RUN_ID']), os.environ['GITHUB_SHA'])
    destination = ROOT / 'preflight-work/evidence/package-admission.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
