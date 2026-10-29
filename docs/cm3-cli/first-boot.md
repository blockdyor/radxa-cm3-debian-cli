# Owner/key enrollment contract (experimental source)

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

The independent validator is `scripts/cm3-owner-config.py`. It reads one JSON
file, validates it and returns success/failure without creating accounts,
changing SSH, writing keys, starting services or touching disks. The project-owned
board package uses this validator in its separate first-boot enroller. Source and
fixture tests are not a secure-provisioning or boot PASS.

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

The `cm3-cli-board-support` source enforces root-owned mode0600 regular input at
`/etc/cm3-cli/owner.json`, no symlinks/hardlinks and single-owner collision checks.
Its service gates SSH on enrollment, identity creation, firewall and active
AppArmor, independent of HDMI; passwords and root SSH are disabled. The enrolled
key owner deliberately receives passwordless sudo because its password is locked.
No default owner/key, arbitrary `/config` shell command or disk expansion exists.
See the package README for offline recovery and interrupted-account boundaries.

The source package now contains a provisioning service and account-mutating code,
but no image installation or target execution is established. Local tests use
isolated account fixtures. The ARM64 package probe denies service starts and
does not test owner creation, first boot, SSH readiness, identity uniqueness or
an active target LSM. Image integration must remove builder machine IDs and host
keys; the exact-product profile now specifies this cleanup and a new external
directory-bootstrap check enforces it. That new stage has not yet passed an
external run, and neither it nor rendering proves first boot. The owner-group
check rejects other accounts' primary-GID membership as well as supplementary
members. No prior unauthorized SSH authentication was demonstrated.
Hardware and secure first-boot gates remain open.
