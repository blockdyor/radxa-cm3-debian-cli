# Retained image2: validation levels and evidence index

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

This work does not simulate or replace RK3566 / Radxa CM3 / CmRat qualification. QEMU `virt` is not an RK3566 emulator. Every physical hardware status remains UNTESTED. Levels 1–3 below do not prove level 4.

Evidence consolidated on 2026-10-31 for task `t_3dac8608`, from five completed validation tasks. This is documentation and preservation, not a product fix, rebuild, release, or permission to flash storage. The original gates are unchanged.

## 1. Exact subject and build validation

The subject is the retained faccad image2, not discarded image1 or the current documentation commit:

- Producing commit: [`2b41b830cae9efc313f3d39d85be265b6e3eae25`](https://github.com/blockdyor/radxa-cm3-debian-cli/commit/2b41b830cae9efc313f3d39d85be265b6e3eae25).
- Producing workflow: [run 41199013085](https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41199013085), `.github/workflows/build.yaml` (display name `CM3 package source preflight`), attempt 1, cumulative producer 22, full-image attempt 2/3.
- Raw `cm3-trixie-arm64-cli.img`: SHA-256 `b0d1f56240fafc49cc32ceab0f041d4bb6f529604635684135ccc6ad26ebbff8`, 1730675712 bytes.
- XZ `cm3-trixie-arm64-cli.img.xz`: SHA-256 `6b72f1005c517309e9647e7c65d2344ee31e013da0e2f4ae5a07c4f2afcd8037`, 207281440 bytes.
- Full retained artifact ZIP, locally named `retained-image-sources.zip`: SHA-256 `cac0f8575b91529e4809d86a99fb460b2279acc19fd8eea56469dca51d959fad`, 1497046145 bytes.
- [Image/source artifact 13044838581](https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41199013085/artifacts/13044838581): recorded expiry `2026-11-14T14:03:12Z`.
- [Separate attestation artifact 13044604426](https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/41199013085/artifacts/13044604426): recorded expiry `2026-11-14T14:04:02Z`; ZIP SHA-256 `16bd19edc0cf4063dd96135a6a2b4f7d18065d63f41d3e5ce4684dcec716bc1a`.

Build validation establishes the recorded compilation, same-run 183 offline tests with zero failures/errors/skips, Stage A, assembly, artifact closure and exact-source provenance. It does not establish runtime behavior. See the historical [candidate handoff](retained-image-candidate.md), [admission decision](retained-image-admission.md), and [independent retained-image verdict](https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1#issuecomment-6545317238). The independent verdict and five reports below supersede the candidate document's historical “inspection pending” statement. The latter remains intact as an acquisition record.

Historical cryptographic evidence is preserved, not claimed as new execution: the predecessor checked exact-source OIDC identity, tampered signatures, 500 delivery hashes, 490 source hashes, 149 Debian source identities / 327 DSC payload hashes and 276 firmware paths. The build worker's 502-member accounting and independent verifier's 500 delivery hashes describe different archive/manifest scopes; neither is a new five-task test count. Original records in the offline packet retain those scopes. No bitwise rebuild or fresh authentication of every installed binary package is claimed here.

Historical image1-only/no-download and OVERLAY-1-pending statements in older validation/build reports are not current candidate status. Image2 is retained with exact corresponding sources/notices; the official Radxa metadata clarification and reviewed firmware terms are recorded in the admission/candidate documents. This does not make proprietary loader/radio payloads wholly FOSS, remove their component-specific conditions, or establish immutable-input/bitwise reproducibility and ongoing BSP maintenance. Those remaining limits are distinct from the resolved retention and metadata-clarification gaps. No source/package-signature execution is inferred merely from preserved source files.

## Verdict vocabulary

- PASS: a named behavior or rejection actually exercised virtually, meeting its explicit expectation. A green test reproducing a hazard is not a safety requirement passed.
- STATIC PASS: offline-only validation; not a boot or runtime result. A host validator may execute while the target behavior remains static.
- UNTESTED: physical qualification is still required, or the named required behavior has not been established. It is not a pass.
- NOT APPLICABLE: not meaningful under this simulation (for example the RK3566 boot chain on `virt`), or no authentic expansion handler exists. Missing functionality remains unmet, not waived.
- FAIL: an attempted check did not establish its expectation; retained explicitly rather than folded into UNTESTED or PASS.

Native installed-script execution with mocks is reported separately as NATIVE FIXTURE EXECUTED. Parent lifecycle reports use PASS for this narrower scope; this index does not recast native host execution as QEMU execution. STATIC VERIFIED and QEMU/USERSPACE VERIFIED in the annotated matrix describe only the stated supporting evidence, never the whole physical row. Native command-double findings remain explicitly native even where carried in a STATIC VERIFIED supporting annotation.

## 2. Offline image validation

[Offline report](evidence/retained-image2/offline/offline-validation-report.txt), task `t_6c2ac45f`: STATIC PASS within its stated limits. Actual retained bytes, not only source configuration, were inspected without target execution:

- Protective MBR, primary/backup GPT CRCs and equality, three partition ranges and 1 MiB alignment; FAT16 config/EFI-labelled partitions and ext4 root; three read-only filesystem checks exit 0. An EFI label is not proof of a UEFI boot chain.
- Both FAT volumes have no allocated data clusters; boot files are in the root filesystem. Root inventory, fstab/UUID correspondence, normal/rescue extlinux paths, CM3/carrier DTB compatibility, three loader placements and ARM64 kernel magic/configuration were checked. The retained kernel is `6.1.84-18+cm3cli1-rk2410-nocsf`.
- 364 initramfs members parsed; 1258 module dependency paths exist, with only two module ELF/vermagic samples checked; 276 firmware hashes match. No module loading or device firmware request was executed.
- 270 configured package identities match the manifest. APT sources/trust intent, machine-id and SSH-key absence, 22 password-locked accounts, focused root ownership/modes, project units and 30 systemd links were inspected. Thirty links include aliases and masks, not 30 enabled services.

[Security report](evidence/retained-image2/security/security-audit-report.txt), task `t_d8a85f3e`: 10 STATIC PASS areas, one SCOPED EXCEPTION, two UNTESTED areas. All 30051 allocated regular files (871005658 bytes) were scanned and reconciled with 2631 filesystem directories. Bounded scanning found no identified deployment/build/developer credentials or password hash material; it is not a secret-free, vulnerability-free or full forensic warranty. SSH policy is public-key-only, no root login, owner-group restricted; enrolled owner sudo is intentionally root-equivalent `NOPASSWD: ALL`. Policy text is not authenticated login evidence.

The literal no-private-keys condition is NOT MET: eight complete PEM blocks in `libgnutls.so.30.40.3` match public upstream self-test vectors in retained `gnutls-3.8.9/lib/crypto-selftests-pk.c`. This requires an explicit public-test-vector exception; no credential values are published. No waiver is inferred. Fresh repository/package signature-chain verification remains UNTESTED; hash matching and APT configuration are not signatures. Existing build-time provenance is not contradicted by the missing fresh per-installed-package chain.

AppArmor activation intent is STATIC PASS, not blanket confinement: boot cmdline requests AppArmor although the retained default CONFIG_LSM omits it. Profile text includes 76 explicit unconfined and 38 complain-mode profiles. Physical retained-kernel activation and enforcement remain UNTESTED; the later cloud-kernel observation below does not change that.

## 3. Virtual/userspace validation and lifecycle fixtures

[Virtual report](evidence/retained-image2/virtual/virtual-validation-report.txt), task `t_f1e96835`: retained ARM64 userspace actually ran in QEMU 10.0.13, `virt`, Cortex-A53 TCG, one vCPU, alternate Debian `6.12.107+deb13-cloud-arm64` kernel (package `6.12.107-1`). No retained RK3566 kernel boot was demonstrated: the retained-kernel attempt exited 0 with empty console and lacks PL011/virtio drivers needed by this harness.

The full retained systemd 257 PID1 started on the alternate kernel but hit generator/journald/time-sync/device timeouts; it was interrupted, without a final child numeric exit. This is not a healthy multi-user boot or an established physical image defect. A separate retained-Bash PID1 path completed two boots, 24 actual probe commands, forced reboot/poweroff and QEMU exit 0 on modified disposable partition copies, not byte-identical full images.

| Requested runtime area | Evidence and scope |
| --- | --- |
| Userspace execution | PASS for retained Bash/tools on alternate kernel; retained board boot NOT APPLICABLE to `virt`, physical boot UNTESTED. |
| systemd configuration/runtime | STATIC PASS for enabled configuration; full runtime FAIL/timeouts; `systemd-analyze verify` FAIL due missing man documentation commands. |
| Package manager | PASS for `dpkg --audit`, `apt-get check`, simulated Bash install; no real package upgrade/install or fresh signature pass. |
| DNS/network | PASS for harness-assigned virtio IPv4 interface/address/route; DNS FAIL (getent exit 2), restricted APT refresh FAIL (timeout 124); no DHCP/IPv6/PHY claim. |
| SSH configuration/startup | PASS for missing-key rejection, key generation, `sshd -t`, direct loopback listener; handshake FAIL (`ssh-keyscan` exit 1), owner login UNTESTED. Not gated systemd SSH. |
| First boot | PASS for actual offboard enrollment/--check rejection (exit 1); successful CM3 enrollment NOT APPLICABLE to this board-mismatched VM. |
| Identity | PASS for machine-id/key generation and persistence across direct reboot, not cross-device uniqueness or duplicate detection. |
| Expansion | NOT APPLICABLE as executable test: project root expansion absent; requirement remains unmet/UNTESTED. |
| Logs | PASS for actual sshd file log and host serial capture; probe tee FAIL due absent /dev/fd, full journald completeness not established. |
| Reboot/shutdown | PASS for forced kernel calls only; systemd ordering NOT APPLICABLE to successful direct-init path, physical behavior UNTESTED. |
| LSM | PASS for observed cloud-kernel AppArmor enabled; not retained-kernel activation or loaded-profile enforcement. |

The virtual report has 24 scoped verdicts: 12 PASS, one STATIC PASS, six FAIL, four NOT APPLICABLE, one UNTESTED. These are not 24 green tests. The separate 24 probe commands have exits 0:16, 1:6, 124:1, 2:1; deliberate negative exits are not automatically defects. Preserve both denominators.

[Lifecycle/storage report](evidence/retained-image2/lifecycle/lifecycle-safety-report.txt), task `t_23036e0d`: 36 native fixture test methods passed, zero failures/errors/skips. Installed Python/Bash enrollment, boot wrapper and U-Boot functions ran with fixture roots, account doubles and recording storage commands; host OpenSSH used explicit disposable prefixes. This is neither QEMU nor retained-systemd execution. Pristine/invalid owner, missing/existing/invalid machine-id, missing/stale host keys, idempotent retries, interrupted/EROFS and policy-tamper cases are covered with exact boundaries in the report. Boot wrapper updater failure propagation was exercised, not full extlinux rollback.

Storage fixtures represent SD/eMMC/NVMe/USB, an unrelated data NVMe and a root partition. The loader does not consume that topology metadata: it takes an explicit target. Already-expanded and expansion-required metadata have no authentic consumer because expansion is absent. No real storage operation, automatic disk selector, Windows helper, SPI or physical maskrom recovery was exercised.

### Demonstrated defects and limits, not corrected

1. Explicit data-NVMe and partition targets are accepted by the low-level loader helper without mounted/root/transport guards. No accidental automatic NVMe discovery was observed. Never use this as an unattended safe selector.
2. Missing U-Boot payload is detected after two recorded idblock write intents. These were mocks, not partially written disks.
3. Maskrom loader `db` failure is ignored; later write/reset intents can execute and return success. This is not proof of loader readiness or safe recovery.
4. Enrollment readiness accepts nonempty invalid host-key material and valid duplicate machine-id. Clean shipped identity is verified offline, but existing cloned identities/keys are preserved by normal tools, not detected or rotated automatically.
5. Late ENOSPC injection leaves earlier account/policy effects even though readiness stays closed; no transactional rollback claim.
6. OS-root expansion and automatic rollback implementation are absent. Generic resize utilities or mock metadata do not satisfy the requirement.

Zero product defects were corrected and zero image rebuilds occurred across these validation tasks. VM service/DNS/handshake/logging failures are disclosed simulation outcomes, not proven CM3 defects. Separate authorization and defect work are needed before any product change.

### Controlled negatives: all 11 requested areas

[Negative report](evidence/retained-image2/negative/negative-test-report.txt), task `t_52443539`, preserves predeclared expectations, mutations, commands and diagnostics:

| Area | Verdict / limitation |
| --- | --- |
| Corrupt manifest | STATIC PASS: truncated source-lock rejected by harness JSON parser, not end-to-end admission. |
| Wrong checksum | STATIC PASS: pinned delivery source-material helper rejects wrong digest; not a new raw-image admission run. |
| Missing partition | STATIC PASS: pinned layout contract rejects altered metadata, not damaged GPT/runtime recovery. |
| Missing DTB | STATIC PASS: checker detects removed actual referenced DTB in disposable partition; no bootloader rejection observed. |
| Missing module | STATIC PASS: referenced module removed and detected; no module-load/boot-failure inference. |
| Wrong fstab UUID | STATIC PASS: pinned boot contract rejects actual copied-file mutation; PID1 recovery UNTESTED. |
| Broken APT source | PASS: actual guest APT exit 100 with malformed-list diagnostic and no continuation marker, NIC disabled. |
| Duplicate machine-id | PASS reproduction of preservation, not detection: retained tool keeps same valid ID in two guest fixture roots. |
| Existing SSH keys | PASS reproduction: cloned keys remain unchanged; explicit removal produces distinct fresh key. |
| Insufficient space | PASS within scoped execution: five native injected enrollment errno-28 failures; actual guest 64 KiB tmpfs write fails exit 1 and recovery write succeeds. Not full-root enrollment. |
| Expansion failure | NOT APPLICABLE: no authentic handler. Requirement remains unmet/UNTESTED. |

Six offline rejections + five native write-fault cases + five actual guest probe commands + 36-test lifecycle replay = 52 cases matching expectations, zero unexpected assertion failures/skips. One absent-expansion case is documented, not executed. The 36 lifecycle methods are already included in 52; do not add them again. Four PASS area labels, six STATIC PASS areas and one NOT APPLICABLE area are requirement-level labels, not another test count. Original virtual 24 probes and later negative five probes are distinct runs; counts are kept separate rather than inventing a combined qualification score.

## 4. Physical CM3 hardware validation

[Original nine-column matrix](hardware-matrix.tsv) remains byte-for-byte unchanged, SHA-256 `24c30e0964dcec3326c723ad8f8b84c39104ff7a8688f33a7e997b2ef2098232`; [archival copy](evidence/retained-image2/hardware-matrix.original.tsv). The [annotated matrix](hardware-matrix-evidence.tsv) preserves all nine original fields of H01–H28 and appends row-specific supporting evidence, limits and report paths. All 28 `current_status` values remain UNTESTED. Original source labels S1–S8 and procedures V01–V09 are defined in [validation.md](validation.md#matrix-source-key).

The original H27 equipment sentence predates disposable fixtures: fixtures are now available as software evidence, but its historical text is preserved, not used to deny the work above. Hardware-equipment availability remains unknown. G0–G7 texts and evidence-hashes locks are not modified. Original G1/G2/G7 remain unmet; no row is waived, including mandatory PCIe/NVMe H13.

Remaining physical checklist (apply exact row applicability and existing proposed procedures, not an invented simplified gate):

- H01–H06: inventory exact module/carrier/RAM/SPI; verify sacrificial flash/readback, retained boot chain, cold/warm/shutdown cycles per claimed medium, SD/eMMC/recovery, OS-only growth and data-disk preservation. No SPI writes authorized.
- H07, H27: two independent fresh identities, secure serial and authenticated SSH, effective gating/firewall/retained-kernel AppArmor and enforcement, actual systemd/udev/network/time and isolated kernel capabilities; authenticated update and distinct-version BSP reboot/rescue.
- H08–H10, H26: physical OPP/sensors/cooling, memory correctness/pressure, wired DHCP/DNS/IPv6/throughput, rated PSU and bounded thermal/soak measurements; power only with an external meter.
- H11–H13: fitted USB topology/hotplug, approved ROM USB/Maskrom recovery, actual PCIe/NVMe negotiation and dedicated-file integrity/durability, with no production disks.
- H14–H25: inventory conditional radios/HDMI/GPIO/I2C/SPI/UART/RTC/audio/CSI/DSI/GPU paths first; review electrical routing before connecting anything; execute only compatible claimed paths.
- H28: separately approved sacrificial rescue/reflash and finite failure/power-loss protocol, preserving evidence and unrelated storage. No production or destructive authorization is supplied here.

Recommendation: retain as an EXPERIMENTAL engineering candidate with these defects and limits prominently disclosed. Do not present it as hardware-tested, production-ready or an unattended safe installer. A public prerelease is not authorized or created by this document; downstream owner/reviewer must decide on the explicit self-test-key exception, unresolved software safety/expansion gaps, maintenance ownership, trust/reproducibility limits, and preservation of exact sources/notices. Existing experimental retention does not imply stable support or physical qualification.

## Preserved evidence and reproduction

All five reports and original packets are now repository files, not only Kanban paths. [Packet index](evidence/retained-image2/packet-index.json) records source task IDs, exact SHA-256 and sizes. Each packet contains its own manifest and verification; ZIP CRC and member manifests must be checked before replay. The offline packet also preserves the prior independent inspection/attestation/source evidence under `prior/`; [original independent handoff](https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1#issuecomment-6545317238) remains the historical publication.

| Evidence | Preserved packet | What to read/run after safe extraction |
| --- | --- | --- |
| Offline | [ZIP](evidence/retained-image2/offline/cm3-offline-validation-evidence.zip) | Report reproduction section; `prepare.py`, `offline-inspect.py`, `finalize.py`; `evidence/commands.json`, fsck logs, `tool-downloads.json`, version summaries. |
| Virtual | [ZIP](evidence/retained-image2/virtual/cm3-virtual-execution-evidence.zip) | `REPRODUCE.txt`, `bootstrap.py`, `prepare-inputs.py`, `probe-vm.py`, `run-virtual.py`, `run-direct.py`; serial logs, command JSON, attempt logs, copy modifications and tool manifest. |
| Lifecycle | [ZIP](evidence/retained-image2/lifecycle/cm3-lifecycle-safety-evidence.zip) | `python3 test_lifecycle.py > execution.log 2>&1`; includes installed subject/pinned-source, observations, environment and storage fixture metadata. Preparation is not needed for portable replay. |
| Security | [ZIP](evidence/retained-image2/security/cm3-security-audit-evidence.zip) | Report environment section; `audit.py`, `supplement.py`, `key-provenance.py`, `coverage.py`, `finalize.py`; sanitized findings/coverage/policy metadata. Restore parent debugfs paths first. |
| Negative | [ZIP](evidence/retained-image2/negative/cm3-negative-test-evidence.zip) | `REPRODUCE.txt`; `negative-static.py`, `run-negative-runtime.py`, lifecycle replay, `bash -n guest-negative.sh`, `finalize-negative.py`; exact mutations/results and original hashes. Restore parent VM tools/kernel/initrd first. |

Small exact records are directly available: [packages](evidence/retained-image2/records/packages.tsv), [verification](evidence/retained-image2/records/verification.json), [delivery manifest](evidence/retained-image2/records/delivery-result.json), [SHA256SUMS](evidence/retained-image2/records/SHA256SUMS), [raw checksum](evidence/retained-image2/records/RAW-SHA256SUMS), [XZ checksum](evidence/retained-image2/records/IMAGE-XZ-SHA256SUMS), [Stage A](evidence/retained-image2/records/image-stage-a.json), [same-run tests](evidence/retained-image2/records/image-offline-tests.json), [admission](evidence/retained-image2/records/image-admission.json), [source lock](evidence/retained-image2/records/sources/source-lock.json), [builder packages](evidence/retained-image2/records/sources/builder-packages.tsv), [loader inputs](evidence/retained-image2/records/sources/loader-inputs.json), [delivery inputs](evidence/retained-image2/records/sources/delivery-inputs.json), [installed source identities](evidence/retained-image2/records/sources/installed-source-identities.tsv), [firmware manifest](evidence/retained-image2/records/sources/firmware-files.json), [notice review](evidence/retained-image2/records/sources/notice-review.json). These records do not replace full corresponding sources/notices in the retained 1.5 GB ZIP.

Before expiry, obtain the entire original artifact and attestation using the candidate document's exact download instructions. Confirm all three subject hashes above; stop on mismatch. The existing local retention is `/opt/data/artifacts/cm3-qualification/t_ce5ca21d/`. Those large files are not in this repository and local copies are not an off-host backup. Originals were mode 0644 with unchanged before/after hashes, not OS-enforced immutable files. Preserve image, full source/notices and signature together.

Replay only in a fresh trusted ordinary Linux ARM64 directory with ample disk (virtual preparation advises at least 7 GB), reviewed pinned scripts and verified originals. Do not mount/chroot original images or expose real block devices. Rebind hardcoded parent scratch/tool paths as documented; finalizers may overwrite disposable outputs. Offline tools: Python 3.14.7, debugfs/e2fsck 1.47.2, dosfstools 4.2; lifecycle execution recorded Python 3.13.5 and Bash 5.2.37. Exact OpenSSH and dependency versions/hashes are in each packet's environment/tool manifest. Different native Python versions reflect different recorded execution environments, not a single fabricated combined host.

Virtual replay uses alternate cloud kernel and regular-file disks with restricted slirp/no forwards; negative guest uses `-nic none`. No KVM, host filesystem shares or block passthrough; namespaces were denied. Host preparation and native mocks are trusted inspected code, not an arbitrary-code security sandbox. Tool downloads were pinned to Debian HTTPS index hashes, not newly signed-Release authenticated; archive availability can block replay. Generated VM disks and private keys are deliberately excluded. Full-system timeouts, failed probe-file logging and earlier harness corrections remain disclosed in original reports/logs; do not run `*-executed.py` historical attempts as the final harness.

This consolidation verifies preservation, linkage, matrix equivalence and scope; it does not relabel all upstream runs as freshly replayed. No new build, physical operation, release or product correction is part of publication.

Recheck this publication from the repository root with `python3 docs/cm3-cli/evidence/retained-image2/verify-publication.py`. The read-only checker verifies all five packet hashes/CRCs and indexed member hashes, report byte equivalence, local documentation links, original locked gates/matrix and every original field in all 28 annotated rows. It includes a negative self-check rejecting promotion of a physical status to PASS. [Recorded publication check](evidence/retained-image2/publication-verification.json) is preservation evidence only; none of these checks boots the image.
