# 系统休眠：s2idle、电源键与合盖

[English](SUSPEND.md) · [项目首页](../README.zh-CN.md)

本项目默认使用 `s2idle`（suspend to idle）。固件也提供 `deep`
（PSCI SYSTEM_SUSPEND），不作默认的原因见“默认值”一节。
本页记录真机实测结果、电源键与合盖如何接到休眠，以及你自己怎么测。

## 真机实测

| | |
|---|---|
| `/sys/power/state` | `freeze mem disk` |
| `/sys/power/mem_sleep` | 固定默认前为 `s2idle [deep]`，之后为 `[s2idle] deep` |
| PSCI | `PSCIv1.1 detected`、`OSI mode supported` —— 固件广告 SYSTEM_SUSPEND，内核因此偏好 `deep` |
| CPU idle | 两个状态：`WFI` 与 `cpu-sleep-0`（retention） |
| 挂起次数 | RTC 定时与电源键触发合计 `success: 4`、`fail: 0` |
| RTC 唤醒 | 可用 —— `pm_wakeup_irq 174`（`c400000.spmi:pmic@0:rtc@6100`） |
| 电源键唤醒 | 可用 —— v0.6.0 已装系统 3/3 次按电源键锁屏挂起、再按唤醒，`pm_wakeup_irq 22`（`pmic_pwrkey`），解锁后回到桌面 |
| v0.2.0 已装系统，RTC 闹钟 300 秒 | compat 与 standard 两种显示模式：`PM: suspend entry (s2idle)`，睡 293 秒，由 IRQ 174 唤醒，闹钟后 3 秒调试通道恢复，Wi-Fi 28 秒重连；显示、触控与传感器均恢复 |
| s2idle 中的计时 | v0.2.0 已装系统：`Timekeeping suspended for 292.961 seconds` |
| 最深电源态 | v0.6.0 候选已装系统，插着 USB 连续 23 次、每次 10 分钟的 RTC 定时挂起，每次挂起前先满载 CPU 一分钟并让 GPU 反复上下电：CX 塌陷驻留 98.0–98.9%，DDR 同样进入自刷新；全部由 RTC 唤醒，Wi-Fi 与键盘每次都恢复，每 5 次检查一次前后摄均能出图（v0.5.0：26 次 × 9 分钟，约 98%） |
| 合盖唤醒 | 可用 —— `pm_wakeup_irq` 为合盖开关（`msmgpio 97 Cover`）；合上约 1 秒后进入挂起 |

电源键无需改设备树即为唤醒源：`pm8941-pwrkey.c` 读取 `wakeup-source` **或**采用按
compatible 的默认值，而 `qcom,pmk8350-pwrkey` 对应
`pon_gen3_pwrkey_data.wakeup_source_default = true`，于是驱动执行
`device_init_wakeup(dev, true)` 并在挂起前武装其中断。唤醒随后经 SPMI PMIC arbiter
（其 irqchip 实现 `irq_set_wake`）走到 SPMI 节点已指向的 PDC 线路。

## 默认值

`tools/lib/boot_profiles.py` 里共用的 cmdline 固定 `mem_sleep_default=s2idle`。
没有它，内核会偏好固件广告的 `deep`。deep 在本板上跑过 300 秒 RTC 定时挂起，
显示、触控、Wi-Fi、蓝牙、电池和传感器都能恢复；但 deep 下 ADSP 经 IPCC/glink 中断
发来的任何消息都会让整机完整恢复，曾因此提前醒来。
s2idle 处理这类中断时不会离开挂起。

## 电源键

亮屏时，电源键现在默认先锁屏、确认锁屏已生效，再熄屏并请求系统挂起（默认 `s2idle`）。
锁屏失败时不会熄屏或请求挂起。登录界面本来就要求认证，因此只熄屏并请求挂起，不改变登录界面。
设备服务独占电源键；GNOME 的动作仍为 `nothing`，logind 的 `HandlePowerKey` 仍为 `ignore`。

