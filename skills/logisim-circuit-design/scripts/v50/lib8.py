"""Logisim-evolution 5.0 电路生成库 v6（8 位总线版）。

几何依据（沿用 v5 已验证常量）：
  AbstractGate 输入口 x = -(size+bonus)，size=50；XOR bonus=10；NAND/NOR/XNOR +10
  D Flip-Flop classic: D(-40,+20) CLK(-40,0) Q(0,0) ~Q(0,+20) R(-10,+30) S(-30,+30)
  Splitter: 分线口 (20, -10*(n//2) + 10*i)，与 fanout=4 的实测 (-20,-10,0,10) 一致
  子电路: 按 facing 分边、10px 间距，锚点落在东边第一个口
"""

import heapq
import math

GRID = 10
LIB_WIRING, LIB_GATES, LIB_MEM, LIB_IO, LIB_BASE = "0", "1", "2", "3", "4"


def _r10(v):
    return int(math.floor(v / 10.0 + 0.5)) * 10


def gate_geom(kind, inputs):
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
        top = -10 * (inputs - 1)
        pts = {"out": (0, 0)}
        for i, nm in enumerate("abcdefgh"[:inputs]):
            pts[nm] = (-w, top + 20 * i)
    return dict(body=(-w, -h // 2, 0, h // 2), ports=pts)


def dff_geom():
    return dict(body=(-40, -10, 0, 30),
                ports={"D": (-40, 20), "CLK": (-40, 0), "Q": (0, 0), "NQ": (0, 20),
                       "R": (-10, 30), "S": (-30, 30)})


def splitter_geom(fanout):
    top = -10 * (fanout // 2)
    ports = {"in": (0, 0)}
    for i in range(fanout):
        ports[f"b{i}"] = (20, top + 10 * i)
    body = (0, top, 20, top + 10 * (fanout - 1))
    return dict(body=body, ports=ports)


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


PINS = {}   # 子电路名 -> [(label, x, y, facing)]


class Board:
    def __init__(self, name):
        self.name = name
        self.comps = []
        self.bodies = []
        self.nets = {}
        self.used = {}
        self.term = {}
        self.all_ports = set()
        self._all_segs = []
        self._blocked_cache = None

    def _add(self, xml, loc, geom):
        x, y = loc
        if x % 10 or y % 10:
            raise ValueError(f"[{self.name}] 元件坐标未对齐 10px 网格: {loc}")
        b = geom["body"]
        self.bodies.append((x + b[0], y + b[1], x + b[2], y + b[3]))
        pts = {k: (x + dx, y + dy) for k, (dx, dy) in geom["ports"].items()}
        for p in pts.values():
            self.all_ports.add((p[0] // GRID, p[1] // GRID))
        self.comps.append(xml)
        self._blocked_cache = None
        return pts

    def sub(self, loc, name, pins=None):
        pins = pins or PINS[name]
        body, ports = sub_geom(pins)
        x, y = loc
        self.comps.append(f'    <comp loc="({x},{y})" name="{name}"></comp>\n')
        self.bodies.append((x + body[0], y + body[1], x + body[2], y + body[3]))
        pts = {k: (x + dx, y + dy) for k, (dx, dy) in ports.items()}
        for p in pts.values():
            self.all_ports.add((p[0] // GRID, p[1] // GRID))
        self._blocked_cache = None
        return pts

    def pin(self, loc, label, kind="input", width=1):
        x, y = loc
        face = "east" if kind == "input" else "west"
        w = f'<a name="width" val="{width}"/>' if width != 1 else ""
        self.comps.append(
            f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Pin">'
            f'<a name="type" val="{kind}"/><a name="facing" val="{face}"/>{w}'
            f'<a name="label" val="{label}"/></comp>\n')
        self.all_ports.add((x // GRID, y // GRID))
        self._blocked_cache = None
        return (x, y)

    def gate(self, loc, kind, inputs=None):
        if inputs is None:
            inputs = 1 if kind == "NOT" else 2
        geom = gate_geom(kind, inputs)
        xml = (f'    <comp lib="{LIB_GATES}" loc="({loc[0]},{loc[1]})" name="{kind} Gate">'
               f'<a name="inputs" val="{inputs}"/></comp>\n')
        return self._add(xml, loc, geom)

    def dff(self, loc, label):
        xml = (f'    <comp lib="{LIB_MEM}" loc="({loc[0]},{loc[1]})" name="D Flip-Flop">'
               f'<a name="trigger" val="rising"/><a name="appearance" val="classic"/>'
               f'<a name="label" val="{label}"/></comp>\n')
        return self._add(xml, loc, dff_geom())

    def splitter(self, loc, fanout, facing="east"):
        bits = "".join(f'<a name="bit{i}" val="{i}"/>' for i in range(fanout))
        fac = "" if facing == "east" else f'<a name="facing" val="{facing}"/>'
        xml = (f'    <comp lib="{LIB_WIRING}" loc="({loc[0]},{loc[1]})" name="Splitter">'
               f'<a name="fanout" val="{fanout}"/><a name="incoming" val="{fanout}"/>'
               f'<a name="appear" val="center"/>{fac}{bits}</comp>\n')
        g = splitter_geom(fanout)
        if facing == "west":
            g = dict(body=(-g["body"][2], g["body"][1], -g["body"][0], g["body"][3]),
                     ports={k: (-v[0], v[1]) for k, v in g["ports"].items()})
        return self._add(xml, loc, g)

    def ground(self, loc):
        self.comps.append(f'    <comp lib="{LIB_WIRING}" loc="({loc[0]},{loc[1]})" name="Ground"/>\n')
        self.all_ports.add((loc[0] // GRID, loc[1] // GRID))
        self._blocked_cache = None
        return loc

    def display(self, loc, label):
        x, y = loc
        self.comps.append(
            f'    <comp lib="{LIB_IO}" loc="({x},{y})" name="Hex Digit Display">'
            f'<a name="label" val="{label}"/></comp>\n')
        self.bodies.append((x + 5, y - 28, x + 62, y + 28))
        self.all_ports.add((x // GRID, y // GRID))
        self._blocked_cache = None
        return (x, y)

    # ---------------- 布线
    def _blocked(self):
        if self._blocked_cache is not None:
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
        pts = [p for p in pts if p is not None]
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
                        return False
            return True

        tree = {pts[0]}
        remaining = list(pts[1:])
        segs = []
        while remaining:
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
            # 拐点与端点：别的网不得从这里穿过（否则 Logisim 里就是 T 型接通的短路）
            for i, p in enumerate(path):
                corner = (i == 0 or i == len(path) - 1)
                if not corner:
                    d1 = "h" if path[i - 1][1] == p[1] else "v"
                    d2 = "h" if p[1] == path[i + 1][1] else "v"
                    corner = d1 != d2
                if corner:
                    self.term[(p[0] // GRID, p[1] // GRID)] = name
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
        best = {}
        pq = []
        for s in starts:
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

    def xml(self):
        body = "".join(self.comps)
        for segs in self.nets.values():
            seen = set()
            for (x1, y1, x2, y2) in segs:
                key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if key in seen:
                    continue
                seen.add(key)
                body += f'    <wire from="({key[0]},{key[1]})" to="({key[2]},{key[3]})"/>\n'
        return f'  <circuit name="{self.name}">\n    <a name="circuit" val="{self.name}"/>\n{body}  </circuit>\n'


def _merge_collinear(segs):
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
                    if lo2 <= hi1 and lo1 <= hi2:
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
    head += f'  <lib desc="#Wiring" name="{LIB_WIRING}"/>\n'
    head += f'  <lib desc="#Gates" name="{LIB_GATES}"/>\n'
    head += f'  <lib desc="#Memory" name="{LIB_MEM}"/>\n'
    head += f'  <lib desc="#I/O" name="{LIB_IO}"/>\n'
    head += f'  <lib desc="#Base" name="{LIB_BASE}"/>\n'
    head += f'  <main name="{circuits[0].name}"/>\n'
    head += "  <options/>\n"
    head += '  <mappings>\n    <tool lib="4" name="Poke Tool" map="Button2"/>\n'
    head += '    <tool lib="4" name="Menu Tool" map="Button3"/>\n  </mappings>\n'
    head += '  <toolbar>\n    <tool lib="4" name="Poke Tool"/>\n    <tool lib="4" name="Edit Tool"/>\n'
    head += '    <tool lib="4" name="Wiring Tool"/>\n    <tool lib="4" name="Text Tool"/>\n    <sep/>\n  </toolbar>\n'
    tail = "</project>\n"
    return head + "".join(c.xml() for c in circuits) + tail


def _poly(self, pts):
    """直接铺折线（探针电路用，不走迷宫布线）。"""
    segs = [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]
    self.nets.setdefault("_poly", []).extend(segs)


Board.poly = _poly


# ---------------------------------------------------------------- 确定性布线
def _z_segs(p1, p2, track):
    """Z 形三段：水平-垂直-水平。"""
    (x1, y1), (x2, y2) = p1, p2
    segs = []
    if x1 != track:
        segs.append((x1, y1, track, y1))
    if y1 != y2:
        segs.append((track, y1, track, y2))
    if track != x2:
        segs.append((track, y2, x2, y2))
    return segs


def _check(self, segs, name):
    """布线自检：不得与已有导线共线重叠；端点不得落在别的导线上。"""
    def h(s):
        return s[1] == s[3]
    for s in segs:
        for t in self._all_segs:
            if t[4] == name:
                continue
            if h(s) and h(t) and s[1] == t[1]:
                lo1, hi1 = min(s[0], s[2]), max(s[0], s[2])
                lo2, hi2 = min(t[0], t[2]), max(t[0], t[2])
                if max(lo1, lo2) < min(hi1, hi2):
                    raise RuntimeError(f"[{self.name}] {name}{s} 与 {t[4]}{t[:4]} 水平共线重叠")
            if (not h(s)) and (not h(t)) and s[0] == t[0]:
                lo1, hi1 = min(s[1], s[3]), max(s[1], s[3])
                lo2, hi2 = min(t[1], t[3]), max(t[1], t[3])
                if max(lo1, lo2) < min(hi1, hi2):
                    raise RuntimeError(f"[{self.name}] {name}{s} 与 {t[4]}{t[:4]} 垂直共线重叠")
    for s in segs:
        for (px, py) in [(s[0], s[1]), (s[2], s[3])]:
            for t in self._all_segs:
                if t[4] == name:
                    continue
                if t[1] == t[3] == py and min(t[0], t[2]) < px < max(t[0], t[2]):
                    raise RuntimeError(f"[{self.name}] {name} 端点 ({px},{py}) 落在 {t[4]} 上")
                if t[0] == t[2] == px and min(t[1], t[3]) < py < max(t[1], t[3]):
                    raise RuntimeError(f"[{self.name}] {name} 端点 ({px},{py}) 落在 {t[4]} 上")


def _z(self, name, p1, p2, track):
    segs = _z_segs(p1, p2, track)
    _check(self, segs, name)
    for s in segs:
        self._all_segs.append((s[0], s[1], s[2], s[3], name))
        self.nets.setdefault(name, []).append(s)


Board._all_segs = []
Board.z = _z


def _w(self, name, *args):
    """任意折线布线（每段必须轴对齐），逐段自检。"""
    pts = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
    segs = []
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        if x1 != x2 and y1 != y2:
            raise RuntimeError(f"[{self.name}] {name} 非轴对齐段 {pts[i]}->{pts[i+1]}")
        if x1 == x2 and y1 == y2:
            continue
        segs.append((x1, y1, x2, y2))
    _check(self, segs, name)
    for s in segs:
        self._all_segs.append((s[0], s[1], s[2], s[3], name))
        self.nets.setdefault(name, []).append(s)


Board.w = _w


def _clock(self, loc):
    """Clock 组件：输出口就在 loc（实测 2.2.circ 中 350,320 处起线）。"""
    x, y = loc
    self.comps.append(
        f'    <comp lib="{LIB_WIRING}" loc="({x},{y})" name="Clock">'
        f'<a name="appearance" val="classic"/></comp>\n')
    self.bodies.append((x - 40, y - 20, x, y + 5))
    self.all_ports.add((x // GRID, y // GRID))
    self._blocked_cache = None
    return (x, y)


Board.clock = _clock
