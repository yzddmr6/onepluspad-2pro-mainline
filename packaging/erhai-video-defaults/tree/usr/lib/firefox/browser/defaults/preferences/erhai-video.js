// SPDX-License-Identifier: GPL-2.0-only
// Defaults only: users retain control through about:config.
pref("media.hardware-video-decoding.enabled", true);
pref("media.ffmpeg.vaapi.enabled", true);
// Qualify this device through VA-API, including builds with a GPU blocklist.
pref("media.hardware-video-decoding.force-enabled", true);
pref("media.hardware-video-decoding-vulkan.enabled", false);
