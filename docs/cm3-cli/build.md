# CM3 Debian CLI experiment

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Target only: `radxa-cm3-rpi-cm4-io`, Radxa CM3/RK3566 on Raspberry Pi CM4 IO Board,
Debian Trixie, ARM64, CLI, 512-byte sectors. Fresh installation only. This branch
currently implements the prerequisite source-package probe, not a usable image.
The upstream product defaults have deliberately not been changed yet.
The workflow registration was repaired through focused bootstrap PR #3. All
first three source-package attempts failed; attempt 4 passed source compilation,
not full signed ARM64 preflight. Seven historical attempts remain recorded.
On 2026-10-29 the owner superseded the package cap and authorized evidence-based
source builds and same-job validation retries on the existing standard runner.
Attempt 5 rebuilt all nine packages and verified
the ephemeral repository signature, then failed before ARM64 bootstrap because
`arch-test` was not installed. Do not rerun it. The final changed attempt 6 passed
compilation, ARM64 bootstrap and APT tamper rejection, then failed at a dpkg
conffile prompt for the fixture's pre-created `/etc/default/u-boot`. The correction
uses the supported config-fragment directory without overwriting that conffile;
attempt 7 validates that conffile correction but fails a later initramfs check.
Do not repeat unchanged failures. Stop after three consecutive same-stage
failures without demonstrable progress. See
`preflight-status.md` for actual run evidence and precise resume requirements.

## Prerequisites and reproduction boundary

Debian's release basis, checked on 2026-10-28 against
https://www.debian.org/releases/, is Debian 13 Trixie (point release 13.7,
2026-09-12). The workflow selects authenticated current `trixie`,
`trixie-updates` and `trixie-security` packages, not a frozen 13.7 rootfs.
Recheck the official release basis before a later authorized build; a stable
release change requires review, not silently changing the target or using the
moving `stable` alias.

For source inspection and unprivileged checks, use Git, Python 3 and Bash in a
separate development checkout. Obtain the fork and select the full reviewed
commit, not merely whichever revision the branch happens to contain:

    git clone --branch dev/cm3-debian-cli https://github.com/blockdyor/radxa-cm3-debian-cli.git
    cd radxa-cm3-debian-cli
    git checkout --detach FULL_REVIEWED_COMMIT
    git rev-parse HEAD
    python3 scripts/cm3-source-preflight.py --check-lock
    python3 -m unittest discover -s tests/cm3-cli -v
    bash -n src/libexec/rsdk/rsdk-build
    git diff --check

`FULL_REVIEWED_COMMIT` is an intentional placeholder for an approved 40-character
Git commit, not a dispatch input or permission to rebuild. Compiler-dependent
tests may skip if their tools are unavailable; inspect the test output rather
than treating a skipped regression as an executed compiler check.

The external workflow requires authenticated fork Actions access, the manual
workflow registered on the default branch, a pushed/reviewed development SHA,
an admitted budget reservation and no overlapping compilation. The disposable
runner supplies Git, Python, jq, Docker and outbound access to GitHub, the pinned
OCI registries and authenticated Debian archives. It registers pinned binfmt
and installs recipe/cross-build/signing/bootstrap dependencies only inside its
external container. Do not run the compile drivers or privileged container
commands on the control host or board. No local Docker installation is required
or authorized by these instructions.

The exact historical dispatches below and `.github/workflows/build.yaml` record
the implemented invocation. The changed seventh source attempt was reserved and
dispatched once at its reviewed, verified pushed SHA. Further changed probes are
authorized under the 2026-10-29 development policy, not a reset of history. Full-image assembly
remains held. Changing `expected_sha`, invoking a
helper directly or cloning a fresh checkout does not reset either budget.

