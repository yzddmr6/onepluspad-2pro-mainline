# 功能支持状态 / Hardware support

当前功能支持程度与已知功能限制集中维护在项目首页：

- [中文支持表](../README.md#硬件支持)
- [English support table](../README.en.md#hardware-support)

✅ 可用 / Working · 🟡 部分支持 / Partial · ❌ 尚不支持 / Unsupported

### v0.8.1

Linux 7.2.15：沙箱程序使用宿主 GPU 加速，Vulkan 设备不再重复；控制中心 50.3，电源键默认锁屏；升级工具保留完整软件包与启动组，支持整版回退。

Linux 7.2.15: host GPU acceleration for sandboxed programs, one Vulkan device registration, Settings 50.3, power-button screen locking, and complete package/boot-set rollback.

### v0.8.0

Linux 7.2.15：GunyahVM、Waydroid 安装支持、共用 Snap 图形提供者、Resources；中断与串口挂起修复；根镜像与升级路径移除 generic 内核和 kdump。

Linux 7.2.15: GunyahVM, Waydroid installation support, shared Snap graphics, Resources; interrupt and UART suspend fixes; generic kernels and kdump removed from images and through the upgrade path.

### v0.9.0

⟦DRAFT⟧

Linux 7.4-rc2、NPU 离线演示、GNOME 硬件录屏、Mesa 驱动修复与系统切换保护；GunyahVM 1.2.0 支持 Linux 和 Windows 来宾。

Linux 7.4-rc2, an offline NPU demo, hardware screen recording in GNOME, Mesa driver fixes and system-switch safeguards. GunyahVM 1.2.0 supports Linux and Windows guests.