如需恢复以前的仅锁屏熄屏行为，以管理员权限执行：

```sh
sudo mkdir -p /etc/erhai
printf 'blank\n' | sudo tee /etc/erhai/power-key-action
```

每次按键都会读取文件，无需重启服务。删除文件可恢复默认值，也可显式写入 `suspend`。
`/run/erhai/power-key-action` 支持相同取值，仅在本次启动内生效，优先于 `/etc`；
采用第一个有效值，跳过不存在、不可读或无法识别的值，没有有效值时默认挂起。
要清除两处覆盖：

```sh
sudo rm -f /run/erhai/power-key-action /etc/erhai/power-key-action
```

`blank` 退出开关只影响电源键，空闲与合盖挂起策略仍然生效。显示默认仍走兼容背光服务：
单纯熄屏只关闭背光，系统与显示管线仍在运行。

如果系统醒着但屏幕已熄灭，按键只恢复显示。恢复时送达的按键也只恢复显示、重置桌面空闲状态，
不会立即再次挂起。保留原有挂起周期标记：挂起前设置、消费一次，并以恢复后 15 秒为窗口区分
唤醒按键与后续按键。两种恢复路径都不会解除锁屏或绕过认证。
**当前内核下电源键从 s2idle 唤醒及重新输入密码仍须真机验证**；早期唤醒记录不能代替当前内核验证。

## 空闲策略

静置变暗、熄屏与自动挂起继承发行版默认值。本项目使用的 Ubuntu 26.04 桌面镜像，
对没有自行修改设置的用户提供以下默认值：

| 条件 | 默认行为 |
|---|---|
| 静置变暗 | 开启（`idle-dim=true`），由 GNOME 在熄屏前安排 |
| 空闲 5 分钟 | 熄屏并锁屏（`idle-delay=300`，锁屏开启） |
| 电池供电，空闲 15 分钟 | 请求挂起（`sleep-inactive-battery-type='suspend'`，超时 `900`） |
| 外部电源供电时空闲 | 正常熄屏，不自动挂起（Ubuntu 设置 `sleep-inactive-ac-timeout=0`） |

