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
| 电源键唤醒 | 可用 —— `pm_wakeup_irq 21`（`pmic_pwrkey`） |
| v0.2.0 已装系统，RTC 闹钟 300 秒 | compat 与 standard 两种显示模式：`PM: suspend entry (s2idle)`，睡 293 秒，由 IRQ 174 唤醒，闹钟后 3 秒调试通道恢复，Wi-Fi 28 秒重连；显示、触控与传感器均恢复 |
| s2idle 中的计时 | v0.2.0 已装系统：`Timekeeping suspended for 292.961 seconds` |
| 最深电源态 | v0.5.0 候选已装系统，插着 USB 连续 26 次、每次 9 分钟的 RTC 定时挂起：每次 CX 塌陷约 100 次、累计约 532 秒，即约 98% 的挂起时间；DDR 同样进入自刷新；全部由 RTC 唤醒，Wi-Fi、蓝牙、键盘与触控均恢复 |
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

默认行为是**锁屏 + 熄屏，不进入休眠**，这是有意的：设备包里的 `erhai-power-key`
服务独占按键的 evdev 节点，以便唤醒时只恢复显示、不解除锁屏（在 greeter 与用户会话中均如此），
同时桌面自身的电源键动作在服务运行期间保持惰性。

系统休眠是**可选开关，改一个文件**：

```sh
echo suspend > /etc/erhai/power-key-action      # 下一次按下即生效
rm /etc/erhai/power-key-action                  # 回到仅锁屏+熄屏
```

存在该 marker 时，按下仍先锁屏+熄屏，随后请求 `systemctl suspend`。
唤醒同样是**按一次**：恢复路径本身已经把显示点亮，
因此"唤醒那一次按键"不能被读成"显示是亮的、再熄一次"。
`erhai-suspend-cycle.sh` 在 **pre（挂起之前）** 阶段置标记，
服务把下一次按键只当作"恢复显示"（须在恢复后 15 秒内），并在消费时清除该标记。
之所以必须在 pre：写在恢复阶段的标记存在竞态——用户态在 `post` 钩子运行前就已解冻，
服务可能先读到那次唤醒按键从而再次挂起
（真机实测：post 标记方案下 12 次按键只有 5 次被正确判为唤醒）。
标记不依赖时钟：早期 RAM 镜像测量曾看到 s2idle 期间 `CLOCK_MONOTONIC` 照常前进，
而 v0.2.0 已装系统的日志为 `Timekeeping suspended for 293 seconds`，时钟行为不能作为判断依据。

`/run/erhai/power-key-action` 同样会被读取且优先，便于镜像或测试在单次启动内启用它。

## 合盖

键盘套或保护套的磁铁正对一颗霍尔开关，内核把它报成合盖开关（`SW_LID`）。合上时 logind
让系统挂起（`/etc/systemd/logind.conf.d/90-erhai-power.conf` 里的 `HandleLidSwitch=suspend`），
打开时由同一开关唤醒，桌面随即点亮锁屏。

* 合盖期间触摸屏与手写笔的输入被忽略（`erhai-cover` 服务对它们设内核的输入屏蔽）。盖板落到
  屏幕上会产生触摸，若不屏蔽，这些触摸会打断挂起前的锁屏，系统要等 logind 的延迟上限
  （约 30 秒）才挂起。
* 开盖唤醒只在**合着盖子挂起**时才武装：开着盖子时这根 GPIO 是高电平，CX 塌陷恢复后唤醒控制器
  会把它记成一个边沿，若此时也武装，系统会被这个假边沿立刻叫醒。因此用电源键挂起后再合盖、
  再开盖，不会唤醒，需要按电源键。

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
