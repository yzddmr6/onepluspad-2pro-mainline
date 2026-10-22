# Building the kernel and device components

[中文](BUILD.zh-CN.md) · [Project overview](../README.md)

Build the kernel, device packages and Ubuntu root filesystem on a Linux host.
Use the project source revisions and original inputs recorded in the manifests.
Before using a resulting image, read the [installation and recovery notes](FLASHING.md).


## Host and source checkout

Use a Linux build host. Kernel builds need Git, Python 3, GNU make, a GNU
AArch64 cross compiler, binutils, bc, bison, flex, OpenSSL and ELF development
headers, and kmod. ccache is optional. Audio topology builds additionally need
m4 and alsa-utils; each graphics/sensor build has its own pinned dependencies.

The kernel checkout must contain the project commit recorded in
[`kernel/source.json`](../kernel/source.json). The `upstream` URL there identifies
Linux stable; it does not contain this tablet's patches. The device kernel is
maintained in [linux-sm8750-erhai](https://github.com/yzddmr6/linux-sm8750-erhai).
Place the matching checkout
at `kernel/linux` under this checkout, or set `ERHAI_WORKSPACE` to a workspace
containing `kernel/linux`. Do not substitute an unmodified upstream kernel.

Use Git checkouts so the build can record the source revisions:

```sh
git clone https://github.com/yzddmr6/onepluspad-2pro-mainline.git
cd onepluspad-2pro-mainline
git clone --filter=blob:none https://github.com/yzddmr6/linux-sm8750-erhai.git kernel/linux
kernel_commit=$(python3 -c 'import json; print(json.load(open("kernel/source.json"))["kernel"]["commit"])')
git -C kernel/linux checkout "$kernel_commit"
```

Kernel builds reject another commit by default. `ALLOW_UNPINNED_KERNEL=1` is an
explicit development override.

Run the commands below from the integration repository root. Python build tools
provide `--help`; shell tools use the environment variables shown below.

## Repository layout

```
tools/       build & packaging entry points (see below)
initramfs/   RAM userspace profiles (USB ACM console / NCM evidence channel)
switch/      dual-boot switcher and its KernelSU module (see switch/README.md)
packaging/   debian metadata for the device .deb set (see tools/build-debs.py),
             and firmware/ -- the device firmware closure it packs
kernel/      source.json pinning the kernel repo identity and tool inputs
```

Tools resolve their workspace automatically when this repo is checked out at
`<workspace>/public/onepluspad-2pro-mainline`; standalone checkouts work too
(`ERHAI_WORKSPACE` overrides). Build outputs land in `out/`. Assemble each
candidate from pinned original sources and that build's outputs; previous
release images and modified root trees are comparison data.

## Prepare inputs

Device firmware, stock boot build inputs and the small AOSP/AudioReach source
archives are included. Normal builds require neither a full stock ROM download
nor manual firmware extraction. Run:

```sh
python3 tools/prepare-inputs.py
```

The script verifies and unpacks the included inputs, downloads pinned Ubuntu
ARM64 BusyBox and reuses verified downloads. It requires Python 3.11+ and
dpkg-deb, and never accesses a tablet. Sources and hashes are recorded in
[kernel/source.json](../kernel/source.json), the
[firmware manifest](../packaging/firmware-manifest.json) and the
[stock input manifest](../packaging/boot-reference/source.json).

| Included | Downloaded separately when needed |
|---|---|
| Device firmware, stock boot build inputs, AOSP tool sources, AudioReach sources and device patches | Ubuntu Desktop, Ubuntu packages, the separate device kernel, Mesa and sensor-stack sources |

The included stock inputs match OPD2413 ColorOS C.34. They are build references,
not a general recovery package. Per-device calibration, addresses and Android
fallback backups must come from the user's own tablet during installation.
Ubuntu Desktop uses the original ISO layers described below; Ubuntu Base and
overlay-merging experiments are not the desktop delivery recipe.

## Build a RAM boot image

```sh
kernel_out="$PWD/out/kernel"
OUT_DIR="$kernel_out" tools/build-kernel.sh
PROFILE=ncm OUT_DIR="$PWD/out/initramfs" \
  GEN_INIT_CPIO="$kernel_out/usr/gen_init_cpio" tools/build-initramfs.sh
python3 tools/build-erhai-abl-symbols.py --output out/abl-dtb \
  --mainline-dtb "$kernel_out/arch/arm64/boot/dts/qcom/sm8750-erhai.dtb" \
  --dtc "$kernel_out/scripts/dtc/dtc" \
  --vendor-boot "${ERHAI_WORKSPACE:-$PWD}/cache/stock-c34/images/vendor_boot.img" \
  --dtbo-img "${ERHAI_WORKSPACE:-$PWD}/cache/stock-c34/images/dtbo.img"
python3 tools/build-mainline-boot.py --output out/mainline-boot \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz
```

`build-erhai-abl-symbols.py` builds the contained overlay sink layout by
default, the one daily deliveries use: the sink sits in a disabled container,
so rpmhpd, the NoCs and the PSCI power domains reach `sync_state()`.
It reads the original `cache/stock-c34/images/vendor_boot.img` and `dtbo.img`
directly; `--vendor-boot` and `--dtbo-img` select other pinned originals.
Base-tree index 6 supplies the identity for the recorded C.34 input; a different
stock layout needs an explicitly verified `--identity-index`. No previous OUT
tree is required. Extracted original trees remain an explicit alternative via
`--base-dir` and, if needed, `--identity-base`.
`--legacy-sink` is retained for developer comparisons. It prevents some
power-management initialization from completing and is not the normal build
choice. Boot and package builders require explicit opt-in for that layout
and record the selected layout in their manifests.

The NCM profile provides a USB link (device `192.168.77.2`, telnet 2323,
HTTP evidence on 8080) with a bounded recovery timer. Its recovery destination
depends on the installed boot images; the host controller must also verify the
return to Android. See [testing and recovery](FLASHING.md). Optional kernel cmdline flags: `erhai.watchdog=NN` (session length),
`erhai.rootfs=<url>` with `erhai.rootfs.sha256=<digest>` (fetch and verify a
squashfs over NCM before mounting its RAM overlay),
`erhai.switchroot=1` (hand PID1 to systemd with a matching expiry timer),
`erhai.weston=1` (autostart the pixman weston desktop).

For a RAM desktop test, add `--profile desktop --rootfs /path/to/desktop.squashfs
--rootfs-url http://192.168.77.10:8000/desktop.squashfs` to the boot-image
builder. Serve that exact file at the specified URL. The builder computes its
SHA-256 and records the URL and digest in both the boot command line and
manifest; it supplies no default root image. The initramfs refuses missing or
mismatched hashes and failed downloads, keeping diagnostics and the original
watchdog running. Whole-file and chunked HTTP/hash handling have been tested
with the pinned ARM64 BusyBox; this updated RAM desktop path has not yet been
booted on the tablet.

A setup image for first-time preparation also passes `--debug-package` with an
`erhai-debug` deb built alone (`tools/build-debs.py --only erhai-debug`). The
builder appends the deb to the ramdisk as a second archive, adds
`erhai.debug=1` and records the package in the manifest. Before handing over to
systemd, the initramfs installs it into the RAM overlay with the root's own
dpkg, so the published root filesystem and installed systems stay without it.

For a temporary kernel using an already installed root, use the persistent
profile with an explicit `erhai.session=90` (valid range 60–3600 seconds).
The initramfs places an expiry service only in the new root's `/run`; once
userspace starts, it returns the tablet to the bootloader after that bound.
Normal persistent boots omit this parameter and do not expire. The runtime
marker `/run/erhai-test-session.started` distinguishes a running userspace
watchdog from a boot that never reached the service.

## Device packages

The installed system is Canonical's Ubuntu, unpacked as it ships. The
functional device layer is packaged separately. The GNOME display-power adapter targets Settings Daemon 50; diagnostics are a separate optional package.

```sh
mkdir -p keys
# Generate once and retain for later builds.
test -f keys/boot.pem || openssl genpkey -algorithm RSA \
  -pkeyopt rsa_keygen_bits:4096 -out keys/boot.pem
python3 tools/build-debs.py --output out/device-packages \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz \
  --avb-key keys/boot.pem \
  --avbtool "${ERHAI_WORKSPACE:-$PWD}/cache/tools/avbtool.py"
```

| Package | Owns |
|---|---|
| `erhai-device-support` | `/usr/sbin/erhai-switch{,-install-ubuntu-images}`, the store directory and its logrotate snippet, the "Switch to Android" desktop entry and its polkit action, the power settings this port needs until suspend/resume works, and the two programs that give this unit its own Bluetooth and Wi-Fi addresses (`erhai-bt-address` with its units, `erhai-wifi-address` with its udev rule and NetworkManager drop-in), and the systemd hardware-watchdog policy: off by default, with an opt-in 30 s variant to copy into `/etc/systemd/system.conf.d/`. The addresses themselves live in `/var/lib/erhai/` and are in **no** package: they are machine-specific data, written on the tablet at first boot |
| `erhai-kernel` | selects a versioned kernel payload; configuration activates its triplet through the switcher without rebooting |
| `erhai-kernel-image-<release>` | matching signed boot images and configured modules; installation only populates files and runs `depmod`, allowing RAM validation before selection |
| `erhai-firmware` | the firmware closure the mainline drivers ask for and the distribution does not ship under those names |
| `erhai-audio` | the board AudioReach topology and UCM for the internal microphones; DisplayPort audio is disabled in the default profile, and internal speaker playback remains opt-in |
| `erhai-display-power` | the backlight power service, its socket and the GNOME 50 display-power adapter; it requires the kernel's single led-backlight device |
| `erhai-debug` (optional) | USB diagnostic DHCP, HTTP and root-shell units, using Ubuntu's `busybox-static`; all units require `erhai.debug=1` |
| `erhai-device` | a metapackage depending on the required device packages |

The kernel build includes all configured modules and records their hashes.
Its release suffix identifies the source, configuration and compiler so that
different builds use different module directories. Runtime modules are staged
with Kbuild's `modules_install`; the target's kmod generates dependency indices.
Build/source symlinks into a developer workspace are excluded.

Versioned payload packages coexist. The selector protects the running kernel
and the switcher's current/previous selections from automatic package removal;
unreferenced kernels can be removed normally. Immutable kernel identity is kept
in the store's `kernel.json`, separate from deployment information in `meta.json`.
Module autoload, SCMI CPU frequency, installed upgrade and booting the previous
unversioned kernel have been verified on hardware. Booting and returning between
two versioned module ABIs has also been verified. The actual installer and APT
parser pass isolated store-rotation tests. Removal of unreferenced project
payloads has also been tested on the installed system; this does not cover
third-party kernels or every future upgrade combination.

When installing a complete local deb set explicitly, mark the versioned payload
as an automatic dependency after verifying the selector. The selector's exact
dependency and the generated retention rules then retain selected kernels
without making every historical payload a permanent manual installation.

The build needs no root (`dpkg-deb --root-owner-group` on a staged tree) and
takes its firmware from `packaging/firmware/`, checking every file against the
sha256 and size recorded in `packaging/firmware-manifest.json` before packing
it — so `erhai-firmware` builds out of this checkout alone, with no ROM cache
and no network. `--refresh-from-rom` runs the other direction: it extracts the
closure from the pinned stock ROM images and upstream archives again and diffs
that against the tree, which is how a later ROM version gets in. Neither the
AVB signing key nor avbtool ever enters a package.

The `erhai-device` metapackage declares minimum compatible component versions,
rather than requiring every component to have an identical version. Audio, firmware and desktop
integration can therefore receive compatible updates without activating a new
kernel. The `erhai-kernel` selector still depends on the exact versioned payload
that contains matching images and modules. Each payload declares the firmware
minimum it actually consumes. Component-only builds also avoid reading a kernel
output or kernel checkout; their archive epoch comes from the integration source
or an explicit `SOURCE_DATE_EPOCH`. On development installations with an
older metapackage, update that metadata-only package first; inspect the APT plan
and reject any proposed kernel activation or removal for this step.

Building `erhai-audio` also requires GNU m4, `alsatplg` from alsa-utils, and the
original archive pinned in `packaging/audio/source.json`. Pass its path with
`--audio-source`; the default is `cache/audioreach-topology-993a17dc.tar.gz` in
the workspace. The builder verifies the archive, compiles the board source and
decodes the result as a format check. Local topology helpers under `packaging/audio/`
are tracked with the board recipe. Tool versions, hashes, source identity
and the upstream BSD license are included in the audio package. No prebuilt
reference-board topology is renamed or used as a build input.

Two builds of the same inputs produce the same bytes: the version carries a
build id derived from payload and package metadata (`<release>[~dbg]+g<kernel>.b<id>`), the AVB footers
use a salt derived from the image instead of avbtool's random default, and the
archive timestamps are pinned to the kernel commit for kernel builds and to
the integration commit for standalone component builds.

Device support and display power can be updated independently while respecting
their declared interface dependencies. The display package also constrains
the GNOME major ABI. The kernel selector
continues to require the exact matching image/module package.

`--debug` includes `erhai.debug=1` in the triplet, builds `erhai-debug` alongside
the device set and marks the version `~dbg`. The normal build omits the optional
package and the flag. The metapackage does not require diagnostics. An explicit
debug handoff needs `erhai-debug` in the root or, for a RAM desktop, carried by
its boot image as described above; the initramfs itself never copies binaries
or creates persistent diagnostic units in a root.

`erhai-device-support` retires recognized, unowned files generated by earlier
initramfs versions on both normal and debug upgrades. Originals remain under
`/var/lib/erhai/debug/legacy/`; package removal does not reactivate them. An
already enabled diagnostic channel keeps its enabled link during migration.
Unknown edited files are preserved and cause the migration to stop for review.
The revised migration is still awaiting final installed-device validation.

## Graphics packages

The optional `erhai-mesa` deb supplies the native desktop driver. Core24 Snap
applications need a separate `gpu-2404` content provider, built against their
own runtime ABI. Both use the same pinned Mesa source and A830v1 patch.
Build, installation and rollback instructions are in [GRAPHICS.md](GRAPHICS.md).
Hardware drawing, application behavior and physical display output have separate
acceptance requirements; development candidates are not validated releases.

## Desktop root filesystem

With 7z installed, download the pinned official Ubuntu Desktop ISO and extract
its two original layers automatically:

```sh
python3 tools/prepare-inputs.py --desktop
```

The layers are placed in `${ERHAI_WORKSPACE:-$PWD}/cache/ubuntu-desktop/casper/`.
Existing original layers can also be passed directly to the assembler; their
hashes must match `packaging/desktop/source.json`.

`tools/build-desktop-rootfs.py` assembles the two original Desktop layers and
explicit device packages. It requires rootful Docker on amd64, an existing
ARM64 binfmt interpreter, Python 3.11+ and `dpkg-dev`. Pull the assembly image
pinned in `packaging/desktop/source.json` first; the builder downloads and
verifies the locked native tools and Ubuntu runtime dependencies itself.

The desktop needs the Mesa package for hardware rendering and the sensor
package for sensor integration. Build both, then assemble them with the device
packages created above. Keep one selected version per component in these output
directories. Both component builders use unprivileged `unshare`, so the host
must permit user namespaces and provide ARM64 binfmt. `--native-nir` also needs
Mako and MarkupSafe in the host Python (`python3-mako` and
`python3-markupsafe` on Ubuntu). These builds run outside the assembly Docker
container. The following example uses Bash.

```sh
python3 tools/build-mesa-root.py --output out/mesa-debs --jobs 6 --native-nir
python3 tools/build-sensors.py --output out/sensor-debs

args=()
for deb in out/device-packages/*.deb out/mesa-debs/*.deb out/sensor-debs/*.deb; do
  args+=(--device-deb "$deb")
done
python3 tools/build-desktop-rootfs.py --layers "${ERHAI_WORKSPACE:-$PWD}/cache/ubuntu-desktop/casper" \
  --output out/desktop-root "${args[@]}"
```

Select one version of each desired device component, including the matching
kernel selector and payload. The container has no network and uses kernel
OverlayFS to apply the original layers, including whiteouts. Its additional
SYS_ADMIN capability and container-only unconfined AppArmor setting permit
trusted attributes and the overlay mount; target package processes drop that
added capability. Package installation uses a temporary local APT source and
service-start policy. The target's normal Ubuntu APT sources remain intact.

The lock also pins Mozilla's Firefox deb by URL and SHA-256. The assembly
requests that exact version, which replaces Ubuntu's transitional `firefox`
package; `erhai-firefox` from the device packages configures Mozilla's APT
repository for later updates. When Mozilla no longer serves the pinned build,
pin a current one.

The output includes `rootfs.squashfs`, the selected package list and build inputs. Machine identifiers, radio addresses, sensor
calibration and the Android rollback set must be supplied on installation.
Use the [installation guide](FLASHING.md) for the supported layout and device
checks. Building alone does not verify hardware support. Local commands and build logs stay
separate from the image and its portable input manifest.

## Existing dual-boot installations

The switcher uses the established active-slot layout and replaces the three
boot images as a set. It is intended for existing installations with matching
partition layouts and complete rollback images; see [testing and recovery](FLASHING.md).
Every image written into `boot`/`init_boot`/`vendor_boot` must carry an AVB
hash footer (`tools/sign-boot-triplet.py`), self-signed included — `vbmeta`
lists `boot` as a chain partition, so a missing footer is malformed metadata
that even an unlocked bootloader refuses. See [the switcher reference](../switch/README.md).
