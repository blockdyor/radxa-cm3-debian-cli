# Retained experimental candidate — image attempt 2

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

This is the retained build-worker handoff, not the independent inspection verdict.
The separate fresh-worker inspection task remains pending. No boot, flashing,
physical-device action, production deployment or GitHub release was performed.

## Exact candidate and retrieval

- Built commit: `2b41b830cae9efc313f3d39d85be265b6e3eae25`.
- Branch/draft: `dev/cm3-debian-cli`, existing PR #1.
- Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41199013085
- Workflow attempt: 1; cumulative producer attempt: 22; image attempt: 2/3.
- Both package/image and isolated provenance jobs completed successfully.
- Artifact: `cm3-EXPERIMENTAL-2b41b830cae9efc313f3d39d85be265b6e3eae25-41199013085`.
- Retrieval: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41199013085/artifacts/13044838581
- Actual API expiry: `2026-11-14T14:03:12Z`; 14-day development retention.
- ZIP bytes: `1497046145`.
- ZIP SHA256: `cac0f8575b91529e4809d86a99fb460b2279acc19fd8eea56469dca51d959fad`.

Authenticated retrieval:

    gh run download 41199013085 --repo blockdyor/radxa-cm3-debian-cli --name cm3-EXPERIMENTAL-2b41b830cae9efc313f3d39d85be265b6e3eae25-41199013085 --dir <fresh-directory>

Download the complete image/source/notice artifact before expiry; it is not a
permanent source mirror or a stable/prerelease release.

## Actual bytes and verification

Image: `cm3-trixie-arm64-cli.img.xz`.

- Compressed bytes: `207281440`.
- Compressed SHA256: `6b72f1005c517309e9647e7c65d2344ee31e013da0e2f4ae5a07c4f2afcd8037`.
- Raw bytes: `1730675712`.
- Raw SHA256: `b0d1f56240fafc49cc32ceab0f041d4bb6f529604635684135ccc6ad26ebbff8`.

The build worker downloaded both artifact ZIPs, matched API digests and sizes,
read every member through ZIP CRC validation, and verified all 502 retained
members against `SHA256SUMS` and the attested `delivery-result.json` manifest.
It separately recomputed the compressed hash/size and streamed XZ decompression
to recompute raw hash/size. All 490 source-material hashes also matched.

Fresh same-run offline tests: 183, zero failures/errors/skips. Same-run Stage A
checks authenticated package inputs, exact-target rootfs, offline security and
exact-head Sonar. Stage-A receipt SHA256:
`cb296d13cd340e3a0240cdbf6f4f5a04ee22eb978cb5692f8080c607c02777bc`.

Workflow read-only inspection PASS covers GPT/filesystems, loader placements,
boot UUID/path consistency, Debian Trixie ARM64 CLI inventory, exact board-policy
bytes/modes/ownership, service enablement and identity/trust cleanup. It is not
a hardware result or a substitute for the fresh independent child inspection.

## Manifest, sources, notices and provenance

All paths below are inside the same retained artifact:

- `packages.tsv`: 270 installed package identities.
- `verification.json`: actual-image offline inspection and boot/layout hashes.
- `image-stage-a.json`, `image-offline-tests.json`, `image-admission.json`.
- `sources/source-lock.json`: pinned SDK/recipe/gitlink/OCI/binfmt inputs; SHA256
  `320cea35c319e260971ea0d40b98027a3c9b507b15bcb965d3edf3022f2bfbd8`.
- `sources/builder-packages.tsv`, `sources/loader-inputs.json`,
  `sources/installed-source-identities.tsv`, `sources/delivery-inputs.json`.
- `sources/modified-bsp-and-builder-sources.tar.gz`: exact tracked modified
  builder/board/recipe/gitlink sources, applied patches and generated configs.
- `sources/debian-sources/`: authenticated exact installed-version Debian sources.
- `sources/installed-notices.tar.gz`: original installed package notices and
  complete common-license texts.
- `sources/firmware-files.json`, `sources/notice-review.json`.
- `sources/hardware-matrix.tsv`, original gates, build/provenance/limitations.

The actual installed overlay copyright matches the official metadata-only
clarification backport from Radxa commit `0ee073720de7652a6b77ea4be8ae029c4a3e7e4e`.
Both reviewed firmware packages remain `20250410-2` with copyright SHA256
`f5d62266d99e91aeae9223a5b4f830ed5e917256672f50470ef868e0378ad6d8`.
Original file/component terms remain controlling; proprietary Rockchip/radio
components are not relicensed or described as wholly FOSS. Keep their notices,
chip-use restrictions and other conditions with these exact bytes.

Separate signature artifact: `cm3-attestation-41199013085-1`:
https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41199013085/artifacts/13044604426
Expiry: `2026-11-14T14:04:02Z`; ZIP SHA256:
`16bd19edc0cf4063dd96135a6a2b4f7d18065d63f41d3e5ce4684dcec716bc1a`.
The downloaded delivery subject was verified against the exact repository,
workflow certificate identity, source/signer commit, development ref and hosted
runner policy. The isolated provenance job also rejected its tampered subject.

Only the allowlisted reviewed delivery and public signature bundle were uploaded.
The tracked-source export omits the unused internal recovery certificate; no
private keys, owner configuration, recovery ciphertext or internal workspace
archive is a delivery input. Build-worker archive-name inspection found no
forbidden private-material paths; independent content inspection is still due.

## Limits and next owner

All 28 original hardware rows remain UNTESTED. Firstboot/enrollment, actual
module/carrier compatibility, active runtime LSM, sustained performance, thermal
behavior, updates/rollback and physical recovery remain UNTESTED. OS-only growth
is unimplemented; BSP maintenance/support ownership and bitwise reproducibility
remain unqualified. Toolkit storage execution is disabled, not topology-qualified.
Original G0–G7 are unchanged; G1/G2/G7 remain unmet. No performance tuning occurred.

The historical discarded image remains recorded as image1; this candidate is
image2 and leaves one image attempt. No rerun or second concurrent heavyweight
pipeline occurred. Later evidence-only commits do not change the built identity.

Next owner: independent task `t_1c2ec09d`. Retrieve the artifact afresh, recompute
identities, inspect actual disk bytes offline and applicable sources/notices, and
publish its own verdict. Do not claim overall completion from this build handoff.
