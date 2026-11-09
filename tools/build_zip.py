#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把插件目录打成可分发 zip。

用法：
    python tools/build_zip.py                 # 输出到 dist/logisim-mcp-<version>.zip
    python tools/build_zip.py --out X.zip

zip 内是插件根目录的内容（根上有 .codebuddy-plugin/ 与 .mcp.json），
解压到任意目录即可作为 CODEBUDDY_PLUGIN_ROOT 使用。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile

def _utf8_console():
    """Windows 控制台默认不是 UTF-8，直接 print 中文会抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


_utf8_console()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_DIRS = {"__pycache__", "dist", ".git", ".in_use", ".idea", ".vscode"}
# 本机私有配置、备份、编辑器文件都不进分发包
EXCLUDE_FILES = {".DS_Store", "Thumbs.db", "logisim.local.json"}
EXCLUDE_EXT = {".pyc", ".pyo", ".zip"}


def manifest():
    with open(os.path.join(ROOT, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)


def iter_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if name in EXCLUDE_FILES or os.path.splitext(name)[1] in EXCLUDE_EXT:
                continue
            if name.endswith(".bak") or ".bak-" in name:
                continue
            full = os.path.join(base, name)
            yield full, os.path.relpath(full, root).replace(os.sep, "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    info = manifest()
    version = info.get("version", "0.0.0")
    name = info.get("name", "plugin")
    out = args.out or os.path.join(ROOT, "dist", f"{name}-{version}.zip")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    files = list(iter_files(ROOT))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for full, rel in files:
            zf.write(full, rel)

    data = open(out, "rb").read()
    size = len(data)
    sha = hashlib.sha256(data).hexdigest()
    print(f"已打包 {name} {version}")
    print(f"  文件数: {len(files)}")
    print(f"  体积  : {size / 1024:.1f} KiB")
    print(f"  输出  : {out}")
    print(f"  sha256: {sha}")
    print("\n校验：")
    print("  python tools/selftest.py --quick   # 打包前自检")
    return 0


if __name__ == "__main__":
    sys.exit(main())
