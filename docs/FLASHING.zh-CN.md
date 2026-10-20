# 试用、安装与恢复

[English](FLASHING.md) · [项目首页](../README.zh-CN.md)

本指南包含首次分区准备、Linux 安装、双系统切换和 Android 启动恢复。
支持范围限定为下述机型与布局；首次准备和既有布局重装的验证状态分别注明。

## 适用范围

已测设备为 OnePlus Pad 2 Pro（OPD2413 / erhai），16 GB + 512 GB，Bootloader 已解锁。
既有安装使用独立 Linux 根分区，在活动槽轮换 Android 与 Ubuntu 的
`boot`、`init_boot`、`vendor_boot` 三件套。其他容量、固件、分区布局和 Pad 3 未验证。

## RAM 试用

RAM 临时启动不替换启动分区，但使用已安装根系统的临时内核仍可能写入文件和日志。
必须区分“全 RAM 根系统”和“临时内核启动持久根系统”。

开发用 RAM 桌面已验证启动、图形驱动与限时恢复，尚未提供一键试用入口。开发者试用需要
匹配的启动镜像、根系统与校验和，并确认会话超时后的恢复方式。不要混用不同构建的产物。

开发会话须绑定目标设备、有明确超时，并具备用户态恢复；panic/用户态定时器不能
保证从所有硬锁死中恢复。免认证 USB 调试通道只用于可信直连。

## 已有安装返回 Android

以下仅适用于已经建立本项目布局，并具有完整切换存储区的设备。

- Ubuntu 桌面打开 **Switch to Android（切换到 Android）**，按提示输入管理员密码，等待自动重启。
- Android 侧使用已安装的 KernelSU 切换模块；其安装和路径约定见
  [切换器说明](../switch/README.md)。
- Linux 或 Fastboot 下电量下降时，先返回 Android 充电，确认电量恢复后再继续。

两个方向的切换在既有测试布局上已有验证。切换会改写三个启动分区，不能用于尚未
安装、缺失回退镜像或布局不一致的设备。

写入失败时切换器停止，不自动重启或自动回滚；中断标记会阻止错误更新 Android 备份。
请保留电脑上的完整 Android 三件套备份；中断后使用下文的 Fastboot 恢复入口。

## 发布版预构建镜像

从 v0.2.1 起，Release 附带本文原本需要自行构建的镜像。安装仍需本仓库检出中的
`tools/install.py` 和下文列出的主机工具，但无需构建内核、Mesa 或根文件系统。

| 附件 | 用途 |
|---|---|
| `ubuntu-pad2pro-版本-rootfs.squashfs.part*` 与 `…-rootfs.manifest.json` | 用于安装的根文件系统，不含 USB 调试通道 |
| `ubuntu-pad2pro-版本-setup-rootfs.squashfs.part*` 与 `…-setup-rootfs.manifest.json` | 仅供首次准备分区时的临时内存桌面使用，含 USB 调试通道 |
| `ubuntu-pad2pro-版本-setup-boot.img` | 该临时内存桌面的启动镜像，从主机加载 setup 根文件系统 |
| `erhai-device-packages-版本.tar` | 升级已有安装用的设备包与传感器包 |
| `erhai-switch-版本.zip` | Android 侧切换模块 |
| `SHA256SUMS` | 所有附件及拼接后镜像的校验值 |

在下载目录中拼接并校验（以 v0.2.2 为例；setup 文件只在首次准备分区时需要）：

```sh
cat ubuntu-pad2pro-v0.2.2-rootfs.squashfs.part* > ubuntu-pad2pro-v0.2.2-rootfs.squashfs
cat ubuntu-pad2pro-v0.2.2-setup-rootfs.squashfs.part* > ubuntu-pad2pro-v0.2.2-setup-rootfs.squashfs
sha256sum --check --ignore-missing SHA256SUMS
```

