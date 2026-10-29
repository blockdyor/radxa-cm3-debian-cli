# Validation status and future measurement protocol

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Original definitions are preserved byte-for-byte in
`gates-validation-verbatim.txt` and `gates-consolidated-verbatim.txt`.
`evidence-hashes.json` locks those texts and the complete original
`hardware-matrix.tsv`. Do not choose the easier of the two wordings or relax a
threshold after observing a failure. Numeric thresholds are provisional proposals
to freeze with the owner before testing; they are not measurements/vendor ratings.

## Current status

G0: no device writes performed, safety/correctness not demonstrated on hardware.
G1: no fresh install/boot/provisioning/expansion/rescue test; not demonstrated.
G2: not met. Signed ARM64 installation, real DKMS and boot-fixture checks pass,
but active LSM, provisioning, distinct-version update/reboot/rescue, complete
input/license closure and assigned vendor maintenance remain unverified.
G3: thermal/electrical/power untested.
G4: no B0 baseline or comparative performance measurements.
G5: no loaded responsiveness measurements.
G6: no sustained/soak measurements.
G7: not met. H01–H28 all UNTESTED (11 P0, 5 P1, 12 P2), no core row waived.

These are gate-status summaries, not replacements for either original text.
H13 remains a mandatory PCIe/NVMe qualification target even without an available
endpoint; no core row is waived. The complete nine-column TSV, including its
original applicability, equipment, evidence and procedure fields, is the matrix
of record rather than a shortened feature list.

## Evidence levels and open blockers

Status as of 2026-10-29; exact historical commits, runs and diagnostic digests are
in `preflight-status.md` and `attempts.json`.

| Evidence level | Established | Not established |
| --- | --- | --- |
| Static/local | Lock validation, original gate/matrix integrity and local policy/regression checks | Complete input snapshot, target execution, image or hardware acceptance |
| External source compilation | Attempt 12 compiled all nine selected BSP packages plus the separately sourced board package at its recorded revision | Source-to-binary reproducibility or compilation of later changes |
| External signed ARM64 fixture | Attempt 12 passed ten-package signed/tamper-negative installation, actual board lifecycle/effective SSH policy, native headers, real DKMS/DTBO, initramfs/extlinux/idempotence, reinstall/remove/restore and audit checks | Target provisioning, active target LSM, distinct-version BSP update or boot/recovery |
| Exact-product RSDK bootstrap | Attempt 12 bootstrapped the actual Trixie/ARM64/CLI profile in a fresh directory; 270 configured packages, clean audit and builder-identity/feed cleanup | Disk image, target services, enrollment, kernel boot or hardware compatibility |
| Boot/security/update | Board package, owner-input validator and boot fixture code exist | Secure target first boot, active target LSM, distinct-version BSP upgrade/reboot/rescue, attested update trust and maintenance ownership |
| Hardware/performance | No physical tests or B0 measurements | All H01–H28 remain UNTESTED; no boot, compatibility, speed, power or sustained-performance claim |

The config-fragment and archive-aware initramfs corrections now have external
coverage in run 40808183234. Its diagnostics and encrypted allowlisted compilation
are retained as native GitHub artifacts; recovery is optional. Current owner
authorization permits evidence-based same-job compile/validation retries.
Image assembly remains guarded off, and licensing/full-input
closure is incomplete. A fixture PASS, a dependency simulation, or the absence of
device writes cannot satisfy a gate. Static checks do not certify the remaining
security defaults: installing nftables does not establish firewall policy, and
compiled AppArmor support does not establish an active intended LSM.

A successful source-package job will only establish its explicitly recorded
stage. It cannot change a physical row or pass G0–G7. Any later package/image
result must cite the exact commit/run/artifact hash and identify performed versus
unperformed checks. No image produced yet; no release published.

## Matrix source key

The original S1–S8 labels remain unchanged in the matrix:

- S1: https://docs.radxa.com/en/som/cm/cm3/low-level-dev/rsdk
- S2: https://github.com/RadxaOS-SDK/rsdk/blob/dba5cba3eafb948a22787560bea56da2b9f8f163/src/share/rsdk/configs/products.json
- S3: https://github.com/radxa-build/radxa-cm3-rpi-cm4-io/releases/tag/rsdk-r2
  (reference metadata, not trusted image reuse; see provenance checksum caveat).
- S4: https://wiki.radxa.com/Rock3/CM3/raspcm4io/getting_started
- S5: https://wiki.radxa.com/Rock3/installusb-install-radxa-cm3-rpi-cm4-io
- S6: https://datasheets.raspberrypi.com/cm4io/cm4io-datasheet.pdf
- S7: https://www.debian.org/releases/
- S8: instrument semantics in official systemd-analyze, Linux thermal sysfs, fio,
  iperf3 and Debian apt-secure/stress-ng manuals. Record installed tool versions;
  documentation is not observed target behavior.

Module electrical sources also include
https://dl.radxa.com/cm3/docs/radxa_cm3_datasheet.pdf and
https://dl.radxa.com/cm3/docs/radxa_cm3_v1300_to_1320_pinout.xlsx.
Text extraction is not a complete native electrical review.

## Future procedures V01–V09

These are preparation, not authorization to execute on hardware. Apply the full
original gate texts, safety boundary in `limitations.md`, and device-specific
approval before physical or destructive work.

V01 Inventory: photograph revisions/SKU/PSU/cooling, map detected/reserved RAM,
module/carrier connectors and stable disk identities/mount holders. Disconnect
production disks. Review native schematics and exact DTB/pin mapping before
peripheral attachment. Unknown hardware stays unknown.

