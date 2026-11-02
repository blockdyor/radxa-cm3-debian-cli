# Radxa CM3 Debian 13 Trixie CLI — Beta 1

BETA — SOFTWARE AND VIRTUAL VALIDATION PASSED
PHYSICAL RADXA CM3 HARDWARE VALIDATION NOT YET PERFORMED.

This is the independently reviewed experimental release v0.1.0-beta.1.
PASS covers only the executed file-only, installed-helper and five alternate-kernel
userspace probes described in validation-report.txt. It does not establish retained
BSP boot, target systemd, active LSM or hardware behavior. The corrected payload
passed independent scoped review and complete-bundle review (t_dce11de0 round2/run228,
2026-11-02). GitHub release publication and GHCR visibility are separate states.
Historical image2 remains NO-PUBLISH.

## Scope

Debian 13 Trixie, ARM64, CLI, Radxa CM3 / RK3566; exact product identifier
`radxa-cm3-rpi-cm4-io`. This fresh-install image is not a supported upgrade from
another distribution. It is not stable, production-ready or physically qualified.
The Raspberry Pi CM4 IO-compatible/CmRat carrier designation is not a promise of
identical electrical routing, peripheral compatibility or boot behavior. Verify
the actual module/carrier revisions and schematics before attaching peripherals.
There is one canonical image for the SD and eMMC installation paths, not separate
recompressed copies. NVMe boot/root is not supported by this beta contract.

## Publication locations

GitHub prerelease: https://github.com/blockdyor/radxa-cm3-debian-cli/releases/tag/v0.1.0-beta.1
Repository: https://github.com/blockdyor/radxa-cm3-debian-cli

Version: v0.1.0-beta.1. GitHub publication date: 2026-11-02.
Built/tested image source: b71152296933808f99d7dc169fc6811861a9001b.
Recovery-signing source: e46c9e137b17a986ce0378bb4b579f6de4004549 (not the built source).
Canonical download filename: radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz.
Compressed SHA-256: e189249e76a527b1680b4c1667ca58c923ab59d7567e1792b8019cc537c72e57.
Raw SHA-256: d514bf7be20e45771eb043e2e620b22e5d584df0f10afe343d6ae47b28b2beca.
Use the GitHub Releases download for normal installation. GHCR is for archival
distribution and automation; it is not a different OS image.

The companion location is ghcr.io/blockdyor/radxa-cm3-debian-cli:0.1.0-beta.1.
It is an OCI data-distribution artifact, not a runnable container or a target
Docker installation. OCI-CONTRACT.json specifies the exact mapped inputs and
labels; OCI-USAGE.txt supplies digest-based pull/export instructions. The separate
publication workflow verifies the exact wrapper digest and authenticated roundtrip.
Published digest: sha256:c73e39347a86a6def34eec67eb637c6712bbfab4e2da0aa266551b377eb0b344.
Package visibility is Public and the associated repository is this repository,
verified by publication run41440663848 on 2026-11-02. The anonymous package page is
https://github.com/blockdyor/radxa-cm3-debian-cli/pkgs/container/radxa-cm3-debian-cli.
No latest/stable tags.
The release assets retain their reviewed staging text byte-for-byte so the pinned
inventory and OCI identity remain unchanged; this page records publication status.

## Download verification

The final bundle must contain:

- radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz
- SHA256SUMS, with unambiguous filenames and no self-entry
- package-manifest.txt and build-manifest.json
- validation-report.txt and virtual-validation-report.txt
- hardware-matrix.txt and KNOWN-LIMITATIONS.txt
- source-notices.tar.gz, containing the complete reviewed corresponding sources/notices
- image3-recovery.json, recovery-attestation.jsonl and RECOVERY-VERIFICATION.txt
- independent-payload-review.txt, source-repack.json and publisher/OCI contracts

Verify the new custom recovery-review signature with the exact signing source
e46c9e137b17a986ce0378bb4b579f6de4004549 and workflow policy in
RECOVERY-VERIFICATION.txt before trusting checksums. This is review-based local
recovery evidence, NOT an original build-provenance attestation. Original producer
41331537371 built b71152296933808f99d7dc169fc6811861a9001b; assembly succeeded,
inspection failed the stale UFS-on-MMC checker and original provenance was skipped.
The hosted recovery signer did not download or rehash the payload. The local
consumer hashes all signed distributed materials and expands XZ to verify raw.
SHA256SUMS from the same untrusted location alone does not authenticate the files.
Run `sha256sum -c SHA256SUMS` from the final bundle directory and
`xz -t radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz`.
Decompress to a new regular file without replacing the archive. Compare that raw
file's SHA256 and byte size with the explicit raw identity in build-manifest.json;
do not compare a raw file against the compressed checksum. Keep source/notices,
attestation and reports together with the original compressed bytes.

