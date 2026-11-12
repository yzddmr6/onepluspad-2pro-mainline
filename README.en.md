# Ubuntu for OnePlus Pad 2 Pro

Run Ubuntu Desktop 26.04 with GNOME on the OnePlus Pad 2 Pro, using a device-adapted
kernel based on upstream Linux. [中文](README.md)

Official builds are published only in this repository's [Releases](https://github.com/yzddmr6/onepluspad-2pro-mainline/releases), free of charge.

## 🧭 Our Approach

There are roughly two ways to bring a Linux desktop to an Android tablet.

One is **make it work first, then adapt**: keep the vendor's downstream drivers and patch the desktop and applications wherever they do not cooperate. Features arrive quickly, but the device's quirks end up spread across the kernel, the desktop and the applications, tied together, and every system upgrade means reworking those changes.

The other is **stay close to upstream, in clean layers**: solve hardware problems in the kernel and drivers the way mainline does, keep Ubuntu, GNOME and the rest unmodified, and let the system recognise the device through standard interfaces. It is slower and harder; many problems can only be fixed once their root cause is found.

We chose the second.

| | Make it work, then adapt | Stay close to upstream (this project) |
|---|---|---|
| Kernel and drivers | Vendor downstream drivers plus temporary workarounds | Mainline kernel and upstream drivers (for example the upstream ath12k driver for Wi-Fi); missing pieces added the upstream way, with device tree bindings |
| Desktop and apps | Desktop components modified to suit this device | Official Ubuntu Desktop packages installed unchanged; device support lives in a few separate `erhai-*` packages |
| When something breaks | Add delays, retries and compatibility layers until it works | Find the root cause and fix it in the layer where it lives |
| System upgrades | Every change has to be reworked, upgrades can get stuck | Normal upgrades with the upstream kernel and Ubuntu |
| Reuse by others | Depends on this whole set of specific changes | Low cost to move to another distribution or a device with the same SoC |

**Why:**

- **Decoupling.** Differences in the display, touch and charging hardware are described by the kernel and the device tree; the desktop just sees a standard display, touchscreen and battery and does not need to know which tablet it runs on.
- **Upgrades are not held hostage.** The fewer the changes, the smoother the upgrades: the kernel can follow new upstream releases and Ubuntu updates install as usual. The few components that must be changed, such as the Mesa graphics driver, ship as separate packages that track upstream and are dropped once upstream supports the feature.
- **Fix once, everyone benefits.** A problem solved the upstream way helps other devices with the same SoC and other distributions; upstream fixes, in turn, apply here directly.
- **Reproducible and maintainable.** Every release is assembled only from inputs whose source and checksum are recorded, so it can be rebuilt from source; few changes with clear boundaries make problems easy to locate instead of piling up.

The price is that features arrive more slowly, and some problems take a long time to trace to their root cause. When the default video player occasionally crashed, for example, we did not fall back to software rendering for it; we traced the crash to unsynchronised texture numbering in the graphics driver and fixed it in Mesa. We accept that price, because this is the route that holds up over time.

## 📮 Follow & Discuss

Project updates, usage notes and discussion are available through these channels,
primarily in Chinese.

| WeChat: 熵减矩阵 | Xiaohongshu: yzddmr6 |
|:---:|:---:|
| <img src="docs/assets/gzh-qr.png" width="200" alt="WeChat: 熵减矩阵"> | <img src="docs/assets/xhs-qr.jpg" width="200" alt="Xiaohongshu: yzddmr6"> |
| Progress and technical notes | Usage and discussion |

## ⚠️ Read Before Installing

- **Device scope:** OnePlus Pad 2 Pro, **OPD2413 / erhai / SM8750P**. **12 GB / 16 GB RAM and 512 GB storage** models are supported.
  ColorOS C.34 and C.35 are supported, and installation needs active slot A.
  The installation procedure does not cover OnePlus Pad 3, other storage capacities or partition layouts.
- **Installation scope:** first-time partition preparation, Linux installation
  and reinstallation are provided for the 512 GB model. First-time partitioning
  erases Android data. See the [installation and recovery guide](docs/FLASHING.en.md)
  for firmware and layout requirements.
