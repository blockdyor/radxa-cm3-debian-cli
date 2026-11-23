import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('stage_a', ROOT / 'scripts/cm3-image-stage-a.py')
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class SonarEvidence(unittest.TestCase):
    def test_failed_regressions_leave_real_error_in_ci_logs_and_no_pass_receipt(self):
        class Broken(unittest.TestCase):
            def runTest(self):
                self.fail('deliberate regression diagnostic fixture')

        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            errors = io.StringIO()
            with patch.object(stage.unittest.defaultTestLoader, 'discover',
                              return_value=unittest.TestSuite([Broken()])), \
                    patch.dict(os.environ, GITHUB_RUN_ID='12'), patch.object(stage.sys, 'stderr', errors):
                with self.assertRaisesRegex(ValueError, 'regressions'):
                    stage.regression(work, 'a' * 40)
            self.assertIn('deliberate regression diagnostic fixture', errors.getvalue())
            report = json.loads((work / 'evidence/image-offline-tests.json').read_text())
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(report['failures'], 1)

    def answers(self, revision='a' * 40, gate='OK', issues=0, hotspots=0):
        return [{'pullRequests': [dict(key='1', commit=dict(sha=revision),
                                      status=dict(qualityGateStatus=gate), analysisDate='now')]},
                dict(total=issues), dict(paging=dict(total=hotspots))]

    def test_exact_analysis_and_empty_current_findings_required(self):
        with patch.object(stage, 'sonar_get', side_effect=self.answers()):
            self.assertEqual(stage.verify_sonar('a' * 40)['source_revision'], 'a' * 40)
        for args in [dict(revision='b' * 40), dict(gate='ERROR'), dict(issues=1), dict(hotspots=1)]:
            with self.subTest(args=args), patch.object(stage, 'sonar_get', side_effect=self.answers(**args)):
                with self.assertRaises(ValueError):
                    stage.verify_sonar('a' * 40)

    def test_unavailable_analysis_is_not_pass(self):
        with patch.object(stage, 'sonar_get', return_value={'pullRequests': []}):
            with self.assertRaises(ValueError):
                stage.verify_sonar('a' * 40)
        with patch.object(stage, 'sonar_get', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError):
                stage.verify_sonar('a' * 40)

    def test_stale_or_skipped_test_receipts_cannot_create_stage_a(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            tests = dict(status='PASS', source_revision='a' * 40, run_id='12', tests=1,
                         failures=0, errors=0, skips=0)
            for changes in [dict(source_revision='b' * 40), dict(run_id='13'), dict(skips=1),
                            dict(tests=0), dict(tests=True), dict(status='FAIL')]:
                with self.subTest(changes=changes):
                    (work / 'evidence/image-offline-tests.json').write_text(json.dumps(dict(tests, **changes)))
                    with patch.object(stage.assembly, 'boundary', return_value='a' * 40), \
                            patch.object(stage.assembly, 'authenticate', return_value={}), \
                            patch.dict(os.environ, GITHUB_RUN_ID='12'), \
                            patch.object(stage, 'verify_sonar') as sonar:
                        with self.assertRaisesRegex(ValueError, 'offline test evidence'):
                            stage.produce(work)
                        sonar.assert_not_called()
                    self.assertFalse((work / 'evidence/image-stage-a.json').exists())

    def test_authentication_failure_cannot_create_receipt(self):
        with patch.object(stage.assembly, 'boundary', return_value='a' * 40), \
                patch.object(stage.assembly, 'authenticate', side_effect=ValueError('signature')), \
                patch.dict(os.environ, GITHUB_RUN_ID='12'), \
                patch.object(stage, 'verify_sonar') as sonar:
            with self.assertRaisesRegex(ValueError, 'signature'):
                stage.produce(Path('/work'))
            sonar.assert_not_called()

    def test_producer_binds_evidence_hashes_without_qualifying_hardware(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            evidence = work / 'evidence'
            evidence.mkdir()
            names = ['result.json', 'arm64-result.json', 'board-lifecycle.json', 'board-manifest.json',
                     'local-repository.json', 'rsdk-profile.json', 'rsdk-profile-result.json',
                     'rsdk-profile-packages.tsv']
            for name in names:
                (evidence / name).write_text('fixture evidence\n')
            (evidence / 'image-offline-tests.json').write_text(json.dumps(dict(
                status='PASS', source_revision='a' * 40, run_id='12', tests=1, failures=0, errors=0, skips=0)))
            with patch.object(stage.assembly, 'boundary', return_value='a' * 40), \
                    patch.object(stage.assembly, 'authenticate', return_value={'source_lock_sha256': 'b' * 64}), \
                    patch.dict(os.environ, GITHUB_RUN_ID='12'), \
                    patch.object(stage, 'verify_sonar', return_value={'gate': 'OK'}):
                report = stage.produce(work)
                with self.assertRaises(FileExistsError):
                    stage.produce(work)
            self.assertEqual(report['decision']['hardware'], 'UNTESTED')
            self.assertEqual(report['decision']['stable_release'], 'BLOCKED')
            self.assertEqual(report['source_revision'], 'a' * 40)
            for name, digest in report['evidence_sha256'].items():
                self.assertEqual(digest, stage.assembly.profile.probe.digest(evidence / name))
