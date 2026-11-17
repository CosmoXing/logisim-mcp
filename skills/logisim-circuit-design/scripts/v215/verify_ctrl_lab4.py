# -*- coding: utf-8 -*-
"""实验4 控制器模块功能验证：生成向量，交给 2.15 探针逐行比对。"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

CIRC = os.environ.get("LAB4_CIRC", "实验4 控制器模块.circ")


def run(name, header, rows, circuit=None, clk=None):
    path = os.path.join(tempfile.gettempdir(), "lab4_%s.vec" % abs(hash(name)))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(" ".join(str(x) for x in r) + "\n")
    res = ita_probe.run_vector(CIRC, path, circuit or name, clk=clk)
    print("%-12s rows=%-4s pass=%-4s fail=%-4s %s" %
          (name, res["rows"], res["pass"], res["fail"], res["fails"][:8]))
    if res["fail"]:
        print("   ", "\n    ".join(res["log"].splitlines()[:12]))
    return res


def test_regs():
    X = "x"
    rows = [
        (1, 0, 0, 0x11, 0, 0, X, X),
        (1, 1, 0, 0x11, 0, 0, X, X),
        (1, 0, 0, 0x11, 0, 0, 0x11, 0x11),
        (1, 0, 1, 0x22, 0, 0, 0x11, 0x11),
        (1, 1, 1, 0x22, 0, 0, X, X),
        (1, 0, 1, 0x22, 1, 0, 0x22, 0x11),
        (1, 0, 2, 0x33, 1, 1, 0x22, 0x22),
        (1, 1, 2, 0x33, 0, 0, X, X),
        (1, 0, 2, 0x33, 2, 1, 0x33, 0x22),
        (1, 0, 3, 0x44, 2, 2, 0x33, 0x33),
        (1, 1, 3, 0x44, 0, 0, X, X),
        (1, 0, 3, 0x44, 3, 2, 0x44, 0x33),
        (0, 1, 0, 0x99, 0, 0, X, X),
        (1, 0, 0, 0x99, 0, 0, 0x11, 0x11),
        (1, 1, 0, 0x99, 0, 0, X, X),
        (1, 0, 0, 0x99, 0, 3, 0x99, 0x44),
    ]
    return run("Regs", "R/W CLK C-Reg Data SA SB A B", rows)


def test_pc():
    X = "x"
    rows = [
        (0, 0, 1, 0, 0, X),
        (0, 1, 1, 0, 0, 0),
        (0, 0, 0, 0, 0, 0),
        (1, 1, 0, 0, 0, 1),
        (1, 0, 0, 0, 0, 1),
        (1, 1, 0, 0, 0, 2),
        (1, 0, 0, 0, 0, 2),
        (1, 1, 0, 1, 5, 7),
        (1, 0, 0, 1, 5, 7),
        (0, 1, 0, 1, 5, 7),
        (1, 0, 0, 0, 0, 7),
        (1, 1, 0, 0, 0, 8),
        (1, 0, 0, 0, 0, 8),
        (1, 1, 1, 0, 0, 0),
    ]
    return run("PC", "TC_en CLK RST JSel Offset P_addr", rows)


def test_ir():
    rows = [
        (0x1234, 0, 0, 1, "x"),
        (0x1234, 0, 1, 1, 0),
        (0x1234, 1, 0, 0, 0),
        (0x1234, 1, 1, 0, 0x1234),
        (0xBEEF, 0, 0, 0, 0x1234),
        (0xBEEF, 0, 1, 0, 0x1234),
        (0xBEEF, 1, 0, 0, 0x1234),
        (0xBEEF, 1, 1, 0, 0xBEEF),
    ]
    return run("IR", "I-in TF CLK RST I_out", rows)


def test_id():
    table = {
        (0, 0, 0): (1, 0, 0, 0, 0, 0, 0),
        (0, 0, 1): (1, 1, 0, 0, 0, 0, 0),
        (0, 1, 0): (0, 0, 0, 1, 0, 0, 0),
        (0, 1, 1): (1, 0, 1, 0, 0, 0, 0),
        (1, 0, 0): (0, 1, 0, 0, 1, 0, 0),
        (1, 0, 1): (0, 1, 0, 0, 0, 1, 0),
        (1, 1, 0): (0, 1, 0, 0, 0, 0, 1),
        (1, 1, 1): (0, 0, 0, 0, 0, 0, 0),
    }
    rows = [(x, y, z) + exp for (x, y, z), exp in table.items()]
    return run("ID", "X Y Z R/W S-B/I RM WM JP JZ JC", rows)


def test_clk():
    rows = [
        (0, 1, 1, 0, 0, 0),
        (1, 1, 1, 0, 0, 0),
        (0, 0, 1, 0, 0, 0),
        (1, 0, 0, 1, 0, 0),
        (0, 0, 0, 1, 0, 0),
        (1, 0, 0, 0, 1, 0),
        (0, 0, 0, 0, 1, 0),
        (1, 0, 0, 0, 0, 1),
        (0, 0, 0, 0, 0, 1),
        (1, 0, 1, 0, 0, 0),
        (0, 0, 1, 0, 0, 0),
        (1, 0, 0, 1, 0, 0),
    ]
    return run("CLK 模块", "CLK RST T0 T1 T2 T3", rows)


def test_sib():
    rows = [
        (0x12, 0x5, 0, 0x12),
        (0x12, 0x5, 1, 0x05),
        (0xAB, 0xF, 0, 0xAB),
        (0xAB, 0xF, 1, 0x0F),
        (0x00, 0xA, 1, 0x0A),
    ]
    return run("S-I/B", "B I sgnl Out", rows)


def test_flag():
    rows = [
        (0x5, 1, 0, 1, "x"),
        (0x5, 1, 1, 1, 0),
        (0x5, 1, 0, 0, 0),
        (0x5, 1, 1, 0, 0x5),
        (0xA, 0, 0, 0, 0x5),
        (0xA, 0, 1, 0, 0x5),
        (0xA, 1, 0, 0, 0x5),
        (0xA, 1, 1, 0, 0xA),
        (0xF, 1, 0, 0, 0xA),
        (0xF, 1, 1, 1, 0),
    ]
    return run("Flag", "D en CLK RST Q", rows)


def test_cu():
    X = "x"
    # 先取指（TF 上升沿），再执行（TC 上升沿）
    hdr = "RST TC TF I-in Offset Z C addr R/W S-B/I RM WM S-op S-Regs JP JZ JC"
    rows = [
        (1, 0, 0, 0, 0, 0, 0, X, X, X, X, X, X, X, X, X, X),
        (1, 0, 1, 0x0000, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0),
        (0, 0, 0, 0x2000, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0),
        (0, 0, 1, 0x2000, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0x00, 0, 0, 0),
        (0, 0, 0, 0x2000, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0x00, 0, 0, 0),
        (0, 1, 0, 0x2000, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0x00, 0, 0, 0),
        (0, 0, 0, 0x4000, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0x00, 0, 0, 0),
        (0, 0, 1, 0x4000, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0x00, 0, 0, 0),
        (0, 0, 0, 0x4000, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0x00, 0, 0, 0),
        (0, 1, 0, 0x4000, 0, 0, 0, 2, 0, 0, 0, 1, 0, 0x00, 0, 0, 0),
        (0, 0, 0, 0x8000, 2, 0, 0, 2, 0, 0, 0, 1, 0, 0x00, 0, 0, 0),
        (0, 0, 1, 0x8000, 2, 0, 0, 2, 0, 1, 0, 0, 0, 0x00, 1, 0, 0),
        (0, 0, 0, 0x8000, 2, 0, 0, 2, 0, 1, 0, 0, 0, 0x00, 1, 0, 0),
        (0, 1, 0, 0x8000, 2, 0, 0, 4, 0, 1, 0, 0, 0, 0x00, 1, 0, 0),
        (0, 0, 0, 0xA000, 3, 1, 0, 4, 0, 1, 0, 0, 0, 0x00, 1, 0, 0),
        (0, 0, 1, 0xA000, 3, 1, 0, 4, 0, 1, 0, 0, 0, 0x00, 0, 1, 0),
        (0, 1, 0, 0xA000, 3, 1, 0, 7, 0, 1, 0, 0, 0, 0x00, 0, 1, 0),
        (0, 0, 0, 0xC000, 1, 0, 1, 7, 0, 1, 0, 0, 0, 0x00, 0, 1, 0),
        (0, 0, 1, 0xC000, 1, 0, 1, 7, 0, 1, 0, 0, 0, 0x00, 0, 0, 1),
        (0, 1, 0, 0xC000, 1, 0, 1, 8, 0, 1, 0, 0, 0, 0x00, 0, 0, 1),
    ]
    return run("CU 控制器", hdr, rows)


def test_system():
    # 每个 T 周期一拍：T0 取指，T3 改 PC
    hdr = ("CLK RST PADDR IRIN T0 T1 T2 T3 RA RB BOP ALUY REGD FQ4 RAMQ IRQ")
    x = "x"
    rows = [
        (0, 1, 0, 0x4001, 1, 0, 0, 0, x, x, x, x, x, x, x, 0),
        (1, 1, 0, 0x4001, 1, 0, 0, 0, x, x, x, x, x, x, x, 0),
        (0, 0, 0, 0x4001, 1, 0, 0, 0, x, x, x, x, x, x, x, 0),
        (1, 0, 0, 0x4001, 0, 1, 0, 0, x, x, x, x, x, x, x, 0),
        (0, 0, 0, 0x4001, 0, 1, 0, 0, x, x, x, x, x, x, x, 0),
        (1, 0, 0, 0x4001, 0, 0, 1, 0, x, x, x, x, x, x, x, 0),
        (0, 0, 0, 0x4001, 0, 0, 1, 0, x, x, x, x, x, x, x, 0),
        (1, 0, 1, 0x8030, 0, 0, 0, 1, x, x, x, x, x, x, x, 0),
        (0, 0, 1, 0x8030, 0, 0, 0, 1, x, x, x, x, x, x, x, 0),
        (1, 0, 1, 0x8030, 1, 0, 0, 0, x, x, x, x, x, x, x, 0x8030),
        (0, 0, 1, 0x8030, 1, 0, 0, 0, x, x, x, x, x, x, x, 0x8030),
        (1, 0, 1, 0x8030, 0, 1, 0, 0, x, x, x, x, x, x, x, 0x8030),
        (0, 0, 1, 0x8030, 0, 1, 0, 0, x, x, x, x, x, x, x, 0x8030),
        (1, 0, 1, 0x8030, 0, 0, 1, 0, x, x, x, x, x, x, x, 0x8030),
        (0, 0, 1, 0x8030, 0, 0, 1, 0, x, x, x, x, x, x, x, 0x8030),
        (1, 0, 0x31, 0x8030, 0, 0, 0, 1, x, x, x, x, x, x, x, 0x8030),
        (0, 0, 0x31, 0x8030, 0, 0, 0, 1, x, x, x, x, x, x, x, 0x8030),
        (1, 0, 0x31, 0x8030, 1, 0, 0, 0, x, x, x, x, x, x, x, 0x8030),
        (0, 0, 0x31, 0x8030, 1, 0, 0, 0, x, x, x, x, x, x, x, 0x8030),
    ]
    # 系统连接里时钟脚名就是 CLK，自动识别
    return run("系统连接", hdr, rows)


def main():
    test_regs()
    test_pc()
    test_ir()
    test_id()
    test_clk()
    test_sib()
    test_flag()
    test_cu()
    test_system()


if __name__ == "__main__":
    main()
