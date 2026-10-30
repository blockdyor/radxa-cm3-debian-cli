# External package preflight status

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Historical runs inspected 2026-10-28 UTC; development authorization updated
2026-10-29. Draft implementation PR:
https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1

## Current implementation checkpoint — experimental pipeline not yet executed

Public image delivery remains withheld for unresolved OVERLAY-1. The owner's
later build-only decision allows engineering assembly and inspection without
payload publication; it does not grant redistribution rights or hardware approval.
The manual workflow defaults `public_distribution=false` and rejects true before
compilation. Build-only runs disable recovery ciphertext and inherited broad
diagnostic uploads, retaining only explicitly staged diagnostics and their
exact-source attestation. Payloads and source bundles stay runner-local and are
discarded with that disposable runner; there is no approved private retention
destination and no downloadable image from this mode.
At the locked overlay commit `a0ffd564a2fdb836e2f3fe60b2c607a58d1d69b6`,
the root `LICENSE` contains GPLv2 while `debian/copyright` declares `Files: *`
GPL-3+. The dummy module source `debian/radxa-overlays.c` declares
only `MODULE_LICENSE("GPL")`, not a version or an exception. These differing
signals do not establish an authoritative file-scope mapping or GPLv2-kernel
compatibility for the built module. Preserve the package and notices; do not
silently relicense or remove board support. Obtain an upstream file-scope
clarification covering the overlay sources and dummy module before public upload.
This is an unresolved permission question, not a finding that all overlays are
undistributable. Exact source links and the existing file-level inventory are
in `provenance.md` (OVERLAY-1). Upstream clarification requested once:
https://github.com/radxa-pkg/radxa-overlays/issues/606
Engineering build/inspection and redistribution clearance are separate outcomes.

Source delivery now requires both actual kernel/U-Boot build configurations,
checks kernel configuration against the retained build evidence, and exports the
existing hashed loader-input/notice mapping. Independent image inspection also
checks board-policy file bytes, root ownership and exact permissions; it does
not infer those properties from a package name/version. These checks have not
yet inspected an assembled disk image.

The owner's later Stage A/B/C timing amendment in `build.md` supersedes the
historical pre-image service/LSM/rollback hold below. A manually selected experimental
workflow now connects actual same-run Stage A production, cumulative three-image
admission, existing RSDK assembly, independent disk inspection and allowlisted
source/notice delivery. It has not yet produced an image. All thirteen historical
source attempts remain recorded; image entries remain 0/3 at this checkpoint.
The latest completed producer remains attempt 13, not this newer validator source.
Actual firstboot/services/active LSM, distinct-version hardware recovery and all
28 matrix rows stay UNTESTED before hardware-qualified/stable-release approval.

## Latest completed run: attempt 13 actual attested repository verified

Run attempt 1 completed SUCCESS at 2026-10-29T17:06:45Z:
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40899447213
Producer source: `c24ad2a0598d000727763803b8c678d6a3411fc0`. The source build,
signed ARM64 ten-package lifecycle and real exact-product clean directory bootstrap
pass; both manifests contain 270 installed packages with exact BSP/board identities.
Configuration hash, run/source/lock/signer/board receipts and cleanup reconcile.
Services were NOT STARTED, enrollment NOT RUN and active target LSM NOT TESTED.

The separate provenance job actually issued the ciphertext attestation. Consumer
`063d7fd5e309e585e229f2d7e0bef0c5e747b995` verifies its exact certificate SAN,
repository, approved producer source/signer digest and ref, issuer, SLSA predicate
and hosted runner policy. The CMS digest also matches the independent package-job
log. Wrong source, wrong digest and a changed signed subject are rejected.
Producer and consumer revisions are not interchangeable.

Diagnostics artifact `12916837556` ZIP SHA256:
`087084d1db6a1c0d8ba9267740a87835f79061532befd3d7827790ac38487efb`.
Encrypted recovery artifact `12917900210` ZIP SHA256:
`1ae6797498ebfad947f8dad3a774c802a33ec2365aafb7a3adf5165fc7c0d721`.
Attestation artifact `12917007147` ZIP SHA256:
`d457d8ee7cacabc50e23e1fa634a04670d2e611f46050624f0f833f5637c4320`.
All three match live API digests; all 57 ZIP members pass CRC. All thirteen
completed runs reconcile, preserving the first twelve ledger records.

