#!/bin/sh
# Invoked only inside the existing disposable, pinned x86_64 builder container.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends python3 ca-certificates apt-utils gnupg gpgv mmdebstrap arch-test debian-archive-keyring mount git gcc make gcc-aarch64-linux-gnu gh binutils libc6-dev openssh-client
git config --global --add safe.directory /src
python3 /src/scripts/cm3-bootstrap-tools.py
command -v jsonnet
arch-test arm64
if [ "$EXPERIMENTAL_IMAGE" = true ]; then
    # Qualify the actual software appliance before any expensive compilation.
    apt-get install -y --no-install-recommends libguestfs-tools python3-guestfs linux-image-amd64 qemu-system-x86 gdisk xz-utils
    export LIBGUESTFS_BACKEND=direct LIBGUESTFS_BACKEND_SETTINGS=force_tcg
    python3 /src/scripts/cm3-image-stage-a.py sonar
    timeout 300 libguestfs-test-tool
fi
python3 /src/scripts/cm3-image-stage-a.py tests
python3 /src/scripts/cm3-source-preflight.py --workdir /work
cp /checks/evidence/image-offline-tests.json /checks/evidence/image-offline-tests.log /work/evidence/
mkdir /work/board-debs
cp /src/preflight-work/board-input/cm3-cli-board-support_0.1.0_all.deb /work/board-debs/
cp /src/preflight-work/board-manifest.json /work/evidence/
python3 /src/scripts/cm3-package-preflight.py --workdir /work
exec python3 /src/scripts/cm3-rsdk-profile.py --workdir /work
