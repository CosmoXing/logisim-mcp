# -*- coding: utf-8 -*-
"""2.15（Logisim-ITA 2.15.0.2）电路构建库。

包含：实测端口几何（门 / NOT / 分线器 / 引脚 / 子电路外观）、Board 追加式构建器、
六项正交布线自检（非正交、压线中段、共线重叠、穿元件体、元件重叠、锚点映射）。

注意：本文件的几何全部来自 2.15.0.2 实测，与 5.0（lib8/route8）和原始 2.7.1
（circ271）不同；不要混用。
"""
from __future__ import annotations

LIB_WIRING, LIB_GATES, LIB_PLEXERS, LIB_ARITH, LIB_BASE = "0", "1", "2", "3", "6"


# ---------------------------------------------------------------- 几何
def gate_input_offsets(n: int) -> list[int]:
    """2.15 实测：奇数 10px 均布；偶数中间留 20px 空档。"""
    if n % 2:
        return [(i - n // 2) * 10 for i in range(n)]
    h = n // 2
    return [-10 * h + 10 * i for i in range(h)] + [10 * (i + 1) for i in range(h)]


def gate_ports(kind: str, loc, n: int):
    x, y = loc
    if kind == "NOT Gate":
        return [(x - 20, y)], (x, y)
    dx = 40 if kind == "XOR Gate" else 30
    return [(x - dx, y + o) for o in gate_input_offsets(n)], (x, y)


def pin_body(loc, facing):
    x, y = loc
    if facing == "east":
        return (x - 50, y - 10, x, y + 10)
    if facing == "west":
        return (x, y - 10, x + 50, y + 10)
    if facing == "south":
        return (x - 10, y - 50, x + 10, y)
    return (x - 10, y, x + 10, y + 50)


def gate_body(kind: str, loc, n: int):
    x, y = loc
    offs = gate_input_offsets(n)
    if kind == "NOT Gate":
        return (x - 20, y - 10, x, y + 10)
    left = x - (40 if kind == "XOR Gate" else 30)
    return (left, y + offs[0] - 10, x, y + offs[-1] + 10)


# 2.15.0.2 实测（enable=false）：数据口在左，sel 在下方，out 在 loc
def mux_ports(loc, select: int):
    x, y = loc
    if select == 1:
        return [(x - 30, y - 10), (x - 30, y + 10)], (x - 20, y + 20), (x, y)
    if select == 2:
        return ([(x - 40, y - 20 + 10 * i) for i in range(4)],
                (x - 20, y + 20), (x, y))
    if select == 3:
        return ([(x - 40, y - 40 + 10 * i) for i in range(8)],
                (x - 20, y + 40), (x, y))
    raise ValueError("select 只支持 1/2/3")


def mux_body(loc, select: int):
    x, y = loc
    return {1: (x - 30, y - 10, x, y + 10),
            2: (x - 40, y - 20, x, y + 20),
            3: (x - 40, y - 40, x, y + 40)}[select]


def split_ports(loc, bits: int, facing="south"):
    """实测：bit i 在 x + off - 10*i，off = (ceil(bits/2)-1)*10；b0 最右。"""
    x, y = loc
    off = ((bits + 1) // 2 - 1) * 10
    dy = 20 if facing == "south" else -20
    return (x, y), [(x + off - 10 * i, y + dy) for i in range(bits)]


def split_body(loc, facing="south"):
    x, y = loc
    return (x - 10, y - 5, x + 10, y + 20) if facing == "south" \
        else (x - 10, y - 20, x + 10, y + 5)


def shifter_ports(loc):
    x, y = loc
    return (x - 40, y - 10), (x - 40, y + 10), (x, y)


def cmp_ports(loc):
    x, y = loc
    return {"A": (x - 40, y - 10), "B": (x - 40, y + 10),
            "gt": (x, y - 10), "eq": (x, y), "lt": (x, y + 10)}


def reg_ports(loc):
    x, y = loc
    return {"D": (x - 30, y), "Q": (x, y), "en": (x - 30, y + 10),
            "clk": (x - 20, y + 20), "clr": (x - 10, y + 20),
            "preset": (x - 10, y - 20), "cs": (x - 30, y - 10)}


def cnt_ports(loc):
    x, y = loc
    return {"Q": (x, y), "D": (x - 30, y), "clk": (x - 20, y + 20),
            "clr": (x - 10, y + 20), "ld": (x - 30, y - 10),
            "en": (x - 30, y + 10), "carry": (x, y + 10),
            "preset": (x - 10, y - 20), "rst": (x - 20, y - 20)}


def ram_ports(loc):
    x, y = loc
    return {"A": (x - 140, y), "Q": (x, y), "D": (x - 140, y + 20),
            "str": (x - 110, y + 40), "cs": (x - 90, y + 40),
            "clk": (x - 70, y + 40), "oe": (x - 50, y + 40),
            "clr": (x - 30, y + 40)}


def rom_ports(loc):
    x, y = loc
    return {"A": (x - 140, y), "D": (x, y), "cs": (x - 90, y + 40)}


def dec_ports(loc, select):
    x, y = loc
    n = 1 << select
    outs = [(x + 20, y - 10 * (n - i)) for i in range(n)]
    return outs, (x, y), (x - 10, y)


def dff_ports(loc):
    x, y = loc
    return {"Q": (x, y), "nQ": (x, y + 40), "D": (x - 60, y),
            "clk": (x - 30, y - 20), "R": (x - 60, y + 40),
            "S": (x - 30, y + 60)}


def adder_ports(loc):
    """2.15 实测：Cin(-20,-20)、Cout(-20,+20)（ITA 把 Cout 也声明成输入脚）。"""
    x, y = loc
    return {"A": (x - 40, y - 20), "B": (x - 40, y + 10),
            "Cin": (x - 20, y - 20), "S": (x, y), "Cout": (x - 20, y + 20)}


def splitn_ports(loc, fanout, facing="south"):
    """多分支分线器：branch i 在 x + off - 10i（最右为 b0）。"""
    x, y = loc
    off = ((fanout + 1) // 2 - 1) * 10
    dy = 20 if facing == "south" else -20
    return (x, y), [(x + off - 10 * i, y + dy) for i in range(fanout)]


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def on_segment(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    if ax == bx == px:
        return min(ay, by) < py < max(ay, by)
    if ay == by == py:
        return min(ax, bx) < px < max(ax, bx)
    return False


def segment_hits_rect(a, b, rect):
    """轴对齐线段是否穿过矩形内部（不含端点贴边）。"""
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


# ---------------------------------------------------------------- 电路
class Board:
    def __init__(self, name: str):
        self.name = name
        self.items = []
        self.wires = []
        self.bodies = []          # (rect, owner, ports)

    def pin(self, loc, label, facing="east", width=1, output=False):
        self.items.append(("pin", dict(loc=loc, label=label, facing=facing,
                                       width=width, output=output)))
        self.bodies.append((pin_body(loc, facing), f"pin {label}", {loc}))

    def tunnel(self, loc, label, width=1, facing="east"):
        self.items.append(("tunnel", dict(loc=loc, label=label, width=width, facing=facing)))

    def gate(self, kind, loc, n, width=1):
        self.items.append(("gate", dict(kind=kind, loc=loc, inputs=n, width=width)))
        ins, out = gate_ports(kind, loc, n)
        self.bodies.append((gate_body(kind, loc, n), f"{kind}@{loc}", set(ins) | {out}))
        return ins, out

    def sub(self, name, loc, offsets):
        self.items.append(("sub", dict(name=name, loc=loc)))
        pts = {k: (loc[0] + d[0], loc[1] + d[1]) for k, d in offsets.items()}
        xs = [p[0] for p in pts.values()]
        ys = [p[1] for p in pts.values()]
        self.bodies.append(((min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5),
                            f"sub {name}@{loc}", set(pts.values())))
        return pts

    def mux(self, loc, select, width=1):
        data, sel, out = mux_ports(loc, select)
        self.items.append(("mux", dict(loc=loc, select=select, width=width)))
        self.bodies.append((mux_body(loc, select), f"mux{select}@{loc}",
                            set(data) | {sel, out}))
        return data, sel, out

    def cmp(self, loc, width=8):
        pts = cmp_ports(loc)
        self.items.append(("cmp", dict(loc=loc, width=width)))
        self.bodies.append(((loc[0] - 40, loc[1] - 10, loc[0], loc[1] + 10),
                            f"cmp@{loc}", set(pts.values())))
        return pts

    def const(self, loc, width=1, value=0):
        self.items.append(("const", dict(loc=loc, width=width, value=value)))
        self.bodies.append(((loc[0] - 30, loc[1] - 8, loc[0], loc[1] + 8),
                            f"const@{loc}", {loc}))
        return loc

    def ext(self, loc, in_width=1, out_width=8):
        self.items.append(("ext", dict(loc=loc, in_width=in_width,
                                       out_width=out_width)))
        self.bodies.append(((loc[0] - 40, loc[1] - 18, loc[0], loc[1] + 18),
                            f"ext@{loc}", {(loc[0] - 40, loc[1]), loc}))
        return (loc[0] - 40, loc[1]), loc

    def shifter(self, loc, width=8, shift="ll"):
        d, n, out = shifter_ports(loc)
        self.items.append(("shifter", dict(loc=loc, width=width, shift=shift)))
        self.bodies.append(((loc[0] - 40, loc[1] - 20, loc[0], loc[1] + 20),
                            f"shifter {shift}@{loc}", {d, n, out}))
        return d, n, out

    def split(self, loc, bits, facing="south"):
        bus, pts = split_ports(loc, bits, facing)
        self.items.append(("split", dict(loc=loc, bits=bits, facing=facing)))
        self.bodies.append((split_body(loc, facing), f"split{bits}@{loc}",
                            set(pts) | {bus}))
        return bus, pts

    def dff(self, loc):
        pts = dff_ports(loc)
        self.items.append(("dff", dict(loc=loc)))
        self.bodies.append(((loc[0] - 60, loc[1] - 20, loc[0], loc[1] + 40),
                            f"dff@{loc}", set(pts.values())))
        return pts

    def adder(self, loc, width=8):
        pts = adder_ports(loc)
        self.items.append(("adder", dict(loc=loc, width=width)))
        self.bodies.append(((loc[0] - 40, loc[1] - 25, loc[0], loc[1] + 25),
                            f"adder@{loc}", set(pts.values())))
        return pts

    def register(self, loc, width=8, label=""):
        pts = reg_ports(loc)
        self.items.append(("register", dict(loc=loc, width=width, label=label)))
        self.bodies.append(((loc[0] - 30, loc[1] - 20, loc[0], loc[1] + 20),
                            f"register@{loc}", set(pts.values())))
        return pts

    def counter(self, loc, width=2, maxval=(1 << 2) - 1):
        pts = cnt_ports(loc)
        self.items.append(("counter", dict(loc=loc, width=width, maxval=maxval)))
        self.bodies.append(((loc[0] - 30, loc[1] - 20, loc[0], loc[1] + 20),
                            f"counter@{loc}", set(pts.values())))
        return pts

    def ram(self, loc, addr_width=4, data_width=8):
        pts = ram_ports(loc)
        self.items.append(("ram", dict(loc=loc, addr_width=addr_width,
                                       data_width=data_width)))
        self.bodies.append(((loc[0] - 140, loc[1] - 10, loc[0], loc[1] + 45),
                            f"ram@{loc}", set(pts.values())))
        return pts

    def rom(self, loc, addr_width=3, data_width=16, contents=""):
        pts = rom_ports(loc)
        self.items.append(("rom", dict(loc=loc, addr_width=addr_width,
                                       data_width=data_width, contents=contents)))
        self.bodies.append(((loc[0] - 140, loc[1] - 10, loc[0], loc[1] + 45),
                            f"rom@{loc}", set(pts.values())))
        return pts

    def decoder(self, loc, select=2, enable=False):
        outs, sel, en = dec_ports(loc, select)
        self.items.append(("decoder", dict(loc=loc, select=select, enable=enable)))
        ports = set(outs) | {sel}
        if enable:
            ports.add(en)
        self.bodies.append(((loc[0] - 10, loc[1] - 10 * (1 << select),
                             loc[0] + 20, loc[1] + 5),
                            f"decoder@{loc}", ports))
        return outs, sel, en

    def splitn(self, loc, fanout, incoming, groups=None, facing="south"):
        """fanout 个分支，incoming 位；groups[i]=第 i 位所属分支（0 = 最右）。"""
        groups = groups or list(range(incoming))
        if len(groups) != incoming:
            raise ValueError(f"{self.name}: splitn groups 长度不符")
        bus, pts = splitn_ports(loc, fanout, facing)
        self.items.append(("splitn", dict(loc=loc, fanout=fanout,
                                          incoming=incoming, groups=groups,
                                          facing=facing)))
        self.bodies.append((split_body(loc, facing), f"splitn{fanout}@{loc}",
                            set(pts) | {bus}))
        return bus, pts

    def text(self, loc, text, bold=False):
        self.items.append(("text", dict(loc=loc, text=text, bold=bold)))

    def lead(self, port, label, width, side, dist=80):
        """引脚引出线：先走 dist，再放隧道，避免隧道压住引脚本体。"""
        dx, dy = {"w": (-1, 0), "e": (1, 0), "n": (0, -1), "s": (0, 1)}[side]
        q = (port[0] + dx * dist, port[1] + dy * dist)
        self.wire(port, q)
        self.tunnel(q, label, width, facing={"w": "west", "e": "east",
                                             "n": "north", "s": "south"}[side])

    def fan_bits(self, bits_ports, prefix, facing="south"):
        """把分线器每个位口竖着拉远，隧道按 30px 递增错开，避免标签重叠。"""
        for i, p in enumerate(bits_ports):
            dy = 30 * (i + 1)
            q = (p[0], p[1] + dy) if facing == "south" else (p[0], p[1] - dy)
            self.wire(p, q)
            self.tunnel(q, f"{prefix}{i}", 1, facing=facing)

    def fan_stub(self, ports, labels, width, side="w"):
        """同侧一排端口的隧道扇出：横向 20+30i，纵向交替 ±25，标签互不压盖。"""
        sx = -1 if side == "w" else 1
        face = {"w": "west", "e": "east", "n": "north", "s": "south"}[side]
        for i, (p, lab) in enumerate(zip(ports, labels)):
            q = (p[0] + sx * (20 + 30 * i), p[1])
            self.wire(p, q)
            dy = -25 if i % 2 == 0 else 25
            r = (q[0], q[1] + dy)
            self.wire(q, r)
            self.tunnel(r, lab, width, facing=face)

    def wire(self, p, q):
        if p == q:
            return
        if p[0] != q[0] and p[1] != q[1]:
            raise ValueError(f"{self.name}: 非正交线 {p}->{q}")
        self.wires.append((p, q))

    def path(self, pts):
        for a, b in zip(pts, pts[1:]):
            self.wire(a, b)

    def stub(self, port, label, width, side):
        dx, dy = {"w": (-20, 0), "e": (20, 0), "n": (0, -20), "s": (0, 20)}[side]
        q = (port[0] + dx, port[1] + dy)
        self.wire(port, q)
        self.tunnel(q, label, width, facing={"w": "west", "e": "east",
                                             "n": "north", "s": "south"}[side])

    def gate_io(self, kind, loc, n, width, in_labels, out_label, out_width=None):
        ins, out = self.gate(kind, loc, n, width)
        if len(in_labels) != len(ins):
            raise ValueError(f"{self.name}: {kind}@{loc} 输入数不符")
        if all(not isinstance(lab, tuple) for lab in in_labels):
            self.fan_stub(ins, in_labels, width, "w")
        else:
            for p, lab in zip(ins, in_labels):
                if isinstance(lab, tuple):
                    self.stub(p, lab[0], lab[1], "w")
                else:
                    self.stub(p, lab, width, "w")
        if isinstance(out_label, tuple):
            self.stub(out, out_label[0], out_label[1], "e")
        else:
            self.stub(out, out_label, out_width or width, "e")
        return out

    # ---- 自检 ----
    def check(self):
        errs = []
        for a, b in self.wires:
            for rect, owner, ports in self.bodies:
                if a in ports or b in ports:
                    continue
                if segment_hits_rect(a, b, rect):
                    errs.append(f"导线穿元件体: {owner} {a}->{b}")
        for i, (a, b) in enumerate(self.wires):
            for j, (c, d) in enumerate(self.wires):
                if i >= j:
                    continue
                for p in (c, d):
                    if on_segment(p, a, b):
                        errs.append(f"线端压线中段: {p} ({a}->{b}) / ({c}->{d})")
                for p in (a, b):
                    if on_segment(p, c, d):
                        errs.append(f"线端压线中段: {p} ({c}->{d}) / ({a}->{b})")
                if a[1] == b[1] == c[1] == d[1]:
                    lo1, hi1 = sorted((a[0], b[0])); lo2, hi2 = sorted((c[0], d[0]))
                    if max(lo1, lo2) < min(hi1, hi2):
                        errs.append(f"共线重叠: {a}->{b} / {c}->{d}")
                if a[0] == b[0] == c[0] == d[0]:
                    lo1, hi1 = sorted((a[1], b[1])); lo2, hi2 = sorted((c[1], d[1]))
                    if max(lo1, lo2) < min(hi1, hi2):
                        errs.append(f"共线重叠: {a}->{b} / {c}->{d}")
        for i in range(len(self.bodies)):
            for j in range(i + 1, len(self.bodies)):
                if overlap(self.bodies[i][0], self.bodies[j][0]):
                    errs.append(f"元件重叠: {self.bodies[i][1]} / {self.bodies[j][1]}")
        return errs

    def to_body(self) -> str:
        """只输出元件与导线（不含 <circuit> 外壳），用于追加到原电路。"""
        out = []
        for kind, d in self.items:
            if kind == "pin":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Pin">',
                        f'      <a name="facing" val="{d["facing"]}"/>',
                        f'      <a name="output" val="{"true" if d["output"] else "false"}"/>',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '      <a name="tristate" val="false"/>',
                        '      <a name="pull" val="none"/>',
                        f'      <a name="label" val="{d["label"]}"/>',
                        '      <a name="labelloc" val="north"/>',
                        '      <a name="labelfont" val="Times New Roman bolditalic 18"/>',
                        '      <a name="labelcolor" val="#000000"/>',
                        '    </comp>']
            elif kind == "tunnel":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Tunnel">',
                        f'      <a name="facing" val="{d["facing"]}"/>',
                        f'      <a name="width" val="{d["width"]}"/>',
                        f'      <a name="label" val="{d["label"]}"/>',
                        '      <a name="labelfont" val="Dialog plain 12"/>',
                        '    </comp>']
            elif kind == "gate":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_GATES}" loc="({x},{y})" name="{d["kind"]}">',
                        f'      <a name="inputs" val="{d["inputs"]}"/>',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '    </comp>']
            elif kind == "mux":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_PLEXERS}" loc="({x},{y})" name="Multiplexer">',
                        f'      <a name="select" val="{d["select"]}"/>',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '      <a name="enable" val="false"/>',
                        '    </comp>']
            elif kind == "cmp":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_ARITH}" loc="({x},{y})" name="Comparator">',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '      <a name="mode" val="unsigned"/>',
                        '    </comp>']
            elif kind == "const":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Constant">',
                        f'      <a name="width" val="{d["width"]}"/>',
                        f'      <a name="value" val="0x{d["value"]:x}"/>',
                        '    </comp>']
            elif kind == "ext":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Bit Extender">',
                        f'      <a name="in_width" val="{d["in_width"]}"/>',
                        f'      <a name="out_width" val="{d["out_width"]}"/>',
                        '      <a name="type" val="zero"/>',
                        '    </comp>']
            elif kind == "shifter":
                x, y = d["loc"]
                out += [f'    <comp lib="{LIB_ARITH}" loc="({x},{y})" name="Shifter">',
                        f'      <a name="width" val="{d["width"]}"/>',
                        f'      <a name="shift" val="{d["shift"]}"/>',
                        '    </comp>']
            elif kind == "split":
                x, y = d["loc"]
                bits = d["bits"]
                bit_attrs = "".join(
                    f'      <a name="bit{i}" val="{i}"/>\n' for i in range(bits))
                out += [f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Splitter">',
                        f'      <a name="facing" val="{d["facing"]}"/>',
                        f'      <a name="fanout" val="{bits}"/>',
                        f'      <a name="incoming" val="{bits}"/>',
                        '      <a name="appear" val="center"/>',
                        bit_attrs.rstrip("\n"),
                        '    </comp>']
            elif kind == "splitn":
                x, y = d["loc"]
                bit_attrs = "".join(
                    f'      <a name="bit{i}" val="{d["groups"][i]}"/>\n'
                    for i in range(d["incoming"]))
                out += [f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Splitter">',
                        f'      <a name="facing" val="{d["facing"]}"/>',
                        f'      <a name="fanout" val="{d["fanout"]}"/>',
                        f'      <a name="incoming" val="{d["incoming"]}"/>',
                        '      <a name="appear" val="center"/>',
                        bit_attrs.rstrip("\n"),
                        '    </comp>']
            elif kind == "dff":
                x, y = d["loc"]
                out += [f'    <comp lib="4" loc="({x},{y})" name="D Flip-Flop">',
                        '      <a name="trigger" val="rising"/>',
                        '    </comp>']
            elif kind == "adder":
                x, y = d["loc"]
                out += [f'    <comp lib="3" loc="({x},{y})" name="Adder">',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '    </comp>']
            elif kind == "register":
                x, y = d["loc"]
                out += [f'    <comp lib="4" loc="({x},{y})" name="Register">',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '      <a name="trigger" val="rising"/>']
                if d["label"]:
                    out.append(f'      <a name="label" val="{d["label"]}"/>')
                out.append('    </comp>')
            elif kind == "counter":
                x, y = d["loc"]
                out += [f'    <comp lib="4" loc="({x},{y})" name="Counter">',
                        f'      <a name="width" val="{d["width"]}"/>',
                        '      <a name="trigger" val="rising"/>',
                        '    </comp>']
            elif kind == "ram":
                x, y = d["loc"]
                out += [f'    <comp lib="4" loc="({x},{y})" name="RAM">',
                        f'      <a name="addrWidth" val="{d["addr_width"]}"/>',
                        f'      <a name="dataWidth" val="{d["data_width"]}"/>',
                        '      <a name="bus" val="separate"/>',
                        '      <a name="trigger" val="rising"/>',
                        '    </comp>']
            elif kind == "rom":
                x, y = d["loc"]
                out += [f'    <comp lib="4" loc="({x},{y})" name="ROM">',
                        f'      <a name="addrWidth" val="{d["addr_width"]}"/>',
                        f'      <a name="dataWidth" val="{d["data_width"]}"/>',
                        f'      <a name="contents">addr/data: {d["addr_width"]} '
                        f'{d["data_width"]}\n{d["contents"]}\n</a>',
                        '    </comp>']
            elif kind == "decoder":
                x, y = d["loc"]
                out += [f'    <comp lib="2" loc="({x},{y})" name="Decoder">',
                        f'      <a name="select" val="{d["select"]}"/>',
                        f'      <a name="enable" val="{"true" if d["enable"] else "false"}"/>',
                        '      <a name="disabled" val="0"/>',
                        '    </comp>']
            elif kind == "sub":
                x, y = d["loc"]
                out.append(f'    <comp loc="({x},{y})" name="{d["name"]}"/>')
            else:
                x, y = d["loc"]
                font = "SansSerif bold 14" if d["bold"] else "SansSerif plain 12"
                out += [f'    <comp lib="{LIB_BASE}" loc="({x},{y})" name="Text">',
                        f'      <a name="text" val="{d["text"]}"/>',
                        f'      <a name="font" val="{font}"/>',
                        '      <a name="color" val="#000000"/>',
                        '      <a name="halign" val="center"/>',
                        '      <a name="valign" val="base"/>',
                        '    </comp>']
        for (x1, y1), (x2, y2) in self.wires:
            out.append(f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>')
        return "\n".join(out)


# ---------------------------------------------------------------- 外观
class Appearance:
    def __init__(self, rect, anchor, ports, label="", label_pos=None):
        """ports: [(name, pin_loc, cx, cy, size)]，cx/cy 是端口中心（符号坐标）。"""
        self.rect, self.anchor, self.ports = rect, anchor, ports
        self.label, self.label_pos = label, label_pos

    def offsets(self):
        ax, ay = self.anchor
        return {p[0]: (p[2] - ax, p[3] - ay) for p in self.ports}

    def to_xml(self):
        x, y, w, h = self.rect
        ax, ay = self.anchor
        out = ['    <appear>',
               f'      <rect x="{x}" y="{y}" width="{w}" height="{h}" '
               f'fill="#ffffff" stroke="#000000"/>']
        if self.label:
            lx, ly = self.label_pos or (ax, ay)
            out.append(f'      <text x="{lx}" y="{ly}" text-anchor="middle" '
                       f'font-family="SansSerif" font-size="11">{self.label}</text>')
        for _, pin, cx, cy, size in self.ports:
            out.append(f'      <circ-port x="{cx - size // 2}" y="{cy - size // 2}" '
                       f'width="{size}" height="{size}" pin="{pin}"/>')
        out.append(f'      <circ-anchor x="{ax - 3}" y="{ay - 3}" width="6" height="6" facing="east"/>')
        out.append('    </appear>')
        return "\n".join(out)
