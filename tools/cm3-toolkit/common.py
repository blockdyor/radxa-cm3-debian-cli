"""Shared, dependency-free cm3-toolkit/v1 results and no-clobber output."""
import datetime
import json
import math
import os
import re
import stat
import uuid

SCHEMA_VERSION = 'cm3-toolkit/v1'
KINDS = {'inspection', 'plan', 'benchmark', 'comparison', 'compatibility'}
STATUSES = {'ok', 'unavailable', 'error', 'not_run'}


def make_result(kind, *, synthetic, fixture_id=None, conditions=None):
    return {
        'schema_version': SCHEMA_VERSION, 'kind': kind,
        'run_id': uuid.uuid4().hex, 'target': 'radxa-cm3-rpi-cm4-io',
        'provenance': {'synthetic': synthetic, 'fixture_id': fixture_id,
                       'origin': 'fixture' if synthetic else
                       ('live-inspection' if kind == 'inspection' else 'derived'),
                       'input_run_ids': [], 'tool_revision': None},
        'time': {'start_utc': None, 'end_utc': None, 'duration_s': None,
                 'clock': 'not-run'},
        'authorization': {'execute': False, 'load': False, 'write': False,
                          'network': False, 'scope_ref': None},
        'conditions': dict(conditions or {}), 'records': [], 'sources': [], 'errors': []}


def add_record(result, name, status, *, value=None, unit=None, source=None, reason=None):
    result['records'].append(dict(name=name, status=status, value=value, unit=unit,
                                  source=source, reason=reason))


def _finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite value')
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError('non-string JSON key')
        for v in value.values():
            _finite(v)
    elif isinstance(value, list):
        for v in value:
            _finite(v)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError('non-JSON value')


def validate_result(result):
    """Reject malformed envelopes; never promote an unavailable value to evidence."""
    try:
        _validate_result(result)
    except (KeyError, TypeError, AttributeError, RecursionError, OverflowError):
        raise ValueError('invalid cm3-toolkit/v1 result') from None


