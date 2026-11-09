# Resources 共用包

使用 `source.json` 钉住的公共配方、五个通用遥测补丁与 Ubuntu 回移包，直接安装
`resources_1.10.2-0ubuntu3.1+piano2_arm64.deb`，不复制或分叉应用实现。
在固定的来源提交下按 `ubuntu/resources/README.zh-CN.md` 构建，并将包显式传入
`tools/build-desktop-rootfs.py --device-deb`。`erhai-apps` 精确依赖此版本并设置 APT pin。
这也会阻止 Resources 的自动安全更新；发行版提供等价遥测后，需同时撤销精确依赖与 pin。
