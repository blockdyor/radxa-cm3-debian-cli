#!/usr/bin/env python3
"""Offline, conservative comparison of two bounded result envelopes."""
import argparse
import hashlib
import json
import math
from pathlib import PurePosixPath
import sys

from common import make_result, add_record, validate_result, emit_result
from bench import read_json, finite, measurements, PROCEDURES

BANNER = 'SYNTHETIC FIXTURE OUTPUT - NOT CM3 EVIDENCE'
ESSENTIAL = ('protocol_id', 'duration_s', 'memory_mib', 'file_mib', 'tool_versions', 'sustained',
             'module_revision', 'carrier_revision', 'ram_sku', 'cooling', 'orientation',
             'fan_control', 'ambient_degc', 'power', 'meter_uncertainty', 'storage',
             'filesystem', 'fill', 'cache_state', 'network', 'logger_overhead', 'warmup',
             'source_lock', 'debian', 'kernel', 'dtb', 'bootloader', 'firmware', 'cpu_policy', 'zram')


def compare(baseline, candidate):
    for result in (baseline, candidate):
        validate_result(result)
        for source in result['sources']:
            path = PurePosixPath(source['path_or_ref'])
            if path.is_absolute() or '..' in path.parts or '\\' in str(path):
                raise ValueError('unsafe raw artifact reference')
        if result['kind'] != 'benchmark' or not result['authorization']['execute']:
            raise ValueError('only executed benchmark results can be compared')
        names = [r['name'] for r in result['records']]
        auth = result['authorization']
        if any(n.startswith(('cpu.', 'memory.', 'storage.', 'network.')) for n in names) and not auth['load']:
            raise ValueError('load authorization missing')
        if any(n.startswith('storage.') for n in names) and not auth['write']:
            raise ValueError('write authorization missing')
        if any(n.startswith('network.') for n in names) and not auth['network']:
            raise ValueError('network authorization missing')
        # Fixture provenance must not be removable by toggling only the boolean.
        if not result['provenance']['synthetic'] and (result['provenance'].get('fixture_id') or
                result['provenance']['origin'] == 'fixture' or
                any(r.get('source') == 'fixture' for r in result['records'])):
            raise ValueError('synthetic result relabeled live')
    synthetic = any(x['provenance']['synthetic'] for x in (baseline, candidate))
    ids = [x['provenance'].get('fixture_id') for x in (baseline, candidate) if x['provenance']['synthetic']]
    result = make_result('comparison', synthetic=synthetic,
                         fixture_id='+'.join(ids) if synthetic else None)
    result['provenance']['origin'] = 'derived'
    result['provenance']['input_run_ids'] = [baseline['run_id'], candidate['run_id']]
    bc, cc = baseline['conditions'], candidate['conditions']
    reasons = []
    for source in (baseline, candidate):
        records = {r['name']: r for r in source['records']}
        procedures = {name.split('.')[0] for name in records}
        for procedure in procedures:
            raw_record = records.get(procedure+'.raw')
            if procedure not in PROCEDURES or not raw_record or raw_record['status'] != 'ok':
                reasons.append('missing raw evidence '+procedure)
                continue
            raw = raw_record['value']
            digest = hashlib.sha256(json.dumps(raw, allow_nan=False, sort_keys=True).encode()).hexdigest()
            if not any(s['path_or_ref'] == procedure+'.raw' and s['sha256'] == digest for s in source['sources']):
                reasons.append('raw digest mismatch '+procedure)
            try:
                expected = measurements(procedure, raw)
            except (ValueError, KeyError, TypeError):
                reasons.append('malformed raw evidence '+procedure)
                continue
            for name, value, unit in expected:
                metric = records.get(procedure+'.'+name)
                if not metric or metric['status'] != 'ok' or metric['value'] != value or metric['unit'] != unit:
                    reasons.append('raw metric mismatch '+procedure+'.'+name)
    if bc.get('role') != 'baseline' or cc.get('role') != 'candidate':
        reasons.append('baseline/candidate roles do not match')
    for key in ESSENTIAL:
        if bc.get(key) is None or cc.get(key) is None or bc.get(key) != cc.get(key):
            reasons.append('unknown or mismatched '+key)
    if not bc.get('image_hash') or not cc.get('image_hash'):
        reasons.append('image identities unknown')
    if baseline['errors'] or candidate['errors']:
        reasons.append('input execution errors')
    for x in (bc, cc):
        if x.get('failures') not in ([], '') or x.get('exclusions') not in ([], ''):
            reasons.append('failures/exclusions unknown or present')
    def indexed(source):
        records = {r['name']: r for r in source['records']}
        if len(records) != len(source['records']):
            raise ValueError('duplicate metric names')
        return records
    b, c = indexed(baseline), indexed(candidate)
    if any(name.startswith('boot-ssh.') for name in set(b) | set(c)):
        for key in ('clock', 'observer_ref', 'start_event', 'end_event', 'authentication', 'host_key_policy', 'uncertainty_s'):
            be, ce = bc.get('boot_events', {}), cc.get('boot_events', {})
            if not isinstance(be, dict) or not isinstance(ce, dict) or be.get(key) is None or ce.get(key) is None or be[key] != ce[key]:
                reasons.append('unknown or mismatched boot method '+key)
    if any(name.startswith(('cpu.', 'memory.')) for name in set(b) | set(c)):
        for key in ('thermal_zone', 'thermal_abort_degc', 'thermal_observer_ref'):
            if bc.get(key) is None or cc.get(key) is None or bc[key] != cc[key]:
                reasons.append('unknown or mismatched '+key)
    if 'memory.allocated' in b and 'memory.allocated' in c and b['memory.allocated']['value'] != c['memory.allocated']['value']:
        reasons.append('different actual memory allocation')
    if not b or not c:
        reasons.append('empty benchmark input')
    if any((name not in b or name not in c or
           b[name]['status'] != 'ok' or c[name]['status'] != 'ok' or b[name]['unit'] != c[name]['unit'])
           for name in set(b) | set(c)):
        reasons.append('metric sets/statuses/units do not match')
    lines = [BANNER if synthetic else 'APPROVED INPUT COMPARISON - NOT HARDWARE QUALIFICATION',
             'Hardware: UNTESTED. Gates G0-G7: NOT EVALUATED.',
             'Single-run descriptive comparison only; no statistical benefit or G4 PASS.']
    for name in sorted(set(b) | set(c)):
        br, cr = b.get(name), c.get(name)
        if not br or not cr or br['status'] != 'ok' or cr['status'] != 'ok':
            reasons.append('incomplete metric '+name)
            add_record(result, name, 'unavailable', reason='incomplete-input')
            lines.append(name+': unavailable/error (retained in input_status)')
            continue
        if br['unit'] != cr['unit']:
            reasons.append('unit mismatch '+name)
            add_record(result, name, 'unavailable', reason='unit-mismatch')
            continue
        values = {'baseline': br['value'], 'candidate': cr['value'], 'delta': None, 'percent': None}
        bv, cv = br['value'], cr['value']
        if not reasons and type(bv) in (int, float) and type(cv) in (int, float):
            finite(bv, -1e20, 1e20)
            finite(cv, -1e20, 1e20)
            delta = cv-bv
            pct = None if bv == 0 else delta/abs(bv)*100
            if math.isfinite(delta) and (pct is None or math.isfinite(pct)):
                values.update(delta=delta, percent=pct)
        add_record(result, name, 'ok', value=values, unit=br['unit'])
        if not name.endswith('.raw'):
            lines.append(name+': '+('descriptive values retained' if values['delta'] is None else
                         f"baseline={bv:g}, candidate={cv:g}, delta={values['delta']:g} {br['unit'] or ''}"))
    add_record(result, 'comparison.input_status', 'ok', value=[
        {'run_id': x['run_id'], 'records': [{'name': r['name'], 'status': r['status'],
          'reason': r.get('reason')} for r in x['records']], 'errors': x['errors'],
         'conditions': x['conditions']} for x in (baseline, candidate)])
    verdict = 'INCONCLUSIVE' if reasons else 'DESCRIPTIVE ONLY'
    lines.insert(3, 'Conclusion: '+verdict)
    if reasons:
        lines.append('Controls: '+'; '.join(sorted(set(reasons))))
        # No earlier metric may retain a delta if a later metric invalidates the pair.
        for record in result['records']:
            if isinstance(record.get('value'), dict) and 'delta' in record['value']:
                record['value']['delta'] = record['value']['percent'] = None
    add_record(result, 'comparison.summary', 'ok', value='\n'.join(lines))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--output')
    args = p.parse_args()
    try:
        baseline, candidate = read_json(args.baseline), read_json(args.candidate)
        result = compare(baseline, candidate)
        emit_result(result, args.output)
        statuses = [r['status'] for x in (baseline, candidate) for r in x['records']]
        return 4 if 'error' in statuses or baseline['errors'] or candidate['errors'] else (3 if 'unavailable' in statuses or 'not_run' in statuses else 0)
    except (OSError, ValueError, KeyError, TypeError):
        print('Invalid result envelope or unsafe path', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
