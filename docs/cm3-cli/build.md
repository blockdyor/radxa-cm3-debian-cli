# CM3 Debian CLI experiment

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Target only: `radxa-cm3-rpi-cm4-io`, Radxa CM3/RK3566 on Raspberry Pi CM4 IO Board,
Debian Trixie, ARM64, CLI, 512-byte sectors. Fresh installation only. This branch
currently implements the prerequisite source-package probe, not a usable image.
The upstream product defaults have deliberately not been changed yet.
The workflow registration was repaired through focused bootstrap PR #3. All
first three source-package attempts failed; attempt 4 passed source compilation,
not full signed ARM64 preflight. The cumulative package limit is SIX; attempts
1–4 remain consumed and two remain. Changed implementation probes may use attempts
5–6, one at a time, with recorded hypotheses and remote revisions. See
`preflight-status.md` for actual run evidence and precise resume requirements.

## Historical package-only invocation (do not repeat unchanged)

The successful source-only fourth attempt used this command. It is recorded for
provenance, not as permission to rerun the successful source:

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli \
      --ref dev/cm3-debian-cli \
      -f expected_sha=112d481fa021b72d7758680eed1b8ce3a25b3141 \
      -f hypothesis='Attempt 4/6: upstream Btrfs allocation-order backport and scoped ARM64 flags for resolve_btfids clean LP64 probe'

That command used a clean checkout of the then-pushed development commit; the
branch has since advanced to retain guards, corrections and the cumulative budget.
Do not reuse the stale expected SHA or rerun an old revision. The workflow rejects
a ref/SHA mismatch, checks the lock and tests, records actual runner resources,
registers digest-pinned ARM64 emulation on the ephemeral runner, and builds the
five locked source projects in a digest-pinned Debian container. It never calls
the upstream composite build/setup actions or checks out upstream over the fork.
No build dependency is installed on the control host or target board.

Runner: standard GitHub-hosted `ubuntu-24.04`, public repository; only free or
already-authorized capacity. Do not select paid/larger/self-hosted production
runners, change spending limits, or weaken repository security policy. Initial
package-probe admission checks require x86_64, 2 CPUs, 7 GB RAM and 24 GiB free
workspace; this is a bounded probe allowance, not proof the entire compile fits.
Compilation uses two jobs. Timeout is 180 minutes. Resource failure is evidence
to retain and diagnose, not permission to use the production machine.
Package-only admission is limited to SIX cumulative attempts, separate from the
full-image budget; four historical attempts remain consumed. Reserve on the
existing implementation card before dispatch and reconcile `attempts.json` with
the entire Actions workflow history. The read-only admission step counts all
observed run attempts under shared concurrency and refuses a seventh attempt,
reruns, missing historical runs, revision drift and overlapping compilation.
It writes a run/SHA-bound admission record checked again by the source driver.
Do not delete runs, invoke old revisions, use another workflow/repository or a
helper task to bypass this coordinator. This is not protection against an owner
deliberately modifying history/code. No automatic write-capable counter or new
service is introduced; workflow-token permissions remain read-only.

The artifact `cm3-source-preflight-RUN_ID-RUN_ATTEMPT` retains allowlisted
source-build diagnostics for 14 days. It does not upload `.deb` files, firmware,
source trees, private signing material, enrollment keys, or a disk image. Review
logs for publication-sensitive content before republishing elsewhere. Source
checkout and package output directories are ignored by Git.

Local, unprivileged checks (Python/Bash; compiler regressions additionally use
GCC14/make and an ARM64 compiler when installed, otherwise explicitly skip):

    python3 -m unittest discover -s tests/cm3-cli -v
    python3 scripts/cm3-source-preflight.py --check-lock
    bash -n src/libexec/rsdk/rsdk-build
    git diff --check

## Holds, not bypasses

A successful source-package job is NOT the complete package preflight. Before
adding/enabling an image stage, implement and pass all of the following on the
qualified disposable external runner:

1. Whitelist the nine BSP packages with exact versions/architectures and inspect
   exact carrier DTB and loader files. Review per-file blob redistribution terms.
2. Build `cm3-cli-board-support` for deterministic extlinux/DTB selection, gzip
   initramfs, ttyFIQ0/1500000 recovery and deliberately enabled AppArmor; do not
   depend on the builder's running device tree. Replace, not duplicate, conflicting
   systemd-boot/overlay hooks. Preserve stock untuned kernel support.
3. Authenticate Debian main/updates/security and a signed whitelist local BSP APT
   repository from bootstrap onward with scoped `signed-by`. Reject a tampered
   metadata fixture. No Bookworm source, Radxa remote feed/pkgs.json, `trusted=yes`,
   insecure APT flag, global key injection, downgrade pin, or unsigned dpkg shortcut
   in the new exact-target route. Leave other products unchanged.
4. Complete a clean Essential-inclusive ARM64 install/configure/upgrade/remove
   test with clean dpkg audit and recorded package/source/origin manifest. Build
   the overlays' real dummy kernel module AND DTBOs using the matching installed
   headers. Exercise native ARM64 header helpers, initial and upgrade initramfs/
   extlinux hooks and staged known-good boot inputs.
5. Test fail-closed owner/key enrollment, no default users/password or root SSH,
   unique machine/host identities, interruption/idempotence, one network manager,
   documented services and firewall, active intended LSM in an appropriate boot
   fixture, and no arbitrary `/config` shell evaluation. Expansion, if provided,
   must identify only the OS partition, never scan/resize attached data disks.
6. Implement and verify the attested signed-bundle update trust round-trip and
   deliberate package import, with no automatic bootloader/media writes. Pin the
   actual compiler/tool/package closure after observing it; do not invent versions
   or call a rolling APT selection a reproducible snapshot.

Until then the standard `rsdk-build` exact Trixie/CLI path rejects assembly rather
than falling through to the inherited missing/unsigned repository logic. There
is no supported full-image invocation at this commit. Do not remove that guard
just because source compilation succeeds. No CLI/security implementation is
represented as finished before these prerequisite results.

## Full-image bounds for the later stage

At most THREE full image attempts across this entire experimental phase, ONE at
a time, shared across branches/workflows/operators. Targeted package probes do
not consume an image attempt. A GitHub "rerun" that enters image assembly does.
Use the fixed `cm3-phase-b-exclusive` concurrency group, `cancel-in-progress:
false`, and a durable phase-wide attempt ledger checked/reserved before assembly.
Each reservation must have commit, source/input digests, run URL, hypothesis or
specific fix, outcome and remaining budget. Concurrency alone is not an attempt
counter. No full-image job exists here, so no resettable counter is presented as
a security control. See `attempts.json` for the initial ledger.

After passing full package preflight, the later implementation must expose one
manual exact-tuple build, populate the actual fork revision, forbid stale rootfs
reuse, and preserve signed repository inputs rather than regenerate unsigned
Release files through upstream `--debs`. Keep `trixie`, `trixie-updates` and
`trixie-security` as maintained runtime sources; no moving `stable` alias.

An image artifact, if later produced, needs independently checked compressed and
raw SHA-256, decompressor test, complete installed package/source manifest,
source/config/patch/tool/blob/license records, reviewed raw boot offsets and
partition separation, limits, this matrix and safe recovery instructions. Never
include the checksum list in its own hash input. Any draft release requires
artifact review; publishing a release or prerelease is not authorized.

No hardware flashing, formatting, SPI change, production install/update, NVMe
write, application/runtime installation or physical test is authorized by this
build procedure. See `limitations.md` and `validation.md`.
