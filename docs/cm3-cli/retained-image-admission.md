# Retained experimental image admission — 2026-10-31

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

This is the continuation of draft PR #1, not a new implementation. The task
attachment and PR admission comment identify the final exact commit and live
check URLs. Historical reports and attempts remain intact. No image is produced
by this admission work. The next worker must recheck the exact head before dispatch.

## Identities and accounting

Repository: https://github.com/blockdyor/radxa-cm3-debian-cli
Branch: `dev/cm3-debian-cli`; draft: https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1
Recovered head before prerequisite corrections: `c83cbb9d4093fb87e9597899551f009a86e4f90f`.
Actual discarded-image producer: `6fac462f2eb7a350077a2b17d6b49439741518d1`,
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41066891788 .
These are different identities; the old successful Stage A is not new-head evidence.

All 52 repository workflow runs/attempts were reconciled on 2026-10-31 before
publication: all completed, exactly one assembly entry, matching the unchanged
21 package-history records and one full-image record in `attempts.json`.
The next assembly is image attempt 2; 1/3 used, 2/3 remaining. No reset, rerun,
source compilation or image dispatch occurs in this admission phase. The existing
three-same-stage/no-progress package stop rule also remains in force.
A new push adds cheap checks, so the build worker must refresh the history again.

Exact pinned inputs are in `project/cm3-cli/source-lock.json`, SHA256
`320cea35c319e260971ea0d40b98027a3c9b507b15bcb965d3edf3022f2bfbd8`.
No functional upstream source pin changes. This includes the SDK base,
five package recipes, kernel/U-Boot/rkbin gitlinks, OCI and binfmt digests.
Pinned Actions remain in the workflows. The current builder/board sources,
local recipe diffs and actual generated kernel/U-Boot configurations must accompany
the next image; exact Debian build/runtime versions and downloaded sources are
recorded at execution, not pretended immutable in advance.

## Payload rights and corresponding materials

