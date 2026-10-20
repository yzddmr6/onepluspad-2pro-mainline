# Device firmware

The 77 binaries under this directory provide the firmware for this tablet's
enabled drivers and its audio and video candidates, laid out exactly as they install under
`/usr/lib/firmware`. `tools/build-debs.py` packs them into `erhai-firmware`
after checking each one against the sha256 and size recorded in
[`../firmware-manifest.json`](../firmware-manifest.json), which is the per-file
provenance record: the input every file came from and its path inside it.

## Included firmware versions

Firmware and the stock boot build inputs are included in the repository. Normal
builds require no ROM download or manual extraction. The vendor firmware set is
from **ColorOS `OPD2413_11.C.34_1340_202607031844`**; the ROCKNIX firmware set is
pinned to **`2b7207cfcb80c53c09dc6e04165789ecaf2d3348`**. The four linux-firmware
files are identified individually in the adjacent manifest. These are firmware
source versions; the project release is **v0.2.2**.

## Origin

| Files | From | What |
|---|---|---|
| 59 | the OnePlus Pad 2 Pro official ColorOS OTA `OPD2413_11.C.34_1340_202607031844`: 58 out of `modem.img`, one out of `dtbo.img` | the ADSP PIL set under `qcom/sm8750/erhai/`, and the NT36536 touch application firmware, which the vendor keeps as an overlay property rather than as a file |
| 1 | the same OTA, `odm.img:/firmware/aw882xx_acf.bin` | the unmodified AW88261 amplifier profile at `awinic/erhai/aw88261_acf.bin`; this is ROM content, not per-unit calibration |
| 1 | the same OTA, `vendor.img:/firmware/vpu35_4v.mbn` | the vendor-signed Iris (VPU 3.5) video core image at `qcom/sm8750/erhai/vpu35_4v.mbn`; linux-firmware carries no SM8750 Iris image, and this unit's TZ authenticates only the vendor-signed one |
| 1 | the same OTA, `vendor.img:/firmware/gen80000_zap.mbn` | the Adreno 830 zap shader signed for this product, at `qcom/sm8750/erhai/gen80000_zap.mbn`; see below |
| 2 | the same OTA, `odm.img:/etc/wifi/peach/bdwlan.elf` and `regdb.bin` | this product's WCN7860 board data and regulatory database, a candidate at `ath12k/WCN7860/hw2.0/erhai/`; `board-2.bin` there is the two files packed by `ath12k-bdencoder` from qca-swiss-army-knife commit `6df4dae3`, `regdb.bin` is the plain file |
| 9 | ROCKNIX `extra-firmware`, commit `2b7207cf` | WCN7860 Wi-Fi (`ath12k/`) and Bluetooth (`qca/`), which upstream linux-firmware does not carry |
| 4 | linux-firmware | Adreno 830 SQE/GMU/AQE microcode and the SM8750 zap shader signed with Qualcomm's test root |

Nothing here is modified or recompiled: each file is the bytes its input
holds, copied out and given mode 0644. The one container, the candidate
`board-2.bin`, wraps the two ODM files unchanged in the encoder's framing and
board names; the encoder is deterministic, so a refresh reproduces it byte for
byte. `tools/build-debs.py --refresh-from-rom` extracts the closure from
those inputs again and diffs it against this directory, which is how a later
ROM version gets in.
Refreshing the ODM and vendor inputs requires `fsck.erofs` from erofs-utils
and temporary space for the unpacked partitions. It runs without mounting or
preserving ROM ownership, extracts each input once, and removes the temporary
tree afterward.
Re-creating the candidate `board-2.bin` also takes the pinned
qca-swiss-army-knife archive the manifest names; the encoder is run from it
with the build's Python, never installed.
Ordinary package builds need none of these tools nor the ROM.

The two zap shaders are the same shader code: their loadable segments are
byte-identical and only the hash segment and signature differ. The
linux-firmware one chains to the SecTools test root that Qualcomm reference
devices accept and this unit's TZ refuses; the vendor one chains to OPLUS ROOT
CA 1, the same root as the ADSP image this unit already loads. Both are kept,
since another SM8750 board may need the test-signed one. The current kernel
candidate selects the vendor one with `firmware-name =
"qcom/sm8750/erhai/gen80000_zap.mbn"`; this authentication path and OpenGL
rendering have passed hardware testing. The GPU probes
before the root is mounted, so `tools/build-initramfs.sh` carries both zap
files in the initramfs.

The Wi-Fi files under `ath12k/WCN7860/hw2.0/erhai/` sit next to the ROCKNIX
`board-2.bin` and `regdb.bin` rather than over them, and the driver does not
read them. ath12k always takes `board-2.bin` from the fixed
`ath12k/WCN7860/hw2.0/` directory -- `firmware-name` applies to its other
files, never to board files -- and the ROCKNIX `board-2.bin` is ROCKNIX's
own board data for another device under this chip's board name. Switching to
this product's data means installing the candidate pair at the fixed path, in
the manifest and in the initramfs alike, since ath12k is built in and may
request the file before the root is mounted. That waits for an A/B comparison
on the device.

The current kernel candidate enables Iris and selects the board-specific image
with the standard `firmware-name` property. Firmware authentication and actual
decoding/encoding still need hardware validation.

The AW88261 profile is selected by the codec's `firmware-name` property.
Amplifier startup and signal routing have been tested; physical listening and
final gain remain unverified, and the actual DVDD supply rail is unresolved.

## License

These are proprietary Qualcomm, OnePlus and Awinic binaries. The project claims no
copyright and grants no license over them, and the repository's GPL-2.0-only
does not reach them; they are redistributed here as they came, unmodified, so
that this device's port builds from one tree. The four linux-firmware files
carry that project's `LICENSE.qcom` redistribution terms, and ROCKNIX
redistributes its nine under the terms it received them.

The stock OTA files are included to support this device. Their original vendor
terms apply; inclusion does not relicense them under the project GPL. The source
release and original paths are recorded above and in the manifest.
