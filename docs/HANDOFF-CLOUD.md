# 云端 AI 交接文档：thyme 三变体 KSU 内核构建（AK3）

> 本文档包含全部关键事实、注意事项、禁止事项与故障排查路径。
> 云端 AI 拿到本文 + 6 个文件后即可开工，不需要重新调研。
> 2026-11-22 更新：从单分支（SukiSU-Nova）扩展为 **3 变体矩阵构建**。

---

## 一、任务一句话

为小米 Mi 10S（thyme / SM8250 / 骁龙870 / PixelOS Android 17 / 内核 4.19.325 非 GKI）
搭建 **3 个变体** 的 GitHub Actions 云端构建仓库，各产出 AnyKernel3 刷机包（AK3 zip）：

| 变体 ID | 内容 | hook 方式 | SUSFS | 状态 |
|---|---|---|---|---|
| `ksun-legacy` | KernelSU-Next（legacy 分支） | syscall-table + 2 个手工 hook | ❌ 无 | ✅ 旧仓库已实机验证 |
| `sukisu-susfs` | SukiSU-Nova（builtin 分支） | branch-link（免手工 hook） | ✅ 全家 | 网络核实过官方文档 |
| `bakasu` | BakaSU（曾用名 ReSukiSU） | branch-link（推断，CI 断言兜底） | 探测式（有则开） | ⚠️ 上游未核实 |

## 二、已核实的关键事实（直接用，不要重新猜）

1. **SukiSU-Ultra 已演化为 SukiSU-Nova**（github.com/SukiSU-Nova/SukiSU-Nova），
   `susfs-main` 分支已不存在（现存 main / dev / builtin / builtin-new）。
   任何教程里提到 SukiSU-Ultra susfs-main 的信息都已过时。
2. **SukiSU 用 `builtin` 分支**：无 kprobes + 手工 hook 入口 + 自带 `CONFIG_KSU_SUSFS`
   全家选项 + KPM。`main` 分支要求 `CONFIG_KPROBES=y`，而 4.19 上 kprobes hook 是禁区。
3. **4.19 ARM64 用 `CONFIG_KSU_HACK_ARM64_BRANCH_LINK=y` 可跳过全部手工 hook**
   （官方推荐 4.19+，上游验证范围 3.10~7.1；补丁失败自动回退 syscall table hook）。
   不需要 reboot.c / stat.c 的手工插桩，也绕开了 C89
   `-Werror=declaration-after-statement` 的坑。
4. **BakaSU 身份（2026-11-22 核实）**：BakaSU 是 `tiann/KernelSU` 的下游分支，
   **曾用名 ReSukiSU**（仓库 github.com/ReSukiSU/ReSukiSU），支持非 GKI 内核自编译、
   兼容 KPM、针对一加机型定向调优。**但**：分支结构、setup.sh 路径、是否带 SUSFS
   **未能从本机网络核实**（GitHub 直连被重置）。workflow 里 `[bakasu]` 步骤做了
   双仓库名回退（ReSukiSU/ReSukiSU → BakaSU/BakaSU）+ Kconfig 断言，不匹配会
   **早失败并打印该 ref 实际提供的 KSU_* 符号清单**，照着改配置即可。
5. **KernelSU-Next 活跃分支**：dev、dev-legacy、legacy-susfs（4.19 专用，要求
   MANUAL_HOOK）。旧仓库 niuyezi/thyme-ksun-build 用的 `legacy` 分支 +
   syscall-table hook + 2 个手工 hook（reboot.c 的 ksu_handle_sys_reboot、
   fs/stat.c 的 ksu_handle_newfstat_ret）已实机验证可开机。本 workflow 的
   `[ksun]` 步骤完整复刻该逻辑（含 can_umount 拼写、copy_to_kernel_nofault
   shim 两个 4.19 兼容补丁）。
6. **内核源码**：Flicker-Android-Devices/kernel_xiaomi_sm8250，提交
   `e7dc99d5350d3f443946af44b196c9fa6f2cb02a`，defconfig = `thyme_defconfig`。
7. **boot 镜像 header v3**：kernel 区固定 offset 4096，kernel_size = 53,469,208，
   ramdisk_size = 3,552,313（ramdisk 在 boot.img 内，不在 vendor_boot），
   分区大小 201,326,592 B（0xC000000），尾部有 AVB footer（设备 unlocked，verity 已放开），
   A/B 分区，当前 slot = b。
