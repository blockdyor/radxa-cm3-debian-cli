#!/usr/bin/env python3
"""Offline experimental-assembly policy; not an evidence verifier or builder."""

import argparse
import json
from pathlib import Path


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path,
                        help='JSON file containing the stage A object')
    parser.add_argument('--output', required=True, type=Path,
                        help='new JSON decision file (must not exist)')
    args = parser.parse_args()
    try:
        result = admit(json.loads(args.evidence.read_text(encoding='utf-8')))
        with args.output.open('x', encoding='utf-8') as output:
            output.write(json.dumps(result, indent=2) + '\n')
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
