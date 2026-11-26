"""读取 .circ 文本 → 重建网表 → 仿真（独立校验器）。

只依据 Logisim 的连通规则：连接点必须在"某根线的端点"或"元件端口"上；
纯内点交叉不导通；共线相接的导线等价合并。
"""

import xml.etree.ElementTree as ET

from . import vprofile


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
    if inputs == 3:
        return {"out": (0, 0), "a": (-w, -20), "b": (-w, 0), "c": (-w, 20)}
    # n>=4：10px 间距，半高 10*(n//2)，偶数输入跳过 0（4.1 源码/实测）
    half = 10 * (inputs // 2)
    ys = [y for y in range(-half, half + 1, 10) if not (inputs % 2 == 0 and y == 0)]
    pts = {"out": (0, 0)}
    for i, nm in enumerate("abcdefgh"[:inputs]):
        pts[nm] = (-w, ys[i])
    return pts


DFF_PORTS = {"D": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
             "R": (-10, 30), "S": (-30, 30)}
TFF_PORTS = {"T": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
             "R": (-10, 30), "S": (-30, 30)}

# 5.0 probe_component 实测；包围盒/端口均与位宽无关，body 统一为 (x1,y1,x2,y2)
REGISTER_PORTS = {"D": (0, 30), "en": (0, 50), "clk": (0, 70), "clr": (30, 90),
                  "Q": (60, 30)}
REGISTER_BODY = (0, 0, 60, 90)
COMPARATOR_PORTS = {"a": (-40, -10), "b": (-40, 10),
                    "gt": (0, -10), "eq": (0, 0), "lt": (0, 10)}
COMPARATOR_BODY = (-40, -20, 0, 20)


def splitter_ports(fanout, facing="east", appear="left"):
    """b0 永远在最上；appear=left/center/right 决定出口相对 bus 的上下位置（5.0 实测）。"""
    appear = str(appear).lower()
    if appear == "center":
        top = -10 * (fanout // 2)
    elif (str(facing).lower() == "east") == (appear == "left"):
        top = -10 * fanout
    else:
        top = 10
    x = 20 if str(facing).lower() == "east" else -20
    pts = {"in": (0, 0)}
    for i in range(fanout):
        pts[f"b{i}"] = (x, top + 10 * i)
    return pts


def splitter_body(fanout, facing="east", appear="left"):
    pts = splitter_ports(fanout, facing, appear)
    ys = [dy for k, (dx, dy) in pts.items() if k.startswith("b")]
    y1, y2 = min(ys + [0]), max(ys + [0]) + 1
    if str(facing).lower() == "west":
        return (-20, y1, 1, y2)
    return (0, y1, 21, y2)


def mux_select(attrs):
    """Multiplexer 的 select 属性是选择位宽：2^n 路输入，缺省 1。"""
    try:
        return max(1, int(attrs.get("select", 1)))
    except (TypeError, ValueError):
        return 1


def decoder_select(attrs):
    try:
        return max(1, int(attrs.get("select", 1)))
    except (TypeError, ValueError):
        return 1


def _mirror(pts):
    """facing=west 是水平镜像。"""
    return {k: (-x, y) for k, (x, y) in pts.items()}


def _mirror_body(body):
    x1, y1, x2, y2 = body
    return (-x2, y1, -x1, y2)


def mux_ports(select, facing="east", enable=False):
    """select=n → 2^n 路输入；2:1 外形更窄，n≥2 输入口从 -10*2^(n-1) 起 10px 间距。"""
    n = 1 << select
    if select == 1:
        pts = {"in0": (-30, -10), "in1": (-30, 10), "sel": (-20, 20), "out": (0, 0)}
    else:
        top = -10 * (1 << (select - 1))
        pts = {f"in{i}": (-40, top + 10 * i) for i in range(n)}
        pts["sel"] = (-20, max(20, 10 << (select - 1)))
        pts["out"] = (0, 0)
    if enable:
        pts["enable"] = (-10, pts["sel"][1])
    return _mirror(pts) if str(facing).lower() == "west" else pts


def mux_body(select, facing="east"):
    if select == 1:
        body = (-30, -20, 0, 20)
    else:
        ytop = -10 * ((1 << (select - 1)) + 1)
        body = (-40, ytop, 0, ytop + 10 * (1 << select) + 20)
    return _mirror_body(body) if str(facing).lower() == "west" else body


def decoder_ports(select, facing="east", enabled=True):
    """out0 在最上（y=-10*2^n），sel/en 都在底部，en 与 sel 只差 10px。"""
    n = 1 << select
    pts = {"sel": (0, 0)}
    if enabled:
        pts["en"] = (-10, 0)
    for i in range(n):
        pts[f"out{i}"] = (20, -10 * (n - i))
    return _mirror(pts) if str(facing).lower() == "west" else pts


def decoder_body(select, facing="east"):
    n = 1 << select
    body = (-20, -10 * (n + 1), 20, 10)
    return _mirror_body(body) if str(facing).lower() == "west" else body


def sub_port_offsets(pins, source=""):
    """pins: [(label, x, y, facing)] → {label: (dx, dy)} 相对实例 loc。

    source 为 .circ 的 <project source="...">：4.1 走固定 220 宽、20px 间距的规则；
    其余（3.9 / 5.0 / 2.x）沿用经典公式。
    """
    return vprofile.sub_geometry(pins, source)[1]


def instance_ports(child):
    """子电路实例端口偏移：自定义外观读 circ-port 的符号坐标，否则按经典布局推导。

    H15/H24：按引脚标签建网表会跨电路串名，按经典布局推端口又会脱开导线；
    这里以内部 Pin 坐标为准把两者对上。
    """
    if child.aports:
        by_pin = {(x, y): label for (label, x, y, _f, _k, _w) in child.pins}
        ax, ay = getattr(child, "anchor", (0, 0))
        out = {}
        for _dir, px, py, sx, sy in child.aports:
            label = by_pin.get((px, py))
            if label is not None:
                # circ-port 的符号坐标相对 <circ-anchor>，实例 loc 就是锚点落点
                out[label] = (sx - ax, sy - ay)
        if out:
            return out
    return sub_port_offsets([(l, x, y, f) for (l, x, y, f, k, w) in child.pins],
                            getattr(child, "source", ""))


class Comp:
    def __init__(self, lib, name, loc, attrs):
        self.lib, self.name, self.loc, self.attrs = lib, name, loc, attrs


class Circuit:
    def __init__(self, name):
        self.name = name
        self.source = ""      # <project source="4.1.0">：决定子电路符号几何
        self.comps, self.wires, self.pins = [], [], []
        self.aports = []   # 自定义外观的符号端口：[(dir, pin_x, pin_y, sym_x, sym_y)]
        self.anchor = (0, 0)   # <circ-anchor>：circ-port 的 x/y 是相对它的，不是相对 loc


def _point(text):
    x, y = [int(v) for v in str(text).strip().strip("()").split(",")]
    return x, y


def parse(path):
    root = ET.parse(path).getroot()
    source = root.get("source", "")
    circuits = {}
    for c in root.findall("circuit"):
        circ = Circuit(c.get("name"))
        circ.source = source
        for comp in c.findall("comp"):
            attrs = {a.get("name"): a.get("val") for a in comp.findall("a")}
            x, y = _point(comp.get("loc", "(0,0)"))
            cm = Comp(comp.get("lib"), comp.get("name"), (x, y), attrs)
            circ.comps.append(cm)
            if cm.name == "Pin":
                kind = attrs.get("type") or ("output" if attrs.get("output") in ("true", "1") else "input")
                circ.pins.append((attrs.get("label", ""), x, y, attrs.get("facing", "east"),
                                  kind, int(attrs.get("width", 1))))
        appear = c.find("appear")
        if appear is not None:
            anchor = appear.find("circ-anchor")
            if anchor is not None:
                try:
                    circ.anchor = (int(anchor.get("x", 0)), int(anchor.get("y", 0)))
                except (TypeError, ValueError):
                    pass
            for cp in appear.findall("circ-port"):
                try:
                    px, py = _point(cp.get("pin"))
                    sx, sy = int(cp.get("x", 0)), int(cp.get("y", 0))
                except (TypeError, ValueError):
                    continue
                circ.aports.append((cp.get("dir", ""), px, py, sx, sy))
        for w in c.findall("wire"):
            a = [int(v) for v in w.get("from").strip("()").split(",")]
            b = [int(v) for v in w.get("to").strip("()").split(",")]
            circ.wires.append((a[0], a[1], b[0], b[1]))
        circuits[circ.name] = circ
    main = root.find("main")
    if main is None or not main.get("name"):
        raise ValueError(".circ 缺少 <main name=\"...\"/> 元素，无法确定顶层电路")
    return circuits, main.get("name")


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
    "Hex Digit Display", "D Flip-Flop", "T Flip-Flop", "Text",
    "AND Gate", "OR Gate", "NOT Gate", "NAND Gate", "NOR Gate", "XOR Gate", "XNOR Gate",
    "Multiplexer", "Decoder", "Register", "Comparator", "7-Segment Display",
}

# I/O 库 7 段数码管：每个段脚 1 位；decimalPoint=true 时多一个 dp 脚
# （3.9 / 5.0 / 2.16 实测坐标一致，见 docs/VERSIONS.md）
SEG7_PORTS = {"a": (20, 0), "b": (30, 0), "c": (20, 60), "d": (10, 60),
              "e": (0, 60), "f": (10, 0), "g": (0, 0), "dp": (30, 60)}

# 纯注释元件：没有电气端口，.circ 里可能不带 lib 属性
ANNOTATIONS = {"Text", "Label", "Anchor"}


def output_ports(kind, nets=None):
    """该元件会驱动网络的端口名（Pin/Splitter 由调用方另行判断）。"""
    if kind.endswith("Gate"):
        return ["out"]
    if kind in ("D Flip-Flop", "T Flip-Flop"):
        return ["Q", "NQ"]
    if kind == "Register":
        return ["Q"]
    if kind == "Multiplexer":
        return ["out"]
    if kind == "Decoder":
        return [k for k in (nets or {}) if k.startswith("out")]
    if kind == "Comparator":
        return ["gt", "eq", "lt"]
    if kind in ("Clock", "Ground", "Constant"):
        return ["p"]
    return []


def is_source(lf):
    """连接性意义上的驱动源：根层输入引脚和真正会输出电平的元件。

    子电路内部输入 Pin 只是"父电路接进来的入口"，在展平网表里是读者，不能当驱动。
    """
    kind = lf["kind"]
    if kind == "Pin":
        t = lf["attrs"].get("type") or ("output" if lf["attrs"].get("output") in ("true", "1") else "input")
        return t == "input" and lf.get("path") == "r"
    if kind == "Splitter":
        return False
    return bool(output_ports(kind, lf["nets"]))


class UnsupportedComponent(RuntimeError):
    """遇到仿真器不认识的元件时抛出，避免"元件被忽略但结果照跑"的静默错误。"""

    def __init__(self, comp):
        lib = comp.lib if comp.lib is not None else "子电路"
        self.component = getattr(comp, "name", "?")
        self.lib = lib
        self.loc = getattr(comp, "loc", None)
        super().__init__(
            f"不支持的元件「{self.component}」(lib={lib}) @ {self.loc}；"
            f"网表仿真只认识：门电路、D/T 触发器、寄存器、多路选择器、译码器、"
            f"比较器、引脚、分线器、隧道、时钟、LED、数码管、常量、接地、子电路。"
        )


class Sim:
    def __init__(self, circuits, main, strict=True):
        self.circuits = circuits
        self.strict = strict
        self.unsupported = []
        self._bad = set()
        self.dsu = DSU()
        self.leaves = []
        self.segs = {}
        self.inst_ports = {}
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
        self.ff_trigger = {i: str(lf["attrs"].get("trigger", "rising")).lower()
                           for i, lf in enumerate(self.leaves)
                           if lf["kind"] in ("D Flip-Flop", "T Flip-Flop")}
        # 寄存器：初始值取 0（与 Logisim 上电状态一致），clr 异步清零，en=1 才在边沿装入
        self.reg = {i: tuple(0 for _ in range(lf["w"].get("Q", 1)))
                    for i, lf in enumerate(self.leaves) if lf["kind"] == "Register"}
        self.reg_trigger = {i: str(lf["attrs"].get("trigger", "rising")).lower()
                            for i, lf in enumerate(self.leaves) if lf["kind"] == "Register"}
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
            if not is_source(lf):
                continue
            keys = ["p"] if lf["kind"] == "Pin" else output_ports(lf["kind"], lf["nets"])
            for k in keys:
                if k in lf["nets"]:
                    drv.setdefault(lf["nets"][k], set()).add(i)
        self.split_mode = {}
        for i, lf in enumerate(self.leaves):
            if lf["kind"] != "Splitter":
                continue
            f = int(lf["attrs"].get("fanout", 2))
            bits_have = any(drv.get(lf["nets"][f"b{b}"], set()) - {i} for b in range(f))
            bus_has = bool(drv.get(lf["nets"]["in"], set()) - {i})
            self.split_mode[i] = "merge" if bits_have or not bus_has else "split"

    def _safe_ports(self, c):
        """strict=False 时把不认识的元件降级成"无端口占位"，让体检仍能给出部分结果。"""
        if c in self._bad:
            return None
        try:
            return self._ports(c)
        except UnsupportedComponent as exc:
            if self.strict:
                raise
            self._bad.add(c)
            self.unsupported.append({"component": exc.component, "lib": exc.lib,
                                     "at": list(exc.loc) if exc.loc else None})
            return None

    # -------- 递归实例化
    def _inst(self, circ, path, depth):
        if depth > 8:
            raise RuntimeError("层次过深")
        self.segs[path] = circ.wires
        pts = set()
        for s in circ.wires:
            self.dsu.union((path, s[0], s[1]), (path, s[2], s[3]))
            pts.add((s[0], s[1]))
            pts.add((s[2], s[3]))
        pin_out = {}
        for c in circ.comps:
            if c.lib is None and c.name in ANNOTATIONS and c.name not in self.circuits:
                continue
            if c.lib is None:      # 子电路实例：端口由子电路外观/引脚位置推导
                child = self.circuits.get(c.name)
                if child is None:
                    raise RuntimeError(f"缺少子电路 {c.name}")
                offs = instance_ports(child)
                for dx, dy in offs.values():
                    pts.add((c.loc[0] + dx, c.loc[1] + dy))
                    self.inst_ports.setdefault(path, []).append((c.loc[0] + dx, c.loc[1] + dy, c.name))
                continue
            pm = self._safe_ports(c)
            if pm is None:
                continue
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
            if c.lib is None and c.name in ANNOTATIONS and c.name not in self.circuits:
                continue
            if c.lib is None:
                child = self.circuits.get(c.name)
                if child is None:
                    raise RuntimeError(f"缺少子电路 {c.name}")
                cpath = f"{path}/{c.name}@{c.loc[0]},{c.loc[1]}"
                cpins = self._inst(child, cpath, depth + 1)
                offs = instance_ports(child)
                for lbl, (dx, dy) in offs.items():
                    if lbl in cpins:
                        self.dsu.union((path, c.loc[0] + dx, c.loc[1] + dy), cpins[lbl])
                continue
            pm = self._safe_ports(c)
            if pm is None:
                continue
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
            return DFF_PORTS if n == "D Flip-Flop" else TFF_PORTS
        if n == "Splitter":
            return splitter_ports(int(c.attrs.get("fanout", 2)),
                                  c.attrs.get("facing", "east"),
                                  c.attrs.get("appear", "left"))
        if n == "Multiplexer":
            enable = str(c.attrs.get("enable", "false")).lower() in ("true", "1")
            return mux_ports(mux_select(c.attrs), c.attrs.get("facing", "east"), enable)
        if n == "Decoder":
            enabled = str(c.attrs.get("enable", "true")).lower() not in ("false", "0")
            return decoder_ports(decoder_select(c.attrs), c.attrs.get("facing", "east"), enabled)
        if n == "Register":
            return REGISTER_PORTS
        if n == "Comparator":
            return COMPARATOR_PORTS
        if n == "7-Segment Display":
            pts = dict(SEG7_PORTS)
            if str(c.attrs.get("decimalPoint", "true")).lower() in ("false", "0"):
                pts.pop("dp")
            return pts
        if n == "Tunnel":
            return {"p": (0, 0)}
        if n in ("Clock", "LED", "Ground", "Constant", "Hex Digit Display", "Probe"):
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
            # 5.0 实测：incoming 缺省恒为 2（不随 fanout 变）
            incoming = int(c.attrs.get("incoming", 2))
            d = {"in": incoming}
            for i in range(f):
                d[f"b{i}"] = 1
            return d
        if n == "Ground":
            return {"p": 1}
        if n == "7-Segment Display":
            return {k: 1 for k in SEG7_PORTS}
        if n == "Constant":
            return {"p": int(c.attrs.get("width", 1))}
        if n == "Tunnel":
            return {"p": 0}      # 位宽由所在网络决定，不参与宽度一致性比较
        if n == "Probe":
            return {"p": 0}
        if n.endswith("Gate"):
            kind = n.split()[0]
            default_inputs = 1 if kind == "NOT" else 2
            ports = gate_ports(kind, int(c.attrs.get("inputs", default_inputs)))
            w = int(c.attrs.get("width", 1))
            return {k: w for k in ports}
        if n == "Multiplexer":
            sel = mux_select(c.attrs)
            w = int(c.attrs.get("width", 1))
            d = {f"in{i}": w for i in range(1 << sel)}
            d["sel"] = sel
            d["out"] = w
            if str(c.attrs.get("enable", "false")).lower() in ("true", "1"):
                d["enable"] = 1
            return d
        if n == "Decoder":
            sel = decoder_select(c.attrs)
            d = {"sel": sel}
            if str(c.attrs.get("enable", "true")).lower() not in ("false", "0"):
                d["en"] = 1
            for i in range(1 << sel):
                d[f"out{i}"] = 1
            return d
        if n == "Register":
            w = int(c.attrs.get("width", 1))
            return {"D": w, "Q": w, "en": 1, "clk": 1, "clr": 1}
        if n == "Comparator":
            w = int(c.attrs.get("width", 1))
            return {"a": w, "b": w, "gt": 1, "eq": 1, "lt": 1}
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
        self._settle_stable(inputs)
        snaps = [self._snap()]
        for _ in range(cycles):
            self._pulse(inputs)
            snaps.append(self._snap())
        return snaps

    def _is_clk_net(self, net):
        return self.clk_net is not None and net == self.clk_net

    def _settle_stable(self, inputs):
        """先收敛组合逻辑，再处理异步复位/置位；状态变了就重新收敛。"""
        for _ in range(16):
            self._settle(inputs)
            if not self._apply_async():
                return
        raise RuntimeError("异步复位/置位未收敛（反馈自激）")

    def _apply_async(self):
        changed = False
        for i, lf in enumerate(self.leaves):
            if lf["kind"] == "Register":
                if self._bit(self._get(lf["nets"].get("clr"))) == 1:
                    zero = tuple(0 for _ in self.reg[i])
                    if self.reg[i] != zero:
                        self.reg[i] = zero
                        changed = True
                continue
            if lf["kind"] not in ("D Flip-Flop", "T Flip-Flop"):
                continue
            r = self._bit(self._get(lf["nets"].get("R")))
            s = self._bit(self._get(lf["nets"].get("S")))
            if r == 1 and s != 1 and self.ff[i] != 0:
                self.ff[i] = 0
                changed = True
            elif s == 1 and r != 1 and self.ff[i] != 1:
                self.ff[i] = 1
                changed = True
        return changed

    @staticmethod
    def _pin_bits(value, width):
        """输入引脚取值 → 位宽对应的位元组（bit0 在前）。整数低位对齐，字符串 MSB 在前。"""
        width = max(1, int(width))
        if isinstance(value, (list, tuple)):
            bits = [1 if x in (1, "1", True) else 0 for x in value]
        elif isinstance(value, str) and value.strip() and all(ch in "01" for ch in value.strip()):
            bits = [int(ch) for ch in reversed(value.strip())]
        else:
            try:
                n = int(value)
            except (TypeError, ValueError):
                n = 0
            bits = [(n >> b) & 1 for b in range(width)]
        if len(bits) < width:
            bits += [0] * (width - len(bits))
        return tuple(bits[:width])

    def _settle(self, inputs):
        for _ in range(300):
            new = {}
            for i, lf in enumerate(self.leaves):
                kind, nets = lf["kind"], lf["nets"]
                if kind == "Pin":
                    k = lf["attrs"].get("type") or ("output" if lf["attrs"].get("output") in ("true", "1") else "input")
                    if k == "input" and lf.get("path") == "r" and not self._is_clk_net(nets["p"]):
                        raw = inputs.get(lf["attrs"].get("label", ""), 0)
                        self._write(new, nets["p"], self._pin_bits(raw, lf["w"].get("p", 1)))
                    continue
                if kind in ("Clock", "Tunnel", "Text", "Probe"):
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
                    self._eval_splitter(new, i, lf)
                    continue
                if kind.endswith("Gate"):
                    g = kind.split()[0]
                    vals = [self._bit(self._get(nets[p])) for p in "abcdefgh" if p in nets]
                    self._write(new, nets["out"], (self._gate(g, vals),))
                    continue
                if kind == "Multiplexer":
                    self._eval_mux(new, lf)
                    continue
                if kind == "Decoder":
                    self._eval_decoder(new, lf)
                    continue
                if kind == "Comparator":
                    self._eval_comparator(new, lf)
                    continue
                if kind == "Register":
                    self._write(new, nets["Q"], self.reg[i])
                    continue
                if kind in ("D Flip-Flop", "T Flip-Flop"):
                    r = self._bit(self._get(nets.get("R")))
                    s = self._bit(self._get(nets.get("S")))
                    if r == 1 and s == 1:
                        q = nq = "E"
                    elif r == 1:
                        q, nq = 0, 1
                    elif s == 1:
                        q, nq = 1, 0
                    else:
                        q = self.ff[i]
                        nq = 1 - q
                    self._write(new, nets["Q"], (q,))
                    self._write(new, nets["NQ"], (nq,))
                    continue
            if self.clk_net is not None and self.clk_drive is not None:
                new[self.clk_net] = (self.clk_drive,)
            changed = new != self.val
            self.val = new
            if not changed:
                return
        raise RuntimeError("组合逻辑未收敛（振荡）")

    def _eval_splitter(self, new, i, lf):
        """分线器：尊重 bit0..bitN 映射与 incoming 位宽（默认恒等映射）。"""
        nets, attrs = lf["nets"], lf["attrs"]
        f = int(attrs.get("fanout", 2))
        incoming = int(attrs.get("incoming", 2))
        bit_map = [int(attrs.get(f"bit{b}", b)) for b in range(f)]
        if self.split_mode.get(i) == "split":
            bus = self._get(nets["in"])
            if bus and len(bus) == incoming:
                for b in range(f):
                    src = bit_map[b]
                    self._write(new, nets[f"b{b}"], (bus[src] if 0 <= src < incoming else "U",))
            else:
                for b in range(f):
                    self._write(new, nets[f"b{b}"], ("U",))
            return
        bus = ["U"] * incoming
        for b in range(f):
            v = self._get(nets[f"b{b}"])
            if not v:
                continue
            dst = bit_map[b]
            if 0 <= dst < incoming:
                if bus[dst] != "U" and bus[dst] != v[0]:
                    bus[dst] = "E"
                else:
                    bus[dst] = v[0]
        self._write(new, nets["in"], tuple(bus))

    @staticmethod
    def _fit(val, width):
        """把端口值补齐/截断到目标位宽；无驱动时按 U 处理。"""
        width = max(1, int(width))
        if not val:
            return tuple("U" for _ in range(width))
        val = tuple(val)
        return val[:width] if len(val) >= width else val + tuple("U" for _ in range(width - len(val)))

    @staticmethod
    def _to_int(val, width, mode="twosComplement"):
        """位元组 → (整数, 未知标记)；有 U/E 时整数为 None。"""
        if not val:
            return None, "U"
        bits = tuple(val[:width])
        if "E" in bits:
            return None, "E"
        if "U" in bits:
            return None, "U"
        n = sum(1 << i for i, b in enumerate(bits) if b == 1)
        if bits and bits[-1] == 1:
            if mode == "onesComplement":
                n = -(((1 << width) - 1) - n)
            elif mode == "signedMagnitude":
                n = -(n & ((1 << (width - 1)) - 1))
            elif mode != "unsigned":
                n -= 1 << width
        return n, None

    def _sel_value(self, net):
        sel = self._get(net)
        if not sel:
            return None, "U"
        if "E" in sel:
            return None, "E"
        if "U" in sel:
            return None, "U"
        return sum(1 << i for i, b in enumerate(sel) if b == 1), None

    def _eval_mux(self, new, lf):
        w = lf["w"].get("out", 1)
        nets = lf["nets"]
        if "enable" in nets:
            en = self._bit(self._get(nets["enable"]))
            if en == 0:
                self._write(new, nets["out"], tuple("E" for _ in range(w)))
                return
            if en in ("U", "E"):
                self._write(new, nets["out"], tuple(en for _ in range(w)))
                return
        idx, bad = self._sel_value(nets["sel"])
        if bad:
            self._write(new, nets["out"], tuple(bad for _ in range(w)))
            return
        net = nets.get(f"in{idx}")
        if net is None:
            self._write(new, nets["out"], tuple("U" for _ in range(w)))
            return
        self._write(new, nets["out"], self._fit(self._get(net), w))

    def _eval_decoder(self, new, lf):
        nets = lf["nets"]
        en = self._bit(self._get(nets["en"])) if "en" in nets else 1
        idx, bad = self._sel_value(nets["sel"])
        for name, net in nets.items():
            if not name.startswith("out"):
                continue
            if en == 0:
                self._write(new, net, (0,))
            elif en in ("U", "E"):
                self._write(new, net, (en,))
            elif bad:
                self._write(new, net, (bad,))
            else:
                self._write(new, net, (1 if int(name[3:]) == idx else 0,))

    def _eval_comparator(self, new, lf):
        w = lf["w"].get("a", 1)
        mode = str(lf["attrs"].get("mode", "twosComplement"))
        a, ea = self._to_int(self._get(lf["nets"]["a"]), w, mode)
        b, eb = self._to_int(self._get(lf["nets"]["b"]), w, mode)
        bad = ea or eb
        if bad:
            for name in ("gt", "eq", "lt"):
                self._write(new, lf["nets"][name], (bad,))
            return
        self._write(new, lf["nets"]["gt"], (1 if a > b else 0,))
        self._write(new, lf["nets"]["eq"], (1 if a == b else 0,))
        self._write(new, lf["nets"]["lt"], (1 if a < b else 0,))

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
            elif lf["kind"] == "Register":
                out[i] = self._bit(self._get(lf["nets"].get("clk")))
        return out

    def _is_edge(self, i, old, new):
        if self.trigger_of(i) == "falling":
            return old == 1 and new == 0
        return old == 0 and new == 1

    def trigger_of(self, i):
        return self.ff_trigger.get(i, self.reg_trigger.get(i, "rising"))

    def _pulse(self, inputs):
        """一个完整时钟脉冲；逐触发器/寄存器按各自 trigger 检测沿（支持异步级联）。"""
        for i, lf in enumerate(self.leaves):
            if i not in self.ff_trigger and i not in self.reg_trigger:
                continue
            trig = self.trigger_of(i)
            if trig not in ("rising", "falling"):
                raise RuntimeError(
                    f"暂不支持边沿触发方式「{trig}」@ {lf['loc']}；只支持 rising / falling")
        self.clk_drive = 0
        self._settle_stable(inputs)
        last = self._clk_state()

        self.clk_drive = 1
        self._settle_stable(inputs)

        for _ in range(64):
            cur = self._clk_state()
            fired = [i for i in cur if self._is_edge(i, last.get(i), cur[i])]
            if not fired:
                break
            for i in fired:
                lf = self.leaves[i]
                if lf["kind"] == "Register":
                    if self._bit(self._get(lf["nets"].get("en"))) == 1:
                        w = lf["w"].get("Q", 1)
                        self.reg[i] = self._fit(self._get(lf["nets"].get("D")), w)
                elif lf["kind"] == "D Flip-Flop":
                    d = self._bit(self._get(lf["nets"]["D"]))
                    self.ff[i] = 1 if d == 1 else 0
                else:
                    t = self._bit(self._get(lf["nets"]["T"]))
                    if t == 1:
                        self.ff[i] ^= 1
            self._settle_stable(inputs)
            last = cur

        self.clk_drive = 0
        self._settle_stable(inputs)

    def _get(self, net):
        return self.val.get(net)

    @staticmethod
    def _bit(v):
        return "U" if v is None else v[0]

    @staticmethod
    def _gate(g, vals):
        if not vals:
            return "U"
        if any(v == "E" for v in vals):
            return "E"
        if g == "NOT":
            return "U" if vals[0] == "U" else (0 if vals[0] == 1 else 1)
        unknown = any(v == "U" for v in vals)
        if g in ("AND", "NAND"):
            if any(v == 0 for v in vals):
                r = 0
            elif unknown:
                return "U"
            else:
                r = 1
        elif g in ("OR", "NOR"):
            if any(v == 1 for v in vals):
                r = 1
            elif unknown:
                return "U"
            else:
                r = 0
        else:
            if unknown:
                return "U"
            r = sum(1 for v in vals if v == 1) % 2
        if g in ("NAND", "NOR", "XNOR"):
            r = 1 - r
        return r

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
