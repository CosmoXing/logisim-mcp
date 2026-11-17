# -*- coding: utf-8 -*-
"""按坐标读运行值，排查 2.15 电路的悬空/错误网络。

用法：python probe_points.py <circ> <circuit> <x,y,w>[,<x,y,w>...] [--set A=0x12,...]
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402


def main():
    circ, circuit, pts = sys.argv[1], sys.argv[2], sys.argv[3]
    args = []
    if "--set" in sys.argv:
        args += ["--set", sys.argv[sys.argv.index("--set") + 1]]
    if pts == "dump":
        args += ["--dump"]
    else:
        args += ["--probe", pts]
    print(ita_probe.run(args, circ, circuit))


if __name__ == "__main__":
    main()
