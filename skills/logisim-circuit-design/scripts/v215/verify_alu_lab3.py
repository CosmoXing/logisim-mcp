# -*- coding: utf-8 -*-
"""实验3 8位 ALU（带比较器）功能验证：生成向量，交给 2.15 探针逐行比对。

覆盖：8位可控加减器、移位器、逻辑运算器、比较器、ALU 顶层。
"""
from __future__ import annotations

import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

CIRC = os.environ.get("LAB3_CIRC", "实验3 ALU设计.circ")


def run(name, header, rows, expect, circuit=None):
    path = os.path.join(tempfile.gettempdir(), "lab3_%s.vec" % abs(hash(name)))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(" ".join(str(x) for x in list(r) + list(expect(r))) + "\n")
    res = ita_probe.run_vector(CIRC, path, circuit or name)
    print("%-14s rows=%-6s pass=%-6s fail=%-4s %s" %
          (name, res["rows"], res["pass"], res["fail"], res["fails"][:6]))
    if res["fails"]:
        idx = res["fails"][0] - 2
        print("   首个失败输入:", rows[idx], "期望:", expect(rows[idx]))
    return res


VALS = [0x00, 0x01, 0x02, 0x03, 0x07, 0x08, 0x0F, 0x10, 0x1F, 0x20,
        0x3F, 0x40, 0x55, 0x7E, 0x7F, 0x80, 0x81, 0xAA, 0xBF, 0xC0,
        0xFE, 0xFF]


def signed_of(a, b, s):
    return 1 if ((a >> 7) == (b >> 7)) and (((s >> 7) != (a >> 7))) else 0


def add8_row(r):
    a, b, sub, cin = r
    bx = b ^ (0xFF if sub else 0)
    total = a + bx + (cin ^ sub)
    s = total & 0xFF
    return [s, (total >> 8) & 1, signed_of(a, bx, s)]


def alu_arith(a, b, s3, s2, s1, s0, cin):
    """返回 [S, SF, ZF, OF, CF]；不在算术模式时返回 None。"""
    if (s3, s2) != (1, 0):
        return None
    if s1 == 1:
        b = 0          # INC / NEC：B 置 0
    bx = b ^ (0xFF if s0 else 0)
    total = a + bx + (cin ^ s0)
    s = total & 0xFF
    return [s, (s >> 7) & 1, 1 if s == 0 else 0,
            signed_of(a, bx, s), (total >> 8) & 1]


def shift_out_left(b, n):
    return 0 if n == 0 else (b >> (8 - n)) & 1


def shift_out_right(b, n):
    return 0 if n == 0 else (b >> (n - 1)) & 1


def sar(b, n):
    if n == 0:
        return b
    v = b if b < 0x80 else b - 0x100
    return (v >> n) & 0xFF