这些时限从空闲开始计算，不是在熄屏后再追加。GNOME 会遵循应用的阻止请求和用户设置；
供电类型以 UPower 上报为准。默认值来源见
[GNOME 电源默认值](https://gitlab.gnome.org/GNOME/gnome-settings-daemon/-/blob/50.0/data/org.gnome.settings-daemon.plugins.power.gschema.xml.in)
及 [Ubuntu 覆盖](https://git.launchpad.net/ubuntu/+source/ubuntu-settings/tree/debian/ubuntu-settings.gsettings-override?h=ubuntu/resolute)。
设备包不再覆盖这些空闲默认值，也不会清除个人设置。

可在**设置 → 电源**中调整时限。如果已有账户曾显式保存“永不熄屏”或“永不挂起”，
希望恢复默认值，可在该用户桌面的终端中只重置以下键（不要使用 `sudo`）：

```sh
gsettings reset org.gnome.desktop.session idle-delay
for key in idle-dim sleep-inactive-ac-type sleep-inactive-ac-timeout \
           sleep-inactive-battery-type sleep-inactive-battery-timeout; do
    gsettings reset org.gnome.settings-daemon.plugins.power "$key"
done
```

升级设备包后，先注销并重新登录，再检查策略。

## 合盖

键盘套或保护套的磁铁正对一颗霍尔开关，内核把它报成合盖开关（`SW_LID`）。合上时 logind
让系统挂起（`/etc/systemd/logind.conf.d/90-erhai-power.conf` 里的 `HandleLidSwitch=suspend`），
打开时由同一开关唤醒，桌面随即点亮锁屏。接着外屏时，桌面/logind 的正常策略会阻止合盖触发挂起。
外屏连接不会关闭电源键的显式挂起请求，也不会关闭上述空闲策略；这一组合下的显示恢复仍待真机验证。

* 合盖期间触摸屏与手写笔的输入被忽略（`erhai-cover` 服务对它们设内核的输入屏蔽）。盖板落到
  屏幕上会产生触摸，若不屏蔽，这些触摸会打断挂起前的锁屏，系统要等 logind 的延迟上限
  （约 30 秒）才挂起。
* 开盖唤醒只在**合着盖子挂起**时才武装：开着盖子时这根 GPIO 是高电平，CX 塌陷恢复后唤醒控制器
  会把它记成一个边沿，若此时也武装，系统会被这个假边沿立刻叫醒。因此开盖状态下由电源键或空闲
  策略挂起后，再合盖、开盖不会唤醒。当前内核下电源键唤醒必须经过验证。

## 如何测量一次挂起

```sh
cat /sys/power/mem_sleep                       # s2idle [deep] / [s2idle] deep
cat /sys/kernel/debug/suspend_stats            # success、fail、last_failed_dev
cat /sys/power/pm_wakeup_irq                   # 结束这次挂起的中断
for w in /sys/class/wakeup/wakeup*; do
  printf '%s %s wc=%s ac=%s ec=%s\n' "$(basename $w)" "$(cat $w/name)" \
    "$(cat $w/wakeup_count)" "$(cat $w/active_count)" "$(cat $w/event_count)"
done
```

`/sys/kernel/debug/qcom_stats`（驱动以 `CONFIG_QCOM_STATS` 构建，节点已在 `sm8750.dtsi` 中）
按子系统给出休眠计数，是判断"到底睡多深"的依据。下面是 v0.5.0 一次 9 分钟挂起前后的增量
（`Accumulated Duration` 以 19.2 MHz 计数，除以 19200000 得秒）：

```
cxsd  Count: +103   Accumulated Duration: +532 秒   ← CX 塌陷
ddr   Count: +103   Accumulated Duration: +532 秒   ← DDR 自刷新
aosd  Count: +0                                      ← 插着 USB 时 AOSS sleep 未发生
```

若要测挂起期间的耗电，请在 `/usr/lib/systemd/system-sleep/` 下放钩子，记录挂起前后电量。
注意 `rtcwake` 直接写 `/sys/power/state`，**绕过 systemd**，因此那种挂起不会触发 sleep 钩子；
请改用 `systemctl suspend`、电源键或已武装的 RTC 闹钟。

要判定"是谁唤醒的"，对比 `pm_wakeup_irq` 与上面各源计数即可：`wakeup_count` 没动的源，
即使其中断触发过，也不是唤醒原因。

## 限制

* 插着 USB 时 AOSS sleep 不发生（见上）；拔线待机的实际耗电尚未实测。
* `deep`（PSCI SYSTEM_SUSPEND）默认不用。此前在本板的跟踪发现 deep 会提前结束
  且没有武装的唤醒中断：IPCC 汇总中断是 `IRQF_NO_SUSPEND`，其 irqchip 置了
  `IRQCHIP_SKIP_SET_WAKE`，于是远程处理器的信号可以完全绕过 `pm_system_irq_wakeup()`。
* 拔线待机续航尚未实测。
* 接近与 SAR 传感器在本板上仍不可用。

## 参考

* postmarketOS wiki《Qualcomm Snapdragon 845/850》——“高通平台目前没有真正的 suspend 模式”；
  wakeirq 与 `IRQF_NO_SUSPEND` 语义；用 `wakeup_count` 反查唤醒源。
* 骁龙 X Elite 挂起笔记（Lenovo Yoga Slim 7x）——`deep` 存在但 resume 是坏的、hibernation 未编入、
  用 `qcom_stats` 量化深度。
* linux-surface issue 2078 —— 如何区分"中断触发了"与"中断唤醒了系统"
  （`wakeup_count` 恒 0 而 `event_count` 在动）。
