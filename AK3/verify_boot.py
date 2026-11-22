#!/usr/bin/env python3
"""AK3 刷机包 boot 镜像自检脚本（离线版）。

用法（在电脑上，刷机前/后都可以跑）:
    python verify_boot.py --original <原版boot.img> --image <新Image> --boot <待校验boot.img>

校验规则（全部满足才算 PASS，任何一条失败即 FAIL）:
  1. 总大小 == 201,326,592 B（0xC000000，thyme boot 分区大小），不变
  2. header 前 4096 B 与原 boot 逐字节一致（kernel_size 等字段不许被改写）
  3. kernel_size 之后（ramdisk + AVB footer）逐字节一致
  4. kernel 区（offset 4096，长度 kernel_size）== 新 Image + 尾部补 0
  5. 新 Image 长度 <= kernel_size（否则刷入必然越界破坏 ramdisk）

说明:
  - kernel_size 从【待校验镜像】自己的 header offset 8 读取（uint32 LE），
    但规则 2 已保证 header 与原版一致，所以两者必然相同。
  - header v3/v4 的 kernel 固定从 offset 4096 开始，与 page_size 无关。
  - 本脚本不依赖任何外部工具，只用 Python 标准库。
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys

PART_SIZE = 201_326_592  # 0xC000000, thyme boot partition
KOFF = 4096              # header v3/v4: kernel always starts at one 4096 page


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True, help="原版 boot.img（刷机前的基准）")
    ap.add_argument("--image", required=True, help="新编译的 Image")
    ap.add_argument("--boot", required=True, help="待校验的 boot.img（AK3 刷出的或 repack 的）")
    args = ap.parse_args()

    orig = open(args.original, "rb").read()
    image = open(args.image, "rb").read()
    boot = open(args.boot, "rb").read()

    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
        if not cond:
            ok = False

    # --- 0. basic sanity ------------------------------------------------
    check("original magic ANDROID!", orig[:8] == b"ANDROID!")
    hdr_ver = struct.unpack_from("<I", orig, 40)[0]
    check("original header_version == 3", hdr_ver == 3, f"v{hdr_ver}")
    orig_ksize = struct.unpack_from("<I", orig, 8)[0]
    print(f"       original kernel_size = {orig_ksize:,} B, ramdisk_size = "
          f"{struct.unpack_from('<I', orig, 12)[0]:,} B")

    # --- 1. total size ---------------------------------------------------
    check("1. total size == 201,326,592 B", len(boot) == PART_SIZE,
          f"got {len(boot):,} B")

    # --- 2. header (first 4096 B) byte-identical --------------------------
    check("2. header first 4096 B identical to original",
          boot[:KOFF] == orig[:KOFF])

    # --- 3. everything after kernel_size byte-identical -------------------
    tail_off = KOFF + orig_ksize
    check("3. ramdisk + AVB footer (after kernel region) identical",
          boot[tail_off:] == orig[tail_off:],
          f"region [{tail_off:,}:]")

    # --- 4. kernel region == new Image + zero padding ---------------------
    ksize = struct.unpack_from("<I", boot, 8)[0]
    region = boot[KOFF:KOFF + ksize]
    expected = image + b"\x00" * (ksize - len(image))
    check("4. kernel region == Image + zero padding",
          region == expected,
          f"kernel region sha256 {sha(region)[:16]}…, "
          f"expected {sha(expected)[:16]}…")

    # --- 5. Image fits ----------------------------------------------------
    check("5. len(Image) <= kernel_size", len(image) <= ksize,
          f"Image {len(image):,} B vs slot {ksize:,} B")

    print()
    print(f"Image sha256 : {sha(image)}")
    print(f"boot  sha256 : {sha(boot)}")
    print("RESULT: " + ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
