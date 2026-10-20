# Ubuntu for OnePlus Pad 2 Pro

在一加平板 2 Pro 上运行 Ubuntu Desktop 26.04，采用 GNOME 桌面与基于上游 Linux
的设备适配内核。[English](README.md)

## 📮 关注与交流

项目进展、使用记录与技术交流会在以下渠道更新，欢迎反馈使用中遇到的问题。

| 公众号：熵减矩阵 | 小红书：yzddmr6 |
|:---:|:---:|
| <img src="docs/assets/gzh-qr.png" width="200" alt="公众号：熵减矩阵"> | <img src="docs/assets/xhs-qr.jpg" width="200" alt="小红书：yzddmr6"> |
| 项目进展 · 技术记录 | 使用分享 · 问题交流 |

## ⚠️ 安装前请阅读

- **适用设备**：一加平板 2 Pro，**OPD2413 / erhai / SM8750P**。已测设备为
  **16 GB 内存、512 GB 存储**；OnePlus Pad 3、其他容量、其他固件及分区布局尚未验证。
- **安装范围**：提供 512 GB 机型的首次分区、Linux 安装及既有布局重装流程。
  首次分区会清除 Android 数据；固件与布局要求见[安装与恢复说明](docs/FLASHING.zh-CN.md)。
- **充电与续航**：Linux 下能从 USB 取电，但尚未验证能净充电：插电脑 USB 口亮屏时，
  输入少于整机耗电，电量仍缓慢下降；充电器下尚未实测，原厂快充在 Linux 下不可用。
  需要充电时返回 Android；Fastboot 不能作为充电方案。
  当前日用熄屏只关闭背光，耗电高于正常待机；电源键系统休眠为可选功能，
  见[系统休眠](docs/SUSPEND.zh-CN.md)。
- **数据与恢复**：解锁 Bootloader 会清除用户数据。操作前请备份个人文件，准备
  匹配的原厂固件；出厂校准与设备地址必须来自本机，不可跨设备复制。
- **调试访问**：USB 调试通道仅供开发使用，启用后提供免认证 root shell 和 HTTP
  服务。请仅连接可信电脑，不要将其开放到公共网络。

## 🚀 获取与使用

设备固件与原厂启动构建输入随仓库提供，无需手动从 ROM 提取。原厂输入版本为
**ColorOS `OPD2413_11.C.34_1340_202607031844`**，其他固件来源见[固件说明](packaging/firmware/README.md)。
构建输入由 `tools/prepare-inputs.py` 统一准备，详见构建指南。

