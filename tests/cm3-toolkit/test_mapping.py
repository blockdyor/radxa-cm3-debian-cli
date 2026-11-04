"""Offline structural checks only; never CM3 or gate acceptance evidence."""
import csv
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / 'docs/cm3-toolkit/sources'
EXPECTED_HASHES = {
    'hardware-matrix.tsv': '24c30e0964dcec3326c723ad8f8b84c39104ff7a8688f33a7e997b2ef2098232',
    'gates-validation-verbatim.txt': '101775854cf704a09bc11277a740fce567d097c3ba74f9b0fb9cc5c8dcbb6c75',
    'gates-consolidated-verbatim.txt': '8265b939c8b7877b900e8f0b43d72fbc192cbd2198d847feae90656d3fe8a094',
}


class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = json.loads((ROOT / 'tools/cm3-toolkit/compatibility.json').read_text())
        with (SOURCES / 'hardware-matrix.tsv').open(newline='') as stream:
            cls.original = list(csv.DictReader(stream, delimiter='\t'))

    def test_immutable_sources_and_gate_definitions(self):
        self.assertEqual(self.mapping['source_sha256'], EXPECTED_HASHES)
        for name, digest in EXPECTED_HASHES.items():
            content = (SOURCES / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), digest, name)
            if name.startswith('gates-'):
                self.assertEqual(re.findall(r'^(G[0-7]) (?=— |[A-Z][^\n:]*:)', content.decode(), re.M),
                                 [f'G{i}' for i in range(8)])

    def test_exact_original_rows_and_no_hardware_promotion(self):
        data = self.mapping
        self.assertEqual(data['schema_version'], 'cm3-toolkit-mapping/v1')
        self.assertEqual(data['target'], 'radxa-cm3-rpi-cm4-io')
        self.assertEqual(data['gate_status'], {f'G{i}': 'NOT EVALUATED' for i in range(8)})
        self.assertEqual([r['id'] for r in data['rows']], [f'H{i:02}' for i in range(1, 29)])
        self.assertEqual(len(self.original), 28)
        for row, original in zip(data['rows'], self.original, strict=True):
            for key in ('id', 'priority', 'applicability', 'interface_or_capability',
                        'equipment_state', 'evidence_basis', 'proposed_test_and_gate', 'procedure'):
                self.assertEqual(row[key], original[key], (row['id'], key))
            self.assertEqual(row['hardware_status'], original['current_status'])
            self.assertEqual(row['hardware_status'], 'UNTESTED')
            self.assertEqual(row['gates'], re.findall(r'G[0-7]\b', original['proposed_test_and_gate']))

    def test_concrete_checks_and_honest_interface_links(self):
        identifiers = []
        for row in self.mapping['rows']:
            self.assertEqual({c['category'] for c in row['checks']},
                             {'files-manifest', 'running-image', 'physical-human'})
            for check in row['checks']:
                identifiers.append(check['id'])
                self.assertTrue(check['id'].startswith(row['id'] + '-'))
                self.assertGreater(len(check['procedure']), 50)
                self.assertTrue(check['prerequisites'])
                self.assertTrue(check['evidence_required'])
                self.assertEqual(check['gates'], row['gates'])
                self.assertEqual(check['status'], 'not_run')
                self.assertFalse(check['establishes_hardware_pass'])
                self.assertIn(check['implementation'], ('manual', 'planned'))
                self.assertTrue(check['unavailable_reason'])
                if check['toolkit_command'] is not None:
                    self.assertEqual(check['implementation'], 'planned')
                    self.assertIsInstance(check['toolkit_command'], list)
                    self.assertNotIn('--execute', check['toolkit_command'])
                    self.assertTrue(check['toolkit_scope'])
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(len(identifiers), 84)


if __name__ == '__main__':
    unittest.main()
