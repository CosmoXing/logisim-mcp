"""元件几何查询：把端口偏移/包围盒统一成一份可查询的数据。"""

import math

from . import knowledge

GATE_WIDTH = {"AND": 50, "OR": 50, "NAND": 60, "NOR": 60, "XOR": 60, "XNOR": 70, "NOT": 30}


def gate_width(kind):
    return GATE_WIDTH[kind]


def gate_ports(kind, inputs=2):
    """返回 {端口名: (dx, dy)}；输出口固定在 (0,0)。"""
    w = gate_width(kind)
    h = max(10 * inputs, 50)
    if inputs == 1:
        pts = {"out": (0, 0), "a": (-w, 0)}
    elif inputs == 2:
        pts = {"out": (0, 0), "a": (-w, -20), "b": (-w, 20)}
    else:
        top = -10 * (inputs - 1)
        pts = {"out": (0, 0)}
        for i, nm in enumerate("abcdefgh"[:inputs]):
            pts[nm] = (-w, top + 20 * i)
    body = (-w, -h // 2, 0, h // 2)
    return pts, body


DFF_PORTS = {"D": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20), "R": (-10, 30), "S": (-30, 30)}
DFF_BODY = (-40, -10, 0, 30)


def splitter_ports(fanout=4):
    pts = {"in": (0, 0)}
    for i in range(fanout):
        pts[f"b{i}"] = (20, -20 + 10 * i)
    return pts, (0, -20, 20, 20)


def _r10(v):
    return int(math.floor(v / 10.0 + 0.5)) * 10


def _dim(mx, others):
    if mx < 3:
        return 30
    return 10 * mx if others == 0 else 10 * mx + 10


def _offs(n, opp, max_others):
    mx = max(n, opp)
    if mx <= 1:
        base = 15 if max_others == 0 else 10
    elif mx == 2:
        base = 10
    else:
        base = 5 if max_others == 0 else 10
    return base + 10 * ((mx - n) // 2)


def sub_geometry(pins):
    """pins: [(label, x, y, facing)] → (body, {label: (dx,dy)})，相对实例 loc。"""
    west = sorted([p for p in pins if p[3] == "east"], key=lambda p: (p[2], p[1]))
    east = sorted([p for p in pins if p[3] == "west"], key=lambda p: (p[2], p[1]))
    nw, ne = len(west), len(east)
    mh = max(nw, ne)
    oe, ow = _offs(ne, nw, 0), _offs(nw, ne, 0)
    width, height = _dim(0, mh), _dim(mh, 0)
    ax = width if ne > 0 else 0
    ay = oe if ne > 0 else 0
    rx, ry = _r10(50 + ax), _r10(50 + ay)
    ports = {}
    for i, p in enumerate(west):
        ports[p[0]] = (rx - (rx + ax), ry + ow + 10 * i - (ry + ay))
    for j, p in enumerate(east):
        ports[p[0]] = (rx + width - (rx + ax), ry + oe + 10 * j - (ry + ay))
    return (-ax, -ay, -ax + width, -ay + height), ports


def describe(component=None):
    """给 MCP 用的几何说明；component 为空返回全表。"""
    table = knowledge.geometry_table()
    if not component:
        return table
    c = component.lower()
    if c in ("and", "or", "nand", "nor", "xor", "xnor", "not", "gate"):
        if c == "gate":
            return {"widths": GATE_WIDTH, "rule": table["gate"]["formula"],
                    "ports_2in": gate_ports("AND", 2)[0], "body_2in": gate_ports("AND", 2)[1]}
        pts, body = gate_ports(c.upper(), 2)
        return {"kind": c.upper(), "width": gate_width(c.upper()), "ports_2in": pts, "body": body}
    if c in ("dff", "d", "flipflop", "d flip-flop"):
        return {"ports": DFF_PORTS, "body": DFF_BODY,
                "note": "classic 外观；上升沿由 trigger=rising 控制；R/S 悬空不影响"}
    if c in ("splitter", "splitter4"):
        pts, body = splitter_ports(4)
        return {"ports": pts, "body": body, "note": "合并侧在 loc，分线侧 bit0 在最上"}
    if c in ("sub", "subcircuit"):
        return {"rule": table["subcircuit"]["formula"]}
    return {"error": f"未知元件 {component}", "可选": ["gate", "and", "nand", "xor", "dff", "splitter", "sub"]}
