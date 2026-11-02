# Radxa CM3 Debian 13 Trixie CLI — Beta 1

BETA — SOFTWARE AND VIRTUAL VALIDATION PASSED
PHYSICAL RADXA CM3 HARDWARE VALIDATION NOT YET PERFORMED.

Experimental fresh-install ARM64 CLI image for Radxa CM3 / RK3566, product
`radxa-cm3-rpi-cm4-io`. Not stable, production-ready or physically qualified.
Scoped software checks do not establish BSP boot, target systemd, active LSM,
carrier compatibility or physical recovery behavior.

[Download v0.1.0-beta.1](https://github.com/blockdyor/radxa-cm3-debian-cli/releases/tag/v0.1.0-beta.1)
and read the [installation, verification and recovery instructions](docs/cm3-beta1.md).
Published 2026-11-02. One canonical image supports the documented SD/eMMC paths;
NVMe boot/root is outside this beta. Owner-key provisioning is required offline
before first boot. No default login or password is provided.

Image: `radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz`.
Built/tested source: `b71152296933808f99d7dc169fc6811861a9001b`.

Compressed SHA-256:
`e189249e76a527b1680b4c1667ca58c923ab59d7567e1792b8019cc537c72e57`.
Download the complete release, including corresponding sources/notices and the
custom review-recovery attestation. Original producer assembly succeeded but its
overall run failed and original build provenance was skipped. Recovery evidence
is independently reviewed local evidence, not original trusted-builder provenance.

Companion OCI distribution: `ghcr.io/blockdyor/radxa-cm3-debian-cli:0.1.0-beta.1`.
The [public package](https://github.com/blockdyor/radxa-cm3-debian-cli/pkgs/container/radxa-cm3-debian-cli)
contains the same 24 release assets. Immutable OCI digest:
`sha256:c73e39347a86a6def34eec67eb637c6712bbfab4e2da0aa266551b377eb0b344`.
The [publication workflow](https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41440663848)
verified the exact reviewed wrapper, registry roundtrip and repository association.
This is an archive of OS assets, not a runnable container. No `latest` tag.

This repository is based on [RadxaOS RSDK](https://RadxaOS-SDK.github.io/rsdk/).
Historical image2 remains NO-PUBLISH; no fourth OS image was built for this release.
