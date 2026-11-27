"""子电路外观：spec 生成、校验、XML 读取/写入与影响面分析。

坐标约定：外观坐标以 circ-anchor 为原点，单位像素，必须落在 grid（默认 10）上。
端口 spec 里的 pin 指向原理图 Pin，pin_at 是 Pin 在原理图中的绝对坐标 "x,y"。
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
import xml.etree.ElementTree as ET

from . import netlist

DEFAULT_LAYOUT = {
    "preserve_port_positions": True,
    "grid": 10,
    "row_pitch": 20,
    "margin_x": 20,
    "margin_top": 20,
    "margin_bottom": 20,
    "min_width": 120,
    "corner_radius": 10,
    "nameplate": {
        "enabled": True,
        "height": 20,
        "fill": "#000000",
        "text_color": "#FFFFFF",
        "font_size": 12,
        "bold": True,
        "text": None,
    },
    "port_labels": {
        "enabled": True,
        "offset": 8,
        "font_size": 11,
        "show_width": True,
        "template": "{label}[{width}]",
    },
    "box": {"stroke": "#000000", "fill": "none", "stroke_width": 2},
    "anchor": {"x": 0, "y": 0, "facing": "east"},
}


def _merge(base, override):
    out = json.loads(json.dumps(base))
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _grid(v, grid=10):
    return int(round(float(v) / grid) * grid)


def _ceil_grid(v, grid=10):
    import math

    return int(math.ceil(float(v) / grid) * grid)


def estimate_text_px(text, size=11):
    """不依赖 Pillow 的宽度估算：ASCII 0.55×字号，CJK/全角 1.0×字号。"""
    total = 0.0
    for ch in str(text):
        if ch == "\t":
            total += 4 * size * 0.55
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            total += size
        else:
            total += size * 0.55
    return int(round(total))


def pin_label(pin, show_width=True, template="{label}[{width}]"):
    label = str(pin.get("label") or "")
    width = int(pin.get("width", 1) or 1)
    if show_width and width > 1:
        try:
            return template.format(label=label, width=width)
        except (KeyError, ValueError):
            return f"{label}[{width}]"
    try:
        return template.format(label=label, width=width) if "{" in template else label
    except (KeyError, ValueError):
        return label


def pins_from_file(path, circuit=None):
    """从 .circ 读取 Pin 列表：label / at / dir / width。"""
    circuits, main = netlist.parse(path)
    name = circuit or main
    circ = circuits.get(name)
    if circ is None:
        raise ValueError(f"电路 {name} 不存在；可选: {sorted(circuits)}")
    out = []
    for (label, x, y, facing, kind, width) in circ.pins:
        out.append({
            "label": label,
            "at": f"{x},{y}",
            "x": x,
            "y": y,
            "dir": "out" if kind == "output" else "in",
            "width": int(width),
        })
    return out


def _port_sort_key(pin):
    return (pin.get("y", 0), pin.get("x", 0))


def auto_layout(pins, circuit, options=None, current_ports=None):
    """生成一份可直接交给 Java 桥的外观 spec。

    current_ports 形如 [{label, at, x, y, dir, width}]，是当前外观里端口的位置。
    默认 preserve_port_positions=True：保留这些端口的相对坐标，只重画框和名称牌。
    """
    layout = _merge(DEFAULT_LAYOUT, options or {})
    grid = int(layout.get("grid", 10))
    pitch = int(layout.get("row_pitch", 20))
    margin_x = int(layout.get("margin_x", 20))
    margin_top = int(layout.get("margin_top", 20))
    margin_bottom = int(layout.get("margin_bottom", 20))
    min_width = int(layout.get("min_width", 120))
    label_opt = layout.get("port_labels") or {}
    plate = layout.get("nameplate") or {}
    plate_h = int(plate.get("height", 20)) if plate.get("enabled", True) else 0

    left = [p for p in pins if p.get("dir") == "in"]
    right = [p for p in pins if p.get("dir") != "in"]
    left.sort(key=_port_sort_key)
    right.sort(key=_port_sort_key)

    ports = []
    if layout.get("preserve_port_positions", True) and current_ports:
        by_key = {(p.get("label"), p.get("at")): p for p in current_ports}
        by_label = {}
        for p in current_ports:
            by_label.setdefault(p.get("label"), []).append(p)
        xs, ys = [], []
        for pin in pins:
            src = by_key.get((pin.get("label"), pin.get("at")))
            if src is None:
                candidates = by_label.get(pin.get("label"), [])
                src = candidates[0] if len(candidates) == 1 else None
            if src is None:
                ports = []
                break
            port = {
                "pin": pin.get("label"),
                "pin_at": pin.get("at"),
                "side": "left" if pin.get("dir") == "in" else "right",
                "x": int(src.get("x", 0)),
                "y": int(src.get("y", 0)),
                "label": pin.get("label"),
                "width": int(pin.get("width", 1)),
                "dir": pin.get("dir"),
            }
            ports.append(port)
            xs.append(port["x"])
            ys.append(port["y"])
        if ports:
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            dx = margin_x - min_x
            dy = margin_top - min_y
            for p in ports:
                p["x"] += dx
                p["y"] += dy
            # 端口已整体平移 dx/dy，框体必须按平移后的极值算，
            # 否则负坐标/大幅偏移的现有外观会把端口画到框外。
            width = max(min_width, _ceil_grid(max_x + dx, grid))
            height = _ceil_grid(max_y + dy + margin_bottom + plate_h, grid)
            layout["strict_ports"] = False
            return _spec(circuit, layout, 0, 0, width, height, ports, pins)
    rows = max(len(left), len(right), 1)
    show_width = label_opt.get("show_width", True)
    template = label_opt.get("template", "{label}[{width}]")
    font_size = int(label_opt.get("font_size", 11))
    label_w = max([estimate_text_px(pin_label(p, show_width, template), font_size)
                   for p in pins] or [0])
    width = max(
        min_width,
        label_w * 2 + 2 * int(label_opt.get("offset", 8)) + 40,
    )
    width = _ceil_grid(width, grid)
    content_h = max(40, (rows - 1) * pitch + 2 * 10)
    height = _ceil_grid(content_h + margin_top + margin_bottom + plate_h, grid)

    def place(items, side):
        n = len(items)
        first = margin_top + _grid(max(0, (content_h - (n - 1) * pitch) / 2), grid)
        for i, pin in enumerate(items):
            ports.append({
                "pin": pin.get("label"),
                "pin_at": pin.get("at"),
                "side": side,
                "x": 0 if side == "left" else width,
                "y": first + i * pitch,
                "label": pin.get("label"),
                "width": int(pin.get("width", 1)),
                "dir": pin.get("dir"),
            })

    place(left, "left")
    place(right, "right")
    return _spec(circuit, layout, 0, 0, width, height, ports, pins)


def _spec(circuit, layout, x, y, width, height, ports, pins):
    layout = json.loads(json.dumps(layout))
    layout["x"] = x
    layout["y"] = y
    layout["width"] = width
    layout["height"] = height
    if layout.get("nameplate", {}).get("enabled", True) and not layout["nameplate"].get("text"):
        layout["nameplate"]["text"] = circuit
    return {
        "version": 1,
        "circuit": circuit,
        "layout": layout,
        "ports": ports,
        "texts": [],
        "shapes": [],
    }


def validate(spec, pins=None):
    """返回错误列表 [{code, message}]；空列表表示通过。"""
    errors = []
    layout = spec.get("layout") or {}
    grid = int(layout.get("grid", 10))
    width = int(layout.get("width", 0) or 0)
    height = int(layout.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        errors.append({"code": "E_BAD_BOX", "message": "layout.width/height 必须是正数"})
    ports = spec.get("ports") or []
    if pins is not None:
        expected = {(p.get("label"), p.get("at")) for p in pins}
        got = set()
        for p in ports:
            key = (p.get("pin"), p.get("pin_at"))
            if key in got:
                errors.append({"code": "E_EXTRA_PORT", "message": f"端口重复: {key}"})
            got.add(key)
        for key in sorted(expected - got, key=str):
            errors.append({"code": "E_MISSING_PORT", "message": f"缺少端口: {key}"})
        for key in sorted(got - expected, key=str):
            errors.append({"code": "E_EXTRA_PORT", "message": f"多余端口: {key}"})
    seen = set()
    plate = layout.get("nameplate") or {}
    plate_h = int(plate.get("height", 20)) if plate.get("enabled", True) else 0
    for p in ports:
        x, y = int(p.get("x", 0)), int(p.get("y", 0))
        if x % grid or y % grid:
            errors.append({"code": "E_GRID", "message": f"端口 {p.get('pin')} 坐标不在 {grid}px 网格"})
        if (x, y) in seen:
            errors.append({"code": "E_PORT_OVERLAP", "message": f"端口坐标重复: ({x},{y})"})
        seen.add((x, y))
        on_edge = x in (0, width) or y in (0, height)
        if not on_edge and spec.get("strict", True):
            errors.append({"code": "E_PORT_OFF_EDGE", "message": f"端口 {p.get('pin')} 不在框边"})
        if plate_h and height - plate_h <= y <= height:
            errors.append({"code": "E_PORT_IN_NAMEPLATE", "message": f"端口 {p.get('pin')} 落在名称牌内"})
    return errors


def read_xml(path, circuit):
    """读取 .circ 里某电路的 appearance 属性与 <appear> 形状。"""
    root = ET.parse(path).getroot()
    for c in root.findall("circuit"):
        if c.get("name") != circuit:
            continue
        attrs = {a.get("name"): a.get("val") for a in c.findall("a")}
        objects = []
        appear = c.find("appear")
        if appear is not None:
            for el in appear:
                item = {"tag": el.tag, "attrs": dict(el.attrib)}
                if el.text and el.text.strip():
                    item["text"] = el.text.strip()
                objects.append(item)
        return {
            "circuit": circuit,
            "appearance": attrs.get("appearance"),
            "named_box_fixed": attrs.get("circuitnamedboxfixedsize"),
            "objects": objects,
        }
    raise ValueError(f"电路 {circuit} 不存在")


def _xml_escape(v):
    s = str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def _shape_xml(item, indent="      "):
    tag = item.get("tag") or item.get("type")
    attrs = item.get("attrs") or {}
    if tag in ("rect", "roundrect", "line", "ellipse", "polyline", "polygon", "path", "circ-anchor", "circ-port"):
        tag = "rect" if tag == "roundrect" else tag
        body = "".join(f' {k}="{_xml_escape(v)}"' for k, v in attrs.items())
        return f"{indent}<{tag}{body}/>"
    if tag == "text":
        body = "".join(f' {k}="{_xml_escape(v)}"' for k, v in attrs.items())
        return f"{indent}<text{body}>{_xml_escape(item.get('text', ''))}</text>"
    raise ValueError(f"不支持的形状 {tag}")


def write_xml(path, spec):
    """无 Java 桥时的兜底：直接把 <appear> 写进 .circ。"""
    circuit = spec["circuit"]
    layout = spec.get("layout") or {}
    width = int(layout.get("width", 0))
    height = int(layout.get("height", 0))
    plate = layout.get("nameplate") or {}
    plate_h = int(plate.get("height", 20)) if plate.get("enabled", True) else 0
    objects = []
    anchor = layout.get("anchor") or {}
    objects.append({"tag": "circ-anchor", "attrs": {
        "x": int(anchor.get("x", 0)), "y": int(anchor.get("y", 0)),
        "facing": anchor.get("facing", "east")}})
    box = layout.get("box") or {}
    body = {"x": int(layout.get("x", 0)), "y": int(layout.get("y", 0)),
            "width": width, "height": height,
            "stroke": box.get("stroke", "#000000"), "fill": box.get("fill", "none"),
            "stroke-width": int(box.get("stroke_width", 2))}
    if int(layout.get("corner_radius", 0) or 0) > 0:
        body["rx"] = int(layout.get("corner_radius"))
    objects.append({"tag": "rect", "attrs": body})
    if plate_h:
        objects.append({"tag": "rect", "attrs": {
            "x": int(layout.get("x", 0)), "y": int(layout.get("y", 0)) + height - plate_h,
            "width": width, "height": plate_h, "stroke": "none",
            "fill": plate.get("fill", "#000000")}})
        objects.append({"tag": "text", "text": plate.get("text") or circuit, "attrs": {
            "x": int(layout.get("x", 0)) + width // 2,
            "y": int(layout.get("y", 0)) + height - plate_h // 2,
            "fill": plate.get("text_color", "#FFFFFF"), "font-family": "SansSerif",
            "font-size": int(plate.get("font_size", 12)),
            "font-weight": "bold" if plate.get("bold", True) else "plain",
            "text-anchor": "middle", "dominant-baseline": "middle"}})
    label_opt = layout.get("port_labels") or {}
    if label_opt.get("enabled", True):
        offset = int(label_opt.get("offset", 8))
        size = int(label_opt.get("font_size", 11))
        for p in spec.get("ports") or []:
            text = pin_label(p, label_opt.get("show_width", True),
                             label_opt.get("template", "{label}[{width}]"))
            left = p.get("side") != "right"
            objects.append({"tag": "text", "text": text, "attrs": {
                "x": int(p.get("x", 0)) + (offset if left else -offset),
                "y": int(p.get("y", 0)), "fill": "#000000",
                "font-family": "SansSerif", "font-size": size,
                "text-anchor": "start" if left else "end",
                "dominant-baseline": "middle"}})
    for p in spec.get("ports") or []:
        objects.append({"tag": "circ-port", "attrs": {
            "x": int(p.get("x", 0)), "y": int(p.get("y", 0)),
            "dir": p.get("dir") or "in", "pin": p.get("pin_at")}})
    for item in spec.get("texts") or []:
        objects.append({"tag": "text", "text": item.get("text", ""), "attrs": {
            "x": int(item.get("x", 0)), "y": int(item.get("y", 0)),
            "fill": item.get("fill", "#000000"), "font-family": "SansSerif",
            "font-size": int(item.get("font_size", 12)),
            "text-anchor": item.get("halign", "middle"),
            "dominant-baseline": item.get("valign", "middle")}})
    for item in spec.get("shapes") or []:
        objects.append(item)

    root = ET.parse(path).getroot()
    target = next((c for c in root.findall("circuit") if c.get("name") == circuit), None)
    if target is None:
        raise ValueError(f"电路 {circuit} 不存在")
    append = None
    for a in target.findall("a"):
        if a.get("name") == "appearance":
            a.set("val", "custom")
            append = a
    if append is None:
        append = ET.Element("a", {"name": "appearance", "val": "custom"})
        target.insert(0, append)
    old = target.find("appear")
    if old is not None:
        target.remove(old)
    appear = ET.Element("appear")
    for item in objects:
        tag = item.get("tag") or item.get("type")
        el = ET.SubElement(appear, tag)
        for k, v in (item.get("attrs") or {}).items():
            el.set(str(k), str(v))
        if item.get("text"):
            el.text = str(item.get("text"))
    target.insert(1, appear)
    ET.indent(root, space="  ")
    text = ET.tostring(root, encoding="unicode")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
        fh.write(text)
        fh.write("\n")
    return len(objects)


def layout_digest(path):
    """对电气部分做顺序无关的语义哈希，用来确认外观改动没碰元件/导线。"""
    root = ET.parse(path).getroot()
    h = hashlib.sha256()
    for c in root.findall("circuit"):
        h.update(("C:" + (c.get("name") or "")).encode("utf-8"))
        comps = []
        for comp in c.findall("comp"):
            attrs = tuple(sorted((a.get("name") or "", a.get("val") or "")
                                 for a in comp.findall("a")))
            comps.append((comp.get("lib") or "", comp.get("name") or "",
                          comp.get("loc") or "", attrs))
        for item in sorted(comps, key=repr):
            h.update(repr(item).encode("utf-8"))
        wires = []
        for w in c.findall("wire"):
            try:
                ax, ay = [int(v) for v in w.get("from").strip("()").split(",")]
                bx, by = [int(v) for v in w.get("to").strip("()").split(",")]
            except (AttributeError, ValueError):
                continue
            wires.append((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))
        for item in sorted(wires):
            h.update(repr(item).encode("utf-8"))
    return h.hexdigest()


def connectivity_digest(path, circuit):
    """只对目标电路做端口分组哈希，忽略 Logisim 保存时其他电路的导线修复。"""
    circuits, _ = netlist.parse(path)
    if circuit not in circuits:
        raise ValueError(f"电路 {circuit} 不存在")
    circ = circuits[circuit]
    child = {}
    for name, c in circuits.items():
        child[name] = [(label, x, y, facing)
                       for (label, x, y, facing, kind, width) in c.pins]

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

    def on(pt, s):
        x, y = pt
        x1, y1, x2, y2 = s
        return ((y == y1 == y2 and min(x1, x2) <= x <= max(x1, x2))
                or (x == x1 == x2 and min(y1, y2) <= y <= max(y1, y2)))

    segs, pts = [], set()
    for (ax, ay, bx, by) in circ.wires:
        segs.append((ax, ay, bx, by))
        pts.add((ax, ay))
        pts.add((bx, by))
        union(("w", ax, ay), ("w", bx, by))
    for p in pts:
        for s in segs:
            if on(p, s):
                union(("w",) + p, ("w", s[0], s[1]))
    groups = {}
    for idx, comp in enumerate(circ.comps):
        pm = _component_ports(comp, child)
        if not pm:
            continue
        for port, (dx, dy) in pm.items():
            pt = (comp.loc[0] + dx, comp.loc[1] + dy)
            union(("p", idx, port), ("w",) + pt)
            for s in segs:
                if on(pt, s):
                    union(("p", idx, port), ("w", s[0], s[1]))
            groups.setdefault(find(("p", idx, port)), set()).add((idx, port))
    h = hashlib.sha256()
    for g in sorted((sorted(v) for v in groups.values()), key=repr):
        h.update(repr(g).encode("utf-8"))
    return h.hexdigest()


def _component_ports(comp, child):
    name, attrs = comp.name, comp.attrs
    if name in ("Pin", "Ground", "Tunnel", "Clock", "LED", "Constant", "Hex Digit Display", "Probe"):
        return {"p": (0, 0)}
    if name == "Splitter":
        f = int(attrs.get("fanout", 2))
        sx = -20 if attrs.get("facing") == "west" else 20
        pts = {"in": (0, 0)}
        for i in range(f):
            pts[f"b{i}"] = (sx, (-40 if f == 8 else -20) + 10 * i)
        return pts
    if name in ("D Flip-Flop", "T Flip-Flop"):
        return netlist.DFF_PORTS if name == "D Flip-Flop" else netlist.TFF_PORTS
    if name.endswith("Gate"):
        kind = name.split()[0]
        return netlist.gate_ports(kind, int(attrs.get("inputs", 1 if kind == "NOT" else 2)))
    if comp.lib is None and name in child:
        return netlist.sub_port_offsets(child[name])
    return {}


def parent_impact(path, circuit, old_ports, new_ports, old_anchor=(0, 0), new_anchor=(0, 0)):
    """统计移动端口会影响多少父电路导线端点（只做数量估算）。"""
    root = ET.parse(path).getroot()
    old_abs = {(int(p["x"]) - int(old_anchor[0]), int(p["y"]) - int(old_anchor[1]))
               for p in old_ports}
    new_abs = {(int(p["x"]) - int(new_anchor[0]), int(p["y"]) - int(new_anchor[1]))
               for p in new_ports}
    moved = old_abs - new_abs
    parents = []
    for c in root.findall("circuit"):
        if c.get("name") == circuit:
            continue
        hits = 0
        for comp in c.findall("comp"):
            if comp.get("name") != circuit:
                continue
            loc = comp.get("loc", "(0,0)")
            try:
                lx, ly = [int(v) for v in loc.strip("()").split(",")]
            except ValueError:
                continue
            for w in c.findall("wire"):
                for key in ("from", "to"):
                    try:
                        wx, wy = [int(v) for v in w.get(key).strip("()").split(",")]
                    except ValueError:
                        continue
                    if (wx - lx, wy - ly) in moved:
                        hits += 1
        if hits:
            parents.append({"circuit": c.get("name"), "wires": hits})
    return {"moved_ports": len(moved), "parents": parents,
            "total_wires": sum(p["wires"] for p in parents)}
