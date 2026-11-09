"""声明式网表 → 多电路工程（自动布局 + 迷宫布线 + .circ 输出）。

规格示例：
{
  "file": "D:/demo.circ",
  "circuits": [
    {"name": "main",
     "pins": [{"label": "a", "dir": "in"}, {"label": "y", "dir": "out"}],
     "components": [{"id": "g1", "type": "AND", "at": [400, 300]}],
     "nets": [{"name": "a", "connect": ["pin:a", "g1.a"]},
              {"name": "y", "connect": ["g1.out", "pin:y"]}]}
  ]
}

引用语法：pin:标签、<元件id>.<端口名>（子电路用其引脚标签）。at 省略时按依赖深度自动排布。
"""

from . import geometry, router

GATE_TYPES = {"AND", "OR", "NAND", "NOR", "XOR", "XNOR", "NOT"}
SPECIAL = {"DFF", "TFF", "SPLITTER4", "CLOCK", "LED", "DISPLAY", "GROUND"}

IN_PORTS = {"a", "b", "c", "d", "e", "f", "g", "h", "D", "T", "R", "S"}
OUT_PORTS = {"out", "Q", "NQ"}
SKIP_FOR_DEPTH = {"CLK"}


class BuildError(Exception):
    pass


def _norm_pins(circ):
    """给每个引脚分配坐标：输入在左列、输出在右列（可显式给 at）。"""
    pins = []
    i = j = 0
    for p in circ.get("pins", []):
        label = str(p["label"])
        direction = (p.get("dir") or "in").lower()
        if direction in ("out", "output"):
            at = p.get("at")
            x, y = (at[0], at[1]) if at else (None, 200 + 80 * j)
            facing, kind = "west", "output"
            j += 1
        else:
            x, y = p.get("at") or [120, 200 + 80 * i]
            facing, kind = "east", "input"
            i += 1
        pins.append({"label": label, "dir": "output" if kind == "output" else "input",
                     "x": x, "y": y, "facing": facing, "width": int(p.get("width", 1))})
    return pins


def _port_map(comp, child_pins):
    t = comp["_type"]
    if t in GATE_TYPES:
        return geometry.gate_ports(t, int(comp.get("inputs", 1 if t == "NOT" else 2)))[0]
    if t in ("DFF", "TFF"):
        return geometry.DFF_PORTS
    if t == "SPLITTER4":
        return geometry.splitter_ports(4)[0]
    if t in ("CLOCK", "LED", "DISPLAY", "GROUND"):
        return {"p": (0, 0)}
    if t in ("PIN",):
        return {"p": (0, 0)}
    # 子电路
    _, ports = geometry.sub_geometry([(p["label"], p["x"], p["y"], p["facing"]) for p in child_pins])
    return ports


def _port_width(port, comp, child_pins, pin_width=1):
    t = comp["_type"]
    if t in GATE_TYPES or t in ("DFF", "TFF", "CLOCK", "LED", "GROUND", "PIN"):
        return 1
    if t == "SPLITTER4":
        return 4 if port == "in" else 1
    if t == "DISPLAY":
        return 4
    for p in child_pins:
        if p["label"] == port:
            return p["width"]
    return 1


def _dir_of(port, comp, child_pins):
    t = comp["_type"]
    if t in GATE_TYPES:
        return "out" if port == "out" else "in"
    if t in ("DFF", "TFF"):
        return "out" if port in ("Q", "NQ") else "in"
    if t == "SPLITTER4":
        return "out" if port == "in" else "in"
    if t in ("CLOCK", "GROUND"):
        return "out"
    if t in ("LED", "DISPLAY"):
        return "in"
    if t in ("PIN",):
        return "in"
    for p in child_pins:
        if p["label"] == port:
            return "out" if p["dir"] == "output" else "in"
    raise BuildError(f"子电路 {t} 没有引脚 {port}")


def _resolve(ref, comps_by_id, pin_labels):
    if ref.startswith("pin:"):
        lbl = ref[4:]
        if lbl not in pin_labels:
            raise BuildError(f"引脚 {lbl} 未定义")
        return ("pin", lbl, None)
    if "." not in ref:
        raise BuildError(f"引用 {ref} 缺少端口名，应写成 元件id.端口")
    cid, port = ref.split(".", 1)
    if cid not in comps_by_id:
        raise BuildError(f"未定义的元件 {cid}（引用 {ref}）")
    return ("comp", cid, port)


def _depth_of(cid, comps_by_id, nets, cache, stack=()):
    if cid in cache:
        return cache[cid]
    if cid in stack:
        raise BuildError(f"组合环：{cid}")
    d = 0
    for net in nets:
        members = net.get("connect", [])
        if not any((not m.startswith("pin:")) and m.split(".", 1)[0] == cid for m in members):
            continue
        for m in members:
            if m.startswith("pin:") or "." not in m:
                continue
            sid, sport = m.split(".", 1)
            if sid == cid:
                continue
            scap = comps_by_id.get(sid)
            if scap is None:
                continue
            try:
                if _dir_of(sport, scap, scap.get("_child_pins", [])) == "in":
                    continue
            except BuildError:
                continue
            d = max(d, _depth_of(sid, comps_by_id, nets, cache, stack + (cid,)) + 1)
    cache[cid] = d
    return d


