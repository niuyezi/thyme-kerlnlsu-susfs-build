# thyme-kerlnlsu-susfs-build

中文 | [English](README.en.md)

为小米 Mi 10S（`thyme`，SM8250 / 骁龙 870）的 **PixelOS / Android 17** 系统，通过 GitHub Actions **云端编译**集成多种 Root 方案（KernelSU-Next / 原版 KernelSU + SUSFS / SukiSU + SUSFS）的内核，并产出 **AnyKernel3 刷机包**。无需本地 Linux、交叉工具链或大内存。

## 这是干什么的

- 拉取与设备精确匹配的内核源码提交（`e7dc99d5350d...`，内核 `4.19.325-perf`，非 GKI）
- 使用 ROM 内核镜像内嵌的 `config.gz` 作为编译配置（无需设备在线）
- 按变体集成不同 Root 方案：剥离 Flicker 树自带的原版 KernelSU 及其手工 hook，再注入对应驱动与 4.19 兼容补丁
- 对 SUSFS 变体打入 susfs4ksu `kernel-4.19` 分支的内核侧补丁（本仓库 `patches/` 内为预适配 thyme 的版本）
- 以 **dd 定点切片**方式打包 AK3 刷机包（不用 magiskboot，boot header / ramdisk / AVB footer 逐字节不动）
- 产出内核镜像、AK3 zip、编译日志和 SHA-256 校验清单；关键变体带 System.map 符号硬验证

## 变体

| 变体 ID | Root 方案 | SUSFS | 配套管理器 | 状态 |
|---|---|---|---|---|
| `ksun-legacy` | KernelSU-Next `legacy`（syscall-table hook + reboot/stat 手工 hook） | ❌ | KernelSU-Next 管理器（UAPI 6） | ✅ 构建通过，复刻旧仓库已验证路径 |
| `ksun-susfs` | Flicker 树附带原版 KernelSU（`11872`）+ prctl 手工 hook + 管理器签名白名单 | ✅ v1.5.5 全家桶 | **原版 KernelSU 管理器** | ✅ 构建通过（含 System.map 四符号验证） |
| `sukisu-ultra` | SukiSU-Nova `builtin` | ⚠️ 待适配 | SukiSU 管理器 | 🧪 试验中：上游已迁移至新版 SUSFS 接口，与 4.19 分支的 v1.5.5 不匹配 |
| `bakasu` | BakaSU | 未适配 | BakaSU 管理器 | ⚠️ 实验占位，默认不跑 |

**默认只跑 `ksun-legacy`**；需要哪个变体就在 `variants` 里显式指定（JSON 数组）。

### 与旧仓库的关系

`niuyezi/thyme-ksun-build` 只做 KernelSU-Next 单变体、无 SUSFS，已日常使用，**只读参考，不要改动**。本仓库的 `ksun-legacy` 完整复刻其已验证逻辑（含两个 4.19 兼容补丁），并新增 SUSFS 路线与 AK3 dd 打包。

## 怎么用

1. 打开本仓库 **Actions** → 选择 **thyme PixelOS multi-variant KSU kernel (AK3)** → **Run workflow**。
2. `variants` 填 JSON 数组，例如 `["ksun-legacy"]` 或 `["ksun-susfs"]`。
3. 其余参数保持默认（已锁定该设备的源码提交与配置）。
4. 等待约 15–30 分钟，在 run 页面下载产物。

### 产物

| Artifact | 内容 |
|---|---|
| `thyme-pixelos-<variant>` | `Image`、`*.dtb`、`dtbo.img`、`final-defconfig.config`、`artifacts.sha256`、`thyme-<variant>-anykernel3-<sha8>.zip` |
| `thyme-<variant>-build-logs` | 编译日志 + 诊断摘要（失败时也会上传） |

## 配套管理器

- **`ksun-legacy`**：KernelSU-Next 仓库 **dev 分支 CI 构建**的普通版管理器（UAPI 6，如 `v3.4.2-200-g32e25d58`）。**不要**用 Release 正式版 `v3.4.0/v3.4.1/v3.4.2`（UAPI 4/5/5，无法授权）。
- **`ksun-susfs`**：**原版 KernelSU 管理器**（`me.weishu.kernelsu`）。内核只接受白名单内签名（原版 `c371061b…` 与 KernelSU-Next 官方 `79e59011…`）。**不要**用新版 KernelSU-Next 管理器驱动它——新管理器的 UAPI/版本门槛高于原版内核，会显示 Unknown、SU 兼容层禁用等异常。SUSFS 功能通过 `ksu_susfs` 命令行工具配置。
- **`sukisu-ultra`**（构建通过后）：SukiSU 管理器，内置 SUSFS 控制界面。

## 引用的文件与来源

### 仓库内文件

| 文件 | 作用 |
|---|---|
| `.github/workflows/build.yml` | 多变体构建工作流（`workflow_dispatch` 手动触发） |
| `input/device.config` | 编译用内核配置（从设备内嵌 `config.gz` 提取） |
| `patches/susfs-thyme.patch` | SUSFS v1.5.5 内核侧补丁（预适配 thyme，8 处 hunk 已修正） |
| `patches/susfs-ksu-thyme.patch` | SUSFS 对原版 KernelSU 的 KSU 侧补丁（预适配） |
| `AK3/` | AnyKernel3 配置与 dd 定点切片打包脚本 |
| `docs/` | 刷入、回退与交接文档 |
| `LICENSE` / `NOTICE.md` | 本仓库授权与上游来源、修改点、许可声明 |

