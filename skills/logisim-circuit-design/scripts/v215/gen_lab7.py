# -*- coding: utf-8 -*-
"""实验7 I/O 接口实验：8 位奇校验编码/解码（Logisim-ITA 2.15.0.2）。

素材 `实验7 校验电路（素材）.circ` 是 2.7.1 工程，提供 `9位随机干扰` 子电路，
`main` 为空。本生成器补：

  - `2k+1奇校验`：9 输入 XOR 树，输出 1 表示 9 位中 1 的个数为奇数；
  - `奇校验编码`：8 位数据 D → 9 位 {奇校验位, D}，保证 9 位中 1 的个数为奇数；
  - `奇校验解码`：9 位接收 → 8 位数据 + 正确/错误；
  - `main`：数据 → 编码 → 素材 9位随机干扰 → 解码 → 输出/正确/错误 LED。

用法（在实验目录下运行）：
    python gen_lab7.py --src "需求/实验7 校验电路（素材）.circ" ^
        --out "实验7 IO接口实验.circ"
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board215 import Appearance, Board  # noqa: E402

# ---------------------------------------------------------------- 外观

ODD_APP = Appearance(
    rect=(0, 20, 200, 520), anchor=(100, 260), label="2k+1 奇校验",
    label_pos=(100, 45),
    ports=[(f"X{i}", f"120,{100 + 60 * i}", 0, 60 + 50 * i, 8)
           for i in range(9)] +
          [("Y", "1600,400", 200, 260, 10)])

ENC_APP = Appearance(
    rect=(0, 20, 220, 140), anchor=(110, 80), label="奇校验编码",
    label_pos=(110, 45),
    ports=[("D", "120,200", 0, 60, 8), ("Y", "1500,300", 220, 60, 9)])

DEC_APP = Appearance(
    rect=(0, 20, 220, 160), anchor=(110, 90), label="奇校验解码",
    label_pos=(110, 45),
    ports=[("A", "120,300", 0, 80, 8), ("D", "1500,200", 220, 50, 8),
           ("正确", "1500,300", 220, 90, 8),
           ("错误", "1500,400", 220, 120, 8)])

SCRAM_OFF = {"9位输入": (-30, 0), "随机加扰屏蔽字": (0, -20),
             "加扰后数据": (30, 0), "CLK": (-10, 20)}


# ---------------------------------------------------------------- 2k+1

def build_odd():
    b = Board("2k+1奇校验")
    for i in range(9):
        y = 100 + 60 * i
        b.pin((120, y), f"X{i}")
        b.lead((120, y), f"X{i}", 1, "e")
    b.pin((1600, 400), "Y", facing="west", output=True)

    b.gate_io("XOR Gate", (500, 160), 2, 1, ["X0", "X1"], "p01")
    b.gate_io("XOR Gate", (500, 320), 2, 1, ["X2", "X3"], "p23")
    b.gate_io("XOR Gate", (500, 480), 2, 1, ["X4", "X5"], "p45")
    b.gate_io("XOR Gate", (500, 640), 2, 1, ["X6", "X7"], "p67")
    b.gate_io("XOR Gate", (800, 240), 2, 1, ["p01", "p23"], "p0123")
    b.gate_io("XOR Gate", (800, 560), 2, 1, ["p45", "p67"], "p4567")
    b.gate_io("XOR Gate", (1100, 400), 2, 1, ["p0123", "p4567"], "p07")
    b.gate_io("XOR Gate", (1400, 400), 2, 1, ["p07", "X8"], "Y")
    b.lead((1600, 400), "Y", 1, "w")

    b.text((700, 780), "9 输入 XOR 树：Y=1 表示 9 位中 1 的个数为奇数", bold=True)
    return b


# ---------------------------------------------------------------- 编码

def build_encoder():
    b = Board("奇校验编码")
    b.pin((120, 200), "D", width=8)
    b.pin((1500, 300), "Y", facing="west", width=9, output=True)

    b.lead((120, 200), "DIN", 8, "e")
    bus, bits = b.split((300, 300), 8, "south")
    b.stub(bus, "DIN", 8, "n")
    b.fan_bits(bits, "d")

    odd = b.sub("2k+1奇校验", (800, 400), ODD_APP.offsets())
    for i in range(8):
        b.stub(odd[f"X{i}"], f"d{i}", 1, "w")
    b.const((600, 650), 1, 1)
    b.stub((600, 650), "ONE", 1, "e")
    b.stub(odd["X8"], "ONE", 1, "w")
    b.stub(odd["Y"], "PAR", 1, "e")

    # 9 位合并：bit0..7 = d0..d7，bit8 = PAR
    bus9, parts = b.splitn((1200, 500), 9, 9, list(range(9)), "south")
    b.stub(bus9, "Y9", 9, "n")
    for i in range(8):
        b.stub(parts[i], f"d{i}", 1, "s")
    b.stub(parts[8], "PAR", 1, "s")

    b.lead((1500, 300), "Y9", 9, "w")
    b.text((700, 760), "Y = {奇校验位, D7..D0}；奇校验位保证 9 位中 1 的个数为奇数",
           bold=True)
    return b


# ---------------------------------------------------------------- 解码

def build_decoder():
    b = Board("奇校验解码")
    b.pin((120, 300), "A", width=9)
    b.pin((1500, 200), "D", facing="west", width=8, output=True)
    b.pin((1500, 300), "正确", facing="west", output=True)
    b.pin((1500, 400), "错误", facing="west", output=True)

    b.lead((120, 300), "AIN", 9, "e")
    bus, bits = b.split((350, 400), 9, "south")
    b.stub(bus, "AIN", 9, "n")
    b.fan_bits(bits, "a")

    odd = b.sub("2k+1奇校验", (850, 500), ODD_APP.offsets())
    for i in range(9):
        b.stub(odd[f"X{i}"], f"a{i}", 1, "w")
    b.stub(odd["Y"], "POK", 1, "e")

    # 低 8 位还原为数据
    bus8, parts = b.splitn((1250, 700), 8, 8, list(range(8)), "south")
    b.stub(bus8, "DOUT", 8, "n")
    for i in range(8):
        b.stub(parts[i], f"a{i}", 1, "s")

    b.gate_io("NOT Gate", (1100, 500), 1, 1, ["POK"], "ERR")

    b.lead((1500, 200), "DOUT", 8, "w")
    b.lead((1500, 300), "POK", 1, "w")
    b.lead((1500, 400), "ERR", 1, "w")
    b.text((700, 820), "2k+1 输出 POK=1 表示传输正确；ERR=NOT POK", bold=True)
    return b


# ---------------------------------------------------------------- 主电路

def build_main():
    b = Board("main")
    b.pin((120, 150), "数据", width=8)
    b.pin((120, 300), "CLK")
    b.pin((1800, 150), "输出", facing="west", width=8, output=True)
    b.pin((1800, 250), "正确", facing="west", output=True)
    b.pin((1800, 350), "错误", facing="west", output=True)
    b.pin((1800, 450), "屏蔽字", facing="west", width=9, output=True)
    b.pin((1800, 550), "传输数据", facing="west", width=9, output=True)

    b.lead((120, 150), "DIN", 8, "e")
    b.lead((120, 300), "CLK", 1, "e")

    enc = b.sub("奇校验编码", (600, 200), ENC_APP.offsets())
    b.stub(enc["D"], "DIN", 8, "w")
    b.stub(enc["Y"], "TX9", 9, "e")

    scr = b.sub("9位随机干扰", (1100, 300), SCRAM_OFF)
    b.stub(scr["9位输入"], "TX9", 9, "w")
    b.stub(scr["随机加扰屏蔽字"], "MASK", 9, "n")
    b.stub(scr["加扰后数据"], "RX9", 9, "e")
    b.lead(scr["CLK"], "CLK", 1, "s", 60)

    dec = b.sub("奇校验解码", (1500, 300), DEC_APP.offsets())
    b.stub(dec["A"], "RX9", 9, "w")
    b.stub(dec["D"], "DOUT", 8, "e")
    b.stub(dec["正确"], "POK", 1, "e")
    b.stub(dec["错误"], "ERR", 1, "e")

    b.lead((1800, 150), "DOUT", 8, "w")
    b.lead((1800, 250), "POK", 1, "w")
    b.lead((1800, 350), "ERR", 1, "w")
    b.lead((1800, 450), "MASK", 9, "w")
    b.lead((1800, 550), "RX9", 9, "w")

    # LED：绿色传输正确、红色错误（LED 本体在 main 末尾以 XML 追加）
    b.tunnel((1470, 400), "POK", 1, "east")
    b.wire((1470, 400), (1450, 400))
    b.tunnel((1470, 450), "ERR", 1, "east")
    b.wire((1470, 450), (1450, 450))
    b.text((1360, 410), "传输正确")
    b.text((1360, 460), "错误")
    b.text((1040, 360), "9位随机干扰")
    b.text((820, 120), "8 位奇校验编码/解码（素材：9位随机干扰）", bold=True)
    return b


LED_XML = """
    <comp lib="5" loc="(1450,400)" name="LED">
      <a name="facing" val="west"/>
      <a name="color" val="#00ff00"/>
      <a name="label" val="LED_OK"/>
      <a name="labelloc" val="south"/>
      <a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="5" loc="(1450,450)" name="LED">
      <a name="facing" val="west"/>
      <a name="color" val="#ff0000"/>
      <a name="label" val="LED_ERR"/>
      <a name="labelloc" val="south"/>
      <a name="labelfont" val="Dialog plain 12"/>
    </comp>"""


# ---------------------------------------------------------------- 组装

def extract_circuit(src: str, name: str) -> str:
    start = src.index(f'<circuit name="{name}">')
    end = src.index("</circuit>", start) + len("</circuit>")
    return src[start:end]


def main():
    ap = argparse.ArgumentParser(description="实验7 奇校验编码/解码生成器（2.15.0.2）")
    ap.add_argument("--src", default="需求/实验7 校验电路（素材）.circ")
    ap.add_argument("--out", default="实验7 IO接口实验.circ")
    args = ap.parse_args()

    src = open(args.src, encoding="utf-8").read()
    blocks = [
        ("2k+1奇校验", build_odd(), ODD_APP),
        ("奇校验编码", build_encoder(), ENC_APP),
        ("奇校验解码", build_decoder(), DEC_APP),
        ("main", build_main(), None),
    ]

    errs = []
    for name, board, _ in blocks:
        errs += [f"{name}: {e}" for e in board.check()]
    if errs:
        print("自检失败，未写文件：")
        for e in errs:
            print("  " + e)
        return 1

    head = src.split('<circuit name="')[0]
    scrambler = extract_circuit(src, "9位随机干扰")

    out = [head, scrambler]
    for name, board, app in blocks:
        body = board.to_body()
        # 2.15 的 XOR Gate 属性顺序/缺省 size 会让它变成同或；
        # 按素材里的顺序重写：width, size=30, inputs, xor=odd
        body = re.sub(
            r'<comp lib="1" loc="\(([^)]+)\)" name="XOR Gate">\s*'
            r'<a name="inputs" val="(\d+)"/>\s*'
            r'<a name="width" val="(\d+)"/>\s*</comp>',
            lambda m: (
                f'<comp lib="1" loc="({m.group(1)})" name="XOR Gate">'
                f'<a name="width" val="{m.group(3)}"/>'
                f'<a name="size" val="30"/>'
                f'<a name="inputs" val="{m.group(2)}"/>'
                f'<a name="xor" val="odd"/></comp>'
            ),
            body)
        if name == "main":
            body += LED_XML
        out.append(f'  <circuit name="{name}">')
        out.append(body)
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
