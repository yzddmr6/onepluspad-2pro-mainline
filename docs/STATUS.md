# 功能支持状态 / Hardware support

当前功能支持程度与已知功能限制集中维护在项目首页：

- [中文支持表](../README.md#硬件支持)
- [English support table](../README.en.md#hardware-support)

✅ 可用 / Working · 🟡 部分支持 / Partial · ❌ 尚不支持 / Unsupported

### v0.11.0

可从通知整组升级系统，从充电菜单暂停充电，并根据屏幕方向切换立体声声道。按本机环境光曲线调节亮度，登录界面保留重启前的亮度，USB 光驱可读取 ISO 9660、Joliet 与 UDF。键盘盖支持 Esc，蓝牙触控板支持按住拖动，笔充电固件随系统提供，前摄支持同进程重开。

Update the whole system from the release notification, pause charging from the charging menu, and keep stereo aligned with the screen. Automatic brightness follows the tablet’s ambient-light curve. The login screen preserves brightness across reboots. USB optical drives read ISO 9660, Joliet and UDF. The keyboard cover supports Esc and Bluetooth click-and-drag. The system includes pen charging firmware and supports reopening the front camera in one process.

### v0.10.2

第三方 PPS 和 UFCS 充电器充电时，整段快充都按开始时的电量选用电流表，和原厂一致；不再在电量过 56%、76%、86% 时逐级降流。常见的 3 A PPS 充电器在 86% 以后从约 2.0 A 恢复到约 2.9 A。

With third-party PPS and UFCS chargers, the whole fast-charge session now uses the current table chosen at its start, as the stock firmware does, instead of stepping down as the charge passes 56 %, 76 % and 86 %. A common 3 A PPS charger keeps about 2.9 A instead of about 2.0 A above 86 %.

### v0.10.1

原装充电器的 SUPERVOOC 电荷泵一直工作到快满时按原厂的低电流判据结束，不再在 89% 左右提前转入慢充；从 73% 充到显示 100% 由约 86 分钟缩短到约 43 分钟。整组升级或回退完成后，自动清掉旧的发布批次、旧内核、旧启动镜像备份和不再使用的旧包，只保留当前版本和用于回退的上一版。GunyahVM 升到 1.3.0，可以在平板上直接从 Apple 的服务器创建 macOS 虚拟机。

With the original charger, the SUPERVOOC charge pump now runs until the stock low-current full criterion near the top instead of handing over to slow charging around 89 %; from 73 % to 100 % shown takes about 43 minutes instead of about 86. After a full upgrade or a rollback, old release batches, old kernels, old boot image backups and packages that are no longer used are removed automatically; only the current version and the previous one kept for rollback remain. GunyahVM 1.3.0 creates macOS VMs on the tablet directly from Apple's servers.

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
