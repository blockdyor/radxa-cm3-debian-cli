#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build only the project-owned configuration package, without installing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSION = '0.1.0'
PAYLOAD = (
    'etc/u-boot-menu/conf.d/99-cm3-cli.conf',
    'etc/initramfs-tools/conf.d/cm3-cli',
    'etc/ssh/sshd_config.d/00-cm3-cli.conf',
    'etc/systemd/system/ssh.service.d/cm3-cli.conf',
    'usr/lib/systemd/system/NetworkManager.service.d/cm3-cli.conf',
    'usr/lib/systemd/system/cm3-cli-enroll.service',
    'usr/lib/systemd/system/cm3-cli-firewall.service',
    'usr/lib/cm3-cli/enroll.py',
    'usr/lib/cm3-cli/boot-update',
    'usr/share/cm3-cli/firewall.nft',
)


def build(destination, revision, epoch):
    if re.fullmatch('[0-9a-f]{40}', revision) is None or epoch < 0:
        raise ValueError('full source revision and nonnegative SOURCE_DATE_EPOCH required')
    destination = Path(destination)
    if destination.exists():
        raise ValueError('refusing to overwrite package output')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cm3-board-') as directory:
        stage = Path(directory) / 'root'
        control = stage / 'DEBIAN'
        for source_dir, names, target_dir in [
                (HERE / 'root', PAYLOAD, stage),
                (HERE / 'control', ('control', 'postinst', 'prerm', 'postrm'), control)]:
            for name in names:
                source = source_dir / name
                if source.is_symlink() or not source.is_file():
                    raise ValueError('package inputs must be regular allowlisted files')
                target = target_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                target.chmod(0o644)
        for path in control.iterdir():
            path.chmod(0o755 if path.name in {'postinst', 'prerm', 'postrm'} else 0o644)
        helper = stage / 'usr/lib/cm3-cli'
        helper.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'scripts/cm3-owner-config.py', helper / 'owner_config.py')
        (helper / 'owner_config.py').chmod(0o644)
        for name in ['enroll.py', 'boot-update']:
            (helper / name).chmod(0o755)
        links = {
            'etc/kernel/install.d/99-update-overlay.install': '/dev/null',
            'etc/kernel/postinst.d/zz-cm3-cli': '/usr/lib/cm3-cli/boot-update',
            'etc/kernel/postrm.d/zz-cm3-cli': '/usr/lib/cm3-cli/boot-update',
            'etc/systemd/system/ssh.socket': '/dev/null',
            'etc/systemd/system/systemd-networkd.service': '/dev/null',
            'etc/systemd/system/systemd-networkd.socket': '/dev/null',
        }
        for name, target in links.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target)
        doc = stage / 'usr/share/doc/cm3-cli-board-support'
        doc.mkdir(parents=True)
        shutil.copyfile(ROOT / 'LICENSE', doc / 'copyright')
        shutil.copyfile(HERE / 'README', doc / 'README')
        provenance = {
            'package': 'cm3-cli-board-support', 'version': VERSION,
            'source_revision': revision,
            'source_date_epoch': epoch,
            'source_lock_sha256': hashlib.sha256((ROOT / 'project/cm3-cli/source-lock.json').read_bytes()).hexdigest(),
            'target': 'radxa-cm3-rpi-cm4-io',
            'configuration_reference': 'radxa-pkg/radxa-system-config@263af2c8c241430e994ffd18bbb8ddfbebf36434',
            'implementation': 'project-owned; no vendor umbrella or credentials',
        }
        (doc / 'source.json').write_text(json.dumps(provenance, sort_keys=True, indent=2) + '\n')
        conffiles = sorted('/' + str(path.relative_to(stage)) for path in (stage / 'etc').rglob('*')
                           if path.is_file() and not path.is_symlink())
        (control / 'conffiles').write_text('\n'.join(conffiles) + '\n')
        executable = {'DEBIAN/postinst', 'DEBIAN/prerm', 'DEBIAN/postrm',
                      'usr/lib/cm3-cli/enroll.py', 'usr/lib/cm3-cli/boot-update'}
        stage.chmod(0o755)
        for path in stage.rglob('*'):
            if not path.is_symlink():
                path.chmod(0o755 if path.is_dir() or str(path.relative_to(stage)) in executable else 0o644)
        env = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch))
        subprocess.run(['dpkg-deb', '--root-owner-group', '--uniform-compression', '-Zgzip',
                        '--build', str(stage), str(destination)], env=env, check=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--epoch', required=True, type=int)
    args = parser.parse_args()
    try:
        current = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        paths = ['packages/cm3-cli-board-support', 'scripts/cm3-owner-config.py',
                 'project/cm3-cli/source-lock.json', 'LICENSE']
        dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--', *paths], text=True)
        if args.revision != current or dirty:
            raise ValueError('package inputs must be clean and match the exact checked-out commit')
        build(args.output, args.revision, args.epoch)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Board-support package build failed: {error}\n')


if __name__ == '__main__':
    main()
