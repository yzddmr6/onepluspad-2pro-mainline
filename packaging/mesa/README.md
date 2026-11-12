# 共用 Mesa / Shared Mesa

`shared/` 原样导入小米集成仓的源码锁、补丁与工具，提交和每个文件的 SHA-256 见
`provenance.json`。共享文档按其中的独立文档提交同步；源码、补丁与配方仍按主提交锁定。
修改在来源仓完成，不单独修改导入副本。

宿主使用 `shared/tools/build-host-mesa.py` 构建 Ubuntu 同名包；固定驱动补丁集保持原样，
完整 arm64 驱动集和 GLVND 沿用发行版。`tools/package-mesa.py` 接收完整共用仓库及
`piano-mesa` 过渡包，生成 `erhai-mesa` 过渡包和按整版组织的 APT 仓库。
参数与装配方式见 [BUILD](../../docs/BUILD.md#宿主-mesa-发布批次)。

Snap 的 `build-mesa.py` / `build-mesa-root.py` 与 gpu-2404 SDK 配方保持独立。
更换宿主包不会更新 Snap provider。过渡包只有在升级路径完成、桌面直接依赖相应
发行版运行库后才能移除；交回 Ubuntu 前同时撤下精确 pin 和精确依赖。

`shared/` is an unmodified import pinned by `provenance.json`. Documentation uses
the separately recorded documentation commit; code, patches and recipes retain
the main source commit. Make changes at the source before refreshing an import.
Host Mesa uses `build-host-mesa.py` and
Ubuntu package names, the complete ARM64 driver set and GLVND. The local wrapper
consumes the complete common repository and creates the OnePlus transition and
release batch; see [BUILD](../../docs/BUILD.en.md#host-mesa-release-batches).
The Snap build recipe and SDK remain separate. Retire transitions only after all
upgrade paths have migrated; remove exact pins and exact dependencies when
returning to Ubuntu's own Mesa packages.
