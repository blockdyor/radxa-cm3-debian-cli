# External package preflight status

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Historical runs inspected 2026-10-28 UTC; development authorization updated
2026-10-29. Draft implementation PR:
https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1

## Current integration: tenth-package validation pending

The workflow now builds `cm3-cli-board-support` separately from the nine locked
BSP packages, binding its manifest and embedded provenance to the exact source
revision, commit timestamp and unchanged source lock. The signed ARM64 probe
uses its actual boot/security policy, not synthetic boot fragments. Authenticated
download/hash verification and package unpack precede kernel configuration;
effective SSH policy and board remove/purge/restore checks are included, with
policy revalidation after restore. Encrypted recovery retains all ten admitted
packages, never plaintext payloads or signing/recipient keys.

This changed integration has local regression coverage but no new external PASS
yet. Attempt 8 below validated only the previous nine-BSP fixture. The exact-product
authenticated RSDK profile and full security/update/license gates remain open;
image assembly is held at 0/3. No target service, enrollment, boot or hardware
result is implied by source or local tests.

## Latest completed run: package attempt 8 passed the source/install fixture

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40808183234

Compiled and validated revision: `c9478e31c1859c9ce818ef1e23b500c2feae869b`.
The standard `ubuntu-24.04` job completed SUCCESS at 2026-10-29T04:22:47Z,
within the unchanged 180-minute timeout. No other heavyweight job was started.
Later accounting/test/documentation commits are not the binary-producing SHA.

Directly inspected `result.json` and `arm64-result.json` both report PASS.
The latter still says `full_package_preflight: NOT COMPLETE`; neither reports
an image build. The nine package identities match the unchanged source lock.
The complete final fixture manifest contains 269 installed packages, including
Essential packages and the retained CLI seeds, firmware and DKMS toolchain.

Performed checks:

- Authenticated Debian/bootstrap and ephemeral signed whitelist APT repository;
  deliberately tampered metadata rejected and restored signed metadata accepted.
- All nine BSP packages configured; exact carrier/SoC DTB and loader file present.
  Loader setup was never executed. Native AArch64 header helper verified.
- Real DKMS dummy module installed and 617 DTBO outputs found, not dtc-only success.
- Generated initramfs has one early newc archive followed by gzip at byte 2912256;
  gzip CRC/truncation validation passes. Exact DTB, serial console, AppArmor intent
  and fixture OS UUID appear in extlinux; unchanged regeneration is idempotent.
- Same-version BSP reinstall, ordinary APT upgrade, clean dpkg audit, overlay
  removal/full-whitelist restoration, and Debian-only APT update after removal
  of the temporary build source/key all passed. No distinct-version BSP upgrade
  or active target-kernel LSM test is implied.

Retained native artifacts (expiry 2026-11-12):

- Diagnostics ID `12872747471`, SHA256
  `bfdc5ed070681a86e116e5b66fa51cb58dbb7c53f5b1ecb833643a6bddabb193`.
- Encrypted compilation ID `12872099361`, ZIP SHA256
  `ec097c400eb4c784f14fc911a5f825d594bf60c95744b1cb9203ed1e5f67efd3`.

Both downloaded ZIP digests match the live artifact API; all 47 diagnostic
members and the one encrypted artifact member pass CRC. Admission binds run 8
to its exact commit, policy and full history. No plaintext recovery was attempted.
No private key, credentials, local private evidence or full workspace was uploaded.
Plaintext BSP distribution remains held pending license/corresponding-source review.

### Source milestone and next integration boundary

This continuation changed `scripts/cm3-{package-budget,source-preflight,package-preflight}.py`,
their budget/source-policy tests and `.github/workflows/build.yaml`, plus project
status/accounting documentation. The corrected initramfs validator was already
committed before this continuation. Source pins, patches, upstream licenses,
required kernel configuration and package identities were not changed.

