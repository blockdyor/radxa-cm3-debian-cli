# Package provenance and maintenance boundary

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Machine-readable authority: `project/cm3-cli/source-lock.json`. All recipe and
gitlink inputs use full commit IDs. The SDK base is
`RadxaOS-SDK/rsdk@dba5cba3eafb948a22787560bea56da2b9f8f163`; the executing fork
commit is asserted against the manual workflow's `expected_sha`.

## Selected rebuilds

- `radxa-pkg/linux-rk2410-nocsf@aa0ba4b96cd6ebb7aea36a488f2cbfdf702fea8b`,
  kernel gitlink `radxa/kernel@fd366906451692033f1ba273e77e7e2f936c78db`.
  Version `6.1.84-18+cm3cli1`; retain exact-board image/header aliases and matching
  ARM64 payloads. Kernel payload includes modules and DTBs; required exact file is
  `rk3566-radxa-cm3-rpi-cm4-io.dtb`. No vendor libc/UAPI package or other board
  alias is selected. Apply both recipe config patches via dpkg-source; preserve
  `rockchip_linux_defconfig rk3576.config radxa.config radxa_custom.config`.
  Build-Depends come from its locked control file (debhelper/devscripts/lintian,
  dh-exec, flex/bison/bc, ncurses/OpenSSL/YAML development libraries, cpio/kmod).
  Add crossbuild-essential-arm64, required ARM64 libraries, libelf/dwarves and
  QEMU; its HOSTCC is intentionally ARM64, not silently changed to native x86.
  Runtime hooks need module/initramfs/boot utilities even when payload control
  declares no Depends. Overlay DKMS requires matching headers and target tools.
  Backport upstream Linux commit `6ff09b6b8c2fb6b3edda4ffaa173153a40653067`
  (Dmitry Antipov, reviewed/signed by David Sterba):
  https://github.com/torvalds/linux/commit/6ff09b6b8c2fb6b3edda4ffaa173153a40653067 .
  Exact two-argument reorder in `fs/btrfs/send.c`, no other allocation change.
  The `resolve_btfids_clean` submake alone receives `CFLAGS="$(HOSTCFLAGS)"`
  because its LP64 preprocessor probe uses exported target CC plus ordinary
  CFLAGS. Kernel Kbuild compiler/flags remain configuration-controlled; header
  helpers remain ARM64 executables run under QEMU and later installed on ARM64.
  Native AMD64 U-Boot host tools and the rkbin executable are not switched.
  Both recipe and nested source diffs retain these corrections in diagnostics.
- `radxa-pkg/u-boot-rk2601@28cee0b81ceff7986220665c4567222c5aaec790`,
  gitlinks `radxa/u-boot@d9ab7ec6029573ac538b6707a0dffd0a5d049e77` and
  `radxa/rkbin@f3e6dd6372377faee13b29d0ce35eb08049356ef`.
  Version `2017.09-71+cm3cli1`; only the generic payload and exact-board alias
  enter the whitelist. Compile only `radxa-cm3-rpi-cm4-io-rk3566_defconfig` through
  its recipe target; other board aliases are discarded. Preserve RK3566 DDR,
  USB helper and BL31 inputs (audited selections v1.25/v1.17/v1.46); archive
  hashes and notices before distributing any payload. Native AMD64 build needs
  the recipe's 32-bit runtime libraries plus ARM/aarch64 cross tools, Python,
  setuptools, SWIG, pyelftools, GnuTLS, ncurses, dtc, dos2unix, xxd, bc and
  debhelper/devscripts/lintian/dh-exec/flex/bison. `file`/`readelf` inspect
  `boot_merger` before execution. No loader setup script runs against any media
  in the source probe. Package installation must not become automatic flashing.
- `radxa-pkg/radxa-overlays@a0ffd564a2fdb836e2f3fe60b2c607a58d1d69b6`,
  release source 0.2.25, rebuilt as `0.2.25+cm3cli1`.
  Build uses its declared debhelper/devscripts/dh-exec/dh-sequence-dkms/fakeroot/
  lintian. Target needs DKMS, compiler/make/dtc and matching headers; it builds a
  real dummy module as well as DTBOs. Do not install recommended rsetup or enable
  overlays by default. CLI board support must own extlinux overlay integration.
- `radxa-pkg/radxa-bootutils@d822e09153486083b2ee491ac70d384746dd65c3`,
  `0.2.6+cm3cli1`: retain Rockchip decompression behavior. Declared build tools
  include debhelper/devscripts/lintian/dh-exec/pandoc/shellcheck; runtime declares
  `file` and also needs Bash/coreutils/gzip/kernel-hook environment. Its overlay
  install hook uses the running device tree and systemd-boot; the CLI board
  package masks it before kernel configuration and owns extlinux regeneration.
