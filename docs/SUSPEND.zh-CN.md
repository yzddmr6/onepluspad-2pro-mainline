# 系统休眠：s2idle 与电源键

[English](SUSPEND.md) · [项目首页](../README.zh-CN.md)

本项目默认使用 `s2idle`（suspend to idle）。固件也提供 `deep`
（PSCI SYSTEM_SUSPEND），不作默认的原因见“默认值”一节。
本页记录真机实测结果、电源键如何接到休眠，以及你自己怎么测。

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
按子系统给出休眠计数，是判断"到底睡多深"的依据：

```
apss  Count: 37928        ← APSS 低功耗态确实进入了
cxsd  Count: 0            ← CX 塌陷从未发生
aosd  Count: 0            ← AOSS sleep 从未发生
ddr   Count: 0
```

若要测挂起期间的耗电，请在 `/usr/lib/systemd/system-sleep/` 下放钩子，记录挂起前后电量。
注意 `rtcwake` 直接写 `/sys/power/state`，**绕过 systemd**，因此那种挂起不会触发 sleep 钩子；
请改用 `systemctl suspend`、电源键或已武装的 RTC 闹钟。

要判定"是谁唤醒的"，对比 `pm_wakeup_irq` 与上面各源计数即可：`wakeup_count` 没动的源，
即使其中断触发过，也不是唤醒原因。

## 限制

* s2idle 下没有 CX/AOSS 塌陷（见上），因此预期是"能撑过一天"，不是"数天"。属于平台性质，
  与骁龙 X Elite 笔记本相同。
* `deep`（PSCI SYSTEM_SUSPEND）默认不用。此前在本板的跟踪发现 deep 会提前结束
  且没有武装的唤醒中断：IPCC 汇总中断是 `IRQF_NO_SUSPEND`，其 irqchip 置了
  `IRQCHIP_SKIP_SET_WAKE`，于是远程处理器的信号可以完全绕过 `pm_system_irq_wakeup()`。
* 长挂起后的外设恢复（Wi-Fi、USB、音频、传感器）、拔线待机续航、以及 SoC 最深电源态仍待完善。
* 接近、霍尔与 SAR 与休眠无关，在本板上仍不可用。

## 参考

* postmarketOS wiki《Qualcomm Snapdragon 845/850》——“高通平台目前没有真正的 suspend 模式”；
  wakeirq 与 `IRQF_NO_SUSPEND` 语义；用 `wakeup_count` 反查唤醒源。
* 骁龙 X Elite 挂起笔记（Lenovo Yoga Slim 7x）——`deep` 存在但 resume 是坏的、hibernation 未编入、
  用 `qcom_stats` 量化深度，以及"平台到不了最深态"的同一结论。
* linux-surface issue 2078 —— 如何区分"中断触发了"与"中断唤醒了系统"
  （`wakeup_count` 恒 0 而 `event_count` 在动）。
