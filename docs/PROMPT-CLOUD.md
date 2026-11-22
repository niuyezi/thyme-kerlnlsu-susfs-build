# 给云端 AI 的提示词（直接整段复制）

> 用法：在云电脑/云端 AI 的对话框里，**先上传第 2 节的 7 个文件**，再把第 1 节整段粘贴发送。

---

## 1. 提示词（复制从这里开始 → 到"复制结束"为止）

```
你是我的云端构建工程师。任务：为小米 10S（thyme）搭建一个 GitHub Actions 仓库，
用三变体矩阵编译 KSU 内核并产出 AnyKernel3 刷机包（AK3 zip）。全部编译在云端，
绝不在我本地电脑跑任何构建或 clone。

【设备事实（已核实，不要再猜）】
- 机型：小米 10S，代号 thyme，SoC SM8250 (kona)，骁龙870
- 系统：PixelOS Android 17，内核 4.19.325-perf，非 GKI（只能整包替换内核，无 LKM）
- boot 镜像：Android boot header v3。magic "ANDROID!" @0；kernel_size @8 = 53,469,208；
  ramdisk_size @12 = 3,552,313（ramdisk 在 boot.img 内，不在 vendor_boot）；
  header_size @20 = 1580；header_version @40 = 3。kernel 区固定 offset 4096（v3/v4 一页，
  与 page_size 无关）。分区大小 201,326,592 B (0xC000000)。尾部有 AVB footer（设备已解锁，
  verity 已放开）。A/B 分区，当前 slot = b。注意：v3 没有 page_size 字段，offset 36 读到 0，
  千万别拿它当页大小（会 MemoryError）。
- 内核源码：Flicker-Android-Devices/kernel_xiaomi_sm8250，提交
  e7dc99d5350d3f443946af44b196c9fa6f2cb02a，defconfig = thyme_defconfig
- 工具链：AOSP prebuilt clang-r596125（clang 22.0.2）+ aarch64-linux-gnu-gcc，
  Runner ubuntu-22.04。4.19 Makefile 硬编码 python2，需伪造 python2 -> python3 包装脚本。

【三个变体（必须都支持，matrix 并行，fail-fast: false）】
1) ksun-legacy —— KernelSU-Next legacy 分支
   hook：syscall table hook + 2 个手工 hook（kernel/reboot.c 的 ksu_handle_sys_reboot，
   fs/stat.c 的 ksu_handle_newfstat_ret）；无 SUSFS。这条路径在旧仓库
   niuyezi/thyme-ksun-build 已实机验证可开机，逻辑必须完整复刻，包括两个 4.19 兼容补丁：
   a) Kbuild 里 can_umount 的 grep 正则要容忍 `static (inline )?int`
   b) hook/patch_memory.c 的 `#if LINUX_VERSION_CODE < KERNEL_VERSION(5,8,0)` 块要改成 #if 0
      （4.19 已有 copy_to_kernel_nofault）
   还要注意 C89 -Werror=declaration-after-statement：extern 原型必须放文件作用域，
   函数体内只留调用。
2) sukisu-susfs —— SukiSU-Nova builtin 分支
   hook：CONFIG_KSU_HACK_ARM64_BRANCH_LINK=y，跳过全部手工 hook（官方推荐 4.19+，
   上游验证 3.10~7.1，补丁失败自动回退 syscall table hook）。
   SUSFS：CONFIG_KSU_SUSFS=y 全家（SUS_MOUNT / AUTO_ADD_SUS_KSU_DEFAULT_MOUNT /
   AUTO_ADD_SUS_BIND_MOUNT / SUS_KSTAT / SUS_KSTAT_EXTEND / SUS_PATH / SUS_SU /
   SPOOF_UNAME / HIDE_KSU_SUSFS_SYMBOLS / OPEN_REDIRECT / SUS_MAP）。
   setup.sh 优先 https://raw.githubusercontent.com/SukiSU-Nova/SukiSU-Nova/builtin/kernel/setup.sh，
   404 时回退官方镜像
   https://git.zako.shirkneko.top:20004/shirkneko/SukiSU/raw/branch/main/kernel/setup.sh