- `radxa-pkg/radxa-udev@f729fd128fcabd84b5f301335016e5e2b3347423`,
  `0.1.4+cm3cli1`: retain reviewed GPIO/SPI/PWM group permissions, not universal
  group membership. Build needs debhelper/devscripts/lintian. Audit group
  creation and device access on the exact board before any hardware claim.

The source probe installs and checks actual declared Build-Depends, refuses
unexpected gitlinks, builds with two jobs and records each local recipe diff.
It does not use upstream's default `DPKG_FLAGS=-d`. Local suffixes distinguish
rebuilds; they are not upstream security-version bumps. Kernel aliases and
payload flavor derive from the same suffixed version. A successful job records
all nine whitelisted package versions/architectures/hashes; this is not the final
Essential-inclusive target manifest or a signed install/configuration result.

## Exact binary whitelist

`scripts/cm3-source-preflight.py --check-lock` derives this set from the lock.
The alias architecture `all` does not make the embedded payload board-neutral.
These are expected package identities, not a final installed image manifest.

| Package | Version | Architecture |
| --- | --- | --- |
| linux-image-radxa-cm3-rpi-cm4-io | 6.1.84-18+cm3cli1 | all |
| linux-headers-radxa-cm3-rpi-cm4-io | 6.1.84-18+cm3cli1 | all |
| linux-image-6.1.84-18+cm3cli1-rk2410-nocsf | 6.1.84-18+cm3cli1 | arm64 |
| linux-headers-6.1.84-18+cm3cli1-rk2410-nocsf | 6.1.84-18+cm3cli1 | arm64 |
| u-boot-radxa-cm3-rpi-cm4-io | 2017.09-71+cm3cli1 | all |
| u-boot-rk2601 | 2017.09-71+cm3cli1 | all |
| radxa-overlays-dkms | 0.2.25+cm3cli1 | all |
| radxa-bootutils | 0.2.6+cm3cli1 | all |
| radxa-udev | 0.1.4+cm3cli1 | all |

The first seven close the missing BSP/overlay binary path; rebuilding bootutils
and udev makes nine selected binaries from five source projects. The separate
`cm3-cli-board-support` package is version `0.1.0`, architecture `all`; its manifest
binds the executing fork revision, commit timestamp, source-lock hash and payload
hash. It is not an upstream BSP binary and does not change the nine-package lock.
Attempt 10 at `d58c5db2088d12fee4bd605bcba29e3c6a881694` validated all ten
packages in the signed ARM64 lifecycle fixture; see `preflight-status.md` for
the exact run and limits. Later source still needs its own validation.
Attempt 12 at `12ad8dcd6d1457260b53c25dcff4f476bd327009` additionally passes the
actual exact-product clean RSDK directory bootstrap, with 270 installed identities
and verified run/lock/signer/board/configuration receipts. Neither result proves
boot, target firstboot/active LSM, distinct-version recovery or enduring trust.
Audited profile sources
are `radxa-pkg/radxa-profiles@fd5c4cd7e1fede8cb44f3b7788d78a20c2363e2a`
and `radxa-pkg/vendor-profiles@f60785267aca74af42b303fe0b8f19da525b1e15`;
neither task umbrella is installed by this probe.

Builder OCI and binfmt digests live in `source-lock.json`; action commit pins
live in `.github/workflows/build.yaml`. Record those files and the actual fork
commit together, including local patches. Pinning only the upstream SDK base
would omit this experiment's source corrections and admission/security guards.

## Deliberate exclusions and retained functions

The missing Trixie path requires seven BSP/overlay binaries from three source
projects; it is not solved by replacing a single URL. Kernel and loader lineage
above is the compatibility candidate, not generic Debian kernel, legacy 5.10,
latest-named U-Boot, CM3 IO, CM3J, RK3568, or a Bookworm userspace substitution.

`radxa-system-config@263af2c8c241430e994ffd18bbb8ddfbebf36434` is a configuration
reference, not an installed umbrella. The source-owned `cm3-cli-board-support`
package supplies serial, exact DTB/extlinux/initramfs/module policy and gated
owner enrollment. Its lifecycle fixture does not start target services or prove
first-boot enrollment, boot or active LSM behavior. No empty Provides package
may fake satisfaction of the board task.
Do not copy generic sysctl/governor tuning, default accounts, arbitrary on-boot
commands, or desktop/media/NPU umbrellas. The module's Ethernet is gmac1/RTL8211F;
PCIe r8125 is conditional on an actual added NIC, not a board requirement.