Private CMS AES-GCM decryption authenticated before extraction. Every inner
manifest hash, exact run/source, ten package identities and the retained public
key/signed-release/index/payload closure pass. Changed index, pool payload,
signed release and wrong fingerprint are rejected. A separate isolated ARM64
APT configuration then authenticated the scoped `signed-by` source and downloaded
all ten exact payloads; APT itself rejected changed index and signed-release
fixtures. Its temporary source was removed. This is acquisition only: no packages
were installed, no maintainer scripts/services ran, and no host APT trust changed.
The key is approved only for this verified bundle, not as enduring update authority.

The actual loader package retains its original copyright and exact rkbin notice
bytes, matching `loader-inputs.json`; NOTICE-1's packaging check now passes.
This does not close the complete corresponding-source/blob-license review.
No private key, plaintext BSP, target root or private evidence was uploaded.
No new workflow, image, checker or timer was dispatched for these checks.

At that historical checkpoint, admitted-bundle installation and runtime checks
were still pre-image requirements. The later owner timing amendment moves actual
runtime/hardware qualification to Stage C; download-only APT validation is still
not installation. The new same-job route must validate its own configuration and
source/notice delivery before experimental assembly. Attempt 13 does not validate
later source or clear its Sonar gate.

## Historical attempt 12 clean exact-product directory bootstrap passed

Run attempt 1 completed SUCCESS at 2026-10-29T13:21:17Z:
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40868611520
Exact source: `12ad8dcd6d1457260b53c25dcff4f476bd327009`. Source and signed
ARM64 ten-package lifecycle PASS; the real RSDK Trixie/ARM64/CLI route also
bootstrapped a fresh directory with all 270 installed packages configured.
The manifest includes every retained userspace seed and DKMS tool, and all ten
selected identities match the BSP and board manifests. The rendered configuration
hash and its exact run/revision/lock/signer/board receipt match. Its cleanup
checks passed: no builder machine identity, SSH host keys, owner document or
temporary build feed/key remained. Services were NOT STARTED, owner enrollment
NOT RUN, and active target LSM NOT TESTED; no boot or hardware result is implied.

Diagnostics artifact `12899169959` ZIP SHA256:
`2f38468d4231395badcc964477fefb99e692b5777665afdea0ff285d7dc7def2`.
Encrypted recovery artifact `12900446452` ZIP SHA256:
`12febbc80d1a6bf6ae32f1eb824b3b334ee04e9363d96391b8bc7cf82153f49b`.
Both match live API digests; all 54 ZIP members pass CRC. All twelve completed
runs reconcile with the ledger, without reruns or reset history. Recovery
decryption was not repeated. This is not enduring update trust or license closure.

SonarCloud analysis at this exact source (2026-10-29T11:50:13Z) matches the GitHub
SUCCESS check: gate OK, all five findings CLOSED/FIXED, zero open issues and zero
hotspots. This does not clear subsequent code or satisfy physical gates.
The image entrypoint remains held at 0/3. Attested bundle import, distinct-version
BSP recovery, complete input/source/blob-license closure and target firstboot/
services/active LSM remain unverified.

The subsequent loader correction pins the actual rkbin input bytes and BL31 path,
records the original Rockchip notice and adds it to the loader package's docs.
Attempt 13 now validates its compilation and original notice packaging. Attempt 12
does not validate that later change, and corresponding-source review remains open.

## Historical attempt 11 failed before profile bootstrap

Attempt 11, run attempt 1, completed FAILURE at 2026-10-29T10:48:16Z:
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40846835210
Exact source: `9d265e09427299fcff0c2fbac7f89acf03cb313d`. Source and signed
ARM64 ten-package lifecycle receipts PASS, with 270 installed identities matching
the nine-BSP and separate board manifests. The terminal failure is
`E: Unable to locate package bdebstrap`; Debian does not ship it in Trixie.
The profile generator was never invoked; no profile result/configuration exists.
Earlier `/dev/pts` warnings were not the terminal failure.

Diagnostics artifact `12890458690` ZIP SHA256:
`a00dfacd17d39d38e1032f2b852e074d3b7e0bdc64433f70c63b16892b6b68a0`.
Encrypted recovery artifact `12891176792` ZIP SHA256:
`d6471b904b867659c7e957957f0402d9eebc3c2dd65f896e01cb1935196acf7a`.
Both match live API digests; all 51 ZIP members pass CRC and exact run/SHA/lock
admission and manifest checks pass. Recovery decryption was not repeated.

