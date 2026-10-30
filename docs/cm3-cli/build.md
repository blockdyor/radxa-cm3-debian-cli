# CM3 Debian CLI experiment

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Target only: `radxa-cm3-rpi-cm4-io`, Radxa CM3/RK3566 on Raspberry Pi CM4 IO Board,
Debian Trixie, ARM64, CLI, 512-byte sectors. Fresh installation only. This branch
implements the prerequisite source-package probe and a manually admitted
experimental image pipeline. No usable or boot-tested image is claimed by code alone.
The owner now
explicitly authorizes experimental exact-target image creation after stage A
below, BEFORE real-target first boot, services, active LSM, hardware recovery or
performance qualification. This supersedes the historical preimage runtime hold;
it does not claim an image exists or enable the inherited image path. Stable
release remains BLOCKED and hardware remains UNTESTED.
Latest completed producer: attempt 13 at `c24ad2a0598d000727763803b8c678d6a3411fc0`
passes source compilation, the signed ARM64 ten-package install/DKMS/board-lifecycle
fixture and the real exact-product RSDK clean directory bootstrap (270 installed
packages, clean audit and builder-identity/feed cleanup). It does not boot a kernel.
This is not the complete package/security preflight or an image: see the latest
section in `preflight-status.md` for remaining integration requirements.
The workflow registration was repaired through focused bootstrap PR #3. All
first three source-package attempts failed; attempt 4 passed source compilation,
not full signed ARM64 preflight. All thirteen historical attempts remain recorded.
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

Profile rendering tests require Jsonnet; full legacy/sibling parity needs
Jsonnet 0.22 or newer because the unchanged upstream routes use `std.contains`.
Signed-index fixture tests require GnuPG and dpkg-deb. The exact CM3 route also
renders with the builder's Trixie Jsonnet; rendering is not bootstrap validation.

The workflow uses `scripts/cm3-rsdk-profile.py` after the signed ARM64
probe in the same admitted external job. It verifies the ephemeral signature,
index/payload closure and nine-plus-one manifests before staging the exact
Trixie/ARM64/CLI Jsonnet route. Existing RSDK `bdebstrap` then exercises those
rendered hooks in a fresh directory, not a disk image. The normal bootstrap
installs CA/keyring prerequisites before the first customize hook performs signed
BSP installation; the second removes the job-only feed/key. Board hash/unpack
still precedes kernel configuration. The checker requires exact installed
identities, clean audit and no builder machine IDs, SSH host keys, owner document
or temporary feed. Attempt 12 passes this stage at its exact recorded revision.
That bootstrap result authorizes or implies no account enrollment, target service
start or disk access. Experimental assembly now follows stage A below; the normal
`rsdk build` entrypoint stays guarded until separately integrated.

`scripts/cm3-bootstrap-tools.py` qualifies the profile tools before compilation.
Debian Trixie does not include `bdebstrap`; the builder installs the exact Debian
`0.8.1-2/all` package from the official pool, SHA256
`43631e6a5628654e9be4407287c3c385f034818d1d6fe5bb2b5509a8894722e9`.
The pin was verified against Debian's signed sid index on 2026-10-29. The helper
checks hash and package/version/architecture before installation; dependencies
and Jsonnet use the existing signed Trixie APT sources, with no sid feed added.
This frontend is builder-only, not a target input or a target-suite change.
Do not replace the pin with an unverified moving version if the download fails.

The subsequent loader-input correction verifies six exact rkbin file SHA256s
before executing its tool, validates the upstream RK3566-to-RK3568 BL31 alias and
replaces the recipe's latest-file selection with that same explicit BL31 path.
It adds Rockchip's original notice to the loader package through dh_installdocs,
records the notice and hashes in `loader-inputs.json`, and includes the added docs
file in the retained recipe diff. These are source-level corrections, not yet an
external package/install PASS or complete license/corresponding-source closure.

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
authorized under the 2026-10-29 development policy, not a reset of history.
Experimental full-image assembly requires stage A below. Changing `expected_sha`, invoking a
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

