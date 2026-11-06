# Panel backlight and the desktop brightness paths

[中文](DISPLAY.md) · [Project overview](../README.en.md)

The panel is driven by a single `led-backlight` device (both KTZ8868 chips behind one
backlight), and `erhai-display-power` switches that device's `bl_power` to blank the screen
without tearing down the display link. This note is about the two desktop-facing paths around
it, which are easy to mix up.

## Where the "Automatic Brightness" switch lives

It is **not** in the top-right quick-settings menu — that menu only has the brightness
slider. The switch is a row in **Settings → Power**, and GNOME's control centre shows it only
when both of these hold (`panels/power/cc-power-panel.c`):

* the sensor proxy reports `HasAmbientLight` (true on this tablet), and
* `has_brightness_control` — a D-Bus proxy for the **session-bus** object
  `org.gnome.Shell.Brightness` (`/org/gnome/Shell/Brightness`) could be created.

Two notes:

* the control centre evaluates that once, when the panel is constructed, and the proxy is
  `DO_NOT_AUTO_START`, so a Settings window opened before the shell exported the name shows no
  row for that instance — closing and reopening is enough;
* the ALS behaviour is independent of the switch's visibility. The proxy was seen streaming
  ambient light (`iio-sensor-proxy` logs `Streaming 'ambient_light' requests`), and with
  `ambient-enabled` on, the level followed the room (measured 1500 → 1805 of 2047 while the
  room light stayed put).

## The brightness write path, and its one requirement

GNOME writes the backlight through logind rather than through sysfs:

```c
/* mutter: src/backends/meta-backlight-sysfs.c */
if (backlight_sysfs->session_proxy)          /* logind has SetBrightness */
        call_set_brightness (...);           /* ← the path taken on this tablet */
else
        pkexec mutter-backlight-helper ...;  /* only when logind answers UNKNOWN_METHOD */
```

logind does the write itself, from a forked process running as root
(`src/login/logind-brightness.c`), so the attribute's permission bits are irrelevant — neither
`uaccess` (sysfs carries no extended attributes, `setfacl` answers `Operation not supported`)
nor a group change can affect this.

What decides it is one line in systemd:

```c
/* src/login/logind-session-dbus.c:693 */
if (s->seat->active != s)
        return sd_bus_error_set (error, BUS_ERROR_NOT_YOUR_DEVICE,
                                 "Session is not in foreground, refusing.");
```

The session must be its seat's **active session** when mutter initialises — and mutter tries
once, keeping the failure for the rest of the session. Measured: a session that started while
the seat still pointed at the previous greeter logged this once at startup and never retried;
a session that was the seat's active session from the start logged nothing. The slider itself
stays on screen either way — what is at stake is whether its writes reach the hardware.

## Related

* Idle dimming and blanking follow Ubuntu defaults; see [System suspend](SUSPEND.en.md)
  for timings, automatic suspend and user settings.
* Blanking and `bl_power` are handled by `erhai-display-power`; nothing here changes them.
