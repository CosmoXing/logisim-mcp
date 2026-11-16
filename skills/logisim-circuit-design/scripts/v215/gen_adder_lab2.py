# -*- coding: utf-8 -*-
"""实验2 加法器：在给定验证电路上补齐设计（2.15.0.2）。

用法：
    python gen_adder_lab2.py                 # 用默认路径
    python gen_adder_lab2.py --src a.circ --out b.circ

依赖同目录 board215.py；生成后自带六项自检，自检不通过不会写文件。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board215 import Board, Appearance  # noqa: E402

HALF_APP = Appearance(
    rect=(0, 30, 110, 115), anchor=(55, 90), label="HA",
    label_pos=(55, 82),
    ports=[("A", "120,100", 0, 60, 8), ("B", "120,180", 0, 100, 8),
           ("S", "360,110", 110, 60, 8), ("C", "360,240", 110, 110, 8)])

FA_APP = Appearance(
    rect=(0, 30, 120, 125), anchor=(60, 90), label="FA",
    label_pos=(60, 82),
    ports=[("A", "120,170", 0, 50, 8), ("B", "120,210", 0, 90, 8),
           ("Cin", "120,300", 0, 130, 8), ("S", "700,120", 120, 60, 8),
           ("Cout", "760,420", 120, 130, 8)])

FA4_APP = Appearance(
    rect=(0, 20, 160, 310), anchor=(80, 170), label="4位全加器",
    label_pos=(80, 60),
    ports=[("A0", "120,100", 0, 40, 8), ("A1", "120,340", 0, 70, 8),
           ("A2", "120,580", 0, 100, 8), ("A3", "120,820", 0, 130, 8),
           ("B0", "120,140", 0, 170, 8), ("B1", "120,380", 0, 200, 8),
           ("B2", "120,620", 0, 230, 8), ("B3", "120,860", 0, 260, 8),
           ("C0", "120,180", 0, 295, 8),
           ("S0", "560,110", 160, 40, 8), ("S1", "560,350", 160, 70, 8),
           ("S2", "560,590", 160, 100, 8), ("S3", "560,830", 160, 130, 8),
           ("C4", "560,900", 160, 170, 8)])

CLA_APP = Appearance(
    rect=(0, 20, 170, 370), anchor=(85, 200), label="74182",
    label_pos=(85, 70),
    ports=[("G4", "30,50", 0, 40, 8), ("P4", "70,50", 0, 75, 8),
           ("G3", "110,50", 0, 110, 8), ("P3", "150,50", 0, 145, 8),
           ("G2", "190,50", 0, 180, 8), ("P2", "230,50", 0, 215, 8),
           ("G1", "270,50", 0, 250, 8), ("P1", "310,50", 0, 285, 8),
           ("Cin", "350,50", 0, 320, 8),
           ("C4", "410,50", 170, 40, 8), ("C3", "450,50", 170, 80, 8),
           ("C2", "490,50", 170, 120, 8), ("C1", "530,50", 170, 160, 8),
           ("G*", "570,50", 170, 200, 8), ("P*", "610,50", 170, 240, 8)])

FAST4_APP = Appearance(
    rect=(0, 20, 170, 210), anchor=(85, 115), label="4位快速加法器",
    label_pos=(85, 65),
    ports=[("A", "50,50", 0, 40, 10), ("B", "150,50", 0, 80, 10),
           ("C0", "240,50", 0, 118, 8),
           ("S", "330,50", 170, 40, 10), ("C3", "440,50", 170, 80, 8),
           ("C4", "400,50", 170, 116, 8), ("G*", "480,50", 170, 152, 8),
           ("P*", "520,50", 170, 188, 8)])


# ---------------------------------------------------------------- 各电路


def build_half():
    b = Board("半加器")
    b.pin((120, 100), "A")
    b.pin((120, 180), "B")
    b.pin((360, 110), "S", facing="west", output=True)
    b.pin((360, 240), "C", facing="west", output=True)
    b.gate("XOR Gate", (260, 110), 2)
    b.gate("AND Gate", (260, 240), 2)
    b.path([(120, 100), (190, 100), (190, 230), (230, 230)])
    b.wire((190, 100), (220, 100))
    b.path([(120, 180), (170, 180), (170, 250), (230, 250)])
    b.path([(170, 180), (170, 120), (220, 120)])
    b.wire((260, 110), (360, 110))
    b.wire((260, 240), (360, 240))
    return b


def build_full(ha_off):
    b = Board("全加器")
    b.pin((120, 170), "A")
    b.pin((120, 210), "B")
    b.pin((120, 300), "Cin")
    b.pin((700, 120), "S", facing="west", output=True)
    b.pin((760, 420), "Cout", facing="west", output=True)
    h1 = b.sub("半加器", (300, 200), ha_off)
    h2 = b.sub("半加器", (560, 340), ha_off)
    ins, out = b.gate("OR Gate", (720, 480), 2)
    b.wire((120, 170), h1["A"])
    b.wire((120, 210), h1["B"])
    b.path([h1["S"], (430, h1["S"][1]), (430, h2["A"][1]), h2["A"]])
    b.path([(120, 300), (150, 300), (150, 320), (490, 320),
            (490, h2["B"][1]), h2["B"]])
    b.path([h2["S"], (660, h2["S"][1]), (660, 120), (700, 120)])
    b.path([h1["C"], (400, h1["C"][1]), (400, 540), (670, 540),
            (670, ins[1][1]), ins[1]])
    b.path([h2["C"], (650, h2["C"][1]), (650, ins[0][1]), ins[0]])
    b.path([out, (740, 480), (740, 420), (760, 420)])
    return b


def build_fa4(fa_off):
    b = Board("4位全加器")
    for i in range(4):
        y = 140 + i * 240
        b.pin((120, y - 40), f"A{i}")
        b.pin((120, y), f"B{i}")
        b.pin((560, y - 30), f"S{i}", facing="west", output=True)
        fa = b.sub("全加器", (400, y), fa_off)
        b.wire((120, y - 40), fa["A"])
        b.wire((120, y), fa["B"])
        b.wire(fa["S"], (560, y - 30))
        if i == 0:
            b.pin((120, y + 40), "C0")
            b.wire((120, y + 40), fa["Cin"])
        else:
            b.path([(460, y - 200), (520, y - 200), (520, y - 90),
                    (300, y - 90), (300, y + 40), fa["Cin"]])
    b.pin((560, 900), "C4", facing="west", output=True)
    b.wire((460, 900), (560, 900))
    return b


def build_cla():
    b = Board("并行进位器")
    col = {"C1": 80, "C2": 380, "C3": 680, "C4": 980, "G*": 1280, "P*": 1580}

    def put(kind, x, y, n, labels, out):
        b.gate_io(kind, (x, y), n, 1, labels, out)

    put("AND Gate", col["C1"], 240, 2, ["P1", "Cin"], "t_c1")
    put("OR Gate", col["C1"] + 160, 240, 2, ["G1", "t_c1"], "C1")

    put("AND Gate", col["C2"], 240, 2, ["P2", "G1"], "t_c2a")
    put("AND Gate", col["C2"], 340, 3, ["P2", "P1", "Cin"], "t_c2b")
    put("OR Gate", col["C2"] + 160, 290, 3, ["G2", "t_c2a", "t_c2b"], "C2")

    put("AND Gate", col["C3"], 240, 2, ["P3", "G2"], "t_c3a")
    put("AND Gate", col["C3"], 340, 3, ["P3", "P2", "G1"], "t_c3b")
    put("AND Gate", col["C3"], 440, 4, ["P3", "P2", "P1", "Cin"], "t_c3c")
    put("OR Gate", col["C3"] + 160, 340, 4,
        ["G3", "t_c3a", "t_c3b", "t_c3c"], "C3")

    put("AND Gate", col["C4"], 240, 2, ["P4", "G3"], "t_c4a")
    put("AND Gate", col["C4"], 340, 3, ["P4", "P3", "G2"], "t_c4b")
    put("AND Gate", col["C4"], 440, 4, ["P4", "P3", "P2", "G1"], "t_c4c")
    put("AND Gate", col["C4"], 540, 5, ["P4", "P3", "P2", "P1", "Cin"], "t_c4d")
    put("OR Gate", col["C4"] + 160, 390, 5,
        ["G4", "t_c4a", "t_c4b", "t_c4c", "t_c4d"], "C4")

    put("AND Gate", col["G*"], 240, 2, ["P4", "G3"], "t_gsa")
    put("AND Gate", col["G*"], 340, 3, ["P4", "P3", "G2"], "t_gsb")
    put("AND Gate", col["G*"], 440, 4, ["P4", "P3", "P2", "G1"], "t_gsc")
    put("OR Gate", col["G*"] + 160, 340, 4, ["G4", "t_gsa", "t_gsb", "t_gsc"], "G*")

    put("AND Gate", col["P*"], 240, 4, ["P4", "P3", "P2", "P1"], "P*")
    return b


def build_fast4(cla_off):
    b = Board("4并行加法器")
    for i in range(4):
        y = 260 + i * 120
        b.gate_io("XOR Gate", (460, y), 2, 1, [f"A{i}", f"B{i}"], f"P{i+1}")
        b.gate_io("AND Gate", (460, y + 60), 2, 1, [f"A{i}", f"B{i}"], f"G{i+1}")
    for i in range(4):
        y = 900 + i * 120
        b.gate_io("XOR Gate", (460, y), 2, 1, [f"P{i+1}", f"C{i}"], f"S{i}")
    cla = b.sub("并行进位器", (1000, 620), cla_off)
    for name in ("G4", "P4", "G3", "P3", "G2", "P2", "G1", "P1", "Cin"):
        b.stub(cla[name], "C0" if name == "Cin" else name, 1, "w")
    for name in ("C4", "C3", "C2", "C1", "G*", "P*"):
        b.stub(cla[name], name, 1, "e")
    return b


def build_16bit(fast4_off, cla_off):
    b = Board("16位验证")
    for i in range(4):
        blk = b.sub("4并行加法器", (350 + i * 320, 560), fast4_off)
        b.stub(blk["A"], f"A{i}", 4, "w")
        b.stub(blk["B"], f"B{i}", 4, "w")
        b.stub(blk["C0"], "C0" if i == 0 else f"C{i}", 1, "w")
        b.stub(blk["S"], f"S{i}", 4, "e")
        b.stub(blk["G*"], f"G{i+1}", 1, "e")
        b.stub(blk["P*"], f"P{i+1}", 1, "e")
        if i == 3:
            b.stub(blk["C4"], "C16", 1, "e")
            b.stub(blk["C3"], "C15", 1, "e")
    cla = b.sub("并行进位器", (1620, 1080), cla_off)
    for name in ("G4", "P4", "G3", "P3", "G2", "P2", "G1", "P1", "Cin"):
        b.stub(cla[name], name if name != "Cin" else "C0", 1, "w")
    for name in ("C1", "C2", "C3", "G*", "P*"):
        b.stub(cla[name], name, 1, "e")
    return b


def build_8bit(fa4_off):
    b = Board("8位串行加法器验证电路")
    low = b.sub("4位全加器", (1400, 320), fa4_off)
    high = b.sub("4位全加器", (1400, 900), fa4_off)
    for i in range(4):
        b.stub(low[f"A{i}"], f"A{i}", 1, "w")
        b.stub(low[f"B{i}"], f"Bx{i}", 1, "w")
        b.stub(low[f"S{i}"], f"S{i}", 1, "e")
        b.stub(high[f"A{i}"], f"A{i+4}", 1, "w")
        b.stub(high[f"B{i}"], f"Bx{i+4}", 1, "w")
        b.stub(high[f"S{i}"], f"S{i+4}", 1, "e")
    b.stub(low["C0"], "CinS", 1, "w")
    b.stub(low["C4"], "C4L", 1, "e")
    b.stub(high["C0"], "C4L", 1, "w")
    b.stub(high["C4"], "Cout", 1, "e")
    for i in range(8):
        b.gate_io("XOR Gate", (800, 200 + i * 90), 2, 1, [f"B{i}", "Sub"], f"Bx{i}")
    b.gate_io("XOR Gate", (800, 1000), 2, 1, ["Cin", "Sub"], "CinS")
    b.gate_io("XOR Gate", (800, 1120), 2, 1, ["A7", "Bx7"], "t_of1")
    b.gate_io("NOT Gate", (800, 1200), 1, 1, ["t_of1"], "t_of2")
    b.gate_io("XOR Gate", (1060, 1120), 2, 1, ["A7", "S7"], "t_of3")
    b.gate_io("AND Gate", (1060, 1200), 2, 1, ["t_of2", "t_of3"], "OF")
    return b


# ---------------------------------------------------------------- 组装
def main():
    ap = argparse.ArgumentParser(description="实验2 加法器生成器（2.15.0.2）")
    ap.add_argument("--src", default="需求/加法器验证电路.circ",
                    help="给定的验证电路（相对当前目录）")
    ap.add_argument("--out", default="实验2 构建加法器.circ",
                    help="输出文件（相对当前目录）")
    args = ap.parse_args()

    body = open(args.src, encoding="utf-8").read().split("?>", 1)[1].lstrip("\n")

    blocks = {
        "半加器": build_half(),
        "全加器": build_full(HALF_APP.offsets()),
        "4位全加器": build_fa4(FA_APP.offsets()),
        "并行进位器": build_cla(),
        "4并行加法器": build_fast4(CLA_APP.offsets()),
        "16位验证": build_16bit(FAST4_APP.offsets(), CLA_APP.offsets()),
        "8位串行加法器验证电路": build_8bit(FA4_APP.offsets()),
    }

    errs = []
    for name, b in blocks.items():
        e = b.check()
        if e:
            errs.append(f"[{name}]")
            errs += ["  " + s for s in e]
    if errs:
        print("\n".join(errs))
        raise SystemExit("自检未通过，未写文件")

    for name, b in blocks.items():
        tag = '<circuit name="%s">' % name
        body_xml = b.to_body()
        if tag in body:
            start = body.index(tag)
            end = body.index("</circuit>", start) + len("</circuit>")
            blk = body[start:end].replace("  </circuit>", body_xml + "\n  </circuit>")
            body = body[:start] + blk + body[end:]
        else:
            body = body.replace("</project>",
                                '  <circuit name="%s">\n%s\n  </circuit>\n</project>'
                                % (name, body_xml))

    for name, app in (("半加器", HALF_APP), ("全加器", FA_APP), ("4位全加器", FA4_APP),
                      ("并行进位器", CLA_APP), ("4并行加法器", FAST4_APP)):
        tag = '<circuit name="%s">' % name
        start = body.index(tag)
        end = body.index("</circuit>", start) + len("</circuit>")
        blk = re.sub(r"\n?\s*<appear>.*?</appear>", "", body[start:end], flags=re.S)
        blk = blk.replace("  </circuit>", app.to_xml() + "\n  </circuit>")
        body = body[:start] + blk + body[end:]

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + body
    open(args.out, "w", encoding="utf-8", newline="\n").write(xml)
    print("written", args.out)
    print("circuits:", [c.get("name") for c in ET.fromstring(xml).findall("circuit")])


if __name__ == "__main__":
    main()
