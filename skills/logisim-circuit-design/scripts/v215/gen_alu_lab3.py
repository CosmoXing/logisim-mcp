# -*- coding: utf-8 -*-
"""实验3 8位 ALU（带比较器）：Logisim-ITA 2.15.0.2 生成器。

以实验2 的加法器文件为骨架，复用 半加器/全加器/4位全加器，
新增 8位可控加减器、移位器、逻辑运算器、比较器、8位 ALU 顶层。
布局按紧凑版排布（模块 2×2、总线用隧道扇出）。

用法：
    python gen_alu_lab3.py [--src 实验2.circ] [--out 实验3.circ]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board215 import Appearance, Board  # noqa: E402

ADD8_APP = Appearance(
    rect=(0, 20, 170, 200), anchor=(85, 120), label="8位可控加减器",
    label_pos=(85, 60),
    ports=[("A", "120,100", 0, 55, 10), ("B", "120,400", 0, 85, 10),
           ("Sub", "120,600", 0, 115, 8), ("Cin", "120,700", 0, 145, 8),
           ("S", "1600,1100", 170, 55, 10), ("Cout", "1600,950", 170, 95, 8),
           ("OF", "1600,1400", 170, 135, 8)])

SHIFT_APP = Appearance(
    rect=(0, 20, 170, 180), anchor=(85, 110), label="移位器",
    label_pos=(85, 60),
    ports=[("X", "120,100", 0, 50, 10), ("N", "120,200", 0, 80, 8),
           ("S1", "120,300", 0, 110, 8), ("S0", "120,400", 0, 140, 8),
           ("Y", "1500,200", 170, 60, 10), ("SOL", "1500,500", 170, 120, 8)])

LOGIC_APP = Appearance(
    rect=(0, 20, 160, 160), anchor=(80, 100), label="逻辑运算器",
    label_pos=(80, 55),
    ports=[("A", "120,100", 0, 50, 10), ("B", "120,200", 0, 80, 10),
           ("S1", "120,300", 0, 110, 8), ("S0", "120,400", 0, 140, 8),
           ("Y", "1200,300", 160, 80, 10)])

CMP_APP = Appearance(
    rect=(0, 20, 170, 200), anchor=(85, 110), label="比较器",
    label_pos=(85, 55),
    ports=[("A", "120,100", 0, 50, 10), ("B", "120,200", 0, 80, 10),
           ("S1", "120,300", 0, 110, 8), ("S0", "120,400", 0, 140, 8),
           ("Y", "1200,300", 170, 50, 10), ("GT", "1200,450", 170, 90, 8),
           ("EQ", "1200,550", 170, 120, 8), ("LT", "1200,650", 170, 150, 8)])


# ---------------------------------------------------------------- 子电路

def build_add8():
    b = Board("8位可控加减器")
    b.pin((120, 100), "A", width=8)
    b.pin((120, 400), "B", width=8)
    b.pin((120, 600), "Sub")
    b.pin((120, 700), "Cin")
    b.pin((1600, 1100), "S", facing="west", width=8, output=True)
    b.pin((1600, 950), "Cout", facing="west", output=True)
    b.pin((1600, 1400), "OF", facing="west", output=True)

    bus_a, bits_a = b.split((300, 100), 8, "south")
    b.wire((120, 100), bus_a)
    b.fan_bits(bits_a, "a")

    bus_b, bits_b = b.split((300, 400), 8, "south")
    b.wire((120, 400), bus_b)
    b.fan_bits(bits_b, "b")

    b.stub((120, 600), "sub", 1, "e")
    b.stub((120, 700), "cin", 1, "e")

    # B 取反：bx = b xor sub（单列 8 门，70px 间距）
    for i in range(8):
        b.gate_io("XOR Gate", (700, 250 + 70 * i), 2, 1,
                  [f"b{i}", "sub"], f"bx{i}")

    # 低位进位：c0 = Cin xor Sub
    b.gate_io("XOR Gate", (700, 850), 2, 1, ["cin", "sub"], "c0")

    # 两个 4 位全加器（上下 330px）
    low = b.sub("4位全加器", (1100, 500), FA4_OFF)
    high = b.sub("4位全加器", (1100, 830), FA4_OFF)
    for i in range(4):
        b.stub(low[f"A{i}"], f"a{i}", 1, "w")
        b.stub(low[f"B{i}"], f"bx{i}", 1, "w")
        b.stub(low[f"S{i}"], f"s{i}", 1, "e")
        b.stub(high[f"A{i}"], f"a{i + 4}", 1, "w")
        b.stub(high[f"B{i}"], f"bx{i + 4}", 1, "w")
        b.stub(high[f"S{i}"], f"s{i + 4}", 1, "e")
    b.stub(low["C0"], "c0", 1, "w")
    b.stub(low["C4"], "c4", 1, "e")
    b.stub(high["C0"], "c4", 1, "w")
    b.stub(high["C4"], "c8", 1, "e")

    # OF = ~(A7 xor Bx7) & (A7 xor S7)
    b.gate_io("XOR Gate", (1400, 1250), 2, 1, ["a7", "bx7"], "t_of1")
    b.gate_io("NOT Gate", (1400, 1320), 1, 1, ["t_of1"], "t_of2")
    b.gate_io("XOR Gate", (1600, 1250), 2, 1, ["a7", "s7"], "t_of3")
    b.gate_io("AND Gate", (1600, 1320), 2, 1, ["t_of2", "t_of3"], "of")

    # S 汇总
    bus_s, bits_s = b.split((1400, 1100), 8, "north")
    b.fan_bits(bits_s, "s", "north")
    b.wire(bus_s, (1600, 1100))

    b.stub((1600, 950), "c8", 1, "w")
    b.stub((1600, 1400), "of", 1, "w")
    return b


def build_shifter():
    b = Board("移位器")
    b.pin((120, 100), "X", width=8)
    b.pin((120, 200), "N", width=3)
    b.pin((120, 300), "S1")
    b.pin((120, 400), "S0")
    b.pin((1500, 200), "Y", facing="west", width=8, output=True)
    b.pin((1500, 500), "SOL", facing="west", output=True)

    bus_x, bits_x = b.split((300, 100), 8, "south")
    b.wire((120, 100), bus_x)
    b.wire(bus_x, (bus_x[0], bus_x[1] - 20))
    b.tunnel((bus_x[0], bus_x[1] - 20), "X", 8, "north")
    b.fan_bits(bits_x, "x")

    b.stub((120, 200), "N", 3, "e")
    b.stub((120, 300), "S1", 1, "e")
    b.stub((120, 400), "S0", 1, "e")

    # 三种移位器（纵向 150px）
    for shift, y in (("ll", 400), ("lr", 550), ("ar", 700)):
        d, n, out = b.shifter((600, y), 8, shift)
        b.stub(d, "X", 8, "w")
        b.stub(n, "N", 3, "w")
        b.stub(out, "Y" + shift, 8, "e")

    # 4 选 1：传送 X / 左移 / 右移 / 算术右移
    data, sel, out = b.mux((1000, 550), 2, 8)
    b.fan_stub(data, ["X", "Yll", "Ylr", "Yar"], 8, "w")
    b.stub(sel, "S10", 2, "s")
    b.stub(out, "Y", 8, "e")

    # S10 = {S1,S0}
    bus2, p2 = b.split((800, 700), 2, "north")
    b.wire(p2[0], (p2[0][0], p2[0][1] - 20))
    b.tunnel((p2[0][0], p2[0][1] - 20), "S0", 1, "north")
    b.wire(p2[1], (p2[1][0], p2[1][1] - 40))
    b.tunnel((p2[1][0], p2[1][1] - 40), "S1", 1, "north")
    b.wire(bus2, (bus2[0], bus2[1] + 20))
    b.tunnel((bus2[0], bus2[1] + 20), "S10", 2, "south")

    # SOL：移出位。N=0 时为 0；左移取 X[8-N]，右移取 X[N-1]
    b.const((300, 900), 1, 0)
    b.stub((300, 900), "zero1", 1, "e")

    left_data = ["zero1"] + [f"x{7 - i}" for i in range(7)]
    data, sel, out = b.mux((600, 1000), 3, 1)
    b.fan_stub(data, left_data, 1, "w")
    b.stub(sel, "N", 3, "s")
    b.stub(out, "SLL", 1, "e")

    right_data = ["zero1"] + [f"x{i}" for i in range(7)]
    data, sel, out = b.mux((1000, 1000), 3, 1)
    b.fan_stub(data, right_data, 1, "w")
    b.stub(sel, "N", 3, "s")
    b.stub(out, "SLR", 1, "e")

    data, sel, out = b.mux((1300, 1000), 1, 1)
    b.fan_stub(data, ["SLL", "SLR"], 1, "w")
    b.stub(sel, "S1", 1, "s")
    b.stub(out, "SOLR", 1, "e")

    b.gate_io("OR Gate", (1300, 1100), 2, 1, ["S1", "S0"], "SHEN")
    b.gate_io("AND Gate", (1450, 1000), 2, 1, ["SOLR", "SHEN"], "SOL")

    b.stub((1500, 200), "Y", 8, "w")
    b.stub((1500, 500), "SOL", 1, "w")
    return b


def build_logic():
    b = Board("逻辑运算器")
    b.pin((120, 100), "A", width=8)
    b.pin((120, 200), "B", width=8)
    b.pin((120, 300), "S1")
    b.pin((120, 400), "S0")
    b.pin((1200, 300), "Y", facing="west", width=8, output=True)

    b.stub((120, 100), "A", 8, "e")
    b.stub((120, 200), "B", 8, "e")
    b.stub((120, 300), "S1", 1, "e")
    b.stub((120, 400), "S0", 1, "e")

    b.gate_io("AND Gate", (500, 200), 2, 8, ["A", "B"], "YAND")
    b.gate_io("OR Gate", (500, 350), 2, 8, ["A", "B"], "YOR")
    b.gate_io("NOT Gate", (500, 500), 1, 8, ["A"], "YNOT")
    b.gate_io("XOR Gate", (500, 650), 2, 8, ["A", "B"], "YXOR")

    bus2, p2 = b.split((700, 750), 2, "north")
    b.wire(p2[0], (p2[0][0], p2[0][1] - 20))
    b.tunnel((p2[0][0], p2[0][1] - 20), "S0", 1, "north")
    b.wire(p2[1], (p2[1][0], p2[1][1] - 40))
    b.tunnel((p2[1][0], p2[1][1] - 40), "S1", 1, "north")
    b.wire(bus2, (bus2[0], bus2[1] + 20))
    b.tunnel((bus2[0], bus2[1] + 20), "S10", 2, "south")

    data, sel, out = b.mux((900, 400), 2, 8)
    b.fan_stub(data, ["YAND", "YOR", "YNOT", "YXOR"], 8, "w")
    b.stub(sel, "S10", 2, "s")
    b.stub(out, "Y", 8, "e")

    b.stub((1200, 300), "Y", 8, "w")
    return b


def build_cmp():
    b = Board("比较器")
    b.pin((120, 100), "A", width=8)
    b.pin((120, 200), "B", width=8)
    b.pin((120, 300), "S1")
    b.pin((120, 400), "S0")
    b.pin((1200, 300), "Y", facing="west", width=8, output=True)
    b.pin((1200, 450), "GT", facing="west", output=True)
    b.pin((1200, 550), "EQ", facing="west", output=True)
    b.pin((1200, 650), "LT", facing="west", output=True)

    b.stub((120, 100), "A", 8, "e")
    b.stub((120, 200), "B", 8, "e")
    b.stub((120, 300), "S1", 1, "e")
    b.stub((120, 400), "S0", 1, "e")

    pts = b.cmp((600, 300), 8)
    b.stub(pts["A"], "A", 8, "w")
    b.stub(pts["B"], "B", 8, "w")
    b.fan_stub([pts["gt"], pts["eq"], pts["lt"]], ["GT", "EQ", "LT"], 1, "e")

    for name, y in (("GT", 350), ("EQ", 450), ("LT", 550)):
        inp, out = b.ext((850, y), 1, 8)
        b.stub(inp, name, 1, "w")
        b.stub(out, name + "8", 8, "e")

    b.const((700, 650), 8, 0)
    b.stub((700, 650), "Z8", 8, "e")

    bus2, p2 = b.split((700, 800), 2, "north")
    b.wire(p2[0], (p2[0][0], p2[0][1] - 20))
    b.tunnel((p2[0][0], p2[0][1] - 20), "S0", 1, "north")
    b.wire(p2[1], (p2[1][0], p2[1][1] - 40))
    b.tunnel((p2[1][0], p2[1][1] - 40), "S1", 1, "north")
    b.wire(bus2, (bus2[0], bus2[1] + 20))
    b.tunnel((bus2[0], bus2[1] + 20), "S10", 2, "south")

    data, sel, out = b.mux((1050, 400), 2, 8)
    b.fan_stub(data, ["GT8", "EQ8", "LT8", "Z8"], 8, "w")
    b.stub(sel, "S10", 2, "s")
    b.stub(out, "Y", 8, "e")

    b.stub((1200, 300), "Y", 8, "w")
    b.stub((1200, 450), "GT", 1, "w")
    b.stub((1200, 550), "EQ", 1, "w")
    b.stub((1200, 650), "LT", 1, "w")
    return b


def build_alu():
    b = Board("ALU 8位（带比较器）")
    b.pin((120, 100), "A", width=8)
    b.pin((120, 250), "B", width=8)
    b.pin((120, 400), "S3")
    b.pin((120, 450), "S2")
    b.pin((120, 500), "S1")
    b.pin((120, 550), "S0")
    b.pin((120, 600), "Cin")
    b.pin((1580, 450), "S", facing="west", width=8, output=True)
    b.pin((1580, 650), "SF", facing="west", output=True)
    b.pin((1580, 750), "ZF", facing="west", output=True)
    b.pin((1580, 850), "OF", facing="west", output=True)
    b.pin((1580, 950), "CF", facing="west", output=True)

    # A：分线取低 3 位；分线器 8 个位口必须全部接负载
    b.wire((120, 100), (300, 100))
    b.wire((300, 100), (300, 80))
    b.tunnel((300, 80), "A", 8, "north")
    _, bits_a = b.split((300, 100), 8, "south")
    b.fan_bits(bits_a, "a")
    b.gate_io("OR Gate", (600, 150), 5, 1,
              [f"a{i}" for i in range(3, 8)], "unusedA")

    # B：直接进隧道
    b.wire((120, 250), (160, 250))
    b.tunnel((160, 250), "B", 8, "east")

    b.stub((120, 400), "S3", 1, "e")
    b.stub((120, 450), "S2", 1, "e")
    b.stub((120, 500), "S1", 1, "e")
    b.stub((120, 550), "S0", 1, "e")
    b.stub((120, 600), "Cin", 1, "e")

    # S32 = {S3,S2}
    bus, p = b.split((380, 700), 2, "north")
    b.wire(p[0], (p[0][0], p[0][1] - 20))
    b.tunnel((p[0][0], p[0][1] - 20), "S2", 1, "north")
    b.wire(p[1], (p[1][0], p[1][1] - 40))
    b.tunnel((p[1][0], p[1][1] - 40), "S3", 1, "north")
    b.wire(bus, (bus[0], bus[1] + 20))
    b.tunnel((bus[0], bus[1] + 20), "S32", 2, "south")

    # S10 = {S1,S0}
    bus, p = b.split((500, 700), 2, "north")
    b.wire(p[0], (p[0][0], p[0][1] - 20))
    b.tunnel((p[0][0], p[0][1] - 20), "S0", 1, "north")
    b.wire(p[1], (p[1][0], p[1][1] - 40))
    b.tunnel((p[1][0], p[1][1] - 40), "S1", 1, "north")
    b.wire(bus, (bus[0], bus[1] + 20))
    b.tunnel((bus[0], bus[1] + 20), "S10", 2, "south")

    # N3 = A[2:0]
    bus, p = b.split((620, 700), 3, "north")
    for i in range(3):
        q = (p[i][0], p[i][1] - 20 * (i + 1))
        b.wire(p[i], q)
        b.tunnel(q, f"a{i}", 1, "north")
    b.wire(bus, (bus[0], bus[1] + 20))
    b.tunnel((bus[0], bus[1] + 20), "N3", 3, "south")

    # B_eff：INC/NEC 时把 B 置 0（S3=1,S2=0,S1=1）
    b.gate_io("NOT Gate", (600, 850), 1, 1, ["S2"], "nS2")
    b.gate_io("NOT Gate", (600, 900), 1, 1, ["S3"], "nS3")
    b.gate_io("AND Gate", (750, 850), 3, 1, ["S3", "nS2", "S1"], "ZB")
    b.const((750, 950), 8, 0)
    b.stub((750, 950), "Z8", 8, "e")
    data, sel, out = b.mux((800, 250), 1, 8)
    b.fan_stub(data, ["B", "Z8"], 8, "w")
    b.stub(sel, "ZB", 1, "s")
    b.stub(out, "BEFF", 8, "e")

    # 四个功能模块（2×2，间距收紧）
    add = b.sub("8位可控加减器", (900, 450), ADD8_APP.offsets())
    for key, lab, w in (("A", "A", 8), ("B", "BEFF", 8),
                        ("Sub", "S0", 1), ("Cin", "Cin", 1)):
        b.stub(add[key], lab, w, "w")
    for key, lab, w in (("S", "YAR", 8), ("Cout", "COUT", 1),
                        ("OF", "OFAR", 1)):
        b.stub(add[key], lab, w, "e")

    sh = b.sub("移位器", (1170, 450), SHIFT_APP.offsets())
    b.stub(sh["X"], "B", 8, "w")
    b.stub(sh["N"], "N3", 3, "w")
    b.stub(sh["S1"], "S1", 1, "w")
    b.stub(sh["S0"], "S0", 1, "w")
    b.stub(sh["Y"], "YSH", 8, "e")
    b.stub(sh["SOL"], "SOL", 1, "e")

    lg = b.sub("逻辑运算器", (900, 700), LOGIC_APP.offsets())
    b.stub(lg["A"], "A", 8, "w")
    b.stub(lg["B"], "B", 8, "w")
    b.stub(lg["S1"], "S1", 1, "w")
    b.stub(lg["S0"], "S0", 1, "w")
    b.stub(lg["Y"], "YLO", 8, "e")

    cp = b.sub("比较器", (1170, 700), CMP_APP.offsets())
    b.stub(cp["A"], "A", 8, "w")
    b.stub(cp["B"], "B", 8, "w")
    b.stub(cp["S1"], "S1", 1, "w")
    b.stub(cp["S0"], "S0", 1, "w")
    b.stub(cp["Y"], "YCM", 8, "e")
    b.stub(cp["GT"], "GT", 1, "e")
    b.stub(cp["EQ"], "EQ", 1, "e")
    b.stub(cp["LT"], "LT", 1, "e")

    # 结果 4 选 1
    data, sel, out = b.mux((1440, 450), 2, 8)
    b.fan_stub(data, ["YSH", "YCM", "YAR", "YLO"], 8, "w")
    b.stub(sel, "S32", 2, "s")
    b.stub(out, "S", 8, "e")

    # S 分线：ZF 用 8 输入或非；SF = S7
    b.wire((1440, 630), (1440, 650))
    b.tunnel((1440, 630), "S", 8, "north")
    _, bits_s = b.split((1440, 650), 8, "south")
    b.fan_bits(bits_s, "s")

    # CF 4 选 1
    data, sel, out = b.mux((1440, 900), 2, 1)
    b.fan_stub(data, ["SOL", "LT", "COUT", "zero1"], 1, "w")
    b.stub(sel, "S32", 2, "s")
    b.stub(out, "CF", 1, "e")

    b.const((1250, 950), 1, 0)
    b.stub((1250, 950), "zero1", 1, "e")

    # ZF：结果全 0 或比较相等
    b.gate_io("OR Gate", (1100, 1000), 8, 1, [f"s{i}" for i in range(8)], "ORZ")
    b.gate_io("NOT Gate", (1250, 1000), 1, 1, ["ORZ"], "Z")
    b.gate_io("AND Gate", (1250, 1100), 2, 1, ["nS3", "S2"], "CMP")
    data, sel, out = b.mux((1440, 1000), 1, 1)
    b.fan_stub(data, ["Z", "EQ"], 1, "w")
    b.stub(sel, "CMP", 1, "s")
    b.stub(out, "ZF", 1, "e")

    b.stub((1580, 450), "S", 8, "w")
    b.stub((1580, 650), "s7", 1, "w")
    b.stub((1580, 750), "ZF", 1, "w")
    b.stub((1580, 850), "OFAR", 1, "w")
    b.stub((1580, 950), "CF", 1, "w")
    return b


FA4_OFF = None  # 运行时由 main 赋值


# ---------------------------------------------------------------- 组装

def extract_circuit(src: str, name: str) -> str:
    start = src.index(f'<circuit name="{name}">')
    end = src.index("</circuit>", start) + len("</circuit>")
    return src[start:end]


def main():
    ap = argparse.ArgumentParser(description="实验3 8位 ALU 生成器（2.15.0.2）")
    ap.add_argument("--src", default="实验2 构建加法器.circ",
                    help="实验2 工程（建议在实验目录下运行）")
    ap.add_argument("--out", default="实验3 ALU设计.circ")
    args = ap.parse_args()

    global FA4_OFF
    src = open(args.src, encoding="utf-8").read()
    FA4_OFF = {"A0": (-80, -130), "A1": (-80, -100), "A2": (-80, -70),
               "A3": (-80, -40), "B0": (-80, 0), "B1": (-80, 30),
               "B2": (-80, 60), "B3": (-80, 90), "C0": (-80, 125),
               "S0": (80, -130), "S1": (80, -100), "S2": (80, -70),
               "S3": (80, -40), "C4": (80, 0)}

    blocks = {
        "8位可控加减器": (build_add8(), ADD8_APP),
        "移位器": (build_shifter(), SHIFT_APP),
        "逻辑运算器": (build_logic(), LOGIC_APP),
        "比较器": (build_cmp(), CMP_APP),
        "ALU 8位（带比较器）": (build_alu(), None),
    }

    errs = []
    for name, (b, _) in blocks.items():
        errs += [f"{name}: {e}" for e in b.check()]
    if errs:
        print("自检失败，未写文件：")
        for e in errs:
            print("  " + e)
        return 1

    head = src.split("<circuit name=")[0]
    head = head.replace('<main name="8位串行加法器验证电路"/>',
                        '<main name="ALU 8位（带比较器）"/>')

    out = [head]
    for name in ("半加器", "全加器", "4位全加器"):
        out.append(extract_circuit(src, name))
    for name, (b, app) in blocks.items():
        out.append(f'  <circuit name="{name}">')
        out.append(b.to_body())
        if app:
            out.append(app.to_xml())
        out.append("  </circuit>")
    out.append("</project>")
    text = "\n".join(out) + "\n"
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("已写", args.out, len(text), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
