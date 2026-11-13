# Upgrade notes

[中文](UPGRADE.md) · [Installation and recovery](FLASHING.en.md)


## v0.9.0 → v0.9.1

Extract the device packages TAR. Use the whole-release upgrade command below with `erhai-0.9.1` as the new repository and `erhai-0.9.0-rollback-0.9.1` for `--previous`. Shut down virtual machines before upgrading and reboot after installing the complete batch.


## v0.8.1 → v0.9.0

Install the complete `erhai-0.9.0` package batch together with its matching
boot images. Keep the supplied `erhai-0.8.1` batch for complete rollback.
The kernel, standard Mesa packages and Snap graphics provider change together;
close virtual machines before upgrading and reboot afterwards.
The default NPU demo includes its runtime, model and board firmware.
Follow the existing whole-release upgrade and rollback commands below, replacing
the repository paths with this release's two batches.


Sensor shutdown detaches client callbacks before closing the drivers, fixing crashes when stopping or restarting the service.

After rebooting into a new session, GNOME uses the Iris hardware encoder for its built-in full-screen recorder. This reduces recorder CPU use; the default settings can produce larger files than software encoding.

## v0.8.0 → v0.8.1

The rollback tool preserves the Ubuntu library versions actually installed on this device. Install the distribution's repository-index tool before the first complete upgrade:

```sh
sudo apt install --no-install-recommends dpkg-dev
```


The power button now locks the screen by default instead of directly suspending. Change its action in Settings > Power. Settings is updated to 50.3 and retains the port author in About. Install the complete batch to migrate both graphics and settings components.

Host Mesa now uses Ubuntu package names and standard multiarch directories, so
sandboxed web processes can discover the device drivers. The driver version and
six patches are unchanged; the Snap graphics provider stays separate. The
`repositories/erhai-0.8.1/` attachment contains a complete release batch,
including all Mesa development and OpenCL packages; only the required runtime
subset is installed by default. libdrm consists of original Ubuntu binaries and
is not pinned, allowing normal Ubuntu updates.

Verify the release attachment checksums and extract both batches into a new empty directory, without overwriting an earlier repository with the same name. The previous
batch must contain the exact installed release packages and their Mesa/libdrm
versions; the tool refuses an incomplete rollback inventory. Copy both repository
directories to the tablet, then run there:

```sh
sudo systemd-run --unit=erhai-release-upgrade --setenv=DEBIAN_FRONTEND=noninteractive \
  /usr/bin/python3 /home/<USER>/repositories/erhai-0.8.1/install.py upgrade \
  /home/<USER>/repositories/erhai-0.8.1 \
  --previous /home/<USER>/repositories/erhai-0.8.0
journalctl -f -u erhai-release-upgrade
sudo dpkg --audit
sudo reboot
```

The tool retains both batches under `/var/lib/erhai/releases/` and saves the
installed versions and current boot set before changing packages. Repeating the
same batch is supported. After an interrupted installation, run
`sudo dpkg --configure -a` and `sudo apt-get -f install`, then repeat the upgrade.
Personal files and application data are outside package rollback scope.

### Complete release rollback

Use a terminal or developer SSH, including when the graphical desktop cannot
start. Restore userspace before changing the kernel:

```sh
sudo systemd-run --unit=erhai-release-rollback --setenv=DEBIAN_FRONTEND=noninteractive \
  /usr/bin/python3 /var/lib/erhai/releases/erhai-0.8.1/install.py rollback --product erhai
journalctl -f -u erhai-release-rollback
sudo dpkg --audit
sudo reboot
```

This restores all release-managed packages to the previous exact versions, then
restores the saved boot set. Mesa rollback reinstates its old `/opt` payload and
registration and removes the new transition package's version policy. A failed
step stops the transaction. Retain both repositories and boot sets until the new
release is stable. Fastboot restores boot partitions only; it cannot restore
userspace packages. When recovery is required, repair the root's packages before
using the matching previous boot set.

## v0.7.2 → v0.8.0

v0.8.0 keeps Linux 7.2.15 and adds Gunyah virtual machines, Waydroid kernel support, Snap graphics, Resources hardware monitoring, together with interrupt and UART suspend fixes.
GunyahVM and Resources are preinstalled. Install Waydroid separately using the [guide](WAYDROID.en.md); it uses software rendering and Android Data Saver is unavailable. Snap graphics use the shared `piano-snap-graphics` package; strict confinement remains affected by snapd feature detection.

Before upgrading, while still running v0.7.2, save an independent boot-set copy. If the destination already exists, inspect it instead of overwriting it:

```sh
sudo test ! -e /var/lib/erhai/rollback-v0.7.2-before-v0.8.0 &&
sudo cp -a --reflink=never /var/lib/erhai/switch/ubuntu /var/lib/erhai/rollback-v0.7.2-before-v0.8.0
sudo sh -c 'cd /var/lib/erhai/rollback-v0.7.2-before-v0.8.0 && sha256sum -c SHA256SUMS'
```

