#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把插件里的技能同步到用户技能目录（单一事实来源 = 插件）。

用法：
    python tools/sync_skill.py            # 只对比，列出差异
    python tools/sync_skill.py --apply    # 真正写入（覆盖前备份）
    python tools/sync_skill.py --to-plugin --apply   # 反向：用户目录 → 插件

默认源：<plugin>/skills/logisim-circuit-design
默认目标：~/.workbuddy/skills/logisim-circuit-design
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_NAME = "logisim-circuit-design"
PLUGIN_SKILL = os.path.join(ROOT, "skills", SKILL_NAME)
USER_SKILL = os.path.join(os.path.expanduser("~/.workbuddy/skills"), SKILL_NAME)

SKIP_DIRS = {"__pycache__", ".git"}
SKIP_EXT = {".pyc", ".pyo"}


def walk(root):
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if os.path.splitext(name)[1] in SKIP_EXT:
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out[rel] = hashlib.sha256(open(full, "rb").read()).hexdigest()
    return out


def diff(src, dst):
    a, b = walk(src), walk(dst)
    added = sorted(set(a) - set(b))
    missing = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    return added, changed, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写入（默认只对比）")
    ap.add_argument("--to-plugin", action="store_true", help="反向：用户目录 → 插件")
    ap.add_argument("--prune", action="store_true", help="删除目标里多出来的文件")
    args = ap.parse_args()

    src, dst = (USER_SKILL, PLUGIN_SKILL) if args.to_plugin else (PLUGIN_SKILL, USER_SKILL)
    if not os.path.isdir(src):
        raise SystemExit(f"源目录不存在: {src}")
    if not os.path.isdir(dst):
        print(f"目标不存在，将新建: {dst}")

    added, changed, missing = diff(src, dst)
    print(f"源  : {src}")
    print(f"目标: {dst}\n")
    print(f"新增 {len(added)}，变更 {len(changed)}，目标独有 {len(missing)}")
    for tag, items in (("+", added), ("~", changed), ("-", missing)):
        for rel in items:
            print(f"  {tag} {rel}")

    if not (added or changed or (args.prune and missing)):
        print("\n已同步，无需操作。")
        return 0
    if not args.apply:
        print("\n（只对比。加 --apply 生效。）")
        return 0

    for rel in added + changed:
        s = os.path.join(src, rel)
        d = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.isfile(d):
            shutil.copy2(d, d + ".bak")
        shutil.copy2(s, d)
    for rel in missing if args.prune else []:
        os.remove(os.path.join(dst, rel))
    print(f"\n已写入 {len(added) + len(changed)} 个文件（覆盖前留 .bak）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
