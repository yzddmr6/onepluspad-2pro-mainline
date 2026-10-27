# 构建指南

[English](BUILD.md) · [项目首页](../README.zh-CN.md)

在 Linux 主机上构建内核、设备包与 Ubuntu 根系统。内核源码由
[linux-sm8750-erhai](https://github.com/yzddmr6/linux-sm8750-erhai) 单独维护，
必须使用输入清单指定的项目提交和原始输入。

## 主机与源码

使用 Linux 主机，准备 Git、Python 3、GNU make、AArch64 GCC/binutils、bc、bison、flex、
OpenSSL/ELF 开发头文件与 kmod；ccache 可选。音频构建另需 m4 和 alsa-utils。
内核版本、配置位置和工具输入见 [kernel/source.json](../kernel/source.json)。

使用 Git 获取源码，保留构建记录所需的提交身份：

```sh
git clone https://github.com/yzddmr6/onepluspad-2pro-mainline.git
cd onepluspad-2pro-mainline
git clone --filter=blob:none https://github.com/yzddmr6/linux-sm8750-erhai.git kernel/linux
kernel_commit=$(python3 -c 'import json; print(json.load(open("kernel/source.json"))["kernel"]["commit"])')
git -C kernel/linux checkout "$kernel_commit"
```

内核构建默认拒绝与清单不一致的提交。`ALLOW_UNPINNED_KERNEL=1` 仅用于明确的开发实验。

独立 checkout 使用以下布局，后续命令均从集成仓库根目录执行：

```text
onepluspad-2pro-mainline/
  kernel/linux/     匹配 source.json 中提交的独立内核 checkout
  cache/           已校验的原始输入
  out/             构建输出，不进源码仓库
```

`ERHAI_WORKSPACE` 可指定另一个包含 `kernel/linux`、`cache` 和 `out` 的工作区。
Python 入口可用 `--help` 查看参数；shell 入口采用下文的环境变量。

## 准备输入

固件、原厂启动构建输入及小型 AOSP/AudioReach 源码归档已随项目提供。普通构建
不需要下载完整原厂 ROM，也不需要手动提取固件。先执行：

```sh
python3 tools/prepare-inputs.py
```

脚本校验并解开随附输入，自动下载固定版本的 Ubuntu ARM64 BusyBox，复用已校验缓存；
不访问平板。准备需要 Python 3.11+ 与 dpkg-deb。各项来源与哈希见
[kernel/source.json](../kernel/source.json)、[固件清单](../packaging/firmware-manifest.json)
及[原厂输入清单](../packaging/boot-reference/source.json)。

| 随项目提供 | 按需从固定来源获取 |
|---|---|
| 设备固件、原厂启动构建输入、AOSP 工具源码、AudioReach 源码及设备补丁 | Ubuntu Desktop、Ubuntu 软件包、独立内核、Mesa 和传感器上游源码 |

原厂构建输入对应 OPD2413 ColorOS C.34；它们用于构建，不是通用恢复包。
本机校准、设备地址和 Android 回退备份在安装时从用户自己的平板取得。

## 内核与 RAM 启动镜像

```sh
kernel_out="$PWD/out/kernel"
OUT_DIR="$kernel_out" tools/build-kernel.sh
```

输出包括 Image、设备树、模块、最终配置及构建身份。重复构建复用兼容的 OUT 与 ccache，
不需要每次全量重编。正式候选必须保持内核和模块匹配。

输入准备器已将 BusyBox 与完整 AOSP 工具放到构建缓存。NCM initramfs 使用本次
内核生成的 `gen_init_cpio`，启动封装使用随附原厂输入：

```sh
PROFILE=ncm OUT_DIR="$PWD/out/initramfs" \
  GEN_INIT_CPIO="$kernel_out/usr/gen_init_cpio" tools/build-initramfs.sh
python3 tools/build-erhai-abl-symbols.py --output out/abl-dtb \
  --mainline-dtb "$kernel_out/arch/arm64/boot/dts/qcom/sm8750-erhai.dtb" \
  --dtc "$kernel_out/scripts/dtc/dtc" \
  --vendor-boot "${ERHAI_WORKSPACE:-$PWD}/cache/stock-c34/images/vendor_boot.img" \
  --dtbo-img "${ERHAI_WORKSPACE:-$PWD}/cache/stock-c34/images/dtbo.img"
python3 tools/build-mainline-boot.py --output out/mainline-boot \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz
```

原厂输入必须匹配目标固件。当前封装逻辑根据已核对的 ColorOS C.34 输入选择原厂
身份条目，不能假定其他版本相同。这些命令只生成开发镜像，不能据此认定已经可以
刷写或得到 Ubuntu 桌面；设备使用范围见[试用与恢复](FLASHING.zh-CN.md)。

## 设备包与图形组件

设备内容分为内核、固件、音频、显示电源、设备支持和可选调试包，分别更新。
`erhai-kernel` 选择器精确依赖匹配的版本化镜像/模块包；音频和固件不要求所有包版本相同。

`tools/build-debs.py --help` 列出构建参数。AOSP avbtool 已由输入准备器提供；
包含启动三件套的构建使用自己的 AVB 签名密钥，密钥不进入软件包。固件从仓库读取，来源与分发边界见
[固件说明](../packaging/firmware/README.md)。音频原始源码由
[packaging/audio/source.json](../packaging/audio/source.json)锁定，默认使用准备器写入的缓存。

Mesa 的构建、安装和回退见[图形专项](GRAPHICS.md)。传感器入口为
`tools/build-sensors.py --help`。组件构建的输入、依赖与包行为详见
[英文构建参考](BUILD.md#device-packages)。

沿用上面的内核、DTB 和 initramfs 输出，完整设备包的构建示例为：

```sh
mkdir -p keys
# 首次构建生成一次；后续保留此密钥。
test -f keys/boot.pem || openssl genpkey -algorithm RSA \
  -pkeyopt rsa_keygen_bits:4096 -out keys/boot.pem
python3 tools/build-debs.py --output out/device-packages \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz \
  --avb-key keys/boot.pem \
  --avbtool "${ERHAI_WORKSPACE:-$PWD}/cache/tools/avbtool.py"
```

签名密钥为 RSA-4096 PEM，`keys/` 不进入 Git。使用其他已核验固件时，可用 `--stock`
指定对应原始启动镜像，不能混用不同设备或固件的输入。


## Ubuntu Desktop 根系统

使用官方 Ubuntu Desktop 26.04 ARM64 ISO 中原始的 `minimal.squashfs` 与
`minimal.standard.squashfs`。安装 7z 后，可自动下载 ISO 并提取这两层：

```sh
python3 tools/prepare-inputs.py --desktop
```

结果位于 `${ERHAI_WORKSPACE:-$PWD}/cache/ubuntu-desktop/casper/`。已有原始层也可直接
传给装配器，按
[packaging/desktop/source.json](../packaging/desktop/source.json)校验输入。

当前装配需要 amd64 主机、rootful Docker、已配置的 ARM64 binfmt、Python 3.11+ 与
dpkg-dev。先拉取清单固定的容器镜像。装配期间容器需要额外的挂载能力；这是可信
本机构建操作，不用于运行未审阅的外部代码。

桌面硬件加速和传感器需要各自的软件包。先完成这两个组件的构建，再将它们与
前面生成的设备包一起装入根系统；每个输出目录只保留本次选定的一个版本。
这两个组件通过非特权 `unshare` 构建，主机需允许 user namespace；`--native-nir`
还要求主机 Python 可导入 Mako 与 MarkupSafe（Ubuntu：`python3-mako`、
`python3-markupsafe`）。它们使用 ARM64 binfmt，不在装配用的 Docker 容器内构建：

```sh
python3 tools/build-mesa-root.py --output out/mesa-debs --jobs 6 --native-nir
python3 tools/build-sensors.py --output out/sensor-debs

args=()
for deb in out/device-packages/*.deb out/mesa-debs/*.deb out/sensor-debs/*.deb; do
  args+=(--device-deb "$deb")
done
python3 tools/build-desktop-rootfs.py --layers "${ERHAI_WORKSPACE:-$PWD}/cache/ubuntu-desktop/casper" \
  --output out/desktop-root "${args[@]}"
```

上述命令使用 Bash。输出包括 `rootfs.squashfs`、软件包列表、构建输入与日志。
装配通过官方 APT 包加入运行依赖和设备组件，保留 Ubuntu 正常的软件源。
清单还按 URL 与 SHA-256 钉住 Mozilla 官方 Firefox deb；装配按确切版本安装它，替换
Ubuntu 的过渡包 `firefox`，设备包中的 `erhai-firefox` 配置 Mozilla APT 源供之后更新。
Mozilla 不再提供已钉住的版本时，改钉当前版本。
账户、校准、无线地址与 Android 回退镜像需要在后续安装阶段处理，不进入通用根树。

安装范围与操作见[试用、安装与恢复](FLASHING.zh-CN.md)。
构建清单记录本次选定的输入；请将启动镜像、根系统与校验和作为一套使用。
