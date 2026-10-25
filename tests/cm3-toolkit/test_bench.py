"""Fixture-only tests: never invoke a hardware workload."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / 'tools/cm3-toolkit'
sys.path.insert(0, str(TOOLS))
import bench
from common import validate_result

FIXTURES = Path(__file__).parent / 'fixtures/bench'


class BenchTests(unittest.TestCase):
    def args(self, proc='cpu', *extra):
        return bench.parser().parse_args([proc, '--fixture-root', str(FIXTURES),
               '--conditions', str(FIXTURES/'conditions.json'), *extra])

    def test_default_is_plan_without_io(self):
        with patch.object(bench, 'execute_live', side_effect=AssertionError('live execution')):
            for proc in bench.PROCEDURES:
                result, code = bench.build(self.args(proc))
                self.assertEqual(code, 0)
                self.assertEqual(result['kind'], 'plan')
                validate_result(result)

    def test_all_synthetic_procedures(self):
        with patch.object(bench, 'execute_live', side_effect=AssertionError('live execution')):
            for proc in bench.PROCEDURES:
                result, code = bench.build(self.args(proc, '--execute', '--allow-load',
                    '--allow-write', '--allow-network', '--approved-dir', '/not-used', '--peer', '192.0.2.1'))
                self.assertEqual(code, 0, (proc, result))
                self.assertTrue(result['provenance']['synthetic'])
                validate_result(result)

    def test_authorization(self):
        for proc in ('cpu', 'memory', 'storage', 'network'):
            with self.assertRaises(ValueError):
                bench.build(self.args(proc, '--execute'))
        for extra in (['--duration-s', 'nan'], ['--duration-s', '61'], ['--memory-mib', '257'], ['--allow-load']):
            with self.assertRaises(ValueError):
                bench.build(self.args('cpu', *extra))
        with self.assertRaises(ValueError):
            bench.build(self.args('cpu', '--execute', '--allow-load', '--sustained', '--duration-s', '3600'))

    def test_malformed_authorization_never_dispatches(self):
        for key in ('scope_ref', 'protocol_id'):
            for value in (1, [], {'bad':1}, ' '):
                conditions = {'scope_ref':'test', 'protocol_id':'test', 'role':'baseline', 'repetition':1}
                conditions[key] = value
                args = self.args('cpu', '--execute', '--allow-load')
                args.fixture_root = None
                with patch.object(bench, 'read_json', return_value=conditions), patch.object(bench, 'execute_live') as live:
                    with self.assertRaises(ValueError):
                        bench.build(args)
                    live.assert_not_called()

    def test_missing_fixture(self):
        args = self.args('cpu', '--execute', '--allow-load')
        with tempfile.TemporaryDirectory() as td:
            args.fixture_root = td
            result, code = bench.build(args)
        self.assertEqual(code, 3)
        self.assertEqual(result['records'][0]['status'], 'unavailable')

    def test_malformed_and_missing_thermal(self):
        for value in ({}, {'operations': 1, 'elapsed_s': 1, 'thermal_samples': []},
                      {'operations': float('nan'), 'elapsed_s': 1, 'thermal_samples': [{'degc': 30, 'elapsed_s': 0}]}):
            with self.assertRaises((ValueError, KeyError)):
                bench.measurements('cpu', value)
        with patch.object(bench, 'read_json', side_effect=[{'scope_ref':'fixture', 'protocol_id':'x', 'role':'baseline', 'repetition':1}, {}]):
            result, code = bench.build(self.args('cpu', '--execute', '--allow-load'))
        self.assertEqual(code, 4)
        validate_result(result)

    def test_storage_cleanup_and_existing_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            with bench.storage_file(td, 1024, 'owned') as fd:
                os.write(fd, b'fixture')
                self.assertTrue((Path(td)/'owned').exists())
            self.assertFalse((Path(td)/'owned').exists())
            (Path(td)/'existing').write_text('user data')
            with self.assertRaises(FileExistsError):
                with bench.storage_file(td, 1024, 'existing'):
                    pass
            self.assertEqual((Path(td)/'existing').read_text(), 'user data')
            with self.assertRaises(RuntimeError):
                with bench.storage_file(td, 1024, 'exception'):
                    raise RuntimeError('fixture')
            self.assertFalse((Path(td)/'exception').exists())

    def test_cleanup_preserves_replacement(self):
        with tempfile.TemporaryDirectory() as td:
            with bench.storage_file(td, 1024, 'test'):
                (Path(td)/'test').rename(Path(td)/'original')
                (Path(td)/'test').write_text('replacement')
            self.assertEqual((Path(td)/'test').read_text(), 'replacement')

    def test_safe_paths_and_space(self):
        for path in ('/dev', '/proc', '/sys', '/', '/etc', 'relative', '/opt/../dev'):
            with self.assertRaises(ValueError):
                bench.open_directory(path)
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'link').symlink_to(td, target_is_directory=True)
            with self.assertRaises(OSError):
                bench.open_directory(str(Path(td)/'link'))
            with self.assertRaises(ValueError):
                with bench.storage_file(td, 1024, '../escape'):
                    pass
            space = os.statvfs_result((1, 1, 100, 10, 10, 0, 0, 0, 0, 255))
            with patch.object(os, 'fstatvfs', return_value=space):
                with self.assertRaises(ValueError):
                    with bench.storage_file(td, 1):
                        pass
            self.assertEqual(list(Path(td).iterdir()), [Path(td)/'link'])

    def test_timeout_cleanup_descendant(self):
        with tempfile.TemporaryDirectory() as td:
            pidfile = Path(td)/'child.pid'
            script = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open(sys.argv[1],'w').write(str(p.pid)); time.sleep(30)"
            with self.assertRaises(TimeoutError):
                bench.run_process([sys.executable, '-c', script, str(pidfile)], 3)
            pid = int(pidfile.read_text())
            status = Path('/proc')/str(pid)/'stat'
            # An adopted zombie has exited; it is not a surviving workload.
            self.assertTrue(not status.exists() or status.read_text().split()[2] == 'Z')

    def test_output_cap_and_exit(self):
        with self.assertRaises(ValueError):
            bench.run_process([sys.executable, '-c', "import sys;sys.stdout.write('x'*1100000)"], 2)
        with self.assertRaises(RuntimeError):
            bench.run_process([sys.executable, '-c', 'raise SystemExit(1)'], 2)
        out, err = bench.run_process([sys.executable, '-c', "print('fixture')"], 2)
        self.assertEqual(out.strip(), 'fixture')

    def test_missing_sensor_stops_before_work(self):
        args = self.args('cpu', '--execute', '--allow-load')
        with patch.object(Path, 'read_text', side_effect=FileNotFoundError), patch.object(bench, 'run_process') as runner:
            with self.assertRaises(FileNotFoundError):
                bench.execute_live(args, {'thermal_zone':0, 'thermal_abort_degc':70, 'thermal_observer_ref':'fixture'})
            runner.assert_not_called()

    def test_thermal_abort_and_sensor_loss(self):
        conditions = {'thermal_zone':0, 'thermal_abort_degc':70, 'thermal_observer_ref':'fixture'}
        with patch.object(Path, 'read_text', return_value='71000'):
            with self.assertRaises(RuntimeError):
                bench.thermal_monitor(conditions, [])
        with patch.object(Path, 'read_text', return_value='bad'):
            with self.assertRaises(ValueError):
                bench.thermal_monitor(conditions, [])

    def test_memory_reserve(self):
        args = self.args('memory', '--execute', '--allow-load')
        args.duration_s = 1
        def fake(argv, *a, **kw):
            self.assertEqual(int(argv[3]), 16*bench.LIMIT)
            return json.dumps({'allocated_bytes':int(argv[3]), 'wake_lateness_ms':[1]}), ''
        with patch.object(bench, 'thermal_monitor', return_value=lambda:None), patch.object(bench, 'memory_capacity', return_value=(128*bench.LIMIT, 64*bench.LIMIT)):
            bench.execute_live(args, {}, runner=fake)
        with patch.object(bench, 'thermal_monitor', return_value=lambda:None), patch.object(bench, 'memory_capacity', return_value=(128*bench.LIMIT, 16*bench.LIMIT)):
            with self.assertRaises(ValueError):
                bench.execute_live(args, {}, runner=fake)

    def test_boot_method(self):
        conditions = json.loads((FIXTURES/'conditions.json').read_text())
        value = bench.boot_events(conditions)
        self.assertEqual(value['seconds'], 8)
        conditions['boot_events']['clock'] = 'wall-clock'
        with self.assertRaises(ValueError):
            bench.boot_events(conditions)

    def test_network_protocol_without_contacting_peer(self):
        args = self.args('network', '--execute', '--allow-load', '--allow-network', '--peer', '192.0.2.1')
        args.duration_s = 10
        calls = []
        def fake(argv, *a, **kw):
            calls.append(argv)
            if '--version' in argv:
                return 'iperf3 fixture-version', ''
            if '-V' in argv:
                return 'ping fixture-version', ''
            if '-n' in argv and argv[0] == 'ping':
                return '64 bytes time=1.25 ms', ''
            return json.dumps({'end':{'sum_sent':{'bytes':bench.LIMIT,'bits_per_second':800000}}}), ''
        with patch.object(bench.shutil, 'which', side_effect=lambda name:name):
            raw = bench.execute_live(args, {}, runner=fake)
            self.assertEqual(raw['latency_ms'], 1.25)
            self.assertEqual(raw['bytes_per_second'], 100000)
            self.assertIn(str(bench.LIMIT), calls[-1])
            self.assertEqual(len(calls), 4)
            args.peer = '127.0.0.1'
            with self.assertRaises(ValueError):
                bench.execute_live(args, {}, runner=fake)
        with patch.object(bench.shutil, 'which', return_value=None):
            with self.assertRaises(FileNotFoundError):
                bench.execute_live(args, {}, runner=fake)

    def test_storage_timeout_cleanup(self):
        args = self.args('storage', '--execute', '--allow-load', '--allow-write')
        args.duration_s = 1
        def timeout(*a, **kw):
            raise TimeoutError('fixture deadline')
        with tempfile.TemporaryDirectory() as td:
            args.approved_dir = td
            with self.assertRaises(TimeoutError):
                bench.execute_live(args, {}, runner=timeout)
            self.assertEqual(list(Path(td).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
