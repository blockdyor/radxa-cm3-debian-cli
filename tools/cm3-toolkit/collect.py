#!/usr/bin/env python3
"""Read-only, allowlisted system inspection. No commands or workload generation."""
import argparse
import datetime
import errno
import itertools
import os
from pathlib import Path
import re
import stat
import sys
import time

from common import add_record, emit_result, make_result

MAX_BYTES = 65536
STATIC = {'/etc/os-release', '/proc/sys/kernel/osrelease', '/proc/sys/kernel/ostype',
          '/proc/meminfo', '/proc/device-tree/model', '/proc/device-tree/compatible',
          '/proc/sys/vm/swappiness', '/proc/sys/vm/overcommit_memory',
          '/sys/kernel/security/lsm'}
PATTERNS = [
    r'/sys/devices/system/cpu/cpufreq/policy[0-9]+/(scaling_governor|scaling_available_governors|scaling_available_frequencies|cpuinfo_min_freq|cpuinfo_max_freq)',
    r'/sys/class/thermal/thermal_zone[0-9]+/(type|temp)',
    r'/sys/block/(mmcblk[0-9]+|sd[a-z]+|nvme[0-9]+n[0-9]+)/(size|ro|removable|queue/rotational|queue/logical_block_size|queue/scheduler)',
    r'/sys/block/zram[0-9]+/(disksize|comp_algorithm)',
]
GROUPS = {
    '/sys/devices/system/cpu/cpufreq': r'policy[0-9]+',
    '/sys/class/thermal': r'thermal_zone[0-9]+',
    '/sys/block': r'mmcblk[0-9]+|sd[a-z]+|nvme[0-9]+n[0-9]+|zram[0-9]+'}


class SourceError(Exception):
    def __init__(self, reason):
        self.reason = reason


class SystemReader:
    """Fixture roots never fall back to live files; only named sysfs links allowed."""
    def __init__(self, root=None):
        self.synthetic = root is not None
        self.root = Path(root).resolve(strict=True) if root is not None else Path('/')
        if not self.root.is_dir():
            raise ValueError('fixture root must be a directory')

    def _path(self, source):
        path = self.root / source.lstrip('/')
        try:
            resolved = path.resolve(strict=True)
            if self.synthetic:
                if not resolved.is_relative_to(self.root):
                    raise SourceError('inaccessible')
                logical = '/' + resolved.relative_to(self.root).as_posix()
                permitted_link = (
                    source.startswith('/sys/') and logical.startswith('/sys/devices/') or
                    source == '/etc/os-release' and logical == '/usr/lib/os-release' or
                    source.startswith('/proc/device-tree/') and logical.startswith('/sys/firmware/devicetree/base/'))
                if resolved != path and not permitted_link:
                    raise SourceError('inaccessible')
            elif resolved != path and not (source.startswith('/sys/') and
                                           resolved.is_relative_to('/sys/devices')):
                # /etc/os-release commonly links to /usr/lib/os-release.
                os_release = source == '/etc/os-release' and resolved == Path('/usr/lib/os-release')
                device_tree = source.startswith('/proc/device-tree/') and resolved.is_relative_to('/sys/firmware/devicetree/base')
                if not (os_release or device_tree):
                    raise SourceError('inaccessible')
            return resolved
        except OSError as exc:
            self._error(exc)
        except RuntimeError:
            raise SourceError('malformed') from None

    @staticmethod
    def _error(exc):
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            reason = 'missing'
        elif exc.errno in (errno.EACCES, errno.EPERM, errno.ELOOP):
            reason = 'inaccessible'
        elif exc.errno in (errno.ENODEV, errno.ENXIO, errno.EOPNOTSUPP):
            reason = 'unsupported'
        else:
            reason = 'io-error'
        raise SourceError(reason) from None

    def read(self, source):
        if source not in STATIC and not any(re.fullmatch(p, source) for p in PATTERNS):
            raise ValueError('source not allowlisted')
        try:
            fd = self._open(self._path(source))
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise SourceError('unsupported')
                data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise SourceError('malformed')
            return data
        except OSError as exc:
            self._error(exc)

    @staticmethod
    def _open(path, directory=False):
        # Resolve permitted sysfs links first, then prevent ancestor-swap escapes.
        parts = path.parts[1:]
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in parts[:-1]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            return os.open(parts[-1], flags | (os.O_DIRECTORY if directory else 0), dir_fd=fd)
        finally:
            os.close(fd)

    def names(self, source):
        if source not in GROUPS:
            raise ValueError('directory not allowlisted')
        try:
            fd = self._open(self._path(source), directory=True)
            try:
                with os.scandir(fd) as entries:
                    names = [e.name for e in itertools.islice(entries, 1025)]
            finally:
                os.close(fd)
            if len(names) > 1024:
                raise SourceError('malformed')
            return sorted(n for n in names if re.fullmatch(GROUPS[source], n))
        except OSError as exc:
            self._error(exc)


