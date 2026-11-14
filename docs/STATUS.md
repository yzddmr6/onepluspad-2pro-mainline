# 功能支持状态 / Hardware support

当前功能支持程度与已知功能限制集中维护在项目首页：

- [中文支持表](../README.md#硬件支持)
- [English support table](../README.en.md#hardware-support)

✅ 可用 / Working · 🟡 部分支持 / Partial · ❌ 尚不支持 / Unsupported

### v0.10.0

连接有线电源时，GNOME 顶栏显示电池侧净充电功率和当前充电通路。 While wired power is connected, the GNOME top bar shows net battery charging power and the active charging protocol.

内屏默认 120 Hz，可在显示设置中选择 90 Hz。Wi-Fi 发射功率由固件和当前监管域决定。

The internal display defaults to 120 Hz and offers 90 Hz in Settings. Wi-Fi transmit power follows the firmware and the active regulatory domain.

Waydroid 图形包支持 Adreno 830 硬件渲染，可从 GNOME 启动 Android 应用。 接着有线充电器时，锁屏或合盖后屏幕关闭，系统保持唤醒，快充可持续至充满。充满后仍保持唤醒，拔线后恢复正常休眠。 接电脑 SDP/CDP 口时可正常空闲挂起；开发者模式会保持连接。系统在本地记录输入和电池充电遥测。

Waydroid runs Android apps from GNOME with Adreno 830 hardware rendering. With a wired charger connected, locking the tablet or closing the cover turns off the screen. The system stays awake so fast charging can continue until full. It stays awake while the charger remains connected and resumes normal sleep behavior after unplugging. The tablet can suspend when idle on an SDP or CDP computer port; USB developer mode keeps the connection awake. Charging samples are recorded locally.

电池温度在 0 °C 至 51 °C 以下时，兼容的 SUPERVOOC、UFCS 和 PPS 充电器可快充，高电量插入也可使用。系统随电池温度和电压调节功率，接近充满时逐步降流。兼容的 PD 或 QC 充电器可用 9 V 充电。 一加手写笔扫描默认开启，支持 DisplayPort 音频输出。

Compatible SUPERVOOC, UFCS and PPS chargers support fast charging from 0 °C to below 51 °C, including when connected at a high state of charge. Power follows cell temperature and voltage, tapering near full charge. Compatible PD and QC chargers support 9 V charging. Pen scanning is enabled by default and DisplayPort audio output is supported.

### v0.9.1

PPS 电荷泵偏离工作电压窗口后会重新调整请求，修复充电意外掉档。目标和上限保持 4 A，并受适配器通告的能力限制。 修复大提交入队前的内存分配失败，修正 UDMABUF 写回内存的 GPU 映射属性。更新接电挂起策略，修复桌面注销和音频会话退出崩溃。

The PPS charge pump adjusts its request when it leaves the operating voltage window, recovering from unintended charging slowdowns. Its target and ceiling remain at 4 A, subject to the adapter’s advertised capabilities. Fix allocation failures before large GPU submissions reach the queue and correct GPU mappings for write-back UDMABUF memory. Update suspend policy on external power and fix desktop and audio session shutdown crashes.

### v0.9.0
Linux 7.4-rc2、NPU 离线演示、GNOME 硬件录屏、Mesa 驱动修复与系统切换保护；支持自动亮度和 USB 外接设备。GunyahVM 1.2.0 支持 Linux 和 Windows 来宾。

Linux 7.4-rc2, an offline NPU demo, hardware screen recording in GNOME, Mesa driver fixes and system-switch safeguards. Automatic brightness and USB peripherals are supported. GunyahVM 1.2.0 supports Linux and Windows guests.

### v0.8.1

Linux 7.2.15：沙箱程序使用宿主 GPU 加速，Vulkan 设备不再重复；控制中心 50.3，电源键默认锁屏；升级工具保留完整软件包与启动组，支持整版回退。

Linux 7.2.15: host GPU acceleration for sandboxed programs, one Vulkan device registration, Settings 50.3, power-button screen locking, and complete package/boot-set rollback.

### v0.8.0

Linux 7.2.15：GunyahVM、Waydroid 安装支持、共用 Snap 图形提供者、Resources；中断与串口挂起修复；根镜像与升级路径移除 generic 内核和 kdump。

Linux 7.2.15: GunyahVM, Waydroid installation support, shared Snap graphics, Resources; interrupt and UART suspend fixes; generic kernels and kdump removed from images and through the upgrade path.
