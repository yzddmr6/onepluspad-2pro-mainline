# System suspend: s2idle, the power button and the cover

[中文](SUSPEND.md) · [Project overview](../README.en.md)

This project defaults to `s2idle` (suspend to idle). The firmware also offers `deep` (PSCI
SYSTEM_SUSPEND); the Defaults section explains why it is not the default. This page records
what has been measured on the tablet, how the power button and the cover are wired to it, and
how to measure a suspend yourself.

## Measured on hardware

| | |
|---|---|
| `/sys/power/state` | `freeze mem disk` |
| `/sys/power/mem_sleep` | `s2idle [deep]` before the default was pinned, `[s2idle] deep` after |
| PSCI | `PSCIv1.1 detected`, `OSI mode supported` — the firmware advertises SYSTEM_SUSPEND, which is why the kernel prefers `deep` |
| CPU idle | two states: `WFI` and `cpu-sleep-0` (retention) |
| Suspend cycles | `success: 4`, `fail: 0` over RTC-timed and power-button cycles |
| Wake from s2idle by RTC | works — `pm_wakeup_irq 174` (`c400000.spmi:pmic@0:rtc@6100`) |
| Power-button wake | Works — on the installed v0.6.0 system, three of three presses locked and suspended the tablet and the next press woke it: `pm_wakeup_irq 22` (`pmic_pwrkey`), back to the desktop after unlocking |
| Installed v0.2.0, RTC alarm 300 s | compat and standard display modes: `PM: suspend entry (s2idle)`, slept 293 s, woken by IRQ 174, debug channel back 3 s after the alarm, Wi-Fi 28 s; display, touch and sensors recovered |
| Timekeeping in s2idle | `Timekeeping suspended for 292.961 seconds` on the installed v0.2.0 system |
| Deepest power states | Installed v0.6.0 candidate, USB connected, 23 consecutive 10-minute RTC-timed suspends, each preceded by a one-minute full CPU load and repeated GPU wake-ups: 98.0–98.9 % of the time in CX collapse; DDR entered self-refresh as well; every suspend was woken by the RTC, Wi-Fi and the keyboard recovered each time, and both cameras streamed after every fifth suspend (v0.5.0: 26 × 9 minutes, about 98 %) |
| Wake by opening the cover | works — `pm_wakeup_irq` is the lid switch (`msmgpio 97 Cover`); the tablet suspends about one second after the cover closes |

The power button is a wake source without any devicetree change:
`pm8941-pwrkey.c` reads `wakeup-source` *or* takes the per-compatible default, and
`qcom,pmk8350-pwrkey` maps to `pon_gen3_pwrkey_data.wakeup_source_default = true`, so the
driver calls `device_init_wakeup(dev, true)` and arms its IRQ on suspend. The wake then
travels through the SPMI PMIC arbiter, whose irqchip implements `irq_set_wake`, to the PDC
line the SPMI node already points at.

## Defaults

The shared command line in `tools/lib/boot_profiles.py` pins `mem_sleep_default=s2idle`.
Without it the kernel prefers the firmware-advertised `deep`. Deep suspend has completed
300-second RTC-timed cycles on this board with the display, touch, Wi-Fi, Bluetooth, battery
and sensors recovering, but in deep any ADSP message on the IPCC/glink interrupts completes a
full resume, which caused early wakes. s2idle handles such interrupts without leaving suspend.

## Power button

The matching GNOME Settings Daemon now handles the power key, with
`power-button-action='lock'` as the default. Choose Lock Screen or another action
in Settings > Power. Locking does not explicitly request system suspend; cover
and idle suspend retain their own policies. Existing personal GNOME settings
are not forcibly changed.

The former device service that exclusively grabbed the input has been removed.
`/etc/erhai/power-key-action` and `/run/erhai/power-key-action` no longer apply;
manage the action through GNOME's power settings. logind keeps
`HandlePowerKey=ignore` to avoid duplicate handling before the desktop takes over.

## Idle policy

Idle dimming, blanking and automatic suspend inherit the distribution's defaults. The
Ubuntu 26.04 desktop image used by this project supplies these values for an unchanged
user profile:

| Condition | Default behavior |
|---|---|
| Idle dimming | Enabled (`idle-dim=true`), timed by GNOME before blanking |
| 5 minutes idle | Blank and lock the screen (`idle-delay=300`, locking enabled) |
| 15 minutes idle on battery | Request suspend (`sleep-inactive-battery-type='suspend'`, timeout `900`) |
| Idle on external power | Blank normally; no automatic suspend (`sleep-inactive-ac-type=nothing`) |

