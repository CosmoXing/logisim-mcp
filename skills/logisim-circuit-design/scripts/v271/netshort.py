#!/usr/bin/env python3
"""多驱动 / 位宽冲突检查（Logisim 2.7.1 / 2.16）

netcheck.py 只能查"位宽不一致"；本脚本查的是**同宽短接**：
两个驱动同时挂在同一个网络上（比如 WE 引脚撞上译码器 out3 输出），
位宽一样时 netcheck 认为没问题，但仿真时一旦两驱动值不同，整根线变红（E）。

用法:
    python netshort.py file.circ "电路名"

原理:
  1) 用 ita_probe ends 拿 Logisim 自己算的真实端口坐标；
  2) 用导线做并查集（端点落在别的导线中段 = T 接）；
  3) 同名 Tunnel 合并；
  4) 统计每个网络上的**驱动端**：
       Pin(dir=in) / Constant / Button / Clock / 门·译码器·MUX·寄存器的 out
     驱动数 ≥ 2 → 报冲突。
"""
import os
import re
import sys
import ast
import subprocess
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "ita_probe.py")

DRIVER_NAMES = {
    "Constant", "Button", "Clock", "Power",
    "AND Gate", "OR Gate", "NAND Gate", "NOR Gate", "XOR Gate", "XNOR Gate",
    "NOT Gate", "Buffer", "Controlled Buffer", "Decoder", "Multiplexer",
    "Demultiplexer", "Adder", "Subtractor", "Comparator", "RAM", "ROM",
}


def probe_ends(circ_file, circuit):
    out = subprocess.run(
        [sys.executable, PROBE, "ends", circ_file, circuit],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def parse_ends(text):
    comps = []
    for line in text.splitlines():
        m = re.match(r"(.+?)\s+\(\s*(\d+),\s*(\d+)\s*\)\s+(\[.*\])\s*$", line.strip())
        if not m:
            continue
        try:
            ports = ast.literal_eval(m.group(4))
        except Exception:
            continue
        comps.append((m.group(1).strip(), int(m.group(2)), int(m.group(3)), ports))
    return comps


def parse_circuit(path, name):
    s = open(path, encoding="utf-8").read()
    i = s.index(f'<circuit name="{name}">')
    j = s.index("</circuit>", i)
    blk = s[i:j]
    wires = [(int(a), int(b), int(c), int(d)) for a, b, c, d in
             re.findall(r'<wire from="\((\d+),(\d+)\)" to="\((\d+),(\d+)\)"', blk)]
    tunnels = {}
    for m in re.finditer(r'<comp[^>]*loc="\((\d+),(\d+)\)"[^>]*name="Tunnel">(.*?)</comp>',
                         blk, re.S):
        lab = re.search(r'name="label"\s+val="([^"]*)"', m.group(3))
        tunnels[(int(m.group(1)), int(m.group(2)))] = lab.group(1) if lab else ""
    return wires, tunnels, blk


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    circ_file, circuit = sys.argv[1], sys.argv[2]
    comps = parse_ends(probe_ends(circ_file, circuit))
    wires, tunnels, blk = parse_circuit(circ_file, circuit)
    if not comps:
        print("[ERR] 没拿到端口信息，检查 ita_probe ends 是否可用")
        return 2

    parent = {}

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
    for _, _, _, ports in comps:
        for p in ports:
            pts.add(tuple(p["loc"]))
    for (px, py) in pts:
        for idx, w in enumerate(wires):
            if on_seg(px, py, w):
                union((px, py), ("w", idx))

    bylabel = defaultdict(list)
    for pos, lab in tunnels.items():
        if lab:
            bylabel[lab].append(pos)
    for lab, poss in bylabel.items():
        for p in poss[1:]:
            union(poss[0], p)

    nets = defaultdict(lambda: {"drivers": [], "widths": set(), "ports": []})
    for (n, cx, cy, ports) in comps:
        for p in ports:
            r = find(tuple(p["loc"]))
            nets[r]["widths"].add(p["width"])
            nets[r]["ports"].append((n, cx, cy, tuple(p["loc"]), p["width"], p["dir"]))
            is_driver = False
            if n == "Pin":
                # ends 的 dir 是"网络视角"：输入引脚 dir=out（驱动），输出引脚 dir=in（负载）
                is_driver = (p["dir"] == "out")
            elif n == "Tunnel" or n == "Splitter":
                is_driver = False
            elif n in DRIVER_NAMES:
                is_driver = (p["dir"] == "out")
            else:
                is_driver = (p["dir"] == "out")          # 子电路输出端口
            if is_driver:
                nets[r]["drivers"].append((n, cx, cy, tuple(p["loc"])))

    bad = 0
    for r, info in nets.items():
        if len(info["drivers"]) < 2:
            continue
        bad += 1
        labels = []
        for pos, lab in tunnels.items():
            if lab and find(pos) == r and lab not in labels:
                labels.append(lab)
        print(f"\n=== 多驱动网络 #{bad}  位宽={sorted(info['widths'])}  标签={labels} ===")
        for d in info["drivers"]:
            print(f"    驱动: {d[0]:16s} @({d[1]},{d[2]}) port={d[3]}")
        others = [p for p in info["ports"] if p not in
                  [(x[0], x[1], x[2], x[3], p2, p3) for (x, p2, p3) in []]]
        for p in info["ports"][:12]:
            if (p[0], p[1], p[2], p[3]) not in [(d[0], d[1], d[2], d[3]) for d in info["drivers"]]:
                print(f"    负载: {p[0]:16s} @({p[1]},{p[2]}) port={p[3]} w{p[4]}")

    print(f"\n[{'FAIL' if bad else 'OK'}] {circuit}: 多驱动网络 {bad} 个 | 网络总数 {len(nets)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