After checking `SHA256SUMS`, run on the tablet:

```sh
tar xf erhai-device-packages-v0.8.0.tar
sudo apt install ./erhai-device-packages-v0.8.0/*.deb
sudo erhai-remove-generic-kernels
```

The cleanup command removes unused Ubuntu generic kernels and kdump, retaining `erhai-kernel-image-*`, the running and rollback kernels, and `linux-firmware`. Reboot after both commands succeed; no repartitioning or reinstallation is needed.
Install the shared packages and their dependencies together with the device packages. Use the matching debug set to retain development access; the normal archive disables debug access after reboot.

GunyahVM and its runtime and guest payload packages are installed by this upgrade. At the first login after upgrading, the default Dock includes GunyahVM; existing customized favorites receive it once at the end, preserving their entries and order. Later user removals are respected. Device access for the active local desktop user comes from GunyahVM’s own udev and polkit rules, with no manual group changes.

### Kernel rollback and upgrading again

Keep this copy and the v0.7.2 kernel/module packages until the new version is confirmed usable. To roll back while Ubuntu is still accessible, run:

```sh
sudo erhai-switch-install-ubuntu-images /var/lib/erhai/rollback-v0.7.2-before-v0.8.0 && sudo reboot
```

The installer verifies all three images, promotes the specified copy to the current Ubuntu boot set, and writes the current active slot. A copy matching `ubuntu.prev` is also promoted. After rebooting, `uname -r` should report `7.2.15-erhai-dev-g870167fad062-a359a9829`. This restores the kernel and boot set only; it does not downgrade applications or restore user data.

To select v0.8.0 again after rollback, reinstall the package set so the kernel postinst activates the v0.8.0 kernel again. A plain `apt install` may skip maintenance scripts because those versions are already installed:

```sh
sudo apt install --reinstall ./erhai-device-packages-v0.8.0/*.deb
sudo erhai-remove-generic-kernels
sudo reboot
```

## v0.7.1 → v0.7.2

v0.7.2 updates the kernel, matching modules and boot images, together with the
graphics driver, the device-support package and the sensor package; see the
[release notes](https://github.com/yzddmr6/onepluspad-2pro-mainline/releases/tag/v0.7.2)
for the fixes. Mesa moves to 26.2.6: the new `piano-mesa` package provides the
drivers and `erhai-mesa` becomes a transitional package that depends on it; both
are in the archive and install together. The new `erhai-release-notifier` package
adds update notifications. Other device packages and the Android switch module
retain their previous versions. Mixed component versions are expected;
repartitioning and reinstalling Ubuntu are unnecessary.

Download `erhai-device-packages-v0.7.2.tar` and `SHA256SUMS`, verify the download,
then transfer the archive to the tablet and install it in Ubuntu:

```sh
tar xf erhai-device-packages-v0.7.2.tar
sudo apt install ./erhai-device-packages-v0.7.2/*.deb
```

Reboot after APT completes successfully. The kernel selector requires an exactly
matching image/module package. Installation updates the active slot's boot images
and retains the previous kernel for [rollback](FLASHING.en.md#failure-and-full-stock-recovery).
User files, accounts and existing device calibration data are preserved. An
existing v0.7.0 Android switch module does not need reinstalling.

The normal archive converts a debug installation to normal boot and disables USB
debugging after reboot. Installations that need to retain development debugging
must use a separately built debug package set for this release; do not mix normal
and debug kernel packages.

## v0.7.0 → v0.7.1

v0.7.1 updates the kernel, matching modules and boot images to fix intermittent
Bluetooth startup failures and audio error floods. The kernel configuration is
unchanged from v0.7.0. The device-support package also hides Android system
partitions from the dock and file manager. Other device packages and the Android
switch module retain their previous versions. Mixed component versions are expected;
repartitioning and reinstalling Ubuntu are unnecessary.

Download `erhai-device-packages-v0.7.1.tar` and `SHA256SUMS`, verify the download,
then transfer the archive to the tablet and install it in Ubuntu:

```sh
tar xf erhai-device-packages-v0.7.1.tar
sudo apt install ./erhai-device-packages-v0.7.1/*.deb
```

Reboot after APT completes successfully. The kernel selector requires an exactly
matching image/module package. Installation updates the active slot's boot images
and retains the previous kernel for [rollback](FLASHING.en.md#failure-and-full-stock-recovery).
User files, accounts and existing device calibration data are preserved. An
existing v0.7.0 Android switch module does not need reinstalling.

The normal archive converts a debug installation to normal boot and disables USB
debugging after reboot. Installations that need to retain development debugging
must use a separately built debug package set for this release; do not mix normal
and debug kernel packages.
