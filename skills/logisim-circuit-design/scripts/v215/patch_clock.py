# -*- coding: utf-8 -*-
"""把 Clock 组件替换成 CLK 输入引脚，导出临时 .circ 用于探针测试。"""
import sys
import xml.etree.ElementTree as ET

src, dst = sys.argv[1], sys.argv[2]
tree = ET.parse(src)
root = tree.getroot()
n = 0
for c in root.iter("comp"):
    if c.get("name") != "Clock":
        continue
    c.set("name", "Pin")
    for a in list(c):
        c.remove(a)
    for k, v in [("facing", "east"), ("output", "false"), ("width", "1"),
                 ("tristate", "false"), ("pull", "none"), ("label", "CLK"),
                 ("labelloc", "west"), ("labelfont", "Dialog plain 12"),
                 ("labelcolor", "#000000")]:
        e = ET.SubElement(c, "a")
        e.set("name", k)
        e.set("val", v)
    n += 1
tree.write(dst, encoding="unicode", xml_declaration=True)
print("patched", n, "clocks ->", dst)