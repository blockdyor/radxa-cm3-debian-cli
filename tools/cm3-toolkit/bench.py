#!/usr/bin/env python3
"""Explicit, bounded benchmark procedures. No workload runs by default."""
import argparse
import contextlib
import datetime
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

from common import make_result, add_record, emit_result, validate_result

LIMIT = 1024 * 1024
PROCEDURES = ('idle', 'cpu', 'memory', 'storage', 'network', 'boot-ssh')
CONDITION_KEYS = ('image_hash', 'source_lock', 'debian', 'kernel', 'dtb', 'bootloader',
                  'firmware', 'module_revision', 'carrier_revision', 'ram_sku',
                  'cooling', 'orientation', 'fan_control', 'ambient_degc', 'power',
                  'meter_uncertainty', 'storage', 'filesystem', 'fill', 'cache_state',
                  'network', 'logger_overhead', 'warmup', 'exclusions', 'failures')
CONDITION_KEYS += ('cpu_policy', 'zram')


def validate_metadata(value, depth=0):
    if depth > 8:
        raise ValueError('metadata nesting too deep')
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 64 or re.search(
                    r'password|secret|credential|serial|wwn|machine.?id|mac.?address|ip.?address|private.?key', key, re.I):
                raise ValueError('identifying/private metadata key')
            validate_metadata(item, depth+1)
    elif isinstance(value, list):
        if len(value) > 128:
            raise ValueError('metadata list too long')
        for item in value:
            validate_metadata(item, depth+1)
    elif isinstance(value, str):
        if len(value) > 512 or value.startswith('/') or re.search(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}|(?:\d{1,3}\.){3}\d{1,3}', value, re.I):
            raise ValueError('identifying/private metadata value')
        try:
            ipaddress.ip_address(value)
        except ValueError:
            pass
        else:
            raise ValueError('peer addresses must not be recorded')
    elif type(value) in (int, float):
        finite(value, -1e20, 1e20)
    elif value is not None and type(value) is not bool:
        raise ValueError('invalid metadata')


def read_json(path, limit=10 * LIMIT):
    # Reject symlink ancestors and special files before reading bounded input.
    p = Path(path)
    fd_dir = open_directory(str(p.absolute().parent))
    try:
        fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd_dir)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('input must be a regular file')
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('input too large')
        def reject_constant(_):
            raise ValueError('nonfinite JSON')
        def parse_float(text):
            number = float(text)
            if not math.isfinite(number):
                raise ValueError('nonfinite JSON')
            return number
        try:
            return json.loads(data, parse_constant=reject_constant, parse_float=parse_float)
        except RecursionError:
            raise ValueError('JSON nesting too deep') from None
    finally:
        os.close(fd_dir)


