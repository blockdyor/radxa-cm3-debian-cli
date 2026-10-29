#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Fail-closed enrollment on the exact CM3 target; never execute /config content."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

from owner_config import MAX_BYTES, validate_owner

ROOT = Path('/')
STATE = 'var/lib/cm3-cli/enrollment.json'
READY = 'run/cm3-cli/enrolled.json'


def read_private(root, relative, limit=16384, public=False):
    path = root / relative
    # All parents must be real, root-owned directories, not account-controlled paths.
    for parent in path.parents:
        if parent == root.parent and root != Path('/'):
            break
        if parent == root:
            break
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError('unsafe enrollment directory')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                info.st_mode & (0o022 if public else 0o077) or
                info.st_nlink != 1 or info.st_size > limit):
            raise ValueError('enrollment files must be private regular root-owned files')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('oversized enrollment file')
    return data


def atomic(root, relative, data, mode=0o600):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('refusing symlink enrollment output')
    fd, temporary = tempfile.mkstemp(prefix='.cm3-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def run(*args):
    # No shell, owner key or JSON in command arguments/logs.
    subprocess.run(args, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'})


def account(root, username):
    entries = [line.split(':') for line in (root / 'etc/passwd').read_text().splitlines()]
    matches = [entry for entry in entries if entry[0] == username]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError('duplicate owner account')
    entry = matches[0]
    if (len(entry) != 7 or not entry[2].isdigit() or not 1000 <= int(entry[2]) < 65534 or
            entry[5] != '/home/' + username or entry[6] != '/bin/bash'):
        raise ValueError('owner account is not the expected regular login account')
    return entry


def locked(root, username):
    matches = [line.split(':') for line in (root / 'etc/shadow').read_text().splitlines()
               if line.split(':', 1)[0] == username]
    return len(matches) == 1 and len(matches[0]) == 9 and matches[0][1].startswith(('!', '*'))


def target(root):
    compatible = (root / 'proc/device-tree/compatible').read_bytes().split(b'\0')
    if b'radxa,cm3-rpi-cm4-io' not in compatible or b'rockchip,rk3566' not in compatible:
        raise ValueError('enrollment restricted to Radxa CM3 on Raspberry Pi CM4 IO')


def document(root):
    config = validate_owner(read_private(root, 'etc/cm3-cli/owner.json', MAX_BYTES))
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    return config, digest


def check(root):
    target(root)
    config, digest = document(root)
    state = json.loads(read_private(root, STATE))
    ready = json.loads(read_private(root, READY))
    expected = {'version': 1, 'username': config['username'], 'digest': digest, 'status': 'complete'}
    if state != expected or ready != expected or account(root, config['username']) is None:
        raise ValueError('incomplete enrollment')
    if not locked(root, 'root') or not locked(root, config['username']):
        raise ValueError('password credentials must remain locked')
    key = read_private(root, 'etc/cm3-cli/authorized_keys/' + config['username'], public=True)
    if key != (config['authorized_key'] + '\n').encode():
        raise ValueError('owner key does not match enrollment')
    sudo = read_private(root, 'etc/sudoers.d/cm3-cli-owner', public=True)
    if sudo != (config['username'] + ' ALL=(ALL:ALL) NOPASSWD: ALL\n').encode():
        raise ValueError('owner administrative policy changed')
    groups = [line.split(':') for line in (root / 'etc/group').read_text().splitlines()
              if line.startswith('cm3-cli-owner:')]
    if (len(groups) != 1 or len(groups[0]) != 4 or not groups[0][2].isascii() or
            not groups[0][2].isdigit() or groups[0][3] != config['username']):
        raise ValueError('SSH owner group changed')
    for entry in (root / 'etc/passwd').read_text().splitlines():
        fields = entry.split(':')
        if (len(fields) != 7 or not fields[3].isascii() or not fields[3].isdigit() or
                (fields[0] != config['username'] and int(fields[3]) == int(groups[0][2]))):
            raise ValueError('SSH owner group has unsafe primary membership')
    machine_id = (root / 'etc/machine-id').read_text().strip()
    if re.fullmatch('[0-9a-f]{32}', machine_id) is None or machine_id == '0' * 32:
        raise ValueError('machine identity not initialized')
    for kind in ['ed25519', 'rsa', 'ecdsa']:
        path = root / ('etc/ssh/ssh_host_' + kind + '_key')
        if not read_private(root, str(path.relative_to(root))):
            raise ValueError('host key missing')
    if 'apparmor' not in (root / 'sys/kernel/security/lsm').read_text().strip().split(','):
        raise ValueError('AppArmor is not active in the booted target kernel')


def enroll(root, command=run):
    (root / READY).unlink(missing_ok=True)
    target(root)
    config, digest = document(root)
    username = config['username']
    state_path = root / STATE
    state = {'version': 1, 'username': username, 'digest': digest, 'status': 'pending'}
    if state_path.exists() or state_path.is_symlink():
        previous = json.loads(read_private(root, STATE))
        if previous not in [state, dict(state, status='complete')]:
            raise ValueError('enrollment differs; offline administrator recovery required')
    elif account(root, username) is not None:
        raise ValueError('refusing to adopt an existing account')
    if account(root, username) is not None:
        rows = [line for line in (root / 'etc/shadow').read_text().splitlines()
                if line.split(':', 1)[0] == username]
        if len(rows) != 1 or len(rows[0].split(':')) != 9:
            # Never repair the global password database or delete a partial user's home.
            raise ValueError('interrupted account database; offline account recovery required')
    atomic(root, STATE, (json.dumps(state, sort_keys=True) + '\n').encode())
    if account(root, username) is None:
        command('/usr/sbin/adduser', '--disabled-password', '--gecos', '', '--home', '/home/' + username,
                '--shell', '/bin/bash', username)
    if account(root, username) is None:
        raise ValueError('owner account creation failed')
    command('/usr/bin/passwd', '--lock', username)
    command('/usr/bin/passwd', '--lock', 'root')
    command('/usr/sbin/groupadd', '--force', '--system', 'cm3-cli-owner')
    command('/usr/sbin/usermod', '--append', '--groups', 'cm3-cli-owner', username)
    # Keys are held outside the user's writable home; partial enrollment cannot enable SSH.
    keydir = root / 'etc/cm3-cli/authorized_keys'
    keydir.mkdir(mode=0o755, exist_ok=True)
    if keydir.is_symlink():
        raise ValueError('unsafe key directory')
    keydir.chmod(0o755)
    atomic(root, 'etc/cm3-cli/authorized_keys/' + username,
           (config['authorized_key'] + '\n').encode(), 0o644)
    atomic(root, 'etc/sudoers.d/cm3-cli-owner', (username + ' ALL=(ALL:ALL) NOPASSWD: ALL\n').encode(), 0o440)
    command('/usr/sbin/visudo', '--check', '--strict')
    command('/usr/bin/ssh-keygen', '-A')
    command('/usr/sbin/apparmor_parser', '--version')
    command('/usr/sbin/aa-status', '--enabled')
    state['status'] = 'complete'
    encoded = (json.dumps(state, sort_keys=True) + '\n').encode()
    atomic(root, STATE, encoded)
    atomic(root, READY, encoded)
    try:
        check(root)
    except Exception:
        (root / READY).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'Enrollment requires root on the target.\n')
    try:
        # The CLI deliberately has no --root or arbitrary-command option.
        lock = ROOT / 'run/cm3-cli'
        lock.mkdir(mode=0o700, exist_ok=True)
        with (lock / 'lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            if args.check:
                check(ROOT)
            else:
                enroll(ROOT)
    except (OSError, ValueError, subprocess.CalledProcessError):
        parser.exit(1, 'CM3 enrollment incomplete; SSH remains gated. Use offline owner-key recovery.\n')


if __name__ == '__main__':
    main()