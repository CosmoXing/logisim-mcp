"""读取 .circ 文本 → 重建网表 → 仿真（独立校验器）。

只依据 Logisim 的连通规则：连接点必须在"某根线的端点"或"元件端口"上；
纯内点交叉不导通；共线相接的导线等价合并。
"""

import math
import xml.etree.ElementTree as ET


def gate_ports(kind, inputs):
    if kind == "NOT":
        w = 30
    else:
        bonus = 10 if kind in ("XOR", "XNOR") else 0
        neg = 10 if kind in ("NAND", "NOR", "XNOR") else 0
        w = 50 + bonus + neg
    if inputs == 1:
        return {"out": (0, 0), "a": (-w, 0)}
    if inputs == 2:
        return {"out": (0, 0), "a": (-w, -20), "b": (-w, 20)}
    top = -10 * (inputs - 1)
    pts = {"out": (0, 0)}
    for i, nm in enumerate("abcdefgh"[:inputs]):
        pts[nm] = (-w, top + 20 * i)
    return pts


DFF_PORTS = {"D": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
             "R": (-10, 30), "S": (-30, 30)}


def splitter_ports(fanout):
    pts = {"in": (0, 0)}
    for i in range(fanout):
        pts[f"b{i}"] = (20, -20 + 10 * i)
    return pts


def _round10(v):
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


def sub_port_offsets(pins):
    """pins: [(label, x, y, facing)] → {label: (dx, dy)} 相对实例 loc。"""
    west = sorted([p for p in pins if p[3] == "east"], key=lambda p: (p[2], p[1]))
    east = sorted([p for p in pins if p[3] == "west"], key=lambda p: (p[2], p[1]))
    nw, ne = len(west), len(east)
    max_h = max(nw, ne)
    oe, ow = _offs(ne, nw, 0), _offs(nw, ne, 0)
    width = _dim(0, max_h)
    ax = width if ne > 0 else 0
    ay = oe if ne > 0 else 0
    rx, ry = _round10(50 + ax), _round10(50 + ay)
    out = {}
    for i, (lab, *_rest) in enumerate(west):
        out[lab] = (rx - (rx + ax), ry + ow + 10 * i - (ry + ay))
    for j, (lab, *_rest) in enumerate(east):
        out[lab] = (rx + width - (rx + ax), ry + oe + 10 * j - (ry + ay))
    return out


class Comp:
    def __init__(self, lib, name, loc, attrs):
        self.lib, self.name, self.loc, self.attrs = lib, name, loc, attrs


class Circuit:
    def __init__(self, name):
        self.name = name
        self.comps, self.wires, self.pins = [], [], []


def parse(path):
    root = ET.parse(path).getroot()
    circuits = {}
    for c in root.findall("circuit"):
        circ = Circuit(c.get("name"))
        for comp in c.findall("comp"):
            attrs = {a.get("name"): a.get("val") for a in comp.findall("a")}
            x, y = [int(v) for v in comp.get("loc", "(0,0)").strip("()").split(",")]
            cm = Comp(comp.get("lib"), comp.get("name"), (x, y), attrs)
            circ.comps.append(cm)
            if cm.name == "Pin":
                kind = attrs.get("type") or ("output" if attrs.get("output") in ("true", "1") else "input")
                circ.pins.append((attrs.get("label", ""), x, y, attrs.get("facing", "east"),
                                  kind, int(attrs.get("width", 1))))
        for w in c.findall("wire"):
            a = [int(v) for v in w.get("from").strip("()").split(",")]
            b = [int(v) for v in w.get("to").strip("()").split(",")]
            circ.wires.append((a[0], a[1], b[0], b[1]))
        circuits[circ.name] = circ
    return circuits, root.find("main").get("name")


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def on_seg(p, s):
    x, y = p
    x1, y1, x2, y2 = s
    if y1 == y2:
        return y == y1 and min(x1, x2) <= x <= max(x1, x2)
    if x1 == x2:
        return x == x1 and min(y1, y2) <= y <= max(y1, y2)
    return False


PORT_WIDTH = {}

SUPPORTED = {
    "Pin", "Splitter", "Tunnel", "Clock", "LED", "Ground", "Constant",
    "Hex Digit Display", "D Flip-Flop", "T Flip-Flop",
    "AND Gate", "OR Gate", "NOT Gate", "NAND Gate", "NOR Gate", "XOR Gate", "XNOR Gate",
}


