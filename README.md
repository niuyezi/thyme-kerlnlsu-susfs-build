# thyme-sukisu-susfs-build

小米 10S（thyme / SM8250 / 骁龙 870，PixelOS Android 17，内核 4.19.325 非 GKI）
的 **三变体 KSU 内核**云端构建仓库。

GitHub Actions 编译内核 → 打成 AnyKernel3 zip → 你下载刷入。本地不需要任何构建环境。

## 三个变体

| 变体 ID | root 方案 | hook 方式 | SUSFS | 管理器 | 可信度 |
|---|---|---|---|---|---|
| `ksun-legacy` | KernelSU-Next `legacy` | syscall-table + reboot.c / stat.c 两个手工 hook | ❌ | KernelSU-Next 管理器 | ✅ 旧仓库已实机验证 |
| `sukisu-susfs` | SukiSU-Nova `builtin-new` | **SUSFS inline-hook**（susfs4ksu `kernel-4.19` 补丁打入内核树） | ✅ | SukiSU-Nova 管理器（内置 SUSFS 一键隐藏） | 上游 Kconfig / 官方文档核实 |
| `bakasu` | BakaSU（现名 Baka-SU/BakaSU，曾用名 ReSukiSU） | 需 KSU_MANUAL_HOOK 手工适配（**未实现**） | 未适配 | BakaSU 管理器 | ⚠️ 实验占位，默认不跑 |

三者共用：同一内核源、同一 AK3 dd 定点切片方案、同一 legacy hook 剥离步骤。
默认跑 `ksun-legacy` + `sukisu-susfs` 两个变体，matrix 并行、`fail-fast: false`。
`bakasu` 保留代码路径但默认不构建：上游 hook 机制（MANUAL_HOOK 系）与本仓库方案不同，需单独移植。

## 与 thyme-ksun-build（旧仓库）的关系

旧仓库 `niuyezi/thyme-ksun-build` **只做 KernelSU-Next 单变体且无 SUSFS**，已在日常使用，只读参考，不要改动。
本仓库的 `ksun-legacy` 变体完整复刻其已验证逻辑（含两个 4.19 兼容补丁）。

| | 旧仓库 | 本仓库 |
|---|---|---|
| 变体数 | 1（KernelSU-Next） | 3（含 SUSFS 变体） |
| AK3 刷写 | magiskboot repack | **dd 定点切片**（header/ramdisk/AVB footer 逐字节不动） |

## 仓库结构

```
.github/workflows/build.yml   ← 3 变体矩阵构建（workflow_dispatch 手动触发）
AK3/anykernel.sh              ← AK3 配置（定点内核替换，不用 magiskboot）
AK3/make_ak3_zip.py           ← 打包脚本（显式 755 权限）
AK3/verify_boot.py            ← 刷机包 boot 镜像五条硬校验（离线）
input/device.config           ← ROM 内核内嵌 config.gz 提取的 6329 行（【需补】换 ROM 必须重提）
docs/FLASH.md                 ← 刷入与回退步骤
docs/HANDOFF-CLOUD.md         ← 云端 AI 交接文档（全部事实 + 禁止事项 + 排查表）
```

## 使用

1. GitHub 仓库页 → Actions → `thyme PixelOS multi-variant KSU kernel (AK3)` → Run workflow
2. `variants` 默认跑两个变体；只要一个就填 JSON 数组（如 `["sukisu-susfs"]`）
3. 首次跑建议在 `boot_image_url` 填当前 ROM 的 boot.img 直链，CI 自动提取 `input/device.config` 与精确 `kernel_ref`
4. 跑完（约 13~15 分钟）下载 artifact：
   `thyme-pixelos-ksun-legacy` / `thyme-pixelos-sukisu-susfs` / `thyme-pixelos-bakasu`，
   各含 `thyme-<variant>-anykernel3-<sha8>.zip`
5. 刷入步骤见 `docs/FLASH.md`（**一次只刷一个变体，验完五关再换**）

## 关键设计决策（为什么这么做）

1. **SukiSU-Nova `builtin-new` 分支**：`builtin` 分支只有基础 SUSFS 选项；`builtin-new` 才提供完整的 SUSFS 支持（`KSU_SUSFS_INLINE_HOOK` 等）与 KPM。无 kprobes，适合 4.19。
2. **SUSFS 必须打内核侧补丁（susfs4ksu `kernel-4.19`）**：SUSFS 启用时唯一支持的 hook 后端是 `KSU_SUSFS_INLINE_HOOK`，它依赖 susfs4ksu 补丁在 `fs/exec.c`、`fs/namei.c`、`fs/stat.c`、`fs/read_write.c`、`kernel/reboot.c`、`kernel/sys.c`、`drivers/input/input.c` 放置的 inline hook。CI 步骤：复制 `fs/` 与 `include/linux/` 文件 → `patch -p1` 应用 `50_add_susfs_in_kernel-4.19.patch` → 检查 `.rej`（有拒绝 hunk 立即失败并打印）。**不打补丁只开配置 = 编译失败或 SUSFS 无效。**
3. **不能同时开 `CONFIG_KSU_HACK_ARM64_BRANCH_LINK` / `CONFIG_KSU_TAMPER_SYSCALL_TABLE`**：两者在 Kconfig 里都 `depends on !KSU_SUSFS`，与 SUSFS 互斥（旧版 workflow 曾误用 branch-link + SUSFS 组合，断言直接失败）。
4. **ksun-legacy 保留手工 hook**：KernelSU-Next 没有 branch-link 能力，必须按旧仓库已验证的 reboot.c / stat.c 插桩（extern 放文件作用域，避开 C89 声明坑）。
5. **AK3 用 dd 定点切片而不是 magiskboot repack**：thyme 的 boot 是 header v3 + 分区尾部 AVB footer。magiskboot repack 会改写 header（kernel_size 变化）并移动 ramdisk 偏移；dd 方案保证 header 前 4096 B、kernel 区之后的所有字节（ramdisk + AVB footer）逐字节不变，新 Image 尾部补 0 到原 kernel_size。刷机时 AK3 脚本内置 sha256 回读校验，失败自动回滚备份。
6. **`do.modules=0`**：vendor 模块由 ROM 提供，自己塞 .ko 会因 vermagic / CONFIG_MODVERSIONS CRC 不匹配报 invalid module format。
7. **先剥离 Flicker 树自带旧 hook**：`drivers/tty/pty.c` 等处的 `ksu_handle_*` 是原版 KernelSU 遗留，任何变体集成后都会链接失败，必须先剥（各变体共用该步骤）。
8. **每次运行从 `input/device.config` 重新生成配置**并断言最终 `.config`（olddefconfig 可能把不满足依赖的符号悄悄改回 n）。SUSFS 子选项只写 `builtin-new` Kconfig 中真实存在的符号（`SUS_SU` / `SUS_KSTAT_EXTEND` / `AUTO_ADD_SUS_*` 是 SukiSU-Ultra 时代选项，Nova 已移除）。

## 验收标准（CI 绿 ≠ 成功，每个变体单独过五关）

1. 能开机（不 bootloop）
2. 对应管理器识别并授权 su（`adb shell su -c id` 返回 uid=0）
3. 模块能用（装一个模块 → 重启 → 生效）
4. SUSFS 生效（仅 sukisu-susfs / bakasu-if-present）
5. 不软重启、不掉基带

回退永远保留：`fastboot flash boot_b <原版 boot.img>`。
