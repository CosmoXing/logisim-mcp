# -*- coding: utf-8 -*-
"""实验6 存储器实验验证（Logisim-ITA 2.15.0.2）。

1. 16*16点阵字库 D1 字扩展：
   - 读 14 位地址、高 2 位、4 片 ROM 的 Q、D1
   - 断言 A14=(区号-1)*94+(位号-1)、D1 == Q[高2位]
2. 16*16姓名显示：
   - 用 Pin 替换 Clock，逐拍验证 9 个机内码的 区号/位号/D1
3. 两个电路的 ERRCOUNT 必须为 0。

用法（在实验目录下运行）：
    python verify_lab6.py [--circ "实验6 存储器实验.circ"]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

CODES = ["B6AB", "B1B1", "B4F3", "D1A7", "BCC6", "CBE3", "BBFA",
         "D3B2", "BCFE"]


def pin(c, x, y, label, width, output=True):
    e = ET.Element("comp", {"lib": "0", "loc": f"({x},{y})", "name": "Pin"})
    for k, v in (("facing", "east"), ("output", "true" if output else "false"),
                 ("width", width), ("tristate", "false"), ("pull", "none"),
                 ("label", label), ("labelloc", "north"),
                 ("labelfont", "Dialog plain 12")):
        a = ET.SubElement(e, "a", {"name": k})
        a.set("val", str(v))
    c.append(e)


def tunnel(c, x, y, label, width):
    e = ET.Element("comp", {"lib": "0", "loc": f"({x},{y})", "name": "Tunnel"})
    for k, v in (("facing", "east"), ("width", width), ("label", label)):
        a = ET.SubElement(e, "a", {"name": k})
        a.set("val", str(v))
    c.append(e)


def wire(c, a, b):
    c.append(ET.Element("wire", {"from": f"({a[0]},{a[1]})",
                                 "to": f"({b[0]},{b[1]})"}))


def make_d1_probe(circ: str) -> str:
    root = ET.parse(circ).getroot()
    c = next(x for x in root.findall("circuit") if x.get("name") == "16*16点阵字库")
    for i in range(4):
        tunnel(c, 1300, 900 + 50 * i, f"B{i}", 32)
        wire(c, (1300, 900 + 50 * i), (1320, 900 + 50 * i))
        pin(c, 1320, 900 + 50 * i, f"OB{i}", 32)
    tunnel(c, 1300, 1120, "A_HI", 2)
    wire(c, (1300, 1120), (1320, 1120))
    pin(c, 1320, 1120, "OHI", 2)
    tunnel(c, 1300, 1170, "ADDR14", 14)
    wire(c, (1300, 1170), (1320, 1170))
    pin(c, 1320, 1170, "OA14", 14)
    dst = os.path.join(tempfile.gettempdir(), "lab6_d1_probe.circ")
    ET.ElementTree(root).write(dst, encoding="utf-8", xml_declaration=True)
    return dst


def make_display_probe(circ: str) -> str:
    root = ET.parse(circ).getroot()
    c = next(x for x in root.findall("circuit") if x.get("name") == "16*16姓名显示")
    for e in list(c):
        if e.tag == "comp" and e.get("name") == "Clock":
            c.remove(e)
    pin(c, 80, 250, "CLK", 1, output=False)

    # ROM Q：从输出脚直接向上引
    wire(c, (270, 210), (270, 180))
    pin(c, 270, 180, "OCODE", 16)

    # 区号/位号：用同名隧道接，避开 x=300 的 ROM→转换竖线
    tunnel(c, 250, 100, "QW", 7)
    wire(c, (250, 100), (270, 100))
    pin(c, 270, 100, "OQW", 7)
    tunnel(c, 250, 120, "WH", 7)
    wire(c, (250, 120), (270, 120))
    pin(c, 270, 120, "OWH", 7)

    # D1（也可以加 D0~D7，这里只验关键 plane）
    tunnel(c, 500, 190, "D1", 32)
    wire(c, (500, 190), (520, 190))
    pin(c, 520, 190, "OD1", 32)

    dst = os.path.join(tempfile.gettempdir(), "lab6_display_probe.circ")
    ET.ElementTree(root).write(dst, encoding="utf-8", xml_declaration=True)
    return dst


def d1_values(circ: str, q: int, w: int) -> dict:
    return ita_probe.eval_pins(circ, "16*16点阵字库",
                               {"区号": q, "位号": w},
                               ["OA14", "OHI", "OB0", "OB1", "OB2", "OB3", "D1"])


def verify_d1(circ: str) -> bool:
    probe = make_d1_probe(circ)
    ok = True
    for code in CODES:
        h, l = int(code[:2], 16), int(code[2:], 16)
        q, w = h - 0xA0, l - 0xA0
        res = d1_values(probe, q, w)
        a = int(res["OA14"], 16)
        hi = int(res["OHI"], 16)
        want_a = (q - 1) * 94 + (w - 1)
        bank = int(res[f"OB{hi}"], 16)
        d1 = int(res["D1"], 16)
        good = a == want_a and d1 == bank
        ok &= good
        print("  D1 %s 区%2d位%2d A14=%04x hi=%d D1=%08x bank=%08x %s"
              % (code, q, w, a, hi, d1, bank, "OK" if good else "FAIL"))
    return ok


def verify_display(circ: str) -> bool:
    probe = make_display_probe(circ)
    rows = ["CLK OCODE OQW OWH OD1"]
    # 9 个机内码的期望 D1 由 16*16点阵字库单独算
    for i, code in enumerate(CODES):
        h, l = int(code[:2], 16), int(code[2:], 16)
        q, w = h - 0xA0, l - 0xA0
        d1 = d1_values(circ, q, w)["D1"]
        if i:
            rows.append("1 0x%s 0x%02x 0x%02x %s" % (code.lower(), q, w, d1))
        rows.append("0 0x%s 0x%02x 0x%02x %s" % (code.lower(), q, w, d1))
    vec = os.path.join(tempfile.gettempdir(), "lab6_display.vec")
    with open(vec, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rows) + "\n")
    res = ita_probe.run_vector(probe, vec, "16*16姓名显示", clk="CLK")
    print("  显示: rows=%s pass=%s fail=%s %s" %
          (res["rows"], res["pass"], res["fail"], res["fails"][:8]))
    return res["fail"] == 0


def main():
    ap = argparse.ArgumentParser(description="实验6 验证")
    ap.add_argument("--circ", default="实验6 存储器实验.circ")
    args = ap.parse_args()

    ok = True
    for name in ("16*16点阵字库", "16*16姓名显示"):
        errs = ita_probe.errors(args.circ, name)
        good = errs == ["ERRCOUNT 0"]
        ok &= good
        print("%-14s errors %s %s" % (name, errs, "OK" if good else "FAIL"))

    print("D1 字扩展：")
    ok &= verify_d1(args.circ)
    print("姓名显示：")
    ok &= verify_display(args.circ)

    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
