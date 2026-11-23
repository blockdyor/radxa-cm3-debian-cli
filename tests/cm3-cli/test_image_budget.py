import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('image_budget', ROOT / 'scripts/cm3-image-budget.py')
budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(budget)


class ImageBudget(unittest.TestCase):
    def test_host_receipt_uses_host_owned_staging_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = root / 'preflight-work/evidence'
            host.mkdir(parents=True)
            run = dict(id=99, head_sha='a' * 40, run_attempt=1)
            environment = dict(GITHUB_REPOSITORY=budget.REPOSITORY, GITHUB_RUN_ATTEMPT='1',
                               GITHUB_REF='refs/heads/dev/cm3-debian-cli', GITHUB_RUN_ID='99',
                               GITHUB_SHA='a' * 40, HYPOTHESIS='test fixture: receipt staging')
            ledger = root / 'docs/cm3-cli/attempts.json'
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps(self.ledger(0)))
            with patch.object(budget, 'ROOT', root), patch.dict('os.environ', environment), \
                    patch.object(budget, 'pages', side_effect=[[run], []]):
                budget.main(check_only=True)
            self.assertFalse((host / 'image-admission.json').exists())
            with patch.object(budget, 'ROOT', root), patch.dict('os.environ', environment), \
                    patch.object(budget, 'pages', side_effect=[[run], []]):
                budget.main()
            receipt = host / 'image-admission.json'
            original = receipt.read_bytes()
            self.assertEqual(json.loads(original)['status'], 'ADMITTED')
            self.assertFalse((root / 'package-work').exists())
            with patch.object(budget, 'ROOT', root), patch.dict('os.environ', environment), \
                    patch.object(budget, 'pages', side_effect=[[run], []]):
                with self.assertRaises(FileExistsError):
                    budget.main()
            self.assertEqual(receipt.read_bytes(), original)

    def test_workflow_copies_only_fresh_receipt_before_assembly(self):
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        step = workflow.split('- name: Reconcile cumulative three-image budget before assembly')[1].split('- name: Assemble')[0]
        self.assertLess(step.index('python3 scripts/cm3-image-budget.py'), step.index('docker cp'))
        self.assertIn('set -euo pipefail', step)
        self.assertIn('test ! -e /work/evidence/image-admission.json', step)
        self.assertIn('test ! -L /work/evidence/image-admission.json', step)
        self.assertIn('docker cp preflight-work/evidence/image-admission.json', step)
        self.assertIn(':/work/evidence/image-admission.json', step)
        self.assertNotIn('chmod', step)
        self.assertNotIn('chown', step)
        self.assertLess(workflow.index('python3 scripts/cm3-image-budget.py --check-only'),
                        workflow.index('- name: Source-build'))

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
