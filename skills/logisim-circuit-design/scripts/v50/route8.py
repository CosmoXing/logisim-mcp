"""严格的确定性布线：在 lib8._check 之上再加「不得压到任何元件引脚」，
并提供带自动选择通道的 route()（失败会自动换通道，全部失败才报错）。
"""
import os

import lib8
from lib8 import Board

DEBUG = bool(os.environ.get("RDEBUG"))

GRID = 10
_old_check = lib8._check


def _strict_check(self, segs, name):
    _old_check(self, segs, name)
    blk = self._blocked()
    for (x1, y1, x2, y2) in segs:
        if y1 == y2:
            lo, hi = min(x1, x2), max(x1, x2)
            for x in range(lo, hi + 1, GRID):
                if (x // GRID, y1 // GRID) in blk:
                    raise RuntimeError(f"[{self.name}] {name} 穿过元件体 ({x},{y1})")
        else:
            lo, hi = min(y1, y2), max(y1, y2)
            for y in range(lo, hi + 1, GRID):
                if (x1 // GRID, y // GRID) in blk:
                    raise RuntimeError(f"[{self.name}] {name} 穿过元件体 ({x1},{y})")
    ends = set()
    for s in segs:
        ends.add((s[0], s[1]))
        ends.add((s[2], s[3]))
    ends2 = set()
    for s in segs:
        ends2.add((s[0], s[1]))
        ends2.add((s[2], s[3]))
    for t in self._all_segs:
        if t[4] == name or t[4] == "_poly":
            continue
        for q in ((t[0], t[1]), (t[2], t[3])):
            if q in ends2:
                raise RuntimeError(f"[{self.name}] {name} 与 {t[4]} 在 {q} 处端点重合（短路）")
    # 旧线的端点若落在新线段上，同样短接（反向也要查）
    for s in segs:
        x1, y1, x2, y2 = s
        for t in self._all_segs:
            if t[4] == name or t[4] == "_poly":
                continue
            for (px, py) in ((t[0], t[1]), (t[2], t[3])):
                if (px, py) in ((x1, y1), (x2, y2)):
                    continue
                if y1 == y2 == py and min(x1, x2) < px < max(x1, x2):
                    raise RuntimeError(f"[{self.name}] {t[4]} 端点 ({px},{py}) 落在 {name} 上（短路）")
                if x1 == x2 == px and min(y1, y2) < py < max(y1, y2):
                    raise RuntimeError(f"[{self.name}] {t[4]} 端点 ({px},{py}) 落在 {name} 上（短路）")
    for s in segs:
        x1, y1, x2, y2 = s
        for (gx, gy) in self.all_ports:
            p = (gx * GRID, gy * GRID)
            if p in ends:
                continue
            if y1 == y2 == p[1] and min(x1, x2) <= p[0] <= max(x1, x2):
                raise RuntimeError(f"[{self.name}] {name} 压到引脚 {p}")
            if x1 == x2 == p[0] and min(y1, y2) <= p[1] <= max(y1, y2):
                raise RuntimeError(f"[{self.name}] {name} 压到引脚 {p}")


lib8._check = _strict_check

DELTA = {"w": (-20, 0), "e": (20, 0), "n": (0, -20), "s": (0, 20)}


def _stub(p, side):
    dx, dy = DELTA[side]
    return (p[0] + dx, p[1] + dy)


def _stub2(p, side, lead):
    dx, dy = DELTA[side]
    return (p[0] + dx * lead // 20, p[1] + dy * lead // 20)


def _combo(p1, p2, s1, s2, t, l1=20, l2=20):
    """按两端出线方向拼出一条折线；t 是中间通道坐标（竖直通道或水平通道）。"""
    a, b = _stub2(p1, s1, l1), _stub2(p2, s2, l2)
    hor1 = s1 in ("w", "e")
    hor2 = s2 in ("w", "e")
    if hor1 and hor2:
        pts = [p1, a, (t, a[1]), (t, b[1]), b, p2]
    elif (not hor1) and (not hor2):
        pts = [p1, a, (a[0], t), (b[0], t), b, p2]
    elif hor1:
        pts = [p1, a, (b[0], a[1]), b, p2]
    else:
        pts = [p1, a, (a[0], b[1]), b, p2]
    out = [pts[0]]
    for q in pts[1:]:
        if q != out[-1]:
            out.append(q)
    return out


def route(self, name, p1, p2, s1, s2, lo, hi, prefer=None, leads=(20, 40, 60, 80)):
    """从 lo..hi 里挑通道、并尝试几种出线长度，返回 (通道, 出线长度)。"""
    cands = list(range(int(lo), int(hi) + 1, GRID))
    if not cands:
        raise RuntimeError("空通道范围")
    ref = prefer if prefer is not None else (p2[0] if s1 in "we" and s2 in "we" else p2[1])
    cands.sort(key=lambda t: abs(t - ref))
    def _ok(t):
        if s1 == "e" and t < p1[0] + 30:
            return False
        if s1 == "w" and t > p1[0] - 30:
            return False
        if s2 == "w" and t > p2[0] - 30:
            return False
        if s2 == "e" and t < p2[0] + 30:
            return False
        return True
    cands = [t for t in cands if t is None or _ok(t)]
    if not cands:
        raise RuntimeError(f"[{self.name}] route 无合法通道 {name} {p1}->{p2}（port 反侧）")
    hor1, hor2 = s1 in "we", s2 in "we"
    if hor1 != hor2:
        cands = [None]
    last = None
    first = None
    for l1 in leads:
        for l2 in leads:
            for t in cands:
                try:
                    self.w(name, _combo(p1, p2, s1, s2, t, l1, l2))
                    return (t, l1, l2)
                except RuntimeError as e:
                    last = e
                    if first is None:
                        first = e
                    if DEBUG:
                        print(f"    try {name} t={t} l={l1}/{l2}: {str(e)[:90]}")
    raise RuntimeError(f"[{self.name}] route 失败 {name} {p1}->{p2}\n  首次: {first}\n  末次: {last}")


Board.route = route


def side_of(ports, key, loc, geom_body):
    """由端口相对坐标推断它落在盒子的哪条边。"""
    dx, dy = ports[key]
    bx0, by0, bx1, by1 = geom_body
    if dx <= bx0 + 1:
        return "w"
    if dx >= bx1 - 1:
        return "e"
    if dy <= by0 + 1:
        return "n"
    return "s"


# ---------------------------------------------------------------- 连通性验证
def _terms(self, name, p1, p2):
    self._net_terms.setdefault(name, set()).update([p1, p2])


_old_z, _old_w = lib8._z, lib8._w


def _z2(self, name, p1, p2, track):
    _old_z(self, name, p1, p2, track)
    _terms(self, name, p1, p2)


def _w2(self, name, *args):
    _old_w(self, name, *args)
    pts = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
    _terms(self, name, pts[0], pts[-1])


lib8._z, lib8._w = _z2, _w2
Board.z, Board.w = _z2, _w2


def verify_nets(self, verbose=False):
    """检查每个网络的所有端点是否真的连成一片（抓主干太短、分支悬空）。"""
    bad = []
    for name, segs in self.nets.items():
        parent = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for (x1, y1, x2, y2) in segs:
            if y1 == y2:
                step = GRID if x2 >= x1 else -GRID
                for x in range(x1, x2 + (step // GRID), step):
                    union((x, y1), (x + step, y1))
            else:
                step = GRID if y2 >= y1 else -GRID
                for y in range(y1, y2 + (step // GRID), step):
                    union((x1, y), (x1, y + step))
        roots = {}
        for t in self._net_terms.get(name, ()):
            if t not in parent:
                bad.append((name, t, "端点不在任何导线上"))
                continue
            roots.setdefault(find(t), []).append(t)
        if len(roots) > 1:
            groups = list(roots.values())
            bad.append((name, groups[0][0], f"网络分裂成 {len(groups)} 段: " +
                        "; ".join(str(g[:2]) for g in groups[:3])))
    if bad:
        msg = "\n".join(f"  [{self.name}] {n} @ {p}: {why}" for n, p, why in bad[:12])
        raise RuntimeError(f"[{self.name}] 连通性检查失败：\n{msg}")
    if verbose:
        print(f"[{self.name}] 网络 {len(self.nets)} 条，全部连通")
    return True


Board._net_terms = None
_old_init = Board.__init__


def _init2(self, name):
    _old_init(self, name)
    self._net_terms = {}


Board.__init__ = _init2
Board.verify_nets = verify_nets


_old_project = lib8.project


def project(circuits):
    for c in circuits:
        c.verify_nets()
    return _old_project(circuits)


lib8.project = project


def _const(self, loc, value, width=1):
    xml = (f'    <comp lib="0" loc="({loc[0]},{loc[1]})" name="Constant">'
           f'<a name="facing" val="east"/><a name="value" val="{value}"/>'
           f'<a name="width" val="{width}"/></comp>\n')
    self.comps.append(xml)
    self.all_ports.add((loc[0] // GRID, loc[1] // GRID))
    if width > 1:
        self.bodies.append((loc[0] - 30, loc[1] - 10, loc[0], loc[1] + 10))
    else:
        self.bodies.append((loc[0] - 30, loc[1] - 5, loc[0], loc[1] + 5))
    self._blocked_cache = None
    return loc


Board.const = _const


def verify_short(self):
    """按"端点落在另一段上才算连"重建电气网络，报告不同命名网被短接的情况。"""
    segs = []
    for name, ss in self.nets.items():
        for s in ss:
            segs.append((s, name))
    n = len(segs)
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def uni(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb

    def on_seg(p, s):
        x, y = p
        x1, y1, x2, y2 = s
        if y1 == y2 == y and min(x1, x2) <= x <= max(x1, x2):
            return True
        return x1 == x2 == x and min(y1, y2) <= y <= max(y1, y2)

    for i in range(n):
        si, ni = segs[i]
        for j in range(i + 1, n):
            sj, nj = segs[j]
            if ni == nj:
                uni(i, j)
                continue
            if (on_seg((sj[0], sj[1]), si) or on_seg((sj[2], sj[3]), si)
                    or on_seg((si[0], si[1]), sj) or on_seg((si[2], si[3]), sj)):
                uni(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), set()).add(segs[i][1])
    bad = [(r, sorted(v)) for r, v in groups.items() if len(v) > 1]
    if bad:
        msg = "\n".join("  " + " <-> ".join(v) for _, v in bad[:10])
        raise RuntimeError(f"[{self.name}] 不同网络被短接：\n{msg}")
    return True


Board.verify_short = verify_short


# ---------------------------------------------------------------- 子电路展平
import re as _re


def pin_nets(self):
    """每个引脚当前挂着的网络名（用来在粘贴时改名合并）。"""
    out = {}
    for (nm, x, y, face) in lib8.PINS[self.name]:
        hits = []
        for net, segs in self.nets.items():
            for (x1, y1, x2, y2) in segs:
                if (x1, y1) == (x, y) or (x2, y2) == (x, y):
                    hits.append(net)
                    break
        out[nm] = hits
    return out


def bbox(self):
    xs, ys = [], []
    for (x1, y1, x2, y2) in [s for segs in self.nets.values() for s in segs]:
        xs += [x1, x2]
        ys += [y1, y2]
    for (x0, y0, x1, y1) in self.bodies:
        xs += [x0, x1]
        ys += [y0, y1]
    for (nm, x, y, f) in lib8.PINS.get(self.name, []):
        xs.append(x)
        ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def paste(self, other, dx, dy, prefix, link=None):
    """把 other 展开粘到本板上：丢引脚、整体平移，指定引脚的网络改名为上层网络。"""
    dx, dy = int(dx), int(dy)
    if dx % GRID or dy % GRID:
        raise ValueError("粘贴偏移必须对齐 10px 网格")
    fixed = other.canonicalize()
    if fixed:
        print(f"  [paste] {other.name}: 归并了 {fixed} 组同名不同段的网络")
    link = link or {}
    rename = {}
    for pin, nets in pin_nets(other).items():
        if pin in link:
            for n in nets:
                rename[n] = link[pin]

    for xml in other.comps:
        if 'name="Pin"' in xml:
            continue
        m = _re.search(r'loc="\((-?\d+),(-?\d+)\)"', xml)
        x, y = int(m.group(1)), int(m.group(2))
        self.comps.append(xml.replace(m.group(0), f'loc="({x + dx},{y + dy})"', 1))

    for name, segs in other.nets.items():
        newname = rename.get(name, f"{prefix}:{name}")
        for (x1, y1, x2, y2) in segs:
            s = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
            self.nets.setdefault(newname, []).append(s)
            self._all_segs.append((s[0], s[1], s[2], s[3], newname))

    for (x0, y0, x1, y1) in other.bodies:
        self.bodies.append((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
    for (gx, gy) in other.all_ports:
        self.all_ports.add((gx + dx // GRID, gy + dy // GRID))
    self._blocked_cache = None

    return {nm: (x + dx, y + dy) for (nm, x, y, f) in lib8.PINS[other.name]}


Board.pin_nets = pin_nets
Board.bbox = bbox
Board.paste = paste


def canonicalize(self):
    """把电气上相连（同名或端点落在彼此上）的导线段合并成同一个网络名。

    构建器里为了好读，同一条进位链可能用了 c1 / ca1 两个名字；展平后必须归一，
    否则 _check 会把新走线当成短路。
    """
    items = [(name, s) for name, segs in self.nets.items() for s in segs]
    n = len(items)
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def uni(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb

    def on_seg(p, s):
        x, y = p
        x1, y1, x2, y2 = s
        if y1 == y2 == y and min(x1, x2) <= x <= max(x1, x2):
            return True
        return x1 == x2 == x and min(y1, y2) <= y <= max(y1, y2)

    for i in range(n):
        ni, si = items[i]
        for j in range(i + 1, n):
            nj, sj = items[j]
            if ni == nj:
                uni(i, j)
                continue
            if (on_seg((sj[0], sj[1]), si) or on_seg((sj[2], sj[3]), si)
                    or on_seg((si[0], si[1]), sj) or on_seg((si[2], si[3]), sj)):
                uni(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(items[i][0])
    newnets = {}
    for i in range(n):
        root = find(i)
        # 取组里最短的名字做代表，前缀保持稳定
        name = min(groups[root], key=lambda x: (len(x), x))
        s = items[i][1]
        newnets.setdefault(name, []).append(s)
    self.nets = newnets
    self._all_segs = [(s[0], s[1], s[2], s[3], name)
                      for name, segs in newnets.items() for s in segs]
    return sum(1 for g in groups.values() if len(set(g)) > 1)


Board.canonicalize = canonicalize
