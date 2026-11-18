#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端口级网络映射 + 共线短接定位（Logisim 2.7.1 / ITA 2.16）

netcheck.py 只回答「哪张网位宽冲突」；本工具回答「端口 A 到底连到哪个端口 B」，
用于核对数码管段位、分线器分支、子电路引脚这类「线都在、就是接错位」的问题，
同时把 Logisim 唯一一种「看不见的错」——同一水平/垂直线上区间重叠（短路）——单列出来。

连通规则（2.16 实测，与 Logisim 一致）：
  1) 两条导线共用端点            → 连通
  2) 一条的端点落在另一条中段    → 连通（T 接）
  3) 双方都只是内点（十字交叉）  → 不连通
  4) 同一直线上区间有重叠        → 短接（本脚本单独报警）

用法：
    python netmap.py file.circ "电路名"
    python netmap.py file.circ "电路名" --comp 七段译码器0~F
    python netmap.py file.circ "电路名" --overlap      # 只查共线重叠（短接）
    python netmap.py file.circ "电路名" --grid         # 只查斜线/非 10 倍数（会导致加载 OOM）

相关：`sevenseg.py check` 用它核对数码管 a~g 段位。
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ita_probe  # noqa: E402


def read_wires(circ: str, circuit: str) -> list[tuple[int, int, int, int]]:
    """读电路 XML 里的 <wire>，统一成 (x1,y1,x2,y2) 且 x1<=x2 / y1<=y2。"""
    s = open(circ, encoding="utf-8").read()
    i = s.index(f'<circuit name="{circuit}">')
    j = s.index("</circuit>", i)
    out = []
    for m in re.finditer(r'<wire from="\((-?\d+),(-?\d+)\)" to="\((-?\d+),(-?\d+)\)"',
                         s[i:j]):
        x1, y1, x2, y2 = map(int, m.groups())
        out.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    return out


