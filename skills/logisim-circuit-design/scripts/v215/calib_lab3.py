# -*- coding: utf-8 -*-
"""实验3 用到的 2.15 元件端口标定。

用实验2 的工程头生成临时 .circ，再用 ita_probe.ends 读真实端口坐标。
覆盖：MUX 2:1/4:1/8:1、Comparator、Bit Extender、Constant、
Shifter(ll/lr/ar)、Splitter(8/3/2 位，南/北)。
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

LAB2 = "实验2 构建加法器.circ"
OUT = os.path.join(os.environ.get("TEMP", "."), "lab3calib.circ")


def split_xml(loc, bits, facing):
    attrs = "".join(f'<a name="bit{i}" val="{i}"/>' for i in range(bits))
    return (f'    <comp lib="0" loc="{loc}" name="Splitter">'
            f'<a name="facing" val="{facing}"/>'
            f'<a name="fanout" val="{bits}"/><a name="incoming" val="{bits}"/>'
            f'<a name="appear" val="center"/>{attrs}</comp>')


PARTS = [
    ('    <comp lib="2" loc="(400,400)" name="Multiplexer">'
     '<a name="select" val="2"/><a name="width" val="8"/>'
     '<a name="enable" val="false"/></comp>'),
    ('    <comp lib="2" loc="(400,800)" name="Multiplexer">'
     '<a name="select" val="1"/><a name="width" val="8"/>'
     '<a name="enable" val="false"/></comp>'),
    ('    <comp lib="2" loc="(400,1800)" name="Multiplexer">'
     '<a name="select" val="3"/><a name="width" val="1"/>'
     '<a name="enable" val="false"/></comp>'),
    ('    <comp lib="3" loc="(800,400)" name="Comparator">'
     '<a name="width" val="8"/><a name="mode" val="unsigned"/></comp>'),
    ('    <comp lib="0" loc="(1000,400)" name="Bit Extender">'
     '<a name="in_width" val="1"/><a name="out_width" val="8"/>'
     '<a name="type" val="zero"/></comp>'),
    ('    <comp lib="0" loc="(200,1000)" name="Constant">'
     '<a name="width" val="8"/><a name="value" val="0x0"/></comp>'),
    ('    <comp lib="1" loc="(700,1200)" name="AND Gate">'
     '<a name="inputs" val="2"/><a name="width" val="8"/></comp>'),
    ('    <comp lib="3" loc="(400,2200)" name="Shifter">'
     '<a name="width" val="8"/><a name="shift" val="ll"/></comp>'),
    ('    <comp lib="3" loc="(800,2200)" name="Shifter">'
     '<a name="width" val="8"/><a name="shift" val="lr"/></comp>'),
    ('    <comp lib="3" loc="(1200,2200)" name="Shifter">'
     '<a name="width" val="8"/><a name="shift" val="ar"/></comp>'),
    split_xml("(400,1400)", 8, "south"),
    split_xml("(400,1600)", 8, "north"),
    split_xml("(600,1400)", 3, "south"),
    split_xml("(600,1600)", 3, "north"),
    split_xml("(800,1400)", 2, "south"),
    split_xml("(800,1600)", 2, "north"),
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


if __name__ == "__main__":
    main()
