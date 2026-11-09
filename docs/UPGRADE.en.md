# Upgrade notes

[中文](UPGRADE.md) · [Installation and recovery](FLASHING.en.md)

## v0.7.2 → v0.8.0

⟦DRAFT:G-RELEASE⟧

v0.8.0 keeps Linux 7.2.15 and adds Gunyah virtual machines, Waydroid kernel support, Snap graphics, Resources hardware monitoring and an 80% battery charge limit, together with interrupt and UART suspend fixes.
GunyahVM and Resources are preinstalled. Install Waydroid separately using the [guide](WAYDROID.en.md); it uses software rendering and Android Data Saver is unavailable. Snap graphics use the shared `piano-snap-graphics` package; strict confinement remains affected by snapd feature detection.
Enable battery protection in GNOME Settings → Power to stop charging at 80% and resume at 75%; it is off by default. Protected charging keeps the system awake until charging stops. If the battery reaches the lower threshold during sleep, charging resumes after the system wakes.

After checking `SHA256SUMS`, run on the tablet:

```sh
tar xf erhai-device-packages-v0.8.0.tar
sudo apt install ./erhai-device-packages-v0.8.0/*.deb
sudo erhai-remove-generic-kernels
```

The cleanup command removes unused Ubuntu generic kernels and kdump, retaining `erhai-kernel-image-*`, the running and rollback kernels, and `linux-firmware`. Reboot after both commands succeed; no repartitioning or reinstallation is needed.
Install the shared packages and their dependencies together with the device packages. Use the matching debug set to retain development access; the normal archive disables debug access after reboot.

GunyahVM and its runtime and guest payload packages are installed by this upgrade. After logging in again, the default Dock includes GunyahVM; explicitly customized favorites remain unchanged. Device access for the active local desktop user comes from GunyahVM’s own udev and polkit rules, with no manual group changes.

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