8. **Flicker 树自带旧版 KernelSU 手工 hook**（如 drivers/tty/pty.c 的
   ksu_handle_devpts，#ifdef CONFIG_KSU 包裹）。集成**任何变体**前必须先剥离这些
   纯 hook 块，否则链接期 undefined symbol（旧项目 run #6 实际踩过）。
   build.yml 里的 "Remove legacy KernelSU inline hooks" 步骤已实现该逻辑（3 变体共用）。
9. **AK3 不用 magiskboot repack**（split_boot/flash_boot 会改写 header 的
   kernel_size 并移动 ramdisk 偏移），改用 **dd 定点切片**：
   header 前 4096 B 不动、kernel 区 = 新 Image + 补 0 到原 kernel_size、
   kernel 区之后（ramdisk + AVB footer）逐字节不动。
10. **do.modules=0**：vendor 模块由 ROM 提供，自己塞 .ko 会因 vermagic /
    CONFIG_MODVERSIONS CRC 不匹配报 invalid module format。
11. **管理器对应关系**：sukisu-susfs 用 SukiSU-Nova 管理器（内置 SUSFS 一键隐藏
    界面）；ksun-legacy 用 KernelSU-Next 管理器；bakasu 用 BakaSU 管理器（或按其
    README 说明的兼容管理器）。**不同变体的管理器不能共存**，切换变体前先卸载
    旧管理器。
12. **工具链**：AOSP prebuilt clang-r596125（clang 22.0.2）+ aarch64-linux-gnu-gcc，
    Runner 用 ubuntu-22.04，均已实测可用。4.19 Makefile 硬编码 python2，需伪造
    `python2 -> python3` 包装脚本。
13. **换 ROM 必须重编**：vermagic / CONFIG_MODVERSIONS CRC 与 vendor .ko 绑定。
    换 ROM 后用 workflow 的 `boot_image_url` 输入新 boot.img 直链自动重推导。

## 三、文件清单（上传到新 GitHub 仓库，保持目录结构）

```
thyme-sukisu-susfs-build/
├── .github/workflows/build.yml   ← 3 变体矩阵构建（本次核心更新）
├── AK3/
│   ├── anykernel.sh              ← AK3 刷机脚本（dd 定点换内核，3 变体共用，
│   │                                kernel.string 由 CI 按变体自动改写）
│   ├── make_ak3_zip.py           ← 打包脚本（显式 755 权限）
│   └── verify_boot.py            ← 刷后镜像五条硬校验（离线）
├── docs/FLASH.md                 ← 刷入与回退步骤
├── docs/HANDOFF-CLOUD.md         ← 本文档
├── README.md                     ← 仓库说明 + 设计决策
└── input/device.config           ← 【需补】ROM 内核内嵌 config.gz 提取的 6329 行
```

**input/device.config 获取方式（二选一）**：
- 从旧仓库 niuyezi/thyme-ksun-build 下载 `input/device.config` 原样放入（推荐）
- 或第一次跑 workflow 时在 `boot_image_url` 填当前 ROM 的 boot.img 直链，
  CI 自动提取生成（直链必须能 curl、镜像含 -g<sha>、内嵌 config.gz，缺一不可）

## 四、workflow 怎么触发（3 变体）

1. GitHub 网页 → Actions → **thyme PixelOS multi-variant KSU kernel (AK3)** →
   Run workflow。
2. 关键参数：
   - `variants`：逗号分隔，默认 `ksun-legacy,sukisu-susfs,bakasu`（3 个全跑）。
     只跑一个就填一个，如 `sukisu-susfs`。
   - `ksun_ref`：默认 `legacy`（旧仓库验证过的分支）。
   - `sukisu_ref`：默认 `builtin`。
   - `bakasu_repo` / `bakasu_ref`：默认 `https://github.com/ReSukiSU/ReSukiSU` /
     `main`。**如果 BakaSU 断言失败**，看 `[bakasu] Assert hook method` 步骤日志里
     打印的 KSU_* 符号清单，改 ref 或改 Prepare config 步骤后重跑。
   - `boot_image_url`：首次跑建议填（自动提取 device.config + 精确 kernel_ref）。
3. 3 个变体是 **matrix 并行 job**，`fail-fast: false`——一个失败不影响其他两个。
4. 产物 artifact 名：`thyme-pixelos-ksun-legacy` / `thyme-pixelos-sukisu-susfs` /
   `thyme-pixelos-bakasu`，各自含 `thyme-<variant>-anykernel3-<sha8>.zip`
   （<sha8> = Image sha256 前 8 位）。
5. 约 13~15 分钟/变体（并行跑总时长不变）。

## 五、"推断"点（CI 失败时优先检查）

