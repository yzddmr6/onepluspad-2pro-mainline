# Changelog

## v0.3.0

Device and sensor packages are numbered 0.3.0 and install over v0.2.x with
APT; see "Upgrading an existing installation" in
[FLASHING](docs/FLASHING.md#upgrading-an-existing-installation). The device
package archive of the release now also carries `erhai-mesa`.

- Kernel `erhai-v0.3.0`:
  - DisplayPort retries reading the sink capabilities after an AUX failure,
    so that a monitor behind a USB-C hub in the reverse plug orientation no
    longer has to be plugged in again.
  - The Iris video decoder offers decode-order output, and clients can set a
    10-bit capture format before the stream is parsed.
  - Each CPU thermal zone has a passive trip at 118 °C, the stock threshold,
    that throttles the core's frequency domain; until now nothing in Linux
    cooled a hot core before the critical shutdown at 125 °C.
  - Holding the magnifier key of the keyboard cover turns the top row into
    F1 to F12. The magnifier key reports `KEY_FN` instead of `KEY_F23`.
  - High-pass filter controls for the TX decimators. `erhai-audio` sets the
    filters of both internal microphones to 75 Hz instead of their 4 Hz reset
    corner, so that rumble and handling noise below 30 Hz no longer set the
    peak level of a recording, and therefore requires this kernel.
  - Bluetooth resets its in-band sleep state when the controller is powered
    off (from a patch posted upstream), so that powering the controller on
    again shortly afterwards does not break its UART link.
  - The battery manager gains charge start and end thresholds through the
    standard power-supply attributes, power for USB devices attached directly
    to the port, such as a mouse on a USB-C to USB-A adapter, and PPS
    charging at up to 8.4 V and 3 A. The end threshold defaults to 100 %,
    which leaves charging to the firmware as before. PPS charging stays off
    unless `qcom_battmgr.pps_enable=1` is set, and is experimental: on the
    tested charger it did not start a PPS contract.
- Firefox is Mozilla's deb from packages.mozilla.org instead of the Ubuntu
  snap, so that it can render with the device graphics driver; it is updated
  through APT. The new `erhai-firefox` package configures the repository with
  Mozilla's signing key and gives Mozilla's builds priority over Ubuntu's
  transitional package. The root filesystem installs a pinned build, and the
  Firefox snap is removed after first-boot seeding. Existing installations
  switch as described in
  [FLASHING](docs/FLASHING.md#upgrading-an-existing-installation). The
  repository setup is based on
  [TheMojoMan's oneplus-erhai-ubuntu](https://github.com/TheMojoMan/oneplus-erhai-ubuntu).
- The on-screen keyboard is no longer forced on. GNOME offers it for touch
  input while the keyboard cover is detached and keeps it hidden while the
  cover is attached.
- Releases attach one root filesystem instead of two. First-time preparation
  runs the installation image as its RAM desktop; the setup boot image carries
  the `erhai-debug` package and installs it into that RAM session only, so
  neither the published image nor an installed system has USB diagnostics.
  See "Prebuilt release images" in [FLASHING](docs/FLASHING.md).
- erhai-mesa revision 5 fixes the Mesa freedreno abort on the
  `fd6_texture_state` assertion. One GL context allocated sampler view seqnos
  in the application thread and freed them in the driver thread without
  locking, so two live textures could share cached texture state. Showtime
  aborted on it during video playback and GNOME Shell aborted on it once.
  The fix is a project patch to Mesa 26.2.3 and is not yet upstream.
- `apt update` no longer fails on the Ubuntu ISO's installation medium
  source, `cdrom.sources`: the root filesystem no longer contains it, and
  the 0.3.0 device packages remove it from existing installations.

Several kernel changes build on @TheMojoMan's
[oneplus-erhai-linux](https://github.com/TheMojoMan/oneplus-erhai-linux).

Tested on the tablet: the installed system upgraded to these packages with
the boot images read back intact, and Bluetooth came up with its address on
every boot during testing and after three power cycles. Everyday applications
ran with hardware OpenGL without GPU faults, including Firefox and video
playback in Showtime; recording used the 75 Hz filters; the 70 % end threshold
stopped charging and 100 % resumed it; a two-minute suspend resumed. With the
keyboard cover, the on-screen keyboard appeared when it was detached and hid
when it was attached, and the top row and its F1 to F12 layer reported the
expected keys. A USB drive on a USB-C to USB-A adapter was powered, mounted on
the desktop and written with a Chinese filename on two insertions. A USB PD
charger net-charged the battery at about 1.6 A at 5 V and 2 A.

Known issues: the touchpad key of the keyboard cover gives F4 with the
magnifier key held only on every other press. After a period without input
the keyboard cover can stop responding and does not recover when reattached;
restarting Linux restores it. PPS charging has no effect yet, as noted above.

## v0.2.2

- The internal microphones record at a usable level (ADC 13, TX DEC 112), and
  the opt-in speaker candidate runs the amplifiers at the stock -2.5 dB
  instead of -22.5 dB; this path still has no vendor speaker protection
  ([#7](https://github.com/yzddmr6/onepluspad-2pro-mainline/pull/7)).
- Kernel: volume up reports `KEY_VOLUMEUP` through the PMIC PON resin input
  ([linux-sm8750-erhai#1](https://github.com/yzddmr6/linux-sm8750-erhai/pull/1));
  included in kernel `erhai-v0.2.2`.
- Kernel: enable userspace regulatory hints and include the ath12k FROMLIST
  single-pdev frequency-range fix. Device packages do not set a country code;
  the radio remains in the world domain (`00`). Changing the country code while
  associated has caused WLAN firmware crashes; do not do so.
- Rebuilt installation and setup images include the 0.2.2 device packages.

Thanks to @HOSHINO61 for both changes.

## v0.2.1

- Prebuilt images are attached to the release: an installation root filesystem
  without USB diagnostics, the setup root filesystem and boot image for first-time
  preparation, and the device packages; see "Prebuilt release images" in
  [FLASHING](docs/FLASHING.md).
- The kernel and device behavior are unchanged from v0.2.0 (kernel
  `erhai-v0.2.0`).

## v0.2.0

Device and sensor packages are numbered 0.2.0 and install over v0.1.0 with APT;
see "Upgrading an existing installation" in [FLASHING](docs/FLASHING.md).

- System suspend defaults to s2idle. On the installed tablet, 300-second
  RTC-timed suspends in both display modes resume the display, touch, Wi-Fi and
  sensors ([#2](https://github.com/yzddmr6/onepluspad-2pro-mainline/pull/2)).
- Opt-in power-key suspend through `/etc/erhai/power-key-action`; the default
  is still lock and blank
  ([#3](https://github.com/yzddmr6/onepluspad-2pro-mainline/pull/3)).
- Compass and gyroscope readings through iio-sensor-proxy
  ([#1](https://github.com/yzddmr6/onepluspad-2pro-mainline/pull/1)).
- GNOME idle dimming is off, because the panel is never blanked automatically
  ([#4](https://github.com/yzddmr6/onepluspad-2pro-mainline/pull/4)).
- Notes on the panel brightness paths
  ([#6](https://github.com/yzddmr6/onepluspad-2pro-mainline/pull/6)).
- Kernel `erhai-v0.2.0`: the IPCC and GLINK drivers return to Linux v7.2 after
  the default-off suspend wake diagnostics are removed.
- H.264 hardware decoding is verified on the tablet. Known issue: Showtime aborts
  on a Mesa freedreno assertion when it draws video frames.

Thanks to @Pidbid for #1–#4 and #6.

## v0.1.0

Developer source preview for the OnePlus Pad 2 Pro (OPD2413).

- Separate integration and device-kernel repositories, with pinned source inputs.
- Component packages for the kernel, firmware and Ubuntu device integration.
- Included device firmware, stock boot build inputs and small upstream tool
  sources, with one command to prepare inputs and optional Ubuntu ISO extraction.
- Root filesystem assembly from official Ubuntu Desktop ARM64 inputs.
- Clean Linux reinstallation on the tested existing slot-A layout, with host
  backups and full boot-partition readback.
- First-time partition preparation for the 512 GB model using the distribution
  partitioning tool; partition creation, Android data reset, Linux first boot and
  dual-boot switching tested on hardware.
- KernelSU module packaging and shared switch/update locking; failed writes stop
  without automatic rollback and cannot replace the Android backup.
- Dual-boot switching for the documented installation layout and optional USB diagnostics.

Tested hardware support and known limitations are maintained in the
[README](README.md#hardware-support). Build and recovery instructions are in
[BUILD](docs/BUILD.md) and [FLASHING](docs/FLASHING.md).