class UnsupportedComponent(RuntimeError):
    """遇到仿真器不认识的元件时抛出，避免"元件被忽略但结果照跑"的静默错误。"""

    def __init__(self, comp):
        lib = comp.lib if comp.lib is not None else "子电路"
        self.component = getattr(comp, "name", "?")
        self.loc = getattr(comp, "loc", None)
        super().__init__(
            f"不支持的元件「{self.component}」(lib={lib}) @ {self.loc}；"
            f"网表仿真只认识：门电路、D/T 触发器、引脚、分线器、隧道、时钟、"
            f"LED、数码管、常量、接地、子电路。"
        )


class Sim:
    def __init__(self, circuits, main):
        self.circuits = circuits
        self.dsu = DSU()
        self.leaves = []
        self.pin_at = {}
        self._inst(circuits[main], "r", 0)
        # 归并到根 + 计算位宽
        self.netw = {}
        for lf in self.leaves:
            lf["nets"] = {k: self.dsu.find(v) for k, v in lf["ports"].items()}
            for k, n in lf["nets"].items():
                self.netw[n] = max(self.netw.get(n, 1), lf["w"].get(k, 1))
        self.val = {}
        self.ff = {i: 0 for i, lf in enumerate(self.leaves)
                   if lf["kind"] in ("D Flip-Flop", "T Flip-Flop")}
        # 时钟网：优先 Clock 组件，其次名字像时钟的根层引脚
        self.clk_net = None
        self.clk_drive = None
        for i, lf in enumerate(self.leaves):
            if lf["kind"] == "Clock":
                self.clk_net = lf["nets"]["p"]
                break
        if self.clk_net is None:
            for (path, lbl), p in self.pin_at.items():
                if path == "r" and lbl.lower() in ("cp", "clk", "clock", "ck"):
                    self.clk_net = self.dsu.find(p)
                    break
        # 静态判定分线器方向：位侧有外部驱动 -> 合并；否则总线侧有驱动 -> 拆分
        drv = {}
        for i, lf in enumerate(self.leaves):
            for k in ("out", "Q", "NQ", "p"):
                if k in lf["nets"]:
                    if lf["kind"] == "Pin" and (lf["attrs"].get("type") or
                                                ("output" if lf["attrs"].get("output") in ("true", "1") else "input")) == "output":
                        continue
                    if lf["kind"] == "Hex Digit Display":
                        continue
                    drv.setdefault(lf["nets"][k], set()).add(i)
        self.split_mode = {}
        for i, lf in enumerate(self.leaves):
            if lf["kind"] != "Splitter":
                continue
            f = int(lf["attrs"].get("fanout", 2))
            bits_have = any(drv.get(lf["nets"][f"b{b}"], set()) - {i} for b in range(f))
            bus_has = bool(drv.get(lf["nets"]["in"], set()) - {i})
            self.split_mode[i] = "merge" if bits_have or not bus_has else "split"

    # -------- 递归实例化
    def _inst(self, circ, path, depth):
        if depth > 8:
            raise RuntimeError("层次过深")
        pts = set()
        for s in circ.wires:
            self.dsu.union((path, s[0], s[1]), (path, s[2], s[3]))
            pts.add((s[0], s[1]))
            pts.add((s[2], s[3]))
        pin_out = {}
        for c in circ.comps:
            if c.lib is None:      # 子电路实例：端口由子电路引脚位置推导
                child = self.circuits.get(c.name)
                if child is None:
                    raise RuntimeError(f"缺少子电路 {c.name}")
                offs = sub_port_offsets([(l, x, y, f) for (l, x, y, f, k, w) in child.pins])
                for dx, dy in offs.values():
                    pts.add((c.loc[0] + dx, c.loc[1] + dy))
                continue
            pm = self._ports(c)
            for n, (dx, dy) in pm.items():
                pts.add((c.loc[0] + dx, c.loc[1] + dy))
            if c.name == "Pin":
                pin_out[c.attrs.get("label", "")] = (path, c.loc[0], c.loc[1])
                self.pin_at[(path, c.attrs.get("label", ""))] = (path, c.loc[0], c.loc[1])
        for p in pts:
            key = (path, p[0], p[1])
            for s in circ.wires:
                if on_seg(p, s):
                    self.dsu.union(key, (path, s[0], s[1]))
        # 隧道：同一层内相同 label 视为同一网络
        tunnels = {}
        for c in circ.comps:
            if c.name == "Tunnel":
                tunnels.setdefault(c.attrs.get("label", ""), []).append(
                    (path, c.loc[0], c.loc[1]))
        for label, points in tunnels.items():
            for q in points[1:]:
                self.dsu.union(points[0], q)
        for c in circ.comps:
            if c.lib is None:
                child = self.circuits.get(c.name)
                if child is None:
                    raise RuntimeError(f"缺少子电路 {c.name}")
                cpath = f"{path}/{c.name}@{c.loc[0]},{c.loc[1]}"
                cpins = self._inst(child, cpath, depth + 1)
                offs = sub_port_offsets([(l, x, y, f) for (l, x, y, f, k, w) in child.pins])
                for lbl, (dx, dy) in offs.items():
                    if lbl in cpins:
                        self.dsu.union((path, c.loc[0] + dx, c.loc[1] + dy), cpins[lbl])
                continue
            pm = self._ports(c)
            widths = self._widths(c)
            self.leaves.append(dict(kind=c.name, lib=c.lib, loc=c.loc, attrs=c.attrs,
                                    path=path,
                                    ports={n: (path, c.loc[0] + dx, c.loc[1] + dy)
                                           for n, (dx, dy) in pm.items()},
                                    w=widths))
        return pin_out

    @staticmethod
    def _ports(c):
        n = c.name
        if n == "Pin":
            return {"p": (0, 0)}
        if n.endswith("Gate"):
            kind = n.split()[0]
            default_inputs = 1 if kind == "NOT" else 2
            return gate_ports(kind, int(c.attrs.get("inputs", default_inputs)))
        if n in ("D Flip-Flop", "T Flip-Flop"):
            return DFF_PORTS
        if n == "Splitter":
            return splitter_ports(int(c.attrs.get("fanout", 2)))
        if n == "Tunnel":
            return {"p": (0, 0)}
        if n in ("Clock", "LED", "Ground", "Constant", "Hex Digit Display"):
            return {"p": (0, 0)}
        if n in SUPPORTED:
            return {}
        raise UnsupportedComponent(c)

    @staticmethod
    def _widths(c):
        n = c.name
        if n == "Pin":
            return {"p": int(c.attrs.get("width", 1))}
        if n == "Hex Digit Display":
            return {"p": 4}
        if n == "Splitter":
            f = int(c.attrs.get("fanout", 2))
            d = {"in": f}
            for i in range(f):
                d[f"b{i}"] = 1
            return d
        if n == "Ground":
            return {"p": 1}
        if n == "Constant":
            return {"p": int(c.attrs.get("width", 1))}
        if n == "Tunnel":
            return {"p": 1}
        return {}

    # -------- 仿真
    def bind_clock(self, label):
        """显式指定时钟信号名（根层引脚标签）。"""
        for (path, lbl), p in self.pin_at.items():
            if path == "r" and lbl == label:
                self.clk_net = self.dsu.find(p)
                return True
        return False

    def run(self, inputs, cycles, clock=None):
        if clock:
            self.bind_clock(clock)
        self.clk_drive = 0
        self._settle(inputs)
        snaps = [self._snap()]
        for _ in range(cycles):
            self._pulse(inputs)
            snaps.append(self._snap())
        return snaps

    def _is_clk_net(self, net):
        return self.clk_net is not None and net == self.clk_net

    def _settle(self, inputs):
        for _ in range(300):
            new = {}
            for i, lf in enumerate(self.leaves):
                kind, nets = lf["kind"], lf["nets"]
                if kind == "Pin":
                    k = lf["attrs"].get("type") or ("output" if lf["attrs"].get("output") in ("true", "1") else "input")
                    if k == "input" and lf.get("path") == "r" and not self._is_clk_net(nets["p"]):
                        self._write(new, nets["p"], (inputs.get(lf["attrs"].get("label", ""), 0),))
                    continue
                if kind in ("Clock", "Tunnel"):
                    continue
                if kind == "Ground":
                    self._write(new, nets["p"], (0,))
                    continue
                if kind == "Constant":
                    w = int(lf["attrs"].get("width", 1))
                    try:
                        raw = int(str(lf["attrs"].get("value", "0")), 16)
                    except ValueError:
                        raw = 0
                    self._write(new, nets["p"], tuple((raw >> b) & 1 for b in range(w)))
                    continue
                if kind == "Splitter":
                    f = int(lf["attrs"].get("fanout", 2))
                    if self.split_mode.get(i) == "split":
                        bus = self._get(nets["in"])
                        if bus and len(bus) == f:
                            for b in range(f):
                                self._write(new, nets[f"b{b}"], (bus[b],))
                        else:
                            for b in range(f):
                                self._write(new, nets[f"b{b}"], ("U",))
                    else:
                        bits = []
                        for b in range(f):
                            v = self._get(nets[f"b{b}"])
                            bits.append(v[0] if v else "U")
                        self._write(new, nets["in"], tuple(bits))
                    continue
                if kind.endswith("Gate"):
                    g = kind.split()[0]
                    a = self._bit(self._get(nets["a"]))
                    if g == "NOT":
                        self._write(new, nets["out"], (0 if a == 1 else (1 if a == 0 else "E"),))
                    else:
                        b = self._bit(self._get(nets["b"]))
                        self._write(new, nets["out"], (self._gate(g, a, b),))
                    continue
                if kind in ("D Flip-Flop", "T Flip-Flop"):
                    self._write(new, nets["Q"], (self.ff[i],))
                    self._write(new, nets["NQ"], (1 - self.ff[i],))
                    continue
            if self.clk_net is not None and self.clk_drive is not None:
                new[self.clk_net] = (self.clk_drive,)
            changed = new != self.val
            self.val = new
            if not changed:
                return
        raise RuntimeError("组合逻辑未收敛（振荡）")

    @staticmethod
    def _write(new, net, val):
        if net in new and new[net] != val:
            new[net] = tuple("E" for _ in val)
        else:
            new[net] = val

    def _clk_state(self):
        out = {}
        for i, lf in enumerate(self.leaves):
            if lf["kind"] in ("D Flip-Flop", "T Flip-Flop"):
                out[i] = self._bit(self._get(lf["nets"]["CLK"]))
        return out

    def _pulse(self, inputs):
        """一个完整时钟脉冲；逐触发器检测各自 CLK 的上升沿（支持异步级联）。"""
        self.clk_drive = 0
        self._settle(inputs)
        last = self._clk_state()

        self.clk_drive = 1
        self._settle(inputs)

        for _ in range(64):
            cur = self._clk_state()
            fired = [i for i in cur if last.get(i) == 0 and cur[i] == 1]
            if not fired:
                break
            for i in fired:
                lf = self.leaves[i]
                if lf["kind"] == "D Flip-Flop":
                    d = self._bit(self._get(lf["nets"]["D"]))
                    self.ff[i] = 1 if d == 1 else 0
                else:
                    t = self._bit(self._get(lf["nets"]["D"]))
                    if t == 1:
                        self.ff[i] ^= 1
            self._settle(inputs)
            last = cur

        self.clk_drive = 0
        self._settle(inputs)

    def _get(self, net):
        return self.val.get(net)

    @staticmethod
    def _bit(v):
        return "U" if v is None else v[0]

    @staticmethod
    def _gate(g, a, b):
        if "E" in (a, b):
            return "E"
        if "U" in (a, b):
            return "U"
        x, y = a == 1, b == 1
        r = {"AND": x and y, "NAND": not (x and y), "OR": x or y,
             "NOR": not (x or y), "XOR": x != y, "XNOR": x == y}[g]
        return 1 if r else 0

    def _snap(self):
        out = {}
        for (path, lbl), p in self.pin_at.items():
            if path == "r":
                v = self.val.get(self.dsu.find(p))
                out[lbl] = v if v is not None else ("U",)
        for lf in self.leaves:
            if lf["kind"] == "Hex Digit Display":
                out["disp:" + lf["attrs"].get("label", "")] = self.val.get(lf["nets"]["p"], ("U",))
            elif lf["kind"] == "LED":
                out["led"] = self.val.get(lf["nets"]["p"], ("U",))
        return out

    # -------- 诊断：列出可疑网络（未驱动 / 多驱动）
    def diagnose(self):
        drivers = {}
        for i, lf in enumerate(self.leaves):
            for k, n in lf["nets"].items():
                if k in ("out", "Q", "NQ", "p", "b0", "b1", "b2", "b3", "in"):
                    continue
            for k in ("out", "Q", "NQ"):
                if k in lf["nets"]:
                    drivers.setdefault(lf["nets"][k], []).append(lf["kind"])
        bad = {k: v for k, v in drivers.items() if len(set(v)) > 1}
        return bad