1. **SukiSU-Nova builtin 分支的 setup.sh 路径**：build.yml 优先用
   `https://raw.githubusercontent.com/SukiSU-Nova/SukiSU-Nova/builtin/kernel/setup.sh`，
   404 时自动回退官方镜像
   `https://git.zako.shirkneko.top:20004/shirkneko/SukiSU/raw/branch/main/kernel/setup.sh`。
2. **SUSFS 子选项名**（如 SUS_KSTAT_EXTEND、AUTO_ADD_SUS_BIND_MOUNT、SUS_SU 等）：
   按常见 SUSFS Kconfig 写的。断言失败时以 `kernel/drivers/kernelsu/Kconfig`
   实际内容为准增删（CI 日志里会打印）。
3. **BakaSU 的 hook 方式**（branch-link）为推断；断言步骤失败时按打印的符号
   清单调整（可能要改成 TAMPER_SYSCALL_TABLE，日志会提示）。
4. **ksun-legacy 的 4.19 兼容补丁**（can_umount 拼写、copy_to_kernel_nofault
   shim）复用旧仓库已验证逻辑，但 KSUN 上游若改了文件结构，断言会报
   "matched N 次"并打印相关行，照着改正则即可。

## 六、禁止事项（前任踩过的雷，别重踩）

1. **不要动 niuyezi/thyme-ksun-build**：那是用户日常在用的已验证仓库，只读参考。
2. **不要 git push --force**，不要改写已推送历史。
3. **token 不落盘**：不写进文件、commit、CI 日志，不回显到聊天。用完让用户撤销。
   fine-grained PAT 需要的权限：Contents 读写、Actions 读写、
   **Workflows 读写（必须，改 .github/workflows/*.yml 要单独勾）**、Metadata 读。
4. **不要下载大 artifact**（24MB 级产物），用户自己下载。只允许拉日志
   （几十 KB）和小文本。
5. **不要在 4.19 上开 kprobes hook**（Kconfig 明确要求 ≥5.10；ksun-legacy 的
   Prepare config 步骤会显式剔除 KPROBES 三件套）。
6. **不要往 AK3 包里塞任何 .ko 模块**（do.modules=0）。
7. **不要用 fastboot 刷 zip**（fastboot 只认 img；AK3 只能在 TWRP 或已 root 的
   KernelFlasher 里刷）。
8. **不要动 vendor_boot**，不要把 ramdisk 替换成 magiskinit。
9. **不要凭记忆写 hook 代码**：所有插桩点必须从官方文档抄
   （sukisu.org/guide/how-to-integrate.html；KSUN 的从旧仓库 reference 抄）。
10. **一次只验证一个变体的刷入**：3 个 zip 都能编出来，但往手机上刷时一次只刷
    一个，验完五关再换下一个，失败时分不清锅。

## 七、故障排查对照表

| 症状 | 原因 | 解法 |
|---|---|---|
| `[bakasu] Integrate` curl 404 | 仓库名/ref 推断错误 | 日志会显示尝试过的 URL；去 github.com 搜 BakaSU 确认实际仓库与分支，改 `bakasu_repo`/`bakasu_ref` 重跑 |
| `[bakasu] Assert` 失败 | hook 方式与推断不符 | 看日志打印的 KSU_* 符号清单；若提示 TAMPER_SYSCALL_TABLE，改 Prepare config 步骤后重跑 |
| `[ksun] Patch` 断言 "matched N 次" | KSUN 上游改了文件结构 | 日志打印相关行，照着改正则 |
| `Integrate SukiSU-Nova` curl 404 | GitHub raw 路径失效 | 已做官方镜像自动回退；若镜像也挂，手动换地址 |
| `Assert SukiSU-Nova symbols` 断言失败 | 用错分支（main 不带 SUSFS）或上游改结构 | 确认用 builtin 分支；按 Kconfig 实际内容调整 |
| 链接期 `undefined symbol: ksu_handle_*` | 旧 hook 剥离步骤没跑或漏剥 | 检查 "Remove legacy KernelSU inline hooks" 是否在 Integrate 之前执行；把报错文件加进剥离逻辑 |
| `olddefconfig` 后 SUSFS/KSU 选项变 n | 依赖不满足被静默改回 | 看 CI 日志里 resolved config，对照 Kconfig 依赖补齐 |
| 编译错误 `declaration-after-statement` | 有人往函数体里加了声明 | 声明放文件作用域，函数体只留调用（branch-link 变体不应有手工 hook；ksun-legacy 的 extern 已按文件作用域写） |
| AK3 刷机时 `unable to run magiskboot` | zip 里可执行文件丢了 755 | 用 make_ak3_zip.py 打包（已处理），别用系统右键压缩 |
| AK3 报 `device not supported` | device.name1 与 ro.product.device 不一致 | PixelOS 上是 thyme，已配置；强刷不推荐 |
| 刷完卡第一屏 / 直接进 fastboot | ramdisk 被动过 / kernel_size 写错 / 跨 ROM 版本刷 | `fastboot flash boot_b boot-backup.img` 回退，逐项核对 |
| 开机后 su 正常但模块全灭 | rc 注入的 st_size 修正没生效 | ksun-legacy 靠 newfstat ret hook；sukisu/bakasu 靠自带 ksud 集成；查管理器版本是否匹配 |
| SUSFS 生效后指纹/相机/WiFi 挂 | SPOOF_UNAME / SPOOF_CMDLINE 改太狠 | 先只开 SUS_MOUNT + SUS_KSTAT + SUS_PATH，逐项加回定位 |

## 八、验收标准（CI 绿 ≠ 成功，五关全过才算；每个变体单独过）

1. 能开机（不 bootloop）
2. 对应变体管理器识别并授权 su（`adb shell su -c id` 返回 uid=0）
3. 模块能用（装一个模块 → 重启 → 生效）
4. SUSFS 生效（仅 sukisu-susfs / bakasu-if-present：管理器 → 内核扩展中心 →
   SUSFS 已启用）
5. 不软重启、不掉基带（打电话 + WiFi + 指纹测试）

回退永远保留：
```bash
# 刷前备份（必须）
adb shell su -c "dd if=/dev/block/bootdevice/by-name/boot_b of=/sdcard/boot-backup.img"
# 回退
fastboot flash boot_b boot-backup.img
```

AK3 刷入时脚本自带 sha256 回读校验（kernel 区 + header 4096B），
失败自动回滚备份，不会留下坏 boot。

## 九、刷后镜像离线校验（可选，最严格）

```bash
adb shell su -c "dd if=/dev/block/bootdevice/by-name/boot_b of=/sdcard/boot-after.img"
adb pull /sdcard/boot-after.img
python AK3/verify_boot.py --original boot-backup.img --image <Image> --boot boot-after.img
```

五条全 PASS 才算刷写层完全正确：
1. 总大小 201,326,592 B 不变
2. header 前 4096 B 与原 boot 逐字节一致
3. kernel_size 之后（ramdisk + AVB footer）逐字节一致
4. kernel 区 == 新 Image + 尾部补 0
5. Image 长度 ≤ kernel_size

## 十、GitHub API 小抄（云端 AI 排查用）

```
# 触发 workflow（body: {"ref":"main","inputs":{"variants":"ksun-legacy,sukisu-susfs,bakasu"}}）
POST /repos/{owner}/{repo}/actions/workflows/build.yml/dispatches   # 204 = 成功
# 查 run / job
GET  /repos/{owner}/{repo}/actions/runs?per_page=3
GET  /repos/{owner}/{repo}/actions/runs/{run_id}/jobs
# 拉日志（job 结束后才有，运行中 404；只拉日志不拉 artifact）
GET  /repos/{owner}/{repo}/actions/jobs/{job_id}/logs
```

## 十一、给云端 AI 的关键词（直接复制）

```
任务：thyme（小米10S，SM8250，PixelOS A17，内核4.19.325非GKI，boot header v3）
三变体 KSU 内核 GitHub Actions 云端构建，产出 AnyKernel3 zip。
变体：ksun-legacy（KernelSU-Next legacy，syscall-table hook + reboot.c/stat.c
两个手工hook，无SUSFS，旧仓库已验证路径）、sukisu-susfs（SukiSU-Nova builtin，
HACK_ARM64_BRANCH_LINK，SUSFS全家）、bakasu（BakaSU，曾用名ReSukiSU，
仓库github.com/ReSukiSU/ReSukiSU，上游未核实，CI断言兜底，失败看打印的
KSU_*符号清单调整）。
内核源：Flicker-Android-Devices/kernel_xiaomi_sm8250 @ e7dc99d5350d3f443946af44b196c9fa6f2cb02a。
AK3用dd定点切片不用magiskboot repack。do.modules=0。
先剥离Flicker树自带旧KernelSU手工hook再集成变体（3变体共用该步骤）。
input/device.config 缺失：从旧仓库 niuyezi/thyme-ksun-build 下载，
或首跑填 boot_image_url 自动提取。
禁止：动旧仓库、本地跑构建、4.19开kprobes给KSU hook、fastboot刷zip。
```
