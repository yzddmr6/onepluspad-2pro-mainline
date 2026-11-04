# 面板背光与桌面亮度两条路径

[English](DISPLAY.en.md) · [项目主页](../README.md)

面板由单个 `led-backlight` 设备驱动（两颗 KTZ8868 合成一个背光），`erhai-display-power`
通过切换它的 `bl_power` 在不拆显示链路的情况下熄灭屏幕。本文记录它周边两条容易被混
为一谈的桌面路径。

## "自动亮度"开关在哪里

它**不在**右上角快捷菜单里——那里只有亮度滑块。开关是**设置 → 电源**里的一行，而且
GNOME 的 control center 只在下面两个条件同时成立时才显示它
（`panels/power/cc-power-panel.c`）：

* 传感器代理报告 `HasAmbientLight`（本平板为 true），且
* `has_brightness_control`——能为**会话总线**上的对象 `org.gnome.Shell.Brightness`
  （`/org/gnome/Shell/Brightness`）创建出 D-Bus 代理。

两点值得知道：

* control center 只在面板构造时求值一次，且该代理是 `DO_NOT_AUTO_START`，所以**早于
  shell 导出该名字**而打开的设置窗口，这一次没有这行——关掉重开即可；
* 自动亮度本身与开关是否显示无关：实测代理在推送环境光（`iio-sensor-proxy` 日志有
  `Streaming 'ambient_light' requests`），`ambient-enabled` 打开时亮度随环境变化
  （环境光不变时实测 1500 → 1805，满量程 2047）。

## 亮度写入路径及其唯一前提

GNOME 写背光走 logind，不走 sysfs：

```c
/* mutter: src/backends/meta-backlight-sysfs.c */
if (backlight_sysfs->session_proxy)          /* logind 有 SetBrightness */
        call_set_brightness (...);           /* ← 本平板走这条 */
else
        pkexec mutter-backlight-helper ...;  /* 仅当 logind 回 UNKNOWN_METHOD */
```

真正的写入由 logind 在 **fork 出的 root 进程**里完成（`src/login/logind-brightness.c`），
所以属性上的权限位无关紧要——`uaccess`（sysfs 没有扩展属性，`setfacl` 返回
`Operation not supported`）或改 group 都不起作用。

决定因素只有 systemd 里的一行：

```c
/* src/login/logind-session-dbus.c:693 */
if (s->seat->active != s)
        return sd_bus_error_set (error, BUS_ERROR_NOT_YOUR_DEVICE,
                                 "Session is not in foreground, refusing.");
```

会话必须是自己 seat 的 **active session**，且是在 mutter 初始化的那一刻——mutter 只
尝试一次，失败会缓存整场。实测：在 seat 还指向前一个 greeter 时启动的会话，启动时留
下一条拒绝且不再重试；从一开始就是 active 的会话则完全正常。**滑块本身始终都在屏上**，
受影响的是它的写入能否到达硬件。

## 相关

* 静置变暗与熄屏跟随 Ubuntu 默认值；时限、自动挂起与用户设置见
  [系统休眠](SUSPEND.md)。
* 熄屏与 `bl_power` 由 `erhai-display-power` 处理，与本文无关。
