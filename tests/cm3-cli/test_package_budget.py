import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('budget', ROOT / 'scripts/cm3-package-budget.py')
budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(budget)


class PackageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((ROOT / 'docs/cm3-cli/attempts.json').read_text())
        self.runs = [dict(id=int(a['run_url'].rsplit('/', 1)[1]), head_sha=a['commit'],
                          run_attempt=a['run_attempt'], event='workflow_dispatch',
                          workflow_id=budget.WORKFLOW, status='completed', conclusion='failure')
                     for a in self.ledger['package_attempts']]
        self.next_id = max(r['id'] for r in self.runs) + 1

    def append(self):
        self.runs.append(dict(id=self.next_id, head_sha='a' * 40, run_attempt=1,
                              event='workflow_dispatch', workflow_id=budget.WORKFLOW,
                              status='in_progress', conclusion=None))
        self.next_id += 1
        return self.runs[-1]['id']

    def test_historical_three_remain_consumed(self):
        self.assertEqual(self.ledger['maximum_package_attempts'], 6)
        self.assertEqual([a['number'] for a in self.ledger['package_attempts'][:3]], [1, 2, 3])
        self.assertEqual([a['run_url'].rsplit('/', 1)[1]
                          for a in self.ledger['package_attempts'][:3]],
                         ['40294636804', '40655341359', '40656875860'])
        self.assertEqual(self.ledger['maximum_full_image_attempts'], 3)
        self.assertEqual(self.ledger['full_image_attempts'], [])

    def test_six_allowed_and_seventh_rejected_without_ledger_refresh(self):
        while len(self.runs) < 6:
            for run in self.runs:
                run['status'] = 'completed'
            run_id = self.append()
            result = budget.admit(self.ledger, self.runs, run_id, 'a' * 40)
            self.assertEqual(result['cumulative_attempts'], len(self.runs))
        for run in self.runs:
            run['status'] = 'completed'
        run_id = self.append()
        with self.assertRaisesRegex(ValueError, 'seventh attempt prohibited'):
            budget.admit(self.ledger, self.runs, run_id, 'a' * 40)

    def test_rerun_deleted_history_sha_mismatch_and_overlap_fail_closed(self):
        run_id = self.append()
        for change in ['rerun', 'deleted', 'wrong_sha', 'overlap', 'wrong_workflow']:
            with self.subTest(change=change):
                runs = copy.deepcopy(self.runs)
                if change == 'rerun':
                    runs[-1]['run_attempt'] = 2
                elif change == 'deleted':
                    runs.pop(0)
                elif change == 'wrong_sha':
                    runs[-1]['head_sha'] = 'b' * 40
                elif change == 'overlap':
                    runs[0]['status'] = 'in_progress'
                else:
                    runs[-1]['workflow_id'] = 123
                with self.assertRaises(ValueError):
                    budget.admit(self.ledger, runs, run_id, 'a' * 40)


if __name__ == '__main__':
    unittest.main()