The next changed stage also seals the exact verified signed repository (public
key, signed metadata and whitelisted payloads) inside this ciphertext. A separate
unprivileged `provenance` job, only after the package job succeeds on the manual
development ref, attests that ciphertext and runs `gh attestation verify` with
the exact repository/workflow/source and signer digests, rejecting self-hosted
runners and a tampered subject. Only that job gets `id-token: write` and
`attestations: write`; the privileged package job retains read-only token scopes,
and no source checkout or decryption/private signing key enters the signing job.
Pinned official actions include pinned transitive actions. Attempt 13 now verifies
the actual producer round-trip and subsequent exact-SAN consumer, authenticated
inner repository closure and isolated ARM64 APT acquisition; see `preflight-status.md`
for exact source/run/digests and negative checks. Acquisition did not install or
execute packages and does not finish deliberate APT installation, distinct-version
recovery or license/source review. The consumer's receipt alone is not inner-key
or enduring update authority.

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
Local fixtures pass; attempt 8 also validates the actual generated archive with
one early newc archive and gzip beginning at byte 2912256. This is not complete
cpio-content validation or package/image readiness. The
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

### Attempt 10: actual ten-package fixture passed, not the full security gate

Historical invocation only; do not rerun the unchanged successful source:

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli \
      --ref dev/cm3-debian-cli -f expected_sha=d58c5db2088d12fee4bd605bcba29e3c6a881694 \
      -f hypothesis='Attempt 10: ignore generated bytecode in payload policy scan; validate authenticated board lifecycle'

Run https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40824823375
completed SUCCESS at 2026-10-29T06:41:04Z. Its source and signed ARM64 results,
exact manifests and native artifact digests were directly inspected. The final
fixture contains 270 installed packages. This SHA's SonarCloud security gate
still fails independently; current source corrections require exact-head analysis.

Implemented probe behavior, exercised by attempt 10: it creates an ephemeral
Ed25519 job-only key outside retained output,
signs the nine locked BSP packages plus the separately admitted board package,
verifies that whitelist APT repository, then bootstraps a
new Essential-inclusive ARM64 minbase directory from authenticated Debian
Trixie/update/security repositories. It adds the BSP through scoped signed-by,
requires signature failure on deliberately tampered metadata, installs the
32 retained seeds plus explicit firmware/AppArmor/DKMS/compiler dependencies,
tests native ARM64 header helpers through actual DKMS dummy-module/DTBO builds,
and checks exact DTB/loader files, gzip initramfs, serial/AppArmor boot arguments
and idempotent extlinux generation in a fixture. It exercises BSP reinstallation,
ordinary Debian upgrade, overlay removal/reinstallation and dpkg audit; records
the complete final package/source manifest and candidate origins; then removes
the build-only APT source/key. The workflow builds `cm3-cli-board-support` from
the exact checked-out revision and commit timestamp, with a separate identity,
hash and embedded-source manifest; it does not alter the nine-BSP source lock.
The probe uses authenticated `apt-get download`, compares admitted bytes, and
unpacks the board-owned boot policy/mask before kernel configuration. It checks
effective SSH policy without starting services and exercises board removal,
purge and restore, including restored SSH/boot policy. Attempt 10 passes these
checks at its exact source revision; attempt 8's historical PASS did not cover them.
Loader setup is hashed, NEVER executed.

Only the disposable external container is privileged for mmdebstrap and isolated
proc/sys/tmpfs-dev mounts, with guaranteed unmount cleanup. It receives no GitHub
token, host block-device bind, signing secret or production connection. The job
still has read-only token permissions, shared exclusive concurrency, two compile
jobs and a 180-minute total bound. Keys, target directory and signed package
payloads are NOT uploaded in plaintext. Diagnostic retention remains allowlisted;
the separate encrypted recovery artifact described above retains compiled output.

Even a PASS here is NOT the full package gate: the OS UUID is a test fixture,
although boot/security policy now comes from `cm3-cli-board-support`; no target kernel boots in chroot,
so active LSM/first boot/enrollment/update recovery are untested. Reinstalling
the same version is NOT distinct-version BSP upgrade validation. Attested update
trust, secure CLI integration and input-snapshot/license closure remain pending.
That historical probe did not enable image assembly; current policy is stage A
below. Read `arm64-result.json` separately from source
`result.json`; neither may be inferred from the other or a workflow name.

