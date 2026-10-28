# Owner/key enrollment contract (validation only)

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

The independent validator is `scripts/cm3-owner-config.py`. It reads one JSON
file, validates it and returns success/failure without creating accounts,
changing SSH, writing keys, starting services or touching disks. It is not yet
connected to first boot, and is not a secure-provisioning PASS.

Version 1 has exactly three fields:

    {"version": 1, "username": "youraccount", "authorized_key": "ssh-ed25519 YOUR_REAL_PUBLIC_KEY"}

Replace the placeholder with a real owner-controlled Ed25519 public key; the
literal placeholder is intentionally invalid. No password or private key is
accepted. The username is a non-system lowercase name, at most 31 characters,
starting with a letter and containing only letters, digits, underscore or hyphen.
The public key must be one plain ssh-ed25519 key, not authorized_keys options;
a printable comment is allowed and stripped from the canonical value. The SSH
wire type/length and canonical base64 are checked, not possession of the private
key. Actual SSH authentication must establish possession later.

Run locally without privileges:

    python3 scripts/cm3-owner-config.py /path/to/owner.json

Input is bounded to 8192 bytes. Unknown/duplicate fields, unsupported versions,
root/system names, shell-like usernames, multiple key lines, control characters,
options, malformed keys and all-zero key material fail closed. Success does not
print the account name or public key. The validator neither reads `/config`
automatically nor evaluates any file as a shell script.

## Remaining integration requirements

A later reviewed `cm3-cli-board-support` package must enforce file ownership,
regular-file/no-symlink checks and single-owner account collision policy before
using this contract. It must gate SSH on completed provisioning independent of
HDMI, lock password authentication and root SSH, create unique host/machine
identities, preserve serial recovery and provide transactional/idempotent
interruption handling. No default accounts/passwords, arbitrary `/config` command
execution or data-disk scanning/expansion may be introduced. Root-only sudo policy
must be explicitly documented and tested before account creation is enabled.

No provisioning service or account-mutating code is installed by this revision.
The current ARM64 package probe uses boot fixtures only and does not test owner
creation, first boot, SSH readiness, identity uniqueness or an active target LSM.
Hardware and secure first-boot gates remain open.