3) bakasu —— BakaSU（曾用名 ReSukiSU，是 tiann/KernelSU 的下游分支）
   仓库默认 https://github.com/ReSukiSU/ReSukiSU，ref 默认 main。
   ⚠️ 这条上游我无法核实（分支结构 / setup.sh 路径 / 是否带 SUSFS 都不确定）。
   要求：集成步骤做双仓库名回退（ReSukiSU/ReSukiSU → BakaSU/BakaSU），
   然后加断言步骤：若 Kconfig 里有 KSU_HACK_ARM64_BRANCH_LINK 就用 branch-link；
   若只有 KSU_TAMPER_SYSCALL_TABLE 就明确报错提示改配置；
   两者都没有则打印该 ref 提供的全部 KSU_* 符号清单后失败。
   SUSFS 用探测式：Kconfig 里有 CONFIG_KSU_SUSFS 才加，没有就构建无 SUSFS 版本。

【三条必须遵守的技术约束】
A. 三个变体共用同一个前置步骤：先剥离 Flicker 内核树自带的旧版 KernelSU 手工 hook
   （drivers/tty/pty.c 的 ksu_handle_devpts 等，#ifdef CONFIG_KSU 包裹的纯 hook 块）。
   不剥会在链接期 undefined symbol（旧项目 run #6 实际踩过）。
   剥离逻辑要能识别"块内全是 ksu_handle_* 调用语句"才算纯 hook，别误删正常代码，
   剥完要断言 pty.c 里已无 ksu_handle_devpts。
B. AK3 打包绝不用 magiskboot repack（split_boot/flash_boot 会改写 header 的 kernel_size
   并移动 ramdisk 偏移，破坏 header v3 + AVB footer 的字节布局）。改用 dd 定点切片：
   header 前 4096 B 完全不动；kernel 区 = 新 Image + 补 0 到原 kernel_size；
   kernel 区之后（ramdisk + AVB footer）逐字节不动。刷机脚本要内置 sha256 回读校验
   （kernel 区 + header 4096B）和失败自动回滚备份。
   另外 AK3 的 do.modules=0（vendor 模块由 ROM 提供，自塞 .ko 会 vermagic/CRC 不匹配），
   do.devicecheck=1，device.name1=thyme，BLOCK=boot，IS_SLOT_DEVICE=1。
C. 4.19 上绝不能开 kprobes hook（Kconfig 要求 ≥5.10）。ksun-legacy 的配置生成步骤
   要显式剔除 CONFIG_KPROBES / CONFIG_KPROBE_EVENTS / CONFIG_KRETPROBES。
   每次运行都从 input/device.config 重新生成配置，并在 olddefconfig 之后对最终 .config
   做硬断言（olddefconfig 会把不满足依赖的符号悄悄改回 n）。

【我给你的文件（7 个，已按目录结构放好）】
.github/workflows/build.yml   3 变体矩阵构建全流程（已写好，你来审查+修正）
AK3/anykernel.sh              AK3 dd 定点替换脚本
AK3/make_ak3_zip.py           打包脚本（显式写 755，防 Windows 打包丢权限）
AK3/verify_boot.py            刷后镜像五条硬校验
README.md                     仓库说明 + 设计决策
docs/FLASH.md                 刷入与回退步骤
docs/HANDOFF-CLOUD.md         完整交接文档（事实/禁止事项/排查表，务必先读）

【input/device.config 缺失，两种补法（二选一）】
- 我从旧仓库 niuyezi/thyme-ksun-build 手动下载 input/device.config 上传（推荐）
- 或 workflow 首次运行时我填 boot_image_url（boot.img 直链），由 CI 自动提取：
  读 header v3 → 从 kernel 区找 "Linux version" banner 的 -g<sha> 展开成完整 commit
  → 扫描内嵌 config.gz 解压写出 input/device.config

【交付要求】
1. 先通读 docs/HANDOFF-CLOUD.md，再逐条核对 .github/workflows/build.yml。
2. 只做我要求的范围，不要顺手重写其他步骤。
3. 每处改动给出 diff 或完整文件，并说明为什么改。
4. 涉及刷机的命令只给命令和校验方法，不要替我执行。
5. 不确定的地方明确标注"推断"，不要编造 AK3/内核文档里没有的行为。
6. 最终交付：可直接推送到 GitHub 的完整文件 + 首次运行该填的参数 + 出问题时的排查路径。

【禁止事项】
- 不要动旧仓库 niuyezi/thyme-ksun-build（只读参考，我日常在用）。
- 不要在我本地电脑跑构建/clone/验证，编译全部在 GitHub Actions。
- 不要 git push --force，不要改写已推送历史。
- token 不落盘、不写进文件/commit/日志、不回显。用完我撤销。
  需要的 fine-grained PAT 权限：Contents 读写、Actions 读写、Workflows 读写（必须单独勾）、
  Metadata 读。