| 我想要 | 入口 |
|---|---|
| 了解目前能用哪些功能 | [硬件支持](#硬件支持) |
| 了解 Android 与 Ubuntu 如何切换 | [双系统切换](#双系统切换) |
| 编译内核与设备组件 | [构建指南](docs/BUILD.zh-CN.md) |
| 查看安装条件与恢复方式 | [安装与恢复说明](docs/FLASHING.zh-CN.md) |
| 不自己构建、直接用发布镜像安装 | [发布版预构建镜像](docs/FLASHING.zh-CN.md#发布版预构建镜像) |
| 开发或调整图形组件 | [图形集成说明](docs/GRAPHICS.md) |
| 查看休眠与电源键 | [系统休眠](docs/SUSPEND.zh-CN.md) |
| 查看背光与亮度 | [显示与背光](docs/DISPLAY.zh-CN.md) |
| 点亮或排查传感器 | [SSC 传感器](docs/SENSORS.zh-CN.md) |
| 贡献代码或反馈问题 | [参与贡献](CONTRIBUTING.md) |
| 查看版本记录 | [Changelog](CHANGELOG.md) |

## 双系统切换

在已安装双系统的设备上，Ubuntu 使用独立的 Linux 根分区，Android 保留自己的系统
和数据。日常切换需要重启，不重新安装系统或清空用户文件。

| 当前系统 | 切换方式 |
|---|---|
| Ubuntu → Android | 打开应用列表中的 **Switch to Android（切换到 Android）**，输入管理员密码，等待自动重启。 |
| Android → Ubuntu | 在 KernelSU 中打开 `erhai dual boot switch` 模块的 WebUI，选择 **Reboot to Ubuntu**。 |

两个系统共用同一活动启动槽；已验证的布局使用 A 槽。切换器将目标系统的
`boot`、`init_boot`、`vendor_boot` 三张启动镜像作为一组写入，读回校验后再重启；
另一套系统的镜像保存在 Linux 分区的切换存储区中。日常切换不改变活动槽。

切换过程中会写入启动分区，请勿断电或强制重启。操作条件与恢复方式见
[安装与恢复说明](docs/FLASHING.zh-CN.md)，实现细节见[切换器说明](switch/README.md)。

## 硬件支持

下表列出当前硬件支持与已知限制。“可用”表示已完成所述范围的真机测试；
开发中的功能不计入已支持范围。

✅ 可用 · 🟡 部分支持 · 🔧 开发中／待实测 · ❌ 尚不支持

### 平台、显示与输入

| 功能 | 器件 / 实现 | 状态 | 范围与限制 |
|---|---|---|---|
| 启动与存储 | SM8750P / UFS | ✅ | Ubuntu 启动与存储读写可用；双系统切换限上述已验证布局。 |
| 内置显示 | 双 DSI / DSC | ✅ | 3392 × 2400、120 Hz；其他刷新率待实测。 |
| 触控 | Novatek NT36536 | ✅ | 手指触控、桌面操作与登录已验证；手写笔单独列项。 |
| GPU 与桌面 | Adreno 830 / Freedreno / Mesa | 🟡 | GNOME 桌面和 OpenGL 渲染已验证；Vulkan 测试出现 GPU 超时，暂不支持。沙箱应用与持续负载待验。 |
| 手动亮度 | 双 KTZ8868 / 统一背光接口 | 🟡 | 已接入统一亮度接口并验证熄屏联动；桌面滑块的实际亮度范围待验。 |
| 磁吸键盘 | Pogo 键盘 / 触控板 | 🟡 | 键盘输入可用；完整键位、触控板手势及拔下重吸待实测。 |
| 手写笔 | NT36536 笔输入 | 🔧 | 笔输入代码已具备；坐标、压感与按键待实测。 |
| 笔充电 | CPS8601 | ❌ | 充电、电量显示与自动控制笔扫描尚未实现。 |

### 无线与 USB

| 功能 | 器件 / 实现 | 状态 | 范围与限制 |
|---|---|---|---|
| Wi-Fi | WCN7860 / ath12k | ✅ | 联网、开机自动连接及短时传输可用；v0.2.2 开启用户态国家码提示并包含 ath12k 频率范围修复，设备包仍保持 world `00`。5 GHz 仅被动扫描，无法开 5 GHz 热点；漫游、2.4 GHz 热点与长时间传输待实测。在关联状态下修改国家码曾导致 WLAN 固件崩溃，请勿这样操作。 |
| 蓝牙 | WCN7860 / BlueZ | 🟡 | 控制器、固件、扫描与本机地址已验证；键鼠和耳机业务尚未验收。 |
| USB 设备模式 | USB-C / NCM | 🟡 | USB 网络通信可用；部分插拔后连接未自动恢复，需要重启。 |
| USB 主机外设 | 键鼠、存储、网卡、数字音频 | 🟡 | 已测扩展坞无需外接 PD 即可使用鼠标；同一鼠标与 USB-A 转接头在 Android 直连正常，Linux 直连失败。其他外设待验。 |
| USB 存储格式 | UAS、exFAT、NTFS3 | 🔧 | 模拟环境下读写与 NTFS 中文文件名检查通过；实盘与桌面挂载待验。 |
| 外接显示 | USB-C DisplayPort Alt Mode | 🟡 | 外接显示器实际出图已确认；显示模式选择与热插拔稳定性待验。 |
| 外屏声音 | DisplayPort / ALSA / PipeWire | ❌ | 默认关闭：播放配置会影响未接外屏时的麦克风发现；播放与插拔恢复待修复、验证。 |

### 音视频与传感器

| 功能 | 器件 / 实现 | 状态 | 范围与限制 |
|---|---|---|---|
| 内置麦克风 | WCD939x / ALSA / PipeWire | 🟡 | 默认输入与双通道采集可用；ADC 13 / TX DEC 112 下，约 30 cm 正常说话峰值约 -8 dBFS、无削波。底噪表现仍待量化。 |
| 扬声器 | 六颗 AW88261 功放 / AudioReach | 🟡 | 手动启用候选的功放值为 350（-2.5 dB），听音位置、响度与音质已通过实体验收。播放仍默认关闭，无原厂扬声器保护。 |
| USB-C 模拟音频 | WCD939x 耳机通路 | ❌ | 模拟转接头与耳麦检测未实现；数字 USB 音频见上表。 |
| 桌面播放器播放视频 | Ubuntu GStreamer 软件包 | ❌ | 默认播放器 Showtime 在绘制视频画面时触发 Mesa freedreno 断言而退出；其他播放器未测。 |
| 视频硬件编解码 | Qualcomm Iris | 🟡 | H.264 硬解在平板上可用：60 帧测试片与软件解码逐帧一致；硬编与桌面播放器调用待验。 |
| 前后摄像头 | SC820CS / SC1300CS | ❌ | 摄像、拍照与视频通话尚未实现。 |
| 自动旋转 | SSC / iio-sensor-proxy | 🟡 | 姿态数据已到达桌面，**初次设置会话**里屏幕可随姿态旋转；**正式会话里即使打开开关，尚未见到旋转**。挂载矩阵为候选值、未实测。 |
| 自动亮度 | SSC 环境光 / GNOME | 🟡 | 光感已接入 GNOME，开启自动亮度后真机背光会自动调整（2047 级中由 1500 变到 1805）。面板不会自动熄屏，因此关闭了 GNOME 的静置变暗。 |
| 指南针与陀螺仪 | SSC / iio-sensor-proxy | 🟡 | v0.2.0 已装系统上经 D-Bus 读到航向与角速度，挂起恢复后仍持续更新；尚无桌面应用使用。 |
| 接近与霍尔 | SSC | ❌ | 本机 DSP 不发布接近传感器；`libssc` 也没有霍尔与 SAR 实现。 |

### 电源、时间与应用

| 功能 | 器件 / 实现 | 状态 | 范围与限制 |
|---|---|---|---|
| 电源键 | Linux input / GNOME | 🟡 | 锁屏并熄屏；把 `/etc/erhai/power-key-action` 设为 `suspend` 时，按下还会进入系统休眠，且同一按键可唤醒。锁屏后再次输入密码的流程待验。 |
| 音量键 | GPIO / PMIC PON input | ✅ | 音量上键上报 `KEY_VOLUMEUP`（115），10 次实体按下全部收到；音量下键仍映射为 `KEY_VOLUMEDOWN`。 |
| 调频与测温 | SCMI / IIO / thermal | 🟡 | 调频和温度读取可用；持续负载下的温控与机身温度管理仍不完整。 |
| 电池信息 | qcom_battmgr / UPower | ✅ | 可读电量、容量与估计剩余时间；充电能力另列。 |
| Linux 充电 | USB 供电 / 厂商固件 | 🔧 | 能从 USB 取电，但未验证净充电：插电脑 USB 口（约 2.5 W）亮屏时，电量仍以每小时约 2–3% 下降；充电器下尚未实测，原厂快充协议在 Linux 下不可用。需要充电时返回 Android。 |
| 挂起与恢复 | Linux 电源管理 | 🟡 | 默认 s2idle；v0.2.0 已装系统在两种显示模式下各挂起 300 秒、由 RTC 唤醒，显示、触控、Wi-Fi 与传感器均恢复；电源键唤醒由贡献者实测。拔线待机续航与 SoC 最深电源态仍待完善；固件广告的 `deep` 默认不用。 |
| RTC | Qualcomm PMIC RTC | 🟡 | 时间读写已验证；重启后出现过时间回退，需要重新校时。 |
| Snap 应用 | AppArmor / snapd / 图形运行库 | ❌ | 本版不支持完整沙箱与 Snap 图形应用；所选内核未启用 AppArmor。 |
| Android 应用 | Android 运行时 | ❌ | 尚未集成 Waydroid。 |

## 使用与维护

基础系统来自官方 Ubuntu Desktop，设备适配通过独立的 `erhai-*` 软件包交付，Ubuntu
软件包继续由 APT 管理。当前显示电源适配针对 GNOME Settings Daemon 50，桌面大版本
升级需先核对兼容性。

反馈问题时，请提供型号、固件与软件包版本、复现步骤及相关日志。分享前删除凭据、
序列号和个人信息；使用交流可通过顶部的公众号与小红书进行。

## 开发与贡献

| 仓库 | 内容 |
|---|---|
| [onepluspad-2pro-mainline](https://github.com/yzddmr6/onepluspad-2pro-mainline) | 设备包、用户态适配、构建工具与文档 |
| [linux-sm8750-erhai](https://github.com/yzddmr6/linux-sm8750-erhai) | Linux 内核源码、驱动、设备树与内核配置 |

构建使用的内核提交记录在 [kernel/source.json](kernel/source.json)。
构建步骤见[构建指南](docs/BUILD.zh-CN.md)，提交与反馈方式见[参与贡献](CONTRIBUTING.md)。

## 致谢与许可证

本项目基于 Linux、Ubuntu、GNOME、Freedreno/Mesa 和 Linux Qualcomm 社区的成果。
设备适配参考了 [ROCKNIX](https://github.com/ROCKNIX/distribution)、OnePlus 与 LineageOS
的相关工作，并复用了 AudioReach 和 SSC 传感器栈的实现。

除文件另有声明外，项目原创集成代码采用 **GPL-2.0-only**。Linux 内核与第三方组件
保留各自许可证和作者声明。详见 [LICENSE](LICENSE)、[NOTICE](NOTICE) 与
[固件来源及分发限制](packaging/firmware/README.md)。
