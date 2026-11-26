"""Logisim-evolution 电路库：精确几何 + 迷宫布线 + XML 输出。

几何依据（源码，非经验值）：
  AbstractGate.getInputOffset : 输入口 x = -(size + bonus)，默认 size=50；XOR bonus=10
  AbstractGate.computePorts   : 输出口 (0,0)
  AbstractFlipFlop.updatePorts: classic 外观 D/T(-40,+20) CLK(-40,0) Q(0,0) ~Q(0,+20) R(-10,+30) S(-30,+30)
  子电路：
    5.0  DefaultClassicAppearance : 按 facing 分边、10px 间距，锚点落在东边口
    4.1  DefaultEvolutionAppearance(fixedSize) : 固定 220 宽、20px 间距，锚点在东边第一个口
  具体走哪个档位由 vprofile 决定（LOGISIM_PROFILE / jar 文件名）。
"""

import heapq
from xml.sax.saxutils import escape as _xml_escape

from . import vprofile

GRID = 10


def _esc(value):
    """XML 属性转义：标签里出现 & < > " ' 时不能直接拼进文档。"""
    return _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def _lib(kind):
    return vprofile.lib(kind)

# ---------------------------------------------------------------- 组件几何
# body: (x0, y0, x1, y1) 相对 loc；ports: name -> (dx, dy)
def _gate_geom(kind, inputs):
    if kind == "NOT":
        w = 30
    else:
        bonus = 10 if kind in ("XOR", "XNOR") else 0
        neg = 10 if kind in ("NAND", "NOR", "XNOR") else 0
        w = 50 + bonus + neg
    # 4.1 实测：2 输入 ±20；3 输入 -20/0/+20；n>=4 用 10px 间距、
    # 半高 = 10*(n//2)，偶数输入跳过 0（4 输入 -20/-10/+10/+20）。
    if inputs == 1:
        pts = {"out": (0, 0), "a": (-w, 0)}
        h = 50
    elif inputs == 2:
        pts = {"out": (0, 0), "a": (-w, -20), "b": (-w, 20)}
        h = 50
    elif inputs == 3:
        pts = {"out": (0, 0), "a": (-w, -20), "b": (-w, 0), "c": (-w, 20)}
        h = 50
    else:
        half = 10 * (inputs // 2)
        ys = [y for y in range(-half, half + 1, 10)
              if not (inputs % 2 == 0 and y == 0)]
        pts = {"out": (0, 0)}
        for i, nm in enumerate("abcdefgh"[:inputs]):
            pts[nm] = (-w, ys[i])
        h = 2 * half + 10
    return dict(body=(-w, -h // 2, 0, h // 2), ports=pts)


def _dff_geom():
    return dict(body=(-40, -10, 0, 30),
                ports={"D": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
                       "R": (-10, 30), "S": (-30, 30)})


def _tff_geom():
    return dict(body=(-40, -10, 0, 30),
                ports={"T": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
                       "R": (-10, 30), "S": (-30, 30)})


def _splitter4_geom():
    return dict(body=(0, -20, 20, 20),
                ports={"in": (0, 0), "b0": (20, -20), "b1": (20, -10),
                       "b2": (20, 0), "b3": (20, 10)})


def _splitter4w_geom():
    """4 位分线器，facing=west、appear=center：位口在左，总线口在右。"""
    return dict(body=(-20, -20, 1, 11),
                ports={"in": (0, 0), "b0": (-20, -20), "b1": (-20, -10),
                       "b2": (-20, 0), "b3": (-20, 10)})


def _splitter3_geom():
    """3 位分线/并线器（fanout=3, incoming=3, appear=center）：in 为 3 位总线，b0..b2 为位。"""
    return dict(body=(0, -10, 21, 11),
                ports={"in": (0, 0), "b0": (20, -10), "b1": (20, 0), "b2": (20, 10)})


def _seg7_geom():
    """I/O/7-Segment Display（decimalPoint=false，7 个段脚）。
    A(20,0) B(30,0) C(20,60) D(10,60) E(0,60) F(10,0) G(0,0)；框 (-5,0,35,60)。
    """
    return dict(body=(-5, 0, 35, 60),
                ports={"a": (20, 0), "b": (30, 0), "c": (20, 60),
                       "d": (10, 60), "e": (0, 60), "f": (10, 0), "g": (0, 0)})


def _const_geom():
    return dict(body=(-35, -8, 35, 16), ports={"out": (0, 0)})


def _decoder_geom(select=3):
    n = 1 << select
    pts = {"sel": (0, 0), "en": (-10, 0)}
    for i in range(n):
        pts[f"out{i}"] = (20, -10 * (n - i))
    return dict(body=(-20, -10 * (n + 1), 20, 10), ports=pts)


def sub_geom(pins):
    """pins: [(label, x, y, facing)] -> (body, {label:(dx,dy)})

    子电路符号几何按当前档位（4.1 固定 220 宽 / 5.0 动态宽度），
    由 vprofile.sub_geometry 统一给出。
    """
    return vprofile.sub_geometry(pins)


class Board:
    """一块电路画布：收集元件与网络，最后统一布线输出。"""

    def __init__(self, name):
        self.name = name
        self.comps = []          # xml 片段
        self.bodies = []         # (x0,y0,x1,y1) 绝对坐标
        self.ports = {}          # 全局端口坐标集合 (用于禁止他网占用)
        self.nets = {}           # name -> [(x1,y1,x2,y2)]
        self.used = {}           # (gx,gy) -> set of ('h'/'v', net)
        self.term = {}           # (gx,gy) -> net  终端点，禁止他网经过
        self.all_ports = set()   # 所有元件端口（任何网络都不得穿越）

    # ---------------- 元件
    def _add(self, xml, loc, geom, names=None):
        x, y = loc
        b = geom["body"]
        self.bodies.append((x + b[0], y + b[1], x + b[2], y + b[3]))
        pts = {k: (x + dx, y + dy) for k, (dx, dy) in geom["ports"].items()}
        for p in pts.values():
            self.all_ports.add((p[0] // GRID, p[1] // GRID))
        self.comps.append(xml)
        self._blocked_cache = None
        return pts

    def sub(self, loc, name, pins):
        """子电路实例。pins 为子电路内部引脚列表 [(label,x,y,facing)]。"""
        body, ports = sub_geom(pins)
        x, y = loc
        xml = f'    <comp loc="({x},{y})" name="{_esc(name)}"></comp>\n'
        self.bodies.append((x + body[0], y + body[1], x + body[2], y + body[3]))
        pts = {k: (x + dx, y + dy) for k, (dx, dy) in ports.items()}
        for p in pts.values():
            self.all_ports.add((p[0] // GRID, p[1] // GRID))
        self.comps.append(xml)
        self._blocked_cache = None
        return pts

    def pin(self, loc, label, kind="input", width=1, initial=None):
        x, y = loc
        face = "east" if kind == "input" else "west"
        w = f'<a name="width" val="{width}"/>' if width != 1 else ""
        if initial is None:
            ini = ""
        elif int(width) > 1:
            ini = f'<a name="initial" val="0x{int(initial) & ((1 << int(width)) - 1):x}"/>'
        else:
            ini = ('<a name="initial" val="1"/>'
                   if str(initial).lower() in ("1", "true", "high") else
                   '<a name="initial" val="0"/>')
        xml = (f'    <comp lib="{_lib("wire")}" loc="({x},{y})" name="Pin">'
               f'<a name="type" val="{kind}"/><a name="facing" val="{face}"/>{w}{ini}'
               f'<a name="label" val="{_esc(label)}"/></comp>\n')
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self._blocked_cache = None
        return (x, y)

    def seg7(self, loc, label=""):
        """7 段数码管（共高有效，7 个段脚）。"""
        geom = _seg7_geom()
        lab = f'<a name="label" val="{_esc(label)}"/>' if label else ""
        xml = (f'    <comp lib="{_lib("io")}" loc="({loc[0]},{loc[1]})" name="7-Segment Display">'
               f'<a name="decimalPoint" val="false"/>{lab}</comp>\n')
        return self._add(xml, loc, geom)

    def constant(self, loc, value=1, width=1):
        geom = _const_geom()
        xml = (f'    <comp lib="{_lib("wire")}" loc="({loc[0]},{loc[1]})" name="Constant">'
               f'<a name="width" val="{int(width)}"/>'
               f'<a name="value" val="0x{int(value) & ((1 << int(width)) - 1):x}"/></comp>\n')
        return self._add(xml, loc, geom)

    def decoder3(self, loc, select=3):
        """3-8 译码器（Plexers/Decoder），sel 与 en 在底边，out0 在最上。"""
        geom = _decoder_geom(int(select))
        xml = (f'    <comp lib="{_lib("plexer")}" loc="({loc[0]},{loc[1]})" name="Decoder">'
               f'<a name="select" val="{int(select)}"/></comp>\n')
        return self._add(xml, loc, geom)

    def gate(self, loc, kind, inputs=None):
        if inputs is None:
            inputs = 1 if kind == "NOT" else 2
        geom = _gate_geom(kind, inputs)
        xml = (f'    <comp lib="{_lib("gate")}" loc="({loc[0]},{loc[1]})" name="{kind} Gate">'
               f'<a name="inputs" val="{inputs}"/></comp>\n')
        return self._add(xml, loc, geom)

    def dff(self, loc, label):
        geom = _dff_geom()
        xml = (f'    <comp lib="{_lib("mem")}" loc="({loc[0]},{loc[1]})" name="D Flip-Flop">'
               f'<a name="trigger" val="rising"/><a name="appearance" val="classic"/>'
               f'<a name="label" val="{_esc(label)}"/></comp>\n')
        return self._add(xml, loc, geom)

    def tff(self, loc, label):
        geom = _tff_geom()
        xml = (f'    <comp lib="{_lib("mem")}" loc="({loc[0]},{loc[1]})" name="T Flip-Flop">'
               f'<a name="trigger" val="rising"/><a name="appearance" val="classic"/>'
               f'<a name="label" val="{_esc(label)}"/></comp>\n')
        return self._add(xml, loc, geom)

    def splitter4(self, loc):
        geom = _splitter4_geom()
        xml = (f'    <comp lib="{_lib("wire")}" loc="({loc[0]},{loc[1]})" name="Splitter">'
               f'<a name="fanout" val="4"/><a name="incoming" val="4"/>'
               f'<a name="appear" val="center"/>'
               f'<a name="bit0" val="0"/><a name="bit1" val="1"/>'
               f'<a name="bit2" val="2"/><a name="bit3" val="3"/></comp>\n')
        return self._add(xml, loc, geom)

    def splitter4w(self, loc):
        geom = _splitter4w_geom()
        xml = (f'    <comp lib="{_lib("wire")}" loc="({loc[0]},{loc[1]})" name="Splitter">'
               f'<a name="fanout" val="4"/><a name="incoming" val="4"/>'
               f'<a name="appear" val="center"/><a name="facing" val="west"/>'
               f'<a name="bit0" val="0"/><a name="bit1" val="1"/>'
               f'<a name="bit2" val="2"/><a name="bit3" val="3"/></comp>\n')
        return self._add(xml, loc, geom)

    def splitter3(self, loc):
        geom = _splitter3_geom()
        xml = (f'    <comp lib="{_lib("wire")}" loc="({loc[0]},{loc[1]})" name="Splitter">'
               f'<a name="fanout" val="3"/><a name="incoming" val="3"/>'
               f'<a name="appear" val="center"/>'
               f'<a name="bit0" val="0"/><a name="bit1" val="1"/>'
               f'<a name="bit2" val="2"/></comp>\n')
        return self._add(xml, loc, geom)

    def clock(self, loc):
        x, y = loc
        xml = f'    <comp lib="{_lib("wire")}" loc="({x},{y})" name="Clock"/>\n'
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x + 5, y - 15, x + 35, y + 15))
        return (x, y)

    def led(self, loc):
        x, y = loc
        xml = f'    <comp lib="{_lib("io")}" loc="({x},{y})" name="LED"/>\n'
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x + 5, y - 12, x + 32, y + 12))
        return (x, y)

    def ground(self, loc):
        x, y = loc
        xml = f'    <comp lib="{_lib("wire")}" loc="({x},{y})" name="Ground"/>\n'
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x - 8, y - 8, x + 8, y + 8))
        return (x, y)

    def display(self, loc, label):
        x, y = loc
        xml = (f'    <comp lib="{_lib("io")}" loc="({x},{y})" name="Hex Digit Display">'
               f'<a name="label" val="{_esc(label)}"/></comp>\n')
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x + 5, y - 28, x + 62, y + 28))
        return (x, y)

    # ---------------- 布线
    def _blocked(self):
        if getattr(self, "_blocked_cache", None) is not None:
            return self._blocked_cache
        cells = set()
        for (x0, y0, x1, y1) in self.bodies:
            for gx in range(int(x0) // GRID, int(x1) // GRID + 1):
                for gy in range(int(y0) // GRID, int(y1) // GRID + 1):
                    x, y = gx * GRID, gy * GRID
                    if x0 + 4 < x < x1 - 4 and y0 + 4 < y < y1 - 4:
                        cells.add((gx, gy))
        self._blocked_cache = cells
        return cells

    def connect(self, name, pts):
        """把 pts 连成一个网络（迷宫布线，禁止穿越元件体、禁止与他网共线重叠）。"""
        if len(pts) < 2:
            return
        blocked = self._blocked()

        own = {(p[0] // GRID, p[1] // GRID) for p in pts}

        def free(cell, net, d):
            g = (cell[0] // GRID, cell[1] // GRID)
            if g in self.all_ports and g not in own:
                return False
            if g in blocked:
                return False
            if g in self.term and self.term[g] != net:
                return False
            occ = self.used.get(cell)
            if occ:
                for dd, nn in occ:
                    if nn == net:
                        continue
                    if dd == d:
                        return False      # 共线重叠 = 短路
            return True

        tree = {pts[0]}
        remaining = list(pts[1:])
        segs = []
        while remaining:
            # 选离已连集合最近的目标
            remaining.sort(key=lambda p: min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in tree))
            target = remaining.pop(0)
            path = self._astar(tree, target, name, free)
            if path is None:
                raise RuntimeError(f"[{self.name}] 网络 {name} 无法布通到 {target}")
            for i in range(len(path) - 1):
                a, b = path[i], path[i + 1]
                d = "h" if a[1] == b[1] else "v"
                self.used.setdefault(a, set()).add((d, name))
                self.used.setdefault(b, set()).add((d, name))
                segs.append((a[0], a[1], b[0], b[1]))
            tree.update(path)
            self.term[(target[0] // GRID, target[1] // GRID)] = name

        for p in pts:
            self.term[(p[0] // GRID, p[1] // GRID)] = name
        self.nets.setdefault(name, []).extend(_merge_collinear(segs))

    def _canvas_limits(self):
        xs = [0, 20]
        ys = [0, 20]
        for (x0, y0, x1, y1) in self.bodies:
            xs += [x0 // GRID, x1 // GRID]
            ys += [y0 // GRID, y1 // GRID]
        for gx, gy in self.all_ports:
            xs.append(gx)
            ys.append(gy)
        return min(xs) - 30, max(xs) + 30, min(ys) - 30, max(ys) + 30

    def _astar(self, starts, target, net, free):
        starts = [(p[0] // GRID, p[1] // GRID) for p in starts]
        tgt = (target[0] // GRID, target[1] // GRID)
        # 目标点允许落在元件体边界（端口点），故不检查 blocked，由 free 统一处理
        start_states = [(s, None) for s in starts]
        best = {}
        pq = []
        for s, _ in start_states:
            best[(s, None)] = 0
            heapq.heappush(pq, (abs(s[0] - tgt[0]) + abs(s[1] - tgt[1]), 0, s, None))
        dirs = [((1, 0), "h"), ((-1, 0), "h"), ((0, 1), "v"), ((0, -1), "v")]
        gx0, gx1, gy0, gy1 = self._canvas_limits()
        prev = {}
        found = None
        while pq:
            f, cost, cell, d = heapq.heappop(pq)
            if cell == tgt:
                found = (cell, d)
                break
            if best.get((cell, d), 1 << 30) < cost:
                continue
            for (dx, dy), nd in dirs:
                nxt = (cell[0] + dx, cell[1] + dy)
                if not (gx0 <= nxt[0] <= gx1 and gy0 <= nxt[1] <= gy1):
                    continue
                is_tgt = nxt == tgt
                if not is_tgt and not free((nxt[0] * GRID, nxt[1] * GRID), net, nd):
                    # 起点/终点本身可能被 free 判为占用，放宽：终点直接允许
                    continue
                turn = 0 if (d is None or d == nd) else 3
                nc = cost + 1 + turn
                if nc < best.get((nxt, nd), 1 << 30):
                    best[(nxt, nd)] = nc
                    prev[(nxt, nd)] = (cell, d)
                    heapq.heappush(pq, (nc + abs(nxt[0] - tgt[0]) + abs(nxt[1] - tgt[1]), nc, nxt, nd))
        if found is None:
            return None
        path = []
        cur = found
        while cur is not None:
            path.append((cur[0][0] * GRID, cur[0][1] * GRID))
            cur = prev.get(cur)
        path.reverse()
        return path

    # ---------------- 输出
    def xml(self):
        body = "".join(self.comps)
        seen = set()
        for segs in self.nets.values():
            for (x1, y1, x2, y2) in segs:
                key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if key in seen:
                    continue
                seen.add(key)
                body += f'    <wire from="({key[0]},{key[1]})" to="({key[2]},{key[3]})"/>\n'
        fixed = ('    <a name="appearance" val="logisim_evolution"/>\n'
                 '    <a name="circuitnamedboxfixedsize" val="true"/>\n'
                 if vprofile.get("named_box_fixed") else "")
        return (f'  <circuit name="{_esc(self.name)}">\n'
                f'    <a name="circuit" val="{_esc(self.name)}"/>\n'
                f'{fixed}{body}  </circuit>\n')


def _merge_collinear(segs):
    """把同一线上的相邻线段合并，减少线数（不改变连通性）。"""
    segs = list(segs)
    changed = True
    while changed:
        changed = False
        out = []
        used = [False] * len(segs)
        for i in range(len(segs)):
            if used[i]:
                continue
            x1, y1, x2, y2 = segs[i]
            used[i] = True
            for j in range(i + 1, len(segs)):
                if used[j]:
                    continue
                a1, b1, a2, b2 = segs[j]
                if y1 == y2 == b1 == b2:
                    lo1, hi1 = min(x1, x2), max(x1, x2)
                    lo2, hi2 = min(a1, a2), max(a1, a2)
                    if lo2 <= hi1 and lo1 <= hi2:      # 同一直线且有交叠
                        x1, x2 = min(lo1, lo2), max(hi1, hi2)
                        used[j] = True
                        changed = True
                elif x1 == x2 == a1 == a2:
                    lo1, hi1 = min(y1, y2), max(y1, y2)
                    lo2, hi2 = min(b1, b2), max(b1, b2)
                    if lo2 <= hi1 and lo1 <= hi2:
                        y1, y2 = min(lo1, lo2), max(hi1, hi2)
                        used[j] = True
                        changed = True
            out.append((x1, y1, x2, y2))
        segs = out
    return segs


def project(circuits):
    base = _lib("base")
    head = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    head += f'<project source="{vprofile.version_string()}" version="1.0">\n'
    for desc, name in vprofile.get("lib_decls") or []:
        head += f'  <lib desc="{desc}" name="{name}"/>\n'
    head += f'  <main name="{_esc(circuits[0][0])}"/>\n'
    head += "  <options/>\n"
    head += f'  <mappings>\n    <tool lib="{base}" name="Poke Tool" map="Button2"/>\n'
    head += f'    <tool lib="{base}" name="Menu Tool" map="Button3"/>\n  </mappings>\n'
    head += f'  <toolbar>\n    <tool lib="{base}" name="Poke Tool"/>\n    <tool lib="{base}" name="Edit Tool"/>\n'
    head += f'    <tool lib="{base}" name="Wiring Tool"/>\n    <tool lib="{base}" name="Text Tool"/>\n    <sep/>\n  </toolbar>\n'
    tail = "</project>\n"
    return head + "".join(c.xml() for _, c in circuits) + tail