Source pins make the experiment inspectable, not bitwise reproducible. The
complete authenticated package/compiler snapshot and two-clean-build comparison
remain missing; see `provenance.md`. A new run may select different Debian
dependencies even with unchanged Git and OCI pins. Stop on missing inputs,
signature/expiry failure, revision drift or resource admission failure; do not
replace sources or weaken checks to continue.

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
Package-only admission has no cumulative ceiling under the current owner policy;
the separate three-image budget is unchanged. Reserve on the
existing implementation card before dispatch and reconcile `attempts.json` with
the entire Actions workflow history. The read-only admission step counts all
observed run attempts under shared concurrency and refuses unaccounted prior runs,
reruns, unchanged hypotheses, revision drift and overlapping compilation.
Three consecutive same-stage failures without progress require a technical diagnosis.
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

The seventh-attempt workflow additionally retains `cm3-encrypted-recovery-RUN_ID-RUN_ATTEMPT`
for 14 days after successful source compilation, even if ARM64 installation fails.
`scripts/cm3-retain-packages.py` revalidates the exact nine binary identities/hashes
and seals only selected packages plus allowlisted JSON/diff/config/buildinfo/changes
with OpenSSL CMS AES-256-GCM to `project/cm3-cli/retention-recipient.pem`.
The recipient private key stays outside the checkout and CI; roots, signing keys,
ordinary logs and arbitrary source trees are excluded. Local real encryption,
decryption, tamper rejection and matching-recipient checks pass. Actual attempt-7
upload/recovery is now verified against both API digests, ZIP CRCs, successful
authenticated decryption, exact run/SHA provenance and all 36 manifest file hashes,
including all nine compiled packages. No recovered package has been installed or
redistributed. This is internal
recovery, not plaintext distribution, source-license closure or update trust.
Before reuse, verify the artifact API digest and exact approved run/SHA, decrypt
to a disposable directory, require successful authenticated decryption before
reading/extracting anything, and verify every archived file against its manifest.
GCM integrity is not producer authentication: anyone with the public certificate
can encrypt a replacement. No automatic cross-run reuse or uncounted rebuild is
enabled; loss of the private recipient key makes the ciphertext unrecoverable.

## Changed next-stage package probe

### Changed attempt 7 (source/install/DKMS passed; gzip check failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40732092034

Dispatched once at reviewed source commit `e2a51296f58f0269a9218154e648a99ea1a93cd8`.
Package job completed FAILURE at 2026-10-28T18:37:14Z. Source compilation, signed ARM64
bootstrap/tamper rejection, all nine package configurations, exact DTB, native
ARM64 header helper and real DKMS dummy module plus DTBO checks passed. The
probe then rejected the generated initramfs because gzip was not at offset zero;
extlinux/idempotence/reinstall/upgrade/remove/audit checks were not reached.
Debian initramfs-tools 0.148.4 emits uncompressed newc prefixes for already-compressed
modules/firmware before the compressed main archive. This makes the old assertion
invalid for that layout, but the failed initrd was not retained, so its actual
layout remains unknown. The narrow correction parses newc prefixes structurally,
requires gzip for the main archive and drains it to validate CRC/truncation.
Local fixtures pass; this is not external revalidation or a complete cpio-content
validation. No package/image readiness claim follows. The
following exact command is a historical dispatch record, NOT permission to rerun:

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli \
      --ref dev/cm3-debian-cli -f expected_sha=e2a51296f58f0269a9218154e648a99ea1a93cd8 \
      -f hypothesis='Attempt 7/7: supported boot drop-in enables signed ARM64 install DKMS DTBO; preserve encrypted compilation'

All seven historical attempts remain consumed; the former cap is superseded.
Encrypted output recovery passed; full ARM64/boot/update integration did not.
Later source or documentation commits are not the compiled SHA. Any future
external probe may compile and validate in the existing job under current owner
authorization. Recovered packages and private-transfer infrastructure are optional,
not prerequisites. The image entrypoint remains held pending real prerequisites.

