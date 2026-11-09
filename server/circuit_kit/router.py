"""Logisim-evolution 5.0 电路库：精确几何 + 迷宫布线 + XML 输出。

几何依据（v5.0.0 源码，非经验值）：
  AbstractGate.getInputOffset : 输入口 x = -(size + bonus)，默认 size=50；XOR bonus=10
  AbstractGate.computePorts   : 输出口 (0,0)
  AbstractFlipFlop.updatePorts: classic 外观 D/T(-40,+20) CLK(-40,0) Q(0,0) ~Q(0,+20) R(-10,+30) S(-30,+30)
  DefaultClassicAppearance    : 子电路端口按 facing 分边、10px 间距，锚点落在东边口
"""

import heapq

GRID = 10

WIRE_LIB = "0"
GATE_LIB = "1"
MEM_LIB = "4"
IO_LIB = "5"
BASE_LIB = "8"

# ---------------------------------------------------------------- 组件几何
# body: (x0, y0, x1, y1) 相对 loc；ports: name -> (dx, dy)
def _gate_geom(kind, inputs):
    if kind == "NOT":
        w = 30
    else:
        bonus = 10 if kind in ("XOR", "XNOR") else 0
        neg = 10 if kind in ("NAND", "NOR", "XNOR") else 0
        w = 50 + bonus + neg
    h = max(10 * inputs, 50)
    if inputs == 1:
        pts = {"out": (0, 0), "a": (-w, 0)}
    elif inputs == 2:
        pts = {"out": (0, 0), "a": (-w, -20), "b": (-w, 20)}
    else:
        step = 20
        top = -10 * (inputs - 1)
        pts = {"out": (0, 0)}
        for i, nm in enumerate("abcdefgh"[:inputs]):
            pts[nm] = (-w, top + step * i)
    return dict(body=(-w, -h // 2, 0, h // 2), ports=pts)


def _dff_geom():
    return dict(body=(-40, -10, 0, 30),
                ports={"D": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
                       "R": (-10, 30), "S": (-30, 30)})


def _splitter4_geom():
    return dict(body=(0, -20, 20, 20),
                ports={"in": (0, 0), "b0": (20, -20), "b1": (20, -10),
                       "b2": (20, 0), "b3": (20, 10)})


def _r10(v):
    import math
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


def sub_geom(pins):
    """pins: [(label, x, y, facing)] -> (body, {label:(dx,dy)})"""
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
    body = (-ax, -ay, -ax + width, -ay + height)
    return body, ports


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
        xml = f'    <comp loc="({x},{y})" name="{name}"></comp>\n'
        self.bodies.append((x + body[0], y + body[1], x + body[2], y + body[3]))
        pts = {k: (x + dx, y + dy) for k, (dx, dy) in ports.items()}
        for p in pts.values():
            self.all_ports.add((p[0] // GRID, p[1] // GRID))
        self.comps.append(xml)
        self._blocked_cache = None
        return pts

    def pin(self, loc, label, kind="input", width=1):
        x, y = loc
        face = "east" if kind == "input" else "west"
        w = f'<a name="width" val="{width}"/>' if width != 1 else ""
        xml = (f'    <comp lib="{WIRE_LIB}" loc="({x},{y})" name="Pin">'
               f'<a name="type" val="{kind}"/><a name="facing" val="{face}"/>{w}'
               f'<a name="label" val="{label}"/></comp>\n')
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self._blocked_cache = None
        return (x, y)

    def gate(self, loc, kind, inputs=None):
        if inputs is None:
            inputs = 1 if kind == "NOT" else 2
        geom = _gate_geom(kind, inputs)
        xml = (f'    <comp lib="{GATE_LIB}" loc="({loc[0]},{loc[1]})" name="{kind} Gate">'
               f'<a name="inputs" val="{inputs}"/></comp>\n')
        return self._add(xml, loc, geom)

    def dff(self, loc, label):
        geom = _dff_geom()
        xml = (f'    <comp lib="{MEM_LIB}" loc="({loc[0]},{loc[1]})" name="D Flip-Flop">'
               f'<a name="trigger" val="rising"/><a name="appearance" val="classic"/>'
               f'<a name="label" val="{label}"/></comp>\n')
        return self._add(xml, loc, geom)

    def tff(self, loc, label):
        geom = _dff_geom()
        xml = (f'    <comp lib="{MEM_LIB}" loc="({loc[0]},{loc[1]})" name="T Flip-Flop">'
               f'<a name="trigger" val="rising"/><a name="appearance" val="classic"/>'
               f'<a name="label" val="{label}"/></comp>\n')
        return self._add(xml, loc, geom)

    def splitter4(self, loc):
        geom = _splitter4_geom()
        xml = (f'    <comp lib="{WIRE_LIB}" loc="({loc[0]},{loc[1]})" name="Splitter">'
               f'<a name="fanout" val="4"/><a name="incoming" val="4"/>'
               f'<a name="appear" val="center"/>'
               f'<a name="bit0" val="0"/><a name="bit1" val="1"/>'
               f'<a name="bit2" val="2"/><a name="bit3" val="3"/></comp>\n')
        return self._add(xml, loc, geom)

    def clock(self, loc):
        x, y = loc
        xml = f'    <comp lib="{WIRE_LIB}" loc="({x},{y})" name="Clock"/>\n'
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x + 5, y - 15, x + 35, y + 15))
        return (x, y)

    def led(self, loc):
        x, y = loc
        xml = f'    <comp lib="{IO_LIB}" loc="({x},{y})" name="LED"/>\n'
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x + 5, y - 12, x + 32, y + 12))
        return (x, y)

    def ground(self, loc):
        x, y = loc
        xml = f'    <comp lib="{WIRE_LIB}" loc="({x},{y})" name="Ground"/>\n'
        self.comps.append(xml)
        self.all_ports.add((x // GRID, y // GRID))
        self.bodies.append((x - 8, y - 8, x + 8, y + 8))
        return (x, y)

    def display(self, loc, label):
        x, y = loc
        xml = (f'    <comp lib="{IO_LIB}" loc="({x},{y})" name="Hex Digit Display">'
               f'<a name="label" val="{label}"/></comp>\n')
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
        return f'  <circuit name="{self.name}">\n    <a name="circuit" val="{self.name}"/>\n{body}  </circuit>\n'


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
    head = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    head += '<project source="5.0.0" version="1.0">\n'
    head += f'  <lib desc="#Wiring" name="{WIRE_LIB}"/>\n'
    head += f'  <lib desc="#Gates" name="{GATE_LIB}"/>\n'
    head += f'  <lib desc="#Memory" name="{MEM_LIB}"/>\n'
    head += f'  <lib desc="#I/O" name="{IO_LIB}"/>\n'
    head += f'  <lib desc="#Base" name="{BASE_LIB}"/>\n'
    head += f'  <main name="{circuits[0][0]}"/>\n'
    head += "  <options/>\n"
    head += '  <mappings>\n    <tool lib="8" name="Poke Tool" map="Button2"/>\n'
    head += '    <tool lib="8" name="Menu Tool" map="Button3"/>\n  </mappings>\n'
    head += '  <toolbar>\n    <tool lib="8" name="Poke Tool"/>\n    <tool lib="8" name="Edit Tool"/>\n'
    head += '    <tool lib="8" name="Wiring Tool"/>\n    <tool lib="8" name="Text Tool"/>\n    <sep/>\n  </toolbar>\n'
    tail = "</project>\n"
    return head + "".join(c.xml() for _, c in circuits) + tail