def text(data):
    value = data.decode('utf-8', errors='strict').strip().rstrip('\x00')
    if not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError('invalid text')
    return value


def integer(data, *, minimum=0, maximum=2**63 - 1):
    value = text(data)
    if not re.fullmatch(r'-?[0-9]+', value):
        raise ValueError('invalid integer')
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError('integer out of range')
    return value


def os_identity(data):
    # Project only image identity, not arbitrary environment keys or shell syntax.
    allowed = {'ID', 'VERSION_ID', 'VERSION_CODENAME', 'BUILD_ID', 'IMAGE_ID', 'IMAGE_VERSION'}
    values = {}
    for line in data.decode('utf-8', errors='strict').splitlines():
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if key not in allowed:
            continue
        if not sep or key in values:
            raise ValueError('invalid image identity')
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not re.fullmatch(r'[A-Za-z0-9._+:/ -]{1,160}', value):
            raise ValueError('invalid identity value')
        values[key] = value
    if 'ID' not in values:
        raise ValueError('missing OS ID')
    return values


def memory(data):
    values = {}
    for line in data.decode('ascii').splitlines():
        if line.split(':', 1)[0] not in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
            continue
        match = re.fullmatch(r'(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+([0-9]+) kB', line)
        if not match or match[1] in values:
            raise ValueError('invalid memory data')
        values[match[1]] = int(match[2])
    if 'MemTotal' not in values or values['MemTotal'] <= 0:
        raise ValueError('missing memory capacity')
    if values.get('MemAvailable', 0) > values['MemTotal'] or values.get('SwapFree', 0) > values.get('SwapTotal', 0):
        raise ValueError('inconsistent memory data')
    return values


def frequencies(data):
    values = text(data).split()
    return [integer(v.encode(), minimum=1, maximum=10**9) for v in values]


def compatible(data):
    values = data.rstrip(b'\x00').split(b'\x00')
    return [text(v) for v in values]


