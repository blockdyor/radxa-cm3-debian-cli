import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


delivery = load('delivery', 'cm3-image-delivery.py')
publish = load('publish', 'cm3-publish-image.py')


class SourceDelivery(unittest.TestCase):
    def test_public_distribution_fails_closed_even_with_approved_environment(self):
        with patch.dict('os.environ', {'PUBLIC_DISTRIBUTION': 'true'}):
            with self.assertRaisesRegex(ValueError, 'OVERLAY-1'):
                publish.stage(Path('/unused'))

    def test_build_only_stages_no_payloads_or_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            image = work / 'image-output'
            sources = work / 'delivery-inputs'
            evidence = work / 'evidence'
            for directory in [image, sources, evidence]:
                directory.mkdir()
            revision = 'a' * 40
            identity = dict(source_revision=revision, run_id='123', label=publish.LABEL)
            compressed = image / (publish.assembly.NAME + '.xz')
            compressed.write_bytes(b'test fixture, not an assembled image')
            report = dict(identity, status='PASS', hardware='UNTESTED', stable_release='BLOCKED',
                          compressed_sha256=publish.assembly.profile.probe.digest(compressed),
                          image_sha256='b' * 64, image_bytes=100, compressed_bytes=compressed.stat().st_size)
            (image / 'verification.json').write_text(json.dumps(report))
            (image / 'packages.tsv').write_text('example\t1\tarm64\n')
            names = ['modified-bsp-and-builder-sources.tar.gz', 'installed-notices.tar.gz',
                     'firmware-files.json', 'installed-source-identities.tsv', 'source-lock.json',
                     'loader-inputs.json', 'debian-sources/example.dsc']
            for name in names:
                path = sources / name
                path.parent.mkdir(exist_ok=True)
                path.write_text('source fixture, must not be published')
            delivery_report = dict(identity, files={name: publish.assembly.profile.probe.digest(sources / name) for name in names})
            (sources / 'delivery-inputs.json').write_text(json.dumps(delivery_report))
            for name in ['image-stage-a.json', 'image-admission.json', 'image-offline-tests.json']:
                (evidence / name).write_text('{}')
            for directory in [image, evidence]:
                (directory / 'unreviewed.cms').write_text('must not be published')
                (directory / 'secret.key').write_text('test-only, not a real key')
            with patch.object(publish.assembly, 'boundary', return_value=revision), patch.dict('os.environ', GITHUB_RUN_ID='123'):
                publish.diagnostics(work)
            destination = work / 'public-diagnostics'
            self.assertEqual({p.name for p in destination.iterdir()},
                             {'verification.json', 'packages.tsv', 'image-stage-a.json', 'image-admission.json',
                              'image-offline-tests.json', 'README.txt', 'RAW-SHA256SUMS', 'IMAGE-XZ-SHA256SUMS',
                              'engineering-result.json', 'SHA256SUMS'})
            self.assertFalse((work / 'public-image').exists())
            engineering = json.loads((destination / 'engineering-result.json').read_text())
            self.assertEqual(engineering['engineering'], 'PASS')
            self.assertEqual(engineering['redistribution'], 'BLOCKED: OVERLAY-1')
            self.assertNotIn('SHA256SUMS', engineering['files'])
            shutil_destination = work / 'previous-diagnostics'
            destination.rename(shutil_destination)
            compressed.write_bytes(b'tampered')
            with patch.object(publish.assembly, 'boundary', return_value=revision), patch.dict('os.environ', GITHUB_RUN_ID='123'):
                with self.assertRaisesRegex(ValueError, 'image changed'):
                    publish.diagnostics(work)
            self.assertFalse(destination.exists())

    def test_all_workflow_uploads_are_explicitly_non_payload_for_build_only(self):
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        packages, provenance = workflow.split('\n  provenance:\n')
        steps = packages.split('      - name: ')[1:]
        upload_steps = [step for step in steps if 'uses: actions/upload-artifact@' in step]
        self.assertEqual(len(upload_steps), 4)
        for step in upload_steps:
            if 'path: package-work/public-diagnostics/' in step:
                self.assertIn('if: inputs.experimental_image && !inputs.public_distribution', step)
            elif 'path: package-work/public-image/' in step:
                self.assertIn('if: inputs.experimental_image && inputs.public_distribution', step)
            else:
                self.assertIn('if: always() && !inputs.experimental_image', step)
        self.assertIn('if test "$PUBLIC_DISTRIBUTION" != false; then', workflow)
        self.assertIn('OVERLAY-1 unresolved; public payload distribution is blocked', workflow)
        self.assertNotIn('actions/cache@', workflow)
        self.assertIn('provenance-input/engineering-result.json', provenance)
        self.assertIn('--source-digest "$APPROVED_SHA"', provenance)
        self.assertIn('if: always() && !inputs.experimental_image',
                      next(step for step in steps if step.startswith('Encrypt allowlisted')))

    def test_actual_build_configs_are_required_and_kernel_evidence_must_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            kernel = work / 'linux-rk2410-nocsf/src/.config'
            loader = work / 'u-boot-rk2601/src/.config'
            retained = work / 'evidence/kernel.config'
            for path in [kernel, loader, retained]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('CONFIG_TEST=y\n')
            self.assertEqual(delivery.build_configs(work), {'kernel.config': kernel, 'u-boot.config': loader})
            kernel.write_text('CONFIG_TEST=n\n')
            with self.assertRaisesRegex(ValueError, 'differs'):
                delivery.build_configs(work)
            kernel.write_bytes(retained.read_bytes())
            for content in ['', None]:
                if content is None:
                    loader.unlink()
                else:
                    loader.write_text(content)
                with self.assertRaises((ValueError, OSError)):
                    delivery.build_configs(work)
            loader.symlink_to(kernel)
            with self.assertRaises(ValueError):
                delivery.build_configs(work)

    def test_source_identity_strictly_matches_download_arguments(self):
        manifest = 'base\t1\tarm64\tbase-source\t1:2-3\nlocal\t1\tall\tlocal\t1\n'
        self.assertEqual(delivery.source_specs(manifest, {'local'}), ['base-source=1:2-3'])
        for bad in [manifest.replace('base-source', '--unsafe'), manifest.replace('1:2-3', '../bad'),
                    manifest.replace('arm64', 'amd64'), 'base\t1\n', '']:
            with self.assertRaises(ValueError):
                delivery.source_specs(bad, {'local'})

    def test_archive_includes_modified_tracked_source_configs_and_not_untracked_keys_or_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'
            root.mkdir()
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True)
            (root / 'source.c').write_text('before\n')
            subprocess.run(['git', '-C', str(root), 'add', 'source.c'], check=True)
            (root / 'source.c').write_text('modified\n')
            (root / '.config').write_text('CONFIG_EXAMPLE=y\n')
            (root / 'private.key').write_text('test-only, not a real key\n')
            (root / 'generated.o').write_text('not source\n')
            archive_path = Path(temporary) / 'source.tar.gz'
            with tarfile.open(archive_path, 'w:gz') as archive:
                delivery.archive_checkout(archive, root, 'export')
            with tarfile.open(archive_path) as archive:
                self.assertEqual(set(archive.getnames()), {'export/source.c', 'export/.config'})
                self.assertEqual(archive.extractfile('export/source.c').read(), b'modified\n')

    def test_public_material_set_rejects_tamper_extra_and_redirected_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            names = ['modified-bsp-and-builder-sources.tar.gz', 'installed-notices.tar.gz',
                     'firmware-files.json', 'installed-source-identities.tsv', 'source-lock.json',
                     'loader-inputs.json', 'debian-sources/example.dsc']
            for name in names:
                path = directory / name
                path.parent.mkdir(exist_ok=True)
                path.write_text('fixture')
            (directory / 'delivery-inputs.json').write_text('{}')
            manifest = dict(files={name: publish.assembly.profile.probe.digest(directory / name) for name in names})
            self.assertEqual(len(publish.checked_materials(directory, manifest)), 8)
            incomplete = dict(files={name: digest for name, digest in manifest['files'].items()
                                     if name != 'loader-inputs.json'})
            (directory / 'loader-inputs.json').unlink()
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                publish.checked_materials(directory, incomplete)
            (directory / 'loader-inputs.json').write_text('fixture')
            extra = directory / 'secret.key'
            extra.write_text('not a real key')
            with self.assertRaisesRegex(ValueError, 'set changed'):
                publish.checked_materials(directory, manifest)
            extra.unlink()
            target = directory / names[0]
            target.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                publish.checked_materials(directory, manifest)
            target.unlink()
            target.symlink_to(directory / names[1])
            with self.assertRaises(ValueError):
                publish.checked_materials(directory, manifest)

    def test_workflow_native_order_and_single_manual_publication(self):
        # Inspect the actual workflow; no fake successful provider/job response.
        workflow = (ROOT / '.github/workflows/build.yaml').read_text()
        steps = ['Prepare exact corresponding sources and preserved notices',
                 'Produce authenticated exact-head Stage A evidence',
                 'Reconcile cumulative three-image budget before assembly',
                 'Assemble experimental CM3 disk image',
                 'Independently inspect actual image and stage sanitized delivery',
                 'Upload reviewed EXPERIMENTAL image and corresponding materials']
        positions = [workflow.index('- name: ' + step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('default: false', workflow)
        self.assertIn('path: package-work/public-image/', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertIn('group: cm3-phase-b-exclusive', workflow)
        self.assertIn('timeout-minutes: 180', workflow)
        shell = (ROOT / 'scripts/cm3-external-preflight.sh').read_text()
        self.assertLess(shell.index('libguestfs-test-tool'), shell.index('cm3-source-preflight.py --workdir'))
        self.assertLess(shell.index('cm3-image-stage-a.py tests'), shell.index('cm3-source-preflight.py --workdir'))
