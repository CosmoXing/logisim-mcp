# -*- coding: utf-8 -*-
"""2.15（Logisim-ITA 2.15.0.2）电路构建库。

包含：实测端口几何（门 / NOT / 分线器 / 引脚 / 子电路外观）、Board 追加式构建器、
六项正交布线自检（非正交、压线中段、共线重叠、穿元件体、元件重叠、锚点映射）。

注意：本文件的几何全部来自 2.15.0.2 实测，与 5.0（lib8/route8）和原始 2.7.1
（circ271）不同；不要混用。
"""
from __future__ import annotations

LIB_WIRING, LIB_GATES, LIB_BASE = "0", "1", "6"


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

    def text(self, loc, text, bold=False):
        self.items.append(("text", dict(loc=loc, text=text, bold=bold)))

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
