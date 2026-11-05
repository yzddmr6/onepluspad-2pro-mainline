# Daily-use policies

This candidate enables internal speaker discovery, three GNOME power modes
and compressed RAM swap. Reboot after upgrading the matching kernel and
device packages. Hardware acceptance of this candidate is still pending.

## Speakers

UCM exposes `Speaker` in the `HiFi` verb on each boot. PipeWire can select it
without a startup helper; UCM reapplies the amplifier and DSP levels whenever
the route opens, including after resume. Existing user choices of an external
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
checks do not establish continuous full-volume safety. Default-on release
acceptance is pending. No other board's amplifier configuration is used.

Hardware references: [AWINIC AW88261 data sheet, pp. 22, 24, 34](https://doc.awinic.com/doc/20230609wm/c815e155-60b7-40fb-889b-676b02e67d0a.pdf),
the board's `packaging/firmware/awinic/erhai/aw88261_acf.bin`, and the
`aw88261_dev_reg_update()` implementation in the pinned kernel.

## GNOME power modes

Ubuntu `tuned-ppd` supplies GNOME's `net.hadess.PowerProfiles` interface and
replaces the conflicting `power-profiles-daemon` package. Select the mode in
GNOME Settings or quick settings. Both mains and battery mappings use the
same board profile; the default is Balanced.

| GNOME mode | TuneD profile | CPU0–5 max (kHz) | CPU6–7 max (kHz) | GPU max (Hz) |
|---|---|---:|---:|---:|
| Power Saver | erhai-power-saver | 1785600 | 1958400 | 342000000 |
| Balanced | erhai-balanced | 2400000 | 2841600 | 660000000 |
| Performance | erhai-performance | 3532800 | 4089600 | 1100000000 |

All profiles retain `schedutil`, CPU minima 384000/1017600 kHz and GPU minimum
160000000 Hz. These are board-supported OPPs. Balanced caps both clusters and
the GPU below their maximum to reduce simultaneous-load heating; Performance
permits the observed board maximum. No boost control or thermal trip is
changed. Firmware and thermal limits may lower the effective maximum.
These policy choices still need device validation; they are not measured
battery-life or sustained-performance claims.

The profiles live in `/usr/lib/tuned/profiles/erhai-*`. The separately owned
`/etc/tuned/erhai-ppd.conf` is a conffile. The `tuned-ppd.service` drop-in binds
it over Ubuntu's `/etc/tuned/ppd.conf` only inside the service, leaving the
original distribution file untouched. Administrator overrides belong under
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
otherwise boot can wait for an absent zram device. Device support depends on
`erhai-kernel-zram`, provided by a kernel payload only after the package builder
checks swap, zram and zstd support. Installing that payload does not activate
the kernel selector, allowing a RAM boot before persistent activation. This
dependency does not verify the currently booted kernel: boot the matching
candidate before runtime checks.

Use `zramctl`, `swapon --show`, `/proc/meminfo` and
`/sys/block/zram0/comp_algorithm` to inspect size, priority and compression.
The size limit describes logical swap capacity; RAM is allocated as used.
