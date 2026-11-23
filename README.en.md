# thyme-kerlnlsu-susfs-build

[中文](README.md) | English

Cloud builds (GitHub Actions) of kernels for the Xiaomi Mi 10S (`thyme`, SM8250 / Snapdragon 870) running **PixelOS / Android 17**, integrating several root solutions (KernelSU-Next / stock KernelSU + SUSFS / SukiSU + SUSFS) and producing **AnyKernel3 flashable zips**. No local Linux, cross toolchain, or large RAM required.

## What it does

- Fetches the exact kernel source commit matching the device (`e7dc99d5350d...`, kernel `4.19.325-perf`, non-GKI)
- Uses the `config.gz` embedded in the ROM kernel image as the build config (device need not be online)
- Integrates a root driver per variant: strips the Flicker tree's bundled stock KernelSU and its manual hooks, then injects the selected driver plus 4.19 compatibility patches
- Applies the susfs4ksu `kernel-4.19` kernel-side patches for SUSFS variants (pre-adapted for thyme in `patches/`)
- Packs AK3 zips by **dd fixed-offset slicing** (no magiskboot; boot header / ramdisk / AVB footer stay byte-identical)
- Produces kernel images, AK3 zips, build logs and SHA-256 manifests; key variants include a hard System.map symbol check

## Variants

| Variant ID | Root driver | SUSFS | Manager | Status |
|---|---|---|---|---|
| `ksun-legacy` | KernelSU-Next `legacy` (syscall-table hook + manual reboot/stat hooks) | ❌ | KernelSU-Next manager (UAPI 6) | ✅ Builds; mirrors the proven legacy path |
| `ksun-susfs` | Stock KernelSU (`11872`) bundled in the Flicker tree + manual prctl hook + manager-signature allowlist | ✅ v1.5.5 full set | **Stock KernelSU manager** | ✅ Builds (System.map 4-symbol check) |
| `sukisu-ultra` | SukiSU-Nova `builtin` | ⚠️ Pending adaptation | SukiSU manager | 🧪 Experimental: upstream now targets the new SUSFS supercall ABI, incompatible with v1.5.5 on the 4.19 branch |
| `bakasu` | BakaSU | Not adapted | BakaSU manager | ⚠️ Placeholder, not built by default |

Only `ksun-legacy` runs by default; request variants explicitly via the `variants` input (JSON array).

### Relation to the old repo

`niuyezi/thyme-ksun-build` builds only KernelSU-Next without SUSFS and is in daily use — **read-only reference, do not modify**. `ksun-legacy` here replicates its verified logic (including both 4.19 compat patches), and this repo adds SUSFS routes plus AK3 dd packing.

## Usage

1. Open **Actions** → **thyme PixelOS multi-variant KSU kernel (AK3)** → **Run workflow**.
2. Set `variants` to a JSON array, e.g. `["ksun-legacy"]` or `["ksun-susfs"]`.
3. Keep other inputs at their defaults (source commit and config are pinned to this device).
4. Wait ~15–30 minutes and download the artifacts from the run page.

### Artifacts

| Artifact | Contents |
|---|---|
| `thyme-pixelos-<variant>` | `Image`, `*.dtb`, `dtbo.img`, `final-defconfig.config`, `artifacts.sha256`, `thyme-<variant>-anykernel3-<sha8>.zip` |
| `thyme-<variant>-build-logs` | Build logs + diagnostics (uploaded on failure too) |

## Matching managers

- **`ksun-legacy`**: the **dev-branch CI build** of the KernelSU-Next manager (UAPI 6, e.g. `v3.4.2-200-g32e25d58`). Do **not** use release builds `v3.4.0/v3.4.1/v3.4.2` (UAPI 4/5/5 — cannot grant root).
- **`ksun-susfs`**: the **stock KernelSU manager** (`me.weishu.kernelsu`). The kernel only accepts allowlisted signatures (stock `c371061b…` and KernelSU-Next official `79e59011…`). Do **not** drive it with a recent KernelSU-Next manager — its UAPI/version floor exceeds the stock driver, causing Unknown version / "SU compat disabled" symptoms. Configure SUSFS via the `ksu_susfs` CLI tool.
- **`sukisu-ultra`** (once it builds): the SukiSU manager, which includes a SUSFS control UI.

## Referenced files and sources

### In this repo

| File | Role |
|---|---|
| `.github/workflows/build.yml` | Multi-variant build workflow (`workflow_dispatch`) |
| `input/device.config` | Kernel build config (extracted from the device `config.gz`) |
| `patches/susfs-thyme.patch` | SUSFS v1.5.5 kernel-side patch, pre-adapted for thyme (8 hunks fixed) |
| `patches/susfs-ksu-thyme.patch` | SUSFS KSU-side patch for stock KernelSU, pre-adapted |
| `AK3/` | AnyKernel3 config and dd fixed-offset packing scripts |
| `docs/` | Flashing, rollback and handoff docs |
| `LICENSE` / `NOTICE.md` | Repo license; upstream origins, modifications and licensing notes |

