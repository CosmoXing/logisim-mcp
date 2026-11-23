# -*- coding: utf-8 -*-
"""Logisim 3.9 单周期 MIPS CPU 生成器（9 条指令，复用 3.3 ALU / 3.4 控制器）。

生成的电路：
  main    数据通路 + 控制 + 停机 + 周期计数
  IM      16K x 32 ROM（14 位字地址，取 A[15:2]）
  DM      16K x 32 RAM（异步读、上升沿写）
  Bank8   8 x 32 寄存器 + 双读口 8:1
  RegFile 4 x Bank8 + 2->4/3->8 译码 + 双 4:1

为什么不用 3.1 的 FourEights：它在 wen=1 且读写地址相同时把 wdata 直接送到 rdata
（写穿透），单周期 R 型指令会形成 ALU->wdata->rdata->ALU 组合环。这里的 RegFile
是同接口重建版（上升沿写、组合读、$0 只读）。详见 references/logisim39-cpu-casebook.md。

用法：
  python gen_cpu39.py --src33 3.3.circ --src34 3.4.circ --out ./out
  python gen_cpu39.py --src33 3.3.circ --src34 3.4.circ \
      --hexdir "../单周期测试程序-RAM和ROM初始化数据" --out ./out
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v50"))
import lib8

SRC = {"3.3": "", "3.4": ""}

HEAD = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="3.9.0" version="1.0">
  This file is intended to be loaded by Logisim-evolution v3.9.0(https://github.com/logisim-evolution/).

  <lib desc="#Wiring" name="0">
    <tool name="Pin">
      <a name="appearance" val="classic"/>
    </tool>
  </lib>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Memory" name="2"/>
  <lib desc="#I/O" name="3"/>
  <lib desc="#Base" name="4"/>
  <lib desc="#Plexers" name="5"/>
  <lib desc="#Arithmetic" name="6"/>
  <main name="main"/>
  <options>
    <a name="gateUndefined" val="ignore"/>
    <a name="simlimit" val="1000"/>
    <a name="simrand" val="0"/>
  </options>
  <mappings>
    <tool lib="4" map="Button2" name="Poke Tool"/>
    <tool lib="4" map="Button3" name="Menu Tool"/>
  </mappings>
  <toolbar>
    <tool lib="4" name="Poke Tool"/>
    <tool lib="4" name="Edit Tool"/>
    <tool lib="4" name="Wiring Tool"/>
    <tool lib="4" name="Text Tool"/>
    <sep/>
  </toolbar>
'''


def get_circuit(tag, name):
    s = open(SRC[tag], encoding="utf-8").read()
    m = re.search(r'  <circuit name="%s">.*?\n  </circuit>' % re.escape(name), s, re.S)
    if not m:
        raise RuntimeError("circuit not found: %s / %s" % (tag, name))
    return m.group(0) + "\n"


# ------------------------------------------------------------------ 元件
def add_comp(b, loc, xml, body, ports):
    x, y = loc
    b.comps.append(xml)
    b.bodies.append((x + body[0], y + body[1], x + body[2], y + body[3]))
    pts = {k: (x + dx, y + dy) for k, (dx, dy) in ports.items()}
    for p in pts.values():
        b.all_ports.add((p[0] // 10, p[1] // 10))
    b._blocked_cache = None
    return pts


def pin(b, loc, label, kind="input", width=1):
    x, y = loc
    face = "east" if kind == "input" else "west"
    out = '<a name="output" val="true"/>' if kind == "output" else ""
    w = f'<a name="width" val="{width}"/>' if width != 1 else ""
    xml = (f'    <comp lib="0" loc="({x},{y})" name="Pin">'
           f'<a name="appearance" val="classic"/><a name="facing" val="{face}"/>'
           f'{out}{w}<a name="label" val="{label}"/></comp>\n')
    b.comps.append(xml)
    b.all_ports.add((x // 10, y // 10))
    b._blocked_cache = None
    return (x, y)


def sub_custom(b, loc, name, offsets, w, h):
    x, y = loc
    xml = f'    <comp loc="({x},{y})" name="{name}"/>\n'
    return add_comp(b, loc, xml, (0, 0, w, h), offsets)


def reg(b, loc, width, label=""):
    x, y = loc
    lab = f'<a name="label" val="{label}"/>' if label else ""
    xml = (f'    <comp lib="2" loc="({x},{y})" name="Register">'
           f'<a name="width" val="{width}"/>{lab}</comp>\n')
    return add_comp(b, loc, xml, (0, 0, 60, 90),
                    {"D": (0, 30), "en": (0, 50), "clk": (0, 70), "clr": (30, 90), "Q": (60, 30)})


def adder(b, loc, width):
    x, y = loc
    xml = f'    <comp lib="6" loc="({x},{y})" name="Adder"><a name="width" val="{width}"/></comp>\n'
    return add_comp(b, loc, xml, (-40, -30, 0, 30),
                    {"A": (-40, -10), "B": (-40, 10), "S": (0, 0),
                     "Cin": (-20, -20), "Cout": (-20, 20)})


def mux2(b, loc, width):
    x, y = loc
    xml = (f'    <comp lib="5" loc="({x},{y})" name="Multiplexer">'
           f'<a name="select" val="1"/><a name="width" val="{width}"/>'
           f'<a name="enable" val="false"/></comp>\n')
    return add_comp(b, loc, xml, (-30, -20, 0, 20),
                    {"in0": (-30, -10), "in1": (-30, 10), "sel": (-20, 20), "out": (0, 0)})


def shifter(b, loc, width):
    x, y = loc
    xml = f'    <comp lib="6" loc="({x},{y})" name="Shifter"><a name="width" val="{width}"/></comp>\n'
    return add_comp(b, loc, xml, (-40, -20, 0, 20),
                    {"data": (-40, -10), "distance": (-40, 10), "out": (0, 0)})


def const(b, loc, value, width=1):
    x, y = loc
    w = f'<a name="width" val="{width}"/>' if width != 1 else ""
    xml = f'    <comp lib="0" loc="({x},{y})" name="Constant"><a name="value" val="{value}"/>{w}</comp>\n'
    return add_comp(b, loc, xml, (-35, -8, 35, 8), {"out": (0, 0)})


def bitext(b, loc, iw, ow, kind="zero"):
    x, y = loc
    xml = (f'    <comp lib="0" loc="({x},{y})" name="Bit Extender">'
           f'<a name="in_width" val="{iw}"/><a name="out_width" val="{ow}"/>'
           f'<a name="type" val="{kind}"/></comp>\n')
    return add_comp(b, loc, xml, (-40, -10, 0, 10), {"in": (-40, 0), "out": (0, 0)})


def split_custom(b, loc, nbits, groups):
    """groups: [[bit,...], ...]，第 i 组对应 b_i。"""
    x, y = loc
    f = len(groups)
    owner = {}
    for gi, bits in enumerate(groups):
        for bit in bits:
            owner[bit] = gi
    attrs = "".join(f'<a name="bit{i}" val="{owner[i]}"/>' for i in range(nbits))
    xml = (f'    <comp lib="0" loc="({x},{y})" name="Splitter">'
           f'<a name="appear" val="center"/><a name="fanout" val="{f}"/>'
           f'<a name="incoming" val="{nbits}"/>{attrs}</comp>\n')
    top = -10 * (f // 2)
    ports = {"bus": (0, 0)}
    for i in range(f):
        ports[f"b{i}"] = (20, top + 10 * i)
    return add_comp(b, loc, xml, (0, top, 20, top + 10 * (f - 1)), ports)


# ------------------------------------------------------------------ 子电路外观
def appear(w, h, title, ports, pinmap):
    s = ['    <appear>',
         f'      <rect fill="none" height="{h}" rx="8" ry="8" stroke="#000000" stroke-width="2" width="{w}" x="0" y="0"/>',
         f'      <rect height="20" stroke="none" width="{w}" x="0" y="{h - 20}"/>',
         f'      <text dominant-baseline="central" fill="#ffffff" font-family="SansSerif" font-size="12" font-weight="bold" text-anchor="middle" x="{w // 2}" y="{h - 10}">{title}</text>']
    for (name, dx, dy, kind) in ports:
        if kind == "in":
            anchor = "start"
            tx = 8
        else:
            anchor = "end"
            tx = w - 8
        s.append(f'      <text dominant-baseline="central" font-family="SansSerif" font-size="11" text-anchor="{anchor}" x="{tx}" y="{dy}">{name}</text>')
        s.append(f'      <circ-port dir="{kind}" pin="{pinmap[name]}" x="{dx}" y="{dy}"/>')
    s.append('      <circ-anchor facing="east" x="0" y="0"/>')
    s.append('    </appear>')
    return "\n".join(s) + "\n"


# ------------------------------------------------------------------ IM / DM
def build_im(contents):
    if not contents:
        contents = "addr/data: 14 32\n00000000"
    b = lib8.Board("IM")
    a = pin(b, (100, 100), "A", "input", 32)
    q = pin(b, (900, 260), "DOUT", "output", 32)
    sp = split_custom(b, (250, 200), 32,
                      [[0, 1], list(range(2, 16)), list(range(16, 32))])
    x, y = 450, 200
    xml = (f'    <comp lib="2" loc="({x},{y})" name="ROM">'
           f'<a name="addrWidth" val="14"/><a name="dataWidth" val="32"/>'
           f'<a name="line" val="single"/><a name="misaligned" val="false"/>'
           f'<a name="contents">{contents}</a></comp>\n')
    rom = add_comp(b, (x, y), xml, (0, 0, 240, 220), {"A": (0, 10), "Q": (240, 60)})
    b.w("im_a", [(100, 100), (250, 100), (250, 200)])
    b.w("im_addr", [(270, 200), (400, 200), (400, 210), (450, 210)])
    b.w("im_q", [rom["Q"], (900, 260)])
    ports = [("A[32]", 0, 30, "in"), ("DOUT[32]", 200, 30, "out")]
    app = appear(200, 80, "Instruction ROM 16K x 32", ports,
                 {"A[32]": "100,100", "DOUT[32]": "900,260"})
    return wrap_im(b, app)


def wrap_im(b, app):
    body = b.comps and "".join(b.comps) or ""
    wires = ""
    for segs in b.nets.values():
        seen = set()
        for (x1, y1, x2, y2) in segs:
            key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if key in seen:
                continue
            seen.add(key)
            wires += f'    <wire from="({key[0]},{key[1]})" to="({key[2]},{key[3]})"/>\n'
    head = ('  <circuit name="IM">\n    <a name="circuit" val="IM"/>\n'
            '    <a name="simulationFrequency" val="8.0"/>\n'
            '    <a name="appearance" val="custom"/>\n')
    return head + app + body + wires + "  </circuit>\n"


def build_dm(contents):
    b = lib8.Board("DM")
    a = pin(b, (100, 100), "A", "input", 32)
    din = pin(b, (100, 290), "DIN", "input", 32)
    we = pin(b, (100, 250), "WE", "input", 1)
    clk = pin(b, (100, 270), "CLK", "input", 1)
    q = pin(b, (900, 290), "DOUT", "output", 32)
    sp = split_custom(b, (250, 200), 32,
                      [[0, 1], list(range(2, 16)), list(range(16, 32))])
    x, y = 450, 200
    xml = (f'    <comp lib="2" loc="({x},{y})" name="RAM">'
           f'<a name="addrWidth" val="14"/><a name="dataWidth" val="32"/>'
           f'<a name="asyncread" val="true"/><a name="trigger" val="rising"/>'
           f'<a name="clearpin" val="false"/><a name="type" val="volatile"/>')
    xml += '</comp>\n'
    ram = add_comp(b, (x, y), xml, (0, 0, 240, 250),
                   {"A": (0, 10), "D": (0, 90), "Q": (240, 90),
                    "WE": (0, 50), "CLK": (0, 70)})
    b.w("dm_a", [(100, 100), (250, 100), (250, 200)])
    b.w("dm_addr", [(270, 200), (400, 200), (400, 210), (450, 210)])
    b.w("dm_din", [(100, 290), (450, 290)])
    b.w("dm_we", [(100, 250), (450, 250)])
    b.w("dm_clk", [(100, 270), (450, 270)])
    b.w("dm_q", [(690, 290), (900, 290)])
    ports = [("A[32]", 0, 30, "in"), ("DIN[32]", 0, 70, "in"),
             ("WE", 0, 110, "in"), ("CLK", 0, 150, "in"), ("DOUT[32]", 240, 90, "out")]
    app = appear(240, 180, "Data RAM 16K x 32", ports,
                 {"A[32]": "100,100", "DIN[32]": "100,290", "WE": "100,250",
                  "CLK": "100,270", "DOUT[32]": "900,290"})
    body = "".join(b.comps)
    wires = ""
    for segs in b.nets.values():
        seen = set()
        for (x1, y1, x2, y2) in segs:
            key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if key in seen:
                continue
            seen.add(key)
            wires += f'    <wire from="({key[0]},{key[1]})" to="({key[2]},{key[3]})"/>\n'
    head = ('  <circuit name="DM">\n    <a name="circuit" val="DM"/>\n'
            '    <a name="simulationFrequency" val="8.0"/>\n'
            '    <a name="appearance" val="custom"/>\n')
    return head + app + body + wires + "  </circuit>\n"


# ------------------------------------------------------------------ 寄存器堆
BANK8_OFF = {"r1lo": (0, 30), "r2lo": (0, 50), "waddrlo": (0, 70), "wdata": (0, 90),
             "wen": (0, 110), "clk": (0, 130), "reset": (0, 150),
             "q1": (200, 80), "q2": (200, 100)}
RF32_OFF = {"raddr1": (0, 30), "raddr2": (0, 50), "waddr": (0, 70), "wdata": (0, 90),
            "wen": (0, 110), "clk": (0, 130), "reset": (0, 150),
            "rdata1": (200, 80), "rdata2": (200, 100)}


def mux8(b, loc):
    x, y = loc
    xml = (f'    <comp lib="5" loc="({x},{y})" name="Multiplexer">'
           f'<a name="select" val="3"/><a name="width" val="32"/>'
           f'<a name="enable" val="false"/></comp>\n')
    ports = {"out": (0, 0), "sel": (-20, 40)}
    for i in range(8):
        ports[f"in{i}"] = (-40, -40 + 10 * i)
    return add_comp(b, loc, xml, (-40, -50, 0, 40), ports)


def mux4(b, loc):
    x, y = loc
    xml = (f'    <comp lib="5" loc="({x},{y})" name="Multiplexer">'
           f'<a name="select" val="2"/><a name="width" val="32"/>'
           f'<a name="enable" val="false"/></comp>\n')
    ports = {"out": (0, 0), "sel": (-20, 20)}
    for i in range(4):
        ports[f"in{i}"] = (-40, -20 + 10 * i)
    return add_comp(b, loc, xml, (-40, -30, 0, 20), ports)


def decoder(b, loc, selbits):
    x, y = loc
    xml = (f'    <comp lib="5" loc="({x},{y})" name="Decoder">'
           f'<a name="select" val="{selbits}"/><a name="disabled" val="0"/></comp>\n')
    n = 1 << selbits
    ports = {"sel": (0, 0), "en": (-10, 0)}
    for i in range(n):
        ports[f"o{i}"] = (20, -10 * (n - i))
    return add_comp(b, loc, xml, (-10, -10 * (n - 1), 20, 0), ports)


def wrap_circuit(name, b, app):
    head = (f'  <circuit name="{name}">\n    <a name="circuit" val="{name}"/>\n'
            '    <a name="simulationFrequency" val="8.0"/>\n'
            '    <a name="appearance" val="custom"/>\n')
    wires = ""
    for segs in b.nets.values():
        seen = set()
        for (x1, y1, x2, y2) in segs:
            key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if key in seen:
                continue
            seen.add(key)
            wires += f'    <wire from="({key[0]},{key[1]})" to="({key[2]},{key[3]})"/>\n'
    return head + app + "".join(b.comps) + wires + "  </circuit>\n"


def build_bank8():
    b = lib8.Board("Bank8")
    pin(b, (100, 100), "r1lo", "input", 3)
    pin(b, (100, 150), "r2lo", "input", 3)
    pin(b, (100, 200), "waddrlo", "input", 3)
    pin(b, (100, 250), "wdata", "input", 32)
    pin(b, (100, 300), "wen", "input", 1)
    pin(b, (100, 350), "clk", "input", 1)
    pin(b, (100, 400), "reset", "input", 1)
    pin(b, (1750, 580), "q1", "output", 32)
    pin(b, (1750, 780), "q2", "output", 32)
    regs = []
    for i in range(8):
        regs.append(reg(b, (400 + 140 * i, 550), 32, f"r{i}"))
    m1 = mux8(b, (1620, 580))
    m2 = mux8(b, (1620, 780))
    dec = decoder(b, (150, 700), 3)
    b.connect("r1lo", [(100, 100), m1["sel"]])
    b.connect("r2lo", [(100, 150), m2["sel"]])
    b.connect("waddrlo", [(100, 200), dec["sel"]])
    b.connect("wen", [(100, 300), dec["en"]])
    for i in range(8):
        b.connect(f"en{i}", [dec[f"o{i}"], regs[i]["en"]])
    b.connect("wdata", [(100, 250)] + [r["D"] for r in regs])
    b.connect("clk", [(100, 350)] + [r["clk"] for r in regs])
    b.connect("reset", [(100, 400)] + [r["clr"] for r in regs])
    for i in range(8):
        b.connect(f"q{i}", [regs[i]["Q"], m1[f"in{i}"], m2[f"in{i}"]])
    b.connect("bank_q1", [m1["out"], (1750, 580)])
    b.connect("bank_q2", [m2["out"], (1750, 780)])
    ports = [("r1lo[3]", 0, 30, "in"), ("r2lo[3]", 0, 50, "in"), ("waddrlo[3]", 0, 70, "in"),
             ("wdata[32]", 0, 90, "in"), ("wen", 0, 110, "in"), ("clk", 0, 130, "in"),
             ("reset", 0, 150, "in"), ("q1[32]", 200, 80, "out"), ("q2[32]", 200, 100, "out")]
    app = appear(200, 180, "Register Bank 8 x 32", ports,
                 {"r1lo[3]": "100,100", "r2lo[3]": "100,150", "waddrlo[3]": "100,200",
                  "wdata[32]": "100,250", "wen": "100,300", "clk": "100,350",
                  "reset": "100,400", "q1[32]": "1750,580", "q2[32]": "1750,780"})
    return wrap_circuit("Bank8", b, app)


def build_regfile():
    b = lib8.Board("RegFile")
    pin(b, (100, 100), "raddr1", "input", 5)
    pin(b, (100, 150), "raddr2", "input", 5)
    pin(b, (100, 200), "waddr", "input", 5)
    pin(b, (100, 250), "wdata", "input", 32)
    pin(b, (100, 300), "wen", "input", 1)
    pin(b, (100, 350), "clk", "input", 1)
    pin(b, (100, 400), "reset", "input", 1)
    pin(b, (1750, 500), "rdata1", "output", 32)
    pin(b, (1750, 900), "rdata2", "output", 32)
    s1 = split_custom(b, (250, 100), 5, [[0, 1, 2], [3, 4]])
    s2 = split_custom(b, (250, 150), 5, [[0, 1, 2], [3, 4]])
    s3 = split_custom(b, (250, 200), 5, [[0, 1, 2], [3, 4]])
    bdec = decoder(b, (420, 300), 2)
    banks = []
    for i in range(4):
        banks.append(sub_custom(b, (700, 200 + 450 * i), "Bank8", BANK8_OFF, 200, 180))
    m1 = mux4(b, (1200, 700))
    m2 = mux4(b, (1200, 1200))

    b.w("raddr1", [(100, 100), (250, 100)])
    b.w("raddr2", [(100, 150), (250, 150)])
    b.w("waddr", [(100, 200), (250, 200)])
    # 输入干线（x 通道彼此错开，横向引线只做垂直跨越，不共点）
    b.w("r1", [(270, 90), (560, 90), (560, 1580)])
    b.w("r2", [(270, 140), (570, 140), (570, 1600)])
    b.w("wa", [(270, 190), (580, 190), (580, 1620)])
    b.w("wdata", [(100, 250), (100, 210), (630, 210), (630, 1640)])
    b.w("clk", [(100, 350), (90, 350), (90, 220), (640, 220), (640, 1680)])
    b.w("reset", [(100, 400), (80, 400), (80, 215), (650, 215), (650, 1700)])
    b.w("wen_bus", [(100, 300), (410, 300)])

    for i in range(4):
        y = 200 + 450 * i
        b.w(f"r1", [(560, y + 30), (700, y + 30)])
        b.w(f"r2", [(570, y + 50), (700, y + 50)])
        b.w(f"wa", [(580, y + 70), (700, y + 70)])
        b.w(f"wdata", [(630, y + 90), (700, y + 90)])
        b.w(f"clk", [(640, y + 130), (700, y + 130)])
        b.w(f"reset", [(650, y + 150), (700, y + 150)])

    # 4 个 bank 的写使能（2→4 译码，各自独立通道）
    for i, xl in enumerate((500, 510, 520, 530)):
        y0 = 260 + 10 * i
        y = 200 + 450 * i + 110
        b.w(f"wenb_{i}", [(440, y0), (xl, y0), (xl, y), (700, y)])

    # bank 读口 → 最终 4:1 选择器
    for i, xl in enumerate((950, 960, 970, 980)):
        y = 200 + 450 * i + 80
        b.w(f"q1_{i}", [(900, y), (xl, y), (xl, 680 + 10 * i), (1160, 680 + 10 * i)])
    for i, xl in enumerate((1000, 1010, 1020, 1030)):
        y = 200 + 450 * i + 100
        b.w(f"q2_{i}", [(900, y), (xl, y), (xl, 1180 + 10 * i), (1160, 1180 + 10 * i)])

    b.w("r1_bank", [(270, 100), (1150, 100), (1150, 740), (1180, 740), (1180, 720)])
    b.w("r2_bank", [(270, 150), (1140, 150), (1140, 1240), (1180, 1240), (1180, 1220)])
    b.w("wa_bank", [(270, 200), (270, 280), (420, 280), (420, 300)])
    b.w("rf_q1", [(1200, 700), (1750, 700), (1750, 500)])
    b.w("rf_q2", [(1200, 1200), (1750, 1200), (1750, 900)])

    ports = [("raddr1[5]", 0, 30, "in"), ("raddr2[5]", 0, 50, "in"), ("waddr[5]", 0, 70, "in"),
             ("wdata[32]", 0, 90, "in"), ("wen", 0, 110, "in"), ("clk", 0, 130, "in"),
             ("reset", 0, 150, "in"), ("rdata1[32]", 200, 80, "out"), ("rdata2[32]", 200, 100, "out")]
    app = appear(200, 180, "Register File 32 x 32", ports,
                 {"raddr1[5]": "100,100", "raddr2[5]": "100,150", "waddr[5]": "100,200",
                  "wdata[32]": "100,250", "wen": "100,300", "clk": "100,350",
                  "reset": "100,400", "rdata1[32]": "1750,500", "rdata2[32]": "1750,900"})
    return wrap_circuit("RegFile", b, app)


# ------------------------------------------------------------------ main
RF_OFF = RF32_OFF
ALU_OFF = {"ALUSource1": (0, 30), "ALUSource2": (0, 70), "ALUControl": (0, 110),
           "ALUResult": (220, 45), "Zero": (220, 100)}
CTL_OFF = {"Opcode": (0, 30), "Func": (0, 70), "Imm": (0, 110),
           "RegDst": (300, 30), "ALUSrc": (300, 70), "Branch": (300, 110),
           "MemRead": (300, 150), "MemWrite": (300, 190), "RegWrite": (300, 230),
           "MemtoReg": (300, 270), "Expand": (300, 310), "Stp": (300, 350),
           "ALUControl": (300, 390), "Slt": (300, 430), "Imm32": (300, 470)}
IM_OFF = {"A": (0, 30), "DOUT": (200, 30)}
DM_OFF = {"A": (0, 30), "DIN": (0, 70), "WE": (0, 110), "CLK": (0, 150),
          "DOUT": (240, 90)}


def build_main(debug=False):
    b = lib8.Board("main")
    # 引脚 / 时钟
    reset = pin(b, (150, 1000), "Reset", "input", 1)
    if debug:
        if debug == 2:
            clock = b.clock((150, 850))
        else:
            clock = pin(b, (150, 850), "clk", "input", 1)
    else:
        clock = b.clock((150, 850))

    pc = reg(b, (200, 200), 32, "PC")
    im = sub_custom(b, (520, 150), "IM", IM_OFF, 200, 80)
    split_r = split_custom(b, (820, 380), 32, [
        [0, 1, 2, 3, 4, 5],
        [6, 7, 8, 9, 10],
        [11, 12, 13, 14, 15],
        [16, 17, 18, 19, 20],
        [21, 22, 23, 24, 25],
        [26, 27, 28, 29, 30, 31],
    ])
    split_i = split_custom(b, (820, 520), 32, [list(range(0, 16)), list(range(16, 32))])
    ctl = sub_custom(b, (1150, 150), "Controller", CTL_OFF, 300, 510)
    wamux = mux2(b, (700, 600), 5)
    rf = sub_custom(b, (850, 600), "RegFile", RF_OFF, 200, 180)
    srcmux = mux2(b, (1200, 720), 32)
    alu = sub_custom(b, (1550, 600), "ALUwith9ins", ALU_OFF, 220, 140)
    dm = sub_custom(b, (1950, 600), "DM", DM_OFF, 240, 180)
    b31 = split_custom(b, (1800, 800), 32, [list(range(0, 31)), [31]])
    ext = bitext(b, (1900, 850), 1, 32, "zero")
    wbm1 = mux2(b, (1750, 950), 32)
    wbm2 = mux2(b, (1950, 950), 32)
    pc4 = adder(b, (400, 1050), 32)
    c4 = const(b, (300, 1060), "0x4", 32)
    c0a = const(b, (340, 1030), "0x0", 1)
    sh = shifter(b, (1050, 1150), 32)
    c2 = const(b, (950, 1160), "0x2", 5)
    badd = adder(b, (750, 1250), 32)
    c0b = const(b, (690, 1230), "0x0", 1)
    nzero = b.gate((1200, 1400), "NOT", 1)
    band = b.gate((1300, 1450), "AND", 2)
    pcmux = mux2(b, (900, 1500), 32)
    sdff = b.dff((320, 850), "STOP")
    nstop = b.gate((450, 900), "NOT", 1)
    aclk = b.gate((550, 950), "AND", 2)
    nstp = b.gate((500, 700), "NOT", 1)
    pen = b.gate((600, 750), "AND", 2)
    cnt = reg(b, (2200, 1100), 16, "CYCLE")
    cadd = adder(b, (2050, 1300), 16)
    c1 = const(b, (1950, 1310), "0x1", 16)
    c0c = const(b, (1990, 1280), "0x0", 1)
    dsp = split_custom(b, (2320, 900), 16, [
        [0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11], [12, 13, 14, 15]])
    d0 = b.display((2420, 980), "")
    d1 = b.display((2480, 980), "")
    d2 = b.display((2540, 980), "")
    d3 = b.display((2600, 980), "")

    # ---------------- 数据通路
    b.connect("pc_q", [pc["Q"], im["A"], pc4["A"]])
    b.connect("instr", [im["DOUT"], split_r["bus"], split_i["bus"]])
    b.connect("rdata1", [rf["rdata1"], alu["ALUSource1"]])
    b.connect("opcode", [split_r["b5"], ctl["Opcode"]])
    b.connect("func", [split_r["b0"], ctl["Func"]])
    b.connect("rs", [split_r["b4"], rf["raddr1"]])
    b.connect("rt", [split_r["b3"], rf["raddr2"], wamux["in0"]])
    b.connect("rd", [split_r["b2"], wamux["in1"]])
    b.connect("imm16", [split_i["b0"], ctl["Imm"]])
    b.connect("waddr", [wamux["out"], rf["waddr"]])
    b.connect("regdst", [ctl["RegDst"], wamux["sel"]])
    b.connect("alusrc", [ctl["ALUSrc"], srcmux["sel"]])
    b.connect("rdata2", [rf["rdata2"], srcmux["in0"], dm["DIN"]])
    b.connect("imm32", [ctl["Imm32"], srcmux["in1"], sh["data"]])
    b.connect("alu_b", [srcmux["out"], alu["ALUSource2"]])
    b.connect("alu_ctl", [ctl["ALUControl"], alu["ALUControl"]])
    b.w("alu_res", [(1770, 645), (1770, 640)])
    b.connect("alu_res", [(1770, 640), dm["A"], wbm1["in0"], b31["bus"]])
    b.connect("alu_zero", [alu["Zero"], nzero["a"]])
    b.connect("branch", [ctl["Branch"], band["a"]])
    b.connect("not_zero", [nzero["out"], band["b"]])
    b.connect("btaken", [band["out"], pcmux["sel"]])
    b.connect("pc4", [pc4["S"], pcmux["in0"], badd["A"]])
    b.connect("shift2", [sh["out"], badd["B"]])
    b.connect("baddr", [badd["S"], pcmux["in1"]])
    b.connect("pc_next", [pcmux["out"], pc["D"]])
    b.connect("mem_q", [dm["DOUT"], wbm1["in1"]])
    b.connect("memtoreg", [ctl["MemtoReg"], wbm1["sel"]])
    b.connect("wb1", [wbm1["out"], wbm2["in0"]])
    b.connect("slt_bit", [b31["b1"], ext["in"]])
    b.connect("slt_ext", [ext["out"], wbm2["in1"]])
    b.connect("slt_sel", [ctl["Slt"], wbm2["sel"]])
    b.connect("wdata", [wbm2["out"], rf["wdata"]])
    b.connect("regwrite", [ctl["RegWrite"], rf["wen"]])
    b.connect("memwrite", [ctl["MemWrite"], dm["WE"]])
    b.connect("const4", [c4["out"], pc4["B"]])
    b.connect("cin0a", [c0a["out"], pc4["Cin"]])
    b.connect("const2", [c2["out"], sh["distance"]])
    b.connect("cin0b", [c0b["out"], badd["Cin"]])

    # ---------------- 复位 / 时钟 / 停机
    b.connect("reset", [reset, pc["clr"], rf["reset"], cnt["clr"], sdff["R"]])
    b.connect("clk_raw", [clock, sdff["CLK"], aclk["a"]])
    b.connect("stopped", [sdff["Q"], nstop["a"]])
    b.connect("run", [nstop["out"], cnt["en"], aclk["b"], pen["a"]])
    b.connect("cpu_clk", [aclk["out"], pc["clk"], rf["clk"], dm["CLK"], cnt["clk"]])
    b.connect("stp", [ctl["Stp"], sdff["D"], nstp["a"]])
    b.connect("nstp", [nstp["out"], pen["b"]])
    b.connect("pc_en", [pen["out"], pc["en"]])

    # ---------------- 周期计数与显示
    b.connect("cycle_q", [cnt["Q"], cadd["A"], dsp["bus"]])
    b.connect("cycle_next", [cadd["S"], cnt["D"]])
    b.connect("cin1", [c1["out"], cadd["B"]])
    b.connect("cin0c", [c0c["out"], cadd["Cin"]])
    b.connect("d3", [dsp["b3"], d3])
    b.connect("d2", [dsp["b2"], d2])
    b.connect("d1", [dsp["b1"], d1])
    b.connect("d0", [dsp["b0"], d0])

    if debug:
        p_pc = pin(b, (2800, 300), "dbg_PC", "output", 32)
        p_ins = pin(b, (2800, 380), "dbg_instr", "output", 32)
        p_alu = pin(b, (2800, 460), "dbg_alu", "output", 32)
        p_wd = pin(b, (2800, 540), "dbg_wdata", "output", 32)
        p_we = pin(b, (2800, 620), "dbg_memwrite", "output", 1)
        p_cy = pin(b, (2800, 700), "dbg_cycle", "output", 16)
        p_st = pin(b, (2800, 780), "dbg_stop", "output", 1)
        p_wb = pin(b, (2800, 860), "dbg_wb", "output", 32)
        p_rw = pin(b, (2800, 940), "dbg_regwrite", "output", 1)
        p_rq = pin(b, (2800, 1020), "dbg_ramq", "output", 32)
        p_r1 = pin(b, (2800, 1100), "dbg_rdata1", "output", 32)
        p_ab = pin(b, (2800, 1180), "dbg_alub", "output", 32)
        p_ac = pin(b, (2800, 1260), "dbg_aluctl", "output", 4)
        b.connect("pc_q", [pc["Q"], p_pc])
        b.connect("instr", [im["DOUT"], p_ins])
        b.connect("alu_res", [(1770, 640), p_alu])
        b.connect("rdata2", [rf["rdata2"], p_wd])
        b.connect("memwrite", [dm["WE"], p_we])
        b.connect("cycle_q", [cnt["Q"], p_cy])
        b.connect("stopped", [sdff["Q"], p_st])
        b.connect("wdata", [wbm2["out"], p_wb])
        b.connect("regwrite", [ctl["RegWrite"], p_rw])
        b.connect("mem_q", [dm["DOUT"], p_rq])
        b.connect("rdata1", [rf["rdata1"], p_r1])
        b.connect("alu_b", [srcmux["out"], p_ab])
        b.connect("alu_ctl", [ctl["ALUControl"], p_ac])

    return b


# ------------------------------------------------------------------ 组装

def build(rom_contents, ram_contents, debug=False, out_path=None):
    main = build_main(debug)
    im = build_im(rom_contents)
    dm = build_dm(ram_contents)
    blocks = [
        build_bank8(),
        build_regfile(),
        get_circuit("3.3", "ALUwith9ins"),
        get_circuit("3.4", "CU"),
        get_circuit("3.4", "ALU_Control"),
        get_circuit("3.4", "Extender"),
        get_circuit("3.4", "Controller"),
    ]
    xml = HEAD + main.xml() + im + dm + "".join(blocks) + "</project>\n"
    if out_path:
        open(out_path, "w", encoding="utf-8", newline="\n").write(xml)
    return xml



# ------------------------------------------------------------------ CLI
def parse_hex(path):
    words = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("v3.0") or ":" not in line:
                continue
            addr, rest = line.split(":", 1)
            base = int(addr, 16)
            for i, tok in enumerate(rest.split()):
                words[base + i] = int(tok, 16)
    return words


def contents(words):
    if not words:
        return ""
    nz = [i for i, v in words.items() if v != 0]
    if not nz:
        return ""
    last = max(nz)
    vals = [words.get(i, 0) for i in range(last + 1)]
    lines = [" ".join("%08x" % v for v in vals[i:i + 8]) for i in range(0, len(vals), 8)]
    return "addr/data: 14 32\n" + "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="生成 Logisim 3.9 单周期 MIPS CPU")
    ap.add_argument("--src33", required=True, help="3.3.circ（含 ALUwith9ins）")
    ap.add_argument("--src34", required=True, help="3.4.circ（含 Controller）")
    ap.add_argument("--hexdir", help="测试程序 hex 目录（给则生成 G1-T1..T6）")
    ap.add_argument("--out", required=True, help="输出目录")
    args = ap.parse_args()

    SRC["3.3"] = os.path.abspath(args.src33)
    SRC["3.4"] = os.path.abspath(args.src34)
    os.makedirs(args.out, exist_ok=True)

    build("", "", False, os.path.join(args.out, "单周期CPU.circ"))
    print("written", os.path.join(args.out, "单周期CPU.circ"))

    if args.hexdir:
        dst = os.path.join(args.out, "测试程序")
        os.makedirs(dst, exist_ok=True)
        for t in range(1, 7):
            rom = contents(parse_hex(os.path.join(args.hexdir, f"G1-T{t}-ROM.hex")))
            p = os.path.join(dst, f"G1-T{t}.circ")
            build(rom, "", False, p)
            print("written", p)


if __name__ == "__main__":
    main()
