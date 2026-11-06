# SSC sensors: measured support and bring-up requirements

[中文](SENSORS.md) · [Project overview](../README.en.md)

`erhai` sensors sit on an ADSP-owned bus and are reached only through the Qualcomm
Sensor Core: the FastRPC file server (`hexagonrpcd`), `libssc` and a build of
`iio-sensor-proxy` with SSC support (`erhai-sensors`).

This page records what was measured on hardware (16 GB OPD2413, ColorOS
`OPD2413_11.C.34_1340_202607031844`), what the two bring-up requirements are, and
what is still missing.

## Measured support

| Sensor | D-Bus / consumer | Measured |
|---|---|---|
| Accelerometer | `HasAccelerometer`, `AccelerometerOrientation`, `AccelerometerTilt` | Works. Orientation and tilt follow the physical pose. Automatic rotation has only been seen in the initial-setup session so far. |
| Ambient light | `HasAmbientLight`, `LightLevel` | Works. Continuous updates (measured between 70 lx and 637 lx). |
| Magnetometer | `libssc` (`ssccli --sensor=magnetometer`) | Works. Streaming readings. |
| Compass | `net.hadess.SensorProxy.Compass`, `CompassHeading` | Works. Heading updates after `ClaimCompass()` (measured 173.649094, 173.848099 …). |
| Gyroscope | `HasGyroscope`, `AngularVelocityX/Y/Z`, `ClaimGyroscope()` | Works with the patch in this series. Measured `X=0.002130 Y=0.006390 Z=0.0 rad/s`. |
| Proximity | `HasProximity` | Not available on this unit. Opening the proximity sensor on the DSP fails, and advertising the `ssc-proximity` tag does not make discovery succeed. |
| Hall, SAR | — | No `libssc` implementation exists for either, and the `pakala` MTP sensor set does not declare `bu52053nvx`/`sx932x`. Firmware and library work, not a bring-up switch. |

## Requirement 1: the per-unit registry must exist before the sensor domain attaches

The ADSP sensor protection domain reads its registry **once**, when the attach
creates it. Restarting the ADSP to re-read a different registry is not an option
on this SoC: the same ADSP also runs audio, the battery link and USB-C.

Consequences:

* Importing the registry and then only restarting `erhai-sensors-rpcd.service`
  is not enough. The domain is already attached and keeps the configuration it
  read first.
* `erhai-sensors-gate.service` fails with
  `no imported sensor registry at /var/lib/erhai/sensors/persist/registry` when
  the registry is missing at attach time, and `iio-sensor-proxy` never publishes
  the accelerometer.

For a RAM desktop session this means the registry has to be in place *before*
`erhai-sensors-rpcd.service` starts. One way, used for the measurements above, is
a oneshot unit ordered before it that copies the tablet's own
`/mnt/vendor/persist/sensors/registry/registry` into
`/var/lib/erhai/sensors/persist/registry` (imported with
`erhai-sensors-import-registry`) and symlinks
`/vendor/etc/sensors/config` to the ODM sensor configuration served by
`hexagonrpcd`. Installed systems keep the imported registry on disk, so this is
only needed for temporary roots.

## Requirement 2: the FastRPC node must announce the sensor types to claim

`iio-sensor-proxy` discovers SSC sensors through `IIO_SENSOR_PROXY_TYPE` on the
FastRPC misc device. `81-erhai-sensors.rules` *assigns* that property, so the
distribution rule cannot add to it. Enabling the compass needed exactly one
change:

```
ENV{IIO_SENSOR_PROXY_TYPE}="ssc-accel ssc-light ssc-compass ssc-gyro"
```

With `ssc-compass` present, the proxy logs
`Found SSC compass at /sys/devices/virtual/misc/fastrpc-adsp-secure` and registers
`net.hadess.SensorProxy.Compass`. `ssc-proximity` is deliberately left out: the
proximity sensor cannot be opened on this unit, so discovery would only fail.

## Gyroscope support

Upstream `iio-sensor-proxy` has accelerometer, light, compass and proximity
drivers only. `0006-iio-sensor-proxy-expose-the-SSC-gyroscope.patch` adds:

* `src/drv-ssc-gyro.c`: SSC gyroscope driver (udev tag `ssc-gyro`, three-axis
  `measurement` signal from `libssc`),
* a `DRIVER_TYPE_GYRO` driver type and `GyroscopeReadings`,
* `HasGyroscope`, `AngularVelocityX/Y/Z`, `ClaimGyroscope`/`ReleaseGyroscope` on
  `net.hadess.SensorProxy`,
* the matching `NUM_SENSOR_TYPES` growth so the per-type arrays cover the new
  type.

## Verifying on hardware

```sh
systemctl status erhai-sensors-rpcd erhai-sensors-gate iio-sensor-proxy

# Data plane, straight from the sensor core
/usr/lib/erhai/sensors/bin/ssccli --sensor=accelerometer --timeout=5
/usr/lib/erhai/sensors/bin/ssccli --sensor=gyroscope     --timeout=5
/usr/lib/erhai/sensors/bin/ssccli --sensor=magnetometer  --timeout=5
/usr/lib/erhai/sensors/bin/ssccli --sensor=compass       --timeout=5

# D-Bus plane
gdbus call --system --dest net.hadess.SensorProxy --object-path /net/hadess/SensorProxy \
  --method net.hadess.SensorProxy.ClaimGyroscope
gdbus call --system --dest net.hadess.SensorProxy --object-path /net/hadess/SensorProxy \
  --method org.freedesktop.DBus.Properties.Get net.hadess.SensorProxy AngularVelocityX
```

## Limits

* `81-erhai-sensors.rules` carries a *candidate* `ACCEL_MOUNT_MATRIX`
  (`0, 1, 0; -1, 0, 0; 0, 0, 1`), derived from the panel's landscape scan-out
  versus the Android sensor frame. It is not measured: rotation has only been seen in the initial-setup session, and the mapping
  that aligns touch coordinates with each of the four orientations still needs a physical check. Without the candidate the proxy
  would use the identity matrix instead.
* Proximity, Hall and SAR remain unavailable for the reasons in the table above.