V02 Artifact/boot: independently authenticate provenance and compressed/raw
hashes, xz integrity, offsets/layout/fit, exact DTB/root identity. After separate
approval, flash/read back only the named sacrificial target. Capture reset-to-boot
serial and actual medium/stage identity. Test each claimed medium separately;
never overwrite SPI or resize a discovered data disk as a shortcut.

V03 Startup: external observer uses one monotonic clock for power assertion,
manual enable when applicable, first serial/kernel, login, link/DHCP and first
host-key-verified authenticated SSH command returning zero. TCP/22 and
systemd-analyze are not boot-to-ready substitutes. Record 20 cold + 20 warm boots
per medium, failures included; two fresh installs must have distinct identities
and host keys. After a fixed five-minute settle, capture idle CPU/RSS/PSS,
MemAvailable, storage, services/sockets and multi-user target.

V04 Debian/security: verify ARM64/Trixie, normal glibc/APT/dpkg/systemd/udev,
authenticated updates and security delivery, clean dpkg audit, ordinary service
package install/configure/start/stop/remove/reinstall, time and single-owner
network reconnect/DHCP/DNS/IPv6. Tampered signatures must fail in a disposable
fixture. Exercise isolated cgroups/namespaces/OverlayFS/bridge/netfilter/TUN/
IPv6/active LSM without container runtimes or changing management networking.
Test matched kernel/DTB/header/DKMS/initramfs/extlinux upgrades, reboot and rescue.
If no actual applicable security update exists, verify signed indices/origins;
do not invent an installed update.

V05 CPU/memory/responsiveness: establish untuned fresh B0, then counterbalanced
AB/BA reversible single-factor candidates. Pin binaries, workload/seed/threads,
absolute working sets, locale and outputs; one reported warm-up plus ten paired
short runs. Test one/all CPUs and bounded pattern verification/bandwidth beyond
cache; preserve >=25% RAM or a stricter reviewed OS reserve. Measure local
fork/exec and persistent authenticated SSH separately. Ten ten-minute runs per
idle/CPU/memory/I/O condition, >=1,000 non-overlapping fixed-cadence probes/run;
record failures/timeouts, pressure, faults and OOM. Missing PSI/counters are not
zero. No unbounded allocations or production benchmarks.

V06 Storage: named dedicated regular test files only; preflight resolves mount/
device, rejects unexpected paths/symlinks and preserves >=25% free after file
allocation. Bound writes/wear/temperature; record media/firmware/filesystem/fill.
Pin fio engine/version/seed/direct setting and achieved depth. Separate 1 MiB
sequential and 4 KiB random read/write at QD1/QD8, 60-second warm-up then
180-second measured runtime; label cache/direct-I/O limits. Add explicit fsync
cadence/durability and CRC/hash read-after-write plus post-clean-reboot deferred
verification. No raw-block fio or fsck of mounted writable media. Stop on errors.

V07 Network: isolated peer, both TCP directions, one/four streams separately,
ten 60-second runs per arm, consistently report/discard first five seconds.
Record negotiated speed, peer bottlenecks, retransmits/errors and unloaded/
saturated ping/SSH latency. Optional UDP is bounded; no public flooding. Radio
and coexistence tests apply only after inventory/license/firmware validation.

V08 Thermal/power: fix module/media/PSU/cooling/orientation/network/cache/tools,
proposed ambient 23 +/-2 C and paired starting sensors within 2 C; separately
qualify the owner-defined maximum ambient. Establish labels/units/trips/control
loop/observer first. Keep protection; abort at the reviewed margin (proposed 5 C
below the lowest critical trip or stricter vendor limit), sensor/control loss,
PSU/undervoltage or growing errors. Log one-second telemetry and logger overhead.
Three 60-minute thermal runs after 15-minute warm-up, cooling between; final
8-hour combined soak. Correlate throughput, cooling/frequency and errors; a
frequency readout is not an effective-clock proof. External rated DC meter needs
model/sample-rate/accuracy/input point/peripherals and integrated joules. No
meter means power UNTESTED; no software-estimated wattage claim.

V09 Recovery/failure: prepare approved exact loader/tools, rescue microSD, console
and verified image before flash. Rehearse removable-OS fault rescue, reflash/
readback and secure provisioning on sacrificial targets. Optional power cuts/
other failure injection need separate written scope, finite wear/cycle budget,
external fsync-acknowledgement observer and no production disks. Stop on first
integrity fault and preserve evidence, not repeat destructive guesses.

## Reporting and tuning

Keep all failures/exclusions with reasons and raw-data hashes, configuration,
operator/reviewer, commit/image/package/tool identity and ambient/cooling. Use
run-level paired 95% uncertainty, median/CV and probe/I/O percentiles; ten run
summaries cannot support a meaningful run-level p99, nor can correlated probes
be counted as independent boards. A single tested SKU qualifies only that SKU.

No speculative tuning in B0. Later candidates need a hypothesis/primary metric,
config diff and rollback. Security updates require matched arms/new B0 rather
than frozen vulnerabilities. Preserve journaling/barriers/flushes/diagnostics/
LSM/mitigations/thermal protection. No overclock/overvoltage/OPP/trip edits,
generic sysctl/TCP bundles or unsafe cache settings. Retain stock behavior when
benefit/trade-off is unproven. Kernel/firmware changes require full qualification.