Local, unprivileged checks (Python/Bash; compiler regressions additionally use
GCC14/make and an ARM64 compiler when installed, otherwise explicitly skip):

    python3 -m unittest discover -s tests/cm3-cli -v
    python3 scripts/cm3-source-preflight.py --check-lock
    bash -n src/libexec/rsdk/rsdk-build
    git diff --check

## Staged admission: experimental assembly is not stable qualification

The owner authorizes experimental image creation for the exact CM3
Trixie/ARM64/CLI tuple before real-target runtime testing. This replaces the
former circular requirement to boot/qualify a not-yet-created image before
assembly. It does not waive security checks, original G0–G7, either original gate
text, or any of the 28 H01–H28 hardware rows. All hardware remains UNTESTED;
stable release remains BLOCKED. No receipt PASS is asserted by this policy.

### A — Offline prerequisites, before experimental assembly

On the qualified disposable external runner, collect inspected receipts for the
exact reviewed head and admitted inputs. Each of these five fields must be the
literal JSON string `"PASS"`; missing, failed, untested or boolean values block
admission:

- `authenticated_inputs`: authenticate Debian main/updates/security and the
  signed whitelist BSP repository from bootstrap onward with scoped `signed-by`;
  verify exact package identities, payload hashes, provenance and tamper rejection.
  Review exact loader/DTB inputs and applicable redistribution terms. No Bookworm
  source, Radxa remote feed/pkgs.json, `trusted=yes`, insecure APT flag, global
  key injection, downgrade pin or unsigned dpkg shortcut in the exact-target route.
- `package_configuration`: clean Essential-inclusive ARM64 install/configure,
  upgrade/remove/reinstall, clean dpkg audit and package/source/origin manifests;
  real matching-header DKMS dummy module and DTBO builds, native ARM64 helpers,
  generated gzip initramfs/extlinux hooks and staged known-good boot inputs.
- `exact_target_rootfs`: fresh actual `radxa-cm3-rpi-cm4-io` Trixie/ARM64/CLI
  rootfs, not a generic fixture or stale reuse; exact board policy, deterministic
  extlinux/DTB selection, ttyFIQ0/1500000 recovery configuration, intended AppArmor
  boot arguments and stock untuned kernel support. Replace conflicting inherited
  hooks; do not depend on the builder's running device tree.
- `offline_security`: inspect fail-closed owner/key enrollment, no default
  users/password or root SSH, identity cleanup, interruption/idempotence fixtures,
  one network manager, service/firewall configuration and no arbitrary `/config`
  shell evaluation. If expansion exists, it targets only the OS partition and
  never scans/resizes attached data disks. Verify attested signed-bundle trust
  round-trip and deliberate import without automatic bootloader/media writes.
  These are offline checks, NOT proof of running target services or active LSM.
- `exact_head_sonar`: passing inspected Sonar analysis/security gate for the
  exact reviewed build head, not an earlier successful source revision.

Use `scripts/cm3-stage-policy.py` as a small shared policy API:

```python
admit(stage_a)  # a dict containing the five fields above
# Returns exactly:
# {"experimental_assembly": "ALLOWED", "stable_release": "BLOCKED", "hardware": "UNTESTED"}
# Raises ValueError for a non-object or any missing/non-PASS required field.
```

CLI reads JSON data on stdin and writes a decision on stdout. It accepts no
filesystem-path arguments. Shell no-clobber protects an existing decision file:

```sh
(set -C; python3 scripts/cm3-stage-policy.py < stage-a.json > decision.json)
```

The input is the stage A object itself, with no wrapper. Successful evaluation
prints the exact decision above and exits zero. Invalid evidence exits nonzero
without printing a decision. The shell opens files, not the policy helper. Extra
fields cannot qualify runtime, hardware or stable release. The helper evaluates
supplied receipts only: it does not authenticate them, invent a PASS, reserve an
attempt, invoke a builder or remove the `rsdk-build` guard. The caller must verify
receipt provenance, exact head/target/input binding, current authorization and
the phase-wide budget before assembly. Do not handwrite PASS values to bypass
missing evidence. The native workflow path below now produces these receipts;
its actual execution result must be inspected before claiming an image exists.

### B — Actual-artifact inspection, after experimental assembly

