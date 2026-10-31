# System suspend: s2idle, the power button and the cover

[中文](SUSPEND.zh-CN.md) · [Project overview](../README.md)

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
| Wake from s2idle by the power button | works — `pm_wakeup_irq 21` (`pmic_pwrkey`) |
| Installed v0.2.0, RTC alarm 300 s | compat and standard display modes: `PM: suspend entry (s2idle)`, slept 293 s, woken by IRQ 174, debug channel back 3 s after the alarm, Wi-Fi 28 s; display, touch and sensors recovered |
| Timekeeping in s2idle | `Timekeeping suspended for 292.961 seconds` on the installed v0.2.0 system |
| Deepest power states | Installed v0.5.0 candidate, USB connected, 26 consecutive 9-minute RTC-timed suspends: about 100 CX collapses and about 532 s of CX collapse per suspend, about 98 % of the time asleep; DDR entered self-refresh as well; every suspend was woken by the RTC, and Wi-Fi, Bluetooth, the keyboard and touch recovered |
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

By default the button locks and blanks the display; it does not suspend. That is
deliberate: the device package's `erhai-power-key` service grabs the key's evdev node so
that waking restores the display without clearing the lockscreen or the greeter, and the
desktop's own power-button action is kept inert while it runs.

System suspend is opt-in, one file:

```sh
echo suspend > /etc/erhai/power-key-action      # takes effect on the next press
rm /etc/erhai/power-key-action                  # back to lock-and-blank only
```

With the marker present, a press locks and blanks as before and then requests `systemctl
suspend`. Waking is again a single press: the resume path has already restored the display, so
the press that resumes the tablet must not be read as "the display is on, blank it again".
`erhai-suspend-cycle.sh` marks the cycle in its pre phase, before the tablet suspends, and the
service treats the next press as display restore only if it arrives within 15 s of the resume,
clearing the flag as it consumes it. The pre phase is what makes it reliable: a flag written on
resume is racy, because userspace is thawed before that hook runs, so the service can read the
resuming press first and suspend again — measured on hardware, 5 of 12 presses were handled
correctly with a post-phase marker. The flag does not rely on clocks: an early RAM-image
measurement saw `CLOCK_MONOTONIC` keep running across s2idle, while the installed v0.2.0
system logs `Timekeeping suspended for 293 seconds`, so clock behaviour is no dependable signal.

`/run/erhai/power-key-action` is read too and takes precedence, so an image or a test can
enable it for one boot.

## The cover

The magnet of the keyboard cover or a case sits over a hall switch, which the kernel reports as
a lid switch (`SW_LID`). Closing the cover makes logind suspend the system (`HandleLidSwitch=suspend`
in `/etc/systemd/logind.conf.d/90-erhai-power.conf`); opening it wakes the system through the same
switch, and the desktop lights up the lock screen.

* Touch and pen input are ignored while the cover is closed: the `erhai-cover` service sets the
  kernel's input inhibit on them. A cover landing on the panel touches it, and without the
  inhibit those touches interrupt the screen lock before suspend, so the system only suspends
  once logind's delay limit (about 30 seconds) runs out.
* The wake on opening is only armed when the system suspends with the cover closed. With the
  cover open the GPIO is high, and the wake-up controller reports an edge on it after CX power
  collapse; armed, that edge would wake the system at once. After suspending with the power
  button, closing and then opening the cover therefore does not wake the tablet; press the power
  button.

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
sleep hooks do not run for those suspend cycles; use `systemctl suspend`, the power button
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