These are idle deadlines, not delays added after blanking. GNOME respects application
inhibitors and user settings; the power source is the one reported by UPower. See the
[GNOME power defaults](https://gitlab.gnome.org/GNOME/gnome-settings-daemon/-/blob/50.0/data/org.gnome.settings-daemon.plugins.power.gschema.xml.in)
and [Ubuntu overrides](https://git.launchpad.net/ubuntu/+source/ubuntu-settings/tree/debian/ubuntu-settings.gsettings-override?h=ubuntu/resolute).
The device package does not replace those idle defaults or erase personal settings.

Use **Settings → Power** to choose different times. If an existing account explicitly
saved the previous never-blank or never-suspend settings, reset just these keys from a
terminal in that user's desktop session (without `sudo`) to inherit the defaults:

```sh
gsettings reset org.gnome.desktop.session idle-delay
for key in idle-dim sleep-inactive-ac-type sleep-inactive-ac-timeout \
           sleep-inactive-battery-type sleep-inactive-battery-timeout; do
    gsettings reset org.gnome.settings-daemon.plugins.power "$key"
done
```

After upgrading the device package, log out and back in before checking the policy.

## The cover

The magnet of the keyboard cover or a case sits over a hall switch, which the kernel reports as
a lid switch (`SW_LID`). On external power the cover locks the screen. On battery, closing it makes logind suspend the system (`HandleLidSwitch=suspend`
in `/etc/systemd/logind.conf.d/90-erhai-power.conf`); opening it wakes the system through the same
switch, and the desktop lights up the lock screen. With an external display connected,
the normal desktop/logind policy inhibits cover-triggered suspend. GNOME power settings
control the power-button action; an external display does not change the idle configuration above.

* Touch and pen input are ignored while the cover is closed: the `erhai-cover` service sets the
  kernel's input inhibit on them. A cover landing on the panel touches it, and without the
  inhibit those touches interrupt the screen lock before suspend, so the system only suspends
  once logind's delay limit (about 30 seconds) runs out.
* The wake on opening is only armed when the system suspends with the cover closed. With the
  cover open the GPIO is high, and the wake-up controller reports an edge on it after CX power
  collapse; armed, that edge would wake the system at once. After suspending with the power
  button or idle policy with the cover open, closing and then opening the cover therefore
  does not wake the tablet; press the power button instead.

## Measuring a suspend

```sh
cat /sys/power/mem_sleep                       # s2idle [deep] / [s2idle] deep
cat /sys/kernel/debug/suspend_stats            # success, fail, last_failed_dev
cat /sys/power/pm_wakeup_irq                   # the IRQ that ended the suspend
for w in /sys/class/wakeup/wakeup*; do
  printf '%s %s wc=%s ac=%s ec=%s\n' "$(basename $w)" "$(cat $w/name)" \
    "$(cat $w/wakeup_count)" "$(cat $w/active_count)" "$(cat $w/event_count)"
done
```

`/sys/kernel/debug/qcom_stats` (driver built as `CONFIG_QCOM_STATS`, node already present
in `sm8750.dtsi`) reports per-subsystem sleep counters and is the way to tell how deep a
suspend actually went. These are the increments across one 9-minute suspend on v0.5.0
(`Accumulated Duration` counts at 19.2 MHz; divide by 19200000 for seconds):

```
cxsd  Count: +103   Accumulated Duration: +532 s   ← CX collapse
ddr   Count: +103   Accumulated Duration: +532 s   ← DDR self-refresh
aosd  Count: +0                                     ← no AOSS sleep with USB connected
```

To measure battery drain across a suspend, use a `systemd-sleep` hook under
`/usr/lib/systemd/system-sleep/` and record the battery before and after. Note that
`rtcwake` writes to `/sys/power/state` directly and therefore **bypasses systemd**, so
sleep hooks do not run for those suspend cycles; use `systemctl suspend`, a power button configured for suspend,
or an armed RTC alarm instead.

To attribute a wake, compare `pm_wakeup_irq` and the per-source counters above. A source
whose `wakeup_count` does not move did not wake the system, even if its IRQ fired.

## Limits

* No AOSS sleep with USB connected (see above); unplugged standby drain has not been measured
  yet.
* `deep` (PSCI SYSTEM_SUSPEND) is not used by default. Earlier tracing on this board found deep
  suspends ending early with no armed wake-up IRQ: the IPCC summary interrupt is
  `IRQF_NO_SUSPEND` and its irqchip sets `IRQCHIP_SKIP_SET_WAKE`, so a signal from a remote
  processor can bypass `pm_system_irq_wakeup()` entirely.
* Unplugged standby life has not been measured yet.
* The proximity and SAR sensors remain unavailable on this board.

## References

* postmarketOS wiki, *Qualcomm Snapdragon 845/850* — "Qualcomm platforms currently don't
  have a real suspend mode"; wakeirqs and `IRQF_NO_SUSPEND` semantics; waking by
  `wakeup_count`.
* Snapdragon X Elite suspend notes (Lenovo Yoga Slim 7x) — `deep` present but resume
  broken, hibernation not built, and `qcom_stats` counters as the depth measurement.
* linux-surface issue 2078 — how to tell "the IRQ fires" from "the IRQ wakes the system"
  (`wakeup_count` stays at 0 while `event_count` moves).
