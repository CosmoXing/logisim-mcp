# -*- coding: utf-8 -*-
"""实验1「熟悉 Logisim 的基本使用」电路生成器（Logisim-ITA 2.15.0.2）。

覆盖文档里的 1~9 个练习：
  1_时钟LED      时钟 + LED（模拟→启用时钟模拟后闪烁）
  2_晶体管门     CMOS 与非/或非 + 反相器 → 与门 / 或门
  3_分离器       8 位总线 → 8 个位；8 个位 → 8 位总线（合并）
  4_运算器       A±B、A*B、A/B + 4:1 数据选择器 + 探针
  5_运算器封装   把 4_运算器 作为子电路（自定义外观）再使用一次
  6_计数器       时钟 + 计数器（最大值 9）+ 探针
  7_扩展器       4 位 → 8 位（零扩展 / 符号扩展）
  8a_A或B与C     A||(B&&C)
  8b_非A与B或C   (!A)&&B||C
  9_3-8译码器    按真值表用门电路搭 3-8 译码器（8 个三输入与门）

几何全部来自 2.15.0.2 实测（见各 *_ports 注释）；不使用隧道。
用法：python gen_lab1.py [输出.circ]
"""
from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARC = os.environ.get("LAB_ARC_DIR", HERE)
TPL = os.path.join(ARC, "实验2 构建加法器.circ")
OUT = os.path.join(ARC, "实验1 熟悉logisim的基本使用.circ")

WIRING, GATES, PLEXERS, ARITH, MEMORY, IO, BASE = "0", "1", "2", "3", "4", "5", "6"
APPEAR = 0 if "--no-appear" in sys.argv else 1


