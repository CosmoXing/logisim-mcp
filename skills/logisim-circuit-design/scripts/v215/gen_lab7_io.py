# -*- coding: utf-8 -*-
"""实验7 第一组：LED计数器、按键编码器、七段显示驱动、主链电路。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board215 import Board, Appearance

CIRC = r"实验7 IO接口实验.circ"

# ---------------------------------------------------------------- 外观（anchor = 左上角第一个输入端口）
LED_APP = Appearance(
    rect=(120, 40, 760, 820), anchor=(120, 100),
    label="LED计数", label_pos=(500, 70),
    ports=[("a", "120,100", 120, 100, 8), ("b", "120,160", 120, 160, 8),
           ("c", "120,220", 120, 220, 8), ("d", "120,280", 120, 280, 8),
           ("e", "120,340", 120, 340, 8),
           ("w", "800,280", 880, 280, 8), ("x", "800,420", 880, 420, 8),
           ("y", "800,560", 880, 560, 8), ("z", "800,700", 880, 700, 8),
           ("u", "800,840", 880, 840, 8)])

ENC_APP = Appearance(
    rect=(120, 40, 760, 820), anchor=(120, 100),
    label="按键编码器", label_pos=(500, 70),
    ports=[("a", "120,100", 120, 100, 8), ("b", "120,160", 120, 160, 8),
           ("c", "120,220", 120, 220, 8), ("d", "120,280", 120, 280, 8),
           ("e", "120,340", 120, 340, 8),
           ("C0", "800,200", 880, 200, 8), ("C1", "800,400", 880, 400, 8),
           ("C2", "800,600", 880, 600, 8), ("C3", "800,800", 880, 800, 8)])

SEG_APP = Appearance(
    rect=(80, 40, 1400, 900), anchor=(120, 100),
    label="七段显示驱动", label_pos=(700, 70),
    ports=[("In1", "120,100", 120, 100, 8), ("In2", "120,180", 120, 180, 8),
           ("In3", "120,260", 120, 260, 8), ("In4", "120,340", 120, 340, 8),
           ("g", "1480,200", 1480, 200, 8), ("f", "1480,320", 1480, 320, 8),
           ("a", "1480,440", 1480, 440, 8), ("b", "1480,560", 1480, 560, 8),
           ("e", "1480,680", 1480, 680, 8), ("d", "1480,800", 1480, 800, 8),
           ("c", "1480,920", 1480, 920, 8)])

# 真值表：各段点亮的数字
SEGMENTS = {
    "g": {0, 2, 3, 5, 6, 8, 9},
    "f": {0, 1, 3, 4, 5, 6, 7, 8, 9},
    "a": {0, 2, 3, 5, 6, 7, 8, 9},
    "b": {0, 1, 2, 3, 4, 7, 8, 9},
    "e": {0, 2, 6, 8},
    "d": {0, 2, 3, 5, 6, 8, 9},
    "c": {0, 1, 3, 4, 5, 6, 7, 8, 9},
}


def raw_button(x, y, label):
    return ('    <comp lib="5" loc="(%d,%d)" name="Button">\n'
            '      <a name="facing" val="east"/>\n'
            '      <a name="label" val="%s"/>\n'
            '      <a name="labelloc" val="north"/>\n'
            '      <a name="labelfont" val="SansSerif bold 14"/>\n'
            '    </comp>' % (x, y, label))


def raw_led(x, y, label, color="#e00000"):
    return ('    <comp lib="5" loc="(%d,%d)" name="LED">\n'
            '      <a name="facing" val="west"/>\n'
            '      <a name="color" val="%s"/>\n'
            '      <a name="offcolor" val="#404040"/>\n'
            '      <a name="active" val="true"/>\n'
            '      <a name="label" val="%s"/>\n'
            '      <a name="labelloc" val="south"/>\n'
            '      <a name="labelfont" val="SansSerif plain 12"/>\n'
            '    </comp>' % (x, y, color, label))


def raw_seg(x, y):
    return ('    <comp lib="5" loc="(%d,%d)" name="7-Segment Display">\n'
            '      <a name="color" val="#e00000"/>\n'
            '      <a name="offcolor" val="#dcdcdc"/>\n'
            '      <a name="bg" val="#ffffff"/>\n'
            '      <a name="active" val="true"/>\n'
            '    </comp>' % (x, y))


# ---------------------------------------------------------------- LED计数
def build_led():
    b = Board("LED计数")
    b.raw = ""
    for i, n in enumerate("abcde"):
        y = 100 + 60 * i
        b.pin((120, y), n)
        b.lead((120, y), n, 1, "e", 60)
    for i, n in enumerate(["w", "x", "y", "z", "u"]):
        y = 280 + 140 * i
        b.pin((800, y), n, facing="west", output=True)
        b.wire((800, y), (740, y))
        b.tunnel((740, y), "e" if n == "u" else n, 1, "west")

    b.gate_io("OR Gate", (500, 700), 2, 1, ["d", "e"], "z")
    b.gate_io("OR Gate", (500, 560), 2, 1, ["c", "z"], "y")
    b.gate_io("OR Gate", (500, 420), 2, 1, ["b", "y"], "x")
    b.gate_io("OR Gate", (500, 280), 2, 1, ["a", "x"], "w")
    b.text((400, 920), "LED 数 = 按下的按键编号：w=a|b|c|d|e，x=b|c|d|e，y=c|d|e，z=d|e，u=e", bold=True)
    return b


# ---------------------------------------------------------------- 按键编码器
def build_enc():
    b = Board("按键编码器")
    b.raw = ""
    for i, n in enumerate("abcde"):
        y = 100 + 60 * i
        b.pin((120, y), n)
        b.lead((120, y), n, 1, "e", 60)
    for i, n in enumerate(["C0", "C1", "C2", "C3"]):
        y = 200 + 200 * i
        b.pin((800, y), n, facing="west", output=True)
        b.wire((800, y), (740, y))
        b.tunnel((740, y), n, 1, "west")

    b.gate_io("OR Gate", (500, 200), 3, 1, ["a", "c", "e"], "C0")
    b.gate_io("OR Gate", (500, 400), 2, 1, ["b", "c"], "C1")
    b.gate_io("OR Gate", (500, 600), 2, 1, ["d", "e"], "C2")
    b.const((500, 800), 1, 0)
    b.stub((500, 800), "C3", 1, "e")
    b.text((400, 900), "按 1/2/3/4/5 分别输出 0001/0010/0011/0100/0101（C3 恒 0）", bold=True)
    return b


def gate_stub(b, kind, loc, n, labels, out):
    ins, o = b.gate(kind, loc, n, 1)
    for p, lab in zip(ins, labels):
        b.stub(p, lab, 1, "w")
    b.stub(o, out, 1, "e")
    return o


# ---------------------------------------------------------------- 七段显示驱动
def build_seg():
    b = Board("七段显示驱动")
    b.raw = ""
    for i, n in enumerate(["In1", "In2", "In3", "In4"]):
        y = 100 + 80 * i
        b.pin((120, y), n)
        b.lead((120, y), n, 1, "e", 60)

    for i, n in enumerate(["In1", "In2", "In3", "In4"]):
        y = 100 + 80 * i
        gate_stub(b, "NOT Gate", (300, y + 240), 1, [n], "n" + n)

    for d in range(10):
        y = 700 + 90 * d
        labels = []
        for bit, name in ((3, "In1"), (2, "In2"), (1, "In3"), (0, "In4")):
            labels.append(name if (d >> bit) & 1 else "n" + name)
        gate_stub(b, "AND Gate", (600, y), 4, labels, "d%d" % d)

    for seg, oy in [("g", 200), ("f", 320), ("a", 440), ("b", 560),
                    ("e", 680), ("d", 800), ("c", 920)]:
        ds = sorted(SEGMENTS[seg])
        prev = "d%d" % ds[0]
        xs = 900
        for k, d in enumerate(ds[1:]):
            y = oy + 40 * (k % 2)
            gate_stub(b, "OR Gate", (xs, y), 2, [prev, "d%d" % d], "s_%s_%d" % (seg, d))
            prev = "s_%s_%d" % (seg, d)
            xs += 60
        b.pin((1480, oy), seg, facing="west", output=True)
        b.wire((1480, oy), (1440, oy))
        b.tunnel((1440, oy), prev, 1, "west")
    b.text((700, 1700), "真值表 0~9；A~F 七段全灭（扩充 A~F 见「七段译码器0~F」电路）", bold=True)
    return b


# ---------------------------------------------------------------- 主链
def build_main():
    b = Board("实验7 主电路")
    b.raw = ""
    for i in range(5):
        y = 100 + 60 * i
        b.raw += raw_button(100, y, "按键%d" % (i + 1))
        b.wire((100, y), (200, y))
        b.tunnel((200, y), "k%d" % (i + 1), 1, "east")

    led_pts = b.sub("LED计数", (600, 300), LED_APP.offsets())
    for i, n in enumerate("abcde"):
        b.stub(led_pts[n], "k%d" % (i + 1), 1, "w")
    for i, n in enumerate(["w", "x", "y", "z", "u"]):
        p = led_pts[n]
        b.wire(p, (p[0] + 20, p[1]))
        b.tunnel((p[0] + 20, p[1]), "L" + n, 1, "east")
        b.raw += raw_led(1600, p[1], "LED%d" % (i + 1))
        b.wire((1600, p[1]), (1560, p[1]))
        b.tunnel((1560, p[1]), "L" + n, 1, "west")

    enc_pts = b.sub("按键编码器", (600, 1300), ENC_APP.offsets())
    for i, n in enumerate("abcde"):
        b.stub(enc_pts[n], "k%d" % (i + 1), 1, "w")
    for n in ["C0", "C1", "C2", "C3"]:
        b.stub(enc_pts[n], n, 1, "e")

    seg_pts = b.sub("七段显示驱动", (1800, 1200), SEG_APP.offsets())
    b.stub(seg_pts["In1"], "C3", 1, "w")
    b.stub(seg_pts["In2"], "C2", 1, "w")
    b.stub(seg_pts["In3"], "C1", 1, "w")
    b.stub(seg_pts["In4"], "C0", 1, "w")

    sx, sy = 3600, 1600
    b.raw += raw_seg(sx, sy)
    b.wire((sx, sy), (sx - 60, sy)); b.tunnel((sx - 60, sy), "g", 1, "west")
    b.wire((sx + 10, sy), (sx + 10, sy - 40)); b.wire((sx + 10, sy - 40), (sx - 40, sy - 40))
    b.tunnel((sx - 40, sy - 40), "f", 1, "west")
    b.wire((sx + 20, sy), (sx + 20, sy - 80)); b.wire((sx + 20, sy - 80), (sx - 30, sy - 80))
    b.tunnel((sx - 30, sy - 80), "a", 1, "west")
    b.wire((sx + 30, sy), (sx + 30, sy - 120)); b.wire((sx + 30, sy - 120), (sx - 20, sy - 120))
    b.tunnel((sx - 20, sy - 120), "b", 1, "west")
    b.wire((sx, sy + 60), (sx - 60, sy + 60)); b.tunnel((sx - 60, sy + 60), "e", 1, "west")
    b.wire((sx + 10, sy + 60), (sx + 10, sy + 100)); b.wire((sx + 10, sy + 100), (sx - 40, sy + 100))
    b.tunnel((sx - 40, sy + 100), "d", 1, "west")
    b.wire((sx + 20, sy + 60), (sx + 20, sy + 140)); b.wire((sx + 20, sy + 140), (sx - 30, sy + 140))
    b.tunnel((sx - 30, sy + 140), "c", 1, "west")

    b.text((1000, 250), "按 4 → 4 个 LED 亮，数码管同时显示 4", bold=True)
    return b


def wrap_circuit(board, appear=None):
    body = board.to_body()
    if board.raw:
        body = body + "\n" + board.raw
    out = ["  <circuit name=\"%s\">" % board.name,
           "    <a name=\"circuit\" val=\"%s\"/>" % board.name,
           "    <a name=\"clabel\" val=\"\"/>",
           "    <a name=\"clabelup\" val=\"east\"/>",
           "    <a name=\"clabelfont\" val=\"SansSerif plain 12\"/>",
           "    <a name=\"clabelcolor\" val=\"#000000\"/>"]
    if appear is not None:
        out.append(appear.to_xml())
    out.append(body)
    out.append("  </circuit>")
    return "\n".join(out) + "\n"


def main():
    led, enc, seg, top = build_led(), build_enc(), build_seg(), build_main()
    for b in (led, enc, seg, top):
        errs = b.check()
        print(b.name, "check:", len(errs))
        for e in errs[:8]:
            print("  ", e)
        if errs:
            raise SystemExit("布线自检失败 " + b.name)
    xml = open(CIRC, encoding="utf-8").read()
    if "LED计数" in xml:
        raise SystemExit("已存在 LED计数，先清理")
    add = (wrap_circuit(led, LED_APP) + wrap_circuit(enc, ENC_APP)
           + wrap_circuit(seg, SEG_APP) + wrap_circuit(top))
    xml = xml.replace("</project>", add + "</project>")
    open(CIRC, "w", encoding="utf-8", newline="\n").write(xml)
    print("written")


main()