#!/usr/bin/env python3
"""Validate a single owner/key enrollment document without changing any accounts."""

import argparse
import base64
import binascii
import json
from pathlib import Path
import re
import struct

MAX_BYTES = 8192
RESERVED = {'root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 'mail',
            'news', 'uucp', 'proxy', 'www-data', 'backup', 'list', 'irc', '_apt', 'nobody'}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate enrollment field')
        value[key] = item
    return value


def validate_owner(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('enrollment must be bytes, at most 8192 bytes')
    try:
        config = json.loads(data.decode('utf-8'), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('enrollment must be a UTF-8 JSON object') from error
    if not isinstance(config, dict) or set(config) != {'version', 'username', 'authorized_key'}:
        raise ValueError('exact enrollment fields required: version, username, authorized_key')
    if type(config['version']) is not int or config['version'] != 1:
        raise ValueError('unsupported enrollment version')
    username = config['username']
    if (not isinstance(username, str) or
            re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', username) is None or username in RESERVED):
        raise ValueError('owner must be a non-system lowercase account name')
    key = config['authorized_key']
    if not isinstance(key, str) or not key.isascii() or any(ord(c) < 32 or ord(c) > 126 for c in key):
        raise ValueError('owner public key must be a single printable ASCII line')
    fields = key.split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519':
        raise ValueError('one plain ssh-ed25519 public key required; no authorized_keys options')
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError('invalid SSH key base64') from error
    # RFC 4251 strings: algorithm followed by the RFC 8709 32-byte Ed25519 key.
    algorithm = b'ssh-ed25519'
    prefix = struct.pack('>I', len(algorithm)) + algorithm + struct.pack('>I', 32)
    if (len(blob) != len(prefix) + 32 or not blob.startswith(prefix) or
            blob[len(prefix):] == bytes(32)):
        raise ValueError('invalid Ed25519 SSH wire encoding')
    if base64.b64encode(blob).decode('ascii') != fields[1]:
        raise ValueError('noncanonical SSH key encoding')
    # Strip comments, never accept options or evaluate any JSON content as shell.
    return {'version': 1, 'username': username,
            'authorized_key': 'ssh-ed25519 ' + fields[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    args = parser.parse_args()
    try:
        with args.document.open('rb') as stream:
            config = validate_owner(stream.read(MAX_BYTES + 1))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Invalid enrollment: {error}\n')
    # Do not print personal usernames or key material in build/log output.
    print('Owner/key document valid; no account or system changes performed.')


if __name__ == '__main__':
    main()
