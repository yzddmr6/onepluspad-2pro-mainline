# Keyboard cover Esc key investigation

Status: `两条通路均已真机验证` (pogo-serial fix on
`fix/pogo-esc-ac-back-v7.2.15`, PR `yzddmr6/linux-sm8750-erhai#9`, working on
kernel `7.2.15-erhai-dev-gaa4213ee0b44-a971763d7` installed 2026-11-12;
Bluetooth UHID path fixed 2026-11-13 by hwdb rule, now shipped in
`erhai-device-support` at `/usr/lib/udev/hwdb.d/99-erhai-pogo-esc.hwdb`,
verified via evtest and in GNOME; suspend/resume not yet exercised)

## Bluetooth path fix (2026-11-13)

The firmware sends Esc as consumer usage `0x0224` (AC Back) on **both**
transports. Over Bluetooth the key lands on the second input device,
`OnePlus Pad 2 Pro Keyboard Consumer Control`, where generic `hid-input`
maps `0x0c0224` to `KEY_BACK`. The kernel driver fix cannot reach this path;
the distro mechanism for it is a hwdb keymap. Installed
`/etc/udev/hwdb.d/99-oneplus-pogo-esc.hwdb`:

```
evdev:name:OnePlus Pad 2 Pro Keyboard Consumer Control:*
evdev:input:b0005v22D9p3869*
 KEYBOARD_KEY_c0224=esc
```

Verified: `evtest` on the Consumer Control device shows
`MSC_SCAN c0224 -> KEY_ESC` press/release.

Two traps worth remembering: this ARM64 host has no DMI modalias, so the
udev-generated name key ends at the trailing colon — the pattern must end in
a bare `*`, not `:input:…`; and `udevadm trigger
--sysname-match="input/event*"` silently matches nothing because sysname is
`event9` — replay with `echo add > /sys/class/input/eventN/uevent`.

Shipped in `erhai-device-support` (2026-11-14): the same rule lives at
`packaging/erhai-device-support/tree/usr/lib/udev/hwdb.d/99-erhai-pogo-esc.hwdb`;
`postinst` rebuilds the hwdb (`systemd-hwdb update`), reloads udev and
replays remove+add on the event nodes of every `0005:22D9:3869.*` HID
device, so an already paired keyboard picks up the mapping and the
`ID_INPUT_KEYBOARD` classification without re-pairing; `postrm` refreshes
the database on removal. Verified on this unit by installing the file from
the package payload, dropping the `/etc` drop-in, replaying the postinst
block and re-checking `ID_INPUT_KEYBOARD=1` plus `systemd-hwdb query`.
Guarded by `tests/test_pogo_esc_hwdb.py` (packaged rule and script logic)
and `tests/test_pogo_keyboard_esc.py` (kernel driver table).

Note on this unit: installing the built `erhai-device-support` deb via apt
currently fails dependency resolution because the tree's control file is on
the v0.8.1 line and pins `gnome-settings-daemon (= 50.0-1ubuntu1+piano2)`,
which is not installed here yet; the file above was placed manually from
the deb payload and will be owned by the package once the v0.8.1 batch
lands.

## Environment (recorded 2026-10-29)

- Integration repo: `main` @ `3a93f5b`, working tree clean at start.
- `kernel/source.json`: `erhai/v0.4` @ `147558188897c27a1e50eb2ffe950a04435ac45f`.
- Running kernel: `7.2.10-erhai-dev-g147558188897-a3e7cb8b9`; package
  `erhai-kernel 0.4.0+g147558188897.b4ac6e711`. Manifest and installed kernel agree.
- `kernel/linux` is not checked out locally. The driver was fetched at the pinned
  commit from the kernel repo (`drivers/input/keyboard/oneplus-pogo-keyboard.c`, 1332 lines).
- Keyboard: `OnePlus Pad 2 Pro Keyboard` (input5), firmware `KA030_B_1.2.0_TP_A_13`,
  attached at boot with no driver errors in `journalctl -k`.

## Findings

1. Mapping is present and correct: `pogo_kb_hid_keys[0x29] == 1 (KEY_ESC)`;
   neighbours are right (0x28 = 28 Enter, 0x2a = 14 Backspace).
2. `KEY_ESC` is in the live capability bitmap of input5
   (`/sys/class/input/input5/capabilities/key`), so registration is fine.
3. `pogo_kb_report_keys()` reports press when a usage > 3 appears and release when it
   disappears. `pogo_kb_key_code()` only diverts Fn-layer usages
   (0x46, 0x68, 0x6b, 0x6c, 0x73); 0x29 is not among them.
4. Esc is not intercepted by the Fn path: `POGO_KB_HID_FN` is 0x72.
5. No GNOME `Escape` shortcut, no keyd/xremap-style service, and no xkb options
   (`xkb-options = []`) are configured for this user.

So the earliest layer that could fail is below the driver (keyboard firmware sends a
different usage or no report, or a frame is dropped by CRC/framing) or above evdev
(libinput/GNOME/app). Source alone cannot tell which. The raw usage has not been observed.

## Not yet done (blocked)

- Real-device evdev capture: `/dev/input/event*` is root:input and this user is not in
  `input`; `sudo` needs a password; `evtest`/`wev` are not installed.
- No kernel was rebuilt and nothing was installed or rebooted. No patch is justified yet.

## Diagnostic for the user

```sh
sudo apt install -y evtest
sudo evtest /dev/input/by-path/*serial0-0*kbd* 2>/dev/null || sudo evtest   # pick "OnePlus Pad 2 Pro Keyboard"
```

Press and release: Esc, a letter, the magnifier key, Enter. Expected for Esc:
`EV_KEY KEY_ESC (1) value 1`, then `value 0`. Interpretation:

| evtest result | Layer | Next step |
|---|---|---|
| Correct Esc events | libinput/GNOME/app | Check `wev`, `libinput debug-events`, the failing app |
| Different key code | Mapping or firmware usage | Add a dev-only `dev_dbg` of the raw usage, compare with vendor driver |
| No event for Esc, other keys fine | Firmware report/frame drop | Enable dyndbg for the driver (`CRC error`, `frame without end code`) |

## Acceptance still required on hardware

Esc press/release in evtest, in GNOME and an app; letters, modifiers, magnifier/Fn and
Fn-layer keys unchanged; detach/reattach; sleep/wake; cold boot.

## Rollback

Nothing was installed, so the current installation is unchanged.