The fifth-attempt development revision extends this SAME admitted manual job
with `scripts/cm3-package-preflight.py`, after successful compilation. Since
attempt 4 retained no payloads and no cache, this necessarily recompiles and
consumes a new cumulative package attempt; it is not a rerun of attempt 4.
The fifth attempt was reserved and dispatched with the existing input names
(historical invocation only; do not repeat):

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli \
      --ref dev/cm3-debian-cli -f expected_sha=293971c1a011ef3cd69343827cf36e1bb91a064f \
      -f hypothesis='Attempt 5/6: signed whitelist APT tamper rejection and clean ARM64 install DKMS extlinux fixture'

The final changed attempt 6 explicitly installs `arch-test` and runs
`arch-test arm64` before compilation. Its actual invocation was (historical,
do not repeat; all six attempts are now reserved/used):

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli \
      --ref dev/cm3-debian-cli -f expected_sha=cc1ba6de1a19c8243f98f52aa73b0b9e7f2166ff \
      -f hypothesis='Attempt 6/6: explicit arch-test dependency and early ARM64 execution check before signed install DKMS probe'

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40711214571

This run completed FAILURE at 2026-10-28T15:52:03Z. Source `result.json` is PASS;
`arm64-result.json` is FAIL at initial seed installation. ARM64 bootstrap,
ephemeral repository signature verification and APT tamper rejection passed;
headers/full BSP install, DKMS, DTBO and boot/update fixture checks did not run.
The subsequent correction moves the unchanged boot settings to
`/etc/u-boot-menu/conf.d/99-cm3-preflight.conf`. Debian u-boot-menu 4.2.4's actual
`read-config` sources this directory after the package-owned default. A local
unprivileged, path-remapped reader check loads the exact settings and leaves the
default file unchanged; the regression fails on the old pre-created conffile.
No global `--force-conf*` setting, security relaxation or source change is needed.
This is NOT a successful package-install test. No compiled payloads were retained
from this completed disposable runner; full external integration needs another
counted compilation. The subsequent explicit approval authorizes only changed
attempt 7 under the limits above; this historical command is not reusable.

Intended full probe behavior (NOT an end-to-end PASS): it creates an ephemeral
Ed25519 job-only key outside retained output,
signs a nine-package whitelist APT repository, verifies it, then bootstraps a
new Essential-inclusive ARM64 minbase directory from authenticated Debian
Trixie/update/security repositories. It adds the BSP through scoped signed-by,
requires signature failure on deliberately tampered metadata, installs the
32 retained seeds plus explicit firmware/AppArmor/DKMS/compiler dependencies,
tests native ARM64 header helpers through actual DKMS dummy-module/DTBO builds,
and checks exact DTB/loader files, gzip initramfs, serial/AppArmor boot arguments
and idempotent extlinux generation in a fixture. It exercises BSP reinstallation,
ordinary Debian upgrade, overlay removal/reinstallation and dpkg audit; records
the complete final package/source manifest and candidate origins; then removes
the build-only APT source/key. Loader setup is hashed, NEVER executed.

Only the disposable external container is privileged for mmdebstrap and isolated
proc/sys/tmpfs-dev mounts, with guaranteed unmount cleanup. It receives no GitHub
token, host block-device bind, signing secret or production connection. The job
still has read-only token permissions, shared exclusive concurrency, two compile
jobs and a 180-minute total bound. Keys, target directory and signed package
payloads are NOT uploaded in plaintext. Diagnostic retention remains allowlisted;
the separate encrypted recovery artifact described above retains compiled output.

Even a PASS here is NOT the full package gate: deterministic configuration is
a probe fixture, not `cm3-cli-board-support`; no target kernel boots in chroot,
so active LSM/first boot/enrollment/update recovery are untested. Reinstalling
the same version is NOT distinct-version BSP upgrade validation. Attested update
trust, secure CLI integration and input-snapshot/license closure remain pending.
Image assembly stays disabled. Read `arm64-result.json` separately from source
`result.json`; neither may be inferred from the other or a workflow name.

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
