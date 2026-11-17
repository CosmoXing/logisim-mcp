# -*- coding: utf-8 -*-
"""实验4 用到的 2.15 元件端口标定。

覆盖：Register、Counter、D Flip-Flop、RAM、ROM、Decoder、Clock。
用实验2 的工程头生成临时 .circ，再用 ita_probe.ends 读真实端口坐标。
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

LAB2 = os.environ.get("LAB2_CIRC", "实验2 构建加法器.circ")
OUT = os.path.join(os.environ.get("TEMP", "."), "lab4calib.circ")

ROM_BODY = """addr/data: 3 16
4001
8030
15f0
4042
8034
15f0
1084
8038"""

def split_xml(loc, fanout, incoming, facing, groups=None):
    groups = groups or list(range(incoming))
    attrs = "".join(f'<a name="bit{i}" val="{groups[i]}"/>'
                    for i in range(incoming))
    return (f'    <comp lib="0" loc="{loc}" name="Splitter">'
            f'<a name="facing" val="{facing}"/>'
            f'<a name="fanout" val="{fanout}"/><a name="incoming" val="{incoming}"/>'
            f'<a name="appear" val="center"/>{attrs}</comp>')


PARTS = [
    ('    <comp lib="4" loc="(400,300)" name="Register">'
     '<a name="width" val="8"/><a name="trigger" val="rising"/>'
     '<a name="label" val="REG8"/></comp>'),
    ('    <comp lib="4" loc="(800,300)" name="Counter">'
     '<a name="width" val="2"/><a name="trigger" val="rising"/>'
     '<a name="max" val="3"/><a name="goal" val="wrap"/></comp>'),
    ('    <comp lib="4" loc="(400,700)" name="D Flip-Flop">'
     '<a name="trigger" val="rising"/></comp>'),
    ('    <comp lib="4" loc="(800,700)" name="D Flip-Flop">'
     '<a name="trigger" val="rising"/><a name="appear" val="classic"/></comp>'),
    ('    <comp lib="4" loc="(400,1100)" name="RAM">'
     '<a name="addrWidth" val="4"/><a name="dataWidth" val="8"/>'
     '<a name="bus" val="separate"/><a name="trigger" val="rising"/></comp>'),
    ('    <comp lib="4" loc="(900,1100)" name="ROM">'
     '<a name="addrWidth" val="3"/><a name="dataWidth" val="16"/>'
     f'<a name="contents" val="{ROM_BODY}"/></comp>'),
    ('    <comp lib="2" loc="(400,1500)" name="Decoder">'
     '<a name="select" val="2"/><a name="enable" val="true"/>'
     '<a name="disabled" val="0"/></comp>'),
    ('    <comp lib="0" loc="(400,1800)" name="Clock">'
     '<a name="facing" val="east"/></comp>'),
    split_xml("(1200,1400)", 2, 16, "south",
              [0] * 8 + [1] * 8),
    split_xml("(1400,1400)", 2, 8, "south",
              [0] * 5 + [1] * 3),
    split_xml("(1600,1400)", 4, 8, "south",
              [0, 0, 1, 1, 2, 2, 3, 3]),
    split_xml("(1800,1400)", 4, 4, "south"),
    split_xml("(2000,1400)", 5, 5, "south"),
    split_xml("(2200,1400)", 3, 3, "south"),
    ('    <comp lib="3" loc="(400,2300)" name="Adder">'
     '<a name="width" val="8"/></comp>'),
]


def main():
    src = open(LAB2, encoding="utf-8").read()
    head = src.split("<circuit name=")[0]
    head = re.sub(r'<main name="[^"]*"/>', '<main name="calib"/>', head)
    body = '<circuit name="calib">\n' + "\n".join(PARTS) + "\n  </circuit>\n</project>\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + body)
    for c in ita_probe.ends(OUT, "calib"):
        print(c["comp"], c["loc"],
              sorted(c["ports"], key=lambda p: (p["loc"][1], p["loc"][0])))
    for e in ita_probe.errors(OUT, "calib"):
        print("ERR", e)


if __name__ == "__main__":
    main()