OVERLAY-1 is no longer awaiting upstream clarification. Official Radxa commit
https://github.com/radxa-pkg/radxa-overlays/commit/0ee073720de7652a6b77ea4be8ae029c4a3e7e4e
is GitHub-signature verified; issue606's closing event names it. Its sole change
adds explicit GPL-2 declarations for the dummy module and arch/**, preserving
file-specific exceptions. Its exact metadata-only patch applies to locked
`a0ffd564a2fdb836e2f3fe60b2c607a58d1d69b6`; patch SHA256 is
`e08dd7d5f575c557653f2cc72669d9deb1622da95bdd5951e2afd531ddaedce7`.
The build applies that patch before packaging. Delivery now requires installed
copyright bytes to equal the patched recipe. No 77-commit functional upgrade or
project relicensing occurs. Preserve GPL-2/GPL-3, BSD-3-Clause Qualcomm and dual
GPL-2.0+/MIT file declarations, attributions and complete terms in the delivered
modified source trees (including kernel LICENSES), package notices and common
license texts. Root/wrapper declarations do not override file-specific terms.

Kernel, U-Boot, overlays, bootutils, udev and board policy require the exact
modified corresponding source, build scripts, local patches, generated configs
and applicable licenses. The existing source-delivery preparation collects these
and exact-version Debian sources for the installed manifest, with signed isolated
APT acquisition. A source URL or diagnostic receipt alone is not delivery.
No source-only/genuinely free-software claim is made for proprietary blobs.

The exact rkbin revision and DDR/USB/BL31 inputs retain the existing SHA256 checks
and original Rockchip notice; its actual grant allows use/copy/distribution and
source modification where source exists, prohibits reverse engineering and notice
removal, and disclaims warranties. The selected BL31 alias is unchanged. Keep the
original notice in the loader docs and corresponding source archive.

The actual intended radio payload is Debian `firmware-brcm80211` and
`firmware-realtek`, both `20250410-2`, not a generic repository-license assumption.
Their downloaded .deb payloads were extracted without installation and their
shared copyright SHA256 is
`f5d62266d99e91aeae9223a5b4f830ed5e917256672f50470ef868e0378ad6d8`.
Delivery rejects a changed firmware version or copyright pending renewed review.
Broadcom binary redistribution requires complete unmodified files, the agreement
and notices, and use only with Broadcom products; Cypress use/distribution is
limited to Cypress products; both retain their proprietary restrictions.
Realtek permissive/restrictive stanzas allow unchanged binary distribution with
notices/disclaimers, no endorsement and applicable reverse-engineering/patent
conditions. GPL-2 calibration files retain source/notices. These are separate
aggregate components, not relicensed as project GPL. Chip compatibility remains
UNTESTED; inclusion is not a claim that every blob is used on this carrier.

File-scope review includes the upstream 20250410 WHENCE:
https://gitlab.com/kernel-firmware/linux-firmware/-/blob/20250410/WHENCE .
Its Cypress section explicitly includes `brcm/brcmfmac4354-sdio.nvidia,p2371-2180.txt`
and the canonical cypress CLM files; brcm CLM names are symlinks to those files.
Those names are not grounds to infer missing grants from incomplete Debian glob
matching. Preserve that WHENCE and LICENCE.cypress in the exact Debian source
archive, as well as all original package copyright and common-license texts.
`firmware-files.json` records actual installed file hashes, and
`installed-source-identities.tsv` binds installed versions to the downloaded sources.

The reviewed source export deliberately omits the unused internal recovery
recipient certificate. Ignored compiled objects, signing keys, recovery secrets,
owner configurations, internal archives and private evidence are not export inputs.
The payload stager selects only verified image/report files and hash-checked
source-delivery materials, not whole workspaces or broad diagnostic directories.

## Gates and execution boundary

Local source checks initially discovered 182 tests with zero failures/errors and
14 explicit missing-tool skips (Jsonnet/GnuPG/depmod); that is not no-skip admission.
The lightweight `CM3 offline admission` workflow verifies all fixtures without
skips on the same standard `ubuntu-24.04` hosted runner, without source/image builds.
Record its exact-head result alongside exact-head Sonar before dispatch.

The actual producer workflow remains `build.yaml`, workflow396827381, active,
manual-only, standard GitHub Actions runner, 180-minute package/image cap and
10-minute isolated provenance cap. Existing authenticated account has push and
workflow access; no paid runner or spending changes. Constant concurrency
`cm3-phase-b-exclusive` remains non-cancelling. An early read-only image-budget
check now precedes compilation; the serialized fresh reservation is still made
immediately before assembly. Never use a rerun of stale code.

Sonar must be exact-head qualityGate OK with zero unresolved issues and hotspots.
Same-run Stage A still requires strict zero-skip offline checks plus authenticated
source/package, signed ARM64 lifecycle, exact-product rootfs, board/boot, identity
cleanup and source-delivery receipts. It cannot be preissued from old receipts.
The build worker obtains that current Stage A inside the changed pipeline, then
reserves attempt2 and assembles only if all prerequisites pass. No gate is weakened.

Respect audit F01–F06: retention addresses the missing candidate, not a hardware
PASS; toolkit storage execution is separately disabled at PR2 `42dae92`; BSP
maintenance/support remains unassigned; mandatory OS-only expansion remains
unimplemented; complete immutable inputs/bitwise reproduction remain unqualified.
No cache or skipped authentication/lifecycle work is introduced. Original G0–G7
and all 28 UNTESTED hardware rows remain unchanged; G1/G2/G7 remain unmet under
the original definitions. Those qualification gaps do not silently become passed
requirements or a demand for physical tests before this authorized experiment.

## Retention and build-worker handoff

For the authorized retained experiment, dispatch the existing manual workflow on
the final admitted head with `experimental_image=true`, `public_distribution=true`,
full `expected_sha` and a new hypothesis describing the official metadata backport
and verified source/image retention. This task does NOT dispatch it.

Artifact name: `cm3-EXPERIMENTAL-<full-commit>-<run-id>`; retention-days: 14.
The actual upload runs only after independent actual-image inspection and
hash/size revalidation. It includes .img.xz, raw/compressed checksums and sizes,
package manifest, verification, same-run receipts, exact source/input identities,
complete applicable sources and notices. The raw .img is not uploaded separately.
`delivery-result.json` binds every retained member by SHA256 and is attested by
the isolated, checkout-free exact workflow/source/signer provenance job.
The signature/verification bundle is `cm3-attestation-<run-id>-1`, also 14 days.

Existing diagnostic artifact12990744023 is live, unexpired and retrievable by API;
its live expiry `2026-11-13T15:56:57Z` demonstrates the existing 14-day path.
It is NOT an image. Exact future expiry must be read from the artifacts API after
upload, not extrapolated from run start. Retrieval requires authenticated GitHub:

    gh run download <run-id> --repo blockdyor/radxa-cm3-debian-cli --name cm3-EXPERIMENTAL-<full-commit>-<run-id> --dir <fresh-directory>
    gh api repos/blockdyor/radxa-cm3-debian-cli/actions/runs/<run-id>/artifacts

Record the actual ID, `/actions/runs/<run-id>/artifacts/<artifact-id>` browser link,
API digest/expiry and a successful download before declaring retention satisfied.
Verify every member, exact provenance and decompressed raw image hash after
retrieval. Download image and sources/notices together before expiry; Actions
storage is temporary development retention, not a permanent mirror or release.
No draft/stable/prerelease release, hardware flashing or production operation.
