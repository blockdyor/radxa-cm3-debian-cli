#!/usr/bin/env python3
"""Produce experimental Stage A evidence from this job's actual checks, never boot proof."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cm3_assembly', ROOT / 'scripts/cm3-assemble-image.py')
assembly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembly)
PROJECT = 'blockdyor_radxa-cm3-debian-cli'


def sonar_get(path):
    with urllib.request.urlopen('https://sonarcloud.io/api/' + path, timeout=30) as response:
        return json.load(response)


def verify_sonar(revision):
    requests = sonar_get('project_pull_requests/list?project=' + PROJECT)['pullRequests']
    current = next((item for item in requests if item['key'] == '1'), None)
    if (current is None or current.get('commit', {}).get('sha') != revision or
            current.get('status', {}).get('qualityGateStatus') != 'OK'):
        raise ValueError('exact-head Sonar PR #1 quality gate OK required')
    issues = sonar_get('issues/search?componentKeys=' + PROJECT + '&pullRequest=1&resolved=false&ps=1')
    hotspots = sonar_get('hotspots/search?projectKey=' + PROJECT + '&pullRequest=1&ps=1')
    if issues['total'] != 0 or hotspots['paging']['total'] != 0:
        raise ValueError('unresolved Sonar issues or security hotspots block assembly')
    return dict(source_revision=revision, gate='OK', unresolved_issues=0, hotspots=0,
                analysis_date=current['analysisDate'])


def regression(work, revision):
    """Run the complete offline suite with real dependencies; any skip blocks admission."""
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/cm3-cli'))
    with (work / 'evidence/image-offline-tests.log').open('x') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    report = dict(status='PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',
                  source_revision=revision, run_id=os.environ['GITHUB_RUN_ID'],
                  tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skips=len(result.skipped))
    with (work / 'evidence/image-offline-tests.json').open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'PASS' or report['tests'] == 0:
        raise ValueError('complete offline regressions must pass without skips; see image-offline-tests.log')
    return report


def produce(work):
    revision = assembly.boundary(work)
    receipt = assembly.authenticate(work, revision, os.environ['GITHUB_RUN_ID'])
    tests = json.loads(assembly.regular(work / 'evidence/image-offline-tests.json').read_text())
    if (tests.get('status') != 'PASS' or tests.get('source_revision') != revision or
            tests.get('run_id') != os.environ['GITHUB_RUN_ID'] or
            type(tests.get('tests')) is not int or tests['tests'] < 1 or
            any(tests.get(name) != 0 for name in ['failures', 'errors', 'skips'])):
        raise ValueError('same-run exact-head offline test evidence required')
    sonar = verify_sonar(revision)
    checks = {name: 'PASS' for name in assembly.policy.REQUIRED}
    decision = assembly.policy.admit(checks)
    files = ['result.json', 'arm64-result.json', 'board-lifecycle.json', 'board-manifest.json',
             'local-repository.json', 'rsdk-profile.json', 'rsdk-profile-result.json',
             'rsdk-profile-packages.tsv', 'image-offline-tests.json']
    report = dict(source_revision=revision, run_id=os.environ['GITHUB_RUN_ID'],
                  source_lock_sha256=receipt['source_lock_sha256'], checks=checks,
                  receipt=receipt, sonar=sonar, decision=decision,
                  evidence_sha256={name: assembly.profile.probe.digest(assembly.regular(work / 'evidence' / name))
                                   for name in files})
    with (work / 'evidence/image-stage-a.json').open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    return report


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ['tests', 'produce', 'sonar']:
        raise SystemExit('usage: cm3-image-stage-a.py {tests|produce|sonar}; fixed external /work only')
    work = Path('/work')
    try:
        revision = assembly.boundary(work)
        if sys.argv[1] == 'sonar':
            result = verify_sonar(revision)
        elif sys.argv[1] == 'tests':
            # Source compilation requires an empty /work. Keep cheap checks outside it.
            checks = Path('/checks')
            (checks / 'evidence').mkdir(parents=True)
            result = regression(checks, revision)
        else:
            result = produce(work)
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
