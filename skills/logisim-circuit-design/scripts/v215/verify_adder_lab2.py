# -*- coding: utf-8 -*-
"""实验2 加法器功能验证：生成向量，交给 2.15 探针跑，逐项比对期望值。"""
from __future__ import annotations

import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "v271"))
import ita_probe  # noqa: E402

CIRC = "实验2 构建加法器.circ"


def run(name, header, rows, expect, circuit=None):
    path = os.path.join(tempfile.gettempdir(), "vec_%s.vec" % abs(hash(name)))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(" ".join(str(x) for x in list(r) + list(expect(r))) + "\n")
    res = ita_probe.run_vector(CIRC, path, circuit or name)
    print("%-16s rows=%-5s pass=%-5s fail=%-3s %s" %
          (name, res["rows"], res["pass"], res["fail"], res["fails"][:8]))
    if res["fails"]:
        print("   首行失败输入:", rows[res["fails"][0] - 2])
    return res


def cla(g4, p4, g3, p3, g2, p2, g1, p1, cin):
    c1 = g1 | (p1 & cin)
    c2 = g2 | (p2 & g1) | (p2 & p1 & cin)
    c3 = g3 | (p3 & g2) | (p3 & p2 & g1) | (p3 & p2 & p1 & cin)
    c4 = (g4 | (p4 & g3) | (p4 & p3 & g2) |
          (p4 & p3 & p2 & g1) | (p4 & p3 & p2 & p1 & cin))
    gs = g4 | (p4 & g3) | (p4 & p3 & g2) | (p4 & p3 & p2 & g1)
    ps = p4 & p3 & p2 & p1
    return [int(c1), int(c2), int(c3), int(c4), int(gs), int(ps)]


def main():
    rnd = random.Random(20261117)

    run("半加器", "A B S C",
        [(a, b) for a in (0, 1) for b in (0, 1)],
        lambda r: [r[0] ^ r[1], r[0] & r[1]])

    run("全加器", "A B Cin S Cout",
        [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)],
        lambda r: [(r[0] + r[1] + r[2]) & 1, (r[0] + r[1] + r[2]) >> 1])

    rows = [(a >> 0 & 1, a >> 1 & 1, a >> 2 & 1, a >> 3 & 1,
             b >> 0 & 1, b >> 1 & 1, b >> 2 & 1, b >> 3 & 1, c)
            for a in range(16) for b in range(16) for c in (0, 1)]

    def fa4(r):
        a = r[0] + 2 * r[1] + 4 * r[2] + 8 * r[3]
        b = r[4] + 2 * r[5] + 4 * r[6] + 8 * r[7]
        s = a + b + r[8]
        return [s >> i & 1 for i in range(4)] + [s >> 4 & 1]

    run("4位全加器", "A0 A1 A2 A3 B0 B1 B2 B3 C0 S0 S1 S2 S3 C4", rows, fa4)

    rows = [(g4, p4, g3, p3, g2, p2, g1, p1, cin)
            for g4 in (0, 1) for p4 in (0, 1) for g3 in (0, 1) for p3 in (0, 1)
            for g2 in (0, 1) for p2 in (0, 1) for g1 in (0, 1) for p1 in (0, 1)
            for cin in (0, 1)]
    run("并行进位器", "G4 P4 G3 P3 G2 P2 G1 P1 Cin C1 C2 C3 C4 G* P*",
        rows, lambda r: cla(*r))

    rows = [(a, b, c) for a in range(16) for b in range(16) for c in (0, 1)]

    def fast4(r):
        a, b, c = r
        total = a + b + c
        g = [(a >> i & 1) & (b >> i & 1) for i in range(4)]
        p = [(a >> i & 1) ^ (b >> i & 1) for i in range(4)]
        gs = g[3] | (p[3] & g[2]) | (p[3] & p[2] & g[1]) | (p[3] & p[2] & p[1] & g[0])
        ps = p[3] & p[2] & p[1] & p[0]
        c3 = (((a & 7) + (b & 7) + c) >> 3) & 1
        return [total & 15, (total >> 4) & 1, c3, int(gs), int(ps)]

    run("4并行加法器", "A B C0 S C4 C3 G* P*", rows, fast4)

    vals = [0, 1, 2, 3, 0x7f, 0x80, 0x81, 0xff, 0xfe, 0x55, 0xaa,
            0x40, 0xbf, 0xc0, 0x0f, 0xf0]
    rows = [(a, b, sub, cin) for a in vals for b in vals
            for sub in (0, 1) for cin in (0, 1)]

    def alu8(r):
        a, b, sub, cin = r
        bp = b ^ (0xFF if sub else 0)
        total = a + bp + (cin ^ sub)
        s = total & 0xFF
        cout = (total >> 8) & 1
        ov = 1 if ((a >> 7) == (bp >> 7)) and (((s >> 7) != (a >> 7))) else 0
        return [s, cout, ov]

    run("8位串行加法器验证电路", "A B Sub Cin S Cout Overflow", rows, alu8)

    rows = [(rnd.randrange(256), rnd.randrange(256),
             rnd.randrange(2), rnd.randrange(2)) for _ in range(2000)]
    run("8位随机抽样", "A B Sub Cin S Cout Overflow", rows, alu8,
        circuit="8位串行加法器验证电路")

    rows = [(0, 0, 0), (0xffff, 0xffff, 1), (0x8000, 0x8000, 0),
            (0x7fff, 0x7fff, 0), (0x8000, 0x7fff, 1), (0x1234, 0x5678, 1),
            (0xffff, 0x0001, 0), (0x0001, 0xffff, 1)]
    for _ in range(500):
        rows.append((rnd.randrange(1 << 16), rnd.randrange(1 << 16),
                     rnd.randrange(2)))

    def add16(r):
        a, b, c = r
        total = a + b + c
        nib_g, nib_p = [], []
        for k in range(4):
            g = [(a >> (4 * k + i) & 1) & (b >> (4 * k + i) & 1) for i in range(4)]
            p = [(a >> (4 * k + i) & 1) ^ (b >> (4 * k + i) & 1) for i in range(4)]
            nib_g.append(g[3] | (p[3] & g[2]) | (p[3] & p[2] & g[1]) |
                         (p[3] & p[2] & p[1] & g[0]))
            nib_p.append(p[3] & p[2] & p[1] & p[0])
        g_star = (nib_g[3] | (nib_p[3] & nib_g[2]) |
                  (nib_p[3] & nib_p[2] & nib_g[1]) |
                  (nib_p[3] & nib_p[2] & nib_p[1] & nib_g[0]))
        p_star = nib_p[3] & nib_p[2] & nib_p[1] & nib_p[0]
        c15 = (((a & 0x7fff) + (b & 0x7fff) + c) >> 15) & 1
        return [total & 0xFFFF, (total >> 16) & 1, c15, g_star, p_star]

    run("16位验证", "A B C0 S C16 C15 G* P*", rows, add16)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="实验2 加法器功能验证（2.15.0.2）")
    ap.add_argument("--circ", default=CIRC, help=".circ 路径（相对当前目录）")
    CIRC = os.path.abspath(ap.parse_args().circ)
    main()
