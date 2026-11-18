# -*- coding: utf-8 -*-
"""实验7 奇校验编码/解码验证（Logisim-ITA 2.15.0.2）。

- 2k+1奇校验：512 组穷举，Y = 9 位异或；
- 奇校验编码：256 组穷举，Y = {奇校验位, D}，9 位中 1 的个数为奇数；
- 奇校验解码：512 组穷举，D = A[7:0]，正确 = A 的奇校验；
- main：数据=0x5A，CLK 连续打拍，用 trace 读取随机屏蔽字，
  验证 传输数据=编码^屏蔽字、输出=数据^屏蔽字[7:0]、错误=屏蔽字奇偶。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

DATA = 0x5A


def write_vec(name, header, rows):
    path = os.path.join(tempfile.gettempdir(), name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(" ".join(header) + "\n")
        for r in rows:
            fh.write(" ".join(str(x) for x in r) + "\n")
    return path


def run(name, header, rows):
    vec = write_vec("lab7_%s.vec" % name, header, rows)
    res = ita_probe.run_vector(CIRC, vec, name, clk=None)
    print("%-12s rows=%-4s pass=%-4s fail=%-4s %s" %
          (name, res["rows"], res["pass"], res["fail"], res["fails"][:8]))
    return res


def test_odd():
    rows = []
    for v in range(512):
        bits = [(v >> i) & 1 for i in range(9)]
        rows.append(bits + [sum(bits) & 1])
    return run("2k+1奇校验", [f"X{i}" for i in range(9)] + ["Y"], rows)


def test_encoder():
    rows = []
    for d in range(256):
        par = 1 if bin(d).count("1") % 2 == 0 else 0
        rows.append((d, (par << 8) | d))
    return run("奇校验编码", ["D", "Y"], rows)


def test_decoder():
    rows = []
    for a in range(512):
        p = bin(a).count("1") & 1
        rows.append((a, a & 0xFF, p, 1 - p))
    return run("奇校验解码", ["A", "D", "正确", "错误"], rows)


def test_main():
    rows = []
    for i in range(160):
        rows.append((i & 1, DATA, "x", "x", "x", "x", "x"))
    vec = write_vec("lab7_main.vec",
                    ["CLK", "数据", "屏蔽字", "传输数据", "输出", "正确", "错误"],
                    rows)
    res = ita_probe.run_vector(CIRC, vec, "main", clk="CLK", trace=True)
    print("main trace rows=%s fail=%s" % (res["rows"], res["fail"]))
    if res["fail"]:
        return False

    enc = 0x100 | DATA if bin(DATA).count("1") % 2 == 0 else DATA
    weights = {}
    ok = True
    for line in res["log"].splitlines():
        if not line.startswith("TRACE "):
            continue
        vals = dict(re.findall(r"(\S+)=(\S+)", line))
        mask = int(vals["屏蔽字"], 16)
        tx = int(vals["传输数据"], 16)
        out = int(vals["输出"], 16)
        okflag = int(vals["正确"], 16)
        err = int(vals["错误"], 16)
        w = bin(mask).count("1")
        weights[w] = weights.get(w, 0) + 1
        good = (tx == (enc ^ mask) and out == (DATA ^ (mask & 0xFF))
                and err == (w & 1) and okflag == (1 - (w & 1)))
        if not good:
            ok = False
            print("  FAIL mask=%03x tx=%03x out=%02x 正确=%d 错误=%d" %
                  (mask, tx, out, okflag, err))
            break
    print("屏蔽字权重分布:", weights)
    return ok


def main():
    global CIRC
    ap = argparse.ArgumentParser(description="实验7 验证")
    ap.add_argument("--circ", default="实验7 IO接口实验.circ")
    args = ap.parse_args()
    CIRC = args.circ

    ok = True
    for name in ("2k+1奇校验", "奇校验编码", "奇校验解码", "main"):
        errs = ita_probe.errors(CIRC, name)
        good = errs == ["ERRCOUNT 0"]
        ok &= good
        print("%-12s errors %s %s" % (name, errs, "OK" if good else "FAIL"))

    ok &= test_odd()["fail"] == 0
    ok &= test_encoder()["fail"] == 0
    ok &= test_decoder()["fail"] == 0
    ok &= test_main()
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
