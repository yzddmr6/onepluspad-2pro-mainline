# 构建指南

[English](BUILD.en.md) · [项目首页](../README.md)

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

## 内核 Rust 构建输入

使用 `kernel/rust-toolchain.json` 锁定的归档和版本。将 Rust 编译器与宿主标准库
安装到同一工具前缀，解包 rust-src、bindgen 和已锁定的 libclang/LLVM 包。每次
内核与树外模块调用均设置 `RUSTC`、`BINDGEN`、`RUST_LIB_SRC`（源码中的
`library/` 目录）和 `LIBCLANG_PATH`；把编译器前缀的 `bin/` 加入 `PATH`，
共享库目录加入该构建进程的 `LD_LIBRARY_PATH`，并用 `BINDGEN_EXTRA_CLANG_ARGS`
指定匹配的 Clang 18 头文件目录。发布入口在配置前拒绝不匹配的工具，并把身份
写入 `build-result.json`；打包树外模块时保留同一环境。Linux 7.4 的
`gen_init_cpio` 位于 `scripts/`，不再位于 `usr/`。

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
PROFILE=ncm ROOT_FSCK_ROOT="$ubuntu_root" OUT_DIR="$PWD/out/initramfs" \
  GEN_INIT_CPIO="$kernel_out/scripts/gen_init_cpio" tools/build-initramfs.sh
python3 tools/build-erhai-abl-symbols.py --output out/abl-dtb \
  --mainline-dtb "$kernel_out/arch/arm64/boot/dts/qcom/sm8750-erhai.dtb" \
  --dtc "$kernel_out/scripts/dtc/dtc" \
  --vendor-boot "${ERHAI_WORKSPACE:-$PWD}/cache/stock-c34/images/vendor_boot.img" \
  --dtbo-img "${ERHAI_WORKSPACE:-$PWD}/cache/stock-c34/images/dtbo.img"
python3 tools/build-mainline-boot.py --output out/mainline-boot \
  --kernel-out "$kernel_out" --dtb out/abl-dtb/erhai-abl.dtb \
  --initramfs out/initramfs/initramfs-ncm.cpio.gz
```

NCM 构建还需要 `ROOT_FSCK_ROOT` 指向本次产品构建所用、已校验的 ARM64 Ubuntu 根目录（解包目录或构建时只读挂载点）。构建器从中携带发行版 e2fsck 及全部 ELF 依赖，并在 `root-fsck-files.json` 记录各输入哈希。持久根在 rw 挂载前执行 preen；需要人工处置的错误会停止启动并保留 RAM 中的检查日志。

原厂输入必须匹配目标固件。当前封装逻辑根据已核对的 ColorOS C.34 输入选择原厂
身份条目，不能假定其他版本相同。这些命令只生成开发镜像，不能据此认定已经可以
刷写或得到 Ubuntu 桌面；设备使用范围见[试用与恢复](FLASHING.md)。

## 设备包与图形组件

同一个软件包名、版本和架构必须对应相同字节。复现发布包时使用包内记录的构建输入；
文档或来源元数据更新若会改变包内容，须使用新的组件版本，不能重打同号包。

设备内容分为内核、固件、音频、显示电源、设备支持和可选调试包，分别更新。
`erhai-kernel` 选择器精确依赖匹配的版本化镜像/模块包；音频和固件不要求所有包版本相同。

`tools/build-debs.py --help` 列出构建参数。AOSP avbtool 已由输入准备器提供；
包含启动三件套的构建使用自己的 AVB 签名密钥，密钥不进入软件包。固件从仓库读取，来源与分发边界见
[固件说明](../packaging/firmware/README.md)。音频原始源码由
[packaging/audio/source.json](../packaging/audio/source.json)锁定，默认使用准备器写入的缓存。

桌面 Mesa 与可选的 `erhai-snap-graphics` 元包的构建、安装和回退见[图形专项](GRAPHICS.md)。
Snap 元包依赖共享的 `piano-snap-graphics`，不再装配另一份 content provider。传感器入口为
`tools/build-sensors.py --help`。组件构建的输入、依赖与包行为详见
[英文构建参考](BUILD.en.md#device-packages)。

沿用上面的内核、DTB 和 initramfs 输出，完整设备包的构建示例为：

`RELEASE_VERSION` 是本次 GitHub 发布标签去掉 `v` 后的版本号，由发布流程传入；构建设备支持包时必填。它写入 `/usr/share/mainline-release/version`，供桌面更新提醒读取，与 `packaging/VERSION` 的组件版本独立。

```sh
mkdir -p keys
# 首次构建生成一次；后续保留此密钥。
test -f keys/boot.pem || openssl genpkey -algorithm RSA \
  -pkeyopt rsa_keygen_bits:4096 -out keys/boot.pem
