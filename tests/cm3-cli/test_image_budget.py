import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('image_budget', ROOT / 'scripts/cm3-image-budget.py')
budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(budget)


class ImageBudget(unittest.TestCase):
    def ledger(self, count):
        return dict(maximum_full_image_attempts=3, maximum_concurrent_full_images=1,
                    full_image_attempts=[dict(run_url=f'https://github.com/example/actions/runs/{n + 1}',
                                              run_attempt=1, commit=str(n) * 40, hypothesis=f'fix{n}')
                                         for n in range(count)])

    def history(self, count):
        return [dict(run_id=n + 1, run_attempt=1, commit=str(n) * 40, status='completed')
                for n in range(count)]

    def test_three_allowed_fourth_rejected(self):
        for count in range(3):
            result = budget.admit(self.ledger(count), self.history(count), 99, 'a' * 40, 'new specific fix')
            self.assertEqual(result['cumulative_attempts'], count + 1)
            self.assertEqual(result['maximum_attempts'], 3)
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            budget.admit(self.ledger(3), self.history(3), 99, 'a' * 40, 'fourth')

    def test_missing_changed_duplicate_or_unrecorded_history_rejected(self):
        ledger = self.ledger(1)
        histories = [[], self.history(1) * 2, self.history(2),
                     [dict(self.history(1)[0], commit='f' * 40)]]
        for history in histories:
            with self.subTest(history=history), self.assertRaises(ValueError):
                budget.admit(ledger, history, 99, 'a' * 40, 'new')

    def test_rerun_and_overlap_and_repeated_hypothesis_rejected(self):
        for ledger, history, run_id, hypothesis in [
                (self.ledger(1), self.history(1), 1, 'new'),
                (self.ledger(1), [dict(self.history(1)[0], status='in_progress')], 99, 'new'),
                (self.ledger(1), self.history(1), 99, 'fix0')]:
            with self.subTest(run_id=run_id, hypothesis=hypothesis), self.assertRaises(ValueError):
                budget.admit(ledger, history, run_id, 'a' * 40, hypothesis)

    def test_policy_and_revision_are_not_relaxed(self):
        for field, value in [('maximum_full_image_attempts', 4), ('maximum_concurrent_full_images', 2)]:
            ledger = self.ledger(0)
            ledger[field] = value
            with self.assertRaises(ValueError):
                budget.admit(ledger, [], 99, 'a' * 40, 'new')
        for revision, hypothesis in [('main', 'new'), ('a' * 40, ' ')]:
            with self.assertRaises(ValueError):
                budget.admit(self.ledger(0), [], 99, revision, hypothesis)
