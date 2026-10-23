# Testing, Installation and Recovery

[中文](FLASHING.zh-CN.md) · [Project overview](../README.md)

This guide covers first-time partition preparation, Linux installation, system
switching and Android boot recovery. The device scope and validation status of
first-time preparation and reinstallation are stated separately below.

## Device scope

Testing uses a bootloader-unlocked OnePlus Pad 2 Pro (OPD2413 / erhai), with
16 GB RAM and 512 GB storage. Its existing installation has a separate Linux root
partition and rotates Android/Ubuntu `boot`, `init_boot` and `vendor_boot` images
through the active slot. Other capacities, firmware, layouts and Pad 3 are untested.

## RAM testing

A temporary RAM boot does not replace boot partitions. A temporary kernel using
an installed root can still write files and journals: this differs from a session
whose root filesystem is entirely in RAM.

The development RAM desktop has passed boot, graphics-driver and bounded
recovery checks. There is no one-command trial for new users. Developer testing requires matching
boot images, a root filesystem and checksums, with recovery after the session
timeout established in advance. Do not combine artifacts from unrelated builds.

Development sessions need explicit device selection, bounded timeouts and
userspace recovery. Panic/userspace timers cannot recover every hardware lockup.
Unauthenticated USB diagnostics are for trusted direct connections only.

## Return to Android on an existing installation

These steps require the established project layout and complete switcher storage.

- In Ubuntu, use **Switch to Android**, enter the administrator password and wait
  for the automatic reboot.
- In Android, use the installed KernelSU switching module; see the
  [switcher reference](../switch/README.md) for its installation and path conventions.
- If battery charge falls in Linux or Fastboot, return to Android to charge and
  confirm that capacity has recovered before continuing.

Both switching directions have been tested on the existing layout. Switching
writes three boot partitions; it does not apply to a fresh tablet, missing
rollback images or a different layout.

The switcher stops on a failed write, without automatically rebooting or
rolling back. An interruption marker prevents replacing the Android backup. Keep the complete Android triplet
backup on the host and use the Fastboot recovery procedure below after an interruption.

## Prebuilt release images

Releases from v0.2.1 attach the images this guide otherwise builds. The
installation still runs `tools/install.py` from this repository's checkout with
the host tools listed below, but no kernel, Mesa or root filesystem build is needed.
From v0.3.0, one root filesystem serves both first-time preparation and
installation.

| Asset | Use |
|---|---|
| `ubuntu-pad2pro-VERSION-rootfs.squashfs.part*` and `…-rootfs.manifest.json` | Root filesystem to install, without USB diagnostics; first-time preparation also runs it as the temporary RAM desktop |
| `ubuntu-pad2pro-VERSION-setup-boot.img` and `…-setup-boot.manifest.json` | Boot image of that temporary RAM desktop; it loads the root filesystem from the host and adds the USB diagnostic channel to that session only |
| `erhai-device-packages-VERSION.tar` | Packages for upgrading an existing installation, without USB diagnostics: the device packages built by `tools/build-debs.py` (kernel, firmware, audio, display power, device support, Firefox repository and the `erhai-device` metapackage), `erhai-mesa` and `erhai-sensors` |
| `erhai-switch-VERSION.zip` | Android switch module |
| `SHA256SUMS` | Checksums of every asset and of the joined image |

Join and check the image in the download directory (shown for v0.3.0):

```sh
cat ubuntu-pad2pro-v0.3.0-rootfs.squashfs.part* > ubuntu-pad2pro-v0.3.0-rootfs.squashfs
sha256sum --check --ignore-missing SHA256SUMS
```

