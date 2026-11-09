"""Logisim-evolution 5.0 .circ 生成器（零依赖，只用标准库）。

设计目标是「一次写对」：所有坐标常量都来自实测（见 references/geometry.md），
不要凭直觉改这里的数字，尤其是子电路端口 10px 间距和分线器 ±(20,20) 偏移。

典型用法：
    import logisim_gen as G
    body  = G.pin(120, 60, "a")
    body += G.gate(320, 100, "XOR")
    body += G.path((120, 60), (300, 100))
    open("demo.circ", "w", encoding="utf-8", newline="\\n").write(G.project([("main", body)]))
"""

GATE = "1"   # #Gates
WIRE = "0"   # #Wiring
IO = "5"     # #I/O
BASE = "8"   # #Base

# 5.0 默认工具栏：lib 必须是 8(#Base)，否则打开时报「在库中找不到该工具」
_TOOLBAR = (
    "  <mappings>\n"
    '    <tool lib="8" name="Poke Tool" map="Button2"/>\n'
    '    <tool lib="8" name="Menu Tool" map="Button3"/>\n'
    "  </mappings>\n"
    "  <toolbar>\n"
    '    <tool lib="8" name="Poke Tool"/>\n'
    '    <tool lib="8" name="Edit Tool"/>\n'
    '    <tool lib="8" name="Wiring Tool"/>\n'
    '    <tool lib="8" name="Text Tool"/>\n'
    "    <sep/>\n"
    "  </toolbar>\n"
)


# ------------------------------------------------------------------ 元件
def pin(x, y, label, kind="input", width=1, facing=None):
    """引脚。kind='input' 朝东，'output' 朝西；loc 就是连线接点。"""
    face = facing or ("east" if kind == "input" else "west")
    extra = f'<a name="width" val="{width}"/>' if width != 1 else ""
    return (
        f'    <comp lib="{WIRE}" loc="({x},{y})" name="Pin">'
        f'<a name="type" val="{kind}"/><a name="facing" val="{face}"/>{extra}'
        f'<a name="label" val="{label}"/></comp>\n'
    )


def gate(x, y, kind, inputs=2, size=None):
    """门。loc 是【输出】口。

    输入口 x = -(size + bonus + 反相圈*10)，5.0 默认 size=50：
        AND/OR  -50      NAND/NOR/XOR  -60      XNOR  -70      NOT  -30（特例，宽度 30）
    3.9 的 size=40 对应 -20，不要混用（差 30px 会整体悬空）。
    kind 例：AND OR NOT XOR NAND NOR XNOR。
    """
    if inputs <= 1:
        inner = '<a name="inputs" val="1"/>'
    else:
        inner = f'<a name="inputs" val="{inputs}"/>'
    if size is not None:
        inner += f'<a name="size" val="{size}"/>'
    return f'    <comp lib="{GATE}" loc="({x},{y})" name="{kind} Gate">{inner}</comp>\n'


def sub(x, y, name, label=None):
    """子电路实例。输入口 (x-30, y+10i)，输出口 (x, y+10j)。"""
    lab = f'<a name="label" val="{label}"/>' if label else ""
    return f'    <comp loc="({x},{y})" name="{name}">{lab}</comp>\n'


def splitter(x, y, fanout, incoming=None, bits=None, appear="center"):
    """分线器。合并侧在 loc，分线侧在 (x+20, y-20+10i)，bit0 在最上。"""
    inc = fanout if incoming is None else incoming
    if bits is None:
        bits = list(range(fanout))
    inner = (
        f'<a name="fanout" val="{fanout}"/><a name="incoming" val="{inc}"/>'
        f'<a name="appear" val="{appear}"/>'
        + "".join(f'<a name="bit{i}" val="{b}"/>' for i, b in enumerate(bits))
    )
    return f'    <comp lib="{WIRE}" loc="({x},{y})" name="Splitter">{inner}</comp>\n'


def display(x, y, label=None, width=4):
    """十六进制数码管。组件名必须是 "Hex Digit Display"；数据口固定 4 位在 loc。"""
    w = f'<a name="width" val="{width}"/>' if width != 4 else ""
    lab = f'<a name="label" val="{label}"/>' if label else ""
    return f'    <comp lib="{IO}" loc="({x},{y})" name="Hex Digit Display">{w}{lab}</comp>\n'


def constant(x, y, value, width=1, facing="east"):
    """常量。value 以十六进制写入（Logisim 的 value 属性按 16 进制解析）。"""
    return (
        f'    <comp lib="{WIRE}" loc="({x},{y})" name="Constant">'
        f'<a name="width" val="{width}"/><a name="value" val="{value:x}"/>'
        f'<a name="facing" val="{facing}"/></comp>\n'
    )


def power(x, y, facing="east"):
    return f'    <comp lib="{WIRE}" loc="({x},{y})" name="Power"><a name="facing" val="{facing}"/></comp>\n'


def ground(x, y, facing="east"):
    return f'    <comp lib="{WIRE}" loc="({x},{y})" name="Ground"><a name="facing" val="{facing}"/></comp>\n'


# ------------------------------------------------------------------ 导线
def wire(x1, y1, x2, y2):
    if x1 == x2 and y1 == y2:
        return ""
    return f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>\n'


def path(*pts):
    """折线：path((0,0),(100,0),(100,60))。"""
    out = ""
    for i in range(len(pts) - 1):
        out += wire(*pts[i], *pts[i + 1])
    return out


def wires_from(nets):
    """把 {net: [(x1,y1,x2,y2), ...]} 去重后转成 <wire> 文本（布线器输出用）。"""
    out, seen = "", set()
    for segs in nets.values():
        for x1, y1, x2, y2 in segs:
            key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if key in seen:
                continue
            seen.add(key)
            out += wire(x1, y1, x2, y2)
    return out


# ------------------------------------------------------------------ 工程
def project(circuits, main="main", toolbar=True):
    """circuits: [(name, body), ...]，第一个通常就是 main。"""
    head = (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<project source="5.0.0" version="1.0">\n'
        f'  <lib desc="#Wiring" name="{WIRE}"/>\n'
        f'  <lib desc="#Gates" name="{GATE}"/>\n'
        f'  <lib desc="#I/O" name="{IO}"/>\n'
        f'  <lib desc="#Base" name="{BASE}"/>\n'
        f'  <main name="{main}"/>\n'
        "  <options/>\n"
    )
    if toolbar:
        head += _TOOLBAR
    body = ""
    for name, content in circuits:
        body += f'  <circuit name="{name}">\n    <a name="circuit" val="{name}"/>\n{content}  </circuit>\n'
    return head + body + "</project>\n"


# ------------------------------------------------------------------ 编辑已有电路
_COORD = __import__("re").compile(r"\((-?\d+),(-?\d+)\)")


def translate(body, ox, oy):
    """整体平移一段电路文本（只改 (x,y) 形式的坐标）。"""
    return _COORD.sub(lambda m: f"({int(m.group(1))+ox},{int(m.group(2))+oy})", body)


def strip_pins(body):
    """去掉所有 Pin 行，便于把子电路内联进上层。"""
    return "".join(l for l in body.splitlines(True) if 'name="Pin"' not in l)


def count(body):
    return {"comp": body.count("<comp"), "wire": body.count("<wire")}


def check(fails):
    """布线结果自检。有失败就别写文件——断头线会让 Logisim 加载时 OOM。"""
    if fails:
        raise RuntimeError(
            f"布线失败 {len(fails)} 条：{fails[:5]}\n"
            "不要写出该文件：断头导线会触发 WireRepair.doOverlaps 死循环（OOM）。"
        )
    return True
