# -*- coding: utf-8 -*-
"""实验7 第二组：哑终端（TTY）——存储器内容、姓名显示、键盘输入。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board215 import Board, cnt_ports

CIRC = r"实验7 IO接口实验.circ"


def raw_clock(x, y, label="时钟"):
    return ('    <comp lib="0" loc="(%d,%d)" name="Clock">\n'
            '      <a name="facing" val="north"/>\n'
            '      <a name="highDuration" val="1"/>\n'
            '      <a name="lowDuration" val="1"/>\n'
            '      <a name="label" val="%s"/>\n'
            '      <a name="labelloc" val="west"/>\n'
            '    </comp>' % (x, y, label))


def raw_counter(x, y, width=4, maxval=15):
    return ('    <comp lib="4" loc="(%d,%d)" name="Counter">\n'
            '      <a name="width" val="%d"/>\n'
            '      <a name="max" val="0x%x"/>\n'
            '      <a name="ongoal" val="wrap"/>\n'
            '      <a name="trigger" val="rising"/>\n'
            '      <a name="behavior" val="old"/>\n'
            '    </comp>' % (x, y, width, maxval))


def raw_tty(x, y, bits=7):
    w = 16 if bits == 16 else 7
    return ('    <comp lib="5" loc="(%d,%d)" name="TTY">\n'
            '      <a name="Char bit width" val="%d"/>\n'
            '      <a name="rows" val="8"/>\n'
            '      <a name="cols" val="32"/>\n'
            '      <a name="trigger" val="rising"/>\n'
            '    </comp>' % (x, y, w))


def raw_kbd(x, y, bits=7):
    w = 16 if bits == 16 else 7
    return ('    <comp lib="5" loc="(%d,%d)" name="Keyboard">\n'
            '      <a name="Char bit width" val="%d"/>\n'
            '      <a name="buflen" val="32"/>\n'
            '      <a name="trigger" val="rising"/>\n'
            '    </comp>' % (x, y, w))


def gnd(b, loc, label="GND"):
    b.const(loc, 1, 0)
    b.wire(loc, (loc[0] + 40, loc[1]))
    b.tunnel((loc[0] + 40, loc[1]), label, 1, "east")


def vcc(b, loc, label):
    b.const(loc, 1, 1)
    b.wire(loc, (loc[0] + 40, loc[1]))
    b.tunnel((loc[0] + 40, loc[1]), label, 1, "east")


# ---------------------------------------------------------------- 存储器内容显示
def build_mem_tty():
    b = Board("存储器内容显示（TTY）")
    b.raw = ""
    text = "Hello World!2024"
    data = " ".join("%02x" % ord(c) for c in text)
    b.raw += raw_clock(220, 700)
    b.raw += raw_counter(560, 600, 4, 15)
    c = cnt_ports((560, 600))
    b.stub(c["clk"], "CLK", 1, "w")
    b.stub(c["Q"], "CNT", 4, "e")
    gnd(b, (400, 780), "GND")

    rom = b.rom((820, 600), addr_width=4, data_width=7, contents=data)
    b.stub(rom["A"], "CNT", 4, "w")
    b.stub(rom["D"], "DATA", 7, "e")
    b.stub(rom["cs"], "GND", 1, "w")

    b.raw += raw_tty(1280, 600, 7)
    b.wire((1280, 590), (1240, 590)); b.tunnel((1240, 590), "DATA", 7, "west")
    b.wire((1280, 600), (1240, 600)); b.tunnel((1240, 600), "CLK", 1, "west")
    b.wire((1290, 610), (1290, 640)); b.wire((1290, 640), (1240, 640))
    b.tunnel((1240, 640), "WR", 1, "west")
    b.wire((1300, 610), (1300, 660)); b.wire((1300, 660), (1240, 660))
    b.tunnel((1240, 660), "RST", 1, "west")
    gnd(b, (1000, 780), "RST")
    vcc(b, (1000, 840), "WR")

    b.wire((220, 700), (220, 720))
    b.wire((220, 720), (260, 720))
    b.tunnel((260, 720), "CLK", 1, "east")
    b.text((700, 880), "定时器（Clock+4 位计数器）逐地址读取 ROM，把 8 位 ASCII 送到哑终端（数据位宽 8）", bold=True)
    return b


# ---------------------------------------------------------------- 姓名显示
def build_name_tty():
    b = Board("姓名显示（TTY）")
    b.raw = ""
    text = "周企航 冶金学院 20243281"
    data = " ".join("%04x" % ord(ch) for ch in text)
    b.raw += raw_clock(220, 700)
    b.raw += raw_counter(560, 600, 5, 31)
    c = cnt_ports((560, 600))
    b.stub(c["clk"], "CLK", 1, "w")
    b.stub(c["Q"], "CNT", 5, "e")
    gnd(b, (400, 780), "GND")

    rom = b.rom((820, 600), addr_width=5, data_width=16, contents=data)
    b.stub(rom["A"], "CNT", 5, "w")
    b.stub(rom["D"], "DATA", 16, "e")
    b.stub(rom["cs"], "GND", 1, "w")

    b.raw += raw_tty(1280, 600, 16)
    b.wire((1280, 590), (1240, 590)); b.tunnel((1240, 590), "DATA", 16, "west")
    b.wire((1280, 600), (1240, 600)); b.tunnel((1240, 600), "CLK", 1, "west")
    b.wire((1290, 610), (1290, 640)); b.wire((1290, 640), (1240, 640))
    b.tunnel((1240, 640), "WR", 1, "west")
    b.wire((1300, 610), (1300, 660)); b.wire((1300, 660), (1240, 660))
    b.tunnel((1240, 660), "RST", 1, "west")
    gnd(b, (1000, 780), "RST")
    vcc(b, (1000, 840), "WR")

    b.wire((220, 700), (220, 720))
    b.wire((220, 720), (260, 720))
    b.tunnel((260, 720), "CLK", 1, "east")
    b.text((700, 900), "ROM 内存「周企航 冶金学院 20243281」的 UTF-16（大端）编码；哑终端数据位宽选 UTF-16 (16-bit)", bold=True)
    return b


# ---------------------------------------------------------------- 键盘输入
def build_kbd_tty():
    b = Board("键盘输入显示（TTY）")
    b.raw = ""
    b.raw += raw_clock(220, 700)
    b.raw += raw_kbd(520, 620, 7)

    b.wire((520, 620), (480, 620)); b.tunnel((480, 620), "CLK", 1, "west")
    b.wire((530, 630), (500, 630)); b.wire((500, 630), (500, 680))
    b.tunnel((500, 680), "RST", 1, "south")
    b.wire((540, 630), (540, 700)); b.tunnel((540, 700), "RD", 1, "south")
    b.wire((650, 630), (650, 560)); b.wire((650, 560), (700, 560))
    b.tunnel((700, 560), "AVL", 1, "east")
    b.wire((660, 630), (660, 580)); b.wire((660, 580), (700, 580))
    b.tunnel((700, 580), "KBD", 7, "east")

    b.raw += raw_tty(1100, 620, 7)
    b.wire((1100, 610), (1060, 610)); b.wire((1060, 610), (1060, 580))
    b.tunnel((1060, 580), "KBD", 7, "west")
    b.wire((1100, 620), (1060, 620)); b.tunnel((1060, 620), "CLK", 1, "west")
    b.wire((1110, 630), (1110, 660)); b.wire((1110, 660), (1060, 660))
    b.tunnel((1060, 660), "AVL", 1, "west")
    b.wire((1120, 630), (1120, 700)); b.wire((1120, 700), (1060, 700))
    b.tunnel((1060, 700), "RST", 1, "west")

    gnd(b, (400, 780), "RST")
    vcc(b, (400, 840), "RD")
    b.wire((220, 700), (220, 720))
    b.wire((220, 720), (260, 720))
    b.tunnel((260, 720), "CLK", 1, "east")
    b.text((700, 880), "键盘缓冲非空（AVL=1）时按键值直接写入哑终端；RD 常 1 表示每拍弹出一个字符", bold=True)
    return b


def wrap_circuit(board):
    body = board.to_body()
    if board.raw:
        body = body + "\n" + board.raw
    return ("  <circuit name=\"%s\">\n"
            "    <a name=\"circuit\" val=\"%s\"/>\n"
            "    <a name=\"clabel\" val=\"\"/>\n"
            "    <a name=\"clabelup\" val=\"east\"/>\n"
            "    <a name=\"clabelfont\" val=\"SansSerif plain 12\"/>\n"
            "    <a name=\"clabelcolor\" val=\"#000000\"/>\n"
            "%s\n  </circuit>\n") % (board.name, board.name, body)


def main():
    boards = [build_mem_tty(), build_name_tty(), build_kbd_tty()]
    for b in boards:
        errs = b.check()
        print(b.name, "check:", len(errs))
        for e in errs[:6]:
            print("  ", e)
        if errs:
            raise SystemExit("布线自检失败 " + b.name)
    xml = open(CIRC, encoding="utf-8").read()
    if "存储器内容显示（TTY）" in xml:
        raise SystemExit("已存在同名电路")
    xml = xml.replace("</project>", "".join(wrap_circuit(b) for b in boards) + "</project>")
    open(CIRC, "w", encoding="utf-8", newline="\n").write(xml)
    print("written")


main()