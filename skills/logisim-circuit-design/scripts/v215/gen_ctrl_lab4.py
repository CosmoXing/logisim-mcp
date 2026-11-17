# -*- coding: utf-8 -*-
"""实验4 控制器模块（带比较器）：Logisim-ITA 2.15.0.2 生成器。

以实验3 的 ALU 工程为骨架，新增：
  Regs、PC、IR、ID、CLK 模块、S-I/B、Flag、CU 控制器、系统连接。

规格来自《实验4 控制器模块-带比较器》：
  - Regs：4×8 位寄存器，R0~R2 数据、R3 地址；写使能 = R/W·译码，CLK 沿写入；
          A/B 两个 4:1 选择器，SA/SB 选择输出。
  - PC：寄存器 + 加法器 + MUX（选常数 01 或地址偏移），TC_en 使能、RST 复位。
  - IR：16 位指令寄存器，TF 取指使能。
  - ID：bit13~15 经 3-8 译码产生 R/W、S-B/I、RM、WM、JP、JZ、JC；
        bit0~7 = S-Regs，bit8~12 = S-op。
  - CLK：2 位计数器 + 2-4 译码器 → T0~T3。
  - S-I/B：B[8] 与 4 位零扩展立即数二选一。
  - Flag：4 位寄存器（Z/C/S/O），带 en。
  - CU：PC + IR + ID 合成；跳转选择 = JP + JZ·Z + JC·C。
  - 系统：CLK/CU/Regs/S-I/B/ALU/RAM/ROM/Flag/MUX。

布局按紧凑版排布：左侧引脚 40px 间距，功能块 150~250px 间距，全部用隧道短接。

用法：
    python gen_ctrl_lab4.py [--src 实验3 ALU设计.circ] [--out 实验4 控制器模块.circ]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board215 import Appearance, Board  # noqa: E402

# ---------------------------------------------------------------- 外观

ALU_APP = Appearance(
    rect=(0, 20, 220, 340), anchor=(110, 160), label="ALU 8位（带比较器）",
    label_pos=(110, 45),
    ports=[("A", "120,100", 0, 60, 10), ("B", "120,250", 0, 110, 10),
           ("S3", "120,400", 0, 150, 8), ("S2", "120,450", 0, 185, 8),
           ("S1", "120,500", 0, 220, 8), ("S0", "120,550", 0, 255, 8),
           ("Cin", "120,600", 0, 290, 8),
           ("S", "1580,450", 220, 60, 10), ("SF", "1580,650", 220, 110, 8),
           ("ZF", "1580,750", 220, 150, 8), ("OF", "1580,850", 220, 190, 8),
           ("CF", "1580,950", 220, 230, 8)])

PC_APP = Appearance(
    rect=(0, 20, 180, 170), anchor=(90, 90), label="PC",
    label_pos=(90, 45),
    ports=[("TC_en", "120,80", 0, 30, 8), ("CLK", "120,120", 0, 60, 8),
           ("RST", "120,160", 0, 90, 8), ("Offset", "120,220", 0, 120, 10),
           ("JSel", "120,280", 0, 150, 8), ("P_addr", "1800,240", 180, 90, 10)])

IR_APP = Appearance(
    rect=(0, 20, 180, 160), anchor=(90, 90), label="IR",
    label_pos=(90, 45),
    ports=[("I-in", "120,80", 0, 30, 10), ("TF", "120,140", 0, 60, 8),
           ("CLK", "120,180", 0, 90, 8), ("RST", "120,220", 0, 120, 8),
           ("I_out", "800,160", 180, 60, 10)])

ID_APP = Appearance(
    rect=(0, 20, 200, 300), anchor=(100, 100), label="ID 译码器",
    label_pos=(100, 42),
    ports=[("X", "120,80", 0, 30, 8), ("Y", "120,140", 0, 60, 8),
           ("Z", "120,200", 0, 90, 8),
           ("R/W", "1050,80", 200, 30, 8), ("S-B/I", "1050,160", 200, 70, 8),
           ("RM", "1050,240", 200, 110, 8), ("WM", "1050,320", 200, 150, 8),
           ("JP", "1050,400", 200, 190, 8), ("JZ", "1050,480", 200, 230, 8),
           ("JC", "1050,560", 200, 270, 8)])

REGS_APP = Appearance(
    rect=(0, 20, 220, 200), anchor=(110, 90), label="Regs 寄存器组",
    label_pos=(110, 45),
    ports=[("Data", "120,80", 0, 30, 10), ("R/W", "120,140", 0, 60, 8),
           ("CLK", "120,180", 0, 90, 8), ("C-Reg", "120,220", 0, 120, 8),
           ("SA", "120,300", 0, 150, 8), ("SB", "120,340", 0, 180, 8),
           ("A", "1450,140", 220, 60, 10), ("B", "1450,380", 220, 120, 10)])

CLK_APP = Appearance(
    rect=(0, 20, 160, 190), anchor=(80, 65), label="CLK 模块",
    label_pos=(80, 40),
    ports=[("CLK", "120,120", 0, 30, 8), ("RST", "120,180", 0, 60, 8),
           ("T0", "1150,100", 160, 25, 8), ("T1", "1150,160", 160, 65, 8),
           ("T2", "1150,220", 160, 105, 8), ("T3", "1150,280", 160, 145, 8)])

SIB_APP = Appearance(
    rect=(0, 20, 180, 120), anchor=(90, 60), label="S-I/B",
    label_pos=(90, 38),
    ports=[("B", "120,80", 0, 30, 10), ("I", "120,160", 0, 60, 8),
           ("sgnl", "120,240", 0, 90, 8), ("Out", "950,120", 180, 60, 10)])

FLAG_APP = Appearance(
    rect=(0, 20, 180, 160), anchor=(90, 75), label="Flag",
    label_pos=(90, 42),
    ports=[("D", "120,80", 0, 30, 10), ("en", "120,140", 0, 60, 8),
           ("CLK", "120,180", 0, 90, 8), ("RST", "120,220", 0, 120, 8),
           ("Q", "800,160", 180, 60, 10)])

CU_APP = Appearance(
    rect=(0, 20, 320, 540), anchor=(160, 200), label="CU 控制器",
    label_pos=(160, 45),
    ports=[("RST", "120,80", 0, 60, 8), ("TC", "120,120", 0, 100, 8),
           ("TF", "120,160", 0, 140, 8), ("I-in", "120,220", 0, 200, 10),
           ("Offset", "120,320", 0, 300, 10), ("Z", "120,400", 0, 340, 8),
           ("C", "120,440", 0, 360, 8),
           ("addr", "1350,80", 320, 60, 10), ("R/W", "1350,140", 320, 100, 8),
           ("S-B/I", "1350,180", 320, 140, 8), ("RM", "1350,220", 320, 180, 8),
           ("WM", "1350,260", 320, 220, 8), ("S-op", "1350,300", 320, 260, 8),
           ("S-Regs", "1350,360", 320, 320, 10), ("JP", "1350,420", 320, 380, 8),
           ("JZ", "1350,460", 320, 420, 8), ("JC", "1350,500", 320, 460, 8),
           ("I-out", "1350,560", 320, 500, 10)])


def gnd(b, port, side="w"):
    b.stub(port, "gnd", 1, side)


def wire_reg(b, r, d_lab, en_lab, width, q_lab, clr_lab=None):
    """寄存器的干净引线：D/EN/CLK/CLR 错开，CS/PRESET 悬空（默认使能）。"""
    b.lead(r["D"], d_lab, width, "w", 70)
    p = r["en"]
    b.wire(p, (p[0] - 40, p[1]))
    b.wire((p[0] - 40, p[1]), (p[0] - 40, p[1] - 40))
    b.tunnel((p[0] - 40, p[1] - 40), en_lab, 1, "north")
    p = r["clk"]
    b.wire(p, (p[0], p[1] + 40))
    b.tunnel((p[0], p[1] + 40), "CLK", 1, "south")
    if clr_lab:
        p = r["clr"]
        b.wire(p, (p[0], p[1] + 40))
        b.wire((p[0], p[1] + 40), (p[0] + 80, p[1] + 40))
        b.tunnel((p[0] + 80, p[1] + 40), clr_lab, 1, "east")
    b.lead(r["Q"], q_lab, width, "e", 60)


# ---------------------------------------------------------------- 子电路

def build_regs():
    b = Board("Regs")
    b.pin((120, 80), "Data", width=8)
    b.pin((120, 140), "R/W")
    b.pin((120, 180), "CLK")
    b.pin((120, 220), "C-Reg", width=2)
    b.pin((120, 300), "SA", width=2)
    b.pin((120, 340), "SB", width=2)
    b.pin((1450, 140), "A", facing="west", width=8, output=True)
    b.pin((1450, 380), "B", facing="west", width=8, output=True)

    b.lead((120, 80), "Data", 8, "e")
    b.lead((120, 140), "RW", 1, "e")
    b.lead((120, 180), "CLK", 1, "e")
    b.lead((120, 220), "CREG", 2, "e")
    b.lead((120, 300), "SA", 2, "e")
    b.lead((120, 340), "SB", 2, "e")

    # C-Reg 拆位
    bus, bits = b.splitn((360, 260), 2, 2, [0, 1], "south")
    b.stub(bus, "CREG", 2, "n")
    b.fan_bits(bits, "c")

    # 译码
    b.gate_io("NOT Gate", (460, 380), 1, 1, ["c1"], "nc1")
    b.gate_io("NOT Gate", (460, 420), 1, 1, ["c0"], "nc0")
    for name, ins, y in (("d0", ["nc1", "nc0"], 140),
                         ("d1", ["nc1", "c0"], 260),
                         ("d2", ["c1", "nc0"], 380),
                         ("d3", ["c1", "c0"], 500)):
        b.gate_io("AND Gate", (640, y), 2, 1, ins, name)

    # 写使能 = 译码 & R/W；时钟沿由 CLK 提供（不对 CLK 做组合门控，避免边沿竞争）
    for i, y in enumerate((140, 260, 380, 500)):
        b.gate_io("AND Gate", (780, y), 2, 1, [f"d{i}", "RW"], f"e{i}")

    # 四个寄存器（120px 行距）
    for i, y in enumerate((140, 260, 380, 500)):
        r = b.register((1000, y), 8, label=f"R{i}")
        wire_reg(b, r, "Data", f"e{i}", 8, f"q{i}")

    # A / B 输出选择
    for name, sel, y in (("A", "SA", 140), ("B", "SB", 380)):
        data, s, out = b.mux((1250, y), 2, 8)
        b.fan_stub(data, ["q0", "q1", "q2", "q3"], 8, "w")
        b.lead(s, sel, 2, "s", 40)
        b.lead(out, name, 8, "e", 40)
        b.lead((1450, y), name, 8, "w")

    b.text((650, 700),
           "写使能 = 2-4 译码(C-Reg) AND R/W，由 CLK 上升沿写入；R3 作地址寄存器",
           bold=True)
    return b


FA4_OFF = {"A0": (-80, -130), "A1": (-80, -100), "A2": (-80, -70),
           "A3": (-80, -40), "B0": (-80, 0), "B1": (-80, 30),
           "B2": (-80, 60), "B3": (-80, 90), "C0": (-80, 125),
           "S0": (80, -130), "S1": (80, -100), "S2": (80, -70),
           "S3": (80, -40), "C4": (80, 0)}


def build_pc():
    b = Board("PC")
    b.pin((120, 80), "TC_en")
    b.pin((120, 120), "CLK")
    b.pin((120, 160), "RST")
    b.pin((120, 220), "Offset", width=8)
    b.pin((120, 280), "JSel")
    b.pin((1800, 240), "P_addr", facing="west", width=8, output=True)

    b.lead((120, 80), "TC", 1, "e")
    b.lead((120, 120), "CLK", 1, "e")
    b.lead((120, 160), "RST", 1, "e")
    b.lead((120, 220), "OFF", 8, "e")
    b.lead((120, 280), "JSEL", 1, "e")

    b.const((380, 380), 8, 1)
    b.stub((380, 380), "one8", 8, "e")
    b.const((380, 440), 1, 0)
    b.stub((380, 440), "gnd", 1, "e")

    data, sel, out = b.mux((600, 280), 1, 8)
    b.fan_stub(data, ["one8", "OFF"], 8, "w")
    b.lead(sel, "JSEL", 1, "s", 40)
    b.lead(out, "ADDV", 8, "e", 40)

    # 操作数拆位
    bus, bits = b.split((760, 520), 8, "south")
    b.stub(bus, "PC", 8, "n")
    b.fan_bits(bits, "p")
    bus, bits = b.split((940, 520), 8, "south")
    b.stub(bus, "ADDV", 8, "n")
    b.fan_bits(bits, "v")

    # 两个 4 位全加器串成 8 位行波进位
    low = b.sub("4位全加器", (1150, 420), FA4_OFF)
    high = b.sub("4位全加器", (1150, 740), FA4_OFF)
    for i in range(4):
        b.stub(low[f"A{i}"], f"p{i}", 1, "w")
        b.stub(low[f"B{i}"], f"v{i}", 1, "w")
        b.stub(low[f"S{i}"], f"s{i}", 1, "e")
        b.stub(high[f"A{i}"], f"p{i + 4}", 1, "w")
        b.stub(high[f"B{i}"], f"v{i + 4}", 1, "w")
        b.stub(high[f"S{i}"], f"s{i + 4}", 1, "e")
    b.stub(low["C0"], "gnd", 1, "w")
    b.stub(low["C4"], "c4", 1, "e")
    b.stub(high["C0"], "c4", 1, "w")

    # 和位拼回 8 位
    bus, bits = b.split((1500, 980), 8, "south")
    b.stub(bus, "PCN", 8, "n")
    for i, p in enumerate(bits):
        q = (p[0], p[1] + 30 + 30 * i)
        b.wire(p, q)
        b.tunnel(q, f"s{i}", 1, "south")

    r = b.register((1600, 240), 8, label="PC")
    wire_reg(b, r, "PCN", "TC", 8, "PC", clr_lab="RST")
    b.lead((1800, 240), "PC", 8, "w")

    b.text((800, 1080), "顺序：JSel=0 加 1；跳转：JSel=1 加 Offset", bold=True)
    return b


def build_ir():
    b = Board("IR")
    b.pin((120, 80), "I-in", width=16)
    b.pin((120, 140), "TF")
    b.pin((120, 180), "CLK")
    b.pin((120, 220), "RST")
    b.pin((800, 160), "I_out", facing="west", width=16, output=True)

    b.lead((120, 80), "IIN", 16, "e")
    b.lead((120, 140), "TF", 1, "e")
    b.lead((120, 180), "CLK", 1, "e")
    b.lead((120, 220), "RST", 1, "e")

    r = b.register((600, 160), 16, label="IR")
    wire_reg(b, r, "IIN", "TF", 16, "IOUT", clr_lab="RST")
    b.lead((800, 160), "IOUT", 16, "w")
    return b


def build_id():
    b = Board("ID")
    b.pin((120, 80), "X")
    b.pin((120, 140), "Y")
    b.pin((120, 200), "Z")
    for name, y in (("R/W", 80), ("S-B/I", 160), ("RM", 240), ("WM", 320),
                    ("JP", 400), ("JZ", 480), ("JC", 560)):
        b.pin((1050, y), name, facing="west", output=True)

    b.stub((120, 80), "X", 1, "e")
    b.stub((120, 140), "Y", 1, "e")
    b.stub((120, 200), "Z", 1, "e")

    b.gate_io("NOT Gate", (380, 420), 1, 1, ["X"], "nX")
    b.gate_io("NOT Gate", (380, 460), 1, 1, ["Y"], "nY")
    b.gate_io("NOT Gate", (380, 500), 1, 1, ["Z"], "nZ")

    mins = [("m0", ["nX", "nY", "nZ"]), ("m1", ["nX", "nY", "Z"]),
            ("m2", ["nX", "Y", "nZ"]), ("m3", ["nX", "Y", "Z"]),
            ("m4", ["X", "nY", "nZ"]), ("m5", ["X", "nY", "Z"]),
            ("m6", ["X", "Y", "nZ"]), ("m7", ["X", "Y", "Z"])]
    for i, (name, ins) in enumerate(mins):
        b.gate_io("AND Gate", (620, 80 + 80 * i), 3, 1, ins, name)

    b.gate_io("OR Gate", (830, 160), 3, 1, ["m0", "m1", "m3"], "RW")
    b.gate_io("OR Gate", (830, 300), 4, 1, ["m1", "m4", "m5", "m6"], "SBI")

    for name, y in (("RW", 80), ("SBI", 160), ("m3", 240), ("m2", 320),
                    ("m4", 400), ("m5", 480), ("m6", 560)):
        b.stub((1050, y), name, 1, "w")

    b.text((650, 760), "000 RW / 001 RW+SBI / 010 WM / 011 RW+RM / "
                       "100 JP / 101 JZ / 110 JC / 111 无", bold=True)
    return b


def build_clk():
    b = Board("CLK 模块")
    b.pin((120, 120), "CLK")
    b.pin((120, 180), "RST")
    for i, y in enumerate((100, 160, 220, 280)):
        b.pin((1150, y), f"T{i}", facing="west", output=True)

    b.lead((120, 120), "CLK", 1, "e")
    b.lead((120, 180), "RST", 1, "e")

    b.const((300, 560), 1, 1)
    b.stub((300, 560), "ONE", 1, "e")

    # 2 位同步计数器：Q0' = ~Q0，Q1' = Q1 xor Q0（1 位寄存器实现）
    r0 = b.register((480, 260), 1, label="Q0")
    wire_reg(b, r0, "nq0", "ONE", 1, "q0", clr_lab="RST")

    r1 = b.register((700, 260), 1, label="Q1")
    wire_reg(b, r1, "d1", "ONE", 1, "q1", clr_lab="RST")

    b.gate_io("NOT Gate", (480, 380), 1, 1, ["q0"], "nq0")
    b.gate_io("NOT Gate", (480, 430), 1, 1, ["q1"], "nq1")
    b.gate_io("XOR Gate", (480, 480), 2, 1, ["q1", "q0"], "d1")

    # 2-4 译码
    for name, ins, y in (("T0", ["nq1", "nq0"], 160),
                         ("T1", ["nq1", "q0"], 260),
                         ("T2", ["q1", "nq0"], 360),
                         ("T3", ["q1", "q0"], 460)):
        b.gate_io("AND Gate", (1000, y), 2, 1, ins, name)

    for i, y in enumerate((100, 160, 220, 280)):
        b.stub((1150, y), f"T{i}", 1, "w")

    b.text((650, 650), "2 位同步计数器 + 门级 2-4 译码器 → T0~T3", bold=True)
    return b


def build_sib():
    b = Board("S-I/B")
    b.pin((120, 80), "B", width=8)
    b.pin((120, 160), "I", width=4)
    b.pin((120, 240), "sgnl")
    b.pin((950, 120), "Out", facing="west", width=8, output=True)

    b.lead((120, 80), "B", 8, "e")
    b.lead((120, 160), "I0", 4, "e")
    b.lead((120, 240), "sgnl", 1, "e")

    inp, out = b.ext((450, 160), 4, 8)
    b.stub(inp, "I0", 4, "w")
    b.stub(out, "I8", 8, "e")

    data, sel, res = b.mux((750, 120), 1, 8)
    b.fan_stub(data, ["B", "I8"], 8, "w")
    b.lead(sel, "sgnl", 1, "s", 40)
    b.lead(res, "OUT", 8, "e", 40)
    b.lead((950, 120), "OUT", 8, "w")

    b.text((600, 340), "sgnl=0 选 B 通道；sgnl=1 选 4 位立即数（零扩展）", bold=True)
    return b


def build_flag():
    b = Board("Flag")
    b.pin((120, 80), "D", width=4)
    b.pin((120, 140), "en")
    b.pin((120, 180), "CLK")
    b.pin((120, 220), "RST")
    b.pin((800, 160), "Q", facing="west", width=4, output=True)

    b.lead((120, 80), "FD", 4, "e")
    b.lead((120, 140), "FEN", 1, "e")
    b.lead((120, 180), "CLK", 1, "e")
    b.lead((120, 220), "RST", 1, "e")

    r = b.register((600, 160), 4, label="Flag")
    wire_reg(b, r, "FD", "FEN", 4, "FQ", clr_lab="RST")
    b.lead((800, 160), "FQ", 4, "w")

    b.text((600, 380), "Q = {O,S,C,Z}，供 JZ/JC 使用", bold=True)
    return b


def build_cu():
    b = Board("CU 控制器")
    b.pin((120, 80), "RST")
    b.pin((120, 120), "TC")
    b.pin((120, 160), "TF")
    b.pin((120, 220), "I-in", width=16)
    b.pin((120, 320), "Offset", width=8)
    b.pin((120, 400), "Z")
    b.pin((120, 440), "C")
    for name, y, w in (("addr", 80, 8), ("R/W", 140, 1), ("S-B/I", 180, 1),
                       ("RM", 220, 1), ("WM", 260, 1), ("S-op", 300, 5),
                       ("S-Regs", 360, 8), ("JP", 420, 1), ("JZ", 460, 1),
                       ("JC", 500, 1), ("I-out", 560, 16)):
        b.pin((1350, y), name, facing="west", width=w, output=True)

    b.lead((120, 80), "RST", 1, "e")
    b.lead((120, 120), "TC", 1, "e")
    b.lead((120, 160), "TF", 1, "e")
    b.lead((120, 220), "IIN", 16, "e")
    b.lead((120, 320), "OFF", 8, "e")
    b.lead((120, 400), "FZ", 1, "e")
    b.lead((120, 440), "FC", 1, "e")

    b.const((300, 800), 1, 1)
    b.stub((300, 800), "ONE", 1, "e")
    b.gate_io("NOT Gate", (300, 740), 1, 1, ["RST"], "nRST")

    ir = b.sub("IR", (450, 250), IR_APP.offsets())
    b.stub(ir["I-in"], "IIN", 16, "w")
    b.stub(ir["TF"], "nRST", 1, "w")
    b.stub(ir["CLK"], "TF", 1, "w")
    b.stub(ir["RST"], "RST", 1, "w")
    b.stub(ir["I_out"], "IR16", 16, "e")

    pc = b.sub("PC", (450, 600), PC_APP.offsets())
    b.stub(pc["TC_en"], "ONE", 1, "w")
    b.stub(pc["CLK"], "TC", 1, "w")
    b.stub(pc["RST"], "RST", 1, "w")
    b.stub(pc["Offset"], "OFF", 8, "w")
    b.stub(pc["JSel"], "JMP", 1, "w")
    b.stub(pc["P_addr"], "PADDR", 8, "e")

    idx = b.sub("ID", (1000, 200), ID_APP.offsets())
    for name in ("X", "Y", "Z"):
        b.stub(idx[name], name, 1, "w")
    for name in ("R/W", "S-B/I", "RM", "WM", "JP", "JZ", "JC"):
        b.stub(idx[name], {"R/W": "RW", "S-B/I": "SBI"}.get(name, name), 1, "e")

    # 指令字段拆分：低 8 位 S-Regs，高 8 位再拆 S-op(5) + XYZ(3)
    bus, parts = b.splitn((700, 400), 2, 16, [0] * 8 + [1] * 8, "south")
    b.stub(bus, "IR16", 16, "n")
    b.wire(parts[0], (700, 460))
    b.tunnel((700, 460), "SREGS", 8, "south")
    b.wire(parts[1], (690, 520))

    sop, xyz = b.splitn((690, 520), 2, 8, [0] * 5 + [1] * 3, "south")[1]
    b.wire(sop, (690, 560))
    b.tunnel((690, 560), "SOP5", 5, "south")
    b.wire(xyz, (680, 620))

    # bit13→Z、bit14→Y、bit15→X（指令高 3 位按 X Y Z 读）
    _, xyz3 = b.splitn((680, 620), 3, 3, [0, 1, 2], "south")
    for i, name in enumerate(("Z", "Y", "X")):
        q = (xyz3[i][0], xyz3[i][1] + 30 + 40 * i)
        b.wire(xyz3[i], q)
        b.tunnel(q, name, 1, "south")

    # 跳转选择 = JP + JZ·Z + JC·C
    b.gate_io("AND Gate", (820, 450), 2, 1, ["JZ", "FZ"], "jz")
    b.gate_io("AND Gate", (820, 500), 2, 1, ["JC", "FC"], "jc")
    b.gate_io("OR Gate", (1000, 475), 2, 1, ["jz", "jc"], "orj")
    b.gate_io("OR Gate", (1150, 450), 2, 1, ["orj", "JP"], "JMP")

    for name, y, w in (("PADDR", 80, 8), ("RW", 140, 1), ("SBI", 180, 1),
                       ("RM", 220, 1), ("WM", 260, 1), ("SOP5", 300, 5),
                       ("SREGS", 360, 8), ("JP", 420, 1), ("JZ", 460, 1),
                       ("JC", 500, 1), ("IR16", 560, 16)):
        b.lead((1350, y), name, w, "w")

    b.text((900, 800), "CU = PC + IR + ID；TF=T0 取指，TC=T3 修改 PC", bold=True)
    return b


def build_system():
    b = Board("系统连接")
    b.pin((120, 100), "CLK")
    b.pin((120, 140), "RST")
    for name, y, w in (("PADDR", 100, 8), ("IRIN", 160, 16), ("T0", 220, 1),
                       ("T1", 260, 1), ("T2", 300, 1), ("T3", 340, 1),
                       ("RA", 400, 8), ("RB", 460, 8), ("BOP", 520, 8),
                       ("ALUY", 580, 8), ("REGD", 640, 8), ("FQ4", 700, 4),
                       ("RAMQ", 760, 8), ("IRQ", 820, 16)):
        b.pin((1850, y), name, facing="west", width=w, output=True)

    b.lead((120, 100), "CLK", 1, "e")
    b.lead((120, 140), "RST", 1, "e")

    b.text((600, 60), "实验4 控制器模块（Logisim-ITA 2.15.0.2）", bold=True)

    # CLK 模块
    clk = b.sub("CLK 模块", (300, 250), CLK_APP.offsets())
    b.stub(clk["CLK"], "CLK", 1, "w")
    b.stub(clk["RST"], "RST", 1, "w")
    for i in range(4):
        b.stub(clk[f"T{i}"], f"T{i}", 1, "e")

    # ROM
    rom = b.rom((650, 250), 3, 16,
                "4001 8030 15f0 4042 8034 15f0 1084 8038")
    b.stub(rom["A"], "PA3", 3, "w")
    b.stub(rom["D"], "IRIN", 16, "e")
    gnd(b, rom["cs"], "s")

    # CU
    cu = b.sub("CU 控制器", (1050, 300), CU_APP.offsets())
    b.stub(cu["RST"], "RST", 1, "w")
    b.stub(cu["TC"], "T3", 1, "w")
    b.stub(cu["TF"], "T0", 1, "w")
    b.stub(cu["I-in"], "IRIN", 16, "w")
    b.stub(cu["Offset"], "IROFF", 8, "w")
    b.lead(cu["Z"], "FZ", 1, "w", 80)
    b.lead(cu["C"], "FC", 1, "w", 140)
    b.stub(cu["addr"], "PADDR", 8, "e")
    b.stub(cu["R/W"], "CRW", 1, "e")
    b.stub(cu["S-B/I"], "SBI", 1, "e")
    b.stub(cu["RM"], "RM", 1, "e")
    b.stub(cu["WM"], "WM", 1, "e")
    b.stub(cu["S-op"], "SOP5", 5, "e")
    b.stub(cu["S-Regs"], "SREGS", 8, "e")
    b.stub(cu["JP"], "JP", 1, "e")
    b.stub(cu["JZ"], "JZ", 1, "e")
    b.stub(cu["JC"], "JC", 1, "e")
    b.stub(cu["I-out"], "IRQ", 16, "e")

    # Regs
    regs = b.sub("Regs", (500, 650), REGS_APP.offsets())
    b.stub(regs["Data"], "REGD", 8, "w")
    b.stub(regs["R/W"], "CRW", 1, "w")
    b.stub(regs["CLK"], "T3", 1, "w")
    b.stub(regs["C-Reg"], "CREG", 2, "w")
    b.stub(regs["SA"], "SA", 2, "w")
    b.stub(regs["SB"], "SB", 2, "w")
    b.stub(regs["A"], "RA", 8, "e")
    b.stub(regs["B"], "RB", 8, "e")

    # S-I/B
    sib = b.sub("S-I/B", (850, 700), SIB_APP.offsets())
    b.stub(sib["B"], "RB", 8, "w")
    b.stub(sib["I"], "IMM4", 4, "w")
    b.stub(sib["sgnl"], "SBI", 1, "w")
    b.stub(sib["Out"], "BOP", 8, "e")

    # ALU
    alu = b.sub("ALU 8位（带比较器）", (1230, 860), ALU_APP.offsets())
    b.stub(alu["A"], "RA", 8, "w")
    b.stub(alu["B"], "BOP", 8, "w")
    for name in ("S3", "S2", "S1", "S0", "Cin"):
        b.stub(alu[name], name.upper(), 1, "w")
    b.stub(alu["S"], "ALUY", 8, "e")
    b.stub(alu["SF"], "SF", 1, "e")
    b.stub(alu["ZF"], "ZF", 1, "e")
    b.stub(alu["OF"], "OF", 1, "e")
    b.stub(alu["CF"], "CF", 1, "e")

    # Flag
    flag = b.sub("Flag", (1560, 680), FLAG_APP.offsets())
    b.stub(flag["D"], "FD4", 4, "w")
    b.lead(flag["en"], "ONE", 1, "w", 80)
    b.stub(flag["CLK"], "T3", 1, "w")
    b.stub(flag["RST"], "RST", 1, "w")
    b.stub(flag["Q"], "FQ4", 4, "e")

    # RAM
    ram = b.ram((750, 1000), 4, 8)
    b.stub(ram["A"], "RA4", 4, "w")
    b.lead(ram["D"], "RB", 8, "w", 80)
    b.stub(ram["Q"], "RAMQ", 8, "e")
    for pin, lab, dy in (("str", "WM", 40), ("cs", "gnd", 80),
                         ("clk", "T3", 40), ("oe", "ONE", 100),
                         ("clr", "gnd", 60)):
        p = ram[pin]
        b.wire(p, (p[0], p[1] + dy))
        b.tunnel((p[0], p[1] + dy), lab, 1, "south")

    # 写回选择：RM=0 选 ALU Y，RM=1 选 RAM Q
    data, sel, out = b.mux((950, 900), 1, 8)
    b.fan_stub(data, ["ALUY", "RAMQ"], 8, "w")
    b.lead(sel, "RM", 1, "s", 40)
    b.lead(out, "REGD", 8, "e", 40)

    # 常量
    b.const((300, 1100), 1, 1)
    b.stub((300, 1100), "ONE", 1, "e")
    b.const((300, 1150), 1, 0)
    b.stub((300, 1150), "gnd", 1, "e")

    # PADDR 取低 3 位给 ROM
    bus, parts = b.splitn((1350, 220), 2, 8, [0, 0, 0, 1, 1, 1, 1, 1], "south")
    b.stub(bus, "PADDR", 8, "n")
    b.wire(parts[0], (1350, 280))
    b.tunnel((1350, 280), "PA3", 3, "south")

    # S-Regs 拆 C-Reg / SA / SB（bit0-1 留作立即数低位）
    bus, parts = b.splitn((1310, 520), 4, 8, [0, 0, 1, 1, 2, 2, 3, 3], "south")
    b.stub(bus, "SREGS", 8, "n")
    for i, name in enumerate(("CREG", "SA", "SB"), start=1):
        q = (parts[i][0], parts[i][1] + 30 + 40 * (i - 1))
        b.wire(parts[i], q)
        b.tunnel(q, name, 2, "south")

    # IR 低 8 位 = Offset / 立即数来源
    bus, parts = b.splitn((1350, 1140), 2, 16, [0] * 8 + [1] * 8, "south")
    b.stub(bus, "IRQ", 16, "n")
    b.wire(parts[0], (1350, 1200))
    b.tunnel((1350, 1200), "IROFF", 8, "south")

    bus, parts = b.splitn((1350, 1300), 2, 8, [0, 0, 0, 0, 1, 1, 1, 1], "south")
    b.stub(bus, "IROFF", 8, "n")
    b.wire(parts[0], (1350, 1360))
    b.tunnel((1350, 1360), "IMM4", 4, "south")

    # S-op 拆 S3..S0 / Cin
    bus, parts = b.splitn((1450, 320), 5, 5, [0, 1, 2, 3, 4], "south")
    b.stub(bus, "SOP5", 5, "n")
    for i, name in enumerate(("CIN", "S0", "S1", "S2", "S3")):
        q = (parts[i][0], parts[i][1] + 30 + 40 * i)
        b.wire(parts[i], q)
        b.tunnel(q, name, 1, "south")

    # 标志位合并 / 拆分
    bus, parts = b.splitn((1480, 850), 4, 4, [0, 1, 2, 3], "south")
    b.stub(bus, "FD4", 4, "n")
    for i, name in enumerate(("ZF", "CF", "SF", "OF")):
        q = (parts[i][0], parts[i][1] + 30 + 40 * i)
        b.wire(parts[i], q)
        b.tunnel(q, name, 1, "south")

    bus, parts = b.splitn((1600, 900), 4, 4, [0, 1, 2, 3], "south")
    b.stub(bus, "FQ4", 4, "n")
    for i, name in enumerate(("FZ", "FC", "FS", "FO")):
        q = (parts[i][0], parts[i][1] + 30 + 40 * i)
        b.wire(parts[i], q)
        b.tunnel(q, name, 1, "south")

    # RA 取低 4 位给 RAM
    bus, parts = b.splitn((500, 900), 2, 8, [0, 0, 0, 0, 1, 1, 1, 1], "south")
    b.stub(bus, "RA", 8, "n")
    b.wire(parts[0], (500, 960))
    b.tunnel((500, 960), "RA4", 4, "south")

    # 观测引脚
    for name, y, w in (("PADDR", 100, 8), ("IRIN", 160, 16), ("T0", 220, 1),
                       ("T1", 260, 1), ("T2", 300, 1), ("T3", 340, 1),
                       ("RA", 400, 8), ("RB", 460, 8), ("BOP", 520, 8),
                       ("ALUY", 580, 8), ("REGD", 640, 8), ("FQ4", 700, 4),
                       ("RAMQ", 760, 8), ("IRQ", 820, 16)):
        b.lead((1850, y), name, w, "w")

    b.text((800, 1200), "指令周期：T0 取指 → T1 译码 → T2 执行 → T3 写回/改 PC",
           bold=True)
    return b


# ---------------------------------------------------------------- 组装

def extract_circuit(src: str, name: str) -> str:
    start = src.index(f'<circuit name="{name}">')
    end = src.index("</circuit>", start) + len("</circuit>")
    return src[start:end]


def main():
    ap = argparse.ArgumentParser(description="实验4 控制器模块生成器（2.15.0.2）")
    ap.add_argument("--src", default="实验3 ALU设计.circ")
    ap.add_argument("--out", default="实验4 控制器模块.circ")
    args = ap.parse_args()

    src = open(args.src, encoding="utf-8").read()

    blocks = [
        ("Regs", build_regs(), REGS_APP),
        ("PC", build_pc(), PC_APP),
        ("IR", build_ir(), IR_APP),
        ("ID", build_id(), ID_APP),
        ("CLK 模块", build_clk(), CLK_APP),
        ("S-I/B", build_sib(), SIB_APP),
        ("Flag", build_flag(), FLAG_APP),
        ("CU 控制器", build_cu(), CU_APP),
        ("系统连接", build_system(), None),
    ]

    errs = []
    for name, board, _ in blocks:
        errs += [f"{name}: {e}" for e in board.check()]
    if errs:
        print("自检失败，未写文件：")
        for e in errs:
            print("  " + e)
        return 1

    head = src.split("<circuit name=")[0]
    head = head.replace('<main name="8位串行加法器验证电路"/>',
                        '<main name="系统连接"/>')
    head = head.replace('<main name="ALU 8位（带比较器）"/>',
                        '<main name="系统连接"/>')

    out = [head]
    for name in ("半加器", "全加器", "4位全加器", "8位可控加减器", "移位器",
                 "逻辑运算器", "比较器"):
        out.append(extract_circuit(src, name))

    # ALU：补一个紧凑外观，供系统连接使用
    alu = extract_circuit(src, "ALU 8位（带比较器）")
    if "<appear>" not in alu:
        alu = alu.replace("  </circuit>", ALU_APP.to_xml() + "\n  </circuit>")
    out.append(alu)

    for name, board, app in blocks:
        out.append(f'  <circuit name="{name}">')
        out.append(board.to_body())
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
