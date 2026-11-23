# Installing Debian 13 CLI on Radxa CM3 + DTV Electronics CmRat

This guide walks you through choosing a storage medium (**onboard eMMC**, **microSD**, or the **CmRat M.2 NVMe slot**), flashing the image with **Raspberry Pi Imager**, provisioning your offline SSH owner config, and booting a **Radxa Compute Module 3 (RK3566)** mounted on a **DTV Electronics CmRat** carrier board.

> **Important status notes before you flash**
> - **Physical hardware remains untested:** End-to-end live boot was verified on a custom virtual Radxa CM3 (`radxa-cm3-cm4-io` with the unmodified retained 6.1.84 BSP kernel, initramfs, DTB, `systemd`, `AppArmor`, `nftables`, and virtual `mmcblk0` eMMC). Physical CmRat switch wiring, Maskrom USB routing, Ethernet PHY, PoE, and power-loss recovery still require confirmation on real hardware.
> - **`v0.1.0-beta.1` first-boot bug advisory:** Live virtual-CM3 testing uncovered **4 first-boot bugs in `v0.1.0-beta.1`** (missing empty `/etc/machine-id` on read-only root, plus `grow_os.py` rejecting `x-systemd.automount`, transient systemd mounts, and Linux 6.1's `mb_optimize_scan=0` ext4 resize option) that prevent `cm3-cli-grow-os.service` and `cm3-cli-enroll.service` from completing on first boot. Fixes and regression tests are prepared for the next beta (`fix/cm3-first-boot-bugs` → `v0.1.0-beta.2`). If you are evaluating `v0.1.0-beta.1` before `v0.1.0-beta.2` is published, see the [Beta 1 offline workaround](#v010-beta1-offline-workaround) below.

---

## 1. Know Your Hardware: Radxa CM3 on CmRat

The **DTV Electronics CmRat** carrier board accepts Raspberry Pi CM4/CM5 modules *and* pin-compatible alternatives such as the **Radxa CM3**. Although the physical connectors match:

- **Radxa CM3 uses a Rockchip RK3566 SoC, not a Broadcom Raspberry Pi SoC.**
- **Do not use Raspberry Pi `rpiboot` or `config.txt` instructions** on a Radxa CM3. Low-level eMMC recovery on RK3566 uses Rockchip **Maskrom mode** (`rkdeveloptool` / `RKDevTool`), not `rpiboot`.
- **Do not use Raspberry Pi Imager's "OS Customisation"** dialog (username/password/SSH/Wi-Fi). This image ignores Raspberry Pi OS `firstrun.sh` / `userconf.txt` files and enforces offline key-only enrollment through `/etc/cm3-cli/owner.json`.

---

## 2. Deciding Where to Install: eMMC vs. microSD vs. CmRat NVMe Slot

The CmRat carrier exposes three possible storage locations when paired with a Radxa CM3. Choose based on how you plan to run the node:

| Medium | Supported as OS boot/root? | Can flash with Raspberry Pi Imager? | Automatic root expansion (`grow_os`) | Recommended Role |
| :--- | :--- | :--- | :--- | :--- |
| **microSD card** | **Yes** | **Yes** (direct via SD card reader) | **Yes** (`/dev/mmcblk*p3`) | Easiest first test, CM3 Lite (no eMMC) modules, and always keep one as a rescue disk |
| **Onboard eMMC** (Radxa CM3 eMMC variants) | **Yes** | **Yes** (when exposed as USB mass storage) or via `rkdeveloptool` | **Yes** (`/dev/mmcblk0p3`) | **Best OS target** for permanent headless CmRat deployments (faster and higher endurance than microSD) |
| **CmRat M.2 NVMe slot** (`/dev/nvme0n1`) | **No** (not in this beta) | Technically writable via USB-NVMe adapter, **but will not boot directly or pass `grow_os`** | **No** (intentionally rejected to protect data disks) | **Dedicated high-speed data drive** (containers, databases, node/blockchain data, logs) paired with OS on eMMC or microSD |

### Which should you pick?

1. **If you have a Radxa CM3 with onboard eMMC + an M.2 NVMe SSD in CmRat (recommended production-style layout):**
   - Put the **Debian 13 CLI OS on onboard eMMC** (the base OS is compact, ~1.9 GiB raw, and eMMC is fast and reliable).
   - Mount the **CmRat M.2 NVMe SSD as a dedicated data volume** (for example `/srv` or `/mnt/data`) *after* first boot completes.
   - This gives you clean OS/data separation: you can reflash or upgrade the OS on eMMC without touching your NVMe data.

2. **If you have a Radxa CM3 Lite (no eMMC) or want the quickest, non-destructive first test:**
   - Install the **OS on a sacrificial microSD card** using Raspberry Pi Imager.
   - If your CM3 *does* have onboard eMMC with an existing OS, remember that RK3566 BootROM checks `SPI Flash → eMMC → microSD` (while Radxa U-Boot on eMMC may still chainload microSD depending on what is flashed). Always verify which root device actually booted (`findmnt /`).

3. **Why you should NOT install this image directly onto the CmRat NVMe slot right now:**
   - **RK3566 BootROM limitation:** Unlike Raspberry Pi CM4/CM5 EEPROM boot, the Rockchip RK3566 BootROM **cannot boot directly from PCIe/NVMe**. Direct NVMe boot on RK3566 requires flashing a compatible NVMe-capable U-Boot into SPI NOR flash (or keeping `/boot` on eMMC/microSD), which is outside this beta.
   - **Intentional OS-growth safety guard:** `cm3-cli-grow-os.service` enforces that the running OS root is `/dev/mmcblk*p3` (`MMC` or `SD`) and explicitly refuses `/dev/nvme*` and `/dev/sd*` targets so attached data SSDs are never modified or resized by first-boot automation.
   - **What future direct NVMe boot would require:** Installing a verified NVMe-capable U-Boot to SPI flash (or hybrid eMMC boot + NVMe root) *and* extending `grow_os.py` with an opt-in NVMe layout contract. Until then, keep the OS on eMMC or microSD and use the NVMe slot for data.

> **Safety rule before flashing:** If an NVMe SSD with important data is already installed in your CmRat, disconnect it (or leave it unmounted and double-check the storage device name/capacity in Raspberry Pi Imager) before writing any OS image.

---

## 3. Download and Verify the Image

Download the release bundle from [GitHub Releases](https://github.com/blockdyor/radxa-cm3-debian-cli/releases) (canonical archive: `radxa-cm3_debian-13-trixie_arm64_cli_<version>.img.xz` plus `SHA256SUMS` and `RECOVERY-VERIFICATION.txt`).

Verify the download checksums before opening Raspberry Pi Imager:

```bash
# Linux
sha256sum -c SHA256SUMS
xz -t radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz
```

```bash
# macOS
shasum -a 256 -c SHA256SUMS
```

```powershell
# Windows PowerShell
Get-FileHash -Algorithm SHA256 .\radxa-cm3_debian-13-trixie_arm64_cli_v0.1.0-beta.1.img.xz
```

Also follow the attestation verification steps in [`docs/cm3-beta1.md#download-verification`](cm3-beta1.md#download-verification) (`RECOVERY-VERIFICATION.txt`).

---

## 4. Prepare the Target Medium & Flash with Raspberry Pi Imager

Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on Linux, macOS, or Windows. Raspberry Pi Imager can read `.img.xz` directly (no manual decompression needed) and verifies written blocks automatically.

### Path A — Installing to microSD (Direct with Raspberry Pi Imager)

1. Insert a sacrificial microSD card (8 GiB or larger recommended) into your host PC's card reader.
2. Open **Raspberry Pi Imager**:
   - **Raspberry Pi Device:** select **No filtering**.
   - **Operating System:** scroll to the bottom, choose **Use custom**, and select the verified `radxa-cm3_debian-13-trixie_arm64_cli_*.img.xz` file.
   - **Storage:** select your exact microSD card after verifying its brand, capacity, and device path.
3. Click **Next**.
4. **CRITICAL — When asked "Would you like to apply OS customisation settings?":**
   - Click **NO** (if you previously saved settings, click **Edit Settings → Clear** first, then choose **NO**).
   - *Why:* Raspberry Pi Imager customization writes Raspberry Pi OS scripts to the FAT partition (`userconf.txt` / `firstrun.sh`). This Debian 13 CM3 image ignores them and requires `/etc/cm3-cli/owner.json` on partition 3 instead.
5. Confirm the destructive write prompt, let Raspberry Pi Imager finish **Writing** and **Verifying**, and **do not insert the card into the CmRat yet** — proceed to [Section 5 (Offline Owner Provisioning)](#5-mandatory-offline-owner-provisioning).

### Path B — Installing to Onboard eMMC on CmRat

Because Radxa CM3 is Rockchip RK3566 (not Broadcom), **Raspberry Pi `rpiboot` will not expose the eMMC**. Choose one of the three Rockchip-compatible ways to reach the onboard eMMC:

#### B1. Expose eMMC as USB Mass Storage and flash with Raspberry Pi Imager
You can use Raspberry Pi Imager directly on eMMC whenever the eMMC is presented to your host PC as a standard USB block device:
- **Via a Radxa CM3 eMMC-to-USB adapter / carrier UMS:** Attach the CM3 eMMC module to a compatible USB eMMC adapter (or boot existing U-Boot over UART2 serial `1500000 8N1` and run `ums 0 mmc 0` with CmRat's USB-C port connected to your host PC).
- Once your host OS detects the eMMC block device, follow the exact same **Raspberry Pi Imager** steps in [Path A](#path-a--installing-to-microsd-direct-with-raspberry-pi-imager) (`No filtering` → `Use custom` → select the exact eMMC capacity → **NO OS customisation** → Write & Verify).
- After writing, provision `/etc/cm3-cli/owner.json` on partition 3 ([Section 5](#5-mandatory-offline-owner-provisioning)) before ejecting.

#### B2. Flash eMMC from a Rescue microSD Booted on the CmRat (No Maskrom Loader Needed)
If your CM3 boots a Linux rescue image from microSD on the CmRat:
1. Boot the rescue OS from microSD and confirm the onboard eMMC is visible and **unmounted** (verify with `lsblk -o NAME,SIZE,TYPE,TRAN,MOUNTPOINTS` — never guess whether `mmcblk0` or `mmcblk1` is eMMC vs. SD; check `cat /sys/class/block/mmcblk*/device/type` where `MMC` is eMMC and `SD` is microSD).
2. Copy the verified `.img.xz` to the rescue system and write it to the whole eMMC device:
   ```bash
   # Replace /dev/mmcblkX ONLY after verifying device/type == MMC and no mounted partitions!
   xz -dc radxa-cm3_debian-13-trixie_arm64_cli_*.img.xz | sudo dd of=/dev/mmcblkX bs=4M status=progress conv=fsync
   sudo sync
   ```
3. Re-read the partition table (`sudo partprobe /dev/mmcblkX`), mount partition 3 (`/dev/mmcblkXp3`), and complete [Section 5 (Offline Owner Provisioning)](#5-mandatory-offline-owner-provisioning) directly from the rescue OS.
4. Power off cleanly, remove the rescue microSD, and boot from eMMC.

#### B3. Direct Rockchip Maskrom Flashing over CmRat USB-C (`rkdeveloptool` / `RKDevTool`)
Use this if the eMMC is blank/unbootable and you do not have a rescue microSD:
1. **Power off** the CmRat completely and remove any microSD card. Disconnect production NVMe drives if attached.
2. On the **CmRat**, set the physical boot-mode switch to **`USBC`** (consult your exact CmRat revision documentation at [DTVElectronics/cmrat](https://github.com/DTVElectronics/cmrat) to verify switch orientation).
3. On the **Radxa CM3**, press and hold the module's **Maskrom / eMMC-disable** button, connect a USB-C data cable from the CmRat's USB-C port to your host PC, wait ~2 seconds, and release the button.
4. Verify the RK3566 appears in Maskrom mode (`lsusb` shows Rockchip ID `2207:350a`, or `rkdeveloptool ld` lists a `Maskrom` device).
5. Decompress the verified `.img.xz` to a raw `.img` file, verify its raw SHA-256 against `RAW-SHA256SUMS`, and flash using a vendor-verified RK3566 SPL loader:
   ```bash
   sudo rkdeveloptool ld
   sudo rkdeveloptool db /path/to/verified-rk356x_spl_loader.bin
   sudo rkdeveloptool wl 0 /path/to/radxa-cm3_debian-13-trixie_arm64_cli_*.img
   sudo rkdeveloptool rd
   ```
   Stop immediately if any command fails.
6. Flip the CmRat boot-mode switch back to **`OSBOOT`**.
7. **Remember:** Raw Maskrom flashing writes the image *without* `/etc/cm3-cli/owner.json`. Before expecting SSH access, you must still provision `/etc/cm3-cli/owner.json` on eMMC partition 3 (either by mounting partition 3 from a rescue microSD or by injecting `owner.json` into a verified local copy of the raw `.img` via `debugfs`/loop-mount on Linux *before* running `rkdeveloptool wl 0`).

### Path C — Using the CmRat M.2 NVMe Slot as Your Data Drive (Post-Install)

After you have booted Debian 13 CLI from **eMMC** or **microSD** and logged in via SSH ([Section 6](#6-first-boot-on-cmrat-and-verification)), attach/enable your M.2 2280 NVMe SSD in the CmRat slot and configure it as a persistent data disk.

> **Why use a systemd `.mount` unit instead of `/etc/fstab`?**
> `cm3-cli-grow-os.service` runs on every boot and strictly verifies that `/etc/fstab` contains only the three OS mounts (`/`, `/config`, `/boot/efi`). Mounting your NVMe data drive with a systemd `.mount` unit keeps `/etc/fstab` clean so `cm3-cli-grow-os.service` passes on every reboot while automatically mounting your NVMe SSD at `/srv`.

```bash
# 1. Confirm the NVMe device (typically /dev/nvme0n1) and verify it is empty or sacrificial
lsblk -o NAME,SIZE,TYPE,FSTYPE,MODEL,MOUNTPOINTS

# 2. Create a GPT partition table and single ext4 data partition (DESTROYS existing NVMe data!)
printf 'label: gpt\n,,L\n' | sudo sfdisk /dev/nvme0n1
sudo mkfs.ext4 -L cmrat-data /dev/nvme0n1p1

# 3. Create and enable a systemd mount unit by UUID at /srv
NVME_UUID=$(sudo blkid -s UUID -o value /dev/nvme0n1p1)
sudo mkdir -p /srv
sudo tee /etc/systemd/system/srv.mount >/dev/null <<EOF
[Unit]
Description=CmRat NVMe Data Volume
After=local-fs.target

[Mount]
What=/dev/disk/by-uuid/${NVME_UUID}
Where=/srv
Type=ext4
Options=defaults,noatime

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now srv.mount
df -h / /srv
```

---

## 5. Mandatory Offline Owner Provisioning

This image ships with **no default user, no password, and SSH closed by default**. Before first boot, you must create `/etc/cm3-cli/owner.json` on **partition 3** (`rootfs`, `ext4`) of the flashed eMMC or microSD card.

### 5.1 Generate an Ed25519 SSH keypair on your workstation (if you don't already have one)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cm3_ed25519 -C "cm3-cmrat-owner"
cat ~/.ssh/cm3_ed25519.pub
```

### 5.2 Create `owner.json`

Create a local file named `owner.json` with **exactly three fields** (`version`, `username`, `authorized_key`):

```json
{
  "version": 1,
  "username": "cm3admin",
  "authorized_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... cm3-cmrat-owner"
}
```

Rules enforced by `cm3-cli-enroll.service`:
- `version`: must be integer `1`.
- `username`: non-system lowercase name (1–31 chars, starts with `[a-z]`, only `[a-z0-9_-]`; `root` and system names are rejected).
- `authorized_key`: a single plain `ssh-ed25519` **public** key (no private keys, no passwords, no `authorized_keys` options).

### 5.3 Install `owner.json` onto Partition 3 (`ext4`)

Partition 3 is an **`ext4`** Linux filesystem:
- **On Linux (or WSL2 / Linux VM):** re-insert the flashed microSD (or mount the exposed eMMC), locate partition 3 (`lsblk -f`, look for the ~1.5 GiB `ext4` partition), and copy `owner.json` as `root:root` mode `0600`:
  ```bash
  # Replace /dev/sdX3 (or /dev/mmcblkXp3) with your actual partition 3!
  sudo mkdir -p /mnt/cm3-root
  sudo mount /dev/sdX3 /mnt/cm3-root
  sudo install -d -o root -g root -m 0755 /mnt/cm3-root/etc/cm3-cli
  sudo install -o root -g root -m 0600 ./owner.json /mnt/cm3-root/etc/cm3-cli/owner.json
  sudo ls -la /mnt/cm3-root/etc/cm3-cli/owner.json
  sudo sync
  sudo umount /mnt/cm3-root
  ```
- **On macOS / Windows without WSL2:** macOS and Windows do not natively mount `ext4` read-write. Use a lightweight Linux VM (e.g., UTM/Lima on macOS, WSL2 on Windows) or a Linux live USB / rescue session to mount partition 3 and run the exact commands above. Do **not** place `owner.json` on the FAT partitions (`/config` or `/boot/efi`) — the enroller only reads `/etc/cm3-cli/owner.json` from partition 3.

### `v0.1.0-beta.1` Offline Workaround

If you are specifically testing the already-published **`v0.1.0-beta.1`** image (before `v0.1.0-beta.2` is built with the `fix/cm3-first-boot-bugs` patches), while partition 3 is mounted at `/mnt/cm3-root` above, also apply these two offline fixes:

1. Create the empty 0-byte `/etc/machine-id` required by `systemd 257` on a `ro` root:
   ```bash
   sudo install -o root -g root -m 0444 /dev/null /mnt/cm3-root/etc/machine-id
   ```
2. Replace `/mnt/cm3-root/usr/lib/cm3-cli/grow_os.py` with the fixed version from branch `fix/cm3-first-boot-bugs` (`packages/cm3-cli-board-support/root/usr/lib/cm3-cli/grow_os.py`, which filters `autofs` and transient mounts and normalizes ext4 mount options).

Once `v0.1.0-beta.2` is released, this workaround will no longer be needed.

---

## 6. First Boot on CmRat and Verification

1. **Check CmRat hardware setup:**
   - Ensure the Radxa CM3 is firmly seated in the CmRat connectors with heatsink/thermal pad fitted.
   - Set the CmRat boot-mode switch to **`OSBOOT`**.
   - Insert your provisioned microSD card (if booting from SD).
   - Connect Gigabit Ethernet to a DHCP-enabled network.
   - *(Optional, strongly recommended for beta testing)* Attach a 3.3V USB-UART adapter to UART2 (`1500000 8N1`) so you can observe boot diagnostics.
   - Connect **one** power source (PoE, USB-C, or DC 12V — follow DTV Electronics' CmRat power guidance).

2. **What happens automatically on first boot:**
   1. `systemd` generates and commits a unique `/etc/machine-id`.
   2. `cm3-cli-grow-os.service` expands partition 3 (`ext4`) online to fill your eMMC or microSD card (without touching any NVMe/USB disks).
   3. `cm3-cli-firewall.service` loads the default-drop `nftables` table (`inet cm3_cli`, allowing SSH TCP/22, DHCP, ICMP/ICMPv6, loopback, and established traffic).
   4. `apparmor.service` loads AppArmor profiles (`capability,apparmor`).
   5. `cm3-cli-enroll.service` validates `/etc/cm3-cli/owner.json`, creates your password-locked owner account with passwordless `sudo`, generates fresh SSH host keys, and enables `ssh.service`.

3. **Log in over SSH and verify:**
   Find the board's DHCP IP address on your router (hostname `radxa-cm3-rpi-cm4-io`) and connect with your Ed25519 key:
   ```bash
   ssh -i ~/.ssh/cm3_ed25519 cm3admin@<cm3-ip-address>
   ```
   Run quick health checks once connected:
   ```bash
   uname -a
   findmnt /
   df -h /
   systemctl --failed
   sudo aa-status --enabled && echo "AppArmor active"
   sudo nft list table inet cm3_cli
   ```
   Expected results:
   - `uname -a` shows `6.1.84-18+cm3cli1-rk2410-nocsf aarch64`.
   - `findmnt /` shows `/dev/mmcblk0p3` (or `/dev/mmcblk1p3`) on `ext4`, expanded to full eMMC/SD capacity in `df -h /`.
   - `systemctl --failed` shows `0 loaded units listed`.
   - AppArmor is enabled and `inet cm3_cli` is active.

---

## 7. Troubleshooting

- **SSH refuses connections after first boot:**
  - Confirm `/etc/cm3-cli/owner.json` exists on **partition 3** (not `/config` or `/boot/efi`), is valid JSON matching the schema, and is owned by `root:root` with mode `0600`.
  - If running unmodified `v0.1.0-beta.1`, check the [Beta 1 offline workaround](#v010-beta1-offline-workaround) above.
  - Capture UART2 serial output (`1500000 8N1`) or mount partition 3 offline on Linux and inspect `journalctl --root=/mnt/cm3-root -u cm3-cli-grow-os -u cm3-cli-enroll`.
- **Inserted microSD did not boot (board booted old eMMC OS instead):**
  - Check `findmnt /` and `cat /sys/class/block/mmcblk*/device/type`. If old firmware on eMMC takes precedence, boot into a rescue environment or enter Maskrom mode to flash the onboard eMMC directly.
- **Need to change owner username or SSH key later:**
  - `cm3-cli-enroll.service` intentionally fails closed if `/etc/cm3-cli/owner.json` is altered after enrollment (protecting against silent key takeover). Manage additional keys or administrative changes after logging in as the enrolled owner, or perform a clean offline re-flash.