Requirements mapping: exact-target/source lineage stays in `source-lock.json`
and `provenance.md`; the admission script preserves historical runs and current
retry authority; both compile/validation consumers require a matching run/SHA;
the workflow retains exclusive concurrency, standard runner, 180 minutes, pinned
actions/containers and same-job validation. Original gate texts and all 28 UNTESTED
hardware rows remain byte-identical. The separate image ledger remains 0/3, held.

The existing source baseline lane can now proceed from a successful dependency
fixture, not from another research handoff. Before enabling an image job it must
pass the newly integrated `cm3-cli-board-support` package checks,
wire the exact-product authenticated CLI profile without upstream insecure trust
hooks, implement/test secure owner enrollment and identity creation, and close
the applicable update/trust/license prerequisites. Keep the image entrypoint held
until those checks actually pass. Existing workflow integration must continue to
build and validate the intended revision in one admitted job; do not reuse this
run's PASS as proof of later source, provisioning, image or hardware behavior.
No new accounts, transfer infrastructure, release publication or routine owner
reapproval is required for ordinary development already authorized.

## Workflow repair (completed, not a package pass)

The historical HTTP 404 occurred despite a workflow blob existing on main:
Actions had no registered workflows. The precise GitHub-side cause was not
established. Focused bootstrap PR #3 promoted the reviewed manual package-only
workflow and guarded inherited automatic build/documentation/release jobs:
https://github.com/blockdyor/radxa-cm3-debian-cli/pull/3

Merged main commit: `133907e883a44a60d911fa8236b1e7e248be0d7d`.
Registered workflow: `396827381`, `build.yaml`, active. No account/repository
security policy or spending setting was relaxed. PR #1 was not merged.
Reversal: review a revert of bootstrap merge `133907e883a44a60d911fa8236b1e7e248be0d7d`
only after disabling the manual workflow and preserving inherited fork guards;
a blind revert would restore inherited automatic triggers and is unsafe.

## Package attempt 1 of 3 (failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40294636804
Checked-out commit: `f531731036391073441cb4a3b770a5eb233ea807`, run attempt 1.
External runner: standard GitHub-hosted `ubuntu-24.04`. Checkout, policy checks
and resource qualification passed. U-Boot failed under GCC's retained
`-Werror=maybe-uninitialized`: `drivers/power/charge_animation.c:791` reported
`soc` and `current` potentially uninitialized. Kernel compilation was not reached.
The uploaded diagnostic artifact is `cm3-source-preflight-40294636804-1`.

The next source revision initializes only those two cached values to zero;
the existing mandatory first successful gauge poll and error checks remain.
It neither disables diagnostics nor changes source lineage/configuration.
Nested gitlink diffs are now recorded as well as recipe diffs so the exact
source patch is retained. Local patch-context/duplicate-application tests are
not a replacement for the actual external compile.

## Package attempt 2 of 3 (failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40655341359
Checked-out commit: `1c362bcc603b35291d0c30f0b30d577ac308af5d`, run attempt 1.
U-Boot, overlays, bootutils and udev built; their actual `.changes`/`.buildinfo`
and the nested U-Boot source diff are in the diagnostic artifact. Kernel build
failed: parallel recipe prerequisites launched `build-defconfig` and `build-all`
together, so compilation saw no `.config`. Kernel clean probes also rejected
AMD64 `-fcf-protection=full` passed to the recipe's ARM64 `HOSTCC`.

The final retry adds the missing `build-all: build-defconfig` dependency and
selects Debian's ARM64 C/C++/link hardening flags explicitly for ARM64 helpers.
It does not turn off hardening or change the kernel configuration/source pin.
A local real `make -j2` fixture checks the ordering; the final external run
below establishes the actual result, not that fixture alone.

## Package attempt 3 (failed; original three-attempt budget exhausted)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40656875860
Checked-out commit: `1519b8aa0bf81a573272bc31261c4855b3eed9e8`, run attempt 1.
Completed failure at 2026-10-28T09:01:49Z. Source driver reports 2056.19 seconds.
Kernel configuration now precedes compilation and compilation proceeds, but
`fs/btrfs/send.c:7950` calls `kvcalloc` with the sizeof expression in the count
argument. GCC14 rejects this with `-Werror=calloc-transposed-args`.
No kernel package or complete nine-package whitelist was produced.

