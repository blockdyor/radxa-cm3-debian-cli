# Bounded experimental build report — 2026-10-31

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

## Outcome and revision boundary

Exact target: `radxa-cm3-rpi-cm4-io`, Radxa CM3/RK3566 on Raspberry Pi CM4 IO
Board, Debian Trixie / ARM64 / CLI / 512-byte sectors. The actual producer was
`6fac462f2eb7a350077a2b17d6b49439741518d1`, not the subsequent integration head
`78c9b4fbf9a2ba8f71589e9c5e246185f6d0b762` or this report's commit.

Run https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41066891788
completed SUCCESS, attempt 1, on 2026-10-30T15:57:34Z. Source compilation,
signed ten-package ARM64 lifecycle, exact-product rootfs bootstrap, source
preparation, authenticated Stage A, actual assembly and independent read-only
image inspection passed. The recorded offline suite ran 179 tests with no skips,
errors or failures. The manifest contains 270 uniquely named installed packages,
all architecture `arm64` or `all`, including all ten exact admitted identities.
No desktop/application-platform package was detected by the focused manifest scan.

The image was deliberately discarded under the later build-only authorization.
There is NO DOWNLOADABLE OR RECOVERABLE IMAGE. Reports and signatures are not an
image, retained corresponding-source bundle, hardware boot or usable deliverable
for installation. This report reconciles the existing successful execution; it
does not spend another attempt to recreate a discarded payload.

## Authorization, accounting and command

The complete Phase B requirements are in existing Kanban `t_bacce4a4`; later
implementation/publication handoffs on `t_b2ac5281`, `t_3231e79c` and `t_16191242`
record the owner's build-only and Stage A/B/C amendments. Their current
implementation is documented in `build.md`. No additional authorization or
redistribution right is inferred from a successful workflow.

Fresh complete Actions history inspection on 2026-10-31T02:21:58Z reconciled
43 workflows and 43 attempts, all completed, with exactly ONE actual assembly
entry. It agrees with `attempts.json`: 21 package-development records preserved,
image budget 1/3 used, 2 remaining. Source retries follow the current evidence-based
policy, not the superseded 3/6/7 package caps: diagnose after three consecutive
same-stage failures without progress. No dispatch/rerun occurred for this report.

Historical executed command, NOT permission to repeat unchanged:

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli --ref dev/cm3-debian-cli -f expected_sha=6fac462f2eb7a350077a2b17d6b49439741518d1 -f experimental_image=true -f public_distribution=false -f 'hypothesis=Stage exclusive image admission under runner ownership then transfer fresh same-run receipt to builder before experimental assembly and independent inspection'

Existing free standard GitHub-hosted Ubuntu 24.04 runner; fixed phase-wide
`cm3-phase-b-exclusive` concurrency; one heavyweight workflow at a time;
180-minute package/build job; two compile/compression jobs; separate 10-minute
scoped-OIDC provenance job. No paid capacity, spending/security-policy changes,
production/device/media writes, flashing, formatting, target installs, deployment,
application-platform testing or release publication. Actual recorded job elapsed
times: packages 7463 seconds, provenance 26 seconds; assembly 15:51:36–15:56:16Z.
Runner image version `20261025.353.1` appears in the log. Qualification checked
x86_64, at least 2 CPUs, 7000000 KiB RAM and 25769803776 free workspace bytes.
The detailed runner.txt was not retained in the diagnostic allowlist; exact
measured CPU/RAM/free-space values and peak resource usage are not available here.
The guestfish appliance's AMD64 kernel log is not the target ARM64 boot.

## Inputs, package and boot evidence

`project/cm3-cli/source-lock.json` SHA256:
`320cea35c319e260971ea0d40b98027a3c9b507b15bcb965d3edf3022f2bfbd8`.
It retains the full recipe/gitlink and digest-pinned Debian builder/binfmt inputs.
The board-support package is separately bound to the producer revision.
`provenance.md` records patches, purpose, dependencies and update responsibilities.
The exact package versions are in retained `packages.tsv` and the ten-identity
receipt in `image-stage-a.json`; do not replace them with current APT candidates.

Authenticated signed Debian Trixie/updates/security and a scoped signed whitelist
BSP repository replace the missing rk3566-trixie feed. No broad Bookworm feed,
other-board substitution, unauthenticated package path or trust bypass is used.
The signed Stage A report records all five offline checks PASS, including the
producer's exact-head Sonar. That is not ongoing vendor update authority.