### 开发所依据的系统包

- **目标 ROM**：PixelOS（非官方）for thyme / Mi 10S，Android 17（构建号 `CP2A.260605.016`）
  - ROM 作者（XDA）：https://xdaforums.com/m/alcatraz323.10682425/
  - 下载目录（SourceForge）：https://sourceforge.net/projects/alcatrazdev-aosp/files/Mi%2010S/
- **底包固件**：Xiaomi HyperOS `1.0.4.0`（thyme）

### 上游源码与工具

| 项目 | 用途 | 链接 | 许可 |
|---|---|---|---|
| Flicker 内核树 | `seventeen` 分支内核源码（附带原版 KernelSU） | https://github.com/Flicker-Android-Devices/kernel_xiaomi_sm8250 | GPL-2.0 |
| KernelSU-Next | `ksun-legacy` 变体驱动（`legacy` 分支） | https://github.com/KernelSU-Next/KernelSU-Next | kernel/ GPL-2.0-only，其余 GPL-3.0-or-later |
| SukiSU-Nova | `sukisu-ultra` 变体驱动 | https://github.com/SukiSU-Nova/SukiSU-Nova | GPL（以文件头为准） |
| susfs4ksu | SUSFS 内核侧补丁与 `ksu_susfs` 工具 | https://gitlab.com/simonpunk/susfs4ksu | GPL（以文件头为准） |
| AnyKernel3 | 刷机包骨架 | https://github.com/osm0sis/AnyKernel3 | 见上游 LICENSE |
| PixelOS libufdt | Python3 版 `mkdtboimg.py` | https://github.com/PixelOS-AOSP/android_system_libufdt | Apache-2.0 |
| AOSP Clang | `clang-r596125` 交叉工具链 | https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86 | Apache-2.0 / LLVM 例外 |

## 开源与许可

本项目非 KernelSU / KernelSU-Next / SukiSU / SUSFS 官方项目，未获上游授权或背书。

本仓库自身的工作流、脚本与文档以 [MIT](LICENSE) 授权；该 MIT **不覆盖**任何上游代码或二进制。上游来源、准确 commit / 分支、许可证，以及本项目对内核的全部插桩修改，统一记录在 [NOTICE.md](NOTICE.md)，发布产物前请先读该文件。

对外发布含 GPL 内核的产物时，必须同时提供可重建的内核源码仓库 + 准确 commit + 本仓库的全部补丁步骤，并保留上游许可证文本；仅发布 `boot.img` / `Image` / AK3 zip 不满足 GPL 义务。

如权利人认为存在权利冲突，请在本仓库提 issue，我会立即下架相关内容。本说明基于许可证文本与开源惯例，不构成法律意见。

## 注意

**CI 绿 ≠ 可用**。每个变体需单独过五关：能开机、管理器识别并授权 root、模块可用、SUSFS 生效（SUSFS 变体）、不软重启不掉基带。回退永远保留原版 `boot.img`。

产物中的 `Image` 是**裸内核镜像**，不是可直接刷入的 `boot.img`；AK3 zip 采用 dd 定点切片：新 `Image` 写入 kernel 区（pagesize `4096` 起始），若大小与原 `kernel_size` 不同需同步更新 boot header v3 的 `kernel_size` 字段（header 内 offset 8，小端 u32），不得超过 ramdisk 起点；header 其余部分、ramdisk 与 AVB footer 保持逐字节不变。`do.modules=0`（vendor 模块由 ROM 提供，自塞 .ko 会因 vermagic / MODVERSIONS CRC 不匹配而失效）。

**SUSFS 版本约束**：susfs4ksu 的 `kernel-4.19` 分支停在 **v1.5.5**（2025-02，老接口）；新版 SUSFS（supercall 接口）仅维护在 5.10+ GKI 分支。因此 4.19 上现实的 SUSFS 路线是 `ksun-susfs`（原版 KernelSU + v1.5.5），`sukisu-ultra` 需要额外版本适配。

root 授权与模块是两条独立链路；SUSFS 隐藏又是第三条链路（依赖内核侧补丁 + `ksu_susfs` 配置）。任何一环异常都应单独定位，不要互相推断。

本 workflow 只负责编译，不会接触你的设备。解锁、刷入都需要你单独明确授权。

### ROM 换版后怎么做

ROM 更新会同时改变内核源码提交与 defconfig，必须重编。推荐：把新系统 `boot.img` 放到可直链下载的位置，触发 workflow 时填入 `boot_image_url`，工作流会自动推导 `kernel_ref` 与 `input/device.config`；或手动更新这两项。

## 致谢

- **Alcatraz323** —— 本设备 PixelOS ROM（thyme 维护者）
- **Flicker372** —— 内核树 `kernel_xiaomi_sm8250` 维护
- **johnmart19** 及 sm8250 平台开发者、**LineageOS** sm8250 维护者 —— 内核基线
- **PixelOS 团队** —— ROM 基础
- **tiann / KernelSU**、**rifsxd / KernelSU-Next**、**SukiSU-Nova 团队** —— Root 方案
- **simonpunk** —— SUSFS 与 susfs4ksu；**backslashxx** —— manual hooks 方案参考
- **osm0sis** —— AnyKernel3；**AOSP / Google** —— 源码、Clang 与 libufdt