## SD installation — destructive, separately authorized sacrificial media only

### Flash to microSD on macOS, Windows or Linux

Balena Etcher is the beginner image-writing option on all three host platforms;
this documents a host workflow, not a physically tested CM3 boot result. After
the strict signature verification above, compare the compressed checksum:

    macOS:   shasum -a 256 radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz
    Linux:   sha256sum radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz
    Windows PowerShell: Get-FileHash -Algorithm SHA256 .\radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz

Download the canonical image; verify it; insert the sacrificial SD; select the
verified image in Etcher; select the SD by its actual identity and capacity;
flash; wait for Etcher verification; then safely remove it. The selected disk
is erased. Perform the owner provisioning below before inserting the SD in the
carrier and attempting boot. Etcher verification does not establish hardware
compatibility, owner enrollment or successful OS boot. An eMMC already fitted
may take boot precedence; an inserted SD is not proof of SD boot. CmRat SD
override/switch behavior is not verified: do not infer it from CM4 instructions.

1. Arrange voltage-safe serial recovery and a verified external recovery host.
   Disconnect production NVMe/data disks. Identify the exact removable SD by
   stable identity, serial/capacity, transport and mount/holder checks; never copy
   a device name from an example. Stop on ambiguity, mounted children or holders.
2. After separate hardware/write authorization, use a trusted image writer on
   the external host to write the verified decompressed image to the whole SD,
   not a partition. This destroys the selected medium. No physical write is
   authorized by this document or was performed during software validation.
3. Sync and read back exactly the raw image byte range. Its hash must match the
   raw release identity; hashing a larger whole SD is not the same comparison.
4. Before first boot, use trusted offline Linux access to the SD's OS partition3
   to create `/etc/cm3-cli/owner.json` as root:root mode0600, through real directories
   without symlinks/hardlinks. Include exactly version1, a non-system lowercase
   username and one real owner-controlled Ed25519 public key. Never place a
   private key or password in this file. Validate with the source's
   `python3 scripts/cm3-owner-config.py /path/to/owner.json`. Validation does not
   itself copy the file or prove possession of the private key.
5. Unmount safely and insert the sacrificial SD. Capture serial from power-on,
   establish the actual boot medium/kernel/DTB/root identity and verify the
   observed SSH host fingerprint through a trusted channel before authentication.
   There is no universal serial/login password or default SSH owner.

## eMMC installation — separate destructive recovery workflow

Use the same verified canonical image, not a second build. Keep a verified rescue
microSD and working serial recovery. eMMC access depends on the exact module,
carrier, SPI population and boot-source precedence; those remain physically
UNTESTED. Raspberry Pi `rpiboot`/`config.txt` instructions are not substitutes for
Rockchip recovery, and this beta does not authorize SPI erasure.

With separate sacrificial-eMMC authorization, expose the exact eMMC whole device
from a trusted rescue OS or an already-qualified external adapter. Apply the same
stable-identity, transport, mount/holder and raw-range readback checks as SD.
Provision owner.json offline on eMMC partition3 before selecting it for first boot.
If the exact eMMC cannot be positively identified or is the running/mounted OS,
stop; do not use a guessed path or an unqualified Maskrom loader. Qualifying a
Maskrom route, USB mode and exact loader is a separate hardware procedure, not a
reason to write a CM4 image using Raspberry Pi firmware tools.

### Rockchip Maskrom/recovery route (conceptual, hardware UNTESTED)

Rockchip ROM Maskrom/recovery exposes a supported USB recovery interface to an
external host. Enter it only using documentation for the exact RK3566 module and
carrier revision. The USB connector, recovery switch/jumper positions and host
driver requirements are not qualified here. Do not guess a loader filename or
use a loader for a different SoC/DDR configuration. Obtain the exact RK356x loader
from a trusted module-vendor source, verify its provenance and checksum, and
establish that the selected recovery target is the intended eMMC before writing.
Decompress the verified XZ to a new regular image file, then verify the raw digest
and size above (1,866,085,376 bytes).

