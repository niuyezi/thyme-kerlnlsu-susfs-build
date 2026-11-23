# NOTICE — 上游来源、修改点与许可声明

本项目 `niuyezi/thyme-kerlnlsu-susfs-build` 是个人设备（Xiaomi Mi 10S / `thyme` / SM8250）的
多变体内核构建工作流与配置仓库，**不是 KernelSU / KernelSU-Next / SukiSU / SUSFS 官方项目，
未获得上游授权或背书**。本文件说明构建过程中引用的上游组件、本项目所做修改，以及分发
GPL 二进制时的义务。

## 1. 上游组件

| 组件 | 来源 | 版本 / commit | 许可证 |
|---|---|---|---|
| 内核源码 | `Flicker-Android-Devices/kernel_xiaomi_sm8250` | `e7dc99d5350d3f443946af44b196c9fa6f2cb02a`（由 boot 镜像 `Linux version` 版本串派生） | GPL-2.0-only（以源码文件头为准） |
| 原版 KernelSU | 随 Flicker 内核树附带于 `drivers/kernelsu` | 随上述内核 commit（`ksu.h` 报告 `11872`） | GPL（以各文件头为准） |
| KernelSU-Next | `KernelSU-Next/KernelSU-Next` | `legacy` 分支，`kernel/setup.sh` 在 CI 中远程注入 | `kernel/` 为 GPL-2.0-only，其余 GPL-3.0-or-later（以上游文件头为准） |
| SukiSU-Nova（原 SukiSU-Ultra，仓库已迁移） | `SukiSU-Nova/SukiSU-Nova` | `builtin` 分支（试验变体） | GPL（以文件头为准） |
| susfs4ksu | `gitlab.com/simonpunk/susfs4ksu` | `kernel-4.19` 分支（SUSFS v1.5.5，2025-02 后未更新） | GPL（以文件头为准） |
| AnyKernel3 | `osm0sis/AnyKernel3` | CI 中浅克隆 | 见上游 LICENSE |
| AOSP Clang | `prebuilts/clang/host/linux-x86` | `clang-r596125` | Apache-2.0（LLVM 各子项目许可见上游） |
| `mkdtboimg.py` | `PixelOS-AOSP/android_system_libufdt` | `seventeen` 分支 `utils/src/mkdtboimg.py` | 见文件头 |
| 设备配置 / boot 镜像 | 用户本地的 PixelOS Android 17 `thyme` 原版 `boot.img` | 由 `boot_image_url` 指定或手工提供 | 仅用于提取内嵌 `config.gz` 与重打包，不随本仓库分发 |

## 2. 本项目对内核源码的修改

所有修改都在 CI 工作流 `.github/workflows/build.yml` 中以脚本形式完成（SUSFS 两处补丁以
`patches/` 内文件形式提供），不把上游源码 vendored 进本仓库。按变体分述：

### 共用

- **剥离 Flicker 树自带的手工 hook**：`fs/exec.c`、`fs/open.c`、`drivers/tty/pty.c` 等文件中
  为原版 KernelSU 预留的 `ksu_handle_*` 调用块（`ksun-susfs` 变体除外，它保留这些 hook）。
- **删除自带原版 KernelSU 目录**（`ksun-legacy` / `sukisu-ultra`）：`drivers/kernelsu` 是实体
  目录，不删除则上游 `setup.sh` 无法替换为符号链接，后续步骤会读到错误源码。

### `ksun-legacy`（KernelSU-Next）

1. **4.19 兼容补丁**：`Kbuild` 的 `can_umount` 检测正则放宽为 `^static (inline )?int`；
   `hook/patch_memory.c` 屏蔽与 4.19 自带实现冲突的 `copy_to_kernel_nofault()` 重定义。
2. **`kernel/kernel/reboot.c`**：reboot syscall 能力检查前插入 `ksu_handle_sys_reboot()` inline
   hook（syscall-table hook 不含 reboot，缺它管理器 reboot supercall 无法工作）。
3. **`fs/stat.c`**：`SYSCALL_DEFINE2(newfstat, ...)` 返回前插入 `ksu_handle_newfstat_ret()`
   （extern 原型置于文件作用域，规避 `-Werror=declaration-after-statement`）。缺它 init 读不到
   注入的 `on post-fs-data` 段，模块系统失效。`COMPAT_SYSCALL_DEFINE2` 刻意不改。
4. 配置：`CONFIG_KSU=y`、`CONFIG_KSU_SYSCALL_TABLE_HOOK=y`，显式关闭 MANUAL/KPROBES hook 与 KPROBES。

### `ksun-susfs`（原版 KernelSU + SUSFS v1.5.5）

1. **`kernel/kernel/sys.c`**：prctl syscall 插入 `ksu_handle_prctl()` 手工 hook（无 kprobes 时
   prctl 入口不存在，管理器检测与 root 授权依赖它）。
2. **管理器签名白名单**：`apk_sign.c` 在原版签名（`c371061b…`）之外加入 KernelSU-Next 官方
   签名（`0x3e6` / `79e59011…`）。
3. **SUSFS 内核侧补丁** `patches/susfs-thyme.patch`：susfs4ksu `50_add_susfs_in_kernel-4.19.patch`
   的 thyme 预适配版（修正 8 处 hunk：fs_context 挂载路径、KABI 字段顺序、额外 include、
   may_create 签名、ROM 自带 map 伪装等）。先复制 susfs4ksu 的 `fs/` 与 `include/linux/`，再 apply。
4. **SUSFS KSU 侧补丁** `patches/susfs-ksu-thyme.patch`：对自带原版 KernelSU 的预适配
   `10_enable_susfs_for_ksu.patch`（函数更名、额外 system_ext umount 目标、签名表管理器检查、
   Makefile 去重）。
5. **System.map 硬验证**：编译后强制检查 `ksu_handle_prctl` / `ksu_handle_execveat` /
   `ksu_handle_execveat_sucompat` / `ksu_handle_faccessat` 四个符号，任一缺失即构建失败。

### AK3 打包（共用）

`Image` 以 dd 定点切片写入 boot 镜像 kernel 区（pagesize 4096 起始），不改动 header 其余部分、
ramdisk 与 AVB footer；`do.modules=0`。新 `Image` 与原 `kernel_size` 不同时，需更新 boot header
v3 的 `kernel_size` 字段（header 内 offset 8，小端 u32），且不得超过 ramdisk 起点。

## 3. 分发 GPL 二进制时的义务

本仓库产物（`Image` / AK3 zip / 重打包 `boot.img`）包含 GPL-2.0 内核二进制。对外发布时必须同时：

- 提供能够重建该二进制的完整源码：**上表内核仓库 + 准确 commit**
  （`e7dc99d5350d3f443946af44b196c9fa6f2cb02a`）+ 本仓库工作流与 `patches/` 中的全部补丁步骤；
- 保留各上游许可证文本（KernelSU-Next 的 `kernel/` 与其余部分许可证不同，不可混写）；
- 说明上表第 2 节的修改点，并保存可审计的 patch / 构建日志。

## 4. 声明

本项目自身编写的文档、脚本与工作流采用 MIT 许可证（见 `LICENSE`）；**MIT 不覆盖任何上游
代码或二进制**。商标 "KernelSU"、"KernelSU-Next"、"SukiSU"、"SUSFS" 归各自权利人所有，本文
中的引用仅用于说明构建来源，不构成官方关系或背书。

如权利人认为存在权利冲突，请在本仓库提 issue，我会立即下架相关内容。

*本文件是基于许可证文本与开源惯例的工程说明，不构成法律意见。*
