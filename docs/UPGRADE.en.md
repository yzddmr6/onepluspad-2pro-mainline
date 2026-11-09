# Upgrade notes

[中文](UPGRADE.md) · [Installation and recovery](FLASHING.en.md)

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