The conceptual rkdeveloptool order is:

    rkdeveloptool ld
    rkdeveloptool db <verified-loader>
    rkdeveloptool wl 0 <image.img>
    rkdeveloptool rd

These are placeholders, not copy-and-run commands or a qualified loader supply.
Require exactly the intended detected device; stop on ambiguity. Run each command
only after the preceding command succeeds. In particular, a failed `db` must
prevent `wl` and `rd`; a failed write must prevent reset and trigger recovery
diagnosis. Writing sector zero destroys the selected target. Preserve NVMe/data
disks and never substitute a Linux NVMe path for a Rockchip recovery target.
Readback/boot and controller behavior remain physically UNTESTED. A Windows
RKDevTool GUI alternative is not qualified by this release, so no unverified GUI
settings or loader recipe are supplied.

### CmRat carrier: verified scope versus expected behavior

VERIFIED SOFTWARE SCOPE: the image targets `radxa-cm3-rpi-cm4-io`, selects the
guarded MMC OS layout, rejects NVMe/USB root-growth targets in fixtures, and ships
no owner login until offline owner provisioning. That is not electrical or
physical carrier qualification.

EXPECTED / REQUIRES PHYSICAL CONFIRMATION: USB recovery routing, switch positions,
normal OS boot, actual SD/eMMC precedence and override, power sequencing, serial
and peripheral routing. Use the exact carrier schematic/vendor procedure; no
switch position or CmRat SD override is asserted here. Disconnect production
NVMe/data disks before destructive installation, never erase SPI as a shortcut,
and verify the actual root/boot medium from captured boot evidence. Keep a rescue
path independent of the medium being erased.

## First boot, expansion and recovery limits

Systemd initializes machine identity. Enrollment validates the owner configuration
and real SSH key material; readiness remains closed on invalid identity, missing
owner, interruption or missing active AppArmor. Password/root SSH is disabled;
the enrolled key owner deliberately receives root-equivalent passwordless sudo.
Existing valid identities persist across reboot. Cloning an already-enrolled OS
clones its identity; there is no global clone detector or automatic key rotation.

Guarded OS-root growth is implemented only for the exact selected MMC partition3,
not NVMe, USB or arbitrary disks. It has fixture-tested interruption/retry bounds,
not physical power-loss qualification, automatic rollback or a data-disk guarantee
outside the admitted topology. Do not bypass failed guards. Malformed identity,
changed owner or partial account-database corruption requires trusted offline
review; preserve data and logs rather than repeatedly regenerating credentials.
Keep the known-good rescue SD and source/notices. Distinct-version BSP upgrades,
retained-kernel enforcement, all physical rows, thermal tuning and power-cut
recovery remain unqualified. Refer to the final limitations and hardware matrix.

## Licensing

Original component licenses apply; the OS is not relicensed under the repository
license. Preserve source, copyright and redistribution notices, including Rockchip
and radio-firmware restrictions. Eight exact public GnuTLS crypto-selftest blocks
have a narrowly hash/path/source-bound classification; this is not a blanket
private-key exception or a literal-zero-PEM claim. No deployment or builder identity
may ship. Public release requires the actual package-chain, source/notices and
allocated-file sanitization checks to pass for the same image bytes.

## Companion OCI artifact contract

Use OCI-CONTRACT.json and OCI-USAGE.txt. One canonical XZ maps to /image/;
metadata/provenance to /metadata/; complete corresponding source/notices to
/notices/source-notices.tar.gz. The source archive removes one nonessential
developer-only absolute Nix symlink; source-repack.json preserves original/public
archive mapping. All 99,266 other regular nested source files are byte-preserved.
No image is rebuilt or recompressed. The prepared image3 recipe has verified all
24 mapped assets, actual extraction and identical repeated wrapper builds. The
historical image2 recipe is not used for this release.

## Current reviewer handoff

The image is the retained third assembly, not a rebuild. Full identities, scopes
and exclusions are in build-manifest.json and KNOWN-LIMITATIONS.txt. New recovery
run41374891653 issued and verified a custom review attestation; original producer
failure/provenance history is unchanged. The bundle contains no private ciphertext,
key, investigation root filesystem or internal workspace archive. Final independent
candidate review is approved; only unsigned staging metadata/documentation/checksums
were promoted afterward. All seven signed subjects remain unchanged. OCI wrapper
publication uses only the exact released inputs and digest. It does not sign the
wrapper or establish physical qualification. Physical writes remain separately
unauthorized.
