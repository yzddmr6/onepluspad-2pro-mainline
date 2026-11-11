# Shared Ubuntu GNOME packages

The source of truth is the Xiaomi Pad 8 Pro repository's `ubuntu/` directory.
`shared/` is an unmodified import at the commit in `provenance.json`; every file
has a SHA-256 digest. Do not edit these copies or maintain separate patches.
`binaries.json` pins the four runtime debs built from that source. Preserve the
shared recipe's licenses, author information and Ubuntu authentication chain.

Run `python3 tools/shared_gnome.py --packages /path/to/runtime-debs` before image
assembly. Pass all four debs to `tools/build-desktop-rootfs.py --device-deb`, once
per deb. The builder verifies their versions and hashes and requires the whole
group whenever `erhai-settings` or `erhai-device` is selected.

`erhai-settings` supplies `/usr/share/gnome-control-center/port-author.ini`, the
exact APT pins, and migration from its former executable diversion. The shared
binary reads that configuration; it has no built-in device name or project URL.
The shared GSD handles the power key, with `lock` as the device's default action.