Architecture-correct helper flags were recorded (including ARM64 branch
protection), but clean probes STILL report x86-only `-fcf-protection=full`.
Therefore that flag-propagation issue is NOT resolved by this run. The main
terminal failure is the Btrfs diagnostic; no diagnostic was suppressed and no
kernel facility was disabled to force a pass. The existing recipe also emits
nonterminal debhelper include-remake warnings; those remain recorded, not hidden.

Diagnostic artifact: `cm3-source-preflight-40656875860-1`, ID `12803836426`.
ZIP SHA256: `76e489b93c08a0097c9f232bf2482bd5df0bb8b8e68be438784d4f575fd660db`
(downloaded bytes independently match the artifact API digest).
GitHub retention ends 2026-11-11T09:01:44Z. Contains logs, locked inputs,
recipe/source diffs, flags and package-tool metadata; no binaries or disk image.

The later 2026-10-28 owner extension supersedes that original budget blocker:
attempts 4–6 are now authorized, not a reset. The next changed-source candidate
backports upstream Linux `6ff09b6b8c2fb6b3edda4ffaa173153a40653067`, swapping only
the two `kvcalloc` arguments, preserving expression types, multiplication overflow
semantics, flags and failure handling. No Btrfs feature/diagnostic is disabled.

The clean-time flag leak is now reproduced: kernel `resolve_btfids_clean` exports
target `CC` to `tools/bpf/resolve_btfids`, whose included
`tools/scripts/Makefile.arch:37` immediately preprocesses the LP64 probe using
ordinary inherited `CFLAGS`, not `HOSTCFLAGS`. Both clean and distclean invoke it.
The targeted correction supplies existing ARM64 `HOSTCFLAGS` only to that clean
submake. The original kernel helper compiler is unchanged; native loader tools
are untouched. No global flag stripping or compiler substitution was applied.
The saved CI log does not show the precise debhelper flag-export command, so
that particular producer is not claimed verified.

Targeted GCC14 checks pass: full pinned source clean reproduces the diagnostic
before the patch and runs without compiler errors after it; the exact backported
allocation excerpt compiles, with five count/overflow boundary checks. This is
not kernel/package compilation. Local dpkg-buildflags is absent, so this clean
check reused the actual ARM64 flag record from attempt 3; the external runner
must regenerate its own flags. Eighteen local regression/policy tests pass,
including a make LP64 fixture, allocation diagnostic before/after, preserved
history, acceptance through six and rejection of an unapproved seventh attempt.
External confirmation of both corrections is recorded by attempt 4 below.

## Package attempt 4 (source-build passed; full preflight NOT RUN)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40682450955
Checked-out commit: `112d481fa021b72d7758680eed1b8ce3a25b3141`, run attempt 1.
Completed SUCCESS at 2026-10-28T13:01:56Z. Source driver reports 4544.82 seconds.
Actual checkout, policy tests, cumulative admission, runner qualification and all
five source-project builds passed. The manifest records all nine expected package
names, versions, architectures and SHA256 hashes, including ARM64 image/headers.
This establishes source compilation, NOT authenticated installation or boot.

Diagnostic artifact: `cm3-source-preflight-40682450955-1`, ID `12817334148`.
ZIP SHA256: `3c187891c26751db1570d558c82c56cc5a734827b9d197e911fb67f22294b930`.
Downloaded ZIP bytes match the GitHub artifact API digest; all 33 members pass
CRC validation. Retention ends 2026-11-11T13:01:52Z. `result.json` explicitly says
`full_package_preflight: NOT RUN` and `image_build: NOT RUN`.
The sole retained artifact contains diagnostics, not `.deb`/`.udeb` payloads;
the successful disposable runner is finished. No compiled package recovery is
claimed. A changed next-stage implementation that needs them must use a counted
attempt, not rerun this successful revision or hide a full rebuild as a test.

