#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
# CM3-only replacement for the pinned multi-board Rockchip setup helper.

require_payload() {
    local FILE SIZE
    for FILE in "$SCRIPT_DIR/idblock.img" "$SCRIPT_DIR/u-boot.itb"; do
        [[ -f "$FILE" && ! -L "$FILE" && -r "$FILE" && -s "$FILE" ]] || return 253
        SIZE=$(stat -c %s -- "$FILE") || return $?
        [[ "$SIZE" =~ ^[0-9]+$ && "$SIZE" -le 8355840 ]] || return 253
    done
}

require_mmc_target() {
    [[ -f "$SCRIPT_DIR/loader-target.py" && ! -L "$SCRIPT_DIR/loader-target.py" ]] || return 253
    python3 "$SCRIPT_DIR/loader-target.py" "${2:-os}" "${1:-}"
}

update_idblock() {
    require_mmc_target "${1:-}" "${2:-os}" || return $?
    require_payload || return $?
    dd conv=notrunc,fsync if="$SCRIPT_DIR/idblock.img" of="$1" bs=512 seek=64
}

update_bootloader() {
    require_mmc_target "${1:-}" "${2:-os}" || return $?
    require_payload || return $?
    update_idblock "$1" "${2:-os}" || return $?
    dd conv=notrunc,fsync if="$SCRIPT_DIR/u-boot.itb" of="$1" bs=512 seek=16384 || return $?
    sync "$1"
}

erase_bootloader() {
    require_mmc_target "${1:-}" "${2:-os}" || return $?
    dd conv=notrunc,fsync if=/dev/zero of="$1" bs=512 seek=64 count=16384 || return $?
    sync "$1"
}

update_image() {
    local IMAGE=${1:-} INFO SIZE
    [[ ${2:-} == 512 && -f "$IMAGE" && ! -L "$IMAGE" ]] || return 251
    INFO=$(stat -c '%h:%u' -- "$IMAGE") || return $?
    [[ "$INFO" == "1:$EUID" ]] || return 251
    SIZE=$(stat -c %s -- "$IMAGE") || return $?
    [[ "$SIZE" =~ ^[0-9]+$ && "$SIZE" -ge 16777216 ]] || return 251
    [[ -f "$SCRIPT_DIR/loader-target.py" && ! -L "$SCRIPT_DIR/loader-target.py" ]] || return 253
    python3 "$SCRIPT_DIR/loader-target.py" image "$IMAGE" || return $?
    require_payload || return $?
    dd conv=notrunc,fsync if="$SCRIPT_DIR/idblock.img" of="$IMAGE" bs=512 seek=64 || return $?
    dd conv=notrunc,fsync if="$SCRIPT_DIR/u-boot.itb" of="$IMAGE" bs=512 seek=16384 || return $?
    sync "$IMAGE"
}

maskrom() {
    require_payload || return $?
    [[ -f "$SCRIPT_DIR/rkboot.bin" && ! -L "$SCRIPT_DIR/rkboot.bin" && -r "$SCRIPT_DIR/rkboot.bin" && -s "$SCRIPT_DIR/rkboot.bin" ]] || return 253
    rkdeveloptool db "$SCRIPT_DIR/rkboot.bin"
}

maskrom_update_idblock() {
    require_payload || return $?
    rkdeveloptool wl 64 "$SCRIPT_DIR/idblock.img"
}

maskrom_update_bootloader() {
    require_payload || return $?
    maskrom_update_idblock || return $?
    rkdeveloptool wl 16384 "$SCRIPT_DIR/u-boot.itb"
}

maskrom_reset() {
    rkdeveloptool rd
}

maskrom_autoupdate_bootloader() {
    require_payload || return $?
    maskrom || return $?
    sleep 10 || return $?
    maskrom_update_bootloader || return $?
    maskrom_reset
}

# No SPI, UFS, automatic target discovery or unbounded dump/erase operations.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    set -euo pipefail
    SCRIPT_DIR=$(dirname "$(realpath "$0")")
    ACTION=${1:-}
    [[ $# -gt 0 ]] && shift
    case "$ACTION" in
        update_idblock|update_bootloader|erase_bootloader)
            [[ $# -eq 1 || ( $# -eq 2 && $2 == provisioning ) ]] || exit 252
            "$ACTION" "$@" ;;
        update_image)
            [[ $# -eq 2 ]] || exit 252
            "$ACTION" "$@" ;;
        maskrom_autoupdate_bootloader)
            [[ $# -eq 0 ]] || exit 252
            "$ACTION" ;;
        *) echo "Unsupported CM3 beta loader action." >&2; exit 252 ;;
    esac
fi
