#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2.15 I/O 元件几何探针：编译并运行 GeoProbe.java。

用法：
    python geo_probe.py --file 实验7 IO接口实验.circ                # 常用 I/O 元件全表
    python geo_probe.py --file X.circ --comp "TTY"                  # 单个元件
    python geo_probe.py --file X.circ --comp "7-Segment Display"

输出：元件包围盒、每个端口相对 loc 的偏移/位宽/方向、属性表与默认值。
jar 定位顺序：LOGISIM_ITA_JAR → logisim.local.json 的 ita_jar → 本机常见路径。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find_jar() -> str:
    d = HERE
    for _ in range(6):
        p = os.path.join(d, "logisim.local.json")
        if os.path.isfile(p):
            try:
                jar = json.load(open(p, encoding="utf-8")).get("ita_jar")
                if jar and os.path.isfile(jar):
                    return jar
            except Exception:
                pass
        d = os.path.dirname(d)
    for p in (os.environ.get("LOGISIM_ITA_JAR", ""),):
        if p and os.path.isfile(p):
            return p
    raise SystemExit("找不到 Logisim-ITA jar，请设置 LOGISIM_ITA_JAR")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--comp", default=None)
    args = ap.parse_args()
    jar = find_jar()
    classes = os.path.join(HERE, "classes")
    os.makedirs(classes, exist_ok=True)
    java = os.path.join(HERE, "GeoProbe.java")
    if not os.path.isfile(os.path.join(classes, "GeoProbe.class")):
        subprocess.check_call(["javac", "-encoding", "UTF-8", "-cp", jar,
                               "-d", classes, java])
    cmd = ["java", "-cp", jar + os.pathsep + classes, "GeoProbe", "--file", args.file]
    if args.comp:
        cmd += ["--comp", args.comp]
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()