# Mesa desktop candidate

Mesa 26.2.3 is built with Freedreno OpenGL/GLES and Turnip Vulkan. The source
archive and ordered patches are pinned in `source.json`. The existing A830v1
upstream entry and texture-sequence allocator fix remain in the series.
The three Turnip patches retain their original authors and patch envelopes;
`0003-mesa-publish-initialized-shared-context.patch` extracts the generic context
publication change from the attributed source commit. Its speedbin hunk is
omitted because the existing upstream A830v1 patch already supplies it.

Build natively in the pinned ARM64 root, or pass `--cross-file ARM64.ini` to
`tools/build-mesa.py --profile desktop`. Cross builds need an ARM64 C/C++
toolchain (GCC 14 or newer), a target sysroot matching `build-root.json`, native
Python/Meson/Ninja/glslang, and a Wayland scanner matching the target Wayland version.
GCC 13 at `-O3` miscompiles the GLSL constant-value switch and triggers an
assertion for valid float constants. GCC 14 retains the valid cases; assertions
remain enabled. The build rejects older GCC and records the target compilers.
The cross file must preserve its sysroot link flags and add
`-Wl,-rpath,/usr/lib/erhai/mesa/lib` to both `c_link_args` and `cpp_link_args`.
Run `tools/package-mesa.py` in the target ARM64 root for dependency scanning.
With QEMU user emulation, always set `QEMU_CPU=max,pauth-impdef=on`.

Libraries stay under `/usr/lib/erhai/mesa`; session selection is unchanged.
The package diverts Ubuntu's standard Freedreno ICD using `dpkg-divert`, installs
an ICD pointing to its private Turnip library, and restores the distribution ICD
on removal. Other Vulkan ICDs remain available. Start a new desktop session
after installation/removal so applications load the intended library versions.

These are experimental Vulkan/compiler changes. Offline construction and library
loading do not establish rendering, performance or suspend reliability. Remove
local patches when the pinned upstream contains equivalent fixes and the affected
workloads pass on the device. See `docs/USERSPACE-TEST.md` for device acceptance.
