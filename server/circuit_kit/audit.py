"""静态连接体检：悬空网络、多驱动冲突、孤立端口。

不依赖仿真取值，只看网表结构；用来在"跑出 E"之前定位问题。
"""

from . import netlist, geometry


def _is_driver(lf, port, split_mode=None):
    kind = lf["kind"]
    if kind == "Pin":
        t = lf["attrs"].get("type") or ("output" if lf["attrs"].get("output") in ("true", "1") else "input")
        return t == "input" and lf.get("path") == "r"
    if kind.endswith("Gate"):
        return port == "out"
    if kind in ("D Flip-Flop", "T Flip-Flop"):
        return port in ("Q", "NQ")
    if kind == "Splitter":
        mode = (split_mode or {}).get("mode", "merge")
        if mode == "split":
            return port.startswith("b")
        return port == "in"
    if kind in ("Clock", "Ground", "Constant"):
        return True
    if kind == "Tunnel":
        return False
    if kind in ("LED", "Hex Digit Display"):
        return False
    return False


def _label(lf):
    return lf["attrs"].get("label") or f'{lf["kind"]}@{lf["loc"]}'


def audit(path):
    circuits, main = netlist.parse(path)
    try:
        sim = netlist.Sim(circuits, main)
    except netlist.UnsupportedComponent as exc:
        return {"file": path, "circuits": sorted(circuits.keys()), "nets": 0, "ports": 0,
                "dangling": [], "floating": [], "conflict": [], "body_overlap": [],
                "unsupported": str(exc), "verdict": "unsupported"}

    members = {}
    split_of = {}
    for idx, lf in enumerate(sim.leaves):
        if lf["kind"] == "Splitter":
            split_of[idx] = {"mode": sim.split_mode.get(idx, "merge")}
        for port, net in lf["nets"].items():
            members.setdefault(net, []).append((idx, lf, port))

    floating, conflict, dangling = [], [], []
    for net, items in members.items():
        drivers = [(lf, p) for idx, lf, p in items if _is_driver(lf, p, split_of.get(idx))]
        readers = [(lf, p) for idx, lf, p in items if not _is_driver(lf, p, split_of.get(idx))]
        if len(items) == 1:
            _, lf, p = items[0]
            benign = (lf["kind"] in ("D Flip-Flop", "T Flip-Flop") and p in ("R", "S", "NQ")) \
                or (lf["kind"] == "Splitter" and p.startswith("b"))
            if not benign:
                dangling.append({"port": f"{_label(lf)}.{p}", "kind": lf["kind"], "at": list(lf["loc"])})
            continue
        if not drivers and readers:
            floating.append({"members": [f"{_label(lf)}.{p}" for _, lf, p in items][:8],
                             "count": len(items)})
        if len(drivers) > 1:
            conflict.append({"drivers": [f"{_label(lf)}.{p}" for lf, p in drivers][:8],
                             "members": len(items)})

    # 元件体是否重叠（同层坐标）
    bodies = []
    for lf in sim.leaves:
        k = lf["kind"]
        loc = lf["loc"]
        if k.endswith("Gate"):
            kind = k.split()[0]
            pts, body = geometry.gate_ports(
                kind, int(lf["attrs"].get("inputs", 1 if kind == "NOT" else 2)))
        elif k in ("D Flip-Flop", "T Flip-Flop"):
            body = geometry.DFF_BODY
        elif k == "Splitter":
            body = geometry.splitter_ports(int(lf["attrs"].get("fanout", 2)))[1]
        elif k == "Clock":
            body = (5, -15, 35, 15)
        elif k == "LED":
            body = (5, -12, 32, 12)
        elif k == "Hex Digit Display":
            # 5.0 源码：Bounds.create(-15, -60, 40, 60)，数据口在 (0,0)（底边）
            body = (-15, -60, 25, 0)
        else:
            continue
        bodies.append((lf.get("path", "r"), (loc[0] + body[0], loc[1] + body[1],
                                             loc[0] + body[2], loc[1] + body[3]), _label(lf)))
    overlap = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            if bodies[i][0] != bodies[j][0]:
                continue
            a, b = bodies[i][1], bodies[j][1]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                overlap.append([bodies[i][2], bodies[j][2]])

    report = {
        "file": path,
        "circuits": sorted(circuits.keys()),
        "nets": len(members),
        "ports": sum(len(v) for v in members.values()),
        "dangling": dangling,
        "floating": floating,
        "conflict": conflict,
        "body_overlap": overlap,
        "verdict": "ok" if not (dangling or floating or conflict or overlap) else "problems",
    }
    return report
