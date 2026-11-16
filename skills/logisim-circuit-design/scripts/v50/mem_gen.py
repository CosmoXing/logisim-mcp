# -*- coding: utf-8 -*-
"""存储器生成器（Logisim-evolution 5.0）：64KB ROM + 64KB RAM。

结构：
  main
   ├─ rom64k : 1 x 16Kx32 ROM + 字节选择
   └─ ram64k : 4 x 16Kx8 RAM 低位交叉 + 字节使能 + 字/字节读选择
       └─ bank8 x4

约束：
  - CPU 给 16 位字节地址；内部 A[15:2] 为字地址，A[1:0] 选字节通道；
  - 字访问 4 个 bank 并行，字节访问只使能一个 bank，均为单周期；
  - 所有连线为实体正交线，不使用隧道；
  - 生成时做连通性/短接自检，失败不落盘。

用法：
  python mem_gen.py out.circ
  # 默认输出到当前目录 mem64k.circ
"""
from __future__ import annotations

import os
import sys

import lib8       # noqa: E402
import route8     # noqa: E402  (patches Board.verify_short / const)

GRID = 10
LIB_WIRE = "0"
LIB_MEM = "2"
LIB_PLEX = "5"

# ---------------------------------------------------------------- 几何工厂


def _comp(b, loc, xml, body_rel, ports_rel):
    """body_rel=(x1,y1,x2,y2) 相对；ports_rel={name:(dx,dy)}。"""
    return b._add(xml, loc, {"body": body_rel, "ports": ports_rel})


def add_ram(b, loc):
    """16Kx8 RAM，异步读，上升沿写，独立读写总线。"""
    x, y = loc
    xml = (f'    <comp lib="{LIB_MEM}" loc="({x},{y})" name="RAM">'
           f'<a name="addrWidth" val="14"/><a name="dataWidth" val="8"/>'
           f'<a name="enables" val="byte"/><a name="type" val="volatile"/>'
           f'<a name="trigger" val="rising"/><a name="asyncread" val="true"/>'
           f'<a name="databus" val="bibus"/><a name="clearpin" val="false"/>'
           f'</comp>\n')
    return _comp(b, loc, xml, (0, 0, 240, 250),
                 {"A": (0, 10), "D": (0, 90), "Q": (240, 90),
                  "WE": (0, 50), "EN": (0, 60), "CLK": (0, 70)})


def add_rom(b, loc, contents):
    """16Kx32 ROM，异步读。"""
    x, y = loc
    xml = (f'    <comp lib="{LIB_MEM}" loc="({x},{y})" name="ROM">'
           f'<a name="addrWidth" val="14"/><a name="dataWidth" val="32"/>'
           f'<a name="line" val="single"/><a name="misaligned" val="false"/>'
           f'<a name="contents" val="{contents}"/>'
           f'</comp>\n')
    return _comp(b, loc, xml, (0, 0, 240, 220),
                 {"A": (0, 10), "Q": (240, 60)})


