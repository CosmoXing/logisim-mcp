# -*- coding: utf-8 -*-
"""按 3.2 手册重建 ram64k / rom64k / main，并新增 rom_test（ROM 测试台）。"""
import re
import sys

SRC = r"C:\Users\ASUS\AppData\Local\Temp\ev\32.circ"
DST = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\ASUS\AppData\Local\Temp\ev\32_new.circ"


class C:
    def __init__(self, name):
        self.name = name
        self.comps = []
        self.wires = []
        self.bodies = []
        self.appear = None

    def net(self, pts):
        for a, b in zip(pts, pts[1:]):
            assert a[0] == b[0] or a[1] == b[1], "非正交 %s: %s->%s" % (self.name, a, b)
            if a != b:
                self.wires.append((a, b))

    def pin(self, loc, label, width=1, out=False):
        self.comps.append(
            '    <comp lib="0" loc="(%d,%d)" name="Pin"><a name="type" val="%s"/>'
            '<a name="facing" val="%s"/><a name="width" val="%d"/>'
            '<a name="radix" val="16"/><a name="label" val="%s"/></comp>'
            % (loc[0], loc[1], "output" if out else "input", "west" if out else "east",
               width, label))
        self.bodies.append((("pin " + label), (loc[0] - (0 if out else 80), loc[1] - 10,
                                               loc[0] + (80 if out else 0), loc[1] + 10), {loc}))

    def gate(self, kind, loc, n=2):
        extra = '<a name="inputs" val="%d"/>' % n if n != 2 else ''
        self.comps.append('    <comp lib="1" loc="(%d,%d)" name="%s">%s</comp>'
                          % (loc[0], loc[1], kind, extra))
        dx = 30 if kind == "NOT Gate" else 50
        ins = [(loc[0] - dx, loc[1] + o) for o in {2: [-20, 20], 3: [-20, 0, 20]}[n]]
        self.bodies.append((kind, (loc[0] - dx, loc[1] - 25, loc[0], loc[1] + 25),
                            set(ins) | {loc}))
        return ins, loc

    def mux(self, loc, ns, width):
        self.comps.append('    <comp lib="5" loc="(%d,%d)" name="Multiplexer">'
                          '<a name="select" val="%d"/><a name="width" val="%d"/></comp>'
                          % (loc[0], loc[1], ns, width))
        ins = ([(loc[0] - 30, loc[1] - 10), (loc[0] - 30, loc[1] + 10)] if ns == 1 else
               [(loc[0] - 40, loc[1] - 20 + 10 * i) for i in range(1 << ns)])
        sel = (loc[0] - 20, loc[1] + 20)
        d = 30 if ns == 1 else 40
        self.bodies.append(("mux", (loc[0] - d, loc[1] - 30, loc[0], loc[1] + 30),
                            set(ins) | {sel, loc}))
        return ins, sel, loc

    def split(self, loc, n, branches, facing="east"):
        a = ('<a name="fanout" val="%d"/><a name="incoming" val="%d"/>'
             '<a name="appear" val="center"/>' % (n, len(branches)))
        if facing != "east":
            a += '<a name="facing" val="%s"/>' % facing
        for i, br in enumerate(branches):
            a += '<a name="bit%d" val="%d"/>' % (i, br)
        self.comps.append('    <comp lib="0" loc="(%d,%d)" name="Splitter">%s</comp>'
                          % (loc[0], loc[1], a))
        dx = 20 if facing == "east" else -20
        bits = [(loc[0] + dx, loc[1] - 10 * (n // 2) + 10 * i) for i in range(n)]
        self.bodies.append(("split", (min(loc[0], loc[0] + dx), bits[0][1],
                                      max(loc[0], loc[0] + dx), bits[-1][1]),
                            set(bits) | {loc}))
        return bits

    def const(self, loc, width, value):
        self.comps.append('    <comp lib="0" loc="(%d,%d)" name="Constant">'
                          '<a name="facing" val="east"/><a name="value" val="%s"/>'
                          '<a name="width" val="%d"/></comp>' % (loc[0], loc[1], value, width))
        self.bodies.append(("const", (loc[0] - 14, loc[1] - 8, loc[0], loc[1] + 8), {loc}))
        return loc

    def probe(self, loc, label):
        self.comps.append('    <comp lib="3" loc="(%d,%d)" name="LED">'
                          '<a name="facing" val="west"/><a name="color" val="#ff0000"/>'
                          '<a name="label" val="%s"/></comp>' % (loc[0], loc[1], label))

    def bext(self, loc, type_="sign"):
        self.comps.append('    <comp lib="0" loc="(%d,%d)" name="Bit Extender">'
                          '<a name="in_width" val="8"/><a name="out_width" val="32"/>'
                          '<a name="type" val="%s"/></comp>' % (loc[0], loc[1], type_))
        self.bodies.append(("bext", (loc[0] - 40, loc[1] - 20, loc[0], loc[1] + 20), set()))
        return (loc[0] - 40, loc[1]), loc

    def bank(self, loc):
        self.comps.append('    <comp loc="(%d,%d)" name="bank8"/>' % loc)
        self.bodies.append(("bank8", (loc[0], loc[1], loc[0] + 180, loc[1] + 170), set()))
        return {"A": (loc[0], loc[1] + 30), "D": (loc[0], loc[1] + 60),
                "WE": (loc[0], loc[1] + 100), "CLK": (loc[0], loc[1] + 130),
                "Q": (loc[0] + 180, loc[1] + 80)}

    def reg(self, loc):
        self.comps.append('    <comp lib="2" loc="(%d,%d)" name="Register">'
                          '<a name="width" val="32"/><a name="label" val="R"/></comp>' % loc)
        self.bodies.append(("reg", (loc[0], loc[1], loc[0] + 60, loc[1] + 90), set()))
        return {"D": (loc[0], loc[1] + 30), "en": (loc[0], loc[1] + 50),
                "clk": (loc[0], loc[1] + 70), "clr": (loc[0] + 30, loc[1] + 90),
                "Q": (loc[0] + 60, loc[1] + 30)}

    def hdd(self, loc):
        self.comps.append('    <comp lib="3" loc="(%d,%d)" name="Hex Digit Display"/>' % loc)
        self.bodies.append(("hdd", (loc[0] - 15, loc[1] - 60, loc[0] + 25, loc[1]), set()))
        return (loc[0], loc[1]), (loc[0] + 20, loc[1])

    def dec(self, loc, nsel):
        self.comps.append('    <comp lib="5" loc="(%d,%d)" name="Decoder">'
                          '<a name="select" val="%d"/></comp>' % (loc[0], loc[1], nsel))
        self.bodies.append(("dec", (loc[0] - 20, loc[1] - 50, loc[0] + 20, loc[1] + 10), set()))
        return loc, (loc[0] - 10, loc[1]), \
               [(loc[0] + 20, loc[1] - 40 + 10 * i) for i in range(1 << nsel)]

    def sub(self, name, loc, ports):
        self.comps.append('    <comp loc="(%d,%d)" name="%s"/>' % (loc[0], loc[1], name))
        return ports

    def rom(self, loc, contents):
        self.comps.append(
            '    <comp lib="2" loc="(%d,%d)" name="ROM"><a name="addrWidth" val="14"/>'
            '<a name="dataWidth" val="32"/><a name="line" val="single"/>'
            '<a name="misaligned" val="false"/><a name="contents" val="%s"/></comp>'
            % (loc[0], loc[1], contents))
        return (loc[0], loc[1] + 10), (loc[0] + 240, loc[1] + 60)

    def set_appear(self, w, h, title, ports):
        o = ['  <appear>',
             '    <rect fill="none" height="%d" rx="10" ry="10" stroke="#000000" '
             'stroke-width="2" width="%d" x="0" y="0"/>' % (h, w),
             '    <rect height="20" stroke="none" width="%d" x="0" y="%d"/>' % (w, h - 20),
             '    <text dominant-baseline="central" fill="#ffffff" font-family="SansSerif" '
             'font-size="12" font-weight="bold" text-anchor="middle" x="%d" y="%d">%s</text>'
             % (w // 2, h - 10, title)]
        for (px, py), (cx, cy), label in ports:
            o.append('    <text dominant-baseline="central" font-family="SansSerif" '
                     'font-size="11" text-anchor="%s" x="%d" y="%d">%s</text>'
                     % ("start" if cx == 0 else "end", 8 if cx == 0 else w - 8, cy + 20, label))
        o.append('    <circ-anchor facing="east" x="0" y="0"/>')
        for (px, py), (cx, cy), label in ports:
            o.append('    <circ-port dir="%s" pin="%d,%d" x="%d" y="%d"/>'
                     % ("in" if cx == 0 else "out", px, py, cx, cy))
        o.append('  </appear>')
        self.appear = "\n".join(o)

    def xml(self):
        o = ['  <circuit name="%s">' % self.name,
             '    <a name="circuit" val="%s"/>' % self.name]
        o += self.comps
        for a, b in self.wires:
            o.append('    <wire from="(%d,%d)" to="(%d,%d)"/>' % (a[0], a[1], b[0], b[1]))
        if self.appear:
            o.append(self.appear)
        o.append('  </circuit>')
        return "\n".join(o)

    def check(self):
        errs = []
        for i, (a, b) in enumerate(self.wires):
            for c, d in self.wires[i + 1:]:
                if a[0] == b[0] == c[0] == d[0]:
                    lo1, hi1 = sorted((a[1], b[1])); lo2, hi2 = sorted((c[1], d[1]))
                    if max(lo1, lo2) < min(hi1, hi2):
                        errs.append("共线 %s-%s / %s-%s" % (a, b, c, d))
                if a[1] == b[1] == c[1] == d[1]:
                    lo1, hi1 = sorted((a[0], b[0])); lo2, hi2 = sorted((c[0], d[0]))
                    if max(lo1, lo2) < min(hi1, hi2):
                        errs.append("共线 %s-%s / %s-%s" % (a, b, c, d))
        for a, b in self.wires:
            for p in (a, b):
                for c, d in self.wires:
                    if (c, d) == (a, b):
                        continue
                    if c[0] == d[0] == p[0] and min(c[1], d[1]) < p[1] < max(c[1], d[1]):
                        errs.append("端点 %s 落在 %s-%s" % (p, c, d))
                    if c[1] == d[1] == p[1] and min(c[0], d[0]) < p[0] < max(c[0], d[0]):
                        errs.append("端点 %s 落在 %s-%s" % (p, c, d))
        return sorted(set(errs))


# ====================================================== ram64k
def build_ram64k():
    c = C("RAMModule")
    c.pin((80, 150), "A", 16)
    c.pin((80, 350), "DIN", 32)
    c.pin((80, 540), "MCntrl")
    c.pin((80, 600), "MemWrite")
    c.pin((80, 640), "CLK")
    c.pin((1950, 350), "DOUT", 32, out=True)

    c.net([(80, 150), (240, 150)])
    al = c.split((240, 150), 2, [0, 0] + [1] * 14)       # (260,140) A[1:0] ; (260,150) A[15:2]
    c.net([(80, 350), (240, 350)])
    dl = c.split((240, 350), 4,
                 [3] * 8 + [2] * 8 + [1] * 8 + [0] * 8)   # (260,330..360) 大端
    b = [c.bank((600, 300)), c.bank((850, 300)), c.bank((1100, 300)), c.bank((1350, 300))]

    c.net([al[1], (280, 150), (280, 250), (1350, 250)])
    for k in b:
        c.net([(k["A"][0], 250), k["A"]])
    c.net([dl[0], (570, 330), (570, 360), b[0]["D"]])
    c.net([dl[1], (820, 340), (820, 360), b[1]["D"]])
    c.net([dl[2], (1070, 350), (1070, 360), b[2]["D"]])
    c.net([dl[3], (500, 360), (500, 310), (1330, 310), (1330, 360), b[3]["D"]])

    c.gate("NOT Gate", (400, 540))
    c.net([(80, 540), (370, 540)])
    c.dec((300, 700), 2)
    c.const((250, 700), 1, "1")
    c.net([(250, 700), (290, 700)])
    c.net([al[0], (270, 140), (270, 680), (300, 680), (300, 700)])
    c.net([(400, 540), (420, 540), (420, 450), (420, 630)])
    douts = [(320, 660), (320, 670), (320, 680), (320, 690)]
    for i in range(4):
        Y = 470 + 60 * i
        c.gate("OR Gate", (520, Y))
        c.net([(420, Y - 20), (470, Y - 20)])
        c.net([douts[i], (340 + 10 * i, douts[i][1]), (340 + 10 * i, Y + 20), (470, Y + 20)])
        c.gate("AND Gate", (600, Y + 30))
        c.net([(520, Y), (530, Y), (530, Y + 50), (550, Y + 50)])
        c.net([(540, Y + 10), (550, Y + 10)])
    c.net([(540, 480), (540, 740)])
    c.net([(80, 600), (100, 600), (100, 740), (540, 740)])
    c.net([(600, 500), (580, 500), (580, 400), (600, 400)])
    c.net([(600, 560), (620, 560), (620, 490), (830, 490), (830, 400), (850, 400)])
    c.net([(600, 620), (640, 620), (640, 480), (1080, 480), (1080, 400), (1100, 400)])
    c.net([(600, 680), (660, 680), (660, 500), (1330, 500), (1330, 400), (1350, 400)])
    c.net([(80, 640), (90, 640), (90, 760), (560, 760), (560, 520), (1400, 520)])
    for x in (600, 850, 1100, 1350):
        c.net([(x - 10, 520), (x - 10, 430), (x, 430)])

    rl = c.split((1650, 300), 4, [3] * 8 + [2] * 8 + [1] * 8 + [0] * 8, facing="west")
    c.net([b[0]["Q"], (800, 380), (800, 280), rl[0]])
    c.net([b[1]["Q"], (1050, 380), (1050, 290), rl[1]])
    c.net([b[2]["Q"], (1300, 380), (1300, 300), rl[2]])
    c.net([b[3]["Q"], (1550, 380), (1550, 310), rl[3]])
    ins, sel, out = c.mux((1750, 450), 2, 8)
    c.net([(1620, 280), (1620, 430), ins[0]])
    c.net([(1610, 290), (1610, 440), ins[1]])
    c.net([(1600, 300), (1600, 450), ins[2]])
    c.net([(1590, 310), (1590, 460), ins[3]])
    c.net([(270, 680), (270, 720), (1730, 720), (1730, 470)])
    bi, bo = c.bext((1790, 450))
    c.net([(1750, 450), bi])
    win, wsel, wout = c.mux((1900, 350), 1, 32)
    c.net([(1650, 300), (1650, 340), win[0]])
    c.net([bo, (1820, 450), (1820, 360), win[1]])
    c.net([(330, 540), (330, 390), (1880, 390), (1880, 370)])
    c.net([(1900, 350), (1950, 350)])
    c.set_appear(240, 230, "RAM Module 64KB",
                 [((80, 150), (0, 30), "A[16]"), ((80, 350), (0, 60), "DIN[32]"),
                  ((80, 600), (0, 110), "MemWrite"), ((80, 540), (0, 140), "MCntrl"),
                  ((80, 640), (0, 170), "CLK"), ((1950, 350), (240, 90), "DOUT[32]")])
    return c


# ====================================================== rom64k
def build_rom64k(contents):
    c = C("rom64k")
    c.pin((80, 200), "A", 16)
    c.pin((80, 320), "MCntrl")
    c.pin((1500, 300), "DOUT", 32, out=True)
    c.net([(80, 200), (240, 200)])
    al = c.split((240, 200), 2, [0, 0] + [1] * 14)      # (260,190) A[1:0] ; (260,200) A[15:2]
    ra, rq = c.rom((700, 300), contents)
    c.net([al[1], (280, 200), (280, 310), ra])
    rl = c.split((1050, 360), 4, [3] * 8 + [2] * 8 + [1] * 8 + [0] * 8)
    c.net([rq, (1050, 360)])
    ins, sel, out = c.mux((1200, 400), 2, 8)
    c.net([rl[0], (1110, 340), (1110, 380), ins[0]])
    c.net([rl[1], (1120, 350), (1120, 390), ins[1]])
    c.net([rl[2], (1130, 360), (1130, 400), ins[2]])
    c.net([rl[3], (1140, 370), (1140, 410), ins[3]])
    c.net([al[0], (270, 190), (270, 420), (1180, 420)])
    bi, bo = c.bext((1280, 400))
    c.net([(1200, 400), bi])
    win, wsel, wout = c.mux((1400, 300), 1, 32)
    c.net([(1050, 360), (1050, 290), (1370, 290)])
    c.net([bo, (1280, 310), (1370, 310)])
    c.net([(80, 320), (80, 440), (1360, 440), (1360, 320), (1380, 320)])
    c.net([(1400, 300), (1500, 300)])
    c.set_appear(220, 150, "ROM 64KB (16Kx32)",
                 [((80, 200), (0, 40), "A[16]"), ((80, 320), (0, 80), "MCntrl"),
                  ((1500, 300), (220, 60), "DOUT[32]")])
    return c


# ====================================================== 测试台
def add_output_stage(c, q, disp_y=200, const_x=1170):
    """q(Q 端口) → 32→8 分线器 → 8 个数码管"""
    c.net([q, (q[0], 220), (1000, 220)])
    bits = c.split((1000, 220), 8, [7 - i for i in range(8) for _ in range(4)])
    c.const((const_x, 290), 1, "0")
    c.net([(const_x, 290), (1640, 290)])
    for i in range(8):
        d, dp = c.hdd((1200 + 60 * i, disp_y))
        c.net([bits[i], (1040 + 20 * i, bits[i][1]), (1040 + 20 * i, 500 + 10 * i),
               (1200 + 60 * i, 500 + 10 * i), d])
        c.net([(1220 + 60 * i, 290), dp])


def build_main():
    c = C("main")
    c.pin((100, 200), "MemWrite")
    c.pin((100, 240), "MemRead")
    c.pin((100, 300), "Address", 16)
    c.pin((100, 340), "DataIn", 32)
    c.pin((100, 390), "MCntrl")
    c.pin((100, 440), "CLK")
    c.pin((100, 160), "SEL")
    
    
    mp = c.sub("RAMModule", (400, 400),
               {"A": (400, 430), "DIN": (400, 460), "MemWrite": (400, 510),
                "MCntrl": (400, 540), "CLK": (400, 570), "DOUT": (640, 490)})
    # A
    c.net([(100, 300), (240, 300)])
    al = c.split((240, 300), 2, [0, 0] + [1] * 14)      # (260,290) A[1:0] ; (260,300)
    c.net([(200, 300), (200, 430), mp["A"]])
    c.net([(100, 340), (380, 340), (380, 460), mp["DIN"]])
    # A[1:0] → 两位
    c.comps.append('    <comp lib="0" loc="(300,290)" name="Splitter">'
                   '<a name="fanout" val="2"/><a name="incoming" val="2"/>'
                   '<a name="appear" val="center"/><a name="bit0" val="0"/>'
                   '<a name="bit1" val="1"/></comp>')
    bits2 = [(320, 280), (320, 290)]
    c.net([al[0], (300, 290)])
    c.gate("OR Gate", (400, 160))
    c.net([bits2[0], (330, 280), (330, 140), (350, 140)])
    c.net([bits2[1], (340, 290), (340, 180), (350, 180)])
    c.gate("NOT Gate", (500, 300))
    c.net([(100, 390), (460, 390), (460, 300), (470, 300)])
    c.net([(430, 390), (430, 540), mp["MCntrl"]])
    c.gate("AND Gate", (560, 240), 3)
    c.net([(400, 160), (420, 160), (420, 220), (510, 220)])
    c.net([(500, 300), (505, 300), (505, 260), (510, 260)])
    # Except = ¬MCntrl ∧ (A1∨A0) ∧ (MemRead∨MemWrite)：只有读/写且未对齐才报
    c.gate("OR Gate", (300, 700))
    c.net([(250, 400), (250, 680)])
    c.net([(150, 200), (150, 680), (250, 680)])
    c.net([(300, 700), (360, 700), (360, 240), (510, 240)])
    c.net([(560, 240), (570, 240), (570, 120), (700, 120)])   # Except
    c.probe((700, 120), "except")
    # 写使能 = MemWrite ∧ ¬Except ∧ ¬MemRead
    c.gate("NOT Gate", (620, 320))
    c.net([(570, 240), (580, 240), (580, 320), (590, 320)])
    c.gate("NOT Gate", (600, 400))
    c.net([(100, 240), (110, 240), (110, 400), (570, 400)])
    c.gate("AND Gate", (700, 340), 3)
    c.net([(620, 320), (650, 320)])
    c.net([(100, 200), (640, 200), (640, 340), (650, 340)])
    c.net([(600, 400), (630, 400), (630, 360), (650, 360)])
    c.net([(700, 340), (690, 340), (690, 510), mp["MemWrite"]])
    # MemRead 门控
    # 输出寄存器：只在“读”时锁存 en = MemRead ∧ ¬Except
    r = c.reg((900, 340))
    c.gate("AND Gate", (760, 400))
    c.net([(620, 320), (620, 380), (710, 380)])
    c.net([(550, 400), (550, 420), (710, 420)])
    c.net([(760, 400), (760, 390), (900, 390)])
    # 任务一：ROM 也接进 main，SEL=1 选 ROM、SEL=0 选 RAM
    rom = c.sub("rom64k", (400, 700),
                {"A": (400, 740), "MCntrl": (400, 780), "DOUT": (620, 760)})
    c.mux((760, 600), 1, 32)
    c.net([(220, 430), (220, 740), rom["A"]])
    c.net([(350, 390), (350, 780), rom["MCntrl"]])
    c.net([mp["DOUT"], (680, 490), (680, 590), (730, 590)])
    c.net([rom["DOUT"], (700, 760), (700, 610), (730, 610)])
    c.net([(100, 160), (120, 160), (120, 660), (740, 660), (740, 620)])
    c.net([(760, 600), (780, 600), (780, 370), r["D"]])
    c.net([(100, 440), (110, 440), (110, 570), mp["CLK"]])
    c.net([(110, 470), (890, 470), (890, 410), r["clk"]])
    c.const((930, 460), 1, "0")
    c.net([(930, 460), (930, 430)])
    add_output_stage(c, r["Q"])
    return c


def build_rom_test():
    c = C("rom_test")
    c.pin((100, 200), "A", 16)
    c.pin((100, 240), "MCntrl")
    c.pin((100, 280), "MemRead")
    c.pin((100, 340), "CLK")
    
    mp = c.sub("rom64k", (400, 300),
               {"A": (400, 340), "MCntrl": (400, 380), "DOUT": (620, 360)})
    c.net([(100, 200), (240, 200), (240, 340), mp["A"]])
    c.net([(100, 240), (230, 240), (230, 380), mp["MCntrl"]])
    r = c.reg((900, 340))
    c.net([mp["DOUT"], (700, 360), (700, 370), r["D"]])
    c.net([(100, 280), (120, 280), (120, 430), (880, 430), (880, 390), r["en"]])
    c.net([(100, 340), (110, 340), (110, 470), (890, 470), (890, 410), r["clk"]])
    c.const((930, 460), 1, "0")
    c.net([(930, 460), (930, 430)])
    add_output_stage(c, r["Q"])
    return c


def main():
    src = open(SRC, encoding="utf-8").read()
    contents = re.search(r'name="contents" val="([^"]*)"', src).group(1)
    keep = {}
    for name in ("bank8",):
        m = re.search(r'  <circuit name="%s">.*?\n  </circuit>' % name, src, re.S)
        assert m
        keep[name] = m.group(0)
    circuits = [("main", build_main()), ("RAMModule", build_ram64k()),
                ("rom64k", build_rom64k(contents)), ("rom_test", build_rom_test())]
    head = src[:src.index('  <circuit name="main">')]
    out = [head]
    for name, cir in circuits:
        out.append(cir.xml() + "\n")
    out.append(keep["bank8"] + "\n")
    out.append("</project>\n")
    open(DST, "w", encoding="utf-8", newline="\n").write("".join(out))
    print("written", DST)
    for name, cir in circuits:
        errs = cir.check()
        print("== %s comps=%d wires=%d 问题=%d" % (name, len(cir.comps), len(cir.wires), len(errs)))
        for e in errs[:12]:
            print("   ", e)


if __name__ == "__main__":
    main()