#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail

repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
# Workspace layout: when this repo is checked out at <workspace>/public/<name>,
# shared inputs and build outputs live in the workspace root; standalone
# checkouts keep everything inside the repo. ERHAI_WORKSPACE overrides both.
if [[ -f $repo/../../AGENTS.md && -d $repo/../../kernel/linux ]]; then
	ws=${ERHAI_WORKSPACE:-$(cd -- "$repo/../.." && pwd)}
else
	ws=${ERHAI_WORKSPACE:-$repo}
fi
src=${KERNEL_SOURCE:-"$ws/kernel/linux"}
out=${OUT_DIR:-"$ws/out/kernel-dev"}
jobs=${JOBS:-$(nproc)}
cross=${CROSS_COMPILE:-aarch64-linux-gnu-}
fragment="$src/arch/arm64/configs/erhai-firstboot.config"

if [[ $# != 0 ]]; then
	echo "Usage: $0 (KERNEL_SOURCE, OUT_DIR, JOBS, CROSS_COMPILE optional)"
	exit 2
fi
src=$(realpath "$src")
[[ $(git -C "$src" rev-parse --show-toplevel) == "$src" ]] || {
	echo 'Kernel source must have its own Git repository.' >&2
	exit 1
}
[[ -f $fragment ]]
mkdir -p "$out"
out=$(realpath "$out")
exec 9>"$out/.build.lock"
flock -n 9 || { echo "Build output is already in use: $out" >&2; exit 1; }

head=$(git -C "$src" rev-parse HEAD)
pinned_head=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["kernel"]["commit"])' "$repo/kernel/source.json")
if [[ $head != "$pinned_head" && ${ALLOW_UNPINNED_KERNEL:-0} != 1 ]]; then
	echo 'Kernel HEAD differs from kernel/source.json; use the pinned checkout.' >&2
	echo 'For an explicit development experiment only, set ALLOW_UNPINNED_KERNEL=1.' >&2
	exit 1
fi
base=$(git -C "$src" describe --tags --abbrev=0 --match 'v[0-9]*' HEAD)
[[ -z $(git -C "$src" status --porcelain --untracked-files=no) ]] || {
	echo 'Commit or snapshot tracked kernel changes before building.' >&2
	exit 1
}
export ARCH=arm64 CROSS_COMPILE="$cross"
export KBUILD_BUILD_USER=yzddmr6 KBUILD_BUILD_HOST=onepluspad-2pro-mainline KBUILD_BUILD_VERSION=1-yzddmr6
export KBUILD_BUILD_TIMESTAMP
KBUILD_BUILD_TIMESTAMP=$(git -C "$src" show -s --format=%cI HEAD)
export KCFLAGS="-ffile-prefix-map=$src=/linux -ffile-prefix-map=$out=/kbuild"
export KAFLAGS="-Wa,--debug-prefix-map=$src=/linux -Wa,--debug-prefix-map=$out=/kbuild"
cc="${cross}gcc"
if command -v ccache >/dev/null; then
	cc="ccache $cc"
fi
args=(-C "$src" O="$out" "CC=$cc")
recipe=$(cat "$src/arch/arm64/configs/defconfig" "$fragment" | sha256sum | cut -d' ' -f1)
toolchain=$("${cross}gcc" --version | head -1)
identity=$(printf '%s\n' "$src" "$base" "$toolchain" "$cross" "$KCFLAGS" "$KAFLAGS" | sha256sum | cut -d' ' -f1)
if [[ -f $out/.build-input && $(cat "$out/.build-input") != "$identity" ]]; then
	echo 'Toolchain/source location changed; select a new OUT_DIR.' >&2
	exit 1
fi
printf '%s\n' "$identity" >"$out/.build-input"
if [[ ! -f $out/.config || ! -f $out/.recipe || $(cat "$out/.recipe") != "$recipe" ]]; then
	make "${args[@]}" defconfig >"$out/configure.log" 2>&1
	"$src/scripts/kconfig/merge_config.sh" -m -O "$out" "$out/.config" "$fragment" >>"$out/configure.log" 2>&1
	make "${args[@]}" olddefconfig >>"$out/configure.log" 2>&1
	printf '%s\n' "$recipe" >"$out/.recipe"
fi
while IFS= read -r setting; do
	case "$setting" in
	CONFIG_*=y)
		grep -Fxq "$setting" "$out/.config" || {
			echo "Requested built-in dependency missing: $setting" >&2; exit 1;
		}
		;;
	esac
done <"$fragment"

printf 'Building %s with %s (%s jobs)\n' "$head" "$toolchain" "$jobs"
# Each source/configuration/compiler combination needs a distinct module ABI
# directory. Package upgrades must never replace modules for a running kernel
# with a different build that happens to use the same local version string.
compiler_sha=$(sha256sum "$(command -v "${cross}gcc")" | cut -d' ' -f1)
config_sha=$(sha256sum "$out/.config" | cut -d' ' -f1)
abi=$(printf '%s\n' "$head" "$config_sha" "$toolchain" "$compiler_sha" | sha256sum | cut -d' ' -f1)
localversion="-g${head:0:12}-a${abi:0:8}"
args+=("LOCALVERSION=$localversion")
make "${args[@]}" -j"$jobs" Image qcom/sm8750-erhai.dtb modules 2>&1 | tee "$out/build.log"
[[ $(git -C "$src" rev-parse HEAD) == "$head" && -z $(git -C "$src" status --porcelain --untracked-files=no) ]] || {
	echo 'Source changed during build; output must not be used.' >&2; exit 1;
}
python3 - "$out" "$head" "$toolchain" "$compiler_sha" "$localversion" <<'PY'
import hashlib, json, pathlib, sys
out, head, compiler, compiler_sha, localversion = pathlib.Path(sys.argv[1]), *sys.argv[2:]
files = ['arch/arm64/boot/Image', 'arch/arm64/boot/dts/qcom/sm8750-erhai.dtb', '.config']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
modules = {}
for name in (out / 'modules.order').read_text().splitlines():
    path = pathlib.Path(name)
    if path.suffix == '.o':
        path = path.with_suffix('.ko')
    assert not path.is_absolute() and '..' not in path.parts, name
    modules[str(path)] = sha(out / path)
assert modules, 'configured module build produced no modules'
result = {'status': 'OFFLINE_BUILD_ONLY', 'kernel_commit': head, 'compiler': compiler,
          'compiler_sha256': compiler_sha, 'localversion': localversion,
          'kernel_release': (out / 'include/config/kernel.release').read_text().strip(),
          'note': 'Mutable development output; package with build-mainline-boot.py before boot.',
          'files': {f: sha(out / f) for f in files},
          'modules': modules,
          'module_metadata': {name: sha(out / name) for name in
                              ('modules.order', 'modules.builtin', 'modules.builtin.modinfo',
                               'Module.symvers', 'System.map')}}
(out / 'build-result.json').write_text(json.dumps(result, indent=2) + '\n')
PY
echo "Platform build complete: $out/build-result.json (not a tablet boot image)"
