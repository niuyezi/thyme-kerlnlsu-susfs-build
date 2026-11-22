# thyme-sukisu-susfs-build

小米 10S（thyme / SM8250 / 骁龙 870，PixelOS Android 17，内核 4.19.325 非 GKI）
的 **三变体 KSU 内核**云端构建仓库。

GitHub Actions 编译内核 → 打成 AnyKernel3 zip → 你下载刷入。本地不需要任何构建环境。

## 三个变体

| 变体 ID | root 方案 | hook 方式 | SUSFS | 管理器 | 可信度 |
|---|---|---|---|---|---|
| `ksun-legacy` | KernelSU-Next `legacy` | syscall-table + reboot.c / stat.c 两个手工 hook | ❌ | KernelSU-Next 管理器 | ✅ 旧仓库已实机验证 |
| `sukisu-susfs` | SukiSU-Nova `builtin` | `CONFIG_KSU_HACK_ARM64_BRANCH_LINK=y`（零手工 hook） | ✅ 全家 | SukiSU-Nova 管理器（内置 SUSFS 一键隐藏） | 官方文档核实 |
| `bakasu` | BakaSU（曾用名 ReSukiSU） | branch-link（推断） | 探测式（Kconfig 有则开） | BakaSU 管理器 | ⚠️ 上游未核实，CI 断言兜底 |

三者共用：同一内核源、同一 AK3 dd 定点切片方案、同一 legacy hook 剥离步骤。
一次触发可全跑（默认 `ksun-legacy,sukisu-susfs,bakasu`），matrix 并行、`fail-fast: false`。

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
2. `variants` 默认三个全跑；只想要一个就填一个（如 `sukisu-susfs`）
3. 首次跑建议在 `boot_image_url` 填当前 ROM 的 boot.img 直链，CI 自动提取 `input/device.config` 与精确 `kernel_ref`
4. 跑完（约 13~15 分钟）下载 artifact：
   `thyme-pixelos-ksun-legacy` / `thyme-pixelos-sukisu-susfs` / `thyme-pixelos-bakasu`，
   各含 `thyme-<variant>-anykernel3-<sha8>.zip`
5. 刷入步骤见 `docs/FLASH.md`（**一次只刷一个变体，验完五关再换**）

## 关键设计决策（为什么这么做）

1. **SukiSU-Nova `builtin` 分支**：官方文档明确 builtin = 无 kprobes + 手工 hook 入口 + **自带 SUSFS 选项**。`main` 分支要求 `CONFIG_KPROBES=y`，而 4.19 上 kprobes hook 是禁区。
2. **`CONFIG_KSU_HACK_ARM64_BRANCH_LINK=y`**：官方对 4.19+ ARM64 的推荐项（上游验证 3.10~7.1），开启后**跳过全部手工 hook**。补丁失败时自动回退 syscall table hook。
3. **ksun-legacy 保留手工 hook**：KernelSU-Next 没有 branch-link 能力，必须按旧仓库已验证的 reboot.c / stat.c 插桩（extern 放文件作用域，避开 C89 声明坑）。
4. **AK3 用 dd 定点切片而不是 magiskboot repack**：thyme 的 boot 是 header v3 + 分区尾部 AVB footer。magiskboot repack 会改写 header（kernel_size 变化）并移动 ramdisk 偏移；dd 方案保证 header 前 4096 B、kernel 区之后的所有字节（ramdisk + AVB footer）逐字节不变，新 Image 尾部补 0 到原 kernel_size。刷机时 AK3 脚本内置 sha256 回读校验，失败自动回滚备份。
5. **`do.modules=0`**：vendor 模块由 ROM 提供，自己塞 .ko 会因 vermagic / CONFIG_MODVERSIONS CRC 不匹配报 invalid module format。
6. **先剥离 Flicker 树自带旧 hook**：`drivers/tty/pty.c` 等处的 `ksu_handle_*` 是原版 KernelSU 遗留，任何变体集成后都会链接失败，必须先剥（3 变体共用该步骤）。
7. **每次运行从 `input/device.config` 重新生成配置**并断言最终 `.config`（olddefconfig 可能把不满足依赖的符号悄悄改回 n）。

## 验收标准（CI 绿 ≠ 成功，每个变体单独过五关）

1. 能开机（不 bootloop）
2. 对应管理器识别并授权 su（`adb shell su -c id` 返回 uid=0）
3. 模块能用（装一个模块 → 重启 → 生效）
4. SUSFS 生效（仅 sukisu-susfs / bakasu-if-present）
5. 不软重启、不掉基带

回退永远保留：`fastboot flash boot_b <原版 boot.img>`。