- **Power:** A PPS charger fast-charges the battery through the charge pump at up to
  about 39 W (below 80 % charge, battery between 12 and 44 °C); other USB PD chargers
  get the 9 V contract (up to 18 W input). On a computer's USB port with the screen on,
  the tablet uses more than the port supplies and the battery still drains slowly. The
  stock SUPERVOOC protocol is not available under Linux. Fastboot is not a
  charging fallback.
  Closing the keyboard cover or a case suspends the tablet; the power button defaults to locking the
  screen and can be configured in Settings > Power. In suspend the SoC reaches its deepest
  power states. When idle, the screen dims and blanks with Ubuntu's defaults and the tablet
  suspends on battery.
  See [System suspend](docs/SUSPEND.en.md) for timings and power-button settings.
- **Data and recovery:** unlocking the bootloader erases user data. Back up
  personal files and obtain matching stock firmware before changing the device.
  Keep factory calibration and device addresses specific to each tablet.
- **Debug access:** USB diagnostics are for development. When enabled, they
  expose an unauthenticated root shell and HTTP service. Connect only to a
  trusted computer and keep these services off public networks.

## 🚀 Getting Started

Device firmware and stock boot build inputs are included; no manual ROM
extraction is needed. Stock inputs use **ColorOS `OPD2413_11.C.34_1340_202607031844`**;
other firmware sources are listed in the [firmware notes](packaging/firmware/README.md). Run `tools/prepare-inputs.py` as described in the build guide.

