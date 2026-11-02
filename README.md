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

Compressed SHA-256:
`e189249e76a527b1680b4c1667ca58c923ab59d7567e1792b8019cc537c72e57`.
Download the complete release, including corresponding sources/notices and the
custom review-recovery attestation. Original producer assembly succeeded but its
overall run failed and original build provenance was skipped. Recovery evidence
is independently reviewed local evidence, not original trusted-builder provenance.

Companion OCI distribution: `ghcr.io/blockdyor/radxa-cm3-debian-cli:0.1.0-beta.1`.
The publication workflow verifies the exact reviewed wrapper and registry roundtrip;
initial package visibility may be private until the owner changes it to Public.
This is an archive of OS assets, not a runnable container. No `latest` tag.

This repository is based on [RadxaOS RSDK](https://RadxaOS-SDK.github.io/rsdk/).
Historical image2 remains NO-PUBLISH; no fourth OS image was built for this release.
