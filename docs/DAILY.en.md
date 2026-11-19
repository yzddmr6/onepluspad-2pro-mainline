# Daily-use policies: speakers, power modes and compressed swap

[中文](DAILY.md) · [Project overview](../README.en.md)

The device packages make the internal speakers available by default and add
three GNOME power modes and compressed RAM swap. Upgrade the kernel and device
packages together, then reboot.

## Speakers

UCM exposes `Speaker` in the `HiFi` verb on each boot. PipeWire can select it
without a startup helper. The HiFi verb establishes FE-to-BE routes before
ACP probes the PCMs; Speaker activation then sets amplifier and DSP levels.
The persistent opt-out disables the playback route while retaining Mic. Existing user choices of an external
output remain under WirePlumber's normal policy.

`sudo erhai-audio-speaker disable` withdraws the speakers persistently;
`sudo erhai-audio-speaker enable` restores them. Both restart active users'
sound servers. `status` reports the policy and current controls. An opt-out
survives an upgrade or package removal; purging `erhai-audio` clears it.

The six amplifier controls remain at 350 (-2.5 dB), matching the original
ACF Music profile; DSP gain stays at 8192 (Q13 unity). WirePlumber sets
`channelmix.max-volume = 1.0` on this board's speaker sink. This clamps that
sink's software volume gain, **not** the amplitude or energy of the mixed
signal, and is not a speaker protection algorithm. Direct ALSA access and
administrator changes can bypass this policy. The ALSA control itself still
allows values up to 360 (0 dB).

AW88261 has chip over-temperature, short-circuit/over-current and supply
voltage protections. The unchanged board ACF enables peak AGC on Amp5 and
Amp6, but not Amp0–3. The vendor DSP excursion/voice-coil-temperature
protection and per-speaker filtering are absent. Therefore matching the
stock volume does not establish equal safety, and prior short listening
checks do not establish continuous full-volume safety. Default-on playback
has passed listening checks. No other board's amplifier configuration is used.

Hardware references: [AWINIC AW88261 data sheet, pp. 22, 24, 34](https://doc.awinic.com/doc/20230609wm/c815e155-60b7-40fb-889b-676b02e67d0a.pdf),
the board's `packaging/firmware/awinic/erhai/aw88261_acf.bin`, and the
`aw88261_dev_reg_update()` implementation in the pinned kernel.

## GNOME power modes

Ubuntu `tuned-ppd` supplies GNOME's `net.hadess.PowerProfiles` interface and
replaces the conflicting `power-profiles-daemon` package. Select the mode in
GNOME Settings or quick settings. Both mains and battery mappings use the
same board profile; the default is Balanced.

| GNOME mode | TuneD profile | CPU0–5 min / max (kHz) | CPU6–7 min / max (kHz) | GPU min / max (Hz) | Boost |
|---|---|---:|---:|---:|---:|
| Power Saver | erhai-power-saver | 384000 / 1785600 | 1017600 / 1958400 | 160000000 / 342000000 | 0 |
| Balanced | erhai-balanced | 1785600 / 3532800 | 1689600 / 4320000 | 160000000 / 1100000000 | 1 |
| Performance | erhai-performance | 2918400 / 3532800 | 2841600 / 4320000 | 160000000 / 1100000000 | 1 |

- All profiles use `schedutil`.
- **Balanced** caps no frequency; the prime cores' 4204800 and 4320000 kHz
  boost points stay enabled, although the governor currently asks for at most
  4089600 kHz. A busy core does not run below about 1.7 GHz, so scrolling
  and animations do not wait for the governor to ramp up from the lowest
  points; idle cores still sleep.
- **Performance** keeps the same range and raises the lowest frequency a busy
  core runs at to about 2.9 GHz. Short bursts (opening an app, scrolling, the
  thread that feeds the GPU) then start fast instead of waiting for the
  governor to ramp up. Idle cores still sleep.
- **Power Saver** caps the CPU and GPU, and caps utilization floors at 320
  (`kernel.sched_util_clamp_min`), which is what the six smaller cores deliver
  at their capped frequency. A larger floor, such as the one a virtual machine
  asks for, would otherwise count as fitting no capped core and be crowded
  onto the two prime cores.
- In every mode, real-time threads (audio, the compositor) get no utilization
  floor by default (`/usr/lib/sysctl.d/50-erhai-uclamp.conf`).

CPUCP firmware and thermal
limits still apply; no thermal trip is changed.

The profiles live in `/usr/lib/tuned/profiles/erhai-*`. The separately owned
`/etc/tuned/erhai-ppd.conf` is a conffile. The `tuned-ppd.service` drop-in binds
it over Ubuntu's `/etc/tuned/ppd.conf` only inside the service, leaving the
original distribution file untouched. Once its conffile is configured, the
package restarts enabled PPD services, including a service that failed during
dependency installation. Disabled or masked PPD services remain stopped.
Administrator overrides belong under
`/etc/tuned/profiles/`. `tuned-adm active` and `sudo tuned-adm verify` inspect
the running profile; GNOME switching should be tested through its D-Bus API,
not inferred from a direct `tuned-adm profile` command alone.

Removing device support clears its profiles from TuneD's saved selection
(using the distribution balanced profile if none remain) and reloads running
TuneD/PPD services with the distribution mapping. Reboot after removal to
recreate swap with the distribution zram policy. Purging also removes the board PPD conffile. The Ubuntu packages
remain installed unless explicitly removed through APT.

## Compressed swap

Ubuntu `systemd-zram-generator` creates `/dev/zram0` with zstd compression,
priority 100 and size `min(ram / 2, 8192)` MiB, where `ram` is usable kernel
MemTotal. A marketed 16 GB device normally gets slightly less than 8 GiB.
There is no custom zram service and no backing-device writeback.

The kernel must provide `CONFIG_ZRAM=m`, `CONFIG_ZRAM_BACKEND_ZSTD=y` and
`CONFIG_ZRAM_DEF_COMP_ZSTD=y` (which also selects zsmalloc). Older erhai
kernels without zram must be upgraded before enabling the generator;
otherwise boot can wait for an absent zram device. Device support depends on this
release's kernel image package, `erhai-kernel-image-<release>`; the package
builder checks that the kernel configuration provides swap, zram and zstd, and
refuses to build otherwise. Installing the image package does not activate the
kernel selector, allowing a RAM boot before persistent activation. This
dependency does not verify the currently booted kernel: boot the matching
kernel before runtime checks.

Use `zramctl`, `swapon --show`, `/proc/meminfo` and
`/sys/block/zram0/comp_algorithm` to inspect size, priority and compression.
The size limit describes logical swap capacity; RAM is allocated as used.
