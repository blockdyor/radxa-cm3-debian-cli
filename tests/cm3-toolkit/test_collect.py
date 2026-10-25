import contextlib
import errno
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/cm3-toolkit'))
from collect import MAX_BYTES, SourceError, SystemReader, collect, main
from common import validate_result

FIXTURE = Path(__file__).parent / 'fixtures/collector/basic.json'


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'fixture'
        for source, data in json.loads(FIXTURE.read_text()).items():
            self.put(source, data.encode())

    def put(self, path, data):
        p = self.root / path.lstrip('/')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def run_collect(self):
        r = collect(SystemReader(self.root))
        validate_result(r)
        return r, {v['name']: v for v in r['records']}

    def test_basic_synthetic_and_units(self):
        r, records = self.run_collect()
        self.assertTrue(r['provenance']['synthetic'])
        self.assertEqual(r['provenance']['origin'], 'fixture')
        self.assertEqual(records['thermal.thermal_zone0.temperature']['value'], 42.125)
        self.assertEqual(records['thermal.thermal_zone0.temperature']['unit'], 'degC')
        self.assertEqual(records['storage.mmcblk0.capacity']['value'], 1048576)
        self.assertEqual(records['cpu.policy0.scaling_available_frequencies']['value'], [408000, 1800000])
        self.assertEqual(records['memory.MemTotal']['unit'], 'KiB')
        self.assertFalse(any(r['authorization'][k] for k in ('execute', 'load', 'write', 'network')))

    def test_missing_sensor_and_files(self):
        shutil.rmtree(self.root / 'sys/class/thermal')
        (self.root / 'proc/meminfo').unlink()
        _, records = self.run_collect()
        self.assertEqual(records['thermal.sensors']['reason'], 'missing')
        self.assertEqual(records['memory.summary']['reason'], 'missing')
        self.assertIsNone(records['memory.summary']['value'])

    def test_empty_sensor_directory(self):
        shutil.rmtree(self.root / 'sys/class/thermal/thermal_zone0')
        _, records = self.run_collect()
        self.assertEqual(records['thermal.sensors']['reason'], 'unsupported')

    def test_malformed_values(self):
        cases = [('/sys/class/thermal/thermal_zone0/temp', b'NaN', 'thermal.thermal_zone0.temperature'),
                 ('/proc/meminfo', b'MemTotal: lots kB', 'memory.summary'),
                 ('/sys/block/mmcblk0/size', b'-10', 'storage.mmcblk0.capacity'),
                 ('/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies', b'0 invalid', 'cpu.policy0.scaling_available_frequencies'),
                 ('/etc/os-release', b'ID=$(secret)', 'image.os_release')]
        for source, raw, name in cases:
            with self.subTest(source=source):
                self.put(source, raw)
                _, records = self.run_collect()
                self.assertEqual(records[name]['reason'], 'malformed')
                self.assertIsNone(records[name]['value'])

    def test_permission_and_unsupported_io_errors(self):
        for err, reason in [(errno.EACCES, 'inaccessible'), (errno.ENODEV, 'unsupported'), (errno.EIO, 'io-error')]:
            with patch('collect.os.open', side_effect=OSError(err, 'DO NOT EMIT PRIVATE PATH')):
                with self.assertRaises(SourceError) as ctx:
                    SystemReader(self.root).read('/proc/meminfo')
            self.assertEqual(ctx.exception.reason, reason)

    def test_no_live_fallback_and_no_live_probe_commands(self):
        isolated = Path(self.tmp.name) / 'empty'
        isolated.mkdir()
        with patch('subprocess.run', side_effect=AssertionError('no subprocesses')), \
             patch('os.uname', side_effect=AssertionError('no host identity')):
            r = collect(SystemReader(isolated))
        self.assertFalse(any(x['status'] == 'ok' for x in r['records']))
        self.assertTrue(r['provenance']['synthetic'])

    def test_privacy_allowlist_and_projection(self):
        private = ['/etc/shadow', '/etc/machine-id', '/proc/cpuinfo', '/proc/cmdline',
                   '/proc/mounts', '/home/user/key', '/sys/block/mmcblk0/device/serial',
                   '/proc/device-tree/serial-number', '/sys/class/net/eth0/address']
        reader = SystemReader(self.root)
        for path in private:
            self.put(path, b'PRIVATE_CANARY')
            with self.assertRaises(ValueError):
                reader.read(path)
        self.put('/etc/os-release', b'ID=debian\nVERSION_ID="13"\nPASSWORD=PRIVATE_CANARY\nHOME_URL=PRIVATE_CANARY\n')
        self.put('/proc/meminfo', b'MemTotal: 100 kB\nPrivate: PRIVATE_CANARY\n')
        r, _ = self.run_collect()
        self.assertNotIn('PRIVATE_CANARY', json.dumps(r))
        self.assertNotIn(str(self.root), json.dumps(r))

    def test_symlink_escape_rejected_and_internal_sysfs_supported(self):
        source = self.root / 'sys/class/thermal/thermal_zone0/temp'
        source.unlink()
        outside = Path(self.tmp.name) / 'outside'
        outside.write_text('12345')
        source.symlink_to(outside)
        _, records = self.run_collect()
        self.assertEqual(records['thermal.thermal_zone0.temperature']['reason'], 'inaccessible')
        source.unlink()
        internal = self.root / 'sys/devices/mock/temp'
        internal.parent.mkdir(parents=True)
        internal.write_text('12345')
        source.symlink_to(internal)
        _, records = self.run_collect()
        self.assertEqual(records['thermal.thermal_zone0.temperature']['value'], 12.345)

    def test_internal_link_to_private_source_is_rejected(self):
        self.put('/etc/shadow', b'PRIVATE_CANARY')
        path = self.root / 'proc/device-tree/model'
        path.unlink()
        path.symlink_to(self.root / 'etc/shadow')
        result, records = self.run_collect()
        self.assertEqual(records['board.model']['reason'], 'inaccessible')
        self.assertNotIn('PRIVATE_CANARY', json.dumps(result))

    def test_oversized_and_special_files(self):
        self.put('/proc/meminfo', b'x' * (MAX_BYTES + 1))
        _, records = self.run_collect()
        self.assertEqual(records['memory.summary']['reason'], 'malformed')
        path = self.root / 'sys/class/thermal/thermal_zone0/temp'
        path.unlink()
        os.mkfifo(path)
        _, records = self.run_collect()
        self.assertEqual(records['thermal.thermal_zone0.temperature']['reason'], 'unsupported')

    def test_board_mismatch(self):
        self.put('/proc/device-tree/compatible', b'other,board\x00')
        _, records = self.run_collect()
        self.assertFalse(records['board.target_match']['value'])

    def test_module_identity_does_not_establish_carrier(self):
        _, records = self.run_collect()
        self.assertEqual(records['board.target_match']['status'], 'unavailable')
        self.assertEqual(records['board.target_match']['reason'], 'unsupported')

    def test_inaccessible_sensor_is_explicit(self):
        reader = SystemReader(self.root)
        original = reader.read
        def read(source):
            if source.endswith('/temp'):
                raise SourceError('inaccessible')
            return original(source)
        with patch.object(reader, 'read', side_effect=read):
            result = collect(reader)
        record = next(r for r in result['records'] if r['name'] == 'thermal.thermal_zone0.temperature')
        self.assertEqual(record['reason'], 'inaccessible')
        self.assertIsNone(record['value'])

    def test_bounded_directory_enumeration(self):
        class Entries:
            def __enter__(self):
                return iter([type('Entry', (), {'name': 'ignored'})()] * 1025)
            def __exit__(self, *args):
                pass
        with patch('collect.os.scandir', return_value=Entries()):
            with self.assertRaises(SourceError) as caught:
                SystemReader(self.root).names('/sys/class/thermal')
        self.assertEqual(caught.exception.reason, 'malformed')

    def test_cli_partial_exit_and_no_implicit_output(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main(['--fixture-root', str(self.root)])
        self.assertEqual(code, 3)
        self.assertTrue(json.loads(out.getvalue())['provenance']['synthetic'])
        output = Path(self.tmp.name) / 'result.json'
        self.assertEqual(main(['--fixture-root', str(self.root), '--output', str(output)]), 3)
        self.assertTrue(output.is_file())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--fixture-root', str(self.root), '--output', str(output)]), 2)


if __name__ == '__main__':
    unittest.main()
