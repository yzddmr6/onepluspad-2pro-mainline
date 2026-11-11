# GNOME 设置

原有的独立作者补丁、控制中心可执行文件构建和 dpkg diversion 已退役。
`erhai-settings` 现在只为 [共享 Ubuntu GNOME 包](../shared-gnome/README.md)
提供作者配置、精确版本 pin 和旧安装的迁移。

源码与补丁只在小米平板 8 Pro 集成仓的 `ubuntu/` 维护；一加按固定提交原样导入，
保留来源和 SHA-256。不要在本目录重新添加设备专用的控制中心补丁。
