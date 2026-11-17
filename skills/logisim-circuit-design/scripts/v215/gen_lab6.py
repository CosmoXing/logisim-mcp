# -*- coding: utf-8 -*-
"""实验6 存储器实验（Logisim-ITA 2.15.0.2）生成器。

在素材 `实验6 汉字显示（素材）.circ`（2.7.1 格式，2.15 可直接打开）上：
  1. 16*16点阵字库：把 D1 的 4 片 4K×32 ROM 按字扩展接成 16K×32
     - 14 位地址拆成低 12 位 / 高 2 位
     - 低 12 位接 4 片 ROM 的 A
     - 高 2 位作 32 位 4:1 选择器的 sel
     - 4 片 ROM 的 Q 进选择器，输出接 D1
  2. 16*16姓名显示：计数器 + 16×16 ROM（机内码）+ 机内转区位码 + 16*16字库 + 点阵
  3. 新增「存储器扩展问答」电路，标注两道扩展题的答案

用法（在实验目录下运行）：
    python gen_lab6.py --src "需求/实验6 汉字显示（素材）.circ" ^
        --out "实验6 存储器实验.circ"
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 例：东北大学计算机硬件（GB2312 机内码）
CODES = ["B6AB", "B1B1", "B4F3", "D1A7", "BCC6", "CBE3", "BBFA",
         "D3B2", "BCFE"]
CODES += ["0000"] * (16 - len(CODES))


def loc(x, y):
    return f"({x},{y})"


def add_comp(circ, lib, x, y, name, attrs):
    """在 <appear> 前插入一个 comp；attrs 为 [(k, v)]，contents 用 text。"""
    comp = ET.Element("comp", {"lib": str(lib), "loc": loc(x, y), "name": name})
    for k, v in attrs:
        a = ET.SubElement(comp, "a", {"name": k})
        if k == "contents":
            a.text = v
        else:
            a.set("val", str(v))
    appear = circ.find("appear")
    idx = list(circ).index(appear) if appear is not None else len(circ)
    circ.insert(idx, comp)
    return comp


def add_sub(circ, x, y, name):
    """插入子电路实例（2.x 的 <comp> 不写 lib）。"""
    comp = ET.Element("comp", {"loc": loc(x, y), "name": name})
    appear = circ.find("appear")
    idx = list(circ).index(appear) if appear is not None else len(circ)
    circ.insert(idx, comp)
    return comp


def add_wire(circ, a, b):
    w = ET.Element("wire", {"from": loc(*a), "to": loc(*b)})
    appear = circ.find("appear")
    idx = list(circ).index(appear) if appear is not None else len(circ)
    circ.insert(idx, w)


def add_tunnel(circ, x, y, label, width, facing="east"):
    add_comp(circ, 0, x, y, "Tunnel",
             [("facing", facing), ("width", width), ("label", label)])


def add_splitter(circ, x, y, incoming, fanout, groups, facing="east"):
    attrs = [("facing", facing), ("fanout", fanout), ("incoming", incoming),
             ("appear", "center")]
    attrs += [(f"bit{i}", groups[i]) for i in range(incoming)]
    add_comp(circ, 0, x, y, "Splitter", attrs)


def add_text(circ, x, y, text, bold=False):
    font = "SansSerif bold 14" if bold else "Dialog plain 12"
    add_comp(circ, 6, x, y, "Text", [("text", text), ("font", font)])


# ---------------------------------------------------------------- D1 字扩展

def extend_d1(circ):
    """16*16点阵字库：4 片 4K×32 → 16K×32。"""
    # 地址总线（14 位）取样点：Subtractor(750,770) 输出总线在 (980,770)
    add_wire(circ, (980, 770), (980, 850))
    add_tunnel(circ, 980, 850, "ADDR14", 14, "south")

    # 14 位拆低 12 / 高 2
    add_splitter(circ, 1180, 470, 14, 2, [0] * 12 + [1] * 2, "south")
    add_wire(circ, (1180, 470), (1180, 450))
    add_tunnel(circ, 1180, 450, "ADDR14", 14, "north")
    add_wire(circ, (1180, 490), (1180, 510))
    add_tunnel(circ, 1180, 510, "A_LO", 12, "south")
    add_wire(circ, (1170, 490), (1170, 510))
    add_tunnel(circ, 1170, 510, "A_HI", 2, "south")

    # 4 片 ROM 的低 12 位地址
    for x in (140, 350, 560, 770):
        add_wire(circ, (x, 370), (x - 20, 370))
        add_tunnel(circ, x - 20, 370, "A_LO", 12, "west")

    # 4 片 ROM 的 Q
    for i, x in enumerate((280, 490, 700, 910)):
        add_wire(circ, (x, 370), (x + 20, 370))
        add_tunnel(circ, x + 20, 370, f"B{i}", 32, "east")

    # 32 位 4:1 选择器
    add_comp(circ, 2, 1120, 370, "Multiplexer",
             [("select", 2), ("width", 32), ("enable", "false")])
    for i, y in enumerate((350, 360, 370, 380)):
        add_wire(circ, (1080, y), (1060, y))
        add_tunnel(circ, 1060, y, f"B{i}", 32, "west")
    add_wire(circ, (1100, 390), (1100, 420))
    add_tunnel(circ, 1100, 420, "A_HI", 2, "south")
    add_wire(circ, (1120, 370), (1140, 370))
    add_tunnel(circ, 1140, 370, "D1", 32, "east")

    add_text(circ, 760, 300,
             "D1 字扩展：4×4K×32 → 16K×32（低 12 位地址并联，高 2 位选片）",
             bold=True)


# ---------------------------------------------------------------- 姓名显示

def build_name_display(circ, rom_template):
    """16*16姓名显示：4 位计数器 → 16×16 ROM → 机内转区位码 → 16*16字库 → 点阵。"""
    add_comp(circ, 0, 80, 250, "Clock",
             [("facing", "north"), ("label", "时钟"),
              ("labelloc", "south"), ("labelfont", "Dialog plain 12")])
    add_comp(circ, 4, 100, 210, "Counter",
             [("width", 4), ("max", "0xf"), ("labelfont", "Dialog plain 12")])
    # 直接复用素材里已工作的 ROM 元素（新造的 ROM 在 2.15 下会输出 U）
    rom = copy.deepcopy(rom_template)
    for a in rom.findall("a"):
        if a.get("name") == "contents":
            a.text = "addr/data: 4 16\n" + " ".join(CODES) + "\n"
    appear = circ.find("appear")
    idx = list(circ).index(appear) if appear is not None else len(circ)
    circ.insert(idx, rom)
    add_sub(circ, 380, 50, "例：机内转区位码")
    add_sub(circ, 430, 40, "16*16点阵字库")

    add_comp(circ, 5, 700, 20, "DotMatrix",
             [("inputtype", "row"), ("matrixcols", 16), ("matrixrows", 16),
              ("color", "#00c000"), ("offcolor", "#bfbfbf"),
              ("dotshape", "circle")])

    # 8 个 32→2 分线器：每片 D 拆成两行
    for i in range(8):
        add_splitter(circ, 670, 30 + 20 * i, 32, 2,
                     [0] * 16 + [1] * 16, "east")

    # 计数器 / ROM / 转换
    add_wire(circ, (80, 250), (80, 230))
    add_wire(circ, (100, 210), (130, 210))
    add_wire(circ, (270, 210), (300, 210))
    add_wire(circ, (300, 210), (300, 60))
    add_wire(circ, (300, 60), (340, 60))

    # 机内转区位码 → 16*16字库
    add_wire(circ, (380, 50), (420, 50))
    add_tunnel(circ, 420, 50, "QW", 7, "east")
    add_wire(circ, (380, 70), (420, 70))
    add_tunnel(circ, 420, 70, "WH", 7, "east")
    add_wire(circ, (430, 80), (410, 80))
    add_tunnel(circ, 410, 80, "QW", 7, "west")
    add_wire(circ, (430, 90), (410, 90))
    add_tunnel(circ, 410, 90, "WH", 7, "west")

    # 字库 D0~D7 → 分线器总线
    for i in range(8):
        y = 50 + 10 * i
        add_wire(circ, (460, y), (480, y))
        add_tunnel(circ, 480, y, f"D{i}", 32, "east")
        sy = 30 + 20 * i
        add_wire(circ, (670, sy), (650, sy))
        add_tunnel(circ, 650, sy, f"D{i}", 32, "west")
        # 两条 16 位行
        add_wire(circ, (690, sy - 10), (700, sy - 10))
        add_wire(circ, (690, sy), (700, sy))

    add_text(circ, 86, 183, "计数器")
    add_text(circ, 204, 164, "GB2312 机内码", bold=True)
    add_text(circ, 330, 120, "机内转区位码")
    add_text(circ, 430, 160, "16*16字库")
    add_text(circ, 700, 190, "16×16 点阵显示")
    add_text(circ, 240, 344,
             "ROM 内为「东北大学计算机硬件」的机内码；"
             "换成自己的姓名/学院时，替换这 16 个 16 位数据即可")


# ---------------------------------------------------------------- 问答

def build_qa(root):
    c = ET.Element("circuit", {"name": "存储器扩展问答"})
    add_text(c, 300, 60, "实验6 存储器扩展 问答", bold=True)
    add_text(c, 300, 140,
             "① 位数扩展：地址位数不变，数据位由 16 位扩展到 32 位，"
             "即 256×16 → 256×32。", bold=False)
    add_text(c, 300, 200,
             "② 扩展后地址总线 8 位；每个地址单元 32 位二进制数据。",
             bold=False)
    add_text(c, 300, 280,
             "位数字数同时扩展：1K×16 → 4K×32，需 (4K/1K)×(32/16)=8 片，"
             "分 4 组、每组 2 片；", bold=False)
    add_text(c, 300, 330,
             "地址总线由 10 位扩展到 12 位（1K=2^10，4K=2^12）。",
             bold=False)
    add_text(c, 300, 410,
             "16×16 点阵字库：D1 的 4 片 4K×32 按字扩展为 16K×32；"
             "低 12 位地址并联，高 2 位经 4:1 选择器选片。", bold=False)
    root.append(c)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="实验6 存储器实验生成器（2.15.0.2）")
    ap.add_argument("--src", default="需求/实验6 汉字显示（素材）.circ")
    ap.add_argument("--out", default="实验6 存储器实验.circ")
    args = ap.parse_args()

    tree = ET.parse(args.src)
    root = tree.getroot()
    circuits = {c.get("name"): c for c in root.findall("circuit")}
    for need in ("16*16点阵字库", "16*16姓名显示", "例：机内转区位码"):
        if need not in circuits:
            raise SystemExit(f"素材缺少电路：{need}")

    extend_d1(circuits["16*16点阵字库"])
    rom_template = next(e for e in circuits["例：32*32汉字显示电路"].findall("comp")
                        if e.get("name") == "ROM")
    build_name_display(circuits["16*16姓名显示"], rom_template)
    build_qa(root)

    # 主电路改为姓名显示
    main = root.find("main")
    if main is not None:
        main.set("name", "16*16姓名显示")

    tree.write(args.out, encoding="utf-8", xml_declaration=True)
    # ET 会写单引号/自闭合差异；统一补齐换行
    text = open(args.out, encoding="utf-8").read()
    if not text.endswith("\n"):
        text += "\n"
    open(args.out, "w", encoding="utf-8", newline="\n").write(text)
    print("已写", args.out, len(text), "bytes")


if __name__ == "__main__":
    main()
