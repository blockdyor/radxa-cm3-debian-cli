#!/usr/bin/env python3
"""Offline experimental-assembly policy; not an evidence verifier or builder."""

import json
import sys


REQUIRED = (
    'authenticated_inputs',
    'package_configuration',
    'exact_target_rootfs',
    'offline_security',
    'exact_head_sonar',
)


def admit(stage_a):
    """Require literal PASS receipts; runtime qualification stays blocked."""
    if not isinstance(stage_a, dict):
        raise ValueError('stage_a must be a JSON object')
    invalid = [name for name in REQUIRED if stage_a.get(name) != 'PASS']
    if invalid:
        raise ValueError('stage A requires literal PASS: ' + ', '.join(invalid))
    return {
        'experimental_assembly': 'ALLOWED',
        'stable_release': 'BLOCKED',
        'hardware': 'UNTESTED',
    }


def main():
    # The policy needs JSON data, never authority to read or write agent-supplied paths.
    if len(sys.argv) != 1:
        raise SystemExit('Read stage A JSON from stdin; no filesystem arguments are accepted')
    try:
        result = admit(json.load(sys.stdin))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
