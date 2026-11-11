#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
#
# Self-test for erhai-switch's decision and verification logic.
#
# What this covers: the parts that decide *whether* to write and *whether a
# write was good* -- image-set validation against SHA256SUMS, refusing to
# archive a Ubuntu slot as Android, the archive/install/read-back cycle, the
# rollback when a read-back does not match, dry-run writing nothing, and the
# state the store is left in.
#
# What this does NOT cover, and cannot: anything about the real device. The
# partitions here are ordinary files in a temporary directory (--dev-dir), so
# a pass says nothing about UFS behaviour, AVB footers, the bootloader, or
# whether the tablet boots afterwards. Those are device experiments.
#
# Needs root for the script's own check; re-execs itself in a user namespace
# when it is not (unshare -r), so it runs unprivileged in CI.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SWITCH=$here/../erhai-switch

if [ "$(id -u)" != 0 ]; then
	exec unshare -r "$0" "$@"
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
dev=$work/dev
store=$work/store
mkdir -p "$dev" "$store"
mkdir -p "$dev/power_supply/battery"
printf 'Battery\n' > "$dev/power_supply/battery/type"
printf '80\n' > "$dev/power_supply/battery/capacity"

pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$*"; }
no() { fail=$((fail + 1)); printf 'FAIL %s\n' "$*"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 (got '$2', want '$3')"; fi; }

switch() { "$SWITCH" --slot _a --store "$store" --dev-dir "$dev" "$@"; }

# A "partition" is a file of the real partition's size; a "boot image" is
# padded to it, because the switcher writes whole partitions.
BOOT_SIZE=$((2 * 1024 * 1024))
INIT_SIZE=$((1 * 1024 * 1024))
VENDOR_SIZE=$((2 * 1024 * 1024))

make_image() { # <file> <size> <first-bytes>
	dd if=/dev/zero of="$1" bs=1048576 count=$(($2 / 1048576)) 2>/dev/null
	printf '%s' "$3" | dd of="$1" conv=notrunc 2>/dev/null
}

make_set() { # <dir> <tag> <marker-or-empty>
	mkdir -p "$1"
	make_image "$1/boot.img" "$BOOT_SIZE" "ANDROID!$2 $3"
	make_image "$1/init_boot.img" "$INIT_SIZE" "ANDROID!$2-init"
	make_image "$1/vendor_boot.img" "$VENDOR_SIZE" "VNDRBOOT$2"
	(cd "$1" && sha256sum boot.img init_boot.img vendor_boot.img > SHA256SUMS)
}

sum() { sha256sum "$1" | cut -d' ' -f1; }

# --- the starting state: Android in the slot, a Ubuntu set in the store ----
make_set "$work/android-src" stock ''
for name in boot init_boot vendor_boot; do
	cp "$work/android-src/$name.img" "$dev/${name}_a"
done
make_set "$store/ubuntu" ubuntu 'erhai.boot=mainline-dev'
android_boot=$(sum "$dev/boot_a")
ubuntu_boot=$(sum "$store/ubuntu/boot.img")

# --- status / verify on a store with no archive yet ------------------------
out=$(switch status)
case $out in
*'installed now:    unknown'*) ok 'status: an un-archived Android slot reads as unknown' ;;
*) no "status: unexpected occupant line: $out" ;;
esac
case $out in
*'erhai marker in boot: no'*) ok 'status: no erhai marker in the stock slot' ;;
*) no 'status: marker misreported for the stock slot' ;;
esac

if switch verify >/dev/null 2>&1; then
	no 'verify: passed although there is no android/ archive'
else
	ok 'verify: fails while the android/ archive is missing'
fi

# --- refusing to switch without an archive ---------------------------------
if switch to-android --no-reboot >/dev/null 2>&1; then
	no 'to-android: accepted a missing archive'
else
	ok 'to-android: refuses when android/ is missing'
fi

