# External package preflight status

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Inspected 2026-10-28 UTC. Draft implementation PR:
https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1

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

## Package attempt 5 (in progress; no result inferred)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40698441411
Checked-out commit: `293971c1a011ef3cd69343827cf36e1bb91a064f`, run attempt 1.
Started 2026-10-28T13:39:30Z. Exact checkout, local tests, cumulative admission
and runner qualification passed. Compilation/ARM64 probe outcome is pending;
there is no claimed signed-install/DKMS PASS or final artifact yet.

## Admission and remaining work

The fifth-attempt implementation adds a signed whitelist/Essential-inclusive
ARM64 install/DKMS/extlinux-fixture probe to the existing manual job, not a full
image or a competing workflow. Its external result is NOT yet established.
See `build.md` for exact scope and remaining gates.

Package-only budget: SIX cumulative attempts across workers and workflow runs;
attempts 1–5 are reserved/used (three failures, then source PASS, fifth pending);
one remains.
A read-only Actions admission step reconciles full
history and run_attempt values under the existing shared exclusive concurrency,
rejects reruns, missing records and a seventh attempt, and binds its result to
the current run/SHA. Reservations still belong on the existing implementation
card before each dispatch. Historical revisions/helper tasks are not bypasses.
See `attempts.json` and `build.md`; image budget/prerequisites are unchanged.

A successful source compile is NOT full package preflight. Signed repository,
clean ARM64 configuration/update, real DKMS module and DTBO builds, exact boot
integration, secure enrollment and attested update verification remain pending.
Image assembly is disabled; no full-image attempt has run in the inspected
repository. Check the phase-wide ledger before any future image stage. Both
original gate definitions and all 28 UNTESTED hardware rows remain unchanged.
