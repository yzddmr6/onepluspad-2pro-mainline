# 共享 Ubuntu GNOME 包

源码、补丁与构建配方的权威位置是小米平板 8 Pro 集成仓的 `ubuntu/`。
`shared/` 按 `provenance.json` 的提交原样导入，每个文件均有 SHA-256；不要修改这些副本，
也不在一加维护第二套补丁。保留原作者、许可证和 Ubuntu 源认证链。
`binaries.json` 固定八个运行时 deb，并与导入的权威 `power-button-lock.SHA256SUMS`、`mutter/SHA256SUMS` 交叉核对。

装配前运行：

```sh
python3 tools/shared_gnome.py --packages /path/to/runtime-debs
```

WirePlumber 与 libwireplumber-0.5-0 使用 Ubuntu 更新包，通过 --dependency-deb 将两者加入离线仓库。
把八个 deb 分别通过 `tools/build-desktop-rootfs.py --device-deb` 传入。
打包器检查版本和哈希；选择 `erhai-settings` 或 `erhai-device` 时必须提供整组。

`erhai-settings` 提供 `/usr/share/gnome-control-center/port-author.ini`、精确 APT pin，
以及旧可执行文件 diversion 的迁移。共享二进制读取设备配置，不内置机型或项目链接。
电源键交给共享 GSD，设备默认动作是 `lock`。

## 迁移中断后的恢复

若 dpkg 在迁移旧 diversion 时中断，旧包的文件归属记录可能尚未退役。
使用同一份已校验的发布批次，先重放 `erhai-settings`，再继续该批次的整组安装：

```sh
sudo dpkg --configure -a
sudo dpkg --unpack /path/to/verified-batch/pool/erhai-settings_*.deb
```

随后按该版本的升级说明运行发布安装器，让 APT 配齐并配置整组依赖。
重放迁移包负责先退役旧文件归属；直接先重装控制中心会被 dpkg 的所有权检查拒绝。
迁移保留原包提供的文件，允许中断后重复执行，并在新控制中心后解包时保留其最新内容。