## Package attempt 5 (source passed, ARM64 bootstrap failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40698441411
Checked-out commit: `293971c1a011ef3cd69343827cf36e1bb91a064f`, run attempt 1.
Started 2026-10-28T13:39:30Z; completed FAILURE at 2026-10-28T14:41:01Z.
Exact checkout, local tests, cumulative admission and runner qualification passed.
Source `result.json` is PASS (3663.35 seconds), with all nine selected packages.
The ephemeral repository's `gpgv` signature verification passed. The separate
`arm64-result.json` is FAIL (3.42 seconds): mmdebstrap exits 25 with
`install arch-test for foreign architecture support`. Explicit no-Recommends
installation omitted that runtime dependency. No target bootstrap, APT tamper
negative, installation, DKMS or boot-fixture check ran; none is a claimed PASS.

Diagnostic artifact ID `12824379107`, retention through 2026-11-11T14:40:57Z.
SHA256 `ed64568e61a6adfea2274ae735eebe06b08a071ca552d181bcc6766b6cc9a1ef`
matches the downloaded bytes and API digest; all 35 ZIP members pass CRC checks.
No compiled package binaries were retained. The final changed candidate adds
the missing explicit `arch-test` dependency without enabling Recommends and
checks actual ARM64 execution before expensive source compilation. Local policy
regression fails before the correction and passes after it; actual foreign
bootstrap remains an external-run check, not a local production-host test.

## Package attempt 6 (source/bootstrap/tamper passed; seed install failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40711214571
Checked-out commit: `cc1ba6de1a19c8243f98f52aa73b0b9e7f2166ff`, run attempt 1.
Started 2026-10-28T14:58:24Z; completed FAILURE at 2026-10-28T15:52:03Z.
Exact checkout, 30 local tests, cumulative admission and runner qualification
passed. Source `result.json` is PASS (2885.06 seconds), all nine packages recorded.
Early ARM64 execution, the real ARM64 minbase bootstrap, ephemeral repository
signature verification and APT rejection of deliberately tampered metadata
passed; restored signed metadata was accepted afterward.

The separate `arm64-result.json` is FAIL (311.73 seconds). Initial retained-seed
installation reaches u-boot-menu 4.2.4 but dpkg prompts for the fixture's
pre-created `/etc/default/u-boot`, receives EOF and fails; APT exits 100.
`DEBIAN_FRONTEND=noninteractive` does not answer dpkg conffile prompts.
Headers/full BSP whitelist installation, real DKMS/DTBO compilation, boot fixture
and reinstall/upgrade/remove/audit checks were NOT reached. A partial seed install
is not a configured target or a full-preflight PASS.

Diagnostic artifact ID `12829104613`, retention through 2026-11-11T15:51:58Z.
SHA256 `1d76e20138b234b1df9ecb1f048c45b877b84f386ca003ed5bc4b978e8218116`
matches the downloaded bytes and API digest; all 36 ZIP members pass CRC checks.
No compiled package payloads or target root were retained.

The subsequent minimal correction keeps all boot values but writes the supported
`/etc/u-boot-menu/conf.d/99-cm3-preflight.conf` instead of the package conffile.
The inspected Debian 4.2.4 reader loads that directory after its default file.
The new local regression fails before the correction and passes afterward;
31 local tests pass. A separate unprivileged, source-path-remapped check of the
actual Debian `read-config` loads the exact serial/AppArmor/DTB settings and
preserves the default file. This is not dpkg/ARM64 integration validation.
No global conffile forcing, warning suppression, security change or new build.
No recoverable compiled payload exists, so complete external verification needs
an owner-authorized counted rebuild. The later explicit extension below resolves
only that budget blocker, not the failed install or remaining readiness gates.

## Package attempt 7 (configured BSP/DKMS passed; gzip assertion failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40732092034
Checked-out commit: `e2a51296f58f0269a9218154e648a99ea1a93cd8`, run attempt 1.
Package job completed FAILURE at 2026-10-28T18:37:14Z. Source `result.json` is PASS
(4858.74 seconds); signed ARM64 `arm64-result.json` is FAIL (710.02 seconds).
The conffile correction works: signed bootstrap/tamper rejection and all nine
package configurations completed. Exact DTB compatible, native AArch64 header
helper, installed DKMS dummy module and DTBO-output assertions passed.
This does not establish booted hardware, active LSM or full package preflight.