python3 tools/build-debs.py --release-version "$RELEASE_VERSION" --output out/device-packages \
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
宿主 Mesa 在独立 resolute 根中按 Ubuntu 配方构建；传感器沿用原非特权 `unshare`
构建。两者使用各自的固定输入，不在装配用的 Docker 容器内构建：

```sh
# Build the shared Ubuntu cohort in an isolated resolute root first:
# packaging/mesa/shared/mesa/README.md
python3 tools/build-sensors.py --output out/sensor-debs
python3 tools/package-mesa.py --shared-package <piano-mesa.deb> \
  --shared-repository <complete-common-batch> --release-id erhai-<release> \
  --release-packages out/device-packages --release-packages out/sensor-debs \
  --release-packages out/shared-apps --output out/mesa-debs

args=()
for deb in out/device-packages/*.deb out/mesa-debs/*.deb out/sensor-debs/*.deb out/shared-apps/*.deb; do
  args+=(--device-deb "$deb")
done
for deb in out/app-dependencies/*.deb; do
  [ -f "$deb" ] || continue
  args+=(--dependency-deb "$deb")
done
python3 tools/build-desktop-rootfs.py --layers "${ERHAI_WORKSPACE:-$PWD}/cache/ubuntu-desktop/casper" \
  --release-repository out/mesa-debs/erhai-<release> --output out/desktop-root "${args[@]}"
```

上述命令使用 Bash。输出包括 `rootfs.squashfs`、软件包列表、构建输入与日志。
装配通过官方 APT 包加入运行依赖和设备组件，保留 Ubuntu 正常的软件源。
清单还按 URL 与 SHA-256 钉住 Mozilla 官方 Firefox deb；装配按确切版本安装它，替换
Ubuntu 的过渡包 `firefox`，设备包中的 `erhai-firefox` 配置 Mozilla APT 源供之后更新。
Mozilla 不再提供已钉住的版本时，改钉当前版本。
账户、校准、无线地址与 Android 回退镜像需要在后续安装阶段处理，不进入通用根树。

安装范围与操作见[试用、安装与恢复](FLASHING.md)。
构建清单记录本次选定的输入；请将启动镜像、根系统与校验和作为一套使用。

原始 Ubuntu 层可通过 `--layer-cache` 复用只读挂载，避免每次解包整套桌面。缓存目录的 `minimal/` 和 `standard/` 必须分别为原始两层的只读挂载，`layers.json` 必须与 `packaging/desktop/source.json` 的 `layers` 数组一致；原始压缩输入仍会校验。缓存不接受旧产品根树。共享图形库由 `piano-mesa` 提供，与 `erhai-mesa` 过渡包一起作为设备包输入。

### v0.8.0 应用输入

