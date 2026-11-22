# 刷入与回退步骤（thyme / 三变体 KSU 内核）

> 只给命令与校验方法。刷机有风险，命令由你自己执行。

## 0. 前提确认

```bash
# 设备已解锁、当前槽位（应为 _b）
adb shell getprop ro.boot.slot_suffix

# 设备代号（应为 thyme）
adb shell getprop ro.product.device
```

**刷入通道确认（重要）**：thyme 没有独立 recovery 分区，AK3 zip 需要在
**第三方 recovery（TWRP/OrangeFox）** 里刷，或在**已有 root 的系统里用
KernelFlasher / Franco Kernel Manager** 刷。fastboot **不能**刷 zip。

- 如果你现在能进 TWRP（`fastboot boot twrp-thyme.img` 或已刷入的 recovery）→ 走第 1 节
- 如果你现在已有 root（旧 KSUN 内核还在）→ 可以直接用 KernelFlasher 刷 AK3 zip
- **两者都没有** → AK3 对你没有实际价值，先停下来解决 recovery 问题

## 1. 刷前准备（电脑上）

```bash
# 1) 从 Actions artifact 解出 zip 后校验（与 CI 日志里的 ak3zip.sha256 对比）
sha256sum thyme-<variant>-anykernel3-<sha8>.zip

# 2) 备份当前 boot（必须！回退全靠它）
adb shell su -c "dd if=/dev/block/bootdevice/by-name/boot$(adb shell getprop ro.boot.slot_suffix) of=/sdcard/boot-backup.img"
adb pull /sdcard/boot-backup.img

# 3) （可选但推荐）离线预演：如果你手上有原版 boot.img 和 Image，
#    可以先在电脑上验证打包逻辑（本仓库 AK3/verify_boot.py 是刷后校验用的）
```

## 2. 刷入（TWRP 为例）

1. 把 `thyme-<variant>-anykernel3-<sha8>.zip` 传到手机
2. 进 TWRP → Install → 选中 zip → 滑动确认
3. AK3 脚本会依次打印：
   - `header_version : 3`、`kernel_size : 53469208`、`partition size : 201326592`
   - `backup : /data/ak3-boot-backup-….img`（或 temp）
   - `kernel region : verified (sha256 match)`
   - `header 4096B : verified (byte-identical)`
4. 任何一步出现 `E:` 开头 → 脚本已自动回滚备份，**不会**留下坏 boot
5. 重启进系统

## 3. 刷后验证（五关）

```bash
# 关 1：能开机（肉眼）

# 关 2：管理器识别 + su 授权
# 装对应变体的管理器 APK（GitHub Releases 下载，三者不能共存！）
#   ksun-legacy  -> KernelSU-Next 管理器
#   sukisu-susfs -> SukiSU-Nova 管理器
#   bakasu       -> BakaSU 管理器
adb shell su -c id        # 期望 uid=0

# 关 3：模块生效（装一个模块重启后验证）

# 关 4：SUSFS 生效
# 管理器 → 内核扩展中心 → SUSFS 状态应为"已启用"
adb shell su -c "cat /proc/ksu_susfs" 2>/dev/null || echo "（以管理器显示为准）"

# 关 5：无软重启、基带/WiFi/指纹正常（肉眼 + 打电话测试）
```

## 4. 刷后镜像离线校验（可选，最严格）

如果你想把刷完的 boot 拉回来逐字节验证：

```bash
adb shell su -c "dd if=/dev/block/bootdevice/by-name/boot_b of=/sdcard/boot-after.img"
adb pull /sdcard/boot-after.img

python AK3/verify_boot.py \
  --original boot-backup.img \
  --image <CI artifact 里的 Image> \
  --boot boot-after.img
```

五条全 PASS 才算刷写层完全正确：
1. 总大小 201,326,592 B 不变
2. header 前 4096 B 与原 boot 逐字节一致
3. kernel_size 之后（ramdisk + AVB footer）逐字节一致
4. kernel 区 == 新 Image + 尾部补 0
5. Image 长度 ≤ kernel_size

## 5. 回退

```bash
# 方式一：fastboot（最稳）
fastboot flash boot_b boot-backup.img

# 方式二：TWRP 里 dd 回备份
adb shell su -c "dd if=/data/ak3-boot-backup-<时间戳>.img of=/dev/block/bootdevice/by-name/boot_b"
```

刷 boot 不动 /data，模块和授权都还在。但**换 root 方案前先卸载旧管理器**
（三种管理器互不兼容，残留的 su 与守护进程会打架）。
**一次只刷一个变体，验完五关再换下一个**，否则出问题分不清是哪个变体的锅。

## 6. 已知边界

- **换 ROM 必须重编**：vermagic / CONFIG_MODVERSIONS CRC 与 vendor .ko 绑定，
  一个内核不能通吃所有 Android 17 的 thyme。换 ROM 后用 workflow 的
  `boot_image_url` 输入新 boot.img 直链自动重推导。
- **SUSFS 子项如果开机异常**（指纹/相机/WiFi 挂）：先怀疑
  `SPOOF_UNAME`，把 `[sukisu] Prepare config` 步骤里对应行改回
  `# CONFIG_KSU_SUSFS_SPOOF_UNAME is not set` 重跑 CI。
- **KPM 默认关闭**：`CONFIG_KPM` 官方注明"可能影响系统稳定性"，
  需要时在对应 `[variant] Prepare config` 步骤里改 `CONFIG_KPM=y` 重跑。
