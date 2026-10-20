# Dual boot: rotating the boot triplet through the active slot

Android and mainline Ubuntu take turns in the **active** A/B slot. Whichever
system is not installed lives as three files on the Linux root filesystem.

This design was validated on the project's established installation. On that
device, slot B contains an older firmware chain that did not boot; the tested
ABL also did not load a separate Linux kernel from `recovery`. These observations
do not establish the state of every tablet or firmware revision.

The switcher requires the matching partition layout and complete system-image
store described below. It is not a first-install or repartitioning tool.

## Hard requirement: AVB footers

`vbmeta` on this device describes `boot` as an AVB **chain partition**, which
means the bootloader reads a vbmeta structure out of the tail of the boot
partition on every cold boot. An image without that footer is not a failed
signature check but malformed metadata, and an *unlocked* bootloader still
refuses it — it drops to fastboot, for an ordinary Android boot as much as for
ours. An unknown key is fine (`verifiedbootstate=orange` tolerates it); a
missing structure is not.

So every image that goes into `boot` / `init_boot` / `vendor_boot` is signed:

```sh
python3 tools/sign-boot-triplet.py --triplet /path/to/unsigned-triplet \
    --stock /path/to/stock/images --avbtool /path/to/avbtool.py \
    --key /path/to/signing-key.pem --output out/signed-triplet
```

Run this from the integration repository root with your own matching inputs.

Partition sizes and rollback indices come from the stock images of the
firmware the device is actually running, so they are matched rather than
guessed. The footer sits in the last pages of the *partition*, which is why
the switcher always writes whole partitions.

## Files

```
erhai-switch                        the switcher; runs on both systems
erhai-switch-install-ubuntu-images   populate the store from a signed triplet
ksu-module/                          KernelSU module: the script + one button
tests/switch-selftest.sh             decision-logic self-test (files, not a device)
```

On the Ubuntu side these are not copied by hand: `erhai-device-support`
installs both scripts into `/usr/sbin` and owns the store directory, and
`erhai-kernel`'s postinst selects the triplet from its versioned payload dependency
(see the main README). The package's postinst also moves any pre-package copy
in `/usr/local/sbin` aside -- that directory comes first on root's PATH, so a
leftover there would keep shadowing the packaged switcher. On the Android side
nothing changes: the KernelSU module carries the same script and no images.

## Store layout

On the Linux root filesystem, so both systems see the same archive. Android
mounts it for the duration of a switch and unmounts it afterwards.

```
/var/lib/erhai/switch/
  ubuntu/       boot.img init_boot.img vendor_boot.img SHA256SUMS meta.json kernel.json
  ubuntu.prev/  the previous Ubuntu triplet, for a rollback without a host
  android/      refreshed from the live slot before every switch to Ubuntu
  state.json    what is in the slot, which slot, when, which hashes
  switch.log
```

`android/` is never shipped. A recognized unchanged Android set reuses its
backup; after an Android OTA or KernelSU change, the running Android system
can refresh it. Interrupted switches cannot replace that backup.

`kernel.json` preserves the package's kernel release and input identity across
store rotation; `meta.json` records the deployment. Kernel retention reads the
former. Restoring an archived set through the image installer preserves that
identity before moving the source directory.

## Build the Android module

From the project root, run `python3 tools/package-switch.py`. Install the resulting
`out/erhai-switch-v0.2.2.zip` through KernelSU and reboot Android. Transfer it first
with `adb -s DEVICE_SERIAL push out/erhai-switch-v0.2.2.zip /sdcard/Download/`,
then select the ZIP from Downloads in KernelSU. The module uses
Android `flock` or KernelSU's bundled BusyBox to serialize writes.

## Use

```sh
erhai-switch status          # what is in the slot and in the store
erhai-switch verify          # re-hash everything; exit non-zero if unusable
erhai-switch stash-android   # archive the live slot (refuses a Ubuntu slot)
erhai-switch to-ubuntu       # archive Android, install Ubuntu, reboot
erhai-switch to-android      # install the archive, reboot
```

Root: `sudo`/`pkexec` on Ubuntu, a KernelSU root shell on Android.
`--no-reboot` stops before the reboot, `--dry-run` writes nothing at all.

In a desktop session the Android direction is also an application:
`erhai-device-support` ships a **Switch to Android** entry that runs
`pkexec erhai-switch to-android` against the polkit action
`org.erhai.switch.run`, so it asks for an administrator password and nothing
else. There is deliberately no desktop entry for the other direction: from
Ubuntu the tablet is already in Ubuntu, and the way back is the KernelSU
module's button on the Android side.

Whether `erhai-switch` is on PATH on the Android side depends on KernelSU
mounting the module's `system/` over `/system`, and that mount does not
appear on every build — on the tablet's own ColorOS it does not, in the init
mount namespace either. The module directory is a real path regardless, so
the WebUI resolves the script at run time and a root shell can always use:

```sh
su -c '/data/adb/modules/erhai_switch/system/bin/erhai-switch to-ubuntu'
```

Before writing, the switcher checks the complete target set and requires each
image to match its partition's full size. A shared lock excludes another switch
or kernel update. Each write is synced and read back once. On failure it stops,
leaves the interruption marker and preserves the backups; it does not attempt
an automatic rollback or reboot. Restore the verified Android set before
retrying. Backup rotation retains `android.prev` until a subsequent refresh.

Nothing else is touched: not `recovery`, not `misc`, not `vbmeta`, not the
slot attributes, not the B slot, not xbl/tz. The slot suffix is read, never
written.

## Finding the active slot

Android 15 puts `androidboot.slot_suffix` in bootconfig. **A mainline kernel
on this ABL gets no slot suffix at all** — not on the command line, and
`/proc/bootconfig` comes up empty (the bootloader appends its own
`oplusboot.*` arguments instead). So on Linux the switcher falls back to the
GPT attribute the bootloader itself uses to choose a slot: bit 50, "active",
the same bit `fastboot --set-active` writes. `--slot _a` overrides everything.

## Known costs

* An Android OTA rewrites `recovery` and, when it updates the other slot, the
  images there. It does not touch the Linux root or the store.
* A factory reset or a large ColorOS upgrade may rebuild the GPT to the stock
  layout and take the Linux partitions with it. Keep backups.
* While Ubuntu is in the slot, recovery mode runs the mainline kernel against
  the stock recovery ramdisk and panics back into Ubuntu. Switch to Android
  before using stock recovery.
* An interrupted write needs a host with fastboot. The script narrows the
  window (verify, then write, then read back) but cannot remove it.

## Testing

`tests/switch-selftest.sh` runs the switcher against ordinary files with
`--dev-dir`, covering set validation, the archive/install/read-back cycle, the
refusal paths and dry-run. It re-execs itself under `unshare -r`, so it needs
no privileges.

It says nothing about the device: not about UFS, not about AVB, not about
whether the tablet boots afterwards. Those are device experiments, and the
cold-boot validation of a signed triplet in the active slot is recorded with
the project's device evidence.