- 不要下载大 artifact（20MB 级产物我自己下），只允许拉日志（几十 KB）。
- 不要用 fastboot 刷 zip（fastboot 只认 img）。
- 不要动 vendor_boot，不要把 ramdisk 换成 magiskinit。

【验收标准（每个变体单独过五关，CI 绿 ≠ 成功）】
1) 能开机，不 bootloop
2) 对应管理器识别并授权 su：adb shell su -c id 返回 uid=0
3) 模块能用：装一个模块 → 重启 → 生效
4) SUSFS 生效（仅 sukisu-susfs 及 bakasu-if-present）：管理器→内核扩展中心→SUSFS 已启用
5) 不软重启、不掉基带（打电话 + WiFi + 指纹）
```

复制结束

---

## 2. 要上传给云端 AI 的 7 个文件

```
.github/workflows/build.yml
AK3/anykernel.sh
AK3/make_ak3_zip.py
AK3/verify_boot.py
README.md
docs/FLASH.md
docs/HANDOFF-CLOUD.md
```

上传时保持相对目录结构（`.github/`、`AK3/`、`docs/` 三个子目录）。

---

## 3. 如果云端 AI 只能读文本（不能收文件）

只发第 1 节提示词也能开工——提示词里已经写全了设备事实、三变体方案、
三条技术约束和禁止事项。但**必须先让它读 `docs/HANDOFF-CLOUD.md`**，
所以至少要把这一个文件的内容一起贴过去。

---

## 4. 还需要你做的事（按顺序）

### 第 1 步：准备 input/device.config（当前唯一缺口）

二选一：

- **方式 A（推荐）**：从旧仓库下载
  `https://github.com/niuyezi/thyme-ksun-build` → `input/device.config`（6329 行）
  → 原样放到新仓库 `input/device.config`
- **方式 B**：跳过，首次跑 workflow 时在 `boot_image_url` 填当前 ROM 的 boot.img 直链，
  由 CI 自动提取（直链必须能 curl、镜像含 `-g<sha>`、内嵌 config.gz，三者缺一不可）

### 第 2 步：新建 GitHub 仓库并上传文件

1. 新建仓库（建议名 `thyme-sukisu-susfs-build`，Public）
2. 上传 7 个文件 + `input/device.config`，保持目录结构
3. `.github` 是隐藏目录，网页上传要手动输入路径，或直接 `git push`

### 第 3 步：确认 token 权限（如果云端 AI 帮你推代码）

fine-grained PAT 必须勾：
- Contents：Read and write
- Actions：Read and write
- **Workflows：Read and write（必须单独勾，改 .github/workflows/*.yml 需要）**
- Metadata：Read

用完立刻撤销。

### 第 4 步：触发构建

Actions → `thyme PixelOS multi-variant KSU kernel (AK3)` → Run workflow

| 参数 | 填什么 |
|---|---|
| `variants` | `ksun-legacy,sukisu-susfs,bakasu`（全跑）或只填一个 |
| `kernel_ref` | 默认 `e7dc99d5350d3f443946af44b196c9fa6f2cb02a` |
| `ksun_ref` | 默认 `legacy` |
| `sukisu_ref` | 默认 `builtin` |
| `bakasu_repo` / `bakasu_ref` | 默认 `https://github.com/ReSukiSU/ReSukiSU` / `main` |
| `boot_image_url` | 首次跑建议填 boot.img 直链 |

### 第 5 步：看结果

- `ksun-legacy`、`sukisu-susfs` 预期能一次跑通
- `bakasu` **预期可能失败**（上游未核实）。失败时把 `[bakasu] Assert hook method`
  步骤的日志发我或云端 AI，日志会打印该 ref 实际提供的全部 `KSU_*` 符号清单，
  照着改 `bakasu_ref` 或 `[bakasu] Prepare config` 步骤即可

### 第 6 步：刷机（一次只刷一个变体）

1. 先刷 `ksun-legacy`（最保险，旧仓库已验证同路径）
2. 过完五关，卸载 KernelSU-Next 管理器
3. 再刷 `sukisu-susfs`，装 SukiSU-Nova 管理器，验 SUSFS
4. 最后再试 `bakasu`

刷前必须备份：
```bash
adb shell su -c "dd if=/dev/block/bootdevice/by-name/boot_b of=/sdcard/boot-backup.img"
adb pull /sdcard/boot-backup.img
```
回退：`fastboot flash boot_b boot-backup.img`