def open_directory(path):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or p == Path('/'):
        raise ValueError('explicit non-root absolute directory required')
    if p.parts[1] in ('dev', 'proc', 'sys', 'etc', 'boot'):
        raise ValueError('unsafe directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def storage_file(directory, size, name=None):
    if not 0 < size <= 64 * LIMIT:
        raise ValueError('storage budget outside 1..64 MiB')
    dfd = open_directory(directory)
    fd = None
    identity = None
    name = name or ('cm3-bench-' + uuid.uuid4().hex + '.tmp')
    try:
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('unsafe test filename')
        space = os.fstatvfs(dfd)
        if space.f_blocks <= 0 or space.f_frsize <= 0:
            raise ValueError('unmeasurable disk capacity')
        if space.f_bavail * space.f_frsize - size < space.f_blocks * space.f_frsize * .25:
            raise ValueError('insufficient free space: 25 percent reserve required')
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise ValueError('test file not regular/owned')
        identity = (st.st_dev, st.st_ino)
        yield fd
    finally:
        if fd is not None:
            os.close(fd)
        if identity is not None:
            try:
                st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                if identity == (st.st_dev, st.st_ino):
                    os.unlink(name, dir_fd=dfd)
            except FileNotFoundError:
                pass
        os.close(dfd)


def run_process(argv, timeout, monitor=None, pass_fds=()):
    """Bounded streams and whole process-group cleanup, including descendants."""
    if not 0 < timeout <= 3605:
        raise ValueError('invalid deadline')
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True, pass_fds=pass_fds)
    sel = selectors.DefaultSelector()
    output = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    deadline = time.monotonic() + timeout
    try:
        for pipe in output:
            os.set_blocking(pipe.fileno(), False)
            sel.register(pipe, selectors.EVENT_READ)
        while sel.get_map():
            if time.monotonic() >= deadline:
                raise TimeoutError('process deadline exceeded')
            if monitor:
                monitor()
            for key, _ in sel.select(.05):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    sel.unregister(key.fileobj)
                    continue
                output[key.fileobj].extend(chunk)
                if len(output[key.fileobj]) > LIMIT:
                    raise ValueError('process output exceeds 1 MiB')
        try:
            proc.wait(timeout=max(.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise TimeoutError('process deadline exceeded') from None
        if proc.returncode:
            raise RuntimeError('workload exited nonzero')
        return bytes(output[proc.stdout]).decode('utf-8'), bytes(output[proc.stderr]).decode('utf-8')
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)
        sel.close()
        proc.stdout.close()
        proc.stderr.close()


def finite(value, minimum: float = 0, maximum: float = 1e20):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum or not math.isfinite(value):
        raise ValueError('invalid finite numeric result')
    return value


def memory_capacity():
    fields = {}
    with open('/proc/meminfo', encoding='ascii') as stream:
        for line in stream:
            parts = line.split()
            if parts[0] in ('MemTotal:', 'MemAvailable:') and len(parts) == 3 and parts[2] == 'kB':
                fields[parts[0][:-1]] = int(parts[1]) * 1024
    total, available = fields['MemTotal'], fields['MemAvailable']
    if not 0 < available <= total:
        raise ValueError('invalid capacity')
    return total, available


def thermal_monitor(conditions, samples):
    zone = conditions.get('thermal_zone')
    if not isinstance(zone, int) or isinstance(zone, bool) or not 0 <= zone <= 255:
        raise ValueError('thermal_zone index required')
    ceiling = finite(conditions.get('thermal_abort_degc'), 1, 120)
    if not conditions.get('thermal_observer_ref'):
        raise ValueError('approved thermal observer required')
    path = Path('/sys/class/thermal') / ('thermal_zone' + str(zone)) / 'temp'
    last = [0.0]
    def monitor():
        now = time.monotonic()
        if now - last[0] < .5:
            return
        last[0] = now
        temp = finite(int(path.read_text()) / 1000, -50, 150)
        samples.append({'elapsed_s': now - start, 'degc': temp})
        if temp >= ceiling:
            raise RuntimeError('thermal abort ceiling reached')
    start = time.monotonic()
    monitor()
    return monitor


CPU_CODE = '''import hashlib,json,sys,time
end=time.monotonic()+float(sys.argv[1]); n=0; start=time.monotonic()
while time.monotonic()<end:
 hashlib.sha256(b'x'*65536).digest(); n+=1
print(json.dumps({'operations':n,'elapsed_s':time.monotonic()-start}))
'''
MEMORY_CODE = '''import json,sys,time
size=int(sys.argv[1]); duration=float(sys.argv[2]); data=bytearray(size)
for i in range(0,size,4096): data[i]=1
end=time.monotonic()+duration; delays=[]; n=0
while time.monotonic()<end:
 start=time.monotonic(); time.sleep(.01); delays.append(max(0,time.monotonic()-start-.01)); n+=1
print(json.dumps({'allocated_bytes':size,'wake_lateness_ms':[x*1000 for x in delays]}))
'''
STORAGE_CODE = '''import json,os,sys,time
fd=int(sys.argv[1]); size=int(sys.argv[2]); block=os.urandom(65536); written=0; lat=[]; start=time.monotonic()
while written<size:
 t=time.monotonic(); n=os.write(fd,block[:min(len(block),size-written)]); os.fsync(fd); lat.append((time.monotonic()-t)*1000)
 if n<=0: raise RuntimeError('short write')
 written+=n
write_s=time.monotonic()-start; os.lseek(fd,0,0); start=time.monotonic(); read=0
while read<size:
 chunk=os.read(fd,min(65536,size-read))
 if not chunk: raise RuntimeError('short read')
 read+=len(chunk)
print(json.dumps({'bytes':written,'write_s':write_s,'read_s':time.monotonic()-start,'write_fsync_latency_ms':lat}))
'''


def sample_idle(duration):
    def cpu():
        with open('/proc/stat', encoding='ascii') as f:
            fields = f.readline().split()
        if fields[0] != 'cpu' or len(fields) < 9:
            raise ValueError('malformed cpu counters')
        values = list(map(int, fields[1:9]))  # guest is already in user/nice.
        if any(x < 0 for x in values):
            raise ValueError('negative cpu counter')
        return sum(values), values[3] + values[4]
    a, idle_a = cpu()
    total_a, available_a = memory_capacity()
    time.sleep(duration)
    b, idle_b = cpu()
    total_b, available_b = memory_capacity()
    if b <= a or not 0 <= idle_b - idle_a <= b - a or total_a != total_b:
        raise ValueError('invalid counter interval')
    return {'busy_percent': 100 * (1 - (idle_b-idle_a)/(b-a)),
            'mem_available_bytes': [available_a, available_b], 'mem_total_bytes': total_a,
            'cpu_raw': [[a, idle_a], [b, idle_b]]}


def boot_events(conditions):
    events = conditions.get('boot_events')
    if not isinstance(events, dict) or events.get('clock') != 'external-monotonic':
        raise ValueError('external monotonic boot events required')
    for key in ('observer_ref', 'start_event', 'end_event', 'authentication', 'host_key_policy'):
        if not isinstance(events.get(key), str) or not events[key]:
            raise ValueError('missing boot observer metadata')
    start = finite(events.get('start_s'))
    end = finite(events.get('end_s'), start, start + 3600)
    uncertainty = finite(events.get('uncertainty_s'), 0, 3600)
    return {'seconds': end-start, 'uncertainty_s': uncertainty, 'events': events}


def execute_live(args, conditions, runner=run_process):
    duration = args.duration_s
    if args.procedure == 'idle':
        return sample_idle(duration)
    if args.procedure == 'boot-ssh':
        return boot_events(conditions)
    if args.procedure in ('cpu', 'memory'):
        samples = []
        monitor = thermal_monitor(conditions, samples)
        if args.procedure == 'cpu':
            out, _ = runner([sys.executable, '-c', CPU_CODE, str(duration)], duration+2, monitor)
        else:
            total, available = memory_capacity()
            reserve = max(total // 4, conditions.get('memory_reserve_bytes', total // 4))
            size = min(args.memory_mib*LIMIT, 256*LIMIT, available//4, available-reserve)
            if size <= 0:
                raise ValueError('memory reserve unavailable')
            thermal = monitor
            last = [0.0]
            def memory_monitor():
                thermal()
                now = time.monotonic()
                if now-last[0] >= .5:
                    last[0] = now
                    current_total, current_available = memory_capacity()
                    if current_total != total or current_available < reserve:
                        raise RuntimeError('memory reserve lost')
            out, _ = runner([sys.executable, '-c', MEMORY_CODE, str(size), str(duration)], duration+2, memory_monitor)
        raw = json.loads(out)
        raw['thermal_samples'] = samples
        return raw
    if args.procedure == 'storage':
        with storage_file(args.approved_dir, args.file_mib*LIMIT) as fd:
            out, _ = runner([sys.executable, '-c', STORAGE_CODE, str(fd), str(args.file_mib*LIMIT)],
                            duration+2, pass_fds=(fd,))
        return json.loads(out)
    ping, iperf = shutil.which('ping'), shutil.which('iperf3')
    if not ping or not iperf:
        raise FileNotFoundError('tool-missing: ping/iperf3')
    # Literal unicast peer only: no DNS, scanning, option injection, or auto-target.
    peer = ipaddress.ip_address(args.peer)
    if peer.is_unspecified or peer.is_multicast or peer.is_loopback or peer.is_link_local:
        raise ValueError('explicit nonlocal unicast peer required')
    deadline = time.monotonic() + duration
    iperf_version, _ = runner([iperf, '--version'], min(1, duration))
    ping_version, _ = runner([ping, '-V'], min(1, max(.01, deadline-time.monotonic())))
    if not iperf_version.strip() or not ping_version.strip():
        raise ValueError('missing network tool versions')
    ping_out, _ = runner([ping, '-n', '-c', '1', '-W', '1', str(peer)], min(2, max(.01, deadline-time.monotonic())))
    remaining = deadline-time.monotonic()
    if remaining <= .1:
        raise TimeoutError('network procedure deadline')
    out, _ = runner([iperf, '-c', str(peer), '-J', '-n', str(1024*1024), '-b', '10M', '-P', '1', '-4' if peer.version == 4 else '-6'], remaining)
    raw = json.loads(out)
    # Do not retain iperf/ping addresses, hostnames or peer identifiers.
    # A '<' response is a bound, not an exact measured latency.
    match = re.search(r'time=([0-9.]+)\s*ms', ping_out)
    if not match:
        raise ValueError('malformed ping result')
    return {'latency_ms': float(match.group(1)),
            'bytes_per_second': raw['end']['sum_sent']['bits_per_second']/8,
            'bytes': raw['end']['sum_sent']['bytes'],
            'tool_versions': {'iperf3': iperf_version.splitlines()[0][:128],
                              'ping': ping_version.splitlines()[0][:128]}}


def measurements(procedure, raw):
    """Parse required metrics, preserving bounded raw data beside them."""
    if not isinstance(raw, dict):
        raise ValueError('raw result must be object')
    allowed = {
        'idle': {'busy_percent', 'mem_available_bytes', 'mem_total_bytes', 'cpu_raw'},
        'cpu': {'operations', 'elapsed_s', 'thermal_samples'},
        'memory': {'allocated_bytes', 'wake_lateness_ms', 'thermal_samples'},
        'storage': {'bytes', 'write_s', 'read_s', 'write_fsync_latency_ms'},
        'network': {'bytes_per_second', 'bytes', 'latency_ms', 'tool_versions'},
        'boot-ssh': {'seconds', 'uncertainty_s', 'events'},
    }
    if set(raw) - allowed[procedure]:
        raise ValueError('unexpected raw fields')
    if procedure in ('cpu', 'memory'):
        samples = raw['thermal_samples']
        if not isinstance(samples, list) or not 1 <= len(samples) <= 7300:
            raise ValueError('missing thermal samples')
        for sample in samples:
            if set(sample) != {'elapsed_s', 'degc'}:
                raise ValueError('malformed thermal sample')
            finite(sample['elapsed_s'], 0, 3605)
            finite(sample['degc'], -50, 150)
    if procedure == 'idle':
        if len(raw['mem_available_bytes']) != 2:
            raise ValueError('idle needs two memory samples')
        return [('busy', finite(raw['busy_percent'], 0, 100), 'percent'),
                ('memory_available', [finite(x) for x in raw['mem_available_bytes']], 'bytes')]
    if procedure == 'cpu':
        n, elapsed = finite(raw['operations']), finite(raw['elapsed_s'], .000001, 3605)
        return [('throughput', n/elapsed, 'operations/s'), ('thermal', raw['thermal_samples'], None)]
    if procedure == 'memory':
        if not 1 <= len(raw['wake_lateness_ms']) <= 6500:
            raise ValueError('invalid responsiveness sample count')
        return [('allocated', finite(raw['allocated_bytes'], 1, 256*LIMIT), 'bytes'),
                ('wake_lateness', [finite(x) for x in raw['wake_lateness_ms']], 'ms')]
    if procedure == 'storage':
        if not 1 <= len(raw['write_fsync_latency_ms']) <= 2048:
            raise ValueError('invalid storage sample count')
        size = finite(raw['bytes'], 1, 64*LIMIT)
        return [('write', size/finite(raw['write_s'], .000001), 'bytes/s'),
                ('read_cached', size/finite(raw['read_s'], .000001), 'bytes/s'),
                ('write_fsync_latency', [finite(x) for x in raw['write_fsync_latency_ms']], 'ms')]
    if procedure == 'network':
        finite(raw['bytes'], 1, LIMIT)
        validate_metadata(raw['tool_versions'])
        return [('throughput', finite(raw['bytes_per_second']), 'bytes/s'),
                ('latency', finite(raw['latency_ms']), 'ms')]
    events = boot_events({'boot_events': raw['events']})
    if raw['seconds'] != events['seconds'] or raw['uncertainty_s'] != events['uncertainty_s']:
        raise ValueError('boot events and derived times disagree')
    return [('elapsed', finite(raw['seconds'], 0, 3600), 'seconds'),
            ('uncertainty', finite(raw['uncertainty_s']), 'seconds')]


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('procedure', choices=PROCEDURES)
    for flag in ('execute', 'allow-load', 'allow-write', 'allow-network'):
        p.add_argument('--'+flag, action='store_true')
    p.add_argument('--sustained', action='store_true', help='distinct CPU-only approved protocol, <=3600 seconds')
    p.add_argument('--duration-s', type=float)
    p.add_argument('--memory-mib', type=int, default=64)
    p.add_argument('--file-mib', type=int, default=16)
    for flag in ('approved-dir', 'peer', 'conditions', 'fixture-root', 'output'):
        p.add_argument('--'+flag)
    return p


def build(args):
    args.duration_s = args.duration_s if args.duration_s is not None else (5 if args.procedure == 'idle' else 10)
    finite(args.duration_s, .1, 3600 if args.sustained else 60)
    if args.sustained and args.procedure != 'cpu':
        raise ValueError('sustained mode is CPU-only')
    if not args.execute and (args.allow_load or args.allow_write or args.allow_network):
        raise ValueError('authorization flags require --execute')
    if not 1 <= args.memory_mib <= 256 or not 1 <= args.file_mib <= 64:
        raise ValueError('resource bound exceeded')
    conditions = read_json(args.conditions, 65536) if args.conditions else {}
    if not isinstance(conditions, dict):
        raise ValueError('conditions must be object')
    validate_metadata(conditions)
    # Retain only protocol fields, never arbitrary caller secrets.
    allowed = set(CONDITION_KEYS) | {'scope_ref', 'protocol_id', 'repetition', 'role', 'thermal_zone',
              'thermal_abort_degc', 'thermal_observer_ref', 'memory_reserve_bytes', 'boot_events', 'sustained_scope_ref'}
    if set(conditions) - allowed:
        raise ValueError('unknown condition keys')
    for key in CONDITION_KEYS:
        conditions.setdefault(key, None)
    conditions['unknown_reasons'] = {k: 'not-supplied' for k in CONDITION_KEYS if conditions[k] is None}
    conditions['duration_s'] = args.duration_s
    conditions['memory_mib'] = args.memory_mib
    conditions['file_mib'] = args.file_mib
    conditions['sustained'] = args.sustained
    conditions['tool_versions'] = {'python': sys.version.split()[0], 'protocol': 'cm3-bench/v1'}
    synthetic = bool(args.fixture_root)
    result = make_result('benchmark' if args.execute else 'plan', synthetic=synthetic,
                         fixture_id='bench-v1' if synthetic else None, conditions=conditions)
    result['authorization'].update(execute=args.execute, load=args.allow_load, write=args.allow_write,
                                   network=args.allow_network, scope_ref=conditions.get('scope_ref'))
    if not args.execute:
        add_record(result, args.procedure+'.plan', 'not_run', reason='not-run')
        return result, 0
    if any(not isinstance(conditions.get(k), str) or not conditions[k].strip() for k in ('scope_ref', 'protocol_id')) or conditions.get('role') not in ('baseline', 'candidate') or type(conditions.get('repetition')) is not int or conditions['repetition'] < 1:
        raise ValueError('execution requires scope_ref, protocol_id, role and repetition')
    if args.sustained and (conditions['protocol_id'] != 'cm3-cpu-sustained/v1' or not isinstance(conditions.get('sustained_scope_ref'), str) or not conditions['sustained_scope_ref'].strip()):
        raise ValueError('separate sustained scope and protocol required')
    if args.procedure in ('cpu', 'memory', 'storage', 'network') and not args.allow_load:
        raise ValueError('--allow-load required')
    if args.procedure == 'storage' and (not args.allow_write or not args.approved_dir):
        raise ValueError('--allow-write and --approved-dir required')
    if args.procedure == 'network' and (not args.allow_network or not args.peer):
        raise ValueError('--allow-network and --peer required')
    start = time.monotonic()
    result['time']['start_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['time']['clock'] = 'external-monotonic' if args.procedure == 'boot-ssh' else 'monotonic'
    result['provenance']['origin'] = 'fixture' if synthetic else 'approved-test'
    # Validate the provisional execution envelope BEFORE any side effect.
    result['time']['end_utc'] = result['time']['start_utc']
    result['time']['duration_s'] = 0
    validate_result(result)
    code = 0
    try:
        if synthetic:
            raw = read_json(str(Path(args.fixture_root) / (args.procedure+'.json')), LIMIT)
        else:
            raw = execute_live(args, conditions)
        for name, value, unit in measurements(args.procedure, raw):
            add_record(result, args.procedure+'.'+name, 'ok', value=value, unit=unit, source='fixture' if synthetic else 'procedure')
        if 'tool_versions' in raw:
            conditions['tool_versions'].update(raw['tool_versions'])
        add_record(result, args.procedure+'.raw', 'ok', value=raw, source='fixture' if synthetic else 'procedure')
        encoded = json.dumps(raw, allow_nan=False, sort_keys=True).encode()
        result['sources'].append({'id': 'raw', 'kind': 'inline', 'path_or_ref': args.procedure+'.raw',
                                  'sha256': hashlib.sha256(encoded).hexdigest()})
    except (FileNotFoundError, PermissionError) as exc:
        add_record(result, args.procedure+'.result', 'unavailable', reason='tool-missing' if 'tool-missing' in str(exc) else 'missing')
        code = 3
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, TimeoutError) as exc:
        add_record(result, args.procedure+'.result', 'error', reason='malformed-or-execution-failure')
        result['errors'].append({'code': 'timeout' if isinstance(exc, TimeoutError) else 'execution',
                                 'message': 'Workload, sensor, deadline or parser failed; no hardware qualification'})
        code = 4
    finally:
        result['time']['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['time']['duration_s'] = time.monotonic()-start
    return result, code


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    args = parser().parse_args()
    output_fd = None
    result = None
    try:
        if args.output:
            path = Path(args.output)
            if '..' in path.parts or str(args.output).endswith('/'):
                raise ValueError('unsafe output path')
            directory_fd = open_directory(str(path.absolute().parent))
            try:
                output_fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                    0o600, dir_fd=directory_fd)
            finally:
                os.close(directory_fd)
        result, code = build(args)
        if output_fd is None:
            emit_result(result)
        else:
            validate_result(result)
            with os.fdopen(output_fd, 'w', encoding='utf-8') as stream:
                output_fd = None
                stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
        return code
    except (ValueError, OSError, KeyError, TypeError):
        if result is not None:
            emit_result(result)
        print('Invalid input, authorization or output path', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Interrupted; owned child processes and temporary files cleaned', file=sys.stderr)
        return 130
    finally:
        if output_fd is not None:
            os.close(output_fd)


if __name__ == '__main__':
    sys.exit(main())