def collect(reader):
    started = time.monotonic()
    result = make_result('inspection', synthetic=reader.synthetic,
                         fixture_id='collector-fixture-v1' if reader.synthetic else None)
    result['time']['start_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def unavailable(name, reason, source=None):
        add_record(result, name, 'error' if reason == 'io-error' else 'unavailable',
                   source=source, reason=reason)

    def metric(name, source, parser=text, unit=None):
        try:
            raw = reader.read(source)
            value = parser(raw)
            add_record(result, name, 'ok', value=value, source=source, unit=unit)
            # Do not hash whole files which may also contain excluded fields.
            if not any(s['id'] == source for s in result['sources']):
                result['sources'].append({'id': source, 'kind': 'system-file',
                                          'path_or_ref': source, 'sha256': None})
            return value
        except SourceError as exc:
            unavailable(name, exc.reason, source)
        except (ValueError, UnicodeError, OverflowError):
            unavailable(name, 'malformed', source)
        return None

    def group(source, name):
        try:
            names = reader.names(source)
            if not names:
                unavailable(name, 'unsupported', source)
            return names
        except SourceError as exc:
            unavailable(name, exc.reason, source)
            return []

    identity = metric('image.os_release', '/etc/os-release', os_identity)
    for key in ('BUILD_ID', 'IMAGE_ID', 'IMAGE_VERSION'):
        if identity is not None and key in identity:
            add_record(result, 'image.' + key.lower(), 'ok', value=identity[key], source='/etc/os-release')
        else:
            unavailable('image.' + key.lower(), 'missing', '/etc/os-release')
    unavailable('image.sha256', 'unsupported')
    metric('kernel.release', '/proc/sys/kernel/osrelease')
    metric('kernel.type', '/proc/sys/kernel/ostype')
    metric('board.model', '/proc/device-tree/model')
    comp = metric('board.compatible', '/proc/device-tree/compatible', compatible)
    if comp is None:
        unavailable('board.target_match', 'missing')
    elif 'radxa,cm3-rpi-cm4-io' in comp:
        add_record(result, 'board.target_match', 'ok', value=True,
                   source='/proc/device-tree/compatible')
    elif any(v.startswith('radxa,cm3') for v in comp):
        # Module identity cannot establish which carrier it is plugged into.
        unavailable('board.target_match', 'unsupported', '/proc/device-tree/compatible')
    else:
        add_record(result, 'board.target_match', 'ok', value=False,
                   source='/proc/device-tree/compatible')
    unavailable('board.carrier_revision', 'unsupported')
    unavailable('board.ram_sku', 'unsupported')
    mem = metric('memory.summary', '/proc/meminfo', memory, 'KiB')
    for key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
        if mem is not None and key in mem:
            add_record(result, 'memory.' + key, 'ok', value=mem[key], unit='KiB', source='/proc/meminfo')
        else:
            unavailable('memory.' + key, 'missing', '/proc/meminfo')
    for name in group('/sys/devices/system/cpu/cpufreq', 'cpu.cpufreq'):
        base = '/sys/devices/system/cpu/cpufreq/' + name + '/'
        for attr in ('scaling_governor', 'scaling_available_governors'):
            metric('cpu.' + name + '.' + attr, base + attr)
        metric('cpu.' + name + '.scaling_available_frequencies', base + 'scaling_available_frequencies', frequencies, 'kHz')
        for attr in ('cpuinfo_min_freq', 'cpuinfo_max_freq'):
            metric('cpu.' + name + '.' + attr, base + attr, lambda d: integer(d, minimum=1), 'kHz')
    for name in group('/sys/class/thermal', 'thermal.sensors'):
        base = '/sys/class/thermal/' + name + '/'
        metric('thermal.' + name + '.type', base + 'type')
        metric('thermal.' + name + '.temperature', base + 'temp',
               lambda d: integer(d, minimum=-273150, maximum=1000000) / 1000, 'degC')
    for name in group('/sys/block', 'storage.devices'):
        base = '/sys/block/' + name + '/'
        if name.startswith('zram'):
            metric('storage.' + name + '.disksize', base + 'disksize', integer, 'bytes')
            metric('storage.' + name + '.comp_algorithm', base + 'comp_algorithm')
            continue
        metric('storage.' + name + '.capacity', base + 'size', lambda d: integer(d) * 512, 'bytes')
        for attr in ('ro', 'removable', 'queue/rotational'):
            metric('storage.' + name + '.' + attr.replace('/', '.'), base + attr,
                   lambda d: integer(d, maximum=1))
        metric('storage.' + name + '.logical_block_size', base + 'queue/logical_block_size',
               lambda d: integer(d, minimum=1), 'bytes')
        metric('storage.' + name + '.scheduler', base + 'queue/scheduler')
    metric('config.swappiness', '/proc/sys/vm/swappiness', lambda d: integer(d, maximum=200))
    metric('config.overcommit_memory', '/proc/sys/vm/overcommit_memory', lambda d: integer(d, maximum=2))
    metric('config.lsm', '/sys/kernel/security/lsm')
    result['time'].update(end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          duration_s=time.monotonic() - started, clock='monotonic')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-root', help='isolated synthetic source tree; never reads live sources')
    parser.add_argument('--output', help='new JSON file in an existing caller-selected directory')
    args = parser.parse_args(argv)
    try:
        result = collect(SystemReader(args.fixture_root))
        emit_result(result, args.output)
        if any(r['status'] == 'error' for r in result['records']):
            return 4
        return 3 if any(r['status'] == 'unavailable' for r in result['records']) else 0
    except (ValueError, OSError):
        print('collector: invalid input or unsafe/unwritable output path', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