class Net:
    """导线连通性（并查集）+ 端口查询。"""

    def __init__(self, segs):
        self.segs = list(segs)
        self.par = list(range(len(self.segs)))
        for a in range(len(self.segs)):
            for b in range(a + 1, len(self.segs)):
                if self._touching(self.segs[a], self.segs[b]):
                    self.union(a, b)

    def find(self, a: int) -> int:
        while self.par[a] != a:
            self.par[a] = self.par[self.par[a]]
            a = self.par[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.par[rb] = ra

    @staticmethod
    def on_seg(p, sg) -> bool:
        x, y = p
        x1, y1, x2, y2 = sg
        if x1 == x2:
            return x == x1 and y1 <= y <= y2
        if y1 == y2:
            return y == y1 and x1 <= x <= x2
        return False

    def _touching(self, a, b) -> bool:
        ea = {(a[0], a[1]), (a[2], a[3])}
        eb = {(b[0], b[1]), (b[2], b[3])}
        if ea & eb:
            return True
        return any(self.on_seg(p, b) for p in ea) or any(self.on_seg(p, a) for p in eb)

    def at(self, loc) -> set[int]:
        """落在该点上的所有导线（端点或中段），返回它们所在网络的根。"""
        return {self.find(k) for k, sg in enumerate(self.segs) if self.on_seg(loc, sg)}

    def overlaps(self) -> list[tuple[int, int]]:
        """共线且区间真重叠（只共享端点=拐角，不算）→ 会短接。"""
        bad = []
        for i in range(len(self.segs)):
            p = self.segs[i]
            for j in range(i + 1, len(self.segs)):
                q = self.segs[j]
                if p[0] == p[2] == q[0] == q[2]:
                    if min(p[3], q[3]) > max(p[1], q[1]):
                        bad.append((i, j))
                elif p[1] == p[3] == q[1] == q[3]:
                    if min(p[2], q[2]) > max(p[0], q[0]):
                        bad.append((i, j))
        return bad


def collect_ports(circ: str, circuit: str) -> list[dict]:
    out = []
    for c in ita_probe.ends(circ, circuit):
        for p in c["ports"]:
            out.append({"comp": c["comp"], "cloc": c["loc"], "loc": p["loc"],
                        "width": p["width"], "dir": p["dir"]})
    return out


def groups(circ: str, circuit: str):
    """返回 (net, {根: [端口...]})；同一端口落在多张网上时按 Logisim 语义合并。"""
    net = Net(read_wires(circ, circuit))
    ports = collect_ports(circ, circuit)
    for p in ports:
        roots = sorted(net.at(p["loc"]))
        for r in roots[1:]:
            net.union(roots[0], r)
    out: dict = {}
    for p in ports:
        roots = sorted(net.at(p["loc"]))
        key = roots[0] if roots else ("float",) + tuple(p["loc"])
        out.setdefault(key, []).append(p)
    return net, out


def grid_problems(segs) -> list[tuple[tuple[int, int, int, int], str]]:
    """导线必须水平/垂直，长度须为 10 的倍数。

    Logisim 的 WireRepair.doOverlaps 按 Wire.iterator() 逐点建 HashMap；
    斜线或非 10 倍数的线会让它反复拆分、表无限增长 —— 体感是「加载卡死/OOM」。
    见 pitfalls L11。
    """
    bad = []
    for sg in segs:
        dx, dy = sg[2] - sg[0], sg[3] - sg[1]
        if dx and dy:
            bad.append((sg, "斜线"))
        elif dx % 10 or dy % 10:
            bad.append((sg, "长度 %d/%d 不是 10 的倍数" % (dx, dy)))
    return bad


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    circ = sys.argv[1]
    circuit = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None
    only_ovl = "--overlap" in sys.argv
    only_grid = "--grid" in sys.argv

    if only_ovl or only_grid:         # 纯几何检查：不需要加载 Logisim
        if circuit is None:
            circuit = ita_probe.list_pins(circ, None)["circuit"]
        segs = read_wires(circ, circuit)
        if only_grid:
            bad = grid_problems(segs)
            if not bad:
                print(f"[OK] {circuit}: {len(segs)} 根导线全部水平/垂直且在 10px 网格上")
            else:
                print(f"[!] {circuit}: {len(bad)} 根导线不在 10px 网格（加载可能卡死/OOM）")
                for sg, why in bad:
                    print("  ", sg, why)
            return
        net = Net(segs)
        if not net.overlaps():
            print(f"[OK] {circuit}: 共线重叠 0 处")
        else:
            print(f"[!] {circuit}: 共线重叠 {len(net.overlaps())} 处（会短接）")
            for i, j in net.overlaps():
                print("  ", net.segs[i], "×", net.segs[j])
        return

    comp = None
    if "--comp" in sys.argv:
        comp = sys.argv[sys.argv.index("--comp") + 1]

    if circuit is None:
        circuit = ita_probe.list_pins(circ, None)["circuit"]
    net, gs = groups(circ, circuit)
    ovl = net.overlaps()

    print(f"{circuit}: 导线 {len(net.segs)} 根，网络 {len(gs)} 个，共线重叠 {len(ovl)} 处")
    if ovl:
        for i, j in ovl:
            print(f"  [!] 短接 {net.segs[i]} × {net.segs[j]}")
    shown = 0
    for key, ps in sorted(gs.items(), key=lambda kv: str(kv[0])):
        if len(ps) < 2:
            continue
        if comp and not any(p["comp"] == comp for p in ps):
            continue
        shown += 1
        print(f"\n#{shown}  {len(ps)} 个端口")
        for p in ps:
            print(f"    {p['comp']}@{p['cloc']}  端口{p['loc']}  w{p['width']} {p['dir']}")
    if shown == 0:
        print("没有找到含 ≥2 个端口的网络（检查电路名 / --comp 过滤）")


if __name__ == "__main__":
    main()