Retained `verification.json` records actual-image GPT partition fit/separation,
loader/layout checks, exact kernel/initrd/DTB hashes and boot contract. Kernel:
`6.1.84-18+cm3cli1-rk2410-nocsf`; exact DTB:
`rockchip/rk3566-radxa-cm3-rpi-cm4-io.dtb`. It also records board-policy file hashes
with actual-image ownership/mode verification, package inventory and builder
identity cleanup. Offline enrollment/SSH/network/firewall/boot policy checks are
not proof of physical first boot, effective running firewall or active target LSM.

## Artifacts, retention and independent checks

Native run artifact links (GitHub download requires suitable signed-in access):

- Engineering diagnostics: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41066891788/artifacts/12990744023
  ZIP SHA256 `85b06b7161ab233b105606462707ad564e24a22ba5ef7a577ea9a5a01238c095`;
  expires 2026-11-13T15:56:57Z.
- Attestation: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41066891788/artifacts/12991332483
  ZIP SHA256 `e7cc37b7374405d09e3533bc22706de333025d79e696335e8ea7d87209a31113`;
  expires 2026-11-13T15:57:30Z.

Both ZIPs were freshly downloaded; independently computed SHA256s match the live
API digests and all ZIP members pass CRC. All nine `SHA256SUMS` entries and eight
nested engineering hashes match. Official `gh attestation verify` independently
accepted the engineering subject with exact workflow certificate SAN, producer
source/signer digest, development ref, GitHub OIDC issuer, hosted-runner requirement
and SLSA v1 predicate. Modified subject and wrong-source negatives were rejected.
This authenticates diagnostic provenance, not the correctness of every producer
claim or a separately signed/retained image. Some Stage A evidence is retained
only as hashes, not the original files; do not claim local re-execution of it.

Reported raw image: 1730655232 bytes, SHA256
`28f4717a1fefa7a286c3a31a4b1799d2e6ed960757d946f7def3904bb0ce98d9`.
Reported compressed image: 206582336 bytes, SHA256
`8a803f1065d7c85a772c89ddbae08c1aad0bdffb8ec82b40369a78ab455e3e77`.
These are authenticated report values; this reviewer cannot rehash, decompress
or inspect nonexistent payload bytes. Those checks ran on the disposable runner.
The Phase A rsdk-r2 aggregate SHA512 self-entry mismatch and missing builder
revision are NOT repaired by changing an expected checksum. No affected reference
binary is reused. New raw/compressed checksum lists are separate, and the
nine-entry diagnostic list does not hash itself. See `provenance.md` for the
original defect and reference-binary trust boundary.

Durable review evidence, logs, verification scripts, signed diagnostic ZIPs and
machine-readable reconciliation accompany Kanban `t_8b0a254f`. This internal
review archive is not uploaded to the public repository. Public distribution
remains BLOCKED by OVERLAY-1; upstream issue606 closure is not file-scope license
clarification. No draft release, public release, image or source payload was
published by this reporting lane.

## Unchanged gates, hardware and next steps

Both original gate texts remain byte-identical in `gates-validation-verbatim.txt`
and `gates-consolidated-verbatim.txt`. `hardware-matrix.tsv` retains all nine
columns and H01–H28, each UNTESTED; all three hashes match `evidence-hashes.json`.
No subset, priority class or conditional row was dropped or passed by inspection.

G0 safety/correctness: not demonstrated on hardware; no device writes in this lane.
G1 install/boot/recovery: not demonstrated.
G2 Debian/security/update: not met; runtime LSM, distinct-version reboot/recovery,
maintenance ownership and full input/license closure remain open.
G3 thermal/electrical/power: untested.
G4 performance: unmeasured, no B0 comparison.
G5 responsiveness: unmeasured.
G6 sustained/soak: unmeasured.
G7 coverage: not met, all 28 hardware rows UNTESTED, including mandatory H13 PCIe/NVMe.

Fresh local review checks: source-lock validation and 16 image-budget/delivery
regressions PASS, zero skips. The full 180-test integration suite was not repeated;
its prior completed run has one explicit missing-depmod skip. No compilation,
physical test, service start or performance measurement was performed here.

Next: use the existing independent security/review lanes; obtain authoritative
OVERLAY-1 clarification before any distribution. Any later retained-image run
needs a specific changed-stage purpose, current exact-head/Sonar/history admission,
and an approved retention/access route; do not rerun unchanged just for a download.
Physical testing requires separate sacrificial-target authorization and the safe
procedures in `validation.md`/`first-boot.md`, with a known-good recovery medium.
Full compiler/package snapshot capture and two-clean-build comparison remain
necessary for a bitwise reproducibility claim. Stable release remains BLOCKED.
