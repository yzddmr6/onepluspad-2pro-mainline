# 共用 Mesa / Shared Mesa

`shared/` 原样导入小米集成仓的 Mesa 源码锁、补丁和构建工具，固定提交与每个文件的 SHA-256 见 `provenance.json`。修改在来源仓完成后整组更新，不能单独修改导入副本。

桌面与 gpu-2404 均运行 `tools/build-mesa.py`；`tools/build-mesa-root.py` 是 gpu-2404 的 SDK 包装入口。桌面只构建一次 `piano-mesa`，然后由 `tools/package-mesa.py --shared-package ... --output ...` 同时收集这个驱动包和 `erhai-mesa` 过渡包。发布包集必须包含两者。过渡包保留原升级路径；所有支持的旧版本完成迁移、桌面元包直接依赖 `piano-mesa` 后，可移除过渡包。

`shared/` is an unmodified import of the source lock, patches and tools from the Xiaomi integration repository. `provenance.json` pins its commit and file hashes. Make changes at the source, then refresh the import as a whole.

Both profiles use `tools/build-mesa.py`; the SDK wrapper `tools/build-mesa-root.py` builds gpu-2404. Build `piano-mesa` once for the desktop, then collect it together with the `erhai-mesa` transition using `tools/package-mesa.py --shared-package ... --output ...`. Ship both debs. Retire the transition after all supported upgrades have migrated and desktop metapackages depend directly on `piano-mesa`.
