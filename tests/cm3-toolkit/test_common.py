import contextlib

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/cm3-toolkit'))
from common import add_record, emit_result, make_result, validate_result


class CommonTests(unittest.TestCase):
    def result(self):
        r = make_result('inspection', synthetic=True, fixture_id='unit')
        add_record(r, 'test.metric', 'ok', value=123, unit='bytes')
        return r

    def test_roundtrip_stdout(self):
        r = self.result()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            emit_result(r)
        self.assertEqual(json.loads(out.getvalue()), r)

    def test_invalid_values(self):
        for value in (float('nan'), float('inf'), None):
            r = self.result()
            r['records'][0]['value'] = value
            with self.assertRaises(ValueError):
                validate_result(r)

    def test_unknown_status_kind_and_provenance(self):
        for change in ('status', 'kind', 'synthetic', 'fixture_id', 'origin'):
            r = self.result()
            if change == 'status':
                r['records'][0]['status'] = 'PASS'
            elif change == 'kind':
                r['kind'] = 'unknown'
            elif change == 'synthetic':
                r['provenance']['synthetic'] = False
            elif change == 'origin':
                r['provenance']['origin'] = 'approved-test'
            else:
                r['provenance']['fixture_id'] = None
            with self.assertRaises(ValueError):
                validate_result(r)

    def test_unavailable_must_have_reason_and_null_value(self):
        r = self.result()
        r['records'][0].update(status='unavailable', reason='missing')
        with self.assertRaises(ValueError):
            validate_result(r)
        r['records'][0]['value'] = None
        validate_result(r)
        r['records'][0]['reason'] = None
        with self.assertRaises(ValueError):
            validate_result(r)

    def test_executed_bounds_and_conditions(self):
        r = self.result()
        r['kind'] = 'benchmark'
        r['authorization'].update(execute=True, load=True)
        with self.assertRaises(ValueError):
            validate_result(r)
        r['authorization']['scope_ref'] = 'test-only'
        r['conditions'] = {'protocol_id': 'fixture', 'role': 'baseline', 'repetition': 1,
                           'duration_s': 10}
        r['time'].update(clock='monotonic', duration_s=10,
                         start_utc='2026-10-25T00:00:00Z', end_utc='2026-10-25T00:00:10Z')
        validate_result(r)
        r['time']['duration_s'] = 4000
        with self.assertRaises(ValueError):
            validate_result(r)

    def test_all_fields_and_nonfinite_conditions(self):
        for key in self.result():
            r = self.result()
            del r[key]
            with self.assertRaises(ValueError):
                validate_result(r)
        r = self.result()
        r['conditions'] = {'bad': float('nan')}
        with self.assertRaises(ValueError):
            validate_result(r)

    def test_duplicate_records(self):
        r = self.result()
        r['records'] *= 2
        with self.assertRaises(ValueError):
            validate_result(r)

    def test_wrong_json_shapes_always_raise_value_error(self):
        for key in self.result():
            for value in (None, [], {}, 3, True):
                r = self.result()
                r[key] = value
                if key in {'records', 'sources', 'errors'} and value == []:
                    continue
                if key == 'conditions' and value == {}:
                    continue
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_result(r)

    def test_output_rejects_pseudo_filesystems(self):
        for path in ('/proc/new.json', '/sys/new.json', '/dev/new.json'):
            with self.assertRaises(ValueError):
                emit_result(self.result(), path)

    def test_executed_missing_and_oversized_conditions(self):
        r = self.result()
        r['authorization'].update(execute=True, scope_ref='unit-only')
        r['time'].update(clock='monotonic', duration_s=1,
                         start_utc='2026-10-25T00:00:00Z', end_utc='2026-10-25T00:00:01Z')
        r['conditions'] = {'protocol_id': 'unit', 'duration_s': 10,
                           'role': 'baseline', 'repetition': 1}
        for key in list(r['conditions']):
            value = r['conditions'].pop(key)
            with self.assertRaises(ValueError):
                validate_result(r)
            r['conditions'][key] = value
        for key, value in (('duration_s', 61), ('duration_s', -1), ('memory_mib', 257),
                           ('file_mib', 65), ('sustained', True)):
            original = r['conditions'].copy()
            r['conditions'][key] = value
            with self.assertRaises(ValueError):
                validate_result(r)
            r['conditions'] = original

    def test_safe_output_no_clobber_or_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out = base / 'result.json'
            emit_result(self.result(), out)
            original = out.read_bytes()
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(OSError):
                emit_result(self.result(), out)
            self.assertEqual(out.read_bytes(), original)
            link = base / 'link'
            link.symlink_to(out)
            with self.assertRaises(OSError):
                emit_result(self.result(), link)
            (base / 'dirlink').symlink_to(base, target_is_directory=True)
            with self.assertRaises(OSError):
                emit_result(self.result(), base / 'dirlink/new.json')
            with self.assertRaises(ValueError):
                emit_result(self.result(), base / '../escape.json')
            os.mkfifo(base / 'fifo')
            with self.assertRaises(OSError):
                emit_result(self.result(), base / 'fifo')
            with self.assertRaises(OSError):
                emit_result(self.result(), base / 'missing/result.json')


if __name__ == '__main__':
    unittest.main()
