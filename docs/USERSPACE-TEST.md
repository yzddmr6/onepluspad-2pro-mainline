# 用户态候选：一次上机验收

本候选尚未上机。先 RAM 启动待验内核并武装有界恢复；确认电量 ≥30%、Iris/GPU 已绑定、
无 D 状态，备好回退包。首个硬件故障立即停测、取内核日志，按设备恢复流程强制重启。
由设备会话执行者安装本批三个 deb（`sudo apt install ./erhai-*.deb`），注销再登录。
准备 3 段已知正常、有运动画面的短片：`h264.mp4`、`h265.mp4`、`vp9.webm`，每段 10–30 秒。
以下从短片目录执行，保留命令输出、浏览器日志与整段 `journalctl -kf`。

| 项目 | 命令 | 通过判据 |
|---|---|---|
| Vulkan 识别 | `timeout 30 vulkaninfo --summary` | Adreno 830 / Turnip；无 llvmpipe、无重复 Freedreno 设备 |
| Vulkan 显示 | `timeout 60 vkcube --wsi wayland --c 300` | 实体屏幕立方体连续正确旋转，正常退出、无 GPU fault |
| Vulkan 负载 | `timeout 180 vkmark` | 完成全部场景，有有效分数，画面正确，无挂起/恢复重置 |
| OpenGL 回归 | `timeout 180 glmark2-es2-wayland` | Adreno 830，全部场景结束，画面正确，无 seqno 断言/内核故障 |
| VA 能力 | `timeout 30 vainfo --display drm` | 自动加载 msm/V4L2 驱动，H.264、HEVC Main、VP9 profile 有 VLD；枚举本身不算硬解通过 |
| GStreamer 能力 | `gst-inspect-1.0 video4linux2`，逐个 `gst-inspect-1.0 v4l2h264dec` / `v4l2h265dec` / `v4l2vp9dec` | 动态工厂存在、rank 512；检查实际绑定 Iris 节点，非摄像头 |

播放器逐段执行（保持默认自动选择，不能指定 decoder 来代替默认路径验收）：

```sh
for f in h264.mp4 h265.mp4 vp9.webm; do
  GST_DEBUG='decodebin*:5,v4l2*:5' GST_DEBUG_FILE="/tmp/$f.gst.log" \
    timeout 90 gst-launch-1.0 -m -v playbin uri="file://$PWD/$f" || break
done
```

三段都须：日志中实际解码元素分别为 `v4l2h264dec`、`v4l2h265dec`、`v4l2vp9dec`，
其 CAPTURE 队列持续 DQBUF、正常 EOS；实体画面正确、声音正常（有音轨时）。同样用系统
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
