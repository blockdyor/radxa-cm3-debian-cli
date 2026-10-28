import copy
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('preflight', ROOT / 'scripts/cm3-source-preflight.py')
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class SourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / 'project/cm3-cli/source-lock.json').read_text())

    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock.json'
            path.write_text(json.dumps(data))
            return preflight.load_lock(path)

    def test_exact_target_and_nine_package_whitelist(self):
        lock = self.load(self.lock)
        packages = preflight.expected_packages(lock)
        self.assertEqual(len(packages), 9)
        self.assertEqual(packages['linux-image-6.1.84-18+cm3cli1-rk2410-nocsf'],
                         ('6.1.84-18+cm3cli1', 'arm64'))
        self.assertTrue(all('cm3cli1' in version for version, _ in packages.values()))
        self.assertFalse(any('libc-dev' in name for name in packages))
        self.assertFalse(any('rock-3' in name or 'cm3-io' in name for name in packages))

    def test_reject_other_board_suite_architecture_and_sector(self):
        for key, value in [('product', 'radxa-cm3-io'), ('suite', 'bookworm'),
                           ('architecture', 'amd64'), ('sector_size', 4096)]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.lock)
                data['target'][key] = value
                with self.assertRaises(ValueError):
                    self.load(data)

    def test_reject_moving_source_and_container(self):
        data = copy.deepcopy(self.lock)
        data['recipes'][0]['commit'] = 'main'
        with self.assertRaises(ValueError):
            self.load(data)
        data = copy.deepcopy(self.lock)
        data['builder_image'] = 'debian:trixie-slim'
        with self.assertRaises(ValueError):
            self.load(data)

    def test_reject_duplicate_or_missing_recipe(self):
        data = copy.deepcopy(self.lock)
        data['recipes'][0] = data['recipes'][1]
        with self.assertRaises(ValueError):
            self.load(data)

    def test_patch_is_exact_and_cannot_be_applied_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'input').write_text('before\n')
            preflight.local_patch(root, 'input', 'before', 'after')
            self.assertEqual((root / 'input').read_text(), 'after\n')
            with self.assertRaises(ValueError):
                preflight.local_patch(root, 'input', 'before', 'after')

    def test_source_build_refuses_local_execution(self):
        result = subprocess.run(['python3', str(ROOT / 'scripts/cm3-source-preflight.py')],
                                env={'PATH': '/usr/local/bin:/usr/bin:/bin'},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('restricted to the external AMD64 CI container', result.stderr)

    def test_package_budget_refuses_external_eighth_compile_before_workdir(self):
        errors = io.StringIO()
        exhausted = json.loads((ROOT / 'docs/cm3-cli/attempts.json').read_text())
        exhausted['package_attempts'] = [{}] * 7
        with patch.dict(preflight.os.environ, GITHUB_ACTIONS='true',
                        GITHUB_REPOSITORY='blockdyor/radxa-cm3-debian-cli'), \
                patch.object(preflight.platform, 'machine', return_value='x86_64'), \
                patch.object(preflight.os, 'geteuid', return_value=0), \
                patch.object(preflight.json, 'loads', side_effect=[self.lock, exhausted]), \
                patch.object(sys, 'argv', ['cm3-source-preflight.py']), \
                contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit):
                preflight.main()
        self.assertIn('package attempt budget exhausted', errors.getvalue())

    def test_loader_initialization_patch_is_narrow_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'src/drivers/power/charge_animation.c'
            target.parent.mkdir(parents=True)
            before = '\tint soc, voltage, current, key_state;'
            after = '\tint soc = 0, voltage, current = 0, key_state;'
            target.write_text('static void fixture(void) {\n' + before + '\n}\n')
            preflight.local_patch(root, 'src/drivers/power/charge_animation.c', before, after)
            self.assertIn(after, target.read_text())
            with self.assertRaises(ValueError):
                preflight.local_patch(root, 'src/drivers/power/charge_animation.c', before, after)
        script = (ROOT / 'scripts/cm3-source-preflight.py').read_text()
        self.assertIn("source / name, 'diff', '--binary'", script)
        self.assertNotIn('-Wno-', script)
        self.assertNotIn('KCFLAGS', script)

    def test_manual_only_fixed_concurrency_and_no_image_command(self):
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        self.assertIn('  workflow_dispatch:', workflow)
        for trigger in ['  push:', '  pull_request:', '  schedule:', '  merge_group:']:
            self.assertNotIn(trigger, workflow)
        self.assertIn('group: cm3-phase-b-exclusive', workflow)
        self.assertIn('cancel-in-progress: false', workflow)
        self.assertNotIn('rsdk build', workflow)
        self.assertNotIn('matrix:', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertNotIn('.github/actions/build', workflow)
        for line in workflow.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'@[0-9a-f]{40}(?:\s|$)')

    def test_kernel_configuration_precedes_parallel_compile_and_arm64_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.github/local').mkdir(parents=True)
            (root / 'Makefile.extra').write_text('DPKG_FLAGS ?= -d\nJOBS=-j$(shell nproc)\n')
            (root / '.github/local/Makefile.local').write_text(
                'KERNEL_DEFCONFIG := rockchip_linux_defconfig rk3576.config radxa.config radxa_custom.config\n')
            (root / 'src/fs/btrfs').mkdir(parents=True)
            (root / 'src/Makefile').write_text('O=$(resolve_btfids_O) clean\n')
            (root / 'src/fs/btrfs/send.c').write_text(
                'kvcalloc(sizeof(*sctx->clone_roots),\n'
                '\t\t\t\t     arg->clone_sources_count + 1,\n'
                '\t\t\t\t     GFP_KERNEL);\n')
            with patch.object(preflight, 'run', return_value='-O2\n') as command:
                preflight.prepare_kernel_recipe(root, root)
            self.assertEqual(command.call_count, 4)
            for call in command.call_args_list:
                self.assertEqual(call.args[:3], ('env', 'DEB_HOST_ARCH=arm64', 'dpkg-buildflags'))
            (root / 'Makefile').write_text(
                'include .github/local/Makefile.local\n'
                '.PHONY: build build-all build-defconfig\n'
                'build: build-defconfig build-all\n'
                'build-defconfig:\n\tsleep 0.1; touch configured\n'
                'build-all:\n\ttest -f configured\n')
            subprocess.run(['make', '-j2', 'build'], cwd=root, check=True, capture_output=True)
            self.assertEqual(json.loads((root / 'kernel-helper-flags.json').read_text())['CFLAGS'], '-O2')
            self.assertNotIn('DPKG_FLAGS ?= -d', (root / 'Makefile.extra').read_text())
            self.assertIn('CFLAGS="$(HOSTCFLAGS)" clean', (root / 'src/Makefile').read_text())
            self.assertIn('kvcalloc(arg->clone_sources_count + 1,',
                          (root / 'src/fs/btrfs/send.c').read_text())

    def test_development_branch_retains_bootstrap_fork_guards(self):
        for name in ['check_linked_issue', 'ci-request-review', 'dependabot',
                     'infra-repo-update-production', 'infra-repo-update-test',
                     'new_version', 'docs', 'release']:
            with self.subTest(workflow=name):
                text = (ROOT / '.github/workflows' / (name + '.yaml')).read_text()
                for job in re.split(r'\n  (?=\S)', text):
                    if 'runs-on:' in job:
                        self.assertIn("github.repository == 'RadxaOS-SDK/rsdk'", job)

    def test_image_entrypoint_is_explicitly_held(self):
        script = (ROOT / 'src/libexec/rsdk/rsdk-build').read_text()
        self.assertIn('CM3 Trixie CLI image assembly is disabled', script)
        self.assertLess(script.index('CM3 Trixie CLI image assembly is disabled'),
                        script.index('local OUTPUT="$PWD/out/'))

    def test_original_gates_and_hardware_rows_preserved(self):
        directory = ROOT / 'docs/cm3-cli'
        expected = json.loads((directory / 'evidence-hashes.json').read_text())
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        with (directory / 'hardware-matrix.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        self.assertEqual([r['id'] for r in rows], [f'H{i:02d}' for i in range(1, 29)])
        self.assertEqual({r['current_status'] for r in rows}, {'UNTESTED'})
        self.assertEqual({p: sum(r['priority'] == p for r in rows) for p in ['P0', 'P1', 'P2']},
                         {'P0': 11, 'P1': 5, 'P2': 12})


if __name__ == '__main__':
    unittest.main()
