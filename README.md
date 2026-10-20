# Ubuntu for OnePlus Pad 2 Pro

Run Ubuntu Desktop 26.04 with GNOME on the OnePlus Pad 2 Pro, using a device-adapted
kernel based on upstream Linux. [中文](README.zh-CN.md)

## 📮 Follow & Discuss

Project updates, usage notes and discussion are available through these channels,
primarily in Chinese.

| WeChat: 熵减矩阵 | Xiaohongshu: yzddmr6 |
|:---:|:---:|
| <img src="docs/assets/gzh-qr.png" width="200" alt="WeChat: 熵减矩阵"> | <img src="docs/assets/xhs-qr.jpg" width="200" alt="Xiaohongshu: yzddmr6"> |
| Progress and technical notes | Usage and discussion |

## ⚠️ Read Before Installing

- **Device scope:** OnePlus Pad 2 Pro, **OPD2413 / erhai / SM8750P**. Testing has
  used a **16 GB RAM / 512 GB storage** unit. OnePlus Pad 3, other capacities and
  other firmware or partition layouts have not been validated.
- **Installation scope:** first-time partition preparation, Linux installation
  and reinstallation are provided for the 512 GB model. First-time partitioning
  erases Android data. See the [installation and recovery guide](docs/FLASHING.md)
  for firmware and layout requirements.