The probe stopped at `initramfs is not gzip compressed`, an assertion requiring
gzip magic at byte zero. Debian initramfs-tools-core 0.148.4 `mkinitramfs`
prepends an uncompressed newc archive for already-compressed `.xz`/`.zst` files
before the compressed main archive. The installed module was `.ko.xz`, making
that layout a likely explanation, not a verified inspection of this initrd:
neither initrd nor target root was retained. The local correction parses newc
prefix records and still requires a CRC-valid, nontruncated gzip main archive.
It checks main newc magic, not complete cpio contents. Plain gzip, padded/multiple
prefixes and malformed/truncated/corrupt/non-gzip fixtures are covered; the
corrected checker has not run against an actual generated target initrd.
Extlinux/idempotence/reinstall/upgrade/remove/audit checks were not reached.
The log also records a missing `rockchip/dptx.bin` firmware warning, fixture-root
fsck identification warning and lack of kernel module signing; none is hidden
or evidence of a hardware/security PASS.

Diagnostic artifact ID `12842575543`, ZIP SHA256
`e3e5de3c6ef5faae207f39056e8a8091d3aa601939d38cb720eb2ea5b19e71d2`,
has 38 CRC-valid members. Encrypted recovery artifact ID `12842325969`, ZIP SHA256
`ca0a7f96e0876aa6b0446754bf0302bb7b57e847e7c5a873883c88c405c06a4e`,
has one CRC-valid member. Both downloaded archives match their API digests.
Successful CMS authenticated decryption, exact approved run/SHA provenance and
all 36 manifest file hashes are verified. All nine compiled packages were
recovered privately, not installed or redistributed. Retention ends
2026-11-11T18:37:10Z (encrypted) / 18:37:11Z (diagnostics).
No target root/initrd/private signing key was uploaded. Recovery does not grant
reuse authorization, license closure or enduring update trust.

## Admission and remaining work

The fifth-attempt implementation adds a signed whitelist/Essential-inclusive
ARM64 install/DKMS/extlinux-fixture probe to the existing manual job, not a full
image or a competing workflow. Its source PASS and bootstrap failure are above.
See `build.md` for exact scope and remaining gates.

Historical package-only budget: SEVEN cumulative attempts following owner approval
on 2026-10-28, superseded by the 2026-10-29 development authorization. All six earlier runs remain consumed and reconcile with the
ledger: five workflow failures and one source-only workflow PASS. Only changed
attempt 7 was newly authorized and is now consumed by run
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40732092034
at `e2a51296f58f0269a9218154e648a99ea1a93cd8`, run attempt 1.
Source and configured BSP/DKMS success do not turn the failed signed ARM64 job
into a PASS. The owner now authorizes evidence-based compilation and validation
retries in the existing standard GitHub-hosted job: one at a time, 180 minutes,
free/already-authorized resources only. Inspect actual failures before retrying;
stop after three consecutive same-stage failures without demonstrable progress.
Encrypted recovery remains optional; no private transfer or key upload is required.
A read-only Actions admission step reconciles full
history and run_attempt values under the existing shared exclusive concurrency,
rejects reruns, missing records and unchanged hypotheses, and binds its result to
the current run/SHA. Reservations still belong on the existing implementation
card before each dispatch. Historical revisions/helper tasks are not bypasses.
See `attempts.json` and `build.md`; image budget/prerequisites are unchanged.

A successful source compile is NOT full package preflight. Ephemeral signatures,
bootstrap and tamper checks above do not pass the remaining complete clean ARM64
configuration/update, exact boot integration, secure enrollment
and attested update requirements.
Image assembly is disabled; no full-image attempt has run in the inspected
repository. Check the phase-wide ledger before any future image stage. Both
original gate definitions and all 28 UNTESTED hardware rows remain unchanged.
