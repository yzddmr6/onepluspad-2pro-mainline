# 共用 Mesa 图形驱动 / Shared Mesa graphics

源码锁和固定驱动补丁集由[小米集成仓](https://github.com/yzddmr6/xiaomipad-8pro-mainline)维护。
`packaging/mesa/shared/` 原样导入，提交与文件摘要见
[provenance.json](../packaging/mesa/provenance.json)。修改先进入来源仓，再更新导入。

宿主使用 Canonical resolute 回移打包，保留完整 Ubuntu arm64 驱动集、GLVND 和编译选项，
产出同名包安装到标准多架构目录。libdrm 是 Ubuntu 原样二进制，不钉版本。
`piano-mesa` 和 `erhai-mesa` 都是过渡包；完整同源二进制及本版其余包保存在本地 APT
发布批次中，默认仅安装运行时子集。构建与仓库命令见 [BUILD](BUILD.md#宿主-mesa-发布批次)，
升级与整版用户态回退见 [UPGRADE](UPGRADE.md)。已有进程需重启才能装载新库。

Snap provider 继续使用独立的 gpu-2404 配方与 SDK，来源同样由锁文件固定。
宿主 deb 升级不更新 Snap provider，也不替代 Flatpak 或 Android 的独立运行时。

The Xiaomi repository maintains the source lock and the pinned driver patch set. The
unmodified import is recorded in `provenance.json`; update it after the source.
Host packages use Canonical's resolute backport packaging, Ubuntu's complete
ARM64 driver selection and GLVND in standard multiarch paths. libdrm archives
are original Ubuntu binaries and are not pinned. Both device-named Mesa packages
are transitional. Retain every same-source binary and the other release packages
in the local APT batch, while installing only the runtime subset. See
[BUILD](BUILD.en.md#host-mesa-release-batches) and [UPGRADE](UPGRADE.en.md).
Existing processes must restart to load new libraries. The separately built
Snap provider and the independent Flatpak/Android runtimes are unchanged.

## Snap 图形应用 / Snap graphics applications

`erhai-snap-graphics` 依赖共用 `piano-snap-graphics`，不再安装第二份内容运行库。
一并安装两个 deb，关闭正在运行的 Snap 图形应用，然后执行：

```sh
sudo piano-snap-graphics-connect --install
```

该包提供 core24 的 `gpu-2404` 内容，服务在首次启动时安装并连接提供者。
它不修正 snapd 的 strict 隔离能力检测。Firefox snap 的硬件 GL 与 strict 隔离分别验收。
现有 Firefox deb 保留；启用 Snap 图形不更换浏览器。

The metapackage selects the shared core24 GPU content provider. Install both
packages and close GPU Snap applications before running the command above.
This does not repair snapd's strict-confinement feature detection. The existing
Firefox deb remains installed.
