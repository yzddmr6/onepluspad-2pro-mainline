# SSC 传感器：实测支持情况与点亮前提

[English](SENSORS.en.md) · [项目首页](../README.md)

`erhai` 的传感器挂在 ADSP 所拥有的总线上，只能经由 Qualcomm Sensor Core 访问：
FastRPC 文件服务（`hexagonrpcd`）、`libssc`，以及一份带 SSC 支持的
`iio-sensor-proxy` 构建（`erhai-sensors`）。

本文记录在真机（16 GB `OPD2413`，ColorOS `OPD2413_11.C.34_1340_202607031844`）上的
实测结果、点亮所需的两条前提，以及目前仍然缺失的部分。

## 实测支持情况

| 传感器 | D-Bus / 使用方 | 实测 |
|---|---|---|
| 加速度计 | `HasAccelerometer`、`AccelerometerOrientation`、`AccelerometerTilt` | 可用。方向与倾角随机身姿态变化；**自动旋转目前只在初次设置会话里见到**。 |
| 环境光 | `HasAmbientLight`、`LightLevel` | 可用。持续更新（实测介于 70 lx 与 637 lx 之间）。 |
| 磁力计 | `libssc`（`ssccli --sensor=magnetometer`） | 可用。持续输出读数。 |
| 指南针 | `net.hadess.SensorProxy.Compass`、`CompassHeading` | 可用。调用 `ClaimCompass()` 后 heading 持续更新（实测 173.649094、173.848099 …）。 |
| 陀螺仪 | `HasGyroscope`、`AngularVelocityX/Y/Z`、`ClaimGyroscope()` | 配合本系列的补丁可用。实测 `X=0.002130 Y=0.006390 Z=0.0 rad/s`。 |
| 接近 | `HasProximity` | 本机不提供。在 DSP 上打开接近传感器会失败，且即使声明 `ssc-proximity` 标签，发现过程也不会成功。 |
| 霍尔、SAR | — | `libssc` 对两者都没有实现，`pakala` 的 MTP 传感器集合也未声明 `bu52053nvx`/`sx932x`。这属于固件与库的开发工作，不是开关问题。 |

## 前提一：每台机器的 registry 必须在传感器域建立之前就位

ADSP 的传感器保护域只在 attach 建立该域时读取一次 registry。在本 SoC 上无法为了
重读另一份 registry 而重启 ADSP：同一个 ADSP 还负责音频、电池链路与 USB-C。

由此产生两个后果：

* 先导入 registry、再只重启 `erhai-sensors-rpcd.service` 是不够的。该域已经建立，
  并继续沿用最初读到的配置。
* registry 在 attach 时缺失时，`erhai-sensors-gate.service` 会以
  `no imported sensor registry at /var/lib/erhai/sensors/persist/registry` 失败，
  且 `iio-sensor-proxy` 永远不会发布加速度计。

对于内存桌面会话，这意味着 registry 必须在 `erhai-sensors-rpcd.service` 启动**之前**
就位。上面各项测量采用的做法是：加一个 oneshot 单元并排在它之前，把平板自身的
`/mnt/vendor/persist/sensors/registry/registry` 复制到
`/var/lib/erhai/sensors/persist/registry`（用 `erhai-sensors-import-registry` 导入），
再把 `/vendor/etc/sensors/config` 指向由 `hexagonrpcd` 提供的 ODM 传感器配置。
已安装的系统会把导入后的 registry 留在磁盘上，因此这套流程只在临时根系统中需要。

## 前提二：FastRPC 节点必须声明可认领的传感器类型

`iio-sensor-proxy` 通过 FastRPC misc 设备上的 `IIO_SENSOR_PROXY_TYPE` 发现 SSC 传感器。
`81-erhai-sensors.rules` 对该属性是**赋值**而非追加，因此发行版的规则无法再往里面加内容。
启用指南针只需一处改动：

```
ENV{IIO_SENSOR_PROXY_TYPE}="ssc-accel ssc-light ssc-compass ssc-gyro"
```

带上 `ssc-compass` 后，代理会打印
`Found SSC compass at /sys/devices/virtual/misc/fastrpc-adsp-secure`，
并注册 `net.hadess.SensorProxy.Compass`。`ssc-proximity` 刻意不加：本机无法打开接近
传感器，声明它只会让发现过程失败。

## 陀螺仪支持

上游 `iio-sensor-proxy` 只有加速度计、光线、指南针与接近四类驱动。
`0006-iio-sensor-proxy-expose-the-SSC-gyroscope.patch` 增加了：

* `src/drv-ssc-gyro.c`：SSC 陀螺仪驱动（udev 标签 `ssc-gyro`，来自 `libssc` 的
  三轴 `measurement` 信号），
* `DRIVER_TYPE_GYRO` 驱动类型与 `GyroscopeReadings`，
* `net.hadess.SensorProxy` 上的 `HasGyroscope`、`AngularVelocityX/Y/Z`、
  `ClaimGyroscope`/`ReleaseGyroscope`，
* 相应扩大 `NUM_SENSOR_TYPES`，使按类型划分的数组覆盖新类型。

## 在真机上验证

```sh
systemctl status erhai-sensors-rpcd erhai-sensors-gate iio-sensor-proxy

# 数据面，直接来自传感器核
/usr/lib/erhai/sensors/bin/ssccli --sensor=accelerometer --timeout=5
/usr/lib/erhai/sensors/bin/ssccli --sensor=gyroscope     --timeout=5
/usr/lib/erhai/sensors/bin/ssccli --sensor=magnetometer  --timeout=5
/usr/lib/erhai/sensors/bin/ssccli --sensor=compass       --timeout=5

# D-Bus 面
gdbus call --system --dest net.hadess.SensorProxy --object-path /net/hadess/SensorProxy \
  --method net.hadess.SensorProxy.ClaimGyroscope
gdbus call --system --dest net.hadess.SensorProxy --object-path /net/hadess/SensorProxy \
  --method org.freedesktop.DBus.Properties.Get net.hadess.SensorProxy AngularVelocityX
```

## 限制

* `81-erhai-sensors.rules` 里带的是一个**候选** `ACCEL_MOUNT_MATRIX`
  （`0, 1, 0; -1, 0, 0; 0, 0, 1`），由面板横向扫描与 Android 传感器坐标系推得，并未实测：
  自动旋转目前只在初次设置会话里见到，把触摸坐标与四种朝向对齐还需要一次实机核对。若不设该候选值，
  代理会改用单位矩阵。
* 接近、霍尔与 SAR 因上表所述原因仍不可用。