# ------------------------------------------------------------------ 几何
def gate_ports(kind, loc, n=2):
    x, y = loc
    if kind == "NOT Gate":
        return [(x - 20, y)], (x, y)
    off = [(i - n // 2) * 10 for i in range(n)] if n % 2 else \
          [-10 * (n // 2) + 10 * i for i in range(n // 2)] + [10 * (i + 1) for i in range(n // 2)]
    return [(x - 30, y + o) for o in off], (x, y)


def mux_ports(loc, select=2):
    x, y = loc
    data = [(x - 40, y - 20 + 10 * i) for i in range(1 << select)]
    return data, (x - 20, y + 20), (x, y)


def split_ports(loc, bits, facing="south"):
    """2.15 实测：8 位时南向位口 x+80-10i、北向 x-10-10i（均 y±20）；
       ≤4 位沿用 board215 公式。"""
    x, y = loc
    dy = 20 if facing == "south" else -20
    if bits == 8:
        base = 80 if facing == "south" else -10
        return (x, y), [(x + base - 10 * i, y + dy) for i in range(bits)]
    off = ((bits + 1) // 2 - 1) * 10
    return (x, y), [(x + off - 10 * i, y + dy) for i in range(bits)]


def arith_ports(kind, loc):
    """2.15 实测：Adder/Sub A=(x-40,y-10) B=(x-40,y+10) Out=(x,y)
       Cin/借位入=(x-20,y-20)  Cout/借位出=(x-20,y+20)。
       Multiplier/Divider 的 (x-20,y-20) 是数据位宽的附加输入（C/Upper），
       (x-20,y+20) 是附加输出（C/余数）。"""
    x, y = loc
    return {"A": (x - 40, y - 10), "B": (x - 40, y + 10), "Y": (x, y),
            "ci": (x - 20, y - 20), "co": (x - 20, y + 20)}


def trans_ports(loc):
    """2.15 实测（facing=east）：in=(x-40,y)，out=(x,y)，gate=(x-20,y-20)。"""
    x, y = loc
    return {"in": (x - 40, y), "out": (x, y), "gate": (x - 20, y - 20)}


def cnt_ports(loc):
    x, y = loc
    return {"Q": (x, y), "D": (x - 30, y), "clk": (x - 20, y + 20),
            "clr": (x - 10, y + 20), "ld": (x - 30, y - 10), "en": (x - 30, y + 10),
            "carry": (x, y + 10), "preset": (x - 10, y - 20), "rst": (x - 20, y - 20)}


def ext_ports(loc):
    x, y = loc
    return (x - 40, y), (x, y)


def pin_body(loc, facing):
    x, y = loc
    return {"east": (x - 50, y - 10, x, y + 10),
            "west": (x, y - 10, x + 50, y + 10),
            "south": (x - 10, y - 50, x, y + 10),
            "north": (x - 10, y, x + 10, y + 50)}[facing]


# ------------------------------------------------------------------ 电路
class Cir:
    def __init__(self, name):
        self.name = name
        self.lines = []
        self.wires = []
        self.bodies = []          # (rect, owner, ports)

    # -- 元件
    def comp(self, lib, loc, name, attrs=(), body=None, ports=(), owner=None):
        a = "".join('      <a name="%s" val="%s"/>\n' % (k, v) for k, v in attrs)
        self.lines.append('    <comp lib="%s" loc="(%d,%d)" name="%s">\n%s    </comp>'
                          % (lib, loc[0], loc[1], name, a))
        if body:
            self.bodies.append((body, owner or "%s@%s" % (name, loc), set(ports)))
        return loc

    def pin(self, loc, label, width=1, facing="east", output=False):
        return self.comp(WIRING, loc, "Pin",
                         [("facing", facing), ("output", "true" if output else "false"),
                          ("width", str(width)), ("tristate", "false"), ("pull", "none"),
                          ("label", label), ("labelloc", "north"),
                          ("labelfont", "SansSerif bold 14"), ("labelcolor", "#000000")],
                         pin_body(loc, facing), [loc], "pin " + label)

    def const(self, loc, value, width=1):
        return self.comp(WIRING, loc, "Constant",
                         [("width", str(width)), ("value", "0x%X" % value)],
                         (loc[0] - 30, loc[1] - 8, loc[0], loc[1] + 8), [loc], "const@%s" % (loc,))

    def clock(self, loc, facing="east"):
        return self.comp(WIRING, loc, "Clock",
                         [("facing", facing), ("highDuration", "1"), ("lowDuration", "1")],
                         None, [loc], "clock@%s" % (loc,))

    def led(self, loc, color="#00ff00"):
        return self.comp(IO, loc, "LED", [("color", color)], None, [loc], "led@%s" % (loc,))

    def probe(self, loc, radix="16"):
        return self.comp(WIRING, loc, "Probe",
                         [("facing", "west"), ("radix", radix)], None, [loc],
                         "probe@%s" % (loc,))

    def transistor(self, loc, kind="p"):
        p = trans_ports(loc)
        return self.comp(WIRING, loc, "Transistor",
                         [("type", kind), ("facing", "east"), ("gate", "tl")],
                         (loc[0] - 30, loc[1] - 10, loc[0], loc[1] + 10),
                         list(p.values()), "T%s@%s" % (kind, loc)), p

    def gate(self, kind, loc, n=2):
        ins, out = gate_ports(kind, loc, n)
        left = loc[0] - (20 if kind == "NOT Gate" else 30)
        ys = [p[1] for p in ins] + [out[1]]
        return self.comp(GATES, loc, kind,
                         [("inputs", str(n)), ("width", "1")] if kind != "NOT Gate" else [],
                         (left, min(ys) - 10, loc[0], max(ys) + 10),
                         ins + [out], "%s@%s" % (kind, loc)), ins, out

    def mux(self, loc, select=2, width=8):
        data, sel, out = mux_ports(loc, select)
        return self.comp(PLEXERS, loc, "Multiplexer",
                         [("select", str(select)), ("width", str(width)), ("enable", "false")],
                         (loc[0] - 40, loc[1] - 20, loc[0], loc[1] + 20),
                         data + [sel, out], "mux@%s" % (loc,)), data, sel, out

    def splitter(self, loc, bits=8, facing="south"):
        bus, pts = split_ports(loc, bits, facing)
        attrs = [("facing", facing), ("incoming", str(bits)), ("fanout", str(bits))]
        attrs += [("bit%d" % i, str(i)) for i in range(bits)]
        dy = 20 if facing == "south" else -20
        return self.comp(WIRING, loc, "Splitter", attrs,
                         (loc[0] - 10, loc[1] - 5 if dy > 0 else loc[1] - 20,
                          loc[0] + 10, loc[1] + 20 if dy > 0 else loc[1] + 5),
                         [bus] + pts, "split@%s" % (loc,)), bus, pts

    def arith(self, kind, loc, width=8):
        p = arith_ports(kind, loc)
        lib = ARITH
        return self.comp(lib, loc, kind, [("width", str(width))],
                         (loc[0] - 40, loc[1] - 20, loc[0], loc[1] + 20),
                         list(p.values()), "%s@%s" % (kind, loc)), p

    def counter(self, loc, width=4, maxval=9):
        p = cnt_ports(loc)
        return self.comp(MEMORY, loc, "Counter",
                         [("width", str(width)), ("max", "0x%X" % maxval),
                          ("trigger", "rising")],
                         (loc[0] - 30, loc[1] - 20, loc[0], loc[1] + 20),
                         list(p.values()), "counter@%s" % (loc,)), p

    def extender(self, loc, in_w=4, out_w=8, kind="zero"):
        inp, out = ext_ports(loc)
        return self.comp(WIRING, loc, "Bit Extender",
                         [("in_width", str(in_w)), ("out_width", str(out_w)), ("type", kind)],
                         (loc[0] - 40, loc[1] - 18, loc[0], loc[1] + 18),
                         [inp, out], "ext@%s" % (loc,)), inp, out

    def sub(self, name, loc, offsets):
        pts = {k: (loc[0] + d[0], loc[1] + d[1]) for k, d in offsets.items()}
        xs = [p[0] for p in pts.values()]
        ys = [p[1] for p in pts.values()]
        self.lines.append('    <comp loc="(%d,%d)" name="%s"/>' % (loc[0], loc[1], name))
        self.bodies.append(((min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5),
                            "sub " + name, set(pts.values())))
        return pts

    def text(self, loc, s, bold=False, halign="left"):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.comp(BASE, loc, "Text",
                  [("text", s), ("font", "SansSerif bold 14" if bold else "SansSerif plain 13"),
                   ("color", "#000000"), ("halign", halign), ("valign", "base")],
                  None, [], "text")

    # -- 连线
    def wire(self, p, q):
        if p == q:
            return
        if p[0] != q[0] and p[1] != q[1]:
            raise ValueError("%s: 非正交线 %s -> %s" % (self.name, p, q))
        self.wires.append((p, q))

    def path(self, pts):
        for a, b in zip(pts, pts[1:]):
            self.wire(a, b)

    # -- 自检
    def check(self):
        errs = []
        for a, b in self.wires:
            for rect, owner, ports in self.bodies:
                if a in ports or b in ports:
                    continue
                if self._hits(a, b, rect):
                    errs.append("导线穿元件体 %s: %s->%s" % (owner, a, b))
        for i, (a, b) in enumerate(self.wires):
            for c, d in self.wires[i + 1:]:
                if a[1] == b[1] == c[1] == d[1]:
                    lo1, hi1 = sorted((a[0], b[0])); lo2, hi2 = sorted((c[0], d[0]))
                    if max(lo1, lo2) < min(hi1, hi2):
                        errs.append("共线重叠 %s->%s / %s->%s" % (a, b, c, d))
                if a[0] == b[0] == c[0] == d[0]:
                    lo1, hi1 = sorted((a[1], b[1])); lo2, hi2 = sorted((c[1], d[1]))
                    if max(lo1, lo2) < min(hi1, hi2):
                        errs.append("共线重叠 %s->%s / %s->%s" % (a, b, c, d))
        return errs

    @staticmethod
    def _hits(a, b, rect):
        (x1, y1), (x2, y2) = a, b
        rx1, ry1, rx2, ry2 = rect
        if y1 == y2:
            if not (ry1 < y1 < ry2):
                return False
            lo, hi = sorted((x1, x2))
            return max(lo, rx1) < min(hi, rx2)
        if x1 == x2:
            if not (rx1 < x1 < rx2):
                return False
            lo, hi = sorted((y1, y2))
            return max(lo, ry1) < min(hi, ry2)
        return False

    def xml(self, appear=None):
        head = ['<circuit name="%s">' % self.name,
                '    <a name="circuit" val="%s"/>' % self.name,
                '    <a name="clabel" val=""/>',
                '    <a name="clabelup" val="east"/>',
                '    <a name="clabelfont" val="SansSerif plain 12"/>',
                '    <a name="clabelcolor" val="#000000"/>']
        wires = ['    <wire from="(%d,%d)" to="(%d,%d)"/>' % (a[0], a[1], b[0], b[1])
                 for a, b in self.wires]
        return "\n".join(head + (appear or []) + self.lines + wires) + "\n</circuit>\n"


# ------------------------------------------------------------------ 各电路
def c1_clock_led():
    b = Cir("1_时钟LED")
    b.text((180, 150), "练习1：时钟 + LED（菜单 模拟 → 启用时钟模拟，灯开始闪烁）", bold=True)
    b.clock((200, 260))
    b.led((420, 260))
    b.wire((200, 260), (420, 260))
    return b


def _cmos(b, kind, X, Y, pfx=""):
    """2 输入 CMOS 门（NAND/NOR）+ 反相器，返回（门输出脚, 与/或输出脚）。

    上拉网络在 VCC(Y) 与 Q(Y+120) 之间，下拉网络在 Q 与 GND(Y+280) 之间；
    VCC/GND 用常量 1/0 表示（等价且端口已知）。"""
    b.const((X, Y), 1)
    b.const((X, Y + 280), 0)
    b.wire((X, Y), (X + 240, Y))
    b.wire((X, Y + 280), (X + 240, Y + 280))
    b.wire((X + 50, Y + 120), (X + 240, Y + 120))          # Q 干线

    if kind == "NAND":
        for dx in (100, 180):                              # p 并联（上拉，VCC→Q）
            b.transistor((X + dx, Y + 60), "p")
            b.wire((X + dx - 40, Y + 60), (X + dx - 40, Y))
            b.wire((X + dx, Y + 60), (X + dx, Y + 120))
        # n 串联（下拉，注意三极管是单向 in→out：GND 接 in 侧）
        b.transistor((X + 70, Y + 200), "n")
        b.transistor((X + 140, Y + 200), "n")
        b.wire((X + 30, Y + 280), (X + 30, Y + 200))
        b.wire((X + 70, Y + 200), (X + 100, Y + 200))
        b.wire((X + 140, Y + 200), (X + 140, Y + 250))
        b.wire((X + 140, Y + 250), (X + 220, Y + 250))
        b.wire((X + 220, Y + 250), (X + 220, Y + 120))
        ngate = [(X + 50, Y + 180), (X + 120, Y + 180)]
        pgate = [(X + 80, Y + 40), (X + 160, Y + 40)]
    else:
        b.transistor((X + 100, Y + 60), "p")               # p 串联（上拉，VCC→Q）
        b.transistor((X + 160, Y + 60), "p")
        b.wire((X + 60, Y + 60), (X + 60, Y))
        b.wire((X + 100, Y + 60), (X + 120, Y + 60))
        b.wire((X + 160, Y + 60), (X + 160, Y + 120))
        # n 并联（下拉，GND 接 in 侧）
        b.transistor((X + 100, Y + 200), "n")
        b.transistor((X + 200, Y + 200), "n")
        b.wire((X + 60, Y + 280), (X + 60, Y + 200))
        b.wire((X + 100, Y + 200), (X + 100, Y + 120))
        b.wire((X + 160, Y + 280), (X + 160, Y + 200))
        b.wire((X + 200, Y + 200), (X + 200, Y + 120))
        ngate = [(X + 80, Y + 180), (X + 180, Y + 180)]
        pgate = [(X + 80, Y + 40), (X + 140, Y + 40)]

    # 栅极：A → 第一个 p 与第一个 n；B → 第二个 p 与第二个 n
    b.pin((X - 100, Y + 40), pfx + "A", 1, "east")
    b.wire((X - 100, Y + 40), pgate[0])
    b.wire((X + 20, Y + 40), (X + 20, Y + 180))
    b.wire((X + 20, Y + 180), ngate[0])
    b.pin((X - 100, Y + 80), pfx + "B", 1, "east")
    b.wire((X - 100, Y + 80), (pgate[1][0], Y + 80))
    b.wire((pgate[1][0], Y + 80), pgate[1])
    b.wire((X - 40, Y + 80), (X - 40, Y + 150))
    b.wire((X - 40, Y + 150), (ngate[1][0], Y + 150))
    b.wire((ngate[1][0], Y + 150), ngate[1])

    # 门输出 → 反相器 = 与/或；反相器之前另引一路 = 原始与非/或非
    b.wire((X + 240, Y + 120), (X + 320, Y + 120))
    b.gate("NOT Gate", (X + 340, Y + 120))
    b.wire((X + 340, Y + 120), (X + 480, Y + 120))
    b.pin((X + 480, Y + 120), pfx + ("AND" if kind == "NAND" else "OR"), 1, "west", output=True)
    b.wire((X + 280, Y + 120), (X + 280, Y + 20))
    b.wire((X + 280, Y + 20), (X + 420, Y + 20))
    b.pin((X + 420, Y + 20), pfx + kind, 1, "west", output=True)
    return (X + 240, Y + 120)


def c2_transistor_gates():
    b = Cir("2_晶体管门")
    b.text((180, 60), "练习2：用三极管搭 CMOS 门（p 并联/n 串联 = 与非，p 串联/n 并联 = 或非，再各接一个反相器）",
           bold=True)
    b.text((100, 760), "上：与非门 + 反相器 = 与门    下：或非门 + 反相器 = 或门", bold=True)
    _cmos(b, "NAND", 320, 120, "1")
    _cmos(b, "NOR", 320, 520, "2")
    return b


def _bit_fan(b, bit_ports, pin_x, base_y, gap, facing_pin="west"):
    """把分线器的位口各自拉到一个输出/输入引脚：竖到独立高度，再横到引脚。
       gap 为相邻位的高度差，保证水平段互不共线。"""
    for i, (bx, by) in enumerate(bit_ports):
        y = base_y + gap * i
        b.wire((bx, by), (bx, y))
        b.wire((bx, y), (pin_x, y))
    return [(pin_x, base_y + gap * i) for i in range(len(bit_ports))]


def c3_splitter():
    b = Cir("3_分离器")
    b.text((120, 100), "练习3：分离器（上：总线→8 位；下：8 位→总线合并）", bold=True)
    # 分离
    b.pin((120, 200), "D", 8, "east")
    _, bus, bits = b.splitter((420, 200), 8, "south")
    b.wire((120, 200), bus)
    for i, (bx, by) in enumerate(bits):
        y = 280 + 24 * i
        b.wire((bx, by), (bx, y))
        b.wire((bx, y), (820, y))
        b.pin((820, y), "D%d" % i, 1, "west", output=True)
    # 合并
    _, bus2, bits2 = b.splitter((420, 880), 8, "north")
    b.wire(bus2, (820, 880))
    b.pin((820, 880), "BUS", 8, "west", output=True)
    for i, (bx, by) in enumerate(bits2):
        y = 780 - 24 * i
        b.wire((bx, by), (bx, y))
        b.wire((200, y), (bx, y))
        b.pin((200, y), "b%d" % i, 1, "east")
    return b


def c4_alu():
    b = Cir("4_运算器")
    b.text((120, 60), "练习4：简易运算器（运算选择 00 加 / 01 减 / 10 乘 / 11 除）", bold=True)
    b.pin((120, 120), "A", 8, "east")
    b.pin((120, 180), "B", 8, "east")
    # A/B 干线（竖直），每行横向接到运算器
    b.wire((120, 120), (200, 120))
    b.wire((200, 120), (200, 510))
    b.wire((120, 180), (240, 180))
    b.wire((240, 150), (240, 510))
    rows = [("Adder", 140), ("Subtractor", 260), ("Multiplier", 380), ("Divider", 500)]
    for kind, y in rows:
        loc = (420, y)
        _, p = b.arith(kind, loc, 8)
        b.wire((200, y - 10), p["A"])
        b.wire((240, y + 10), p["B"])
        wide = kind in ("Multiplier", "Divider")
        b.const((p["ci"][0] - (60 if wide else 20), p["ci"][1]), 0, 8 if wide else 1)
        b.wire((p["ci"][0] - (60 if wide else 20), p["ci"][1]), p["ci"])
    # 4:1 选择器：sel=0 加 / 1 减 / 2 乘 / 3 除
    _, data, sel, out = b.mux((960, 320), 2, 8)
    for src_y, vx, dy in ((140, 880, 300), (260, 860, 310), (380, 820, 320), (500, 840, 330)):
        b.wire((420, src_y), (vx, src_y))
        b.wire((vx, src_y), (vx, dy))
        b.wire((vx, dy), (920, dy))
    b.pin((760, 340), "SEL", 2, "east")
    b.wire((760, 340), sel)
    b.wire(out, (1120, 320))
    b.probe((1120, 320))
    b.wire((1120, 320), (1260, 320))
    b.pin((1260, 320), "Y", 8, "west", output=True)
    b.text((1080, 400), "探针可切换十六进制 / 有符号十进制查看", bold=False)
    return b


def c5_packaged():
    b = Cir("5_运算器封装")
    b.text((150, 120), "练习5：把 4_运算器 封装成芯片后再使用（芯片内是 4 个运算部件 + 4:1 选择器）", bold=True)
    b.text((610, 230), "运算器", bold=True)
    offs = {"A": (-90, -40), "B": (-90, 0), "SEL": (-90, 40), "Y": (90, 0)}
    pts = b.sub("4_运算器", (560, 300), offs)
    b.pin((250, pts["A"][1]), "A", 8, "east")
    b.wire((250, pts["A"][1]), pts["A"])
    b.pin((250, pts["B"][1]), "B", 8, "east")
    b.wire((250, pts["B"][1]), pts["B"])
    b.pin((250, pts["SEL"][1]), "SEL", 2, "east")
    b.wire((250, pts["SEL"][1]), pts["SEL"])
    b.wire(pts["Y"], (740, pts["Y"][1]))
    b.probe((740, pts["Y"][1]))
    b.wire((740, pts["Y"][1]), (900, pts["Y"][1]))
    b.pin((900, pts["Y"][1]), "Y", 8, "west", output=True)
    return b


def c6_counter():
    b = Cir("6_计数器")
    b.text((150, 120), "练习6：计数器（最大值 = 9，计到 9 后归零）", bold=True)
    b.clock((240, 300))
    _, p = b.counter((480, 300), 4, 9)
    b.wire((240, 300), (240, 320))
    b.wire((240, 320), p["clk"])
    b.const((560, 400), 0, 1)
    b.wire((560, 400), (560, 320))
    b.wire((560, 320), p["clr"])
    b.wire(p["Q"], (760, 300))
    b.probe((760, 300))
    b.wire((760, 300), (900, 300))
    b.pin((900, 300), "Q", 4, "west", output=True)
    b.wire(p["carry"], (620, 310))
    b.led((640, 310))
    b.text((520, 440), "Q 用探针看计数；LED 在 9→0 时闪一下", bold=False)
    return b


def c7_extender():
    b = Cir("7_扩展器")
    b.text((150, 100), "练习7：位扩展（上：零扩展；下：符号扩展）", bold=True)
    b.pin((200, 200), "D4", 4, "east")
    _, inp, out = b.extender((520, 200), 4, 8, "zero")
    b.wire((200, 200), inp)
    b.wire(out, (700, 200))
    b.probe((700, 200))
    b.wire((700, 200), (860, 200))
    b.pin((860, 200), "D8U", 8, "west", output=True)
    b.pin((200, 400), "D4b", 4, "east")
    _, inp2, out2 = b.extender((520, 400), 4, 8, "sign")
    b.wire((200, 400), inp2)
    b.wire(out2, (700, 400))
    b.probe((700, 400))
    b.wire((700, 400), (860, 400))
    b.pin((860, 400), "D8S", 8, "west", output=True)
    return b


def c8a():
    b = Cir("8a_A或B与C")
    b.text((150, 140), "练习8a：Y = A || (B && C)", bold=True)
    b.pin((150, 260), "A", 1, "east")
    b.pin((150, 290), "C", 1, "east")
    b.pin((150, 340), "B", 1, "east")
    _, ins, out = b.gate("AND Gate", (420, 300), 2)
    b.wire((150, 290), ins[0])                    # C → 与门 in0 (400..)
    b.wire((150, 340), (340, 340))
    b.wire((340, 340), (340, 310))
    b.wire((340, 310), ins[1])
    _, ins2, out2 = b.gate("OR Gate", (640, 300), 2)
    b.wire((150, 260), (540, 260))
    b.wire((540, 260), (540, 290))
    b.wire((540, 290), ins2[0])
    b.wire(out, (520, 300))
    b.wire((520, 300), (520, 310))
    b.wire((520, 310), ins2[1])
    b.wire(out2, (820, 300))
    b.pin((820, 300), "Y", 1, "west", output=True)
    return b


def c8b():
    b = Cir("8b_非A与B或C")
    b.text((150, 140), "练习8b：Y = (!A && B) || C", bold=True)
    b.pin((150, 260), "A", 1, "east")
    b.pin((150, 310), "B", 1, "east")
    b.pin((150, 360), "C", 1, "east")
    _, ni, no = b.gate("NOT Gate", (320, 260))
    b.wire((150, 260), ni[0])
    _, ai, ao = b.gate("AND Gate", (480, 300), 2)
    b.wire(no, (420, 260))
    b.wire((420, 260), (420, 290))
    b.wire((420, 290), ai[0])
    b.wire((150, 310), ai[1])
    _, oi, oo = b.gate("OR Gate", (700, 300), 2)
    b.wire(ao, (620, 300))
    b.wire((620, 300), (620, 310))
    b.wire((620, 310), oi[1])
    b.wire((150, 360), (600, 360))
    b.wire((600, 360), (600, 290))
    b.wire((600, 290), oi[0])
    b.wire(oo, (900, 300))
    b.pin((900, 300), "Y", 1, "west", output=True)
    return b


def c9_decoder():
    b = Cir("9_3-8译码器")
    b.text((150, 120), "练习9：3-8 译码器（按真值表 a'b'c' … abc 用 8 个三输入与门实现）", bold=True)
    b.pin((120, 300), "a", 1, "east")
    b.pin((120, 360), "b", 1, "east")
    b.pin((120, 420), "c", 1, "east")
    # 六个字面量干线：a/b/c 从引脚导线上取 T 接点，a'/b'/c' 用反相器输出
    b.wire((120, 300), (240, 300)); b.gate("NOT Gate", (260, 300))
    b.wire((120, 360), (280, 360)); b.gate("NOT Gate", (300, 360))
    b.wire((120, 420), (320, 420)); b.gate("NOT Gate", (340, 420))
    trunk = {"a'": (260, 300), "b'": (300, 360), "c'": (340, 420),
             "a": (160, 300), "b": (180, 360), "c": (200, 420)}
    for x, y0 in trunk.values():
        b.wire((x, y0), (x, 1000))
    names = ["x", "y", "z", "u", "v", "w", "s", "t"]
    lits = [("a'", "b'", "c'"), ("a'", "b'", "c"), ("a'", "b", "c'"), ("a'", "b", "c"),
            ("a", "b'", "c'"), ("a", "b'", "c"), ("a", "b", "c'"), ("a", "b", "c")]
    for i, (l1, l2, l3) in enumerate(lits):
        y = 480 + 70 * i
        _, ins, out = b.gate("AND Gate", (760, y), 3)
        for lit, port in zip((l1, l2, l3), ins):
            b.wire((trunk[lit][0], port[1]), port)
        b.wire(out, (980, y))
        b.pin((980, y), names[i], 1, "west", output=True)
    return b


# ------------------------------------------------------------------ 组装
def appear_alu():
    """4_运算器 的自定义外观：左边 A/B/SEL，右边 Y。

    注意（2.15 实测）：`circ-anchor` 存的是 6×6 锚点框左上角，Logisim 以它的
    **中心**（x+3, y+3）为原点，故实例端口 = loc + (端口中心 − (anchor+3))。
    这里 anchor=(97,57) → 原点 (100,60)，偏移 = (-90,-40)/(-90,0)/(-90,40)/(90,0)，
    必须与 c5_packaged() 的 offs 完全一致；差 1~3px 就会整块端口悬空（Y 全是 x）。"""
    ports = [("A", "120,120", 10, 20, 8),
             ("B", "120,180", 10, 60, 8),
             ("SEL", "760,340", 10, 100, 8),
             ("Y", "1260,320", 190, 60, 8)]
    ap = []
    ap.append("    <appear>")
    ap.append('      <rect x="0" y="0" width="200" height="120" fill="#ffffff" stroke="#000000"/>')
    for _, pin, cx, cy, size in ports:
        ap.append('      <circ-port x="%d" y="%d" width="%d" height="%d" pin="%s"/>'
                  % (cx - size // 2, cy - size // 2, size, size, pin))
    ap.append('      <circ-anchor x="97" y="57" width="6" height="6" facing="east"/>')
    ap.append("    </appear>")
    return ap


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    s = io.open(TPL, encoding="utf-8").read()
    head = s[:s.index("<circuit ")]
    import re
    head = re.sub(r'<main name="[^"]*"\s*/>', '<main name="4_运算器"/>', head)

    circs = [c1_clock_led(), c2_transistor_gates(), c3_splitter(), c4_alu()]
    for c in circs:
        errs = c.check()
        if errs:
            print("[!] %s 自检：" % c.name)
            for e in errs[:8]:
                print("     ", e)
    body = [c.xml() for c in circs]
    body.append(c5_packaged().xml())
    for c in (c6_counter(), c7_extender(), c8a(), c8b(), c9_decoder()):
        errs = c.check()
        if errs:
            print("[!] %s 自检：" % c.name)
            for e in errs[:8]:
                print("     ", e)
        body.append(c.xml())
    # 给 4_运算器 补外观（APPEAR=0 时用 Logisim 默认外观）
    if APPEAR:
        xml4 = body[3]
        body[3] = xml4.replace('<circuit name="4_运算器">\n    <a name="circuit" val="4_运算器"/>\n',
                               '<circuit name="4_运算器">\n    <a name="circuit" val="4_运算器"/>\n'
                               + "\n".join(appear_alu()) + "\n")
    io.open(out, "w", encoding="utf-8", newline="\n").write(head + "".join(body) + "</project>\n")
    print("已生成", out)
    print("circuits:", ", ".join(re.findall(r'<circuit name="([^"]+)"', "".join(body))))


if __name__ == "__main__":
    main()