之后用它们替代下文的构建产物：首次准备分区时，把 setup 根文件系统移到
`out/desktop-root/rootfs.squashfs`，并用 `ubuntu-pad2pro-v0.2.2-setup-boot.img` 代替
`out/ram-desktop/boot-mainline.img`；安装时，把安装用根文件系统与其清单放在同一目录，
分别命名为 `rootfs.squashfs` 和 `manifest.json`，再把该 `rootfs.squashfs` 传给 `--rootfs`；
升级时，解开 `erhai-device-packages-v0.2.2.tar`，按[升级已有安装](#升级已有安装)安装其中的包。

## 首次准备 Linux 分区

本节只适用于 **512 GB OPD2413 的原厂分区布局**，Bootloader 已解锁，Android 中已有
KernelSU root 和 USB 调试权限。活动槽必须为 **A**，原厂固件须在
[已验证组合](../packaging/installation.json)中；下方 `check-device` 会在进入 RAM 桌面前检查。**首次分区会清除 Android 的应用、账户和文件，请先将个人数据备份到电脑。**
已有 `linux_rootfs` / `linux_data` 的设备跳过本节，直接使用后面的重装步骤。

该分区工具已在上述机型上完成分区创建和 Android 数据清除验证。
分区方案为 Android 200 GiB、Linux 根分区 60 GiB，其余为 Linux 数据。
它不改变活动槽、原厂启动镜像或其他 UFS 分区。

按[构建指南](BUILD.zh-CN.md)构建设备包时，先在 `build-debs.py` 命令加入 `--debug`，
再装配 `out/desktop-root/rootfs.squashfs`，以便首次准备时使用 RAM 桌面的调试通道。沿用构建指南中的
`kernel_out`、DTB 与 initramfs，生成限时 RAM 启动镜像和切换模块：

```sh
python3 tools/build-mainline-boot.py --output out/ram-desktop \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz --profile desktop \
  --rootfs out/desktop-root/rootfs.squashfs \
  --rootfs-url http://192.168.77.10:8088/rootfs.squashfs \
  --cmdline-extra 'erhai.session=1800 erhai.debug=1'
python3 tools/package-switch.py
ln -sf "$PWD/tools/prepare-dualboot.py" out/desktop-root/prepare-dualboot.py
mkdir -p out/desktop-root/rootfs.squashfs.parts
split -b 64M -d out/desktop-root/rootfs.squashfs out/desktop-root/rootfs.squashfs.parts/part
python3 -m http.server 8088 --bind 0.0.0.0 --directory out/desktop-root
```

分段文件用于避开当前 USB 长连接传输的停滞；下载完成后可删除 `.parts` 目录。
保持文件服务器运行。在另一个终端设置目标序列号，备份本机启动镜像，再临时启动：

```sh
set -e
device_serial=DEVICE_SERIAL
python3 tools/install.py --serial "$device_serial" --work out/device-check --phase check-device
device_backup="$PWD/out/device-backup-$device_serial"
mkdir -p "$device_backup"
for part in boot init_boot vendor_boot; do
  adb -s "$device_serial" exec-out su -c "cat /dev/block/by-name/${part}_a" > "$device_backup/$part.img"
done
adb -s "$device_serial" reboot bootloader
fastboot -s "$device_serial" boot out/ram-desktop/boot-mainline.img
```

电脑识别出 USB 网络后，用 `ip -br link` 查到新增接口名。将下方 `USB_INTERFACE` 换成
该接口名；文件服务器终端继续保持运行。若电脑已通过 USB DHCP 获得 `192.168.77.10`，
可跳过地址设置。调试网络只连接自己的电脑；主机需要 `curl` 和 Telnet 客户端。

```sh
sudo ip link set USB_INTERFACE up
sudo ip address replace 192.168.77.10/24 dev USB_INTERFACE
```

等待 RAM 桌面出现，再从电脑连接 `telnet 192.168.77.2 2323`。以下命令在平板的
root shell 中执行，只查看方案并保存分区表（下载成功后才执行）：

```sh
/usr/bin/busybox wget -O /run/prepare-dualboot.py http://192.168.77.10:8088/prepare-dualboot.py &&
python3 /run/prepare-dualboot.py
```

回到电脑终端，把分区表备份保存下来：

```sh
set -e
curl --fail http://192.168.77.2:8081/run/erhai-gpt-backup.bin -o "$device_backup/gpt.bin"
curl --fail http://192.168.77.2:8081/run/erhai-gpt-backup.json -o "$device_backup/gpt.json"
```

确认备份已在电脑上、接受 Android 数据全部丢失后，在同一个平板 root shell 中应用：

```sh
python3 /run/prepare-dualboot.py --erase-android && reboot bootloader
```

工具报告失败时停止，不执行下面的擦除。在工具成功、平板回到 Fastboot 后，从电脑执行：

```sh
set -e
fastboot -s "$device_serial" erase userdata
fastboot -s "$device_serial" erase metadata
fastboot -s "$device_serial" reboot
```

完成 Android 的初始化；若原厂恢复界面要求格式化数据，完成该步骤。重新安装 KernelSU
管理应用，恢复 USB 调试，并在 KernelSU 的“超级用户”中允许 **Shell（ADB）** 使用 root。
清除 Android 数据会重置这项授权；仅开启 USB 调试还不够。从电脑把模块传到平板：

```sh
adb -s "$device_serial" push out/erhai-switch-v0.2.2.zip /sdcard/Download/
```

在 KernelSU 中选择“下载”目录里的 ZIP 安装，重启 Android，随后执行下面的 Linux 安装步骤。

若分区写入中断，保留电脑上的备份，重新进入 RAM 桌面，用 `sgdisk --load-backup=备份路径 /dev/sda`
恢复原分区表，再运行 `sgdisk --verify /dev/sda` 检查。恢复分区表不能恢复已擦除的数据。

## 既有 Linux 分区的全新安装

安装器适用于已建立 `linux_rootfs` 与 `linux_data`、当前活动槽为 **A** 的 OPD2413 双系统布局。这一路径已完成清空重装、启动三件套读回、普通重启和双系统往返验证。
它保留 Android 数据和 GPT；清空两个 Linux 分区，并通过既有切换器安装
Ubuntu 启动三件套。尚未划分 Linux 分区的原厂设备不适用这一流程。

主机需要 amd64 Linux、rootful Docker、Android platform-tools、ARM64 binfmt、原生 C 编译器及 `dpkg-deb`。平板从 Android 开始，电量至少 50%，USB 调试与 KernelSU
root 可用，且已安装本项目的切换模块。固件须在[已验证组合](../packaging/installation.json)中；
同型号的其它 OTA 不会自动获准刷入。准备构建指南生成的 `rootfs.squashfs` 及同目录
`manifest.json`，备份目录应有足够空间存放系统安装镜像。安装器自动从固定输入构建
AOSP `ext2simg`，按 ext4 已分配块转换，保留必要的零元数据。

`backup` 只保存 Android 启动镜像和设备数据，不备份 Linux 用户文件。
需要保留的 Linux 文件请事先另行导出；下面的备份无法恢复它们。

从项目目录依次执行；序列号使用 `adb devices` 列出的本机值：

```sh
device_serial=DEVICE_SERIAL
install_work="$PWD/out/install-device"
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase backup
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase prepare \
  --rootfs out/desktop-root/rootfs.squashfs
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase install --erase-linux
```

前两步读取本机启动备份、校准并在电脑上准备镜像。第三步的 `--erase-linux` 明确确认
删除 Linux 系统和用户文件。安装器核对设备、分区和输入，清除并写入两个 Linux 分区，
返回 Android 后调用切换器，读回全部启动三件套再重启 Ubuntu。首次账户设置在平板上完成。

`install_work` 包含设备专属备份及校准，应私密保存，不上传至仓库或作为公共镜像发布。
安装器报告写入完成后，仍需检查首次启动、触控、桌面和双系统切换。

若 Ubuntu 启动失败，进入 Fastboot 后可写回本机已校验的 Android 备份：

```sh
python3 tools/install.py --serial "$device_serial" --work "$install_work" --phase restore-android
```

该命令恢复 Android 启动三件套并读回核对；Linux 分区保持重装后的内容。

## 日常使用与 USB 调试

首次分区准备使用 `--debug` 构建，包含免认证的 USB root shell 和文件服务。
需要继续开发时可以保留，并仅连接可信电脑。日常使用要关闭整个启动过程的调试，
请按[构建指南](BUILD.zh-CN.md#设备包与图形组件)重新打包同版本设备包，省略 `--debug`，
并使用新的空输出目录 `--output out/device-packages-normal`，避免混入旧调试包；
无需重编内核或重建 Ubuntu 根系统。将生成的 `device-packages-normal` 目录传入平板，
在平板终端执行：

```sh
sudo apt install ./device-packages-normal/*.deb && sudo reboot
```

普通包替换调试启动镜像，重启后不再启用 USB shell、HTTP 和调试 DHCP。
只停止桌面上的调试服务不能关闭调试镜像在启动早期提供的通道。

## 升级已有安装

新版本用 APT 直接装在已有安装之上，不重新分区、不重装 Ubuntu，也不碰 Android。
按[构建指南](BUILD.zh-CN.md#设备包与图形组件)用 `tools/build-debs.py` 和 `tools/build-sensors.py`
分别把新版本的设备包和传感器包构建到新的空输出目录，
`--debug` 的选择与已装的包保持一致。把两个目录传到平板，在平板终端执行：

```sh
sudo apt install ./device-packages/*.deb ./sensor-debs/*.deb && sudo reboot
```

也可以直接用 Release 里的 `erhai-device-packages-版本.tar`：其中的包不含 USB 调试通道，
装上后调试安装也会变成普通安装（`tar xf erhai-device-packages-v0.2.2.tar && sudo apt install ./erhai-device-packages-v0.2.2/*.deb`）。

安装时内核包会把新的启动镜像写入活动槽，旧内核包仍保留；安装时导入的传感器注册表保持不变。
新内核起不来时，按下文的恢复步骤处理。

## 异常与完整恢复

若平板无响应，同时按住 **电源键＋音量上键约 15 秒**，屏幕熄灭或出现 OnePlus
标志后松开；若只关机了，再按电源开机。此组合已在 OPD2413 上用于恢复。

启动失败后保留报错、镜像版本和备份，先确认当前系统与已完成的写入步骤。不要反复
重跑安装或混刷不同版本的启动三件套；三个分区需要作为一组核对。

切换回既有 Android 不等于恢复出厂布局。完整原厂恢复还涉及匹配固件、分区布局及
用户数据，本项目尚未提供经过独立真机验收的通用恢复流程。

保留本机启动镜像及校准备份；不得使用其他设备的校准、地址或 persist。
设备仍含非原厂镜像时不要重新锁定 Bootloader。
