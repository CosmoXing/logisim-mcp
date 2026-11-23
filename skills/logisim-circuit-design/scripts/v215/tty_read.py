#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2.15 哑终端(TTY)无头读写探针：编译并运行 TtyRead.java。

用法：
    python tty_read.py --file 实验7.circ --circuit main --pin CLK \
        --set "Prog=2" --cycles 300
    python tty_read.py ... --probe "1980,1400,8;1480,1520,16"

能力：
  - 用 Pin 驱动 CLK（可先用 patch_clock.py 把 Clock 换成 CLK 引脚）；
  - 自动先打两拍 RST=1 复位，再跑 cycles 个完整时钟；
  - --set 设定其它输入引脚（Prog 等）；
  - 结束后反射 TtyState.getRowString(i) 打印 8 行文本；
  - --probe 读任意坐标电平，定位中间网络（x = 悬空）。

注意：不要依赖 Simulator.tick()，无头 Project 里它不产生 TtyState（K65）。
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
    ap.add_argument("--circuit", required=True)
    ap.add_argument("--pin", default="CLK")
    ap.add_argument("--set", default=None)
    ap.add_argument("--cycles", type=int, default=32)
    ap.add_argument("--probe", default=None)
    args = ap.parse_args()
    jar = find_jar()
    classes = os.path.join(HERE, "classes")
    os.makedirs(classes, exist_ok=True)
    if not os.path.isfile(os.path.join(classes, "TtyRead.class")):
        subprocess.check_call(["javac", "-encoding", "UTF-8", "-cp", jar,
                               "-d", classes, os.path.join(HERE, "TtyRead.java")])
    cmd = ["java", "-cp", jar + os.pathsep + classes, "TtyRead",
           "--file", args.file, "--circuit", args.circuit,
           "--pin", args.pin, "--cycles", str(args.cycles)]
    if args.set:
        cmd += ["--set", args.set]
    if args.probe:
        cmd += ["--probe", args.probe]
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()