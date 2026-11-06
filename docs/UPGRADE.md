# 升级说明

[English](UPGRADE.en.md) · [安装与恢复](FLASHING.md)

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