def main():
    rnd = random.Random(20261117)

    # ---------------- 8位可控加减器 ----------------
    rows = [(a, b, sub, cin) for a in VALS for b in VALS
            for sub in (0, 1) for cin in (0, 1)]
    rows += [(rnd.randrange(256), rnd.randrange(256),
              rnd.randrange(2), rnd.randrange(2)) for _ in range(1500)]
    run("8位可控加减器", "A B Sub Cin S Cout OF", rows, add8_row)

    # ---------------- 移位器 ----------------
    rows, exp = [], []
    for b in VALS + [rnd.randrange(256) for _ in range(40)]:
        for n in range(8):
            for s1, s0 in ((0, 0), (0, 1), (1, 0), (1, 1)):
                rows.append((b, n, s1, s0))
                if (s1, s0) == (0, 0):
                    exp.append((b, 0))
                elif (s1, s0) == (0, 1):
                    exp.append(((b << n) & 0xFF, shift_out_left(b, n)))
                elif (s1, s0) == (1, 0):
                    exp.append((b >> n, shift_out_right(b, n)))
                else:
                    exp.append((sar(b, n), shift_out_right(b, n)))
    run("移位器", "X N S1 S0 Y SOL", rows,
        lambda r, it=iter(exp): next(it))

    # ---------------- 逻辑运算器 ----------------
    rows, exp = [], []
    for a in VALS:
        for b in VALS:
            for s1, s0 in ((0, 0), (0, 1), (1, 0), (1, 1)):
                rows.append((a, b, s1, s0))
                exp.append([a & b, a | b, (~a) & 0xFF, a ^ b][s1 * 2 + s0])
    run("逻辑运算器", "A B S1 S0 Y", rows,
        lambda r, it=iter(exp): [next(it)])

    # ---------------- 比较器 ----------------
    rows, exp = [], []
    for a in VALS:
        for b in VALS:
            for s1, s0 in ((0, 0), (0, 1), (1, 0)):
                rows.append((a, b, s1, s0))
                gt, eq, lt = int(a > b), int(a == b), int(a < b)
                y = [gt, eq, lt][s1 * 2 + s0]
                exp.append([y, gt, eq, lt])
    run("比较器", "A B S1 S0 Y GT EQ LT", rows,
        lambda r, it=iter(exp): next(it))

    # ---------------- ALU：移位 ----------------
    rows, exp = [], []
    for b in VALS:
        for n in range(8):
            for s1, s0 in ((0, 0), (0, 1), (1, 0), (1, 1)):
                rows.append((n, b, 0, 0, s1, s0, 0))
                if (s1, s0) == (0, 0):
                    y, cf = b, 0
                elif (s1, s0) == (0, 1):
                    y, cf = (b << n) & 0xFF, shift_out_left(b, n)
                elif (s1, s0) == (1, 0):
                    y, cf = b >> n, shift_out_right(b, n)
                else:
                    y, cf = sar(b, n), shift_out_right(b, n)
                exp.append([y, "x", "x", "x", cf])
    run("ALU-移位", "A B S3 S2 S1 S0 Cin S SF ZF OF CF", rows,
        lambda r, it=iter(exp): next(it), circuit="ALU 8位（带比较器）")

    # ---------------- ALU：比较 ----------------
    rows, exp = [], []
    for a in VALS:
        for b in VALS:
            for s1, s0 in ((0, 0), (0, 1), (1, 0)):
                rows.append((a, b, 0, 1, s1, s0, 0))
                gt, eq, lt = int(a > b), int(a == b), int(a < b)
                y = [gt, eq, lt][s1 * 2 + s0]
                exp.append([y, "x", eq, "x", lt])
    run("ALU-比较", "A B S3 S2 S1 S0 Cin S SF ZF OF CF", rows,
        lambda r, it=iter(exp): next(it), circuit="ALU 8位（带比较器）")

    # ---------------- ALU：算术 ----------------
    rows, exp = [], []
    for (s1, s0, cin) in ((0, 0, 0), (0, 0, 1), (0, 1, 0),
                          (0, 1, 1), (1, 0, 1), (1, 1, 1)):
        for a in VALS:
            for b in VALS:
                rows.append((a, b, 1, 0, s1, s0, cin))
                exp.append(alu_arith(a, b, 1, 0, s1, s0, cin))
    # 随机补充
    for _ in range(800):
        a, b = rnd.randrange(256), rnd.randrange(256)
        s1, s0, cin = rnd.choice([(0, 0, 0), (0, 0, 1), (0, 1, 0),
                                  (0, 1, 1), (1, 0, 1), (1, 1, 1)])
        rows.append((a, b, 1, 0, s1, s0, cin))
        exp.append(alu_arith(a, b, 1, 0, s1, s0, cin))
    run("ALU-算术", "A B S3 S2 S1 S0 Cin S SF ZF OF CF", rows,
        lambda r, it=iter(exp): next(it), circuit="ALU 8位（带比较器）")

    # ---------------- ALU：逻辑 ----------------
    rows, exp = [], []
    for a in VALS:
        for b in VALS:
            for s1, s0 in ((0, 0), (0, 1), (1, 0), (1, 1)):
                rows.append((a, b, 1, 1, s1, s0, 0))
                y = [a & b, a | b, (~a) & 0xFF, a ^ b][s1 * 2 + s0]
                exp.append([y, "x", 1 if y == 0 else 0, "x", "x"])
    run("ALU-逻辑", "A B S3 S2 S1 S0 Cin S SF ZF OF CF", rows,
        lambda r, it=iter(exp): next(it), circuit="ALU 8位（带比较器）")


if __name__ == "__main__":
    main()
