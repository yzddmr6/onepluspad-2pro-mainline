# Iris VA-API driver

Build the pinned upstream archive with `tools/build-iris-vaapi-deb.py
--source-archive ARCHIVE --cross-file ARM64.ini --output OUTPUT`.
The ARM64 sysroot needs libva 2.23, libdrm, EGL, GLES and GBM development
packages. The cross-file executable wrapper must set
`QEMU_CPU=max,pauth-impdef=on` when using QEMU.

The MIT/LGPL-2.1 upstream driver, original authors, licenses and corresponding
source are shipped in the deb. Source and patch provenance is in `source.json`.
The GPL-2.0 SM8750 video acceleration repository is a reference for the stateful
V4L2 and decode-order requirements; its device configuration is not imported.
The build recipe is adapted from yzddmr6's MIT-licensed integration (see the
source lock). The Chrome-specific policy patch is outside this package's scope.

`erhai-iris-vaapi` owns the V4L2 VA driver and an `msm_drv_video.so` discovery
symlink. No global LIBVA override, browser replacement or kernel installation
is involved. Iris decode-order/display-delay controls in the running kernel are needed
for the intended low-latency path; display-order fallback is not qualified. H.264, HEVC and VP9 are candidates; AV1 is not enabled.
Build and host smoke results do not establish hardware playback.

`erhai-video-defaults` prefers the distribution's `vah264dec`, `vah265dec`
and `vavp9dec` GStreamer elements, using the same Iris VA adapter as Firefox.
`GST_VA_ALL_DRIVERS=1` admits this driver's real vendor string through
GStreamer's vendor filter; no driver identity is spoofed. The generic V4L2
VP9 path can stop producing frames across an initial flush/restart, so it
is no longer promoted by this package. The package leaves decoder selection
to playbin and respects an explicit `GST_PLUGIN_FEATURE_RANK` override.
It also enables VA-API defaults for native Firefox installed in `/usr/lib/firefox` or `/usr/lib/firefox-esr`. User preferences take
precedence. Hardware video decoding is force-enabled for this candidate; the
Vulkan Video path is disabled to keep the browser on VA-API. Log out and back in after installing or removing it. The package
does not modify profiles, policies, application launchers or sandbox settings.
Snap/Flatpak Firefox cannot use this host driver through this deb alone and is
outside this candidate. A native Firefox build with HEVC support is required
for the HEVC browser check; codec availability must be checked on the device.

Remove with `apt remove erhai-video-defaults erhai-iris-vaapi`. This removes all
owned defaults and driver files; distribution packages remain installed.
