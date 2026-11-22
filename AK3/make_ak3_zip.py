#!/usr/bin/env python3
"""把编译出来的 Image 打成一个权限正确的 AnyKernel3 zip。

Windows 上用 zipfile 打包会把 tools/magiskboot 之类的可执行文件写成 644，
到了手机上 update-binary 无法执行 -> AK3 直接 abort。这个脚本显式写 755。

用法:
    python make_ak3_zip.py --template <AK3模板目录> --image <Image> --out <输出zip>

模板目录要求（osm0sis/AnyKernel3 解压后的样子）:
    anykernel.sh
    META-INF/com/google/android/update-binary
    tools/ak3-core.sh  tools/magiskboot  tools/busybox  ...
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile

EXEC_DIRS = ("tools/",)
EXEC_FILES = ("META-INF/com/google/android/update-binary",)
# 这些目录留着只会让 AK3 多做事，本设备不需要
DROP_DIRS = ("patch/", "ramdisk/", "modules/")


def is_exec(rel: str) -> bool:
    return rel.startswith(EXEC_DIRS) or rel in EXEC_FILES


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="AnyKernel3 模板目录")
    ap.add_argument("--image", required=True, help="编译出的 Image")
    ap.add_argument("--out", required=True, help="输出 zip 路径")
    ap.add_argument("--name", default=None, help="可选：写入 anykernel.sh 的 kernel.string")
    args = ap.parse_args()

    tpl = os.path.abspath(args.template)
    img = os.path.abspath(args.image)
    out = os.path.abspath(args.out)
    if not os.path.isfile(os.path.join(tpl, "anykernel.sh")):
        sys.exit(f"模板目录里没有 anykernel.sh: {tpl}")
    if not os.path.isfile(img):
        sys.exit(f"Image 不存在: {img}")
    if not os.path.isfile(os.path.join(tpl, "tools", "magiskboot")):
        sys.exit("模板缺少 tools/magiskboot，v3 header 无法处理")

    entries: list[tuple[str, str]] = []  # (绝对路径, zip 内相对路径)
    for dirpath, dirnames, filenames in os.walk(tpl):
        dirnames.sort()
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, tpl).replace("\\", "/")
            if any(rel.startswith(d) for d in DROP_DIRS):
                continue
            if rel == "Image":
                continue
            entries.append((p, rel))
    entries.append((img, "Image"))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p, rel in entries:
            zi = zipfile.ZipInfo.from_file(p, rel)
            zi.external_attr = (0o100755 if is_exec(rel) else 0o100644) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(p, "rb") as fh:
                z.writestr(zi, fh.read())

    size = os.path.getsize(out)
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        names = z.namelist()
        kernel = z.read("Image")

    print(f"zip      : {out}")
    print(f"size     : {size:,} bytes")
    print(f"sha256   : {hashlib.sha256(open(out, 'rb').read()).hexdigest()}")
    print(f"crc      : {'OK' if bad is None else 'BAD ' + str(bad)}")
    print(f"Image    : {len(kernel):,} bytes  sha256 {hashlib.sha256(kernel).hexdigest()[:16]}…")
    for need in ("anykernel.sh", "Image", "tools/magiskboot", "tools/ak3-core.sh",
                 "tools/busybox", "META-INF/com/google/android/update-binary"):
        if need not in names:
            sys.exit(f"缺少必需文件: {need}")
    print("required : all present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