def build(spec, write=True):
    """执行规格，返回 (文本, 统计信息)。"""
    circuits = spec.get("circuits") or []
    if not circuits:
        raise BuildError("spec.circuits 不能为空")
    if not any(c.get("name") == "main" for c in circuits):
        circuits[0]["name"] = "main"

    pin_sets = {c["name"]: _norm_pins(c) for c in circuits}

    ordered = sorted(circuits, key=lambda c: 0 if c.get("name") == "main" else 1)
    boards = []
    stats = {}
    for circ in ordered:
        name = circ["name"]
        pins = pin_sets[name]
        b = router.Board(name)

        comps = []
        for raw in circ.get("components", []):
            comp = dict(raw)
            cid = str(comp.get("id") or f"c{len(comps)}")
            comp["id"] = cid
            raw = str(comp.get("type", "AND"))
            t = raw.upper()
            if t in ("PIN",):
                continue
            if t not in GATE_TYPES and t not in SPECIAL:
                # 当作子电路名（大小写不敏感）
                match = next((k for k in pin_sets if k.lower() == raw.lower()), None)
                if match is None:
                    raise BuildError(f"未知元件类型 {raw}（既不是门/触发器，也不是已定义的子电路）")
                t = match
            comp["_type"] = t
            comp["_child_pins"] = pin_sets.get(t, [])
            comps.append(comp)

        by_id = {c["id"]: c for c in comps}
        nets = circ.get("nets", [])
        cache = {}
        depths = {}
        for comp in comps:
            if comp["_type"] in GATE_TYPES or comp["_type"] in ("DFF", "TFF"):
                depths[comp["id"]] = _depth_of(comp["id"], by_id, nets, cache)
        max_d = max(depths.values(), default=0)

        counters = {}
        occupied = set()
        for comp in comps:
            if comp.get("at"):
                comp["_x"], comp["_y"] = int(comp["at"][0]), int(comp["at"][1])
                occupied.add((comp["_x"], comp["_y"]))
                continue
            t = comp["_type"]
            if t in GATE_TYPES or t in ("DFF", "TFF"):
                d = depths[comp["id"]]
                x = 340 + 200 * d
                key = ("col", d)
            elif t == "CLOCK":
                x = 200
                key = ("col", -1)
            else:                      # LED / DISPLAY 放最右列
                x = 340 + 200 * (max_d + 1)
                key = ("col", max_d + 1)
            seen = counters.setdefault(key, 0)
            y = 160 + 110 * seen
            while (x, y) in occupied:
                y += 40
            counters[key] = seen + 1
            occupied.add((x, y))
            comp["_x"], comp["_y"] = x, y

        # 输出引脚统一放到最右侧，避开所有元件
        right = 340 + 200 * (max_d + 2)
        for p in pins:
            if p["dir"] == "output" and p["x"] is None:
                p["x"] = right

        # 引脚（放在布局之后，因为输出引脚的 x 此时才确定）
        for p in pins:
            b.pin((p["x"], p["y"]), p["label"], p["dir"], p["width"])

        # 冒烟：类型对应的几何必须存在
        for comp in comps:
            t = comp["_type"]
            loc = (comp["_x"], comp["_y"])
            if t in GATE_TYPES:
                comp["_ports"] = b.gate(loc, t, int(comp.get("inputs", 1 if t == "NOT" else 2)))
            elif t == "DFF":
                comp["_ports"] = b.dff(loc, comp.get("label") or comp["id"])
            elif t == "TFF":
                comp["_ports"] = b.tff(loc, comp.get("label") or comp["id"])
            elif t == "SPLITTER4":
                comp["_ports"] = b.splitter4(loc)
            elif t == "CLOCK":
                comp["_ports"] = {"p": b.clock(loc)}
            elif t == "LED":
                comp["_ports"] = {"p": b.led(loc)}
            elif t == "DISPLAY":
                comp["_ports"] = {"p": b.display(loc, comp.get("label") or comp["id"])}
            elif t == "GROUND":
                comp["_ports"] = {"p": b.ground(loc)}
            else:
                comp["_ports"] = b.sub(loc, t, [(p["label"], p["x"], p["y"], p["facing"]) for p in pin_sets[t]])

        pin_points = {p["label"]: (p["x"], p["y"]) for p in pins}
        pin_widths = {p["label"]: p["width"] for p in pins}
        for net in nets:
            nname = str(net.get("name") or f"net{len(stats)}")
            pts = []
            widths = []
            for ref in net.get("connect", []):
                kind, a, port = _resolve(ref, by_id, pin_points)
                if kind == "pin":
                    pts.append(pin_points[a])
                    widths.append((ref, pin_widths[a]))
                else:
                    comp = by_id[a]
                    if port not in comp["_ports"]:
                        raise BuildError(f"元件 {a}({comp['_type']}) 没有端口 {port}，可用 {list(comp['_ports'])}")
                    pts.append(comp["_ports"][port])
                    widths.append((ref, _port_width(port, comp, comp["_child_pins"])))
            if len(pts) < 2:
                raise BuildError(f"网络 {nname} 少于两个连接点")
            uniq = {w for _, w in widths}
            if len(uniq) > 1:
                detail = "、".join(f"{r}={w}位" for r, w in widths)
                raise BuildError(f"网络 {nname} 位宽不一致：{detail}")
            try:
                b.connect(nname, pts)
            except RuntimeError as exc:
                raise BuildError(str(exc))

        stats[name] = {"components": len(b.comps), "nets": len(b.nets),
                       "segments": sum(len(v) for v in b.nets.values())}
        boards.append((name, b))

    # main 放最前
    boards.sort(key=lambda nb: 0 if nb[0] == "main" else 1)
    text = router.project(boards)
    out = spec.get("file")
    if write and out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return text, stats