def _validate_result(result):
    _finite(result)
    def require(condition):
        if not condition:
            raise ValueError('invalid cm3-toolkit/v1 result')
    require(isinstance(result, dict))
    require(result.get('schema_version') == SCHEMA_VERSION)
    require(result.get('kind') in KINDS)
    require(result.get('target') == 'radxa-cm3-rpi-cm4-io')
    require(isinstance(result.get('run_id'), str) and bool(result['run_id']))
    p = result.get('provenance', {})
    require(isinstance(p, dict) and type(p.get('synthetic')) is bool)
    require(p.get('origin') in {'fixture', 'live-inspection', 'approved-test', 'derived'})
    require('fixture_id' in p and 'tool_revision' in p)
    require(p['tool_revision'] is None or bool(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', p['tool_revision'])))
    require(isinstance(p.get('input_run_ids'), list))
    require(all(isinstance(v, str) and v for v in p['input_run_ids']))
    require(not p['synthetic'] or (isinstance(p['fixture_id'], str) and bool(p['fixture_id'])))
    require(p['synthetic'] or (p['origin'] != 'fixture' and p['fixture_id'] is None))
    require(not p['synthetic'] or p['origin'] in {'fixture', 'derived'})
    t = result.get('time', {})
    require(isinstance(t, dict) and t.get('clock') in {'monotonic', 'external-monotonic', 'not-run'})
    for key in ('start_utc', 'end_utc'):
        require(key in t)
        if t[key] is not None:
            require(isinstance(t[key], str))
            try:
                parsed = datetime.datetime.fromisoformat(t[key].replace('Z', '+00:00'))
                require(parsed.utcoffset() == datetime.timedelta(0))
            except (ValueError, TypeError):
                raise ValueError('invalid UTC time') from None
    duration = t.get('duration_s')
    require('duration_s' in t and (duration is None or
            (type(duration) in (int, float) and duration >= 0)))
    a = result.get('authorization', {})
    require(isinstance(a, dict) and 'scope_ref' in a)
    require(all(type(a.get(k)) is bool for k in ('execute', 'load', 'write', 'network')))
    require(a['execute'] or not any(a[k] for k in ('load', 'write', 'network')))
    c = result.get('conditions')
    require(isinstance(c, dict))
    if a['execute']:
        require(isinstance(a['scope_ref'], str) and bool(a['scope_ref']))
        require(bool(c) and t['clock'] != 'not-run')
        require(isinstance(c.get('protocol_id'), str) and bool(c['protocol_id']))
        require(c.get('role') in {'baseline', 'candidate'})
        require(type(c.get('repetition')) is int and c['repetition'] >= 1)
        bound = c.get('duration_s')
        sustained = c.get('sustained', False)
        require(type(sustained) is bool)
        require(type(bound) in (int, float) and 0 < bound <= (3600 if sustained else 60))
        if sustained:
            require(c['protocol_id'] == 'cm3-cpu-sustained/v1')
            require(isinstance(c.get('sustained_scope_ref'), str) and bool(c['sustained_scope_ref']))
        require(duration is not None and duration <= bound + 5)
        require(t['start_utc'] is not None and t['end_utc'] is not None)
        for key, cap in (('memory_mib', 256), ('file_mib', 64)):
            if key in c:
                require(type(c[key]) is int and 1 <= c[key] <= cap)
    require(isinstance(result.get('records'), list))
    names = set()
    for r in result['records']:
        require(isinstance(r, dict) and set(r) >= {'name', 'status', 'value', 'unit', 'source', 'reason'})
        require(isinstance(r['name'], str) and bool(re.fullmatch(r'[A-Za-z0-9_.-]+', r['name'])))
        require(r['name'] not in names)
        names.add(r['name'])
        require(r['status'] in STATUSES)
        require(r['unit'] is None or r['unit'] in {
            'bytes', 'KiB', 'Hz', 'kHz', 'degC', 'seconds', 'ms',
            'bytes/s', 'operations/s', 'percent'})
        require(r['source'] is None or isinstance(r['source'], str))
        if r['status'] == 'ok':
            require(r['value'] is not None and r['reason'] is None)
        else:
            require(r['value'] is None and isinstance(r['reason'], str) and bool(r['reason']))
    require(isinstance(result.get('sources'), list) and isinstance(result.get('errors'), list))
    for s in result['sources']:
        require(isinstance(s, dict) and set(s) >= {'id', 'kind', 'path_or_ref', 'sha256'})
        require(all(isinstance(s[k], str) and s[k] for k in ('id', 'kind', 'path_or_ref')))
        require(s['sha256'] is None or bool(re.fullmatch('[0-9a-f]{64}', s['sha256'])))
    for e in result['errors']:
        require(isinstance(e, dict) and set(e) >= {'code', 'message'})
        require(all(isinstance(e[k], str) and 0 < len(e[k]) <= 512 for k in ('code', 'message')))


def safe_filename(name):
    """Accept one plain filename, never a hidden name, separator or encoded path."""
    match = re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name)
    if match is None:
        raise ValueError('plain filename of at most 128 ASCII characters required')
    return match.group(0)


def emit_result(result, output=None):
    """Write only to stdout or a new 0600 file; walk ancestors without symlinks."""
    validate_result(result)
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if output is None:
        print(text, end='')
        return
    path = os.fspath(output)
    if not path or '..' in path.split('/') or path.endswith('/'):
        raise ValueError('unsafe output path')
    parts = os.path.abspath(path).split('/')[1:]
    filename = safe_filename(parts[-1])
    if parts[0] in {'dev', 'proc', 'sys'}:
        raise ValueError('unsafe output filesystem')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        out = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=fd)
        with os.fdopen(out, 'w', encoding='utf-8') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('output is not a regular file')
            stream.write(text)
    finally:
        os.close(fd)
