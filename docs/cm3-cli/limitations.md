# Limits and safe recovery boundary

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

No image, boot success, performance improvement, stable support or full hardware
compatibility is claimed. Read `validation.md` and all 28 original matrix rows.
No missing bench fixture may be relabeled NOT PRESENT. Actual RAM/eMMC/radio/SPI
population, module/carrier revisions and physical wiring remain unknown.

## Exact carrier

- Two fitted USB2 sockets plus expansion header, not four promised fitted USB-A
  sockets or native USB3. Legacy exact-board wiki wording conflicts with the
  carrier datasheet; physical inventory must resolve the actual routing.
- CM3 native USB3/eDP use its third connector, which this carrier does not mate.
  The module has one HDMI transmitter; two carrier HDMI sockets do not establish
  dual independent output. Camera/display graphs and sensor/panel support need
  revision-specific review, not Raspberry Pi CM4 compatibility assumptions.
- microUSB hub/device switching, Rockchip Maskrom and recovery require exact
  module/carrier/loader qualification. Raspberry Pi `rpiboot`/`config.txt` methods
  are not substitutes. Revision-dependent GLOBAL_EN/startup behavior is untested.
- PCIe2 x1/NVMe link/reset/power behavior must be qualified with an expendable
  endpoint. NVMe root/boot is a separate experiment, not ROM-native support.
- GPIO pin26 hazards, CSI lane remapping, DSI panel graphs, fan control and RTC
  behavior require native schematic/pinout inspection before attachment. PDF
  text and partial spreadsheet extraction do not establish all wiring, hidden
  sheets, formulas or electrical limits. Do not attach a Pi-specific peripheral
  blindly. Preserve voltage-safe serial recovery and thermal protection.
- GPU/media/NPU kernel configuration is not proof of a supported headless API.
  Optional vendor userspace ABI, radio firmware/calibration and Bluetooth remain
  unresolved. No broad firmware package or desktop runtime is a workaround.

## Future artifact and bench checks

Before any write, inspect the exact artifact on an external host: authenticated
provenance, xz integrity, compressed/raw hashes, partition map, exact DTB, extlinux
root identity, matching initramfs/modules/headers and loader payload. Preserve
GPT/512-byte sectors/ext4; partition name `efi` does not imply a UEFI boot chain.
The audited assembly places partition 1 at LBA32768, ID block at bs=512 seek=64
and bs=4096 seek=136, and FIT at bs=512 seek=16384. The later image checker must
assert both raw ranges are disjoint from GPT/partitions and within an image-only
regular file. These offsets are source evidence, NOT a command to write media.

Physical testing needs separate approval naming sacrificial hardware and the
exact OS target by stable identity, serial/WWN/capacity and mount-holder checks.
Physically disconnect production NVMe/data disks. Prepare a verified rescue
microSD, external recovery host, reviewed exact loader/tool versions and console
before the first flash. Do not erase SPI to discover boot order. Read back the
written image range before first boot; capture serial and identify actual boot
medium/kernel/DTB/root source, not merely an attached card.

Rehearse rescue from a deliberately invalid configuration only on approved
removable OS media, then reflash/readback and secure provisioning. Recovery and
boot-source precedence are still UNTESTED. There is no automatic rollback or
verified rescue claim here. Power-cut/fault injection requires separate written
approval, finite cycles/endurance budget, external observer and sacrificial media.
Stop on the first integrity/safety fault and preserve evidence read-only.

No production OS/services, partitions, bootloader, SPI, NVMe data or applications
may be changed. CasaOS, YunoHost, Docker installation in the target, migrations
and application-platform testing are out of scope. External CI container tooling
is build infrastructure, not software shipped in the target.