Preserve the original 33 userspace seeds, replacing only the standalone ttyFIQ0
config selection with the reviewed board-support package. Add AppArmor policy,
Debian firmware-brcm80211/firmware-realtek and deliberate DKMS tools. Preserve
Essential/APT/dpkg/glibc/systemd/udev, networking, SSH, time, nftables, storage and
recovery behavior. Do not strip target compilers while retaining DKMS. Regenerate
the complete installed manifest; historical 184-package metadata solving is not
that manifest. No broad Radxa firmware/diversion bundle is selected; additional
radio calibration or Bluetooth blobs require chip/file/license evidence.

## Sources, licensing and reproducibility

Preserve upstream LICENSE and every package copyright/notice. Corresponding
kernel/U-Boot sources, patches, generated configs and build scripts must accompany
any later public binary delivery. rkbin and radio blobs need per-file license
review; wrapper GPL text is not a blanket blob redistribution grant. No wholly
FOSS, secure-boot or source-to-binary equivalence claim is made.

The subsequent loader correction checks the exact DDR v1.25, USB helper v1.17,
BL31 v1.46, boot_merger tool, RK3566 packing INI and original rkbin LICENSE bytes
against SHA256 pins before tool execution. The upstream RK3566 BL31 name is a
symlink to `rk3568_bl31_v1.46.elf`, not a different SoC target; the recipe now uses
that same verified file explicitly. `loader-inputs.json` records every checked
hash and the unmodified notice. Rockchip's notice permits use/copy/distribution
and prohibits reverse engineering and notice removal; it is included in the
loader package's docs without replacing the existing upstream copyright.
This improves notice/input preservation but does not complete legal review or
corresponding-source delivery. Attempt 13 compiled the correction; its actual
loader package contains the exact original rkbin notice bytes and retains its
existing copyright. Attempt 12 predates it. No blob bytes are added to Git.

Selected-payload delivery records remain open (not additional development gates):

- CS-1: bind actual binary hashes to complete modified kernel/U-Boot sources,
  recipe patches, generated configs, board sources, build scripts and notices.
  Binary-only builds, diagnostics and encrypted retention are not that delivery.
- NOTICE-1 packaging check passed in attempt 13: the actual loader package's
  `LICENSE` matches the pinned rkbin SHA256 and `loader-inputs.json` notice,
  alongside its existing copyright. This is not full source/license clearance.
- RADIO-1: before final-image delivery, record exact installed firmware versions,
  files/hashes and matching Debian source/copyright stanzas for the two selected
  radio packages; seed names alone do not establish file-level license closure.
- OVERLAY-1: reconcile the shipped overlay tree's GPL-2 root license, GPL-3+
  packaging declaration and file-specific notices; do not apply wrapper terms
  indiscriminately to the installed source tree.