把共用 `piano-snap-graphics` 提供者、[固定的 Resources 包](../packaging/resources/source.json)，
以及 [GunyahVM 1.0.1](https://github.com/yzddmr6/GunyahVM) 的 `gunyahvm`、
`gunyahvm-runtime`、`gunyahvm-guest-kernel`、`gunyahvm-guest-mesa` 四包放进
`out/shared-apps`。四包的发布 URL、版本与 SHA-256 固定在
[packaging/gunyahvm/source.json](../packaging/gunyahvm/source.json)，产品镜像装配会检查四包齐全且内容匹配。Snap 提供者使用与 `packaging/mesa/shared/mesa/source.json` 一致的
Mesa 来源。GunyahVM 所需的 Ubuntu 依赖已钉在 `packaging/desktop/source.json`，由装配器获取。
其他额外的 Ubuntu 依赖 deb 才放进 `out/app-dependencies`，每个包只留一个版本；
从固定 Ubuntu snapshot 获取，并保留索引中的 URL 与 SHA-256。
`--dependency-deb` 只把包交给 APT 求解，不强制安装。装配容器不联网，输入必须包含完整依赖闭包。

装配会清除 Ubuntu generic 内核与 kdump，并保留设备内核包。已安装系统的[升级说明](UPGRADE.md)
调用同一清理命令。

装配容器默认限 4096 MiB 内存、8192 MiB 内存加交换空间；用 `--memory-mib` 和 `--jobs`
按主机余量及同时运行的构建调整。Docker 守护进程不继承调用者的用户 slice。

## 宿主 Mesa 发布批次

宿主使用共用 Ubuntu 同名 Mesa 包、标准多架构路径和 GLVND。完整同源包与 Ubuntu
原样 libdrm 保存在整版批次仓库中；libdrm 不钉版本。源码、固定补丁集和打包锁由
`packaging/mesa/shared/` 的固定导入提供；`packaging/mesa/provenance.json` 记录来源。
Snap provider 继续使用既有独立运行时。

```sh
python3 tools/package-mesa.py --shared-package <piano-mesa.deb> \
  --shared-repository <verified-common-batch> --release-id erhai-<release> \
  --release-packages <other-release-packages> --output out/host-mesa-release
```

`build-desktop-rootfs.py --release-repository <批次目录>` 保留完整仓库并将其中未显式
选择的包作为依赖提供给 APT。`--device-deb` 选择过渡包和设备包，只安装依赖需要的
子集；其他依赖也可通过既有 `--dependency-deb` 提供。显式包须与批次哈希相同。
发布附件同时包含整版仓库及上一批回退仓库。

`install.py upgrade` 保存上一版精确用户态和启动组；
`install.py rollback --product erhai` 先恢复包，再调用现有的
`erhai-switch-install-ubuntu-images`。操作顺序见 [UPGRADE](UPGRADE.md)。

## NPU 运行库和离线演示

`python3 tools/build-npu.py --cache out/npu-cache --output out/npu-build --download`
从固定源码构建 glibc FastRPC、llama.cpp 和 v79 DSP 计算库，并打包固定模型。
复建时去掉 `--download` 可禁止联网。把生成的运行库、演示模型和本机型NPU固件包同时交给根镜像构建入口；用法见
[运行库说明](../packaging/npu/README.md)。Hexagon SDK 仅用于构建，不随运行库分发。

CDSP 固件和原厂 DSP 运行文件已随仓库提供，正常构建不需要原厂分区或安装时提取。
来源和哈希见固件清单与 `firmware/npu/source.json`；未取得再分发许可，权利方要求时移除。
根镜像同时收录 `qcom-npu-runtime`、`qcom-npu-demo-model` 和 `erhai-npu-firmware`。

## 独立构建组件组

0.9.0 按输入身份保留各组件的原始归档与构建记录。Mesa 变更时，
完整重建宿主同源包和独立的 gpu-2404 提供者，并递增其版本；其他输入未变的组件
复用已校验归档，不重新压缩或以同一版本号重新生成不同内容。

内核基线变化只重建匹配的内核、模块与启动镜像组；小米还重建同 ABI 的相机
loopback 模块。根镜像、整版 APT 仓库与附件始终用最终组件重新装配和校验。
GunyahVM 1.2.0 的输入锁包含四个应用包、两个 Casilda 包和九个系统依赖。
组装时将整组放入发布包池。换版时更新该组的源锁，再重跑整组升级、
回退及应用门槛，无需重编 Mesa。宿主 Mesa 与 Snap 的构建输出目录分别保留。
