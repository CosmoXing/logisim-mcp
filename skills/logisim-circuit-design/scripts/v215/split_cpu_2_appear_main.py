# -*- coding: utf-8 -*-
"""实验7 重构第二步：给 CPU 加外观，用实验5 的程序 ROM 重建「整机测试」主电路。"""
import re
import sys

sys.path.insert(0, r"c:\Users\ASUS\.trae-cn\skills\logisim-circuit-design\scripts\v215")
from board215 import Board, Appearance

LAB5 = r"实验5 指令分析.circ"
LAB7 = r"实验7 IO接口实验.circ"

INS = ["CLK", "RST", "IR_IN", "RAM_Q"]
OUTS = ["PC", "IR", "RA", "RAM_D", "RAM_A", "RAM_WE", "RAM_RD",
        "R0", "R1", "R2", "R3", "FLAGS", "T0", "T1", "T2", "T3", "BOP", "ALUY"]


def attr(body, key):
    m = re.search(r'<a name="%s" val="([^"]*)"/>' % key, body)
    return m.group(1) if m else None


# ---------- 1. 取实验5 四片 ROM 的内容
x5 = open(LAB5, encoding="utf-8").read()
blk5 = re.search(r'  <circuit name="系统连接">.*?\n  </circuit>\n', x5, re.S).group(0)
roms = []
for m in re.finditer(r'<comp lib="4" loc="\(\d+,\d+\)" name="ROM">(.*?)</comp>', blk5, re.S):
    body = m.group(1)
    c = re.search(r'<a name="contents">(.*?)</a>', body, re.S)
    if not c:
        continue
    lines = [ln for ln in c.group(1).split("\n") if ln.strip()]
    if lines and lines[0].startswith("addr/data"):
        lines = lines[1:]
    roms.append("\n".join(lines))
print("rom contents lines:", [r.split("\n")[0] for r in roms], [len(r) for r in roms])
assert len(roms) == 4 and all(roms)
# 按 Prog 约定重排：P0=例1(2008) P1=例2(200c) P2=例3(2001) P3=例4(2002)
order = {"2008": 0, "200c": 1, "2001": 2, "2002": 3}
roms.sort(key=lambda r: order.get(r.split()[0].lower(), 9))
print("rom order:", [r.split()[0] for r in roms])
assert [r.split()[0].lower() for r in roms] == ["2008", "200c", "2001", "2002"]

# ---------- 2. CPU 外观
xml = open(LAB7, encoding="utf-8").read()
m = re.search(r'  <circuit name="CPU">.*?\n  </circuit>\n', xml, re.S)
cpu = m.group(0)
ports = []
y = 60
for n in INS:
    ports.append((n, "0,0", 80, y, 8)); y += 60
y = 60
for n in OUTS:
    ports.append((n, "%d,%d" % (0, 0), 540, y, 8)); y += 20
app = Appearance(rect=(60, 20, 520, 460), anchor=(80, 60),
                 label="CPU", label_pos=(300, 42), ports=ports)

# 按 label 找到真实 pin 坐标填入 circ-port
pinloc = {}
for pm in re.finditer(r'<comp lib="0" loc="\((\d+),(\d+)\)" name="Pin">(.*?)</comp>', cpu, re.S):
    lab = attr(pm.group(3), "label")
    if lab:
        pinloc[lab] = "%s,%s" % (pm.group(1), pm.group(2))
ports = []
y = 60
for n in INS:
    ports.append((n, pinloc[n], 80, y, 8)); y += 60
y = 60
for n in OUTS:
    ports.append((n, pinloc[n], 540, y, 8)); y += 20
app = Appearance(rect=(60, 20, 520, 460), anchor=(80, 60),
                 label="CPU", label_pos=(300, 42), ports=ports)
cpu2 = re.sub(r'<appear>.*?</appear>\n', '', cpu, flags=re.S)
j = cpu2.find('    <a name="clabelcolor"')
k = cpu2.find("\n", j) + 1
cpu2 = cpu2[:k] + app.to_xml() + "\n" + cpu2[k:]
xml = xml.replace(cpu, cpu2)
offs = app.offsets()
print("CPU offsets sample:", {k2: offs[k2] for k2 in ("CLK", "IR_IN", "RAM_Q", "PC", "RAM_A", "RAM_WE", "T3")})

# ---------- 3. 删除旧整机测试、调整 main 命名
xml = re.sub(r'  <circuit name="整机测试">.*?\n  </circuit>\n', '', xml, flags=re.S)
if "实验7 I/O 演示" not in xml:
    xml = xml.replace('  <circuit name="main">\n    <a name="circuit" val="main"/>',
                      '  <circuit name="实验7 I/O 演示">\n    <a name="circuit" val="实验7 I/O 演示"/>')
if "整机测试：CPU（封装）" in xml:
    xml = re.sub(r'  <circuit name="main">.*?\n  </circuit>\n', '', xml, flags=re.S)
open(LAB7, "w", encoding="utf-8", newline="\n").write(xml)

# ---------- 4. 构建整机测试
b = Board("main")
b.raw = ""


def gnd(loc, label="GND"):
    b.const(loc, 1, 0)
    b.wire(loc, (loc[0] + 40, loc[1]))
    b.tunnel((loc[0] + 40, loc[1]), label, 1, "east")


def one(loc, label="ONE"):
    b.const(loc, 1, 1)
    b.wire(loc, (loc[0] + 40, loc[1]))
    b.tunnel((loc[0] + 40, loc[1]), label, 1, "east")


