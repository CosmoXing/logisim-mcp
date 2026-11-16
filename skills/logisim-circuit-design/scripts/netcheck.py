#!/usr/bin/env python3
"""按真实端口坐标 + 导线图检查 .circ 的网络位宽冲突。

为什么需要：Logisim 状态栏只会显示“位宽不匹配 (N)”，不告诉你位置；
而 MCP 的 `circ271_check` 按引脚**标签**建网，跨电路同名标签会被并成一张网
（假阳性）。本脚本用 `ita_probe.ends()` 拿 Logisim 自己算出的端口坐标，
再按几何连通性（端点重合 / 端点落在另一根线中段 = T 接）建网，
逐网比对端口位宽，一次列出全部冲突点及其所属元件。

用法：
    python netcheck.py <circ> [circuit]
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ita_probe  # noqa: E402


def _read_circuit_xml(path: str, circuit: str) -> str:
    s = open(path, encoding="utf-8").read()
    i = s.index(f'<circuit name="{circuit}">')
    j = s.index("</circuit>", i)
    return s[i:j]


def check(circ: str, circuit: str) -> list[dict]:
    comps = ita_probe.ends(circ, circuit)
    ports = []
    for c in comps:
        for p in c["ports"]:
            ports.append((p["loc"][0], p["loc"][1], p["width"], c["comp"], c["loc"]))

    blk = _read_circuit_xml(circ, circuit)
    wires = [(int(a), int(b), int(c), int(d)) for a, b, c, d in
             re.findall(r'<wire from="\((\d+),(\d+)\)" to="\((\d+),(\d+)\)"', blk)]

    parent: dict = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def on_seg(px, py, w):
        x1, y1, x2, y2 = w
        if x1 == x2 == px and min(y1, y2) <= py <= max(y1, y2):
            return True
        if y1 == y2 == py and min(x1, x2) <= px <= max(x1, x2):
            return True
        return False

    for idx, w in enumerate(wires):
        union(("w", idx), (w[0], w[1]))
        union(("w", idx), (w[2], w[3]))

    pts = set()
    for w in wires:
        pts.add((w[0], w[1]))
        pts.add((w[2], w[3]))
    for p in ports:
        pts.add((p[0], p[1]))

    for (px, py) in pts:
        for idx, w in enumerate(wires):
            if on_seg(px, py, w):
                union((px, py), ("w", idx))

    nets: dict = {}
    for (x, y, w, comp, loc) in ports:
        nets.setdefault(find((x, y)), []).append((comp, loc, (x, y), w))

    bad = []
    for root, lst in nets.items():
        widths = sorted({p[3] for p in lst})
        if len(widths) > 1:
            bad.append({"widths": widths, "ports": lst})
    return bad


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    circ = sys.argv[1]
    circuit = sys.argv[2] if len(sys.argv) > 2 else None
    if circuit is None:
        info = ita_probe.list_pins(circ, None)
        circuit = info["circuit"]

    bad = check(circ, circuit)
    if not bad:
        print(f"[OK] {circuit}: 唯一网络位宽全部一致，无冲突")
        return
    print(f"[!] {circuit}: {len(bad)} 个网络存在位宽冲突")
    for i, b in enumerate(bad, 1):
        print(f"\n#{i} 位宽 {b['widths']}")
        for w in b["widths"]:
            sub = [p for p in b["ports"] if p[3] == w]
            print(f"  [{w}位] {len(sub)} 个:",
                  [(c, l, xy) for c, l, xy, _ in sub[:5]],
                  "..." if len(sub) > 5 else "")
    sys.exit(1)


if __name__ == "__main__":
    main()
