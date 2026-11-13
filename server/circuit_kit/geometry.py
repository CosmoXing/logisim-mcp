"""元件几何查询：把端口偏移/包围盒统一成一份可查询的数据。

权威来源：logisim-evolution 5.0 probe_component 实测（见 knowledge.json 的 geometry）。
"""

import math
import re

from . import knowledge, netlist

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


def splitter_ports(fanout=4, facing="east", appear="left"):
    return netlist.splitter_ports(fanout, facing, appear), \
        netlist.splitter_body(fanout, facing, appear)


def splitter_body(fanout=4, facing="east", appear="left"):
    return netlist.splitter_body(fanout, facing, appear)


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


def _ports_json(pts, widths=None):
    return {k: list(v) for k, v in pts.items()}, widths or {}


def describe(component=None, select=None, width=None):
    """给 MCP 用的几何说明；component 为空返回全表。

    component 支持：gate/and[2]/or/not/nand/nor/xor/xnor、dff/tff、splitter[4][/west]、
    mux[4|4:1]、decoder[3]、register[32]、comparator[3]、pin、constant、tunnel、clock、
    led、ground、sub。未知名字返回提示，可改用 circ_probe 走 Java 桥实测。
    """
    table = knowledge.geometry_table()
    if not component:
        return table
    raw = str(component).strip()
    key = re.sub(r"[\s_\-]+", "", raw.lower())

    def trailing(default=None):
        m = re.search(r"(\d+)$", key)
        return int(m.group(1)) if m else default

    def kb(name):
        return table.get(name)

    gates = {"and", "or", "not", "nand", "nor", "xor", "xnor"}
    gate = next((g for g in gates if key.startswith(g)), None)
    if key == "gate" or (gate and (key == gate or key[len(gate):].isdigit())):
        if key == "gate":
            return {"widths": GATE_WIDTH, "rule": (kb("gate") or {}).get("formula", ""),
                    "ports_2in": gate_ports("AND", 2)[0], "body_2in": gate_ports("AND", 2)[1],
                    "kb": kb("gate")}
        inputs = trailing(1 if gate == "not" else 2)
        if not 1 <= inputs <= 8:
            return {"error": f"{raw} 的输入数只支持 1~8"}
        pts, body = gate_ports(gate.upper(), inputs)
        return {"kind": gate.upper(), "inputs": inputs, "ports": pts, "body": body,
                "width": GATE_WIDTH[gate.upper()], "kb": kb("gate")}

    if key in ("dff", "d", "dflipflop", "flipflop"):
        return {"kind": "D Flip-Flop", "ports": DFF_PORTS, "body": DFF_BODY,
                "note": "classic 外观；上升沿由 trigger=rising 控制；R/S 悬空不影响"}
    if key in ("tff", "t", "tflipflop"):
        return {"kind": "T Flip-Flop", "ports": netlist.TFF_PORTS, "body": DFF_BODY,
                "note": "端口与 D 触发器同构，T 替代 D"}

    if key.startswith("split"):
        fanout = trailing(4)
        facing = "west" if "west" in key else "east"
        appear = "center" if "center" in key else ("right" if "right" in key else "left")
        pts, body = splitter_ports(fanout, facing, appear)
        geo = kb("splitter") or {}
        return {"kind": "Splitter", "fanout": fanout, "facing": facing, "appear": appear,
                "ports": {k: list(v) for k, v in pts.items()}, "body": list(body),
                "port_widths": {"in": "incoming", **{f"b{i}": 1 for i in range(fanout)}},
                "note": geo.get("_note", ""),
                "kb": geo.get(facing)}

    if key.startswith(("multiplex", "mux")):
        n = select
        if n is None:
            ch = re.search(r"(\d+)\s*:", raw)
            if ch:
                n = max(1, (int(ch.group(1)) - 1).bit_length())
            else:
                ch = trailing(2)
                n = max(1, (ch - 1).bit_length())
        n = max(1, min(int(n), 6))
        w = int(width) if width else 1
        facing = "west" if "west" in key else "east"
        enable = "enable" in key
        pts = netlist.mux_ports(n, facing, enable)
        widths = {k: (w if k.startswith("in") or k == "out" else n) for k in pts}
        if "enable" in pts:
            widths["enable"] = 1
        geo = kb("mux") or {}
        return {"kind": "Multiplexer", "select": n, "channels": 1 << n, "width": w,
                "facing": facing, "enable": enable,
                "ports": {k: list(v) for k, v in pts.items()}, "port_widths": widths,
                "body": list(netlist.mux_body(n, facing)),
                "note": geo.get("_note", ""), "kb": geo.get(f"{1 << n}:1")}

    if key.startswith("dec") or key.startswith("decoder"):
        n = int(select) if select else trailing(2)
        n = max(1, min(n, 8))
        facing = "west" if "west" in key else "east"
        enabled = "noenable" not in key
        pts = netlist.decoder_ports(n, facing, enabled)
        widths = {k: (n if k == "sel" else 1) for k in pts}
        geo = kb("decoder") or {}
        return {"kind": "Decoder", "select": n, "outputs": 1 << n,
                "facing": facing, "enable": enabled,
                "ports": {k: list(v) for k, v in pts.items()}, "port_widths": widths,
                "body": list(netlist.decoder_body(n, facing)),
                "note": geo.get("_note", ""), "kb": geo}

    if key.startswith("reg"):
        w = int(width) if width else trailing(1)
        geo = kb("register32") or {}
        return {"kind": "Register", "width": w,
                "ports": {k: list(v) for k, v in netlist.REGISTER_PORTS.items()},
                "port_widths": {"D": w, "Q": w, "en": 1, "clk": 1, "clr": 1},
                "body": list(netlist.REGISTER_BODY),
                "note": geo.get("_note", "") + "；width 只影响端口位宽，不影响坐标",
                "kb": geo}

    if key.startswith(("comparator", "compare", "cmp")):
        w = int(width) if width else trailing(1)
        return {"kind": "Comparator", "width": w,
                "ports": {k: list(v) for k, v in netlist.COMPARATOR_PORTS.items()},
                "port_widths": {"a": w, "b": w, "gt": 1, "eq": 1, "lt": 1},
                "body": list(netlist.COMPARATOR_BODY),
                "note": (kb("comparator") or {}).get("_note", ""),
                "kb": kb("comparator")}

    if key.startswith("pin"):
        geo = kb("pin") or {}
        facing = "west" if "west" in key else "east"
        return {"kind": "Pin", "facing": facing, "ports": {"p": [0, 0]},
                "body": list((geo.get(facing) or {}).get("body") or [-50, -10, 50, 20]),
                "note": (geo.get("_note") or "端口就是 loc；标签画在框外侧，x 太小时会被面板挡住")}

    if key.startswith("const"):
        geo = kb("constant") or {}
        return {"kind": "Constant", "ports": geo.get("ports", {"out": [0, 0]}),
                "body": geo.get("body"), "port_widths": {"out": "width 属性"}}

    if key.startswith("tunnel"):
        return {"kind": "Tunnel", "ports": {"p": [0, 0]}, "note": "同名隧道在**同一层电路**内互通"}
    if key.startswith("clock"):
        return {"kind": "Clock", "ports": {"p": [0, 0]}, "body": [5, -15, 35, 15]}
    if key.startswith("led"):
        return {"kind": "LED", "ports": {"p": [0, 0]}, "body": [5, -12, 32, 12]}
    if key.startswith("ground"):
        return {"kind": "Ground", "ports": {"p": [0, 0]}, "port_widths": {"p": 1}}
    if key.startswith("sub"):
        return {"rule": (kb("subcircuit") or {}).get("formula", "")}

    if key in table:
        return table[key]
    return {"error": f"未知元件 {component}",
            "可选": ["gate", "and", "or", "nand", "xor", "dff", "tff", "splitter",
                     "mux", "decoder", "register", "comparator", "pin", "constant",
                     "tunnel", "clock", "led", "ground", "sub"],
            "hint": "任意元件（含 TTL/算术库）可用 circ_probe 让 Logisim 自己报几何"}
