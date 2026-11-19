# -*- coding: utf-8 -*-
"""实验7 重构第一步：把「系统连接」拆成纯 CPU（去掉程序 ROM、RAM、Prog），
并把这四片 ROM / 4:1 选择器 / RAM 的接线信息导出给整机测试使用。"""
import json
import re
import sys

LAB7 = r"实验7 IO接口实验.circ"

xml = open(LAB7, encoding="utf-8").read()
m = re.search(r'  <circuit name="系统连接">.*?\n  </circuit>\n', xml, re.S)
blk = m.group(0)


def attr(body, key):
    mm = re.search(r'<a name="%s" val="([^"]*)"/>' % key, body)
    return mm.group(1) if mm else None


# 1) 导出 4 片 ROM 的内容
roms = []
for mm in re.finditer(r'<comp lib="4" loc="\((\d+),(\d+)\)" name="ROM">(.*?)</comp>', blk, re.S):
    roms.append({
        "loc": (int(mm.group(1)), int(mm.group(2))),
        "addrWidth": attr(mm.group(3), "addrWidth"),
        "dataWidth": attr(mm.group(3), "dataWidth"),
        "contents": attr(mm.group(3), "contents"),
    })
print("roms:", [(r["loc"], r["addrWidth"], r["dataWidth"], (r["contents"] or "").split("\n")[0]) for r in roms])
assert len(roms) == 4
json.dump(roms, open(r"C:\Users\ASUS\AppData\Local\Temp\lab7_roms.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 2) 删掉 4 片 ROM
blk2 = re.sub(r'    <comp lib="4" loc="\(\d+,\d+\)" name="ROM">.*?</comp>\n', "", blk, flags=re.S)
print("rom left:", len(re.findall(r'name="ROM"', blk2)))

# 3) 删掉 4:1 指令选择器（Multiplexer select=2 width=16）
blk2 = re.sub(r'    <comp lib="2" loc="\(\d+,\d+\)" name="Multiplexer">\n'
              r'(?:(?!</comp>).)*?<a name="select" val="2"/>(?:(?!</comp>).)*?</comp>\n',
              "", blk2, flags=re.S)
print("mux select2 left:", len(re.findall(r'<a name="select" val="2"/>', blk2)))

# 4) 删掉 RAM
blk2 = re.sub(r'    <comp lib="4" loc="\(\d+,\d+\)" name="RAM">.*?</comp>\n', "", blk2, flags=re.S)
print("ram left:", len(re.findall(r'name="RAM"', blk2)))

# 5) 删掉 Prog 输入引脚
blk2 = re.sub(r'    <comp lib="0" loc="\(120,180\)" name="Pin">\n'
              r'(?:(?!</comp>).)*?<a name="label" val="Prog"/>(?:(?!</comp>).)*?</comp>\n',
              "", blk2, flags=re.S)
print("prog pin left:", blk2.count('val="Prog"'))

# 6) 网络改名（只改 tunnel 的 label 值）
renames = {"IRIN": "IR_IN", "RA4": "RAM_A", "RB": "RAM_D",
           "WM": "RAM_WE", "RM": "RAM_RD", "RAMQ": "RAM_Q"}


def rename_label(mm):
    key = 'name="label" val="'
    v = mm.group(1)
    return '%s%s"/>' % (key, renames.get(v, v))


blk2 = re.sub(r'name="label" val="([^"]+)"/>', rename_label, blk2)

# 7) 改引脚方向/名字
def set_pin(block, loc, label=None, output=None):
    pat = r'(    <comp lib="0" loc="\(%s\)" name="Pin">\n)(?:(?!</comp>).)*?</comp>\n' % loc
    mm = re.search(pat, block, re.S)
    if not mm:
        raise SystemExit("找不到引脚 " + loc)
    body = mm.group(0)
    if label:
        body = re.sub(r'<a name="label" val="[^"]*"/>', '<a name="label" val="%s"/>' % label, body)
    if output is not None:
        body = re.sub(r'<a name="output" val="(true|false)"/>',
                      '<a name="output" val="%s"/>' % ("true" if output else "false"), body)
    return block.replace(mm.group(0), body)


# RAMQ 输出 → RAM_Q 输入（按 label 精确定位）
def retarget(block, old_label, new_label, output):
    pat = r'(    <comp lib="0" loc="\((\d+),(\d+)\)" name="Pin">\n)(?:(?!</comp>).)*?</comp>\n'
    for mm in re.finditer(pat, block, re.S):
        if '<a name="label" val="%s"/>' % old_label in mm.group(0):
            body = mm.group(0)
            body = re.sub(r'<a name="label" val="[^"]*"/>', '<a name="label" val="%s"/>' % new_label, body)
            body = re.sub(r'<a name="output" val="(true|false)"/>',
                          '<a name="output" val="%s"/>' % ("true" if output else "false"), body)
            return block.replace(mm.group(0), body)
    raise SystemExit("找不到引脚 " + old_label)


blk2 = retarget(blk2, "RAM_Q", "RAM_Q", False)
blk2 = retarget(blk2, "RAM_D", "RAM_D", True)
blk2 = retarget(blk2, "RAM_WE", "RAM_WE", True)


def has_pin(block, label):
    for mm in re.finditer(r'    <comp lib="0" loc="\(\d+,\d+\)" name="Pin">\n(?:(?!</comp>).)*?</comp>\n',
                          block, re.S):
        if '<a name="label" val="%s"/>' % label in mm.group(0):
            return True
    return False


print("pins now:", [l for l in ["CLK", "RST", "IR_IN", "RAM_Q", "RAM_A", "RAM_D", "RAM_WE", "RAM_RD"]
                    if has_pin(blk2, l)])


def new_pin(loc, label, width, output):
    return ('    <comp lib="0" loc="(%d,%d)" name="Pin">\n'
            '      <a name="facing" val="%s"/>\n'
            '      <a name="output" val="%s"/>\n'
            '      <a name="width" val="%d"/>\n'
            '      <a name="tristate" val="false"/>\n'
            '      <a name="pull" val="none"/>\n'
            '      <a name="label" val="%s"/>\n'
            '      <a name="labelloc" val="north"/>\n'
            '      <a name="labelfont" val="Times New Roman bolditalic 18"/>\n'
            '      <a name="labelcolor" val="#000000"/>\n'
            '    </comp>\n') % (loc[0], loc[1], "west" if output else "east",
                               "true" if output else "false", width, label)


extra = ""
if not has_pin(blk2, "IR_IN"):
    extra += new_pin((120, 220), "IR_IN", 16, False)
if not has_pin(blk2, "RAM_RD"):
    extra += new_pin((1850, 1120), "RAM_RD", 1, True)
if not has_pin(blk2, "RAM_A"):
    extra += new_pin((1850, 1180), "RAM_A", 4, True)
i = blk2.rfind("  </circuit>")
blk2 = blk2[:i] + extra + blk2[i:]

# 8) 电路改名 CPU
blk2 = blk2.replace('  <circuit name="系统连接">', '  <circuit name="CPU">')
blk2 = blk2.replace('<a name="circuit" val="系统连接"/>', '<a name="circuit" val="CPU"/>')
blk2 = re.sub(r'<appear>.*?</appear>\n', '', blk2, flags=re.S)

xml = xml.replace(blk, blk2)
open(LAB7, "w", encoding="utf-8", newline="\n").write(xml)
print("CPU block written")