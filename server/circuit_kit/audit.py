"""静态连接体检：悬空网络、多驱动冲突、孤立端口、位宽冲突、10px 断口。

不依赖仿真取值，只看网表结构；用来在"跑出 E"之前定位问题。
"""

from . import geometry, netlist


def _is_driver(lf, port, split_mode=None):
    kind = lf["kind"]
    if kind == "Pin":
        t = lf["attrs"].get("type") or ("output" if lf["attrs"].get("output") in ("true", "1") else "input")
        return t == "input" and lf.get("path") == "r"
    if kind == "Splitter":
        mode = (split_mode or {}).get("mode", "merge")
        return port.startswith("b") if mode == "split" else port == "in"
    return port in netlist.output_ports(kind, lf["nets"])


def _label(lf):
    return lf["attrs"].get("label") or f'{lf["kind"]}@{lf["loc"]}'


def _body(lf):
    """元件包围盒 (x1,y1,x2,y2)，相对 loc；未知元件返回 None。"""
    k = lf["kind"]
    attrs = lf["attrs"]
    if k.endswith("Gate"):
        kind = k.split()[0]
        inputs = int(attrs.get("inputs", 1 if kind == "NOT" else 2))
        return geometry.gate_ports(kind, inputs)[1]
    if k in ("D Flip-Flop", "T Flip-Flop"):
        return geometry.DFF_BODY
    if k == "Splitter":
        f = int(attrs.get("fanout", 2))
        return geometry.splitter_body(f, attrs.get("facing", "east"), attrs.get("appear", "left"))
    if k == "Register":
        return netlist.REGISTER_BODY
    if k == "Multiplexer":
        return netlist.mux_body(netlist.mux_select(attrs), attrs.get("facing", "east"))
    if k == "Decoder":
        return netlist.decoder_body(netlist.decoder_select(attrs), attrs.get("facing", "east"))
    if k == "Comparator":
        return netlist.COMPARATOR_BODY
    if k == "Clock":
        return (5, -15, 35, 15)
    if k == "LED":
        return (5, -12, 32, 12)
    if k == "Hex Digit Display":
        # 5.0 源码：Bounds.create(-15, -60, 40, 60)，数据口在 (0,0)（底边）
        return (-15, -60, 25, 0)
    return None


def _dangling_wires(sim):
    """线头连通性：线端既不在端口上、也不搭在别的线上 → 悬空线头。

    H21 的 10px 断口就是这种形态：两段线各自的端点都"看起来接上了"，实际没连。
    """
    found = []
    for path, wires in sim.segs.items():
        ports = {}
        for lf in sim.leaves:
            if lf.get("path") != path:
                continue
            for port, pt in lf["ports"].items():
                if pt[0] == path:
                    ports.setdefault((pt[1], pt[2]), f"{_label(lf)}.{port}")
        for (x, y, name) in sim.inst_ports.get(path, []):
            ports.setdefault((x, y), f"{name} 实例端口")
        for seg in wires:
            x1, y1, x2, y2 = seg
            if (x1, y1) == (x2, y2):
                continue
            for (x, y) in ((x1, y1), (x2, y2)):
                if (x, y) in ports:
                    continue
                if any(other != seg and netlist.on_seg((x, y), other) for other in wires):
                    continue
                near = None
                for (px, py), pname in ports.items():
                    if (px == x and abs(py - y) <= 20) or (py == y and abs(px - x) <= 20):
                        d = abs(px - x) + abs(py - y)
                        if near is None or d < near[0]:
                            near = (d, pname, (px, py))
                item = {"end": [x, y], "path": path}
                if near:
                    item.update({"nearest_port": near[1], "port_at": list(near[2]), "gap": near[0]})
                found.append(item)
    return found


def audit(path):
    circuits, main = netlist.parse(path)
    # strict=False：不认识的元件先记下来，其余部分仍给出体检结果
    sim = netlist.Sim(circuits, main, strict=False)

    members = {}
    split_of = {}
    for idx, lf in enumerate(sim.leaves):
        if lf["kind"] == "Splitter":
            split_of[idx] = {"mode": sim.split_mode.get(idx, "merge")}
        for port, net in lf["nets"].items():
            members.setdefault(net, []).append((idx, lf, port))

    floating, conflict, dangling, width_conflict = [], [], [], []
    for net, items in members.items():
        drivers = [(lf, p) for idx, lf, p in items if _is_driver(lf, p, split_of.get(idx))]
        readers = [(lf, p) for idx, lf, p in items if not _is_driver(lf, p, split_of.get(idx))]
        if len(items) == 1:
            _, lf, p = items[0]
            benign = (lf["kind"] in ("D Flip-Flop", "T Flip-Flop") and p in ("R", "S", "NQ")) \
                or (lf["kind"] == "Splitter" and p.startswith("b")) \
                or (lf["kind"] == "Comparator" and p in ("gt", "eq", "lt"))
            if not benign:
                dangling.append({"port": f"{_label(lf)}.{p}", "kind": lf["kind"], "at": list(lf["loc"])})
            continue
        if not drivers and readers:
            floating.append({"members": [f"{_label(lf)}.{p}" for _, lf, p in items][:8],
                             "count": len(items)})
        if len(drivers) > 1:
            conflict.append({"drivers": [f"{_label(lf)}.{p}" for lf, p in drivers][:8],
                             "members": len(items)})
        widths = {}
        for idx, lf, p in items:
            w = lf["w"].get(p, 0)
            if w and w > 0:
                widths.setdefault(w, []).append(f"{_label(lf)}.{p}")
        if len(widths) > 1:
            width_conflict.append({
                "widths": {str(w): names[:4] for w, names in sorted(widths.items())},
                "members": len(items),
            })

    # 元件体是否重叠（同层坐标）
    bodies = []
    for lf in sim.leaves:
        body = _body(lf)
        if body is None:
            continue
        loc = lf["loc"]
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

    near = _dangling_wires(sim)
    problems = dangling or floating or conflict or overlap or width_conflict or near
    report = {
        "file": path,
        "circuits": sorted(circuits.keys()),
        "nets": len(members),
        "ports": sum(len(v) for v in members.values()),
        "dangling": dangling,
        "floating": floating,
        "conflict": conflict,
        "width_conflict": width_conflict,
        "dangling_wire": near,
        "body_overlap": overlap,
        "verdict": "partial" if sim.unsupported else ("problems" if problems else "ok"),
    }
    if sim.unsupported:
        report["unsupported"] = sim.unsupported
        report["warning"] = ("有元件不在网表支持范围内，以上结论只覆盖其余元件；"
                             "请用 circ_probe 确认该元件的几何，或先扩展 netlist.SUPPORTED。")
    return report