Inspect the actual artifact independently: compressed/raw SHA-256, decompressor
integrity, raw boot offsets, partition separation/fit, exact target DTB/root
identity and complete installed package/source manifest. Retain source/config/
patch/tool/blob/license records, signed-input provenance, limits and safe recovery
instructions. Pin the actual observed compiler/tool/package closure; do not invent
versions or call rolling APT selection a reproducible snapshot. An assembly PASS
is not an artifact-inspection PASS, and neither satisfies runtime qualification.

### C — Runtime/hardware qualification, required for stable release

After stage B and separately authorized sacrificial-target testing, verify actual
first boot, fail-closed enrollment, unique machine/host identities, interruption/
idempotence, running services/firewall/network ownership, active intended LSM,
OS-only expansion if provided, distinct-version BSP update/reboot and hardware
recovery. Qualify hardware and performance under the unchanged original G0–G7
and all 28 H01–H28 rows, including the mandatory PCIe/NVMe row. No row is waived
and no result is inferred from offline fixtures or artifact creation. This API
never grants stable release; release/publication requires separate authorization.

## Full-image bounds for the later stage

At most THREE full image attempts across this entire experimental phase, ONE at
a time, shared across branches/workflows/operators. Targeted package probes do
not consume an image attempt. A GitHub "rerun" that enters image assembly does.
Use the fixed `cm3-phase-b-exclusive` concurrency group, `cancel-in-progress:
false`, and a durable phase-wide attempt ledger checked/reserved before assembly.
Each reservation must have commit, source/input digests, run URL, hypothesis or
specific fix, outcome and remaining budget. Concurrency alone is not an attempt
counter. `cm3-image-budget.py` reconciles complete repository run/attempt/step
history against `attempts.json` before allowing entry to the assembly step.
Reruns, overlap, missing history, repeated hypotheses and a fourth entry fail closed.

The existing manual `build.yaml` accepts `experimental_image=true` (default false).
Its same-job pinned builder qualifies the software guestfish appliance and full
offline suite before compilation, then builds/configures the ten signed inputs,
bootstraps the exact product rootfs, retains exact corresponding sources/notices,
produces Stage A with current exact-head Sonar evidence, reserves the cumulative
image allowance, assembles through existing RSDK guestfish code, independently
inspects the actual disk, and uploads only hash-allowlisted sanitized materials.
There is no hand-authored receipt, stale rootfs import or unsigned `--debs` path.
The source-only default remains available. Both paths share exclusive concurrency,
standard Ubuntu 24.04, 180 minutes, two compilation/compression threads, and no release
permission. Target runtime feeds remain signed `trixie`, `trixie-updates` and
`trixie-security`; no moving `stable` alias or reproducible-snapshot claim.

After publishing and verifying the exact reviewed SHA and Sonar gate, the command is:

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli --ref dev/cm3-debian-cli -f expected_sha=FULL_REVIEWED_COMMIT -f experimental_image=true -f 'hypothesis=SPECIFIC_CHANGED_STAGE'

The placeholders must be replaced, and the cumulative ledger/live history reconciled
before dispatch. This is execution documentation, not a claim that this revision ran.
`cm3-image-stage-a.py` accepts only `tests`, `sonar` or `produce`, with fixed external
paths. Image/source/delivery validators accept no caller-supplied filesystem paths.
`cm3-verify-image.py` opens only the fixed regular image read-only through libguestfs;
it verifies decompressed bytes, GPT/layout, loader byte offsets, actual UUID/fstab/
extlinux agreement, pinned boot payloads, package inventory and identity cleanup.
`cm3-publish-image.py` stages only verified `.img.xz`, checksums and reviewed
source/notice/provenance files, never raw roots, private evidence or signing keys.
The raw checksum is separate in `RAW-SHA256SUMS`; decompress before checking it.
No checksum list hashes itself. These new paths remain externally unexercised
until a recorded actual run proves otherwise; code/tests alone do not establish PASS.

An image artifact, if later produced, needs independently checked compressed and
raw SHA-256, decompressor test, complete installed package/source manifest,
source/config/patch/tool/blob/license records, reviewed raw boot offsets and
partition separation, limits, this matrix and safe recovery instructions. Never
include the checksum list in its own hash input. Any draft release requires
artifact review; publishing a release or prerelease is not authorized.

No hardware flashing, formatting, SPI change, production install/update, NVMe
write, application/runtime installation or physical test is authorized by this
build procedure. See `limitations.md` and `validation.md`.