- **Power:** Linux draws power from USB, but net charging is not verified. On a
  computer's USB port with the screen on, the tablet uses more than the port
  supplies and the battery still drains slowly; wall chargers have not been
  measured, and the stock fast-charging protocols are not available under Linux.
  Return to Android to charge; Fastboot is not a charging fallback.
  Backlight-only screen blanking also consumes more power than normal standby;
  system suspend on the power button is opt-in, see [System suspend](docs/SUSPEND.md).
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
| Build the kernel and device components | [Build guide](docs/BUILD.md) |
| Check installation requirements and recovery | [Installation and recovery](docs/FLASHING.md) |
| Install from the release images without building | [Prebuilt release images](docs/FLASHING.md#prebuilt-release-images) |
| Work on the graphics stack | [Graphics integration](docs/GRAPHICS.md) |
| Check suspend and the power button | [System suspend](docs/SUSPEND.md) |
| Check the panel backlight and brightness | [Display and backlight](docs/DISPLAY.md) |
| Bring up or check the sensors | [SSC sensors](docs/SENSORS.md) |
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

Both systems use the same active boot slot; the tested layout uses slot A.
The switcher writes the target system's `boot`, `init_boot` and `vendor_boot`
images as a set, reads them back for verification, then reboots. The other
system's images remain in the switcher storage on the Linux partition.
Routine switching does not change the active slot.

Switching writes the boot partitions. Do not interrupt power or force a restart
during the operation. See [installation and recovery](docs/FLASHING.md) for
requirements and recovery, and the [switcher reference](switch/README.md) for
implementation details.

## Hardware Support

The tables below describe current hardware support and known limitations.
“Working” means tested on hardware within the stated scope. Features under
development are not included in the supported feature set.

✅ Working · 🟡 Partial · 🔧 In development / Awaiting testing · ❌ Unsupported

### Platform, Display and Input

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Boot and storage | SM8750P / UFS | ✅ | Ubuntu boot and storage access work. Dual-boot switching is limited to the tested layout described above. |
| Internal display | Dual DSI / DSC | ✅ | 3392 × 2400 at 120 Hz. Other refresh rates await hardware testing. |
| Touch | Novatek NT36536 | ✅ | Finger input, desktop interaction and login verified. Pen support is tracked separately. |
| GPU and desktop | Adreno 830 / Freedreno / Mesa | 🟡 | GNOME and OpenGL hardware rendering are verified. Vulkan testing triggered a GPU timeout and is unsupported. Sandboxed applications and sustained loads need testing. |
| Brightness | Dual KTZ8868 / one backlight interface | 🟡 | Unified brightness control and blanking are integrated; the slider’s usable brightness range needs physical testing. |
| Magnetic keyboard | Pogo keyboard / touchpad | 🟡 | Keyboard input works. Full key mapping, touchpad gestures and detach/reattach need testing. |
| Active pen | NT36536 pen input | 🔧 | Pen input code is available; position, pressure and buttons await physical testing. |
| Pen charging | CPS8601 | ❌ | Charging, battery reporting and automatic scan control are not implemented. |

### Wireless and USB

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Wi-Fi | WCN7860 / ath12k | ✅ | Networking, automatic reconnect at boot and short transfers work. v0.2.2 enables userspace regulatory hints and includes the ath12k frequency-range fix; packages leave the radio in world domain `00`. 5 GHz uses passive scanning and cannot host a hotspot; roaming, 2.4 GHz hotspot operation and sustained transfers need testing. Changing the country code while associated has caused WLAN firmware crashes; do not do so. |
| Bluetooth | WCN7860 / BlueZ | 🟡 | Controller, firmware, discovery and per-device address verified; keyboard, mouse and headset use remain unverified. |
| USB device mode | USB-C / NCM | 🟡 | USB networking works. Some reconnects failed to restore the connection and required a reboot. |
| USB host peripherals | HID, storage, network and digital audio | 🟡 | Mouse use through the tested dock works without external PD power. The same mouse and USB-A adapter work directly in Android but fail in Linux; other peripherals remain untested. |
| USB storage formats | UAS, exFAT and NTFS3 | 🔧 | Emulated filesystem tests include independent verification of Chinese NTFS filenames. Real drives and desktop mounting remain untested. |
| External display | USB-C DisplayPort Alt Mode | 🟡 | Output on a physical monitor is confirmed. Display-mode selection and hotplug stability still need testing. |
| External display audio | DisplayPort / ALSA / PipeWire | ❌ | Disabled by default: playback configuration prevents microphone discovery with no monitor attached. Playback and hotplug recovery need further work and testing. |

### Audio, Video and Sensors

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Internal microphones | WCD939x / ALSA / PipeWire | 🟡 | Default input and two-channel capture work. With ADC 13 / TX DEC 112, normal speech at about 30 cm peaks around -8 dBFS without clipping. Background-noise performance remains uncharacterized. |
| Speakers | Six AW88261 amplifiers / AudioReach | 🟡 | The opt-in candidate at amplifier value 350 (-2.5 dB) passed listening checks for channel position, loudness and sound quality. Playback remains disabled by default and has no vendor speaker protection. |
| USB-C analog audio | WCD939x headset path | ❌ | Analog adapters and headset detection are not implemented. Digital USB audio is tracked above. |
| Video playback in desktop players | Ubuntu GStreamer packages | ❌ | Showtime, the default player, aborts on a Mesa freedreno assertion when it draws video frames. Other players are untested. |
| Hardware video codecs | Qualcomm Iris | 🟡 | H.264 hardware decoding works on the tablet: a 60-frame test clip matches the software decoder frame by frame. Encoding and use from desktop players need testing. |
| Front and rear cameras | SC820CS / SC1300CS | ❌ | Camera capture and video calls are not implemented. |
| Automatic rotation | SSC / iio-sensor-proxy | 🟡 | Orientation reaches the desktop and the screen rotates in the initial-setup session, but not yet in a normal session even with the switch on. The mount matrix is a candidate and unmeasured. |
| Automatic brightness | SSC ambient light / GNOME | 🟡 | The light sensor reaches GNOME, and with automatic brightness enabled the backlight level adjusted on hardware (1500 → 1805 of 2047). GNOME idle dimming is off because the panel is never blanked automatically. |
| Compass and gyroscope | SSC / iio-sensor-proxy | 🟡 | Heading and angular velocity are read over D-Bus on the installed v0.2.0 system and keep updating after suspend. No desktop application uses them yet. |
| Proximity and Hall | SSC | ❌ | The DSP does not publish the proximity sensor on this unit, and `libssc` has no Hall or SAR implementation. |

### Power, Time and Applications

| Feature | Component / Implementation | Status | Scope and limitations |
|---|---|---|---|
| Power button | Linux input / GNOME | 🟡 | Locks and blanks the display. With `/etc/erhai/power-key-action` set to `suspend`, a press also enters system suspend, and the same button wakes the tablet. Password re-entry after locking needs testing. |
| Volume keys | GPIO / PMIC PON input | ✅ | Volume up reports `KEY_VOLUMEUP` (115); all 10 physical presses passed. Volume down remains mapped to `KEY_VOLUMEDOWN`. |
| CPU frequency and temperature | SCMI / IIO / thermal | 🟡 | Frequency scaling and temperature readings work. Sustained-load thermal control and enclosure-temperature management remain incomplete. |
| Battery reporting | qcom_battmgr / UPower | ✅ | Capacity and runtime estimates available; charging behavior is a separate limitation. |
| Charging in Linux | USB power / vendor firmware | 🔧 | Power is drawn from USB, but net charging is not verified. On a computer's USB port (about 2.5 W) with the screen on, the battery still drains by about 2–3 % per hour. Wall chargers are untested, and the stock fast-charging protocols are not available under Linux. Return to Android to charge. |
| Suspend and resume | Linux power management | 🟡 | Defaults to s2idle. On the installed v0.2.0 system, 300-second RTC-timed suspends in both display modes resumed the display, touch, Wi-Fi and sensors; power-button wake was verified by a contributor. Unplugged standby life and the deepest SoC power states remain open; the firmware-advertised `deep` state is not used by default. |
| RTC | Qualcomm PMIC RTC | 🟡 | Time read/write verified. Clock rollback was observed after restarting and requires time synchronization. |
| Snap applications | AppArmor / snapd / graphics runtime | ❌ | Full confinement and graphical Snap apps are unsupported in this release. The selected kernel does not enable AppArmor. |
| Android applications | Android runtime | ❌ | Waydroid is not integrated. |

## Use and Maintenance

The base system comes from the official Ubuntu Desktop image. Device support is
delivered as separate `erhai-*` packages; Ubuntu packages remain managed by APT.
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
See the [build guide](docs/BUILD.md) and [contribution guide](CONTRIBUTING.md).

## Acknowledgements and License

This project builds on Linux, Ubuntu, GNOME, Freedreno/Mesa and the Linux Qualcomm
community. Device integration draws on work from
[ROCKNIX](https://github.com/ROCKNIX/distribution), OnePlus and LineageOS, and
uses AudioReach and the SSC sensor stack.

Original integration code is licensed under **GPL-2.0-only**, unless a file
states otherwise. The Linux kernel and third-party components retain their own
licenses and authorship. See [LICENSE](LICENSE), [NOTICE](NOTICE), and the
[firmware provenance and distribution restrictions](packaging/firmware/README.md).