| I want to | Read |
|---|---|
| Check whether the tablet meets my needs | [Hardware support](#hardware-support) |
| Switch between Android and Ubuntu | [Dual boot](#dual-boot) |
| Build the kernel and device components | [Build guide](docs/BUILD.en.md) |
| Check installation requirements and recovery | [Installation and recovery](docs/FLASHING.en.md) |
| Install from the release images without building | [Prebuilt release images](docs/FLASHING.en.md#prebuilt-release-images) |
| Work on the graphics stack | [Graphics integration](docs/GRAPHICS.md) |
| Check suspend and the power button | [System suspend](docs/SUSPEND.en.md) |
| Check the panel backlight and brightness | [Display and backlight](docs/DISPLAY.en.md) |
| Bring up or check the sensors | [SSC sensors](docs/SENSORS.en.md) |
| Contribute code or report a problem | [Contributing](CONTRIBUTING.md) |
| Read release history | [Changelog](CHANGELOG.md) |

## Dual Boot

On a tablet with both systems installed, Ubuntu uses a separate Linux root
partition while Android retains its own system and data. Routine switching
requires a reboot; it does not reinstall either system or erase user files.

| Current system | How to switch |
|---|---|
| Ubuntu → Android | Open **Switch to Android** from the application list, enter the administrator password and wait for the automatic reboot. |
| Android → Ubuntu | Open the **erhai dual boot switch** module's WebUI in KernelSU and select **Reboot to Ubuntu**. |

Both systems use the same active boot slot; the project layout uses slot A.
The switcher writes the target system's `boot`, `init_boot` and `vendor_boot`
images as a set, reads them back for verification, then reboots. The other
system's images remain in the switcher storage on the Linux partition.
Routine switching does not change the active slot.

Switching writes the boot partitions. Do not interrupt power or force a restart
during the operation. See [installation and recovery](docs/FLASHING.en.md) for
requirements and recovery, and the [switcher reference](switch/README.md) for
implementation details.

## Hardware Support

The tables below describe current hardware support and known limitations.
Features under development are not included in the supported feature set.

✅ Working · 🟡 Partial · ❌ Unsupported

### Platform, Display and Input

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Boot and storage | SM8750P / UFS | ✅ | Ubuntu boot and storage access work. Dual-boot switching is limited to the partition layout described above. |
| Internal display | Dual DSI / DSC | ✅ | 3392 × 2400 at 120 Hz only. |
| Touch | Novatek NT36536 | ✅ | Finger input, desktop interaction and login work. Pen support is listed separately. |
| GPU and desktop | Adreno 830 / Freedreno / Turnip / Mesa | ✅ | GNOME, OpenGL and Vulkan hardware rendering work. Vulkan uses Turnip. If GPU recovery fails, applications can remain stuck during exit and a reboot may be needed. |
| Brightness | Dual KTZ8868 / one backlight interface | ✅ | Unified backlight control supports manual brightness adjustment and screen blanking. |
| Magnetic keyboard | Pogo keyboard / touchpad | ✅ | Keyboard input works and stays connected while idle and after system sleep. The on-screen keyboard appears for touch input when detached and hides when attached. Holding the magnifier key turns the top row into F1 to F12. |
| Active pen | NT36536 pen input | 🟡 | Pen input is not enabled yet: the driver is present but off by default. |
| Pen charging | CPS8601 | ✅ | A pen attached to the back charges wirelessly. |

### Wireless and USB

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Wi-Fi | WCN7860 / ath12k | ✅ | Networking, automatic connection at boot and data transfers work. Packages keep the radio in world domain `00`. 5 GHz uses passive scanning and cannot host a hotspot. Changing the country code while associated can crash the WLAN firmware; do not do so. |
| Bluetooth | WCN7860 / BlueZ | ✅ | The Bluetooth controller, scanning and device connections work. |
| USB device mode | USB-C / NCM | 🟡 | USB networking works. Some unplug/replug cycles require a reboot to restore the connection. |
| USB host peripherals | HID, storage, network and digital audio | ✅ | USB drives connected directly through a USB-C to USB-A adapter receive power from the tablet and can be recognized and mounted. A mouse connected through a dock works without external PD power. |
| USB storage formats | UAS, exFAT and NTFS3 | ✅ | exFAT and NTFS3 support reading, writing and Chinese filenames. NTFS USB drives mount automatically on the desktop. |
| External display | USB-C DisplayPort Alt Mode | ✅ | External monitor output works over USB-C DisplayPort. |
| External display audio | DisplayPort / ALSA / PipeWire | ❌ | Disabled by default: the playback configuration prevents microphone discovery with no monitor attached. External display audio playback is unavailable. |

### Audio, Video and Sensors

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Internal microphones | WCD939x / ALSA / PipeWire | ✅ | Default input and two-channel capture work, including recording before and after suspend. |
| Speakers | Six AW88261 amplifiers / AudioReach | 🟡 | Speakers are enabled by default and can be disabled persistently. Vendor DSP speaker protection is absent. See [daily-use policies](docs/DAILY.en.md). |
| USB-C analog audio | WCD939x headset path | ❌ | Analog adapters and headset detection are not implemented. Digital USB audio is tracked above. |
| Video playback in desktop players | Ubuntu GStreamer packages / Iris | ✅ | Showtime, the default player, plays H.264, H.265 and VP9 with hardware decoding and continues playback after seeking. |
| Hardware video codecs | Qualcomm Iris | ✅ | Hardware decoding of H.264, H.265 and VP9 (the default player through GStreamer, Firefox through VA-API) and hardware encoding of H.264 and H.265. |
| Front and rear cameras | SC820CS / SC1300CS | 🟡 | The default Camera app (Snapshot) supports preview and photos with both cameras. Automatic white balance uses a simple grey-world algorithm, so scenes dominated by one colour can look tinted. Lens-shading correction is absent, leaving darker corners. Focus is fixed at a distance, making close objects soft, and dim scenes are noisy. |
| Automatic rotation | SSC / iio-sensor-proxy | ✅ | With the keyboard detached, the screen follows the orientation in all four directions, each the right way up. With the keyboard attached it stays fixed, as on a laptop. |
| Automatic brightness | SSC ambient light / GNOME | ✅ | The ambient-light sensor is integrated with GNOME. Enable Automatic Brightness in Settings → Power to adjust the backlight to ambient light; idle dimming and blanking follow Ubuntu defaults. |
| Compass and gyroscope | SSC / iio-sensor-proxy | ✅ | Heading and angular velocity are available over D-Bus and keep updating after suspend. |
| Proximity | SSC | ❌ | The DSP does not publish the proximity sensor on this unit, and `libssc` has no SAR implementation. |

### Power, Time and Applications

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Cover | Hall switch / logind | ✅ | Closing the keyboard cover or a case suspends the tablet within about a second; opening it wakes the tablet and lights up the screen. Touch input is ignored while the cover is closed. Closing and opening the cover does not wake a suspend entered with the cover open (for example through idle suspend); press the power button instead. |
| Power button | Linux input / GNOME | ✅ | GNOME handles the key; its default action is to lock the screen and can be changed in Settings > Power. The old `power-key-action` files no longer apply. |
| Volume keys | GPIO / PMIC PON input | ✅ | Volume up and down report `KEY_VOLUMEUP` and `KEY_VOLUMEDOWN`, respectively. |
| CPU frequency and temperature | SCMI / IIO / thermal | 🟡 | Frequency scaling and temperature readings work. Sustained-load thermal control and enclosure-temperature management are incomplete. |
| Battery reporting | qcom_battmgr / UPower | ✅ | Capacity and runtime estimates available; charging behavior is a separate limitation. |
| Charging in Linux | USB power / vendor firmware / SC8547A charge pump | ✅ | A PPS charger fast-charges through the charge pump at up to about 39 W (below 80 % charge, battery between 12 and 44 °C); other PD chargers get the 9 V contract, up to 18 W input. On a computer's USB port (about 2.5 W) with the screen on, the battery still drains by about 2–3 % per hour. The stock SUPERVOOC protocol is not available. |
| Suspend and resume | Linux power management | ✅ | Defaults to s2idle, with CX power collapse and DDR self-refresh. Cover, power-button and RTC wake are supported; Wi-Fi, keyboard and cameras remain usable after resume. The firmware-provided `deep` state is not used by default. See [System suspend](docs/SUSPEND.en.md). |
| RTC | Qualcomm PMIC RTC | ✅ | Time read/write works. A forced reset loses the RTC time; it is set again once online. Certificate time checks do not block initial synchronization, and networks blocking authenticated time (NTS) use their own time server. Synchronized time is written back to the RTC and survives a normal restart. |
| Snap applications | AppArmor / snapd / GPU content provider | 🟡 | Shared Adreno 830 graphics runtime; strict confinement remains affected by snapd feature detection. |
| Android applications | Waydroid | 🟡 | Applications and networking with software rendering; Android Data Saver is unavailable. [Installation](docs/WAYDROID.en.md). |
| Virtual machines | Gunyah / GunyahVM 1.1.0 | ✅ | Preinstalled virtual machine manager for ARM64 Linux guests. |
| Hardware monitoring | Resources | ✅ | CPU, GPU and battery telemetry, with available temperature sensors. |

## Use and Maintenance

Checks GitHub anonymously once a day for the latest release and notifies you when a newer version is available; this can be disabled in notification settings.

The base system comes from the official Ubuntu Desktop image. Device support is
delivered as separate `erhai-*` packages; Ubuntu packages remain managed by APT.
Firefox comes from Mozilla's APT repository (`erhai-firefox`) instead of the
snap, so that it renders with the device graphics driver and updates through APT.
The display-power adapter currently targets GNOME Settings Daemon 50; desktop
major-version upgrades need compatibility checks.

For problem reports, include the model, firmware and package versions,
reproduction steps and relevant logs. Remove credentials, serial numbers and
personal information before sharing. Use the channels above for discussion.

## Development and Contributions

| Repository | Owns |
|---|---|
| [onepluspad-2pro-mainline](https://github.com/yzddmr6/onepluspad-2pro-mainline) | Device packages, userspace integration, build tools and documentation |
| [linux-sm8750-erhai](https://github.com/yzddmr6/linux-sm8750-erhai) | Linux kernel source, drivers, device trees and kernel configuration |

The kernel revision used for builds is recorded in [kernel/source.json](kernel/source.json).
See the [build guide](docs/BUILD.en.md) and [contribution guide](CONTRIBUTING.md).

## Acknowledgements and License

This project builds on Linux, Ubuntu, GNOME, Freedreno/Mesa and the Linux Qualcomm
community. Device integration draws on work from
[ROCKNIX](https://github.com/ROCKNIX/distribution), OnePlus and LineageOS, and
uses AudioReach and the SSC sensor stack.

Original integration code is licensed under **GPL-2.0-only**, unless a file
states otherwise. The Linux kernel and third-party components retain their own
licenses and authorship. See [LICENSE](LICENSE), [NOTICE](NOTICE), and the
[firmware provenance and distribution restrictions](packaging/firmware/README.md).