# 顶层引脚
b.pin((200, 300), "CLK")
b.wire((200, 300), (240, 300)); b.tunnel((240, 300), "CLK", 1, "east")
b.pin((200, 360), "RST")
b.wire((200, 360), (240, 360)); b.tunnel((240, 360), "RST", 1, "east")
b.pin((200, 420), "Prog", width=2)
b.wire((200, 420), (240, 420)); b.tunnel((240, 420), "PROG2", 2, "east")

# CPU 实例
OFF = {n: offs[n] for n in INS + OUTS}
cpu_pts = b.sub("CPU", (1500, 1400), OFF)
for n in INS:
    b.stub(cpu_pts[n], n, 16 if n == "IR_IN" else (8 if n == "RAM_Q" else 1), "w")
for n in OUTS:
    w = 16 if n == "IR" else (8 if n in ("PC", "RA", "RAM_D", "R0", "R1", "R2", "R3", "BOP", "ALUY")
                              else (4 if n in ("RAM_A", "FLAGS") else 1))
    b.stub(cpu_pts[n], n, w, "e")

# PC[3:0] → PA4
b.splitn((2100, 700), 2, 8, [0, 0, 0, 0, 1, 1, 1, 1], "south")
b.stub((2100, 700), "PC", 8, "n")
b.stub((2100, 720), "PA4", 4, "s")

# 四片程序 ROM
for i, content in enumerate(roms):
    pts = b.rom((600, 600 + 200 * i), addr_width=4, data_width=16, contents=content)
    b.stub(pts["A"], "PA4", 4, "w")
    b.stub(pts["D"], "P%dD" % i, 16, "e")
    gnd((400, 660 + 200 * i))
    b.stub(pts["cs"], "GND", 1, "w")

# 4:1 程序选择器
data, sel, out = b.mux((1300, 900), 2, 16)
for i in range(4):
    b.stub(data[i], "P%dD" % i, 16, "w")
b.stub(sel, "PROG2", 2, "s")
b.stub(out, "IR_IN", 16, "e")

# RAM
ram = b.ram((1100, 1500), addr_width=4, data_width=8)
b.stub(ram["A"], "RAM_A", 4, "w")
b.stub(ram["D"], "RAM_D", 8, "w")
b.stub(ram["Q"], "RAM_Q", 8, "e")
b.stub(ram["str"], "RAM_WE", 1, "w")
b.stub(ram["clk"], "T3", 1, "s")
gnd((950, 1620))
b.stub(ram["cs"], "GND", 1, "s")
one((1350, 1620))
b.stub(ram["oe"], "ONE", 1, "s")
gnd((1250, 1680))
b.stub(ram["clr"], "GND", 1, "s")

# RAM_D → 个位数字 ROM → TTY
vals = " ".join("%02x" % (0x30 + (v % 10)) for v in range(256))
drom = b.rom((1500, 1950), addr_width=8, data_width=7, contents=vals)
b.stub(drom["A"], "RAM_D", 8, "w")
b.stub(drom["D"], "DIGIT", 7, "e")
gnd((1300, 2010))
b.stub(drom["cs"], "GND", 1, "w")

# WE = T3 ? RAM_WE : 0
md, ms, mo = b.mux((2200, 1750), 1, 1)
b.const((2050, md[0][1]), 1, 0)
b.wire((2050, md[0][1]), md[0])
b.stub(md[1], "RAM_WE", 1, "w")
b.stub(ms, "T3", 1, "s")
b.stub(mo, "WE", 1, "e")

b.raw += ('    <comp lib="5" loc="(2400,1800)" name="TTY">\n'
          '      <a name="Char bit width" val="7"/>\n'
          '      <a name="rows" val="8"/>\n'
          '      <a name="cols" val="32"/>\n'
          '      <a name="trigger" val="rising"/>\n'
          '    </comp>')
b.wire((2400, 1790), (2360, 1790)); b.tunnel((2360, 1790), "DIGIT", 7, "west")
b.wire((2400, 1800), (2360, 1800)); b.tunnel((2360, 1800), "CLK", 1, "west")
b.wire((2410, 1810), (2410, 1840)); b.wire((2410, 1840), (2360, 1840))
b.tunnel((2360, 1840), "WE", 1, "west")
b.wire((2420, 1810), (2420, 1870)); b.wire((2420, 1870), (2360, 1870))
b.tunnel((2360, 1870), "RST", 1, "west")

b.text((1200, 200), "整机测试：CPU（封装）+ 程序 ROM（Prog 选择 4 段程序）+ RAM + 哑终端；"
                    "CLK/RST 由顶层控制", bold=True)
b.text((1200, 260), "写入使能 WE = T3 ? RAM_WE : 0，RAM 写数据经 256×7 ROM 映射成个位数字符送 TTY", bold=True)

errs = b.check()
print("check:", len(errs))
for e in errs[:8]:
    print("  ", e)
if errs:
    raise SystemExit("布线自检失败")

body = b.to_body() + "\n" + b.raw
circ = ("  <circuit name=\"main\">\n"
        "    <a name=\"circuit\" val=\"main\"/>\n"
        "    <a name=\"clabel\" val=\"\"/>\n"
        "    <a name=\"clabelup\" val=\"east\"/>\n"
        "    <a name=\"clabelfont\" val=\"SansSerif plain 12\"/>\n"
        "    <a name=\"clabelcolor\" val=\"#000000\"/>\n"
        + body + "\n  </circuit>\n")
xml = open(LAB7, encoding="utf-8").read()
xml = xml.replace("</project>", circ + "</project>")
open(LAB7, "w", encoding="utf-8", newline="\n").write(xml)
print("main written")