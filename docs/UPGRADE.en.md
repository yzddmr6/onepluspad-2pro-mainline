# Upgrade notes

[中文](UPGRADE.md) · [Installation and recovery](FLASHING.en.md)

## v0.7.2 → v0.8.0

v0.8.0 keeps Linux 7.2.15 and adds Gunyah virtual machines, Waydroid kernel support, Snap graphics, Resources hardware monitoring and an 80% battery charge limit, together with interrupt and UART suspend fixes.
GunyahVM and Resources are preinstalled. Install Waydroid separately using the [guide](WAYDROID.en.md); it uses software rendering and Android Data Saver is unavailable. Snap graphics use the shared `piano-snap-graphics` package; strict confinement remains affected by snapd feature detection.
Enable battery protection in GNOME Settings → Power to stop charging at 80% and resume at 75%; it is off by default. Protected charging keeps the system awake until charging stops. If the battery reaches the lower threshold during sleep, charging resumes after the system wakes.

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

To select v0.8.0 again after rollback, reinstall the package set so the kernel postinst activates the candidate again. A plain `apt install` may skip maintenance scripts because those versions are already installed:

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
