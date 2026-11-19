# -*- coding: utf-8 -*-
"""给 CPU 里没有导线的引脚补一根短线 + 同名隧道，保证与同名网络连通。"""
import re

p = r'实验7 IO接口实验.circ'
xml = open(p, encoding='utf-8').read()
m = re.search(r'  <circuit name="CPU">.*?\n  </circuit>\n', xml, re.S)
blk = m.group(0)


def attr(body, key):
    mm = re.search(r'<a name="%s" val="([^"]*)"/>' % key, body)
    return mm.group(1) if mm else None


wires = set()
for mm in re.finditer(r'<wire from="\((\d+),(\d+)\)" to="\((\d+),(\d+)\)"/>', blk):
    a = (int(mm.group(1)), int(mm.group(2)))
    b = (int(mm.group(3)), int(mm.group(4)))
    wires.add((a, b)); wires.add((b, a))

targets = [("IR_IN", 16), ("RAM_A", 4), ("RAM_RD", 1), ("RAM_WE", 1)]
add = ""
for mm in re.finditer(r'<comp lib="0" loc="\((\d+),(\d+)\)" name="Pin">(.*?)</comp>', blk, re.S):
    loc = (int(mm.group(1)), int(mm.group(2)))
    body = mm.group(3)
    lab = attr(body, "label")
    if lab not in [t[0] for t in targets]:
        continue
    width = dict(targets)[lab]
    out = attr(body, "output") == "true"
    if out:
        q = (loc[0] - 80, loc[1])
        face = "west"
    else:
        q = (loc[0] + 80, loc[1])
        face = "east"
    if (loc, q) in wires or (q, loc) in wires:
        print(lab, "already wired")
        continue
    add += '    <wire from="(%d,%d)" to="(%d,%d)"/>\n' % (loc[0], loc[1], q[0], q[1])
    add += ('    <comp lib="0" loc="(%d,%d)" name="Tunnel">\n'
            '      <a name="facing" val="%s"/>\n'
            '      <a name="width" val="%d"/>\n'
            '      <a name="label" val="%s"/>\n'
            '      <a name="labelfont" val="Dialog plain 12"/>\n'
            '    </comp>\n') % (q[0], q[1], face, width, lab)
    print(lab, "wired ->", q)

i = blk.rfind("  </circuit>")
blk2 = blk[:i] + add + blk[i:]
xml = xml.replace(blk, blk2)
open(p, "w", encoding="utf-8", newline="\n").write(xml)
print("done")