# gpu-2404 runtime

The packager overlays freshly compiled Mesa on Canonical mesa-2404 revision
1166, pinned in mesa-2404.json. Keep every stock file: gpu-snap cleanup removes
these libraries from consumer snaps, including libraries outside Mesa's own
dependency closure. The stock wrapper, hooks, component declarations and
per-library licence notices remain unchanged. The provider exports one content
directory, avoiding a second overlapping gpu-2404 mount.

This packaging implementation is adapted from
https://github.com/yzddmr6/xiaomipad-8pro-mainline/commit/c14de88ac73f2f83354bf3799ca75aeae774a897
(GPL-2.0-only, original author yzddmr6). It originated in this project's Mesa
tools. The connection helper and offline fixtures are MIT; see the package
copyright and tools/fixtures/snap-graphics/README.md.

The original Canonical snap recipe corresponds to
https://github.com/canonical/mesa-2404/commit/07eefb905dd4a75b31f05b7954326312cb19e99a
(Christopher James Halse Rogers). The original snap is a pinned upstream input,
not a previous locally built provider. Build only from --build-output; no
previous provider payload is used as input.

Build with the GCC version in packaging/mesa/toolchain.json, a core24 sysroot
from packaging/mesa/build-root-core24.json, and --profile gpu-2404. Package on
the host with --base-snap mesa-2404_1166.snap. Validate with
validate-mesa-snap.py (stock content, ABI and softpipe),
test-snap-graphics-glsl.py (including mediump constants), and
test-snap-graphics.py (connection and failure handling).
