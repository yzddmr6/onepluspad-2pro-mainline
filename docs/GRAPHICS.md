# Graphics builds and integration

## Mesa build and device package

`packaging/mesa/source.json` pins the original Mesa archive and two patches: the
unmodified upstream A830v1 device-table entry, and a freedreno fix, not yet
upstream, that makes the texture state seqno allocator thread-safe. Without it,
GTK drawing GStreamer video frames could abort on the `fd6_texture_state`
assertion. `tools/build-mesa.py` checks all hashes and builds natively on
ARM64. It installs only into an output staging tree; it does not replace the
host's graphics libraries. `tools/package-mesa.py` turns a verified desktop
build into the separately removable `erhai-mesa` package.
The patches keep their authors and the affected files' MIT license;
Mesa's own `docs/license.rst` and per-file notices govern the source archive.
This repository's GPL license applies to its build tooling, not to Mesa.

On an Ubuntu ARM64 development system, the build dependencies are:

```sh
apt install build-essential meson ninja-build pkg-config libdrm-dev \
  libexpat1-dev python3-mako python3-ply python3-yaml bison flex \
  zlib1g-dev libzstd-dev libelf-dev libwayland-dev libwayland-egl-backend-dev \
  wayland-protocols libx11-dev libx11-xcb-dev libxcb-dri2-0-dev \
  libxcb-dri3-dev libxcb-present-dev libxcb-randr0-dev libxcb-sync-dev \
  libxcb-xfixes0-dev libxcb-glx0-dev libxcb-shm0-dev libxshmfence-dev \
  libxxf86vm-dev libxrandr-dev libglvnd-dev glslang-tools python3-packaging \
  libvulkan-dev vulkan-tools
tools/build-mesa.py --source-archive mesa-26.2.3.tar.xz \
  --profile desktop --output out/mesa-desktop --jobs 2
tools/package-mesa.py --build-output out/mesa-desktop --output out/mesa-debs
```

On a host that is not ARM64, `tools/build-mesa-root.py --output DIR` runs the
same two tools in a disposable Ubuntu 26.04 arm64 build root (qemu-user binfmt
and an unprivileged user namespace, no root). The build root and its package
versions are pinned in `packaging/mesa/build-root.json`; the output directory
receives the package, its manifest and a record of the build root.

The package owns libraries under `/usr/lib/erhai/mesa` and a systemd user
environment generator. The generator selects them for every user manager (the
GDM greeter's and each user's, so GNOME Shell and its applications) only while
the Adreno GPU is bound to its kernel driver; otherwise the session uses
Ubuntu's Mesa and its software renderer, which this build does not include. It
decides at session start; a GPU failure later in a session is not caught. EGL is
selected with `__EGL_VENDOR_LIBRARY_DIRS`, which sandboxed applications with
their own graphics runtimes extend rather than lose.

The desktop package enables OpenGL and GLES. Turnip is excluded after hardware
validation triggered a GPU timeout. Upgrading from the experimental Vulkan
package removes its ICD diversion and restores Ubuntu's original loader entry;
fresh installations do not divert it. The package continues to leave Ubuntu's
Mesa libraries under APT ownership. Dependencies and source/build hashes are
recorded in the package manifest.

Install the resulting deb with `sudo apt install ./out/mesa-debs/erhai-mesa_*.deb`, then cold boot
to apply the new environment to every user manager. Removal with `apt remove erhai-mesa` restores the distribution selection
after the next cold boot. Ubuntu Mesa currently lacks this chip entry, so removal
restores software rendering. Sandboxed applications with their own graphics
runtimes need separate validation; this package does not replace their runtimes.

The `probe` profile supplies minimal GBM/EGL/GLES; `desktop` also builds the
Wayland, X11 and GLVND interfaces. The separate core24 candidate still includes
Turnip and remains unvalidated on hardware. Neither desktop profile builds
a software renderer. These are development profiles, not a complete supported
desktop package. The manifest records build inputs, native package versions,
staged file hashes and symlinks. Compatible outputs are incremental and locked
against concurrent writers; changed inputs require a fresh output directory.
Keep the distribution's working desktop available while validating the staged
driver. Hardware drawing, compositor correctness and physical display output
are separate checks.

## Graphics for core24 snaps

This experimental provider requires a separately prepared kernel and Snap
environment with working confinement. The v0.2.2 kernel does not enable AppArmor;
installing this provider alone does not make Snap applications supported.

A desktop deb cannot supply libraries inside a snap with its own graphics runtime.
The desktop build uses Ubuntu 26.04 and requires its newer glibc. The separate
`gpu-2404` profile builds Freedreno, Turnip and softpipe against Ubuntu 24.04 and
packages a standard `gpu-2404` content provider named `erhai-mesa-2404`:

```sh
tools/build-mesa-root.py --target gpu-2404 --work out/mesa-core24-build \
  --output out/mesa-core24-package --jobs 6
```

For the architecture-independent NIR Python generator, `--native-nir` uses a compatible
host Python executable in Mesa's configured Ninja rule and records its
version/hash, template-library versions, Ninja hash and generated C hash. The
host needs Python 3.10 or newer, Mako and MarkupSafe. For the amd64 desktop build, the helper downloads the
Ninja version pinned in `packaging/mesa/native-tools.json`, matching the SDK
build-log format. Use `--ninja PATH` to provide a matching executable yourself. This avoids running a large
Python generator under CPU emulation. Target C/C++ compilation and packaging
remain in the ARM64 SDK.

A failed compile can continue with `--resume` and the same work/target/source.
This preserves that attempt's frozen compile recipe and compatible objects;
it does not pick up later recipe/source changes. Select a new work directory
for changed inputs. The build record hashes the recipe actually copied into
the SDK, including when it differs from a newer checkout.

`packaging/mesa/build-root-core24.json` pins the Ubuntu Base archive, signed APT
snapshot and build-only Meson/Wayland protocol inputs. The source and A830 patch
are shared with the desktop build. The provider contains Mesa, GLVND/Vulkan
loaders, the SDK runtime dependency closure, notices and build provenance;
core24 continues to supply glibc and its loader. It has no application or daemon.
The provider wrapper follows the [Canonical gpu-2404 interface](https://github.com/canonical/gpu-snap)
and preserves the consuming snap's library precedence. Its data layout includes
`libdrm`, `drirc.d` and `X11`, as used by current core24 Firefox/desktop consumers.
It does not provide video acceleration or support snaps built for other bases.

This is a development candidate. Building and unpacking it, or rendering with
softpipe under QEMU, cannot validate Adreno hardware, snap confinement or browser
output. Before selecting it, retain the existing provider and record the actual
consumer's base, plug and current connection with `snap info` / `snap connections`.
For a compatible Firefox installation, local acceptance uses:

```sh
sudo snap install --dangerous ./out/mesa-core24-package/erhai-mesa-2404_*.snap
sudo snap connect firefox:gpu-2404 erhai-mesa-2404:gpu-2404
```

Close and reopen Firefox, then verify the selected renderer and real page/video
output. Reconnect the recorded previous slot to roll back, close/reopen the
consumer, and only then remove the candidate. Connecting this content does not
change host Mesa or every snap globally. The remaining cost is maintaining a
separate runtime provider until the distribution's standard provider includes
the chip entry; retire this package once that provider passes the same acceptance.
