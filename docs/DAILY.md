# 日用配置：扬声器、电源模式与压缩交换空间

[English](DAILY.en.md) · [项目首页](../README.md)

设备支持包默认提供内置扬声器，并加入 GNOME 三档电源模式与压缩内存交换空间。
内核与设备支持包需一起升级，升级后重启。

## 扬声器

每次启动时，UCM 在 `HiFi` 场景中提供 `Speaker` 设备，PipeWire 无需启动辅助程序即可选用。
HiFi 场景在 ACP 探测 PCM 之前建立前端到后端的路由，启用 Speaker 时再设置功放与 DSP 电平。
持久关闭会撤下播放路由，保留麦克风；用户已选择的外部输出仍按 WirePlumber 的常规策略处理。

`sudo erhai-audio-speaker disable` 持久关闭扬声器，`sudo erhai-audio-speaker enable` 恢复；
两者都会重启在线用户的声音服务。`status` 显示当前策略与控件状态。
关闭设置在升级或卸载软件包后保留，彻底清除（purge）`erhai-audio` 时一并清除。

六路功放控件保持 350（-2.5 dB），与原厂 ACF 的音乐配置一致；DSP 增益保持 8192（Q13 单位增益）。
WirePlumber 为本机扬声器输出设置 `channelmix.max-volume = 1.0`，它限制的是这一输出的软件音量增益，
**不是**混音信号的幅度或能量，也不是扬声器保护算法。直接访问 ALSA 或管理员修改可以绕过这一策略；
ALSA 控件本身仍允许设到 360（0 dB）。

AW88261 芯片自带过温、短路/过流与供电电压保护。未改动的板级 ACF 在 Amp5 与 Amp6 上启用了峰值 AGC，
Amp0–3 没有。原厂 DSP 的振幅/音圈温度保护与逐路滤波都没有实现，因此音量与原厂一致不等于安全性一致，
此前的短时听音也不能证明长时间满音量播放安全。默认开启的播放已通过听音确认。未使用其他机型的功放配置。

硬件参考：[AWINIC AW88261 数据手册第 22、24、34 页](https://doc.awinic.com/doc/20230609wm/c815e155-60b7-40fb-889b-676b02e67d0a.pdf)、
本机的 `packaging/firmware/awinic/erhai/aw88261_acf.bin`，以及所固定内核中的 `aw88261_dev_reg_update()` 实现。

## GNOME 电源模式

Ubuntu 的 `tuned-ppd` 提供 GNOME 使用的 `net.hadess.PowerProfiles` 接口，并替换与之冲突的
`power-profiles-daemon` 软件包。在 GNOME 设置或快捷设置中选择模式；插电与用电池使用同一套板级配置，默认为均衡。

| GNOME 模式 | TuneD 配置 | CPU0–5 下限 / 上限（kHz） | CPU6–7 下限 / 上限（kHz） | GPU 下限 / 上限（Hz） | Boost |
|---|---|---:|---:|---:|---:|
| 省电 | erhai-power-saver | 384000 / 1785600 | 1017600 / 1958400 | 160000000 / 342000000 | 0 |
| 均衡 | erhai-balanced | 1785600 / 3532800 | 1689600 / 4320000 | 160000000 / 1100000000 | 1 |
| 性能 | erhai-performance | 2918400 / 3532800 | 2841600 / 4320000 | 160000000 / 1100000000 | 1 |

- 各档都用 `schedutil`。
- **均衡**不压 CPU 和 GPU 的上限；大核的 4204800、4320000 kHz 两个 boost 频点开着，但调频目前最高只请求到 4089600 kHz。忙碌的核心不低于约 1.7 GHz，滚动和动画不用等调频从最低档爬上来；空闲的核心照样休眠。
- **性能**范围与均衡相同，但把忙碌核心的最低频率抬到约 2.9 GHz：打开应用、滚动、给 GPU 送数据这类短时负载一开始就是高频，不用等调频爬上来。空闲的核心照样休眠。
- **省电**压低 CPU 与 GPU 上限，并把利用率下限封顶在 320（`kernel.sched_util_clamp_min`），也就是六个小核在受限频率下能提供的能力。更大的下限（例如虚拟机申请的）会被当成哪个受限核心都放不下，全部挤到两个大核上。
- 各档中，实时线程（音频、合成器）默认都不设利用率下限（`/usr/lib/sysctl.d/50-erhai-uclamp.conf`）。

CPUCP 固件与温控限制仍然有效，没有改动任何温控触发点。

配置位于 `/usr/lib/tuned/profiles/erhai-*`。单独归属的 `/etc/tuned/erhai-ppd.conf` 是配置文件（conffile）；
`tuned-ppd.service` 的 drop-in 只在该服务内部把它绑定到 Ubuntu 的 `/etc/tuned/ppd.conf` 上，发行版原文件保持不变。
这个配置文件配置完成后，软件包会重启已启用的 PPD 服务，包括在安装依赖期间启动失败的服务；
已禁用或屏蔽的 PPD 服务保持停止。管理员的覆盖配置放在 `/etc/tuned/profiles/`。
`tuned-adm active` 与 `sudo tuned-adm verify` 可检查当前配置；检验 GNOME 的切换请通过它的 D-Bus 接口，
不要只凭直接执行 `tuned-adm profile` 推断。

卸载设备支持包时，会从 TuneD 保存的选择中清除这些配置（若没有剩余，则改用发行版的 balanced 配置），
并让运行中的 TuneD/PPD 服务按发行版映射重新加载。卸载后重启，交换空间会按发行版的 zram 策略重新创建。
彻底清除还会删除本机的 PPD 配置文件。除非通过 APT 明确删除，Ubuntu 软件包会保留。

## 压缩交换空间

Ubuntu 的 `systemd-zram-generator` 创建 `/dev/zram0`：zstd 压缩，优先级 100，大小为 `min(ram / 2, 8192)` MiB，
其中 `ram` 是内核可用的 MemTotal。标称 16 GB 的设备通常得到略少于 8 GiB。
没有自定义 zram 服务，也没有后备设备回写。

内核必须提供 `CONFIG_ZRAM=m`、`CONFIG_ZRAM_BACKEND_ZSTD=y` 与 `CONFIG_ZRAM_DEF_COMP_ZSTD=y`（后者也会选上 zsmalloc）。
不带 zram 的旧 erhai 内核必须先升级才能启用生成器，否则启动时可能一直等待不存在的 zram 设备。
设备支持包依赖本版的内核镜像包 `erhai-kernel-image-<release>`；打包时会检查这个内核的配置有 swap、zram 与 zstd 支持，不满足就不出包。
安装镜像包不会激活内核选择器，因此可以先 RAM 启动验证，再持久激活。
这一依赖不检查当前运行的内核：做运行时检查前，请先启动对应的内核。

可用 `zramctl`、`swapon --show`、`/proc/meminfo` 与 `/sys/block/zram0/comp_algorithm` 查看大小、优先级与压缩算法。
大小上限指逻辑交换容量，内存按实际使用分配。
