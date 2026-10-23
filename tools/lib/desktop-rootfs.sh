#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Runs only inside the pinned assembly container; /work is a new build output.
set -euo pipefail
jobs=$1
shift
export LC_ALL=C.UTF-8 DEBIAN_FRONTEND=noninteractive
root=/work/root

# Apply the ISO layers through OverlayFS, including whiteouts. The writable
# layer contains only this build's package installation; no previous root is used.
mounted=0
proc_mounted=0
policy_installed=0
target() {
    setpriv --bounding-set=-sys_admin chroot "$root" "$@"
}
cleanup_policy() {
    policy_installed=0
    rm -f "$root/usr/sbin/policy-rc.d"
    target dpkg-divert --local --remove --rename \
        --divert /usr/sbin/policy-rc.d.erhai-build /usr/sbin/policy-rc.d
}
cleanup() {
    status=$?
    if [ "$policy_installed" = 1 ]; then cleanup_policy || status=1; fi
    if [ "$proc_mounted" = 1 ]; then umount -R "$root/proc" || status=1; fi
    if [ "$mounted" = 1 ]; then umount "$root" || status=1; fi
    if [ "$status" = 0 ]; then
        rm -rf /work/minimal /work/standard /work/changes /work/overlay-work "$root"
    fi
    exit "$status"
}
trap cleanup EXIT

# SYS_ADMIN is needed here for original trusted xattrs and the private overlay
# mount. Target package scripts drop that added capability via target().
dpkg -i /work/native/*.deb
unsquashfs -no-progress -processors "$jobs" -d /work/minimal /layers/minimal.squashfs
unsquashfs -no-progress -processors "$jobs" -d /work/standard /layers/minimal.standard.squashfs
mkdir -p "$root" /work/changes /work/overlay-work
mount -t overlay overlay \
    -o lowerdir=/work/standard:/work/minimal,upperdir=/work/changes,workdir=/work/overlay-work "$root"
mounted=1
# Reuse only this container's PID namespace and its existing proc restrictions.
# No host /dev or /sys is exposed to the package scripts.
mount --rbind /proc "$root/proc"
proc_mounted=1
test ! -d "$root/run/systemd/system"

build=$root/.erhai-build
mkdir -p "$build/repo" "$build/lists/partial" "$build/archives/partial" "$build/sourceparts"
cp --reflink=auto /work/repo/* "$build/repo/"
printf 'deb [trusted=yes] file:/.erhai-build/repo ./\n' > "$build/sources.list"
apt_options=(-o Dir::Etc::sourcelist=/.erhai-build/sources.list
             -o Dir::Etc::sourceparts=/.erhai-build/sourceparts
             -o Dir::State::lists=/.erhai-build/lists
             -o Dir::Cache::archives=/.erhai-build/archives)

# The target chroot has no booted systemd and no host /dev or /sys bindings.
# Keep standard package configuration, but inhibit starting services while assembling.
target dpkg-divert --local --add --rename \
    --divert /usr/sbin/policy-rc.d.erhai-build /usr/sbin/policy-rc.d
policy_installed=1
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
target apt-get "${apt_options[@]}" update
# Mozilla's firefox, requested by exact version, replaces Ubuntu's
# transitional firefox, whose version epoch sorts higher, so apt counts it as
# a downgrade. Apt never selects a lower version that was not requested.
target apt-get "${apt_options[@]}" --no-install-recommends --assume-yes \
    --allow-downgrades install "$@"
cleanup_policy
rm -rf "$build"
# The ISO lists its own medium as a package source. An installed system has no
# /cdrom, so apt update would fail on it; the Ubuntu archive sources stay.
rm -f "$root/etc/apt/sources.list.d/cdrom.sources"

target dpkg --audit > /work/audit.txt
test ! -s /work/audit.txt
target dpkg-divert --list > /work/diversions.txt
target dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\t${Status}\n' \
    > /work/rootfs-packages.txt

# Per-unit state belongs to installation or first boot, never a generic image.
for path in var/lib/erhai/bt-address var/lib/erhai/wifi-address \
            var/lib/erhai/sensors/persist/registry var/lib/erhai/switch/android \
            var/lib/erhai/switch/state.json; do
    if [ -e "$root/$path" ]; then
        echo "Unexpected machine state in root: $path" >&2
        exit 1
    fi
done
if [ -s "$root/etc/machine-id" ] && [ "$(cat "$root/etc/machine-id")" != uninitialized ]; then
    echo 'Unexpected initialized machine-id in root' >&2
    exit 1
fi

# Runtime mounts must not become part of the filesystem or its manifests.
umount -R "$root/proc"
proc_mounted=0

mksquashfs "$root" /work/rootfs.squashfs -noappend -comp zstd -processors "$jobs" -no-progress
