# -*- coding: utf-8 -*-
"""实验5 指令分析：模型化全程序验证。

对 系统连接 电路逐拍驱动 CLK，按 ISA 语义在 Python 侧同步建模，
在每条指令的 T3 后比对 R0~R3、PC、IR、RAMQ、FLAGS。

覆盖：
  例1 -8*10、例2 -4/4、例3 斐波那契（PC+n）、
  例4 r0>r1 的 > / = / < 三种分支（后两种用临时 ROM 变体）。

用法（在实验目录下运行）：
    python verify_lab5.py [--circ "实验5 指令分析.circ"]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

DEFAULT_CIRC = "实验5 指令分析.circ"

P0 = [0x2008, 0x0040, 0x20C0, 0x0200, 0x0244, 0x0244, 0x0244, 0x1084,
      0x4038] + [0] * 7
P1 = [0x200C, 0x0600, 0x0600, 0x0040, 0x20C0, 0x4034] + [0] * 10
P2 = [0x2001, 0x2041, 0x20C0, 0x1084, 0x4038, 0x15FC, 0x0004, 0x0058,
      0x800B] + [0] * 7
P3 = [0x2002, 0x204D, 0x0884, 0xA004, 0xC003, 0x2081, 0x8002, 0x2080,
      0x8000] + [0] * 7
P3_EQ = [0x2002, 0x2042, 0x0884, 0xA004, 0xC003, 0x2081, 0x8002, 0x2080,
         0x8000] + [0] * 7
P3_LT = [0x200D, 0x2042, 0x0884, 0xA004, 0xC003, 0x2081, 0x8002, 0x2080,
         0x8000] + [0] * 7


def rom_text(words):
    return " ".join("%04x" % (w & 0xFFFF) for w in words)


class Cpu:
    """与电路同构的 ISA 模型。"""

    def __init__(self, rom):
        self.rom = rom
        self.regs = [0, 0, 0, 0]
        self.pc = 0
        self.ir = 0
        self.ram = [0] * 16
        self.flags = 0          # bit0 Z, bit1 C, bit2 S, bit3 O

    # ---- 单条指令的执行语义（T3 沿） ----
    def execute(self):
        ir = self.ir
        fn = (ir >> 13) & 7
        sop = (ir >> 8) & 0x1F
        sr = ir & 0xFF
        creg = (sr >> 6) & 3
        sa = (sr >> 4) & 3
        sb = (sr >> 2) & 3
        imm4 = sr & 0xF
        imm8 = imm4 if not (imm4 & 8) else imm4 + 240   # 8 位补码表示
        off = imm4 - 16 if imm4 & 8 else imm4           # 有符号偏移
        s3, s2 = (sop >> 4) & 1, (sop >> 3) & 1
        s1, s0, cin = (sop >> 2) & 1, (sop >> 1) & 1, sop & 1

        # A 通道：S3S2=00（MOV/移位）时强制 1，移位数固定 1 位
        a = 1 if (s3, s2) == (0, 0) else self.regs[sa]
        # B 通道：RW+立即数（fn=001）选符号扩展立即数；跳转不影响结果
        b = imm8 if fn == 1 else self.regs[sb]

        # ALU 的 OF 始终来自加法器
        beff = 0 if (s3, s2, s1) == (1, 0, 1) else b
        bx = beff ^ (0xFF if s0 else 0)
        total = a + bx + (cin ^ s0)
        of = int(bool((~(a ^ bx)) & (a ^ (total & 0xFF)) & 0x80))
        cout = (total >> 8) & 1

        s32 = sop >> 3
        if s32 == 0:
            if (s1, s0) == (0, 0):
                y, cf = b, 0
            elif (s1, s0) == (0, 1):
                y, cf = (b << 1) & 0xFF, (b >> 7) & 1
            elif (s1, s0) == (1, 0):
                y, cf = b >> 1, b & 1
            else:
                y, cf = ((b >> 1) | (b & 0x80)) & 0xFF, b & 1
            zf = int(y == 0)
        elif s32 == 1:
            sa_s = a - 256 if a & 0x80 else a
            sb_s = b - 256 if b & 0x80 else b
            gt, eq, lt = int(sa_s > sb_s), int(sa_s == sb_s), int(sa_s < sb_s)
            y = (gt, eq, lt, 0)[s1 * 2 + s0]
            cf, zf = lt, eq
        elif s32 == 2:
            y = total & 0xFF
            cf, zf = cout, int(y == 0)
        else:
            idx = s1 * 2 + s0
            y = (a & b, a | b, (~a) & 0xFF, a ^ b)[idx]
            cf, zf = 0, int(y == 0)

        sf = (y >> 7) & 1
        old_z, old_c = self.flags & 1, (self.flags >> 1) & 1

        # 写回 / 写主存
        if fn in (0, 1):
            self.regs[creg] = y
        elif fn == 3:
            self.regs[creg] = self.ram[self.regs[sa] & 0xF]
        elif fn == 2:
            self.ram[self.regs[sa] & 0xF] = self.regs[sb]

        # 标志：跳转指令不更新
        if fn not in (4, 5, 6):
            self.flags = zf | (cf << 1) | (sf << 2) | (of << 3)

        # PC：跳转按 4 位有符号偏移，否则 +1
        if fn == 4 or (fn == 5 and old_z) or (fn == 6 and old_c):
            self.pc = (self.pc + off) & 0xFF
        else:
            self.pc = (self.pc + 1) & 0xFF

    # ---- 时钟沿：e%4==1 取指，e%4==3 执行 ----
    def edge(self, e):
        if e % 4 == 1:
            self.ir = self.rom[self.pc & 0xF]
        elif e % 4 == 3:
            self.execute()

    def ramq(self):
        sa = (self.ir >> 4) & 3
        return self.ram[self.regs[sa] & 0xF]


def make_vector(rom, prog, ninstr):
    """生成逐拍向量：每个沿 1 行 + 0 行，T3 后的 0 行做全量比对。"""
    cpu = Cpu(rom)
    rows = [("CLK", "RST", "Prog", "R0", "R1", "R2", "R3",
             "PC", "IR", "RAMQ", "FLAGS")]

    def row(clk, rst, checks):
        vals = [str(clk), str(rst), str(prog)]
        for name in ("R0", "R1", "R2", "R3", "PC", "IR", "RAMQ", "FLAGS"):
            vals.append("x" if checks is None else "0x%x" % checks[name])
        rows.append(tuple(vals))

    # 复位：同步/异步两种清法都覆盖
    for clk, rst in ((0, 1), (1, 1), (0, 1), (0, 0)):
        row(clk, rst, {"R0": 0, "R1": 0, "R2": 0, "R3": 0,
                       "PC": 0, "IR": 0, "RAMQ": 0, "FLAGS": 0})

    total_edges = 4 * ninstr + 2
    for e in range(1, total_edges + 1):
        if (e - 1) % 4 == 0:      # 指令边界：取指沿之前
            pass
        row(1, 0, None)           # 上升沿
        cpu.edge(e)
        if e % 4 == 1:
            checks = {"R0": cpu.regs[0], "R1": cpu.regs[1],
                      "R2": cpu.regs[2], "R3": cpu.regs[3],
                      "PC": cpu.pc, "IR": cpu.ir, "RAMQ": cpu.ramq(),
                      "FLAGS": cpu.flags}
        elif e % 4 == 3:
            checks = {"R0": cpu.regs[0], "R1": cpu.regs[1],
                      "R2": cpu.regs[2], "R3": cpu.regs[3],
                      "PC": cpu.pc, "IR": cpu.ir, "RAMQ": cpu.ramq(),
                      "FLAGS": cpu.flags}
        else:
            checks = None
        row(0, 0, checks)
    return rows


def write_vec(rows, path):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(" ".join(r) + "\n")


def run(name, circ, rom, prog, ninstr):
    rows = make_vector(rom, prog, ninstr)
    vec = os.path.join(tempfile.gettempdir(),
                       "lab5_%d.vec" % (abs(hash(name)) % 100000))
    write_vec(rows, vec)
    res = ita_probe.run_vector(circ, vec, "系统连接", clk="CLK")
    print("%-18s rows=%-4s pass=%-4s fail=%-4s %s" %
          (name, res["rows"], res["pass"], res["fail"], res["fails"][:10]))
    if res["fail"]:
        for line in res["log"].splitlines():
            if "FAIL" in line:
                print("   " + line)
    return res


def variant_circ(circ, base_words, new_words, tag):
    src = open(circ, encoding="utf-8").read()
    old = rom_text(base_words)
    new = rom_text(new_words)
    if old not in src:
        raise RuntimeError("找不到 %s 的 ROM 内容，无法生成变体" % tag)
    dst = os.path.join(tempfile.gettempdir(), "lab5_%s.circ" % tag)
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src.replace(old, new))
    return dst


def main():
    ap = argparse.ArgumentParser(description="实验5 全程序验证")
    ap.add_argument("--circ", default=DEFAULT_CIRC)
    args = ap.parse_args()

    ok = True
    ok &= run("例1 -8*10", args.circ, P0, 0, 10)["fail"] == 0
    ok &= run("例2 -4/4", args.circ, P1, 1, 7)["fail"] == 0
    ok &= run("例3 斐波那契", args.circ, P2, 2, 27)["fail"] == 0
    ok &= run("例4 2>-3", args.circ, P3, 3, 9)["fail"] == 0

    circ_eq = variant_circ(args.circ, P3, P3_EQ, "p3eq")
    ok &= run("例4 2=2", circ_eq, P3_EQ, 3, 8)["fail"] == 0
    circ_lt = variant_circ(args.circ, P3, P3_LT, "p3lt")
    ok &= run("例4 -3<2", circ_lt, P3_LT, 3, 8)["fail"] == 0

    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