# --- dry run writes nothing ------------------------------------------------
before=$(sum "$dev/boot_a")
switch to-ubuntu --dry-run > "$work/dryrun.log"
check 'dry-run: the slot is untouched' "$(sum "$dev/boot_a")" "$before"
if [ -d "$store/android" ]; then
	no 'dry-run: created an archive'
else
	ok 'dry-run: created no archive'
fi
if [ -f "$store/state.json" ]; then
	no 'dry-run: wrote state.json'
else
	ok 'dry-run: wrote no state.json'
fi

# --- archive, then install Ubuntu ------------------------------------------
switch stash-android > /dev/null
check 'stash: boot.img archived byte for byte' "$(sum "$store/android/boot.img")" "$android_boot"
if [ -f "$store/android/SHA256SUMS" ] && [ -f "$store/android/meta.json" ]; then
	ok 'stash: SHA256SUMS and meta.json written'
else
	no 'stash: archive metadata missing'
fi

switch to-ubuntu --no-reboot > "$work/to-ubuntu.log"
check 'to-ubuntu: the slot now holds the Ubuntu boot image' \
	"$(sum "$dev/boot_a")" "$ubuntu_boot"
check 'to-ubuntu: vendor_boot too' \
	"$(sum "$dev/vendor_boot_a")" "$(sum "$store/ubuntu/vendor_boot.img")"
check 'to-ubuntu: state.json records ubuntu' \
	"$(sed -n 's/.*"installed": *"\([^"]*\)".*/\1/p' "$store/state.json")" ubuntu
case $(switch status) in
*'installed now:    ubuntu'*) ok 'status: recognises the installed Ubuntu set' ;;
*) no 'status: did not recognise the installed Ubuntu set' ;;
esac

# --- the guard that protects the only way back -----------------------------
if switch stash-android >/dev/null 2>&1; then
	no 'stash: archived a Ubuntu slot as Android'
else
	ok 'stash: refuses to archive a Ubuntu slot as Android'
fi
check 'stash: the Android archive survived the refusal' \
	"$(sum "$store/android/boot.img")" "$android_boot"

# --- and back --------------------------------------------------------------
switch to-android --no-reboot > /dev/null
check 'to-android: the slot holds Android again' "$(sum "$dev/boot_a")" "$android_boot"
check 'to-android: state.json records android' \
	"$(sed -n 's/.*"installed": *"\([^"]*\)".*/\1/p' "$store/state.json")" android
switch verify > /dev/null && ok 'verify: passes once both sets exist' ||
	no 'verify: failed with both sets present'

# --- a store that does not match its own SHA256SUMS is refused -------------
printf 'tampered' | dd of="$store/ubuntu/boot.img" conv=notrunc 2>/dev/null
if switch to-ubuntu --no-reboot >/dev/null 2>&1; then
	no 'to-ubuntu: wrote an image that does not match SHA256SUMS'
else
	ok 'to-ubuntu: refuses an image that does not match SHA256SUMS'
fi
check 'to-ubuntu: the slot was left alone after the refusal' \
	"$(sum "$dev/boot_a")" "$android_boot"

# --- a read-back mismatch rolls back and does not reboot -------------------
# The slot is made read-only-ish by pointing the "partition" at a file the
# switcher can write but whose content it cannot keep: a FIFO would block, so
# instead the stored image is corrupted *after* SHA256SUMS is computed, which
# is exactly what a bad write looks like from the read-back's point of view.
make_set "$store/ubuntu" ubuntu 'erhai.boot=mainline-dev'
sed -i "s/^[0-9a-f]\{64\}  boot.img/$(printf '%064d' 0)  boot.img/" "$store/ubuntu/SHA256SUMS"
if switch to-ubuntu --no-reboot >/dev/null 2>&1; then
	no 'to-ubuntu: accepted a set whose SHA256SUMS is wrong'
else
	ok 'to-ubuntu: a wrong SHA256SUMS is caught before any write'
fi
check 'to-ubuntu: slot untouched by the bad set' "$(sum "$dev/boot_a")" "$android_boot"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" = 0 ]