Then use it in place of the build outputs named below. In this checkout, save
the joined image as `out/desktop-root/rootfs.squashfs` and its manifest as
`out/desktop-root/manifest.json`. First-time preparation serves that file to the
tablet and boots `ubuntu-pad2pro-v0.3.0-setup-boot.img` instead of
`out/ram-desktop/boot-mainline.img`; installation passes the same file to
`--rootfs`. For an upgrade, unpack `erhai-device-packages-v0.3.0.tar` and install
its packages as described in
[Upgrading an existing installation](#upgrading-an-existing-installation).

## Preparing Linux partitions for the first time

This step is for a **512 GB OPD2413 with its stock partition layout**, an unlocked
bootloader, working KernelSU root and USB debugging. **Slot A must be active**,
and firmware must match [the tested combination](../packaging/installation.json).
The `check-device` command below checks these before entering the RAM desktop. **First-time partition preparation erases Android apps,
accounts and files. Back up personal data to the host first.** Skip this section
if `linux_rootfs` and `linux_data` already exist.

Partition creation and Android data erasure have been tested on the device
specified above. The allocation is 200 GiB Android, 60 GiB Linux root and the
remaining space for Linux home. It leaves the active slot, stock boot images
and other UFS partitions unchanged.

Follow the [build guide](BUILD.md) to assemble `out/desktop-root/rootfs.squashfs`;
the installation below uses the same file. Preparation runs it as a temporary
RAM desktop. The boot image of that desktop carries the separately built
`erhai-debug` package and installs it in RAM for the USB diagnostic channel;
the root filesystem itself stays without it. With the build guide's
`kernel_out`, DTB and initramfs, create the package, the bounded RAM image and
the Android switch module:

```sh
python3 tools/build-debs.py --only erhai-debug --output out/debug-package
python3 tools/build-mainline-boot.py --output out/ram-desktop \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz --profile desktop \
  --rootfs out/desktop-root/rootfs.squashfs \
  --rootfs-url http://192.168.77.10:8088/rootfs.squashfs \
  --debug-package out/debug-package/erhai-debug_*_all.deb \
  --cmdline-extra erhai.session=1800
python3 tools/package-switch.py
ln -sf "$PWD/tools/prepare-dualboot.py" out/desktop-root/prepare-dualboot.py
mkdir -p out/desktop-root/rootfs.squashfs.parts
split -b 64M -d out/desktop-root/rootfs.squashfs out/desktop-root/rootfs.squashfs.parts/part
python3 -m http.server 8088 --bind 0.0.0.0 --directory out/desktop-root
```

The chunks avoid the current USB stall during long transfers. They can be removed
after the download. Keep the server running. In another host terminal, select the tablet, save its
boot images and start the temporary image:

```sh
set -e
device_serial=DEVICE_SERIAL
python3 tools/install.py --serial "$device_serial" --work out/device-check --phase check-device
device_backup="$PWD/out/device-backup-$device_serial"
mkdir -p "$device_backup"
for part in boot init_boot vendor_boot; do
  adb -s "$device_serial" exec-out su -c "cat /dev/block/by-name/${part}_a" > "$device_backup/$part.img"
done
adb -s "$device_serial" reboot bootloader
fastboot -s "$device_serial" boot out/ram-desktop/boot-mainline.img
```

Use `ip -br link` to find the new USB network interface and substitute its name
for `USB_INTERFACE` below. Skip address configuration if USB DHCP has already
assigned `192.168.77.10` to the host. Keep this diagnostic network connected only
to your own computer. The host needs `curl` and a Telnet client.

```sh
sudo ip link set USB_INTERFACE up
sudo ip address replace 192.168.77.10/24 dev USB_INTERFACE
```

Wait for the RAM desktop, then connect from the host with
`telnet 192.168.77.2 2323`. In the tablet's root shell, save the partition-table
backup and display the plan:

```sh
/usr/bin/busybox wget -O /run/prepare-dualboot.py http://192.168.77.10:8088/prepare-dualboot.py &&
python3 /run/prepare-dualboot.py
```

In the host terminal, retrieve both backup files:

```sh
set -e
curl --fail http://192.168.77.2:8081/run/erhai-gpt-backup.bin -o "$device_backup/gpt.bin"
curl --fail http://192.168.77.2:8081/run/erhai-gpt-backup.json -o "$device_backup/gpt.json"
```

Once the backups are on the host and you accept losing all Android data, apply
the plan in the same tablet root shell:

```sh
python3 /run/prepare-dualboot.py --erase-android && reboot bootloader
```

Stop if the tool reports a failure. Only after it succeeds and the tablet reaches
Fastboot, run these commands on the host:

```sh
set -e
fastboot -s "$device_serial" erase userdata
fastboot -s "$device_serial" erase metadata
fastboot -s "$device_serial" reboot
```

Complete Android setup. If stock recovery requests a data format, complete that
step. Reinstall the KernelSU manager, enable USB debugging, and grant **Shell (ADB)**
root access under KernelSU's Superuser page. Erasing Android data resets this
grant; enabling USB debugging alone is not enough. Transfer the module from the host:

```sh
adb -s "$device_serial" push out/erhai-switch-v0.3.0.zip /sdcard/Download/
```

Select the ZIP from Downloads in KernelSU, install it and reboot Android.
Continue with the Linux installation below.

If partition editing is interrupted, retain the host backup, return to the RAM
desktop and use `sgdisk --load-backup=BACKUP_PATH /dev/sda` to restore the table,
then check it with `sgdisk --verify /dev/sda`. Restoring the table cannot recover
erased files.

## Clean installation on an existing Linux layout

The installer targets OPD2413 devices that already have `linux_rootfs` and
`linux_data` partitions and **active slot A**. Clean reinstallation, live boot
partition readback, normal reboot and both switching directions have been tested
on this layout. It retains
Android data and the GPT, replaces both Linux filesystems, and uses the existing
switcher to activate the Ubuntu boot triplet. Stock devices without Linux
partitions are outside this procedure.

The host needs amd64 Linux, rootful Docker, Android platform-tools, ARM64 binfmt, a native C compiler and `dpkg-deb`. Start with Android
running, battery at least 50%, USB debugging, working KernelSU root and this
project's switch module installed. Firmware must match the [tested combination](../packaging/installation.json); another OTA on the same model is not automatically accepted. Use the build guide's `rootfs.squashfs` and
its adjacent `manifest.json`. Allow space for the private installation images.
The installer builds the pinned AOSP `ext2simg` tool, which uses the ext4 allocation
bitmap and preserves zero metadata needed when replacing an older filesystem.

`backup` saves Android boot images and device data; it does
not back up Linux user files. Export any Linux files you want to keep before
proceeding: this backup cannot restore them.

From the project directory, use the tablet's serial from `adb devices`:

```sh
device_serial=DEVICE_SERIAL
install_work="$PWD/out/install-device"
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase backup
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase prepare \
  --rootfs out/desktop-root/rootfs.squashfs
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase install --erase-linux
```

The first two phases back up the tablet's boot set and calibration and prepare
images on the host. `--erase-linux` explicitly permits deleting the Linux system
and user files. The installer checks device, partition and input identities,
erases and flashes the two Linux partitions, returns to Android, then invokes
the switcher. It reads back all three boot partitions before rebooting Ubuntu.
Complete first-run account setup on the tablet.

Keep `install_work` private: it contains this tablet's backups and calibration,
not public release assets. A completed write still requires first-boot, touch,
desktop and dual-boot checks.

If Ubuntu fails to start, enter Fastboot and restore the verified Android set:

```sh
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase restore-android
```

This restores and verifies the Android boot triplet. The Linux partitions retain
the newly installed contents.

## Daily use and USB diagnostics

The unauthenticated USB root shell and file service of first-time preparation
exist only in the RAM session of the setup boot image. The root filesystem and
an installation made from it have no diagnostic channel. To keep the channel
for development with a trusted host, assemble the root filesystem from device
packages built with `--debug` (see the [build guide](BUILD.md#device-packages))
and install that root instead: their kernel package adds `erhai.debug=1` to the
boot images and requires `erhai-debug`.

Installing regular device packages over such an installation, built without
`--debug` into a new empty output directory or taken from a release's
`erhai-device-packages-VERSION.tar` as described in
[Upgrading an existing installation](#upgrading-an-existing-installation),
replaces the diagnostic boot images. After reboot, the USB shell, HTTP service
and diagnostic DHCP stay disabled. Stopping only the desktop services does not
disable the early-boot channels in a diagnostic image.

## Upgrading an existing installation

A newer release installs over an existing installation with APT. It does not
repartition the tablet, reinstall Ubuntu or touch Android. Build the release's
device packages and sensor package (`tools/build-debs.py` and `tools/build-sensors.py`,
see the [build guide](BUILD.md#device-packages)), each into a new empty output
directory, with the same choice of `--debug` as the installed packages. Transfer
both directories to the tablet, then run in its terminal:

```sh
sudo apt install ./device-packages/*.deb ./sensor-debs/*.deb && sudo reboot
```

The release's `erhai-device-packages-VERSION.tar` holds the same packages and
`erhai-mesa`, without USB diagnostics; installing them also turns a diagnostic
installation into a regular one (`tar xf erhai-device-packages-v0.3.0.tar && sudo apt install ./erhai-device-packages-v0.3.0/*.deb`).

The kernel package writes the new boot images to the active slot during the
installation, and the previous kernel package stays installed. The sensor
registry imported at installation time is kept. If the new kernel does not start,
follow the recovery steps below.

The `erhai-firefox` package moves Firefox from the Ubuntu snap to Mozilla's deb.
After the upgrade, run `sudo apt update && sudo apt install firefox` and accept
the replacement of Ubuntu's transitional `firefox` package, which APT lists as a
downgrade because of that package's version epoch. The snap keeps each user's
profile in `~/snap/firefox/common/.mozilla/firefox`; to keep it, copy it before
the first start of the new Firefox with
`mkdir -p ~/.mozilla && cp -a ~/snap/firefox/common/.mozilla/firefox ~/.mozilla/`,
then remove the snap with `sudo snap remove firefox`. The snap is removed
automatically at boot only when no user has a `~/snap/firefox` directory.

## Failure and full stock recovery

If the tablet stops responding, hold **Power + Volume Up for about 15 seconds**.
Release when the screen turns off or the OnePlus logo appears. If it stays off,
press Power to start it. This combination has been used to recover the OPD2413.

Preserve errors, image versions and backups after a failed boot. Establish the
current system and completed writes before proceeding. Do not repeatedly rerun
installation or mix versions of the boot triplet; check all three partitions together.

Returning to the existing Android system does not restore a factory partition
layout. Full stock recovery also depends on matching firmware, layout and user
data. A general recovery procedure has not been independently hardware-validated
by this project.

Keep this tablet's boot-image and calibration backups. Never restore another
device's calibration, addresses or persist partition. Keep the bootloader unlocked
while non-stock images remain installed.