The correction installs the exact-byte Debian `bdebstrap 0.8.1-2/all` frontend
only in the disposable builder, before compilation. Its SHA256 and identity
are verified before APT executes it; dependencies resolve from existing signed
Trixie sources. No testing/unstable feed or package enters the target. Official
Debian archive signature -> index -> package hash/size and an isolated AMD64
Trixie APT dependency simulation passed locally. Attempt 12 then validates the
actual builder-tool install and exact-product directory bootstrap, as recorded above.

## Historical attempt 10: ten-package lifecycle fixture passed

The workflow now builds `cm3-cli-board-support` separately from the nine locked
BSP packages, binding its manifest and embedded provenance to the exact source
revision, commit timestamp and unchanged source lock. The signed ARM64 probe
uses its actual boot/security policy, not synthetic boot fragments. Authenticated
download/hash verification and package unpack precede kernel configuration;
effective SSH policy and board remove/purge/restore checks are included, with
policy revalidation after restore. Encrypted recovery retains all ten admitted
packages, never plaintext payloads or signing/recipient keys.

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40824823375

Exact source revision: `d58c5db2088d12fee4bd605bcba29e3c6a881694`, run attempt 1.
The standard job completed SUCCESS at 2026-10-29T06:41:04Z. Directly inspected
source and ARM64 results report PASS; the latter still says full preflight is
NOT COMPLETE and image NOT RUN. All ten selected packages configured; the final
fixture manifest records 270 installed packages. Actual board policy, effective
`sshd -t/-T`, configure/reinstall/remove/purge/restore, DKMS dummy module and 617
DTBOs, gzip/extlinux/idempotence, ordinary APT upgrade, clean audit and Debian-only
update after build-source removal passed. No target services were started.

Diagnostics artifact `12878945706` has ZIP SHA256
`7e2f87be2693ef430d37eb785b733be47ca200e725473ca6594e0b3ec538d54e`;
encrypted recovery artifact `12878457706` has ZIP SHA256
`e581bd91e878af67bbf5791810d1380b42de87af846a36f8bf1a1c0da75e0753`.
Both digests match the live API and all 51 ZIP members pass CRC. Native artifact
retention ends 2026-11-12. Local authenticated CMS AES-GCM decryption, exact
run/SHA provenance and all 42 manifest hashes pass; ten debs were recovered
privately, never installed/executed or redistributed. No target root, signing
key or recipient private key was uploaded. These checks do not establish
enduring update trust, license closure or authorization to distribute binaries.

SonarCloud security acceptance is separate. At attempt 10's compiled source SHA it failed.
At `9d265e09427299fcff0c2fbac7f89acf03cb313d`, the live PR analysis dated
2026-10-29T09:00:56Z matches the exact GitHub head/check: gate OK, all five
findings CLOSED/FIXED by analysis, zero open issues and zero hotspots. This
includes the four original high-security path/argument findings and the later
receipt-file path finding; the unnecessary receipt file was removed. No rule
suppression or manual false-positive disposition was used.
Later changes require their own exact-head analysis; this result does not extend
the historical package PASS to later source or waive remaining prerequisites.

Attempt 12 validates the separately checked exact-product RSDK profile and
clean directory-bootstrap probe after same-job signed ARM64 acceptance. The
signed install hook follows normal CA/keyring installation, before build-feed
cleanup; source and index/payload closure are checked again. Local render,
signature/tamper and hook-order fixtures alone were not an external bootstrap PASS.
The image entrypoint stays held. The owner-group gate also now rejects other
passwd accounts sharing its primary GID, not just supplementary membership;
this is an isolated-fixture regression fix, not a demonstrated prior SSH bypass.

Attempt 11's result and its builder dependency correction are recorded above.
It does not validate the profile or later source changes.

Attempt 9 at `878f197ee9c2a8e3de4f198b744b24524ad0bfd7` failed before
compilation: a policy test read generated `__pycache__` bytes as UTF-8. Exact run:
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40824419303
The error was reproduced locally with Python bytecode overrides removed; the
test now scans the explicit package input allowlist instead of generated files.
CI ran 65 tests with one error and two explicit compiler-toolchain skips; no
board/BSP build, admission or signed ARM64 install stage ran. This run stays in
the cumulative ledger. Attempt 10 fixes that failure and validates the integration.
Attempt 8 below validated only the previous nine-BSP fixture. The full security/update/license gates remain open;
image assembly is held at 0/3. No target service, enrollment, boot or hardware
result is implied by source or local tests.

## Historical attempt 8: previous nine-BSP source/install fixture

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
retain the tenth-package checks validated in attempt 10, wire the exact-product
authenticated CLI profile without upstream insecure trust
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
