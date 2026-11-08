# 共用 Mesa 图形驱动 / Shared Mesa graphics

Mesa 的源码锁、补丁、desktop 与 gpu-2404 配方由 [小米集成仓](https://github.com/yzddmr6/xiaomipad-8pro-mainline) 统一维护。本仓的 `packaging/mesa/shared/` 原样导入，提交和文件摘要见 [provenance.json](../packaging/mesa/provenance.json)。修改先进入来源仓，再更新整个导入副本。

两种 profile 都使用 `--optimization=2` 和 `b_ndebug=true`，配置后核对 Meson 选项和实际目标编译命令。源码包、补丁、配置或目标编译器发生变化时，使用新的输出目录重新配置。构建工具只在主机上运行，不操作平板。

桌面构建：

```sh
python3 tools/build-mesa.py --profile desktop --source-archive <official-Mesa-archive> \
  --cross-file <arm64-cross-file> --target-root <arm64-SDK> --output out/mesa-build
python3 packaging/mesa/shared/tools/package-mesa.py --mesa-build out/mesa-build \
  --output out/shared-mesa --version <package-version>
python3 tools/package-mesa.py --shared-package out/shared-mesa/piano-mesa_*_arm64.deb \
  --output out/mesa-debs
```

`piano-mesa` 提供 Freedreno、Turnip 与 softpipe，`erhai-mesa` 是依赖它的过渡包。升级包集必须包含这两个 deb；依赖从实际 ELF 符号表生成。私有目录通过动态链接器注册，发行版仍拥有自己的 Mesa 文件。所有支持的旧版完成迁移、桌面元包直接依赖 `piano-mesa` 后，可移除过渡包。已有进程需重启才能装载新库。

Snap provider 使用相同源码与补丁，单独构建 `gpu-2404` profile，再用 `tools/package-mesa-snap.py --build-output ... --base-snap ... --output ...` 打包。完整的 stock provider 与 SDK 输入锁在 `packaging/mesa/shared/mesa/snap/`；产物名称为 `piano-mesa-2404`。更换桌面 deb 不会自动更新 Snap provider。

The Xiaomi integration repository is the authority for the source lock, patches
and both build profiles. `packaging/mesa/shared/` is an unmodified import pinned
by `provenance.json`; update it as a whole after changing the source repository.
Both profiles use checked `-O2` and `b_ndebug=true` settings. Changed source,
patches, configuration or target compilers require a fresh output directory.
The commands above build on the host without accessing a tablet.

The common `piano-mesa` deb contains Freedreno, Turnip and softpipe.
`erhai-mesa` depends on it to preserve upgrades; ship both debs. Dependencies
come from the ELF symbol tables. The private libraries are registered with the
dynamic linker, and distribution Mesa files retain their ownership. Existing
processes must restart to load new libraries. Retire the transition after all
supported upgrades have migrated and desktop metapackages depend directly on
`piano-mesa`.

Build the `gpu-2404` profile and package it with `tools/package-mesa-snap.py`
using the pinned stock provider and SDK inputs. The provider is named
`piano-mesa-2404`; a desktop deb upgrade does not update it.
