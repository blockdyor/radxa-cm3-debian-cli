"""Assembly admission and real Jsonnet rendering only; NEVER build/mount locally."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('cm3_assembly', ROOT / 'scripts/cm3-assemble-image.py')
assembly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembly)


class Admission(unittest.TestCase):
    def test_offline_ssh_parser_accepts_explicit_temporary_key_without_weakening_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'run').mkdir()
            output = '\n'.join(['permitrootlogin no', 'passwordauthentication no',
                                'kbdinteractiveauthentication no', 'authenticationmethods publickey',
                                'allowgroups cm3-cli-owner'])
            with patch.object(assembly.profile.probe, 'chroot', return_value=output) as chroot:
                assembly.profile.probe.verify_ssh_policy(root, host_key='/run/check/key')
                self.assertEqual(chroot.call_args_list[0].args, (root, 'sshd', '-t', '-h', '/run/check/key'))
                self.assertEqual(chroot.call_args_list[1].args, (root, 'sshd', '-T', '-h', '/run/check/key'))
            with patch.object(assembly.profile.probe, 'chroot', return_value=output.replace('permitrootlogin no', 'permitrootlogin yes')):
                with self.assertRaises(ValueError):
                    assembly.profile.probe.verify_ssh_policy(root, host_key='/run/check/key')

    def test_local_cli_is_rejected_without_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            result = subprocess.run(['python3', str(ROOT / 'scripts/cm3-assemble-image.py'),
                                     '--workdir', str(work)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('external GitHub-hosted', result.stderr)
            self.assertEqual(list(work.iterdir()), [])

    def test_local_environment_cannot_reach_authentication_or_builder(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(assembly, 'authenticate') as authenticate, \
                patch.object(assembly, 'render') as render:
            with self.assertRaises(ValueError):
                assembly.assemble(Path('/work'))
            authenticate.assert_not_called()
            render.assert_not_called()

    def test_regular_file_rejects_symlink_directory_and_parent_redirection(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            file = base / 'file'
            file.write_text('not an image')
            self.assertEqual(assembly.regular(file), file)
            link = base / 'link'
            link.symlink_to(file)
            for path in [base, link]:
                with self.assertRaises(ValueError):
                    assembly.regular(path)
            redirected = base / 'redirected'
            redirected.symlink_to(base, target_is_directory=True)
            with self.assertRaises(ValueError):
                assembly.regular(redirected / 'file')

    def test_existing_or_symlinked_output_and_temp_fail_before_jsonnet(self):
        for name in ['image-output', 'image-assembly-temp']:
            for symlink in [False, True]:
                with self.subTest(name=name, symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                    work = Path(temporary)
                    path = work / name
                    path.symlink_to(work / 'missing') if symlink else path.mkdir()
                    with patch.object(assembly, 'command') as command:
                        with self.assertRaisesRegex(ValueError, 'fresh output'):
                            assembly.render(work)
                        command.assert_not_called()

    def test_failed_profile_or_receipt_never_reaches_chroot(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            (work / 'evidence/rsdk-profile-result.json').write_text(json.dumps({'status': 'FAIL'}))
            with patch.object(assembly.profile, 'verified_receipt', return_value={}), \
                    patch.object(assembly.profile.probe, 'chroot') as chroot:
                with self.assertRaisesRegex(ValueError, 'authenticated RSDK profile'):
                    assembly.authenticate(work, 'a' * 40, '1')
                chroot.assert_not_called()

    def test_signature_and_admission_failures_propagate(self):
        with patch.object(assembly.profile, 'verified_receipt', side_effect=ValueError('bad signature')), \
                patch.object(assembly.profile.probe, 'chroot') as chroot:
            with self.assertRaisesRegex(ValueError, 'bad signature'):
                assembly.authenticate(Path('/work'), 'a' * 40, '1')
            chroot.assert_not_called()

    def test_exact_head_environment_and_checkout_required(self):
        environment = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                           GITHUB_REPOSITORY='blockdyor/radxa-cm3-debian-cli',
                           GITHUB_SHA='a' * 40, EXPECTED_SHA='a' * 40, GITHUB_RUN_ID='12')
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(assembly.platform, 'machine', return_value='x86_64'), \
                patch.object(assembly.os, 'geteuid', return_value=0), \
                patch.object(Path, 'is_file', return_value=True), \
                patch.object(assembly, 'command', return_value='b' * 40 + '\n'):
            with self.assertRaisesRegex(ValueError, 'checkout differs'):
                assembly.boundary(Path('/work'))
            with patch.dict(os.environ, EXPECTED_SHA='b' * 40):
                with self.assertRaisesRegex(ValueError, 'exact expected head'):
                    assembly.boundary(Path('/work'))

    def test_failed_guestfish_writes_failure_and_never_compresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            failure = subprocess.CalledProcessError(1, ['guestfish'])
            with patch.object(assembly, 'boundary', return_value='a' * 40), \
                    patch.object(assembly, 'experimental_admission', return_value={}), \
                    patch.object(assembly, 'authenticate', return_value={}), \
                    patch.dict(os.environ, GITHUB_RUN_ID='12'), \
                    patch.object(assembly, 'render', return_value=(work / assembly.NAME, work / 'temp', work / 'recipe')), \
                    patch.object(assembly.subprocess, 'run', side_effect=failure) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    assembly.assemble(work)
                self.assertEqual(run.call_count, 1)
            status = json.loads((work / 'evidence/image-assembly-result.json').read_text())
            self.assertEqual(status['status'], 'FAIL')
            self.assertNotIn('image_sha256', status)
            self.assertEqual(status['hardware_boot'], 'UNTESTED')

    def test_missing_admission_cannot_reach_packages_or_builder(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with patch.object(assembly, 'boundary', return_value='a' * 40), \
                    patch.dict(os.environ, GITHUB_RUN_ID='12'), \
                    patch.object(assembly, 'authenticate') as authenticate, \
                    patch.object(assembly, 'render') as render:
                with self.assertRaises(FileNotFoundError):
                    assembly.assemble(work)
                authenticate.assert_not_called()
                render.assert_not_called()

    def test_stage_and_budget_admission_are_bound_and_do_not_qualify_hardware(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            budget = dict(status='ADMITTED', commit='a' * 40, run_id=12, run_attempt=1,
                          maximum_attempts=3, cumulative_attempts=1)
            stage = dict(source_revision='a' * 40, run_id='12',
                         source_lock_sha256=assembly.profile.probe.digest(ROOT / 'project/cm3-cli/source-lock.json'),
                         checks={name: 'PASS' for name in assembly.policy.REQUIRED})
            def check():
                (work / 'evidence/image-admission.json').write_text(json.dumps(budget))
                (work / 'evidence/image-stage-a.json').write_text(json.dumps(stage))
                return assembly.experimental_admission(work, 'a' * 40, '12')
            self.assertEqual(check(), dict(experimental_assembly='ALLOWED', stable_release='BLOCKED', hardware='UNTESTED'))
            for field, value in [('commit', 'b' * 40), ('run_id', 13), ('run_attempt', 2),
                                 ('maximum_attempts', 4), ('cumulative_attempts', 4),
                                 ('cumulative_attempts', True)]:
                with self.subTest(field=field, value=value):
                    original = budget[field]
                    budget[field] = value
                    with self.assertRaises(ValueError):
                        check()
                    budget[field] = original
            for field in stage['checks']:
                stage['checks'][field] = 'UNTESTED'
                with self.assertRaises(ValueError):
                    check()
                stage['checks'][field] = 'PASS'
            stage['source_revision'] = 'b' * 40
            with self.assertRaisesRegex(ValueError, 'exact-head'):
                check()


@unittest.skipUnless(shutil.which('jsonnet'), 'actual Jsonnet executable required')
class Rendering(unittest.TestCase):
    def test_existing_route_renders_real_disk_from_existing_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            output, temp, recipe = assembly.render(work)
            text = recipe.read_text()
            self.assertEqual(output, work / 'image-output/cm3-trixie-arm64-cli.img')
            self.assertIn('disk-create "' + str(output) + '" raw "10G"', text)
            self.assertIn('blocksize:512', text)
            self.assertIn('part-init /dev/sda gpt', text)
            self.assertIn('mkfs ext4 /dev/sda3', text)
            self.assertIn('copy-in ' + str(work / 'rsdk-profile-stage/root') + '/. /', text)
            self.assertIn('/u-boot/radxa-cm3-rpi-cm4-io/setup.sh" update_bootloader "' + str(output) + '" 512', text)
            self.assertIn('resize2fs /dev/sda3', text)
            self.assertIn('!rm -rf "' + str(temp) + '"', text)
            self.assertNotIn('losetup', text)
            self.assertNotIn('tar-in', text)
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.iterdir()), [])

    def test_recipe_collision_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'evidence').mkdir()
            path = work / 'evidence/image-assembly.guestfish'
            path.write_text('original evidence')
            with self.assertRaises(FileExistsError):
                assembly.render(work)
            self.assertEqual(path.read_text(), 'original evidence')
