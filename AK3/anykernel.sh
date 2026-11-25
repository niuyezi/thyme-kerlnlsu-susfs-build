### AnyKernel3 Ramdisk Mod Script
## osm0sis @ xda-developers
## configured for Xiaomi Mi 10S (thyme) / SM8250 / PixelOS Android 17
## SukiSU-Nova builtin + SUSFS variant
##
## IMPORTANT - read carefully:
## This is NOT the stock osm0sis flow. This device's boot image uses
## Android boot image header v3 and carries an AVB footer at the end of
## the partition. The stock AK3 split_boot/flash_boot path repacks the
## image with magiskboot, which rewrites the header (kernel_size, and the
## offsets of everything after the kernel) and moves the ramdisk. On this
## device we require a byte-exact surgical replacement instead:
##   - header (first 4096 bytes)  : untouched
##   - kernel region              : new Image, zero-padded to the ORIGINAL
##                                  kernel_size read from the header
##   - everything after kernel    : untouched (ramdisk + AVB footer)
## Therefore this script does NOT call split_boot/flash_boot and does NOT
## run magiskboot at all. It uses dd with byte offsets computed from the
## header itself. See docs/FLASH.md for the matching offline verifier.

### AnyKernel setup
# global properties
properties() { '
kernel.string=SukiSU-Nova builtin+SUSFS 4.19.325 (thyme / PixelOS A17)
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=thyme
device.name2=
device.name3=
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties


### AnyKernel install
## boot files attributes
boot_attributes() {
set_perm_recursive 0 0 755 644 $RAMDISK/*;
set_perm_recursive 0 0 750 750 $RAMDISK/init* $RAMDISK/sbin;
} # end attributes

# boot shell variables
BLOCK=boot;
IS_SLOT_DEVICE=1;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching - see for reference (DO NOT REMOVE)
. tools/ak3-core.sh;

# boot install
# --- surgical kernel replacement for boot image header v3 ---------------
# ak3-core.sh has already:
#   * verified the device (do.devicecheck=1, device.name1=thyme)
#   * resolved $BLOCK to the by-name node of the CURRENT slot
#     (IS_SLOT_DEVICE=1 -> boot_b on this device right now)
#   * mounted the zip contents at $HOME/.anykernel (Image is at $HOME/Image)
# We only need busybox from tools/; magiskboot is intentionally NOT used.

ui_print " "
ui_print "  KernelSU variant : SukiSU-Nova builtin + SUSFS"
ui_print "  Target           : $BLOCK"
ui_print "  Mode             : surgical kernel swap (header v3, AVB footer preserved)"

# 1. Read the ORIGINAL header straight from the block device.
#    Header v3 layout (all uint32 LE):
#      offset 0   magic "ANDROID!"   (8 bytes)
#      offset 8   kernel_size
#      offset 12  ramdisk_size
#      offset 40  header_version
#    Kernel payload always starts at byte 4096 on v3/v4.
dd if=$BLOCK of=/tmp/ak3_header bs=4096 count=1 2>/dev/null;

MAGIC=$(dd if=/tmp/ak3_header bs=1 count=8 2>/dev/null);
if [ "$MAGIC" != "ANDROID!" ]; then
  abort "E: $BLOCK does not start with ANDROID! - refusing to touch it";
fi;

KERNEL_SIZE=$(dd if=/tmp/ak3_header bs=1 skip=8 count=4 2>/dev/null | od -An -tu4 | tr -d ' \n');
HEADER_VER=$(dd if=/tmp/ak3_header bs=1 skip=40 count=4 2>/dev/null | od -An -tu4 | tr -d ' \n');
PART_SIZE=$(blockdev --getsize64 $BLOCK 2>/dev/null);

ui_print "  header_version   : $HEADER_VER";
ui_print "  kernel_size      : $KERNEL_SIZE";
ui_print "  partition size   : $PART_SIZE";

if [ "$HEADER_VER" -lt 3 ]; then
  abort "E: expected boot image header v3+, got v$HEADER_VER - aborting";
fi;
if [ -z "$KERNEL_SIZE" ] || [ "$KERNEL_SIZE" -le 0 ] 2>/dev/null; then
  abort "E: could not read a sane kernel_size from the header";
fi;

# 2. The new Image must fit into the original kernel slot.
NEW_SIZE=$(wc -c < $HOME/Image | tr -d ' ');
if [ "$NEW_SIZE" -gt "$KERNEL_SIZE" ]; then
  abort "E: new Image ($NEW_SIZE bytes) is larger than the original kernel slot ($KERNEL_SIZE bytes) - aborting";
fi;
ui_print "  new Image size   : $NEW_SIZE (padded with zeros to $KERNEL_SIZE)";

# 3. Back up the current boot image to /data (or /tmp if /data is not
#    writable, e.g. when flashing from a recovery that has not decrypted).
BAK=/data/ak3-boot-backup-$(date +%Y%m%d-%H%M%S).img
if dd if=$BLOCK of=$BAK bs=4096 2>/dev/null && [ -s "$BAK" ]; then
  ui_print "  backup           : $BAK";
else
  BAK=/tmp/ak3-boot-backup.img
  dd if=$BLOCK of=$BAK bs=4096 2>/dev/null
  ui_print "  backup (temp)    : $BAK (recovery RAMdisk - will not survive reboot!)";
fi;

# 4. Write the new kernel at offset 4096, padded to the ORIGINAL
#    kernel_size. conv=notrunc keeps the header and everything after the
#    kernel region (ramdisk + AVB footer) byte-identical.
#    dd pads the final partial block with zeros, which is exactly the
#    padding contract required by docs/FLASH.md.
dd if=$HOME/Image of=$BLOCK bs=4096 seek=1 conv=notrunc,sync 2>/dev/null;
if [ $? -ne 0 ]; then
  abort "E: failed to write the kernel region";
fi;

# 5. Zero-fill the gap between the end of the new Image and the end of the
#    original kernel slot (dd above only zero-pads its own last block).
GAP_START=$(( (NEW_SIZE + 4095) / 4096 * 4096 + 4096 ));
GAP_LEN=$(( 4096 + KERNEL_SIZE - GAP_START ));
if [ "$GAP_LEN" -gt 0 ]; then
  if [ "$((GAP_LEN / 4096))" -gt 0 ]; then
    dd if=/dev/zero of=$BLOCK bs=4096 count=$((GAP_LEN / 4096)) seek=$((GAP_START / 4096)) conv=notrunc 2>/dev/null;
  fi
  if [ "$((GAP_LEN % 4096))" -gt 0 ]; then
    dd if=/dev/zero of=$BLOCK bs=1 count=$((GAP_LEN % 4096)) seek=$((GAP_START + GAP_LEN / 4096 * 4096)) conv=notrunc 2>/dev/null;
  fi
fi;

# 6. Read back and verify the kernel region hash matches Image + padding.
dd if=$BLOCK bs=4096 skip=1 count=$(( KERNEL_SIZE / 4096 + 1 )) 2>/dev/null | head -c $KERNEL_SIZE | sha256sum > /tmp/ak3_written.sha;
cat $HOME/Image > /tmp/ak3_expected.bin;
PAD=$(( KERNEL_SIZE - NEW_SIZE ));
if [ "$PAD" -gt 0 ]; then
  dd if=/dev/zero bs=4096 count=$((PAD / 4096)) 2>/dev/null >> /tmp/ak3_expected.bin;
  dd if=/dev/zero bs=1 count=$((PAD % 4096)) 2>/dev/null >> /tmp/ak3_expected.bin;
fi;
sha256sum /tmp/ak3_expected.bin | cut -d' ' -f1 > /tmp/ak3_expected.sha;
WRITTEN=$(cut -d' ' -f1 /tmp/ak3_written.sha);
EXPECTED=$(cat /tmp/ak3_expected.sha);
if [ "$WRITTEN" != "$EXPECTED" ]; then
  ui_print "E: kernel region verification FAILED";
  ui_print "   written : $WRITTEN";
  ui_print "   expected: $EXPECTED";
  ui_print "   restoring backup ...";
  dd if=$BAK of=$BLOCK bs=4096 2>/dev/null;
  abort "E: boot image restored from backup, kernel NOT flashed";
fi;
ui_print "  kernel region    : verified (sha256 match)";

# 7. Verify the header was not touched (first 4096 bytes unchanged).
dd if=$BLOCK of=/tmp/ak3_header_after bs=4096 count=1 2>/dev/null;
if ! cmp -s /tmp/ak3_header /tmp/ak3_header_after; then
  ui_print "E: header verification FAILED - restoring backup ...";
  dd if=$BAK of=$BLOCK bs=4096 2>/dev/null;
  abort "E: boot image restored from backup, kernel NOT flashed";
fi;
ui_print "  header 4096B     : verified (byte-identical)";

ui_print " "
ui_print "  Done! Reboot and install the SukiSU-Nova manager APK.";
ui_print "  Rollback: fastboot flash boot_b <backup img>";
## end boot install
