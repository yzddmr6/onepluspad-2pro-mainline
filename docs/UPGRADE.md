# 升级说明

[English](UPGRADE.en.md) · [安装与恢复](FLASHING.md)


## v0.9.0 → v0.9.1

解压本版软件包 TAR。沿用下文整版升级命令，新仓库选 `erhai-0.9.1`，`--previous` 选 `erhai-0.9.0-rollback-0.9.1`。升级前关闭虚拟机，整组安装后重启。


## 从 v0.8.1 升级到 v0.9.0

使用完整的 `erhai-0.9.0` 软件包批次和配套启动镜像，保留附件中的
`erhai-0.8.1` 批次供整版回退。本版同时更新内核、宿主 Mesa 同名包和
Snap 图形提供者；升级前正常关闭虚拟机，完成后重启。默认 NPU 演示包含
运行库、模型和本机型固件。沿用下文整版升级与回退命令，将仓库路径替换为
本版的新旧两批；无需重分区。


传感器服务关闭时先撤销客户端回调，修复停止或重启服务时的崩溃。

重启进入新会话后，GNOME 内置整屏录制默认使用 Iris 硬件编码。录屏进程的 CPU 占用较低；默认画质设置下，文件可能比软件编码大。

## v0.8.0 → v0.8.1

回退工具会保全本机实际已装的 Ubuntu 库版本。首次整版升级前，先安装发行版提供的仓库索引工具：

```sh
sudo apt install --no-install-recommends dpkg-dev
```


本版电源键默认锁屏，不再直接进入休眠；可在“设置 → 电源”中调整动作。控制中心更新为 50.3，
“关于”页继续显示移植作者。升级同时迁移图形驱动和设置组件，请使用完整批次。

宿主 Mesa 改为 Ubuntu 同名包，安装到标准多架构目录，使网页进程和其他沙箱
能够使用设备驱动。保留原驱动版本和补丁；Snap 图形提供者不变。
升级附件包含按整版组织的 `repositories/erhai-0.8.1/`，完整 Mesa 同源包
供以后安装开发包和 OpenCL 使用，默认只安装桌面所需子集。
libdrm 使用 Ubuntu 原样包，不钉版本，后续正常接收 Ubuntu 更新。

先校验发布附件的校验文件，并将新、旧两批仓库解压到新的空目录，勿覆盖此前同名仓库。旧批次必须包括已安装发布包
及其 Mesa/libdrm 依赖的精确版本；缺包时升级工具会拒绝继续，不会仅保存启动镜像。
把两个仓库目录传到平板后，在平板运行：

```sh
sudo systemd-run --unit=erhai-release-upgrade --setenv=DEBIAN_FRONTEND=noninteractive \
  /usr/bin/python3 /home/<USER>/repositories/erhai-0.8.1/install.py upgrade \
  /home/<USER>/repositories/erhai-0.8.1 \
  --previous /home/<USER>/repositories/erhai-0.8.0
journalctl -f -u erhai-release-upgrade
sudo dpkg --audit
sudo reboot
```

工具将完整批次保留在 `/var/lib/erhai/releases/`，在修改包之前保存当前启动
镜像组及已安装包版本。相同批次可重复运行；若安装中断，先运行
`sudo dpkg --configure -a`、`sudo apt-get -f install`，再重跑同一升级命令。
已有个人文件和应用数据不在回退范围内。

### 整版回退

通过终端或开发者 SSH 通道运行；无图形界面时也可使用。不要先切回旧内核。

```sh
sudo systemd-run --unit=erhai-release-rollback --setenv=DEBIAN_FRONTEND=noninteractive \
  /usr/bin/python3 /var/lib/erhai/releases/erhai-0.8.1/install.py rollback --product erhai
journalctl -f -u erhai-release-rollback
sudo dpkg --audit
sudo reboot
```

回退先把发布管理的用户态包整组恢复为上一批精确版本，随后恢复已保存的启动镜像组。
Mesa 回退会恢复旧的 `/opt` 库和注册，并移除新过渡包拥有的精确钉版本文件。
任一步失败都会停止，不会宣布回退完成。新旧仓库及启动镜像组应保留到新版本稳定。
Fastboot 仅恢复启动分区，不能恢复用户态包；只能进入恢复系统时，先修复根分区内的
软件包，再使用对应旧启动组。不要把“换回启动镜像”当作整版回退。

## v0.7.2 → v0.8.0

v0.8.0 保留 Linux 7.2.15，增加 Gunyah 虚拟机、Waydroid 内核支持、Snap 图形、Resources 硬件监控，并修正中断与串口挂起行为。
GunyahVM 与 Resources 随系统预装；Waydroid 按[安装指南](WAYDROID.md)单独安装，使用软件渲染，Android“省流量”不可用。Snap 图形使用共用 `piano-snap-graphics` 包；strict 隔离仍受 snapd 能力检测问题影响。

升级前，在仍运行 v0.7.2 时保存独立启动组副本；若目标目录已经存在，先核实它，勿覆盖：

