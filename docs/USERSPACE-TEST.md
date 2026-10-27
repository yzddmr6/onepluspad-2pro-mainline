# 用户态候选：一次上机验收

测试前先 RAM 启动待验内核并武装有界恢复；确认电量 ≥30%、Iris/GPU 已绑定、
无 D 状态，备好回退包。首个硬件故障立即停测、取内核日志，按设备恢复流程强制重启。
由设备会话执行者安装本批三个 deb（`sudo apt install ./erhai-*.deb`），注销再登录。
准备 3 段已知正常、有运动画面的短片：`h264.mp4`、`h265.mp4`、`vp9.webm`，每段 10–30 秒。
以下从短片目录执行，保留命令输出、浏览器日志与整段 `journalctl -kf`。

| 项目 | 命令 | 通过判据 |
|---|---|---|
| Vulkan 识别 | `timeout 30 vulkaninfo --summary` | Adreno 830 / Turnip；仅一个 Adreno，列为 GPU0 / 默认设备；允许系统 llvmpipe |
| Vulkan 显示 | `timeout 60 vkcube --wsi wayland --c 300` | 实体屏幕立方体连续正确旋转，正常退出、无 GPU fault |
| Vulkan 负载 | `timeout 180 vkmark` | 完成全部场景，有有效分数，画面正确，无挂起/恢复重置 |
| OpenGL 回归 | `timeout 420 glmark2-es2-wayland` | Adreno 830，全部场景结束，画面正确，无 seqno 断言/内核故障 |
| VA 能力 | `timeout 30 vainfo --display drm` | 自动加载 msm/V4L2 驱动，H.264、HEVC Main、VP9 profile 有 VLD；枚举本身不算硬解通过 |
| GStreamer 能力 | `gst-inspect-1.0 va`，逐个 `gst-inspect-1.0 vah264dec` / `vah265dec` / `vavp9dec` | 动态工厂存在、rank 512；VA 驱动为 Iris，实际打开 Iris 解码节点 |

播放器逐段执行（保持默认自动选择，不能指定 decoder 来代替默认路径验收）：

```sh
for f in h264.mp4 h265.mp4 vp9.webm; do
  V4L2_VA_TRACE=1 GST_DEBUG='decodebin*:5,va*:5' GST_DEBUG_FILE="/tmp/$f.gst.log" \
    timeout 90 gst-launch-1.0 -m -v playbin uri="file://$PWD/$f" || break
done
```

三段都须：日志中实际解码元素分别为 `vah264dec`、`vah265dec`、`vavp9dec`，
Iris trace 中有实际提交和完成，渲染帧数持续增长、正常 EOS；实体画面正确、声音正常（有音轨时）。同样用系统
播放器各打开一段并拖动进度条；仅画面播放、低 CPU 或 `avdec_*` 不算硬解通过。

完全退出原生 Firefox 后运行（snap/Flatpak 不在这组 deb 的覆盖范围）：

```sh
MOZ_LOG='FFmpegVideo:5,PlatformDecoderModule:5' MOZ_LOG_FILE=/tmp/firefox-video \
  V4L2_VA_TRACE=1 firefox "file://$PWD/h264.mp4" \
  "file://$PWD/h265.mp4" "file://$PWD/vp9.webm" 2>/tmp/firefox-iris.log
```

逐标签播放、暂停、seek：每种编码须有对应的 VA-API decoder 初始化及持续输出帧，Iris
trace 有实际 session/解码提交，画面正确且 seek 后继续；`about:support` 硬解能力只作辅助。
确认 `about:config` 的包默认值生效、无旧用户覆盖；拒绝把 V4L2 直解或软件回退记作 VA-API。
若原生 Firefox 不支持 HEVC、沙箱拒绝视频节点或缺 decode-order 控制，记录为未通过并停在
该层，不关闭沙箱、不换浏览器构建来掩盖结果。设备会话结束后恢复临时日志/设置并核对。

当前默认路径已验证 Showtime 50 中 1280×720、30 fps、8 位 H.264/HEVC/VP9 的播放、
暂停及进度条拖动；没有使用软件解码回退。通用 `v4l2vp9dec` 在初始化 flush/restart 后
停帧的问题仍存在，本包不再提高该路径的优先级。手动覆盖 rank 选择它不属于上述通过结果。
原生 Firefox 的 VA-API 与系统播放器分别验收；截图或帧计数不替代实体听音与完整画质验收。
