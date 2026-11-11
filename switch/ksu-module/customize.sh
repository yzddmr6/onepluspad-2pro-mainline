# SPDX-License-Identifier: GPL-2.0-only
#
# KernelSU install hook. This module carries no boot images and patches
# nothing in the system: it installs one script and a one-button WebUI.
# The Ubuntu triplet lives on the Linux root filesystem, maintained from
# Ubuntu by the erhai-kernel package, so an Android-side update can never
# hand out a stale kernel.

SKIPUNZIP=0
MODDIR_AT_RUNTIME=/data/adb/modules/erhai_switch

ui_print "- erhai dual boot switch"

if [ "$ARCH" != "arm64" ]; then
	ui_print "! this module is arm64 only (got $ARCH)"
	abort "! aborting"
fi

# One unit under test: the same script the Ubuntu side runs.
mkdir -p "$MODPATH/system/bin"
mv -f "$MODPATH/erhai-switch" "$MODPATH/system/bin/erhai-switch"
mv -f "$MODPATH/switch-common.sh" "$MODPATH/system/bin/switch-common.sh"
set_perm "$MODPATH/system/bin/switch-common.sh" 0 0 0644
set_perm "$MODPATH/system/bin/erhai-switch" 0 0 0755
set_perm_recursive "$MODPATH/webroot" 0 0 0755 0644

ui_print "- installed /system/bin/erhai-switch"
# Whether that path exists at run time is KernelSU's business, and on some
# builds its module mount never appears; the module directory always does.
ui_print "- if 'erhai-switch' is not on PATH after the reboot, call it as"
ui_print "  $MODDIR_AT_RUNTIME/system/bin/erhai-switch"
ui_print "- run 'erhai-switch status' in a root shell, or use the WebUI button"
ui_print "- it refuses to switch until the Linux root carries a signed triplet"
