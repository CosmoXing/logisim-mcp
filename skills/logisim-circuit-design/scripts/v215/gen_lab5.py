# -*- coding: utf-8 -*-
"""实验5 指令分析和程序设计：Logisim-ITA 2.15.0.2 生成器。

在实验3 ALU 与实验4 控制器的基础上：
  - S-Regs 改为 C-Reg=IR[7:6]、SA=IR[5:4]、SB=IR[3:2]、4 位立即数=IR[3:0]；
  - 立即数与跳转偏移均按 4 位有符号数符号扩展；
  - 移位类 S-op 的移位数固定为 1（ALU 的 A 通道送 1）；
  - 比较器改为补码（twosComplement）比较，支持负数；
  - IR 改为 T1 沿取指（实验4 的 T0 沿会漏掉第 0 条指令）；
  - 4 片 16×16 ROM + 4 选 1 选择器，Prog[2] 切换例1~例4；
  - Regs 增加 Q0~Q3 观测输出；Flag 在跳转指令时不更新，保证连续条件跳转。

用法（在实验目录下运行）：
    python gen_lab5.py --src "实验3 ALU设计.circ" --out "实验5 指令分析.circ"
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board215 import Appearance, Board  # noqa: E402
import gen_ctrl_lab4 as L4  # noqa: E402

ALU_APP = L4.ALU_APP
PC_APP = L4.PC_APP
IR_APP = L4.IR_APP
ID_APP = L4.ID_APP
CLK_APP = L4.CLK_APP
SIB_APP = L4.SIB_APP
FLAG_APP = L4.FLAG_APP
CU_APP = L4.CU_APP

# ---------------------------------------------------------------- 程序 ROM

PROGRAMS = [
    # 例1：-8*10
    "2008 0040 20c0 0200 0244 0244 0244 1084 4038 0000 0000 0000 0000 0000 0000 0000",
    # 例2：-4/4（算术右移两次）
    "200c 0600 0600 0040 20c0 4034 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000",
    # 例3：斐波那契（PC+n）
    "2001 2041 20c0 1084 4038 15fc 0004 0058 800b 0000 0000 0000 0000 0000 0000 0000",
    # 例4：r0>r1 输出 1（2 > -3）
    "2002 204d 0884 a004 c003 2081 8002 2080 8000 0000 0000 0000 0000 0000 0000 0000",
]

# ---------------------------------------------------------------- 外观

REGS5_APP = Appearance(
    rect=(0, 20, 220, 360), anchor=(110, 90), label="Regs 寄存器组",
    label_pos=(110, 45),
    ports=[("Data", "120,80", 0, 30, 10), ("R/W", "120,140", 0, 60, 8),
           ("CLK", "120,180", 0, 90, 8), ("C-Reg", "120,220", 0, 120, 8),
           ("SA", "120,300", 0, 150, 8), ("SB", "120,340", 0, 180, 8),
           ("A", "1450,140", 220, 60, 10), ("B", "1450,380", 220, 120, 10),
           ("Q0", "1450,620", 220, 180, 10), ("Q1", "1450,700", 220, 230, 10),
           ("Q2", "1450,780", 220, 280, 10), ("Q3", "1450,860", 220, 330, 10)])


def gnd(b, port, side="s"):
    b.stub(port, "gnd", 1, side)


# ---------------------------------------------------------------- 子电路

def build_regs5():
    """实验4 Regs + Q0~Q3 观测输出。"""
    b = Board("Regs")
    b.pin((120, 80), "Data", width=8)
    b.pin((120, 140), "R/W")
    b.pin((120, 180), "CLK")
    b.pin((120, 220), "C-Reg", width=2)
    b.pin((120, 300), "SA", width=2)
    b.pin((120, 340), "SB", width=2)
    b.pin((1450, 140), "A", facing="west", width=8, output=True)
    b.pin((1450, 380), "B", facing="west", width=8, output=True)
    for i, y in enumerate((620, 700, 780, 860)):
        b.pin((1450, y), f"Q{i}", facing="west", width=8, output=True)
        b.lead((1450, y), f"q{i}", 8, "w")

    b.lead((120, 80), "Data", 8, "e")
    b.lead((120, 140), "RW", 1, "e")
    b.lead((120, 180), "CLK", 1, "e")
    b.lead((120, 220), "CREG", 2, "e")
    b.lead((120, 300), "SA", 2, "e")
    b.lead((120, 340), "SB", 2, "e")

    bus, bits = b.splitn((360, 260), 2, 2, [0, 1], "south")
    b.stub(bus, "CREG", 2, "n")
    b.fan_bits(bits, "c")

    b.gate_io("NOT Gate", (460, 380), 1, 1, ["c1"], "nc1")
    b.gate_io("NOT Gate", (460, 420), 1, 1, ["c0"], "nc0")
    for name, ins, y in (("d0", ["nc1", "nc0"], 140),
                         ("d1", ["nc1", "c0"], 260),
                         ("d2", ["c1", "nc0"], 380),
                         ("d3", ["c1", "c0"], 500)):
        b.gate_io("AND Gate", (640, y), 2, 1, ins, name)

    for i, y in enumerate((140, 260, 380, 500)):
        b.gate_io("AND Gate", (780, y), 2, 1, [f"d{i}", "RW"], f"e{i}")

    for i, y in enumerate((140, 260, 380, 500)):
        r = b.register((1000, y), 8, label=f"R{i}")
        L4.wire_reg(b, r, "Data", f"e{i}", 8, f"q{i}")

    for name, sel, y in (("A", "SA", 140), ("B", "SB", 380)):
        data, s, out = b.mux((1250, y), 2, 8)
        b.fan_stub(data, ["q0", "q1", "q2", "q3"], 8, "w")
        b.lead(s, sel, 2, "s", 40)
        b.lead(out, name, 8, "e", 40)
        b.lead((1450, y), name, 8, "w")

    b.text((650, 940),
           "写使能 = 2-4 译码(C-Reg) AND R/W；Q0~Q3 供实验5 直接观测；R3 兼作地址寄存器",
           bold=True)
    return b


def build_sib5():
    """S-I/B：4 位立即数按有符号数符号扩展（例1/2/4 的负数立即数）。"""
    b = Board("S-I/B")
    b.pin((120, 80), "B", width=8)
    b.pin((120, 160), "I", width=4)
    b.pin((120, 240), "sgnl")
    b.pin((950, 120), "Out", facing="west", width=8, output=True)

    b.lead((120, 80), "B", 8, "e")
    b.lead((120, 160), "I0", 4, "e")
    b.lead((120, 240), "sgnl", 1, "e")

    inp, out = b.ext((450, 160), 4, 8, sign=True)
    b.stub(inp, "I0", 4, "w")
    b.stub(out, "I8", 8, "e")

    data, sel, res = b.mux((750, 120), 1, 8)
    b.fan_stub(data, ["B", "I8"], 8, "w")
    b.lead(sel, "sgnl", 1, "s", 40)
    b.lead(res, "OUT", 8, "e", 40)
    b.lead((950, 120), "OUT", 8, "w")

    b.text((600, 340), "sgnl=0 选 B 通道；sgnl=1 选 4 位立即数（符号扩展）",
           bold=True)
    return b


def build_system5():
    b = Board("系统连接")
    b.pin((120, 100), "CLK")
    b.pin((120, 140), "RST")
    b.pin((120, 180), "Prog", width=2)

    outs = (("R0", 100, 8, "Q0"), ("R1", 160, 8, "Q1"),
            ("R2", 220, 8, "Q2"), ("R3", 280, 8, "Q3"),
            ("PC", 340, 8, "PADDR"), ("IR", 400, 16, "IRQ"),
            ("RAMQ", 460, 8, "RAMQ"), ("FLAGS", 520, 4, "FQ4"),
            ("RA", 580, 8, "RA"), ("RB", 640, 8, "RB"),
            ("ALUY", 700, 8, "ALUY"), ("BOP", 760, 8, "BOP"),
            ("T0", 820, 1, "T0"), ("T1", 880, 1, "T1"),
            ("T2", 940, 1, "T2"), ("T3", 1000, 1, "T3"))
    for name, y, w, _ in outs:
        b.pin((1850, y), name, facing="west", width=w, output=True)
        b.lead((1850, y), _, w, "w")

    b.lead((120, 100), "CLK", 1, "e")
    b.lead((120, 140), "RST", 1, "e")
    b.lead((120, 180), "PROG2", 2, "e")

    b.text((700, 60), "实验5 指令分析和程序设计（Logisim-ITA 2.15.0.2）",
           bold=True)

    # CLK 模块
    clk = b.sub("CLK 模块", (300, 250), CLK_APP.offsets())
    b.stub(clk["CLK"], "CLK", 1, "w")
    b.stub(clk["RST"], "RST", 1, "w")
    for i in range(4):
        b.stub(clk[f"T{i}"], f"T{i}", 1, "e")

    # 4 片程序 ROM
    for i, y in enumerate((120, 220, 320, 420)):
        rom = b.rom((800, y), 4, 16, PROGRAMS[i])
        b.stub(rom["A"], "PA4", 4, "w")
        b.stub(rom["D"], f"P{i}D", 16, "e")
        gnd(b, rom["cs"], "s")

    # 4 选 1：Prog 选择例1~例4
    data, sel, out = b.mux((1020, 80), 2, 16)
    b.fan_stub(data, ["P0D", "P1D", "P2D", "P3D"], 16, "w")
    b.lead(sel, "PROG2", 2, "s", 40)
    b.lead(out, "IRIN", 16, "e", 40)

    # CU
    cu = b.sub("CU 控制器", (1050, 300), CU_APP.offsets())
    b.stub(cu["RST"], "RST", 1, "w")
    b.stub(cu["TC"], "T3", 1, "w")
    b.stub(cu["TF"], "T1", 1, "w")          # 取指沿：T1
    b.stub(cu["I-in"], "IRIN", 16, "w")
    b.stub(cu["Offset"], "SEXT8", 8, "w")
    b.lead(cu["Z"], "FZ", 1, "w", 80)
    b.lead(cu["C"], "FC", 1, "w", 80)
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
    regs = b.sub("Regs", (500, 650), REGS5_APP.offsets())
    b.stub(regs["Data"], "REGD", 8, "w")
    b.stub(regs["R/W"], "CRW", 1, "w")
    b.stub(regs["CLK"], "T3", 1, "w")
    b.stub(regs["C-Reg"], "CREG", 2, "w")
    b.stub(regs["SA"], "SA", 2, "w")
    b.stub(regs["SB"], "SB", 2, "w")
    b.stub(regs["A"], "RA", 8, "e")
    b.stub(regs["B"], "RB", 8, "e")
    for i in range(4):
        b.lead(regs[f"Q{i}"], f"Q{i}", 8, "e", 60)

    # S-I/B
    sib = b.sub("S-I/B", (850, 700), SIB_APP.offsets())
    b.stub(sib["B"], "RB", 8, "w")
    b.stub(sib["I"], "IMM4", 4, "w")
    b.stub(sib["sgnl"], "SBI", 1, "w")
    b.stub(sib["Out"], "BOP", 8, "e")

    # ALU
    alu = b.sub("ALU 8位（带比较器）", (1230, 860), ALU_APP.offsets())
    b.stub(alu["A"], "ALUA", 8, "w")
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
    b.lead(flag["en"], "NENF", 1, "w", 80)
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

    # 写回选择：RM=0 → ALUY，RM=1 → RAMQ
    data, sel, out = b.mux((950, 900), 1, 8)
    b.fan_stub(data, ["ALUY", "RAMQ"], 8, "w")
    b.lead(sel, "RM", 1, "s", 40)
    b.lead(out, "REGD", 8, "e", 40)

    # ALU A 通道：移位类（S3S2=00）送 0x01，移位数固定为 1
    b.gate_io("NOR Gate", (860, 540), 2, 1, ["S3", "S2"], "SHIFT")
    data, sel, out = b.mux((1000, 780), 1, 8)
    b.fan_stub(data, ["RA", "ONE8"], 8, "w")
    b.lead(sel, "SHIFT", 1, "s", 40)
    b.lead(out, "ALUA", 8, "e", 40)

    # Flag 使能：跳转指令不更新标志（连续 JZ/JC 依赖同一次比较结果）
    b.gate_io("OR Gate", (1350, 540), 3, 1, ["JP", "JZ", "JC"], "ANYJMP")
    b.gate_io("NOT Gate", (1450, 540), 1, 1, ["ANYJMP"], "NENF")

    # 常量
    b.const((300, 1100), 1, 1)
    b.stub((300, 1100), "ONE", 1, "e")
    b.const((300, 1150), 1, 0)
    b.stub((300, 1150), "gnd", 1, "e")
    b.const((300, 1200), 8, 1)
    b.stub((300, 1200), "ONE8", 8, "e")

    # PC[3:0] → ROM 地址
    bus, parts = b.splitn((1350, 220), 2, 8, [0, 0, 0, 0, 1, 1, 1, 1], "south")
    b.stub(bus, "PADDR", 8, "n")
    b.wire(parts[0], (1350, 280))
    b.tunnel((1350, 280), "PA4", 4, "south")

    # S-Regs：C-Reg=bit7:6，SA=bit5:4，SB=bit3:2
    bus, parts = b.splitn((1300, 620), 4, 8, [0, 0, 1, 1, 2, 2, 3, 3], "south")
    b.stub(bus, "SREGS", 8, "n")
    for i, name in ((1, "SB"), (2, "SA"), (3, "CREG")):
        q = (parts[i][0], parts[i][1] + 30 + 40 * (i - 1))
        b.wire(parts[i], q)
        b.tunnel(q, name, 2, "south")

    # S-op 拆 S3..S0 / Cin
    bus, parts = b.splitn((1380, 320), 5, 5, [0, 1, 2, 3, 4], "south")
    b.stub(bus, "SOP5", 5, "n")
    for i, name in enumerate(("CIN", "S0", "S1", "S2", "S3")):
        q = (parts[i][0], parts[i][1] + 30 + 40 * i)
        b.wire(parts[i], q)
        b.tunnel(q, name, 1, "south")

    # IR[3:0] → 立即数 / 跳转偏移，符号扩展为 8 位
    bus, parts = b.splitn((1350, 1140), 2, 16, [0, 0, 0, 0] + [1] * 12, "south")
    b.stub(bus, "IRQ", 16, "n")
    b.wire(parts[0], (1350, 1200))
    b.tunnel((1350, 1200), "IMM4", 4, "south")

    inp, out = b.ext((1500, 1300), 4, 8, sign=True)
    b.stub(inp, "IMM4", 4, "w")
    b.stub(out, "SEXT8", 8, "e")

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

    # RA[3:0] → RAM 地址
    bus, parts = b.splitn((500, 940), 2, 8, [0, 0, 0, 0, 1, 1, 1, 1], "south")
    b.stub(bus, "RA", 8, "n")
    b.wire(parts[0], (500, 1000))
    b.tunnel((500, 1000), "RA4", 4, "south")

    b.text((800, 1240),
           "T1 取指 → T2 译码/执行 → T3 写回、改 PC、写存储器；"
           "移位按 1 位，比较按补码", bold=True)
    return b


# ---------------------------------------------------------------- 组装

def extract_circuit(src: str, name: str) -> str:
    start = src.index(f'<circuit name="{name}">')
    end = src.index("</circuit>", start) + len("</circuit>")
    return src[start:end]


def main():
    ap = argparse.ArgumentParser(description="实验5 指令分析生成器（2.15.0.2）")
    ap.add_argument("--src", default="实验3 ALU设计.circ")
    ap.add_argument("--out", default="实验5 指令分析.circ")
    args = ap.parse_args()

    src = open(args.src, encoding="utf-8").read()

    blocks = [
        ("Regs", build_regs5(), REGS5_APP),
        ("PC", L4.build_pc(), PC_APP),
        ("IR", L4.build_ir(), IR_APP),
        ("ID", L4.build_id(), ID_APP),
        ("CLK 模块", L4.build_clk(), CLK_APP),
        ("S-I/B", build_sib5(), SIB_APP),
        ("Flag", L4.build_flag(), FLAG_APP),
        ("CU 控制器", L4.build_cu(), CU_APP),
        ("系统连接", build_system5(), None),
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
    head = head.replace('<main name="ALU 8位（带比较器）"/>',
                        '<main name="系统连接"/>')

    out = [head]
    for name in ("半加器", "全加器", "4位全加器", "8位可控加减器", "移位器",
                 "逻辑运算器"):
        out.append(extract_circuit(src, name))

    # 实验5 需要补码比较（例4：2 > -3）
    cmp_circ = extract_circuit(src, "比较器").replace(
        'name="mode" val="unsigned"', 'name="mode" val="twosComplement"')
    out.append(cmp_circ)

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
