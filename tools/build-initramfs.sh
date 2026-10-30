#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
umask 022
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
# Workspace layout: when this repo is checked out at <workspace>/public/<name>,
# shared inputs and build outputs live in the workspace root; standalone
# checkouts keep everything inside the repo. ERHAI_WORKSPACE overrides both.
if [[ -f $repo/../../AGENTS.md && -d $repo/../../kernel/linux ]]; then
	ws=${ERHAI_WORKSPACE:-$(cd -- "$repo/../.." && pwd)}
else
	ws=${ERHAI_WORKSPACE:-$repo}
fi
busybox=${BUSYBOX:-"$ws/cache/busybox-arm64"}
out=${OUT_DIR:-"$ws/out/initramfs-dev"}
gen_init_cpio=${GEN_INIT_CPIO:-"$ws/out/kernel-firstboot/usr/gen_init_cpio"}
expected=52151e7f322f926b64049cdaa1410dc3ea6485525e0624b05813791c219ae933
[[ $(sha256sum "$busybox" | cut -d' ' -f1) == "$expected" ]] || {
	echo 'Expected the pinned Ubuntu ARM64 static BusyBox; see README.md (inputs).' >&2
	exit 1
}
[[ -x $gen_init_cpio ]] || {
	echo "gen_init_cpio not found at $gen_init_cpio (plain cpio cannot create device nodes)." >&2
	exit 1
}
mkdir -p "$out"
out=$(realpath "$out")
profile=${PROFILE:-acm}
case "$profile" in
acm) init_src="$repo/initramfs/init"; usb_src="$repo/initramfs/usb-acm"
	apps='sh mount mkdir cat uname sleep setsid cttyhack getty ln ls dmesg poweroff reboot'
	image_name=initramfs.cpio.gz ;;
ncm) init_src="$repo/initramfs/init-ncm"; usb_src="$repo/initramfs/usb-ncm"
	apps='sh mount mkdir cat cp uname sleep ip ln touch chmod sed udhcpd httpd telnetd dmesg reboot poweroff ls dd sha256sum sync tr date mv fdisk readlink timeout devmem awk od grep'
	ncm_helper="$repo/packaging/erhai-debug/tree/usr/libexec/erhai-ncm"
	ncm_config="$repo/packaging/erhai-debug/tree/usr/lib/erhai/debug/udhcpd.conf"
	image_name=initramfs-ncm.cpio.gz
	# DRM writeback diagnostic (erhai.wb=1): statically linked against the
	# workspace kernel uapi headers. Skipped in standalone checkouts that
	# have no kernel tree; WB_CAPTURE=on makes it a hard requirement.
	wb_src="$repo/tools/wb-capture.c"
	wb_inc="$ws/kernel/linux"
	if [[ -f $wb_src && -d $wb_inc/include/uapi/drm ]]; then
		wb_bin="$out/wb-capture"
		"${CROSS_COMPILE:-aarch64-linux-gnu-}"gcc -static -O2 -Wall -Wextra \
			-I"$wb_inc/include/uapi" -I"$wb_inc/arch/arm64/include/uapi" \
			-o "$wb_bin" "$wb_src"
		extra_bins="$wb_bin"
	elif [[ ${WB_CAPTURE:-auto} == on ]]; then
		echo "wb-capture requested but kernel uapi headers not found at $wb_inc" >&2
		exit 1
	else
		echo "note: kernel uapi headers not found; building without wb-capture" >&2
	fi
	# Novatek NT36536 TDDI loses its RAM firmware on every panel prepare; the
	# built-in touch driver requests it from the rootfs.
	firmware="$repo/packaging/firmware"
	# The initramfs and installed firmware package use the same original
	# inputs. Never chain a new boot image from a previous OUT's blobs.
	python3 - "$repo" <<'PY'