At the pinned overlay revision, source-policy reconciliation selects 818 files,
not the preliminary 819: `.github/local/rules.local` explicitly excludes
`arch/arm64/boot/dts/rockchip/overlays/Makefile.rk3588-can` from installation.
This is not an inspection of a built package. Six notice/delivery questions remain:
four selected Makefiles declare GPL-2.0 rather than the wildcard GPL-3+;
46 Qualcomm overlays declare BSD-3-Clause with full text delivery unresolved;
one overlay declares `(GPL-2.0+ OR MIT)` and BayLibre/Radxa attribution;
the dummy module's generic `MODULE_LICENSE("GPL")` specifies no version;
766 files have no detected file-local notice, leaving root/wildcard scope
unresolved; and final binary delivery of the license texts needs inspection.
Absence of a file-local notice is not evidence that a file is unlicensed.
Source: [pinned overlay packaging and notices](https://github.com/radxa-pkg/radxa-overlays/tree/a0ffd564a2fdb836e2f3fe60b2c607a58d1d69b6).
No blanket license clearance or changed upstream terms are inferred.

The pinned U-Boot notice is `Licenses/README` plus `Licenses/gpl-2.0.txt`, not
a missing root LICENSE. Bootutils declares its terms in `debian/copyright`.
The loader recipe replaces vendor SPL with compiled U-Boot SPL; the selected
embedded proprietary inputs are DDR, USB helper and BL31, while `boot_merger`
is a host build tool. These source-selection facts do not prove the contents or
corresponding-source completeness of a later delivered binary.

The first source probe pins OCI manifests and Git sources but resolves fresh
signed Trixie build dependencies. It records installed source/package versions,
APT InRelease files and generated `.buildinfo`/`.changes`. These enable auditing;
they do NOT by themselves freeze the entire build-input closure. Pin the observed
compiler/tools and authenticated package snapshots before image qualification.
Two independent clean builds and binary comparison are required for a bitwise
reproducibility claim. Do not suppress signature/expiry errors to recreate an
old snapshot.

Reference-image bytes are not reused. Historical `rsdk-r2` has an empty builder
revision and a reported self-entry mismatch in its aggregate SHA512 list. Four
small metadata assets were independently consistent in the source audit, but
that is not a whole-release PASS or proof of image tampering. The full reference
image was not independently hashed here. Avoiding its binaries removes the need
to trust them for this rebuild; it does not retroactively repair the defect.

## Updates

Routine Debian updates must use authenticated Trixie/update/security sources.
Vendor kernel/U-Boot/rkbin/overlay/config maintenance is the project's explicit
responsibility, not Debian security coverage. A named CVE/backport owner and
support horizon remain unassigned; stable-release claims are blocked.

Review source/backport/license diffs; rebuild kernel + DTBs + headers + aliases +
overlays as one tested update unit. Review U-Boot + rkbin + exact-carrier loader
as another. Increment local packaging versions monotonically, retain known-good
boot inputs and retest install/upgrade/reboot/rescue before promotion. Never
silently switch lineage, downgrade, reboot unattended, write SPI or scan disks.

The planned no-server experiment uses an ephemeral job-only APT signing key and
signed whitelist repository bundle. Trust a future bundle/key only after verifying
its GitHub attestation against the exact repository, signer workflow, approved
signer digest and source digest; then use a temporary scoped `signed-by` APT
source and remove it after authenticated import. The producer now has a separate
trusted signing job that attests only the verified repository's encrypted bundle,
then checks exact repository/workflow/source/signer identity and tamper rejection.
The package builder itself still has read-only token scopes. Attempt 13 at
`c24ad2a0598d000727763803b8c678d6a3411fc0` now verifies the actual producer
round-trip. The later exact-SAN consumer at `063d7fd5e309e585e229f2d7e0bef0c5e747b995`
accepted that producer's ciphertext, with wrong-source/digest/subject rejection.
Private authenticated decryption and manifest/key/signature/index/payload closure
passed. Isolated ARM64 APT acquisition accepted all ten exact packages and rejected
changed metadata, without installing packages or changing host trust. Deliberate
imported-package installation and enduring update authority remain unverified.
The standalone `scripts/cm3-verify-bundle.py` consumer requires a local public
attestation bundle, independently approved full producer commit and ciphertext
SHA256. It uses official `gh attestation verify` with fixed repository/workflow,
source/ref/signer, issuer, SLSA v1 and hosted-runner policies; a failed check emits
no receipt. Its JSON receipt verifies ciphertext only: it neither approves the
inner APT key nor authorizes decryption/import. Producer and later consumer
revisions must not be conflated, and historical encrypted retention is not an
attested update channel.
The certificate SAN must equal the complete workflow URI ending in
`build.yaml@refs/heads/dev/cm3-debian-cli`. Official gh 2.101's
`--signer-workflow` matches a prefix, so both verification sites use exact
`--cert-identity` instead; gh forbids combining those two selectors.
Upstream signed-fixture checks reproduce prefix acceptance and exact-identity
rejection of a truncated workflow, extra suffix and wrong ref. This verifies
the CLI policy behavior; attempt 13 separately validates the actual CM3 producer.
If attestation fails/unavailable, stop; obtain an approved
persistent signing-key mechanism instead of falling back to unsigned packages.
No private key or enrollment secret may enter an artifact. There is no claimed
existing maintained online BSP feed.

Before support or update promotion, assign a named maintainer and support
end date for the source-built BSP and project board support. Responsibility must
cover routine upstream/license review, urgent CVE triage/backports, signing and
attestation trust, monotonic versions, distinct-version upgrades, known-good boot
retention and rescue verification. Review Debian and vendor changes monthly and
on urgent advisories; this is a required maintenance policy, not evidence that a
maintainer or service already exists. Unassigned ownership remains a G2 blocker.

Official [6.1.84-17 recipe metadata](https://github.com/radxa-pkg/linux-rk2410-nocsf/tree/10fe8d13a975faa185844e52185948d10f0c8103)
identifies a real same-lineage recovery-fixture candidate with kernel gitlink
`05e5b99dfa5ac568ab684ad83c1001491d1a70e5`; upstream
[changes to -18](https://github.com/radxa-pkg/linux-rk2410-nocsf/compare/6.1.84-17...6.1.84-18)
include source and configuration, not just a version rename. That does not establish
an authenticated, coherent second BSP unit or DKMS compatibility. Current pins
remain unchanged; no historical package download, build, downgrade or physical
recovery is authorized or proven by this metadata.

Current diagnostic retention is not a corresponding-source distribution: the
diagnostic artifact deliberately excludes source trees and binaries. The separate
encrypted recovery artifact is internal retention, not a reviewed plaintext
distribution or attested update channel; see `build.md`. Before any binary
artifact delivery, separately assemble and review the complete applicable
source/config/patch/build-script and license records, including file-level blob
hashes/terms. If redistribution terms or corresponding sources cannot be closed,
withhold the affected payload rather than treating a successful compile as legal
clearance. Never upload the private research bundle as a substitute.
