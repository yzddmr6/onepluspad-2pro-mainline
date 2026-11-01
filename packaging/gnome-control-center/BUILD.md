# GNOME Settings

`erhai-settings` adds an “作者” (Chinese) / “Author” group to **Settings →
System → About**, showing `yzddmr6` and a clickable project link. It installs
only `/usr/bin/gnome-control-center`, using `dpkg-divert` to retain Ubuntu's
executable. Removing the package restores that executable. Ubuntu continues
to manage `gnome-control-center` and `gnome-control-center-data`; both are
restricted to the GNOME 50 series.

On a Linux build host with Python 3.11+, sudo, ARM64 QEMU binfmt, dpkg-dev,
GNU tar and `gresource` (Ubuntu: `libglib2.0-bin`):

```sh
sudo env QEMU_CPU=max,pauth-impdef=on python3 tools/build-settings.py \
  --output out/gnome-control-center --jobs 12
python3 tools/build-debs.py --only erhai-settings \
  --settings-build out/gnome-control-center --output out/device-packages
```

Use a new build directory. `source.json` pins Ubuntu's source archives and
our patch; `build-root.json` pins Ubuntu Base 26.04 arm64 and the APT snapshot.
The builder runs the full Ubuntu binary-package build with its standard tests,
saves the program, Ubuntu packages, compiled About UI, logs and `build-info.json`,
and removes the chroot. `--base-archive` accepts a cached original Base archive.

A normal `tools/build-debs.py` invocation includes `erhai-settings`; pass
`--settings-build` if its build output is elsewhere. `erhai-device` depends on
it. Include the resulting `out/device-packages/*.deb` with the other component
packages in the root filesystem's `--device-deb` arguments and in the upgrade
package archive, as described in [the build guide](../../docs/BUILD.md).