import hashlib, json, pathlib, sys
repo = pathlib.Path(sys.argv[1])
manifest = json.loads((repo / 'packaging/firmware-manifest.json').read_text())
for entry in manifest['files']:
    path = repo / 'packaging/firmware' / entry['install']
    data = path.read_bytes()
    if len(data) != entry['size'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise SystemExit(f'Firmware does not match manifest: {entry["install"]}')
PY
	identity_src="$repo/packaging/erhai-device-support/tree/usr/libexec/erhai-physical-platform"
	extra_bins="${extra_bins:-} $identity_src"
	fw_files="$firmware/novatek/nt36536-xn242.bin"
	# ADSP PIL firmware: mdt container + sparsely numbered adsp.bNN segments,
	# resolved by the loader next to firmware-name qcom/sm8750/erhai/adsp.mdt.
	adsp_src="$firmware/qcom/sm8750/erhai"
	adsp_dst=/lib/firmware/qcom/sm8750/erhai
	# Adreno 830 firmware: SQE/GMU/AQE (linux-firmware) by catalog name. The
	# GPU probes about 2 s into boot, before the root is mounted, so both zap
	# shaders the DT firmware-name may select ride along: the linux-firmware
	# one (test-signed) and the vendor-signed erhai/ one this unit's TZ takes.
	gpu_src="$firmware/qcom"
	# WCN7860 (ath12k) firmware; not in upstream linux-firmware, sourced from
	# the ROCKNIX extra-firmware pack (Odin 3 set, same chip family).
	wifi_src="$firmware/ath12k/WCN7860/hw2.0"
	bt_src="$firmware/qca" ;;
*) echo "Unknown PROFILE '$profile' (acm|ncm)." >&2; exit 1 ;;
esac
exec 9>"$out/.build.lock"
flock -n 9 || { echo 'Initramfs output is already in use.' >&2; exit 1; }
stage=$(mktemp -d "$out/stage.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
{
	sha256sum "$init_src" "$usb_src" | cut -d' ' -f1
	[[ -z ${extra_bins:-} ]] || sha256sum "$wb_src" | cut -d' ' -f1
	[[ -z ${identity_src:-} ]] || sha256sum "$identity_src" | cut -d' ' -f1
	[[ -z ${ncm_helper:-} ]] || sha256sum "$ncm_helper" "$ncm_config" | cut -d' ' -f1
	printf '%s\n' "$expected"
} | sha256sum | cut -d' ' -f1 >"$stage/build-id"
{
	for d in / /bin /dev /proc /sys /run /etc; do
		printf 'dir %s 0755 0 0\n' "$d"
	done
	# /dev must not be empty at PID1: devtmpfs automount timing is not a contract.
	printf 'nod /dev/console 0600 0 0 c 5 1\n'
	printf 'nod /dev/null 0666 0 0 c 1 3\n'
	printf 'file /init %s 0755 0 0\n' "$init_src"
	printf 'file /bin/%s %s 0755 0 0\n' "$(basename -- "$usb_src")" "$usb_src"
	printf 'file /bin/busybox %s 0755 0 0\n' "$busybox"
	for b in ${extra_bins:-}; do
		printf 'file /bin/%s %s 0755 0 0\n' "$(basename -- "$b")" "$b"
	done
	printf 'file /etc/build-id %s 0644 0 0\n' "$stage/build-id"
	if [[ -n ${ncm_helper:-} ]]; then
		for d in /usr /usr/libexec /usr/lib /usr/lib/erhai /usr/lib/erhai/debug; do
			printf 'dir %s 0755 0 0\n' "$d"
		done
		printf 'file /usr/libexec/erhai-ncm %s 0755 0 0\n' "$ncm_helper"
		printf 'file /usr/lib/erhai/debug/udhcpd.conf %s 0644 0 0\n' "$ncm_config"
	fi
	if [[ -n ${fw_files:-} ]]; then
		printf 'dir /lib 0755 0 0\n'
		printf 'dir /lib/firmware 0755 0 0\n'
		printf 'dir /lib/firmware/novatek 0755 0 0\n'
	fi
	for fw in ${fw_files:-}; do
		[[ -f $fw ]] || { echo "Firmware blob not found: $fw" >&2; exit 1; }
		printf 'file /lib/firmware/novatek/%s %s 0644 0 0\n' "$(basename -- "$fw")" "$fw"
	done
	if [[ -n ${gpu_src:-} ]]; then
		for f in gen80000_sqe.fw gen80000_gmu.bin gen80000_aqe.fw sm8750/gen80000_zap.mbn \
			sm8750/erhai/gen80000_zap.mbn; do
			[[ -f $gpu_src/$f ]] || { echo "GPU firmware not found: $gpu_src/$f" >&2; exit 1; }
		done
		printf 'dir /lib 0755 0 0\n'
		printf 'dir /lib/firmware 0755 0 0\n'
		printf 'dir /lib/firmware/qcom 0755 0 0\n'
		printf 'dir /lib/firmware/qcom/sm8750 0755 0 0\n'
		printf 'dir /lib/firmware/qcom/sm8750/erhai 0755 0 0\n'
		for f in gen80000_sqe.fw gen80000_gmu.bin gen80000_aqe.fw sm8750/gen80000_zap.mbn \
			sm8750/erhai/gen80000_zap.mbn; do
			printf 'file /lib/firmware/qcom/%s %s 0644 0 0\n' "$f" "$gpu_src/$f"
		done
	fi
	if [[ -n ${wifi_src:-} ]]; then
		for f in amss.bin m3.bin board-2.bin regdb.bin qdss.cfg aux_ucode.bin bdwlan.elf; do
			[[ -f $wifi_src/$f ]] || { echo "WLAN firmware not found: $wifi_src/$f" >&2; exit 1; }
		done
		for d in /lib /lib/firmware /lib/firmware/ath12k /lib/firmware/ath12k/WCN7860 /lib/firmware/ath12k/WCN7860/hw2.0; do
			printf 'dir %s 0755 0 0\n' "$d"
		done
		for f in amss.bin m3.bin board-2.bin regdb.bin qdss.cfg aux_ucode.bin bdwlan.elf; do
			printf 'file /lib/firmware/ath12k/WCN7860/hw2.0/%s %s 0644 0 0\n' "$f" "$wifi_src/$f"
		done
		# WCN7860 Bluetooth firmware (hci_qca loads qca/gngbtfwXX.mbn + gngbtnvXX.bin)
		for f in gngbtfw20.mbn gngbtnv20.bin; do
			[[ -f $bt_src/$f ]] || { echo "BT firmware not found: $bt_src/$f" >&2; exit 1; }
		done
		printf 'dir /lib/firmware/qca 0755 0 0\n'
		for f in gngbtfw20.mbn gngbtnv20.bin; do
			printf 'file /lib/firmware/qca/%s %s 0644 0 0\n' "$f" "$bt_src/$f"
		done
	fi
	if [[ -n ${adsp_src:-} ]]; then
		[[ -f $adsp_src/adsp.mdt ]] || { echo "ADSP mdt not found: $adsp_src/adsp.mdt" >&2; exit 1; }
		for d in /lib/firmware/qcom /lib/firmware/qcom/sm8750 "$adsp_dst"; do
			printf 'dir %s 0755 0 0\n' "$d"
		done
		for seg in "$adsp_src"/adsp.mdt "$adsp_src"/adsp.b* \
			"$adsp_src"/adsp_dtb.mdt "$adsp_src"/adsp_dtb.b*; do
			[[ -f $seg ]] || continue
			printf 'file %s/%s %s 0644 0 0\n' "$adsp_dst" "$(basename -- "$seg")" "$seg"
		done
		# The SoCCP starts early through PAS so that it can drop the boot bus
		# vote it inherits from the bootloader; that happens before the root
		# is mounted.
		[[ -f $adsp_src/soccp.mbn ]] || { echo "SoCCP firmware not found: $adsp_src/soccp.mbn" >&2; exit 1; }
		printf 'file %s/soccp.mbn %s 0644 0 0\n' "$adsp_dst" "$adsp_src/soccp.mbn"
	fi
	for app in $apps; do
		printf 'slink /bin/%s busybox 0777 0 0\n' "$app"
	done
} >"$stage/cpio.list"
"$gen_init_cpio" -t 0 "$stage/cpio.list" 2>"$out/cpio.log" | gzip -n >"$out/$image_name"
sha256sum "$out/$image_name" >"$out/$image_name.sha256"
echo "Built $out/$image_name (profile $profile, RAM userspace only, no boot image)"