### System packages used for development

- **Target ROM**: PixelOS (unofficial) for thyme / Mi 10S, Android 17 (`CP2A.260605.016`)
  - Author on XDA: https://xdaforums.com/m/alcatraz323.10682425/
  - Downloads (SourceForge): https://sourceforge.net/projects/alcatrazdev-aosp/files/Mi%2010S/
- **Base firmware**: Xiaomi HyperOS `1.0.4.0` (thyme)

### Upstream sources and tools

| Project | Role | Link | License |
|---|---|---|---|
| Flicker kernel tree | `seventeen` branch kernel source (bundles stock KernelSU) | https://github.com/Flicker-Android-Devices/kernel_xiaomi_sm8250 | GPL-2.0 |
| KernelSU-Next | `ksun-legacy` driver (`legacy` branch) | https://github.com/KernelSU-Next/KernelSU-Next | kernel/ GPL-2.0-only, rest GPL-3.0-or-later |
| SukiSU-Nova | `sukisu-ultra` driver | https://github.com/SukiSU-Nova/SukiSU-Nova | GPL (per file headers) |
| susfs4ksu | SUSFS kernel-side patches and `ksu_susfs` tool | https://gitlab.com/simonpunk/susfs4ksu | GPL (per file headers) |
| AnyKernel3 | Flashable zip skeleton | https://github.com/osm0sis/AnyKernel3 | See upstream LICENSE |
| PixelOS libufdt | Python3 `mkdtboimg.py` | https://github.com/PixelOS-AOSP/android_system_libufdt | Apache-2.0 |
| AOSP Clang | `clang-r596125` cross toolchain | https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86 | Apache-2.0 / LLVM exception |

## Open source & licensing

This is not an official KernelSU / KernelSU-Next / SukiSU / SUSFS project and is not endorsed by those upstreams.

The workflow, scripts and documentation authored in this repo are under the [MIT](LICENSE) license; that MIT license does **not** cover any upstream code or binaries. Upstream origins, exact commits / branches, licenses, and every instrumentation change this project makes to the kernel are recorded in [NOTICE.md](NOTICE.md) — read it before redistributing artifacts.

When publishing artifacts containing the GPL kernel, you must also provide the rebuildable kernel source repo + exact commit + all patch steps in this repo, and keep the upstream license texts. Publishing only `boot.img` / `Image` / AK3 zips does not satisfy GPL obligations.

If a rights holder believes there is a conflict, please open an issue and the related content will be taken down promptly. This section is an engineering note based on license texts and open-source practice, not legal advice.

## Notes

**A green CI run does not mean usable.** Each variant must pass five checks independently: boots, manager detects and grants root, modules work, SUSFS effective (SUSFS variants), no soft-reboots or baseband loss. Always keep the stock `boot.img` for rollback.

The `Image` in the artifacts is a **bare kernel image**, not a flashable `boot.img`. AK3 zips use dd fixed-offset slicing: the new `Image` goes into the kernel area (starting at pagesize `4096`); if its size differs from the original `kernel_size`, update the `kernel_size` field in boot header v3 (offset 8 within the header, little-endian u32), and never exceed the ramdisk start. The rest of the header, the ramdisk and the AVB footer stay byte-identical. `do.modules=0` (vendor modules come from the ROM; injected .ko files fail vermagic / MODVERSIONS CRC checks).

**SUSFS version constraint**: the susfs4ksu `kernel-4.19` branch stopped at **v1.5.5** (2025-02, legacy ABI); the new SUSFS supercall ABI is only maintained on 5.10+ GKI branches. The realistic SUSFS route on 4.19 is therefore `ksun-susfs` (stock KernelSU + v1.5.5); `sukisu-ultra` needs extra version adaptation.

Root granting, modules, and SUSFS hiding are three independent chains (SUSFS additionally needs kernel-side patches + `ksu_susfs` configuration). Debug each chain on its own evidence instead of inferring one from another.

This workflow only compiles; it never touches your device. Unlocking and flashing require your separate explicit consent.

### After a ROM update

A ROM update changes both the kernel source commit and the defconfig, so rebuild. Recommended: host the new `boot.img` at a direct-download URL and pass it as `boot_image_url` when dispatching — the workflow derives `kernel_ref` and `input/device.config` automatically. Or update both manually.

## Credits

- **Alcatraz323** — PixelOS ROM for this device (thyme maintainer)
- **Flicker372** — `kernel_xiaomi_sm8250` tree maintenance
- **johnmart19** and sm8250 developers, **LineageOS** sm8250 maintainers — kernel baseline
- **PixelOS team** — ROM foundation
- **tiann / KernelSU**, **rifsxd / KernelSU-Next**, **SukiSU-Nova team** — root solutions
- **simonpunk** — SUSFS and susfs4ksu; **backslashxx** — manual-hooks reference
- **osm0sis** — AnyKernel3; **AOSP / Google** — sources, Clang and libufdt