```sh
sudo test ! -e /var/lib/erhai/rollback-v0.7.2-before-v0.8.0 &&
sudo cp -a --reflink=never /var/lib/erhai/switch/ubuntu /var/lib/erhai/rollback-v0.7.2-before-v0.8.0
sudo sh -c 'cd /var/lib/erhai/rollback-v0.7.2-before-v0.8.0 && sha256sum -c SHA256SUMS'
```

核对 `SHA256SUMS` 后在平板上执行：

```sh
tar xf erhai-device-packages-v0.8.0.tar
sudo apt install ./erhai-device-packages-v0.8.0/*.deb
sudo erhai-remove-generic-kernels
```

清理命令移除这台平板不用的 Ubuntu generic 内核及 kdump；保留 `erhai-kernel-image-*`、当前内核、回退内核和 `linux-firmware`。确认命令成功后重启；无需重新分区或重装。
共用包与其依赖须和设备包一起安装。保留开发调试通道时使用同版调试包集合；普通归档重启后关闭调试通道。

升级会安装 GunyahVM 及其运行时、来宾载荷包。升级后首次登录时，默认 Dock 包含 GunyahVM；已有自定义收藏只在末尾追加一次，保留原有项目和顺序。之后用户删除该图标，不会再次追加。本机活动桌面用户的设备访问权限由 GunyahVM 自带的 udev 与 polkit 规则授予，无需手动修改用户组。

### 回退内核与再次升级

保留上述副本及 v0.7.2 内核/模块包，直到新版本确认可用。需要回退且仍能进入 Ubuntu 时，执行：

```sh
sudo erhai-switch-install-ubuntu-images /var/lib/erhai/rollback-v0.7.2-before-v0.8.0 && sudo reboot
```

安装器校验三个镜像，将指定副本提升为当前 Ubuntu 启动组，并写入当前活动槽；即使它与 `ubuntu.prev` 相同，也会完成提升。重启后 `uname -r` 应回到 `7.2.15-erhai-dev-g870167fad062-a359a9829`。这只回退内核与启动组，不会降级应用包或还原用户数据。

回退后再次选择 v0.8.0，需要重新配置已安装的包，使内核 postinst 再次激活 v0.8.0 内核；普通 `apt install` 可能因版本已安装而不执行维护脚本：

```sh
sudo apt install --reinstall ./erhai-device-packages-v0.8.0/*.deb
sudo erhai-remove-generic-kernels
sudo reboot
```

## v0.7.1 → v0.7.2

v0.7.2 更新内核、匹配模块与启动镜像，同时更新图形驱动、设备支持包和传感器包，具体修正见[发布说明](https://github.com/yzddmr6/onepluspad-2pro-mainline/releases/tag/v0.7.2)。
图形驱动更新到 Mesa 26.2.6：新增的 `piano-mesa` 包提供驱动库，`erhai-mesa` 改为依赖它的过渡包，两者都在归档里，一起安装即可。
新增更新提醒包 `erhai-release-notifier`；其他设备包和 Android 侧切换模块保持原版本。
归档里出现不同组件版本是正常情况；无需重新分区或重装 Ubuntu。

下载 `erhai-device-packages-v0.7.2.tar` 和 `SHA256SUMS`，核对下载校验后，
将归档传到平板并在 Ubuntu 中安装：

```sh
tar xf erhai-device-packages-v0.7.2.tar
sudo apt install ./erhai-device-packages-v0.7.2/*.deb
```

确认 APT 成功结束后重启。内核选择器依赖精确匹配的镜像与模块包，
安装时更新活动槽的启动镜像，并保留上一版内核供[回退](FLASHING.md#异常与完整恢复)。
用户文件、账户与已有机器校准数据保持原样；Android 侧已有 v0.7.0 切换模块无需重装。

普通归档会将调试安装切换为普通启动，重启后关闭 USB 调试通道。
需要保留开发调试通道的安装应使用单独构建的同版本调试包集合，不能混装普通与调试内核包。

## v0.7.0 → v0.7.1

v0.7.1 更新内核、匹配模块与启动镜像，修复开机偶发蓝牙不可用和音频错误刷屏。
设备支持包同时更新，让 Dock 与文件管理器不再列出 Android 系统分区。
内核配置与 v0.7.0 相同，其他设备包和 Android 侧切换模块保持原版本。
归档里出现不同组件版本是正常情况；无需重新分区或重装 Ubuntu。

下载 `erhai-device-packages-v0.7.1.tar` 和 `SHA256SUMS`，核对下载校验后，
将归档传到平板并在 Ubuntu 中安装：

```sh
tar xf erhai-device-packages-v0.7.1.tar
sudo apt install ./erhai-device-packages-v0.7.1/*.deb
```

确认 APT 成功结束后重启。内核选择器依赖精确匹配的镜像与模块包，
安装时更新活动槽的启动镜像，并保留上一版内核供[回退](FLASHING.md#异常与完整恢复)。
用户文件、账户与已有机器校准数据保持原样；Android 侧已有 v0.7.0 切换模块无需重装。

普通归档会将调试安装切换为普通启动，重启后关闭 USB 调试通道。
需要保留开发调试通道的安装应使用单独构建的同版本调试包集合，不能混装普通与调试内核包。