def add_split(b, loc, fanout, incoming, facing="east"):
    """等宽分线/合并；b0 在最上。"""
    x, y = loc
    bits = "".join(
        f'<a name="bit{i}" val="{i * fanout // incoming}"/>' for i in range(incoming))
    fac = "" if facing == "east" else '<a name="facing" val="west"/>'
    xml = (f'    <comp lib="{LIB_WIRE}" loc="({x},{y})" name="Splitter">'
           f'<a name="fanout" val="{fanout}"/><a name="incoming" val="{incoming}"/>'
           f'<a name="appear" val="center"/>{fac}{bits}</comp>\n')
    top = -10 * (fanout // 2)
    dx = 20 if facing == "east" else -20
    ports = {"bus": (0, 0)}
    for i in range(fanout):
        ports[f"b{i}"] = (dx, top + 10 * i)
    if facing == "east":
        body = (0, top, 21, top + 10 * (fanout - 1) + 1)
    else:
        body = (-21, top, 0, top + 10 * (fanout - 1) + 1)
    return _comp(b, loc, xml, body, ports)


def add_mux(b, loc, select, width):
    x, y = loc
    xml = (f'    <comp lib="{LIB_PLEX}" loc="({x},{y})" name="Multiplexer">'
           f'<a name="select" val="{select}"/><a name="width" val="{width}"/></comp>\n')
    n = 1 << select
    if select == 1:
        body = (-30, -20, 0, 20)
        ports = {"in0": (-30, -10), "in1": (-30, 10),
                 "sel": (-20, 20), "out": (0, 0)}
    elif select == 2:
        body = (-40, -30, 0, 30)
        ports = {f"in{i}": (-40, -20 + 10 * i) for i in range(4)}
        ports.update(sel=(-20, 20), out=(0, 0))
    elif select == 3:
        body = (-40, -50, 0, 50)
        ports = {f"in{i}": (-40, -40 + 10 * i) for i in range(8)}
        ports.update(sel=(-20, 40), out=(0, 0))
    else:
        raise ValueError("unsupported mux select")
    return _comp(b, loc, xml, body, ports)


def add_decoder(b, loc, select=2):
    x, y = loc
    n = 1 << select
    xml = (f'    <comp lib="{LIB_PLEX}" loc="({x},{y})" name="Decoder">'
           f'<a name="select" val="{select}"/></comp>\n')
    ports = {f"out{i}": (20, -10 * (n - i)) for i in range(n)}
    ports.update(sel=(0, 0), en=(-10, 0))
    body = (-20, -10 * (n + 1), 20, 10)
    return _comp(b, loc, xml, body, ports)


def add_extender(b, loc, in_w, out_w):
    x, y = loc
    xml = (f'    <comp lib="{LIB_WIRE}" loc="({x},{y})" name="Bit Extender">'
           f'<a name="in_width" val="{in_w}"/><a name="out_width" val="{out_w}"/>'
           f'<a name="type" val="zero"/></comp>\n')
    return _comp(b, loc, xml, (-40, -20, 0, 20), {"in": (-40, 0), "out": (0, 0)})


def add_pin(b, loc, label, kind, width):
    p = b.pin(loc, label, kind, width)
    x, y = loc
    if kind == "input":
        b.bodies.append((x - 50, y - 10, x, y + 10))
    else:
        b.bodies.append((x, y - 10, x + 50, y + 10))
    b._blocked_cache = None
    return p


def stub_left(p, d=20):
    return (p[0] - d, p[1])


def stub_right(p, d=20):
    return (p[0] + d, p[1])


def add_sub(b, loc, name, ports, w, h):
    """子电路实例；ports={name:(dx,dy,width)}，必须与外观 circ-port 一致。"""
    x, y = loc
    b.comps.append(f'    <comp loc="({x},{y})" name="{name}"></comp>\n')
    b.bodies.append((x, y, x + w, y + h))
    pts = {k: (x + dx, y + dy) for k, (dx, dy, _w) in ports.items()}
    for p in pts.values():
        b.all_ports.add((p[0] // GRID, p[1] // GRID))
    b._blocked_cache = None
    return pts


# ---------------------------------------------------------------- 外观


def appear(name, w, h, ports):
    """ports: [(dir, label, app_x, app_y, pin_x, pin_y)]"""
    lines = [
        '  <appear>',
        f'    <rect fill="none" height="{h}" rx="10" ry="10" '
        f'stroke="#000000" stroke-width="2" width="{w}" x="0" y="0"/>',
        f'    <rect height="20" stroke="none" width="{w}" x="0" y="{h - 20}"/>',
        f'    <text dominant-baseline="central" fill="#ffffff" '
        f'font-family="SansSerif" font-size="12" font-weight="bold" '
        f'text-anchor="middle" x="{w // 2}" y="{h - 10}">{name}</text>',
    ]
    for d, label, ax, ay, _ix, _iy in ports:
        anchor = "start" if d == "in" else "end"
        tx = 8 if d == "in" else w - 8
        lines.append(
            f'    <text dominant-baseline="central" font-family="SansSerif" '
            f'font-size="11" text-anchor="{anchor}" x="{tx}" y="{ay}">{label}</text>')
    lines.append('    <circ-anchor facing="east" x="0" y="0"/>')
    for d, _label, ax, ay, ix, iy in ports:
        lines.append(
            f'    <circ-port dir="{d}" pin="{ix},{iy}" x="{ax}" y="{ay}"/>')
    lines.append('  </appear>')
    return "\n".join(lines) + "\n"


BANK_PORTS = [
    ("in", "A[14]", 0, 30, 120, 310),
    ("in", "D[8]", 0, 60, 120, 390),
    ("in", "WE", 0, 100, 120, 350),
    ("in", "CLK", 0, 130, 120, 370),
    ("out", "Q[8]", 180, 80, 680, 390),
]
BANK_APPEAR = appear("RAM Bank 16Kx8", 180, 170, BANK_PORTS)

ROM_PORTS = [
    ("in", "A[16]", 0, 40, 80, 200),
    ("in", "BYTE", 0, 80, 80, 320),
    ("out", "DOUT[32]", 220, 60, 1500, 300),
]
ROM_APPEAR = appear("ROM 64KB (16Kx32)", 220, 150, ROM_PORTS)

RAM_PORTS = [
    ("in", "A[16]", 0, 20, 80, 150),
    ("in", "DIN[32]", 0, 50, 80, 350),
    ("in", "WE", 0, 110, 80, 600),
    ("in", "BYTE", 0, 140, 80, 540),
    ("in", "CLK", 0, 170, 80, 640),
    ("out", "DOUT[32]", 260, 90, 1950, 350),
]
RAM_APPEAR = appear("RAM 64KB (4x16Kx8 interleaved)", 260, 220, RAM_PORTS)


class MemBoard(lib8.Board):
    def __init__(self, name, appearance=""):
        super().__init__(name)
        self.appearance = appearance

    def xml(self):
        body = "".join(self.comps)
        for segs in self.nets.values():
            seen = set()
            for (x1, y1, x2, y2) in segs:
                key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if key in seen:
                    continue
                seen.add(key)
                body += (f'    <wire from="({key[0]},{key[1]})" '
                         f'to="({key[2]},{key[3]})"/>\n')
        return (f'  <circuit name="{self.name}">\n'
                f'    <a name="circuit" val="{self.name}"/>\n'
                f'{body}{self.appearance}  </circuit>\n')


# ---------------------------------------------------------------- bank8


def build_bank8():
    b = MemBoard("bank8", BANK_APPEAR)
    add_pin(b, (120, 310), "A", "input", 14)
    add_pin(b, (120, 390), "D", "input", 8)
    add_pin(b, (120, 350), "WE", "input", 1)
    add_pin(b, (120, 370), "CLK", "input", 1)
    add_pin(b, (680, 390), "Q", "output", 8)
    r = add_ram(b, (360, 300))
    b.const((300, 360), "1", 1)
    b.w("A", [(120, 310), r["A"]])
    b.w("D", [(120, 390), r["D"]])
    b.w("WE", [(120, 350), r["WE"]])
    b.w("CLK", [(120, 370), r["CLK"]])
    b.w("EN", [(300, 360), r["EN"]])
    b.w("Q", [r["Q"], (680, 390)])
    return b


# ---------------------------------------------------------------- rom64k


def build_rom64k():
    b = MemBoard("rom64k", ROM_APPEAR)
    a16 = add_pin(b, (80, 200), "A", "input", 16)
    by = add_pin(b, (80, 320), "BYTE", "input", 1)
    q = add_pin(b, (1500, 300), "DOUT", "output", 32)

    s16 = add_split(b, (240, 200), 8, 16, "east")
    m14 = add_split(b, (400, 200), 7, 14, "west")
    b.connect("a_in", [a16, s16["bus"]])
    # A[3:2]..A[15:14] -> 14 位字地址（b1..b7 -> m.b0..b6）
    for k in range(7):
        b.connect(f"wa{k}", [s16[f"b{k + 1}"], m14[f"b{k}"]])

    rom = add_rom(b, (700, 300), ROM_CONTENTS)
    b.connect("rom_a", [m14["bus"], rom["A"]])

    s32 = add_split(b, (1050, 360), 4, 32, "east")
    b.connect("rom_q", [rom["Q"], s32["bus"], (1370, 290)])

    mx = add_mux(b, (1200, 400), 2, 8)
    for i in range(4):
        b.connect(f"rbyte{i}", [s32[f"b{i}"], mx[f"in{i}"]])
    b.connect("lane", [s16["b0"], mx["sel"]])

    ext = add_extender(b, (1280, 400), 8, 32)
    b.connect("byte32", [mx["out"], ext["in"]])

    outm = add_mux(b, (1400, 300), 1, 32)
    b.connect("ext_out", [ext["out"], outm["in1"]])
    b.connect("byte_sel", [by, outm["sel"]])
    b.connect("rom_dout", [outm["out"], q])
    return b


# ---------------------------------------------------------------- ram64k


def build_ram64k():
    b = MemBoard("ram64k", RAM_APPEAR)
    a16 = add_pin(b, (80, 150), "A", "input", 16)
    d32 = add_pin(b, (80, 350), "DIN", "input", 32)
    we = add_pin(b, (80, 600), "WE", "input", 1)
    by = add_pin(b, (80, 540), "BYTE", "input", 1)
    clk = add_pin(b, (80, 640), "CLK", "input", 1)
    q = add_pin(b, (1950, 350), "DOUT", "output", 32)

    # 地址：16 位 -> 8 个 2 位分支；b1..b7 合成 14 位字地址
    s16 = add_split(b, (240, 150), 8, 16, "east")
    m14 = add_split(b, (400, 150), 7, 14, "west")
    b.connect("a_in", [a16, s16["bus"]])
    for k in range(7):
        b.connect(f"wa{k}", [s16[f"b{k + 1}"], m14[f"b{k}"]])

    bank_names = ["bank0", "bank1", "bank2", "bank3"]
    bank_x = [600, 850, 1100, 1350]
    banks = []
    for i, (nm, x) in enumerate(zip(bank_names, bank_x)):
        ports = {
            "A": (0, 30, 14), "D": (0, 60, 8), "WE": (0, 100, 1),
            "CLK": (0, 130, 1), "Q": (180, 80, 8),
        }
        banks.append(add_sub(b, (x, 300), "bank8", ports, 180, 170))

    # 14 位字地址扇出到 4 个 bank；每个端口先用 20px 水平短桩引入
    b.connect("word_addr", [m14["bus"]] +
              [stub_left(bk["A"]) for bk in banks] + [bk["A"] for bk in banks])

    # 数据输入：32 位 -> 4 个字节
    s32 = add_split(b, (240, 350), 4, 32, "east")
    b.connect("din_in", [d32, s32["bus"]])
    muxes = []
    for i in range(4):
        muxes.append(add_mux(b, (570 + 250 * i, 250), 1, 8))
    # 先布扇出最大的两根网，避免被后面的短线堵死
    b.connect("byte_data", [s32["b0"], muxes[0]["in0"], muxes[0]["in1"],
                            muxes[1]["in1"], muxes[2]["in1"], muxes[3]["in1"]])
    for i in range(1, 4):
        b.connect(f"word_byte{i}", [s32[f"b{i}"], muxes[i]["in0"]])
    for i in range(4):
        b.connect(f"dout{i}", [muxes[i]["out"],
                               stub_left(banks[i]["D"]), banks[i]["D"]])

    # 字节使能：BE_i = ~BYTE | lane_i
    dec = add_decoder(b, (240, 500), 2)
    b.const((170, 500), "1", 1)
    b.connect("dec_en", [(170, 500), dec["en"]])
    notb = b.gate((240, 560), "NOT", 1)
    b.connect("byte_net", [by, notb["a"], (1830, 370)] +
              [mx["sel"] for mx in muxes])

    ors = []
    ands = []
    for i in range(4):
        ox = 560 + 250 * i
        ors.append(b.gate((ox, 480), "OR", 2))
        ands.append(b.gate((ox, 550), "AND", 2))
    b.connect("not_byte_fan", [notb["out"]] + [g["a"] for g in ors])
    for i in range(4):
        b.connect(f"lane{i}", [dec[f"out{i}"], ors[i]["b"]])
        b.connect(f"be{i}", [ors[i]["out"], ands[i]["b"]])
        b.connect(f"we{i}", [ands[i]["out"],
                             stub_left(banks[i]["WE"]), banks[i]["WE"]])
    b.connect("we_fan", [we] + [g["a"] for g in ands])
    b.connect("clk_fan", [clk] + [stub_left(bk["CLK"]) for bk in banks] +
              [bk["CLK"] for bk in banks])

    # 读：4 个 bank Q -> 32 位合并 + 4:1 字节选择
    m32 = add_split(b, (1650, 300), 4, 32, "west")
    bmx = add_mux(b, (1650, 450), 2, 8)
    for i in range(4):
        b.connect(f"q{i}", [banks[i]["Q"], stub_right(banks[i]["Q"]),
                            m32[f"b{i}"], bmx[f"in{i}"]])
    b.connect("lane_dec", [s16["b0"], dec["sel"], bmx["sel"]])

    ext = add_extender(b, (1750, 450), 8, 32)
    b.connect("ram_byte32", [bmx["out"], ext["in"]])

    outm = add_mux(b, (1850, 350), 1, 32)
    b.connect("ram_word", [m32["bus"], outm["in0"]])
    b.connect("ram_byte", [ext["out"], outm["in1"]])
    b.connect("ram_dout", [outm["out"], q])
    return b


# ---------------------------------------------------------------- main


def build_main():
    b = MemBoard("main")
    a = add_pin(b, (100, 200), "A", "input", 16)
    din = add_pin(b, (100, 260), "DIN", "input", 32)
    we = add_pin(b, (100, 340), "WE", "input", 1)
    by = add_pin(b, (100, 380), "BYTE", "input", 1)
    sel = add_pin(b, (100, 420), "SEL", "input", 1)
    clk = add_pin(b, (100, 460), "CLK", "input", 1)
    dout = add_pin(b, (1050, 400), "DOUT", "output", 32)

    rom_ports = {
        "A": (0, 40, 16), "BYTE": (0, 80, 1), "DOUT": (220, 60, 32),
    }
    ram_ports = {
        "A": (0, 20, 16), "DIN": (0, 50, 32), "WE": (0, 110, 1),
        "BYTE": (0, 140, 1), "CLK": (0, 170, 1), "DOUT": (260, 90, 32),
    }
    rom = add_sub(b, (400, 150), "rom64k", rom_ports, 220, 150)
    ram = add_sub(b, (400, 400), "ram64k", ram_ports, 260, 220)

    we_and = b.gate((300, 340), "AND", 2)
    b.connect("a_bus", [a, rom["A"], ram["A"]])
    b.connect("din_bus", [din, ram["DIN"]])
    b.connect("byte_bus", [by, rom["BYTE"], ram["BYTE"]])
    b.connect("clk_bus", [clk, ram["CLK"]])
    b.connect("we_raw", [we, we_and["a"]])
    b.connect("sel_bus", [sel, we_and["b"], (880, 420)])
    b.connect("ram_we", [we_and["out"], ram["WE"]])

    outm = add_mux(b, (900, 400), 1, 32)
    b.connect("rom_q", [rom["DOUT"], outm["in0"]])
    b.connect("ram_q", [ram["DOUT"], outm["in1"]])
    b.connect("dout_bus", [outm["out"], dout])
    return b


# ---------------------------------------------------------------- ROM 初始化


def rom_contents():
    """前 64 个字放测试图案，其余为 0。"""
    words = [((0x11223344 + i * 0x01010101) & 0xFFFFFFFF) for i in range(64)]
    lines = [f"{w:08X}" for w in words]
    return "addr/data: 14 32&#10;" + "&#10;".join(lines)


ROM_CONTENTS = rom_contents()


def project(boards):
    """lib8.project 只声明 0~4 号库，这里补上 Plexers(5)。"""
    data = lib8.project(boards)
    if '<lib desc="#Plexers"' not in data:
        data = data.replace(
            '  <lib desc="#Base" name="4"/>\n',
            '  <lib desc="#Base" name="4"/>\n'
            '  <lib desc="#Plexers" name="5"/>\n')
    return data


# ---------------------------------------------------------------- 主流程


def main(out_path=None):
    boards = [build_main(), build_ram64k(), build_rom64k(), build_bank8()]
    bad = 0
    for b in boards:
        try:
            b.verify_nets()
            b.verify_short()
            print(f"[{b.name}] comps={len(b.comps)} nets={len(b.nets)}  OK")
        except Exception as exc:  # noqa: BLE001
            bad += 1
            print(f"[{b.name}] FAIL: {exc}")
    if bad:
        print("!! 自检失败，未写文件")
        sys.exit(1)
    out_path = out_path or os.path.join(os.getcwd(), "mem64k.circ")
    parent = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(parent, exist_ok=True)
    data = project(boards)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
    print("written", out_path, len(data), "bytes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
