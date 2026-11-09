# 升级说明

[English](UPGRADE.en.md) · [安装与恢复](FLASHING.md)

## v0.7.2 → v0.8.0

⟦DRAFT:G-RELEASE⟧

v0.8.0 保留 Linux 7.2.15，增加 Gunyah 虚拟机、Waydroid 内核支持、Snap 图形、Resources 硬件监控和 80% 电池保护，并修正中断与串口挂起行为。
GunyahVM 与 Resources 随系统预装；Waydroid 按[安装指南](WAYDROID.md)单独安装，使用软件渲染，Android“省流量”不可用。Snap 图形使用共用 `piano-snap-graphics` 包；strict 隔离仍受 snapd 能力检测问题影响。
电池保护在 GNOME 设置 → 电源中开启，到 80% 停充、降至 75% 复充；默认关闭。

核对 `SHA256SUMS` 后在平板上执行：

```sh
tar xf erhai-device-packages-v0.8.0.tar
sudo apt install ./erhai-device-packages-v0.8.0/*.deb
sudo erhai-remove-generic-kernels
```

清理命令移除这台平板不用的 Ubuntu generic 内核及 kdump；保留 `erhai-kernel-image-*`、当前内核、回退内核和 `linux-firmware`。确认命令成功后重启；无需重新分区或重装。
共用包与其依赖须和设备包一起安装。保留开发调试通道时使用同版调试包集合；普通归档重启后关闭调试通道。

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
