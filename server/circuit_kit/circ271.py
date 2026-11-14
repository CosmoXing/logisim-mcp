# -*- coding: utf-8 -*-
"""Logisim 2.7.1 语义层：网表检查 + 网表仿真 + 端口几何。

与 `netlist.py` / `geometry.py` 的区别
--------------------------------------
`netlist.py`、`geometry.py` 面向 Logisim-evolution 5.0：
  * 元件库编号、端口偏移、Splitter 分支坐标、RAM 控制脚都不同；
  * 5.0 的 Pin 语义、Decoder 禁用输出、RAM 写使能判定也不同。

本模块按 **Logisim 2.7.1 实测语义** 实现：
  * Splitter（east）：分支 i 在 y - 10*fanout + 10*i；west：y + 10*(i+1)
  * 门电路：inputs 默认 5，输入在 x-50，纵向 40px 内均布（2 输入为 y±20）
  * Decoder：禁用默认输出悬空(Z)；`disabled=0` 时输出 0
  * RAM：底部 str(-110)/CS(-90)/clk(-70)/OE(-50)/clr(-30)；WE 判定为「≠0 即写」
  * Register：仅 `en == FALSE` 时禁止加载（悬空等价使能）
  * 保存时 Logisim 会省略默认属性（如 Splitter 的 fanout、Decoder 的 enable）

支持范围：Pin/Tunnel/Splitter/Constant/基本门/Comparator/Decoder/Multiplexer/
RAM/ROM/Register。Adder/Shifter/子电路等不在支持范围内，会列在 unknown_components。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def on_seg(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if x1 == x2 == x:
        return min(y1, y2) <= y <= max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) <= x <= max(x1, x2)
    return False


def pt(loc):
    x, y = loc.strip('()').split(',')
    return (int(x), int(y))


def attrs(comp):
    return {a.get('name'): a.get('val') for a in comp.findall('a')}


def attr_text(comp, name):
    for a in comp.findall('a'):
        if a.get('name') == name:
            return (a.text or '').strip()
    return ''


def width_of(a, name, default=1):
    try:
        return int(a.get(name, default))
    except (TypeError, ValueError):
        return default


def splitter_fanout(a):
    """2.7.1 保存时可能省略 fanout（推导值）；缺失时按 bit 映射推导。"""
    raw = a.get('fanout')
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            pass
    incoming = width_of(a, 'incoming')
    top = -1
    for i in range(incoming):
        b = a.get(f'bit{i}', '0')
        if b != 'none':
            try:
                top = max(top, int(b))
            except ValueError:
                pass
    return top + 1 if top >= 0 else 1


def parse_contents(text, data_width):
    """解析 ROM/RAM 的 `<a name="contents">addr/data: 12 32\\n...` 文本。"""
    mem = {}
    if not text:
        return mem
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    addr = 0
    for ln in lines:
        if ln.lower().startswith('addr/data'):
            continue
        for tok in ln.split():
            try:
                mem[addr] = int(tok, 16) & ((1 << data_width) - 1)
            except ValueError:
                pass
            addr += 1
    return mem


# --------------------------------------------------------------------------
# 端口几何（2.7.1 实测）
# --------------------------------------------------------------------------
class Port:
    def __init__(self, comp, name, p, width, direction):
        self.comp = comp
        self.name = name
        self.p = p
        self.width = width
        self.direction = direction  # in / out / io


GATE_NAMES = ('AND Gate', 'OR Gate', 'NAND Gate', 'NOR Gate', 'XOR Gate', 'XNOR Gate')


def component_body(comp):
    n = comp.get('name')
    x, y = pt(comp.get('loc'))
    a = attrs(comp)
    if n == 'Comparator':
        return (x - 40, y - 20, x, y + 20)
    if n in GATE_NAMES:
        return (x - 50, y - 20, x - 10, y + 20)
    if n == 'NOT Gate':
        return (x - 30, y - 10, x - 10, y + 10)
    if n == 'Decoder':
        sel = width_of(a, 'select')
        cnt = 1 << sel
        return (x - 20, y - 10 * (cnt + 1), x + 20, y)
    if n == 'Multiplexer':
        sel = width_of(a, 'select')
        half = (1 << sel) // 2
        return (x - 40, y - 10 * half - 10, x, y + 10 * half)
    if n in ('RAM', 'ROM'):
        return (x - 140, y - 40, x, y + 40)
    if n == 'Register':
        # 2.7.1 实测：Q(0,0) 在右边缘、D/en 在左边缘、clk/clr 在底边
        return (x - 30, y - 10, x, y + 20)
    return None


def segment_hits_body(a, b, rect):
    x1, y1, x2, y2 = rect
    (ax, ay), (bx, by) = a, b
    if ay == by:
        if not (y1 < ay < y2):
            return False
        lo, hi = min(ax, bx), max(ax, bx)
        return max(lo, x1) < min(hi, x2)
    if ax == bx:
        if not (x1 < ax < x2):
            return False
        lo, hi = min(ay, by), max(ay, by)
        return max(lo, y1) < min(hi, y2)
    return False


def component_ports(comp):
    n = comp.get('name')
    x, y = pt(comp.get('loc'))
    a = attrs(comp)
    out = []

    def add(name, px, py, w, d):
        out.append(Port(n, name, (px, py), w, d))

    if n == 'Pin':
        w = width_of(a, 'width')
        # 2.7.1：output=true 是电路输出（负载）；否则是驱动源
        d = 'in' if a.get('output') == 'true' else 'out'
        add('p', x, y, w, d)
    elif n == 'Tunnel':
        add('p', x, y, width_of(a, 'width'), 'io')
    elif n == 'Constant':
        add('out', x, y, width_of(a, 'width'), 'out')
    elif n == 'Clock':
        add('out', x, y, 1, 'out')
    elif n == 'Splitter':
        incoming = width_of(a, 'incoming')
        fanout = splitter_fanout(a)
        facing = a.get('facing', 'east')
        dx = 20 if facing != 'west' else -20
        add('bus', x, y, incoming, 'io')
        groups = defaultdict(int)
        for i in range(incoming):
            b = a.get(f'bit{i}', '0')
            if b == 'none':
                continue
            try:
                groups[int(b)] += 1
            except ValueError:
                pass
        for i in range(fanout):
            w = groups.get(i, 0)
            if w:
                py = y + 10 * (i + 1) if facing == 'west' else y + 10 * (i - fanout)
                add(f'b{i}', x + dx, py, w, 'io')
    elif n in GATE_NAMES:
        cnt = width_of(a, 'inputs', 5)
        w = width_of(a, 'width')
        step = 40 // (cnt - 1) if cnt > 1 else 0
        for i in range(cnt):
            add(f'in{i}', x - 50, y - 20 + i * step, w, 'in')
        add('out', x, y, w, 'out')
    elif n == 'NOT Gate':
        w = width_of(a, 'width')
        add('in', x - 30, y, w, 'in')
        add('out', x, y, w, 'out')
    elif n == 'Comparator':
        w = width_of(a, 'width')
        add('A', x - 40, y - 10, w, 'in')
        add('B', x - 40, y + 10, w, 'in')
        add('gt', x, y - 10, 1, 'out')
        add('eq', x, y, 1, 'out')
        add('lt', x, y + 10, 1, 'out')
    elif n == 'Multiplexer':
        sel = width_of(a, 'select')
        w = width_of(a, 'width')
        cnt = 1 << sel
        for i in range(cnt):
            add(f'in{i}', x - 40, y - 10 * (cnt // 2) + 10 * i, w, 'in')
        add('sel', x - 20, y + 10 * (cnt // 2), sel, 'in')
        add('en', x - 10, y + 10 * (cnt // 2), 1, 'in')
        add('out', x, y, w, 'out')
    elif n == 'Decoder':
        sel = width_of(a, 'select')
        cnt = 1 << sel
        for i in range(cnt):
            add(f'out{i}', x + 20, y - 10 * (cnt - i), 1, 'out')
        add('sel', x, y, sel, 'in')
        # enable 默认 true；保存时可能被省略
        if a.get('enable', 'true') == 'true':
            add('en', x - 10, y, 1, 'in')
    elif n == 'RAM':
        aw = width_of(a, 'addrWidth')
        dw = width_of(a, 'dataWidth')
        add('Q', x, y, dw, 'out')
        add('A', x - 140, y, aw, 'in')
        add('D', x - 140, y + 20, dw, 'in')
        for name, dx in [('str', -110), ('cs', -90), ('clk', -70), ('oe', -50), ('clr', -30)]:
            add(name, x + dx, y + 40, 1, 'in')
    elif n == 'ROM':
        aw = width_of(a, 'addrWidth')
        dw = width_of(a, 'dataWidth')
        add('A', x - 140, y, aw, 'in')
        add('Q', x, y, dw, 'out')
        add('cs', x - 90, y + 40, 1, 'in')
    elif n == 'Register':
        w = width_of(a, 'width')
        add('Q', x, y, w, 'out')
        add('D', x - 30, y, w, 'in')
        add('en', x - 30, y + 10, 1, 'in')
        add('clk', x - 20, y + 20, 1, 'in')
        add('clr', x - 10, y + 20, 1, 'in')
    return out


# --------------------------------------------------------------------------
# 加载与建网
# --------------------------------------------------------------------------
def load_circuit(path, name='main'):
    root = ET.parse(path).getroot()
    for c in root.findall('circuit'):
        if c.get('name') == name:
            return c
    names = [c.get('name') for c in root.findall('circuit')]
    raise SystemExit(f'circuit {name!r} not found; circuits={names}')


def list_circuits(path):
    root = ET.parse(path).getroot()
    return [c.get('name') for c in root.findall('circuit')]


class Netlist:
    """一个 2.7.1 电路的连通网络。"""

    def __init__(self, path, circuit_name='main'):
        self.circuit = load_circuit(path, circuit_name)
        self.segs = [(pt(w.get('from')), pt(w.get('to')))
                     for w in self.circuit.findall('wire')]
        self.comps = list(self.circuit.findall('comp'))
        self.uf = UF()
        for a, b in self.segs:
            self.uf.union(a, b)
        for a, b in self.segs:
            for p in (a, b):
                for c, d in self.segs:
                    if p == c or p == d:
                        continue
                    if on_seg(p, c, d):
                        self.uf.union(p, c)

        self.ports = []
        self.unknown = []
        for comp in self.comps:
            ps = component_ports(comp)
            if not ps and comp.get('name') != 'Tunnel':
                self.unknown.append(comp.get('name'))
            for port in ps:
                self.ports.append(port)
                for c, d in self.segs:
                    if on_seg(port.p, c, d):
                        self.uf.union(port.p, c)
                        break

        self.tunnel_labels = defaultdict(list)
        for comp in self.comps:
            if comp.get('name') == 'Tunnel':
                a = attrs(comp)
                self.tunnel_labels[a.get('label')].append(
                    (comp, pt(comp.get('loc')), width_of(a, 'width')))
        for _, items in self.tunnel_labels.items():
            for _, p, _ in items[1:]:
                self.uf.union(items[0][1], p)

        self.nets = defaultdict(list)
        for port in self.ports:
            self.nets[self.uf.find(port.p)].append(port)

    def tunnel_value_location(self, label):
        items = self.tunnel_labels.get(label)
        return items[0][1] if items else None


# --------------------------------------------------------------------------
# 静态检查
# --------------------------------------------------------------------------
def check(path, circuit='main'):
    nl = Netlist(path, circuit)
    circuit_el = nl.circuit
    errors = []
    warnings = []

    # 导线穿过元件体
    for a, b in nl.segs:
        for comp in nl.comps:
            body = component_body(comp)
            if body and segment_hits_body(a, b, body):
                errors.append(f'导线穿元件体: {comp.get("name")}@{comp.get("loc")} {a}->{b}')

    # Decoder/Mux 的 sel/en 必须从下方接入；Comparator 输出不能向体内走
    for comp in nl.comps:
        n = comp.get('name')
        for port in component_ports(comp):
            if not ((n in ('Decoder', 'Multiplexer') and port.name in ('sel', 'en'))
                    or (n == 'Comparator' and port.name in ('gt', 'eq', 'lt'))):
                continue
            for a, b in nl.segs:
                if not on_seg(port.p, a, b):
                    continue
                if a[1] == b[1]:
                    other = b if a == port.p else a
                    if n == 'Comparator' and other[0] < port.p[0]:
                        errors.append(
                            f'{n}@{comp.get("loc")} 的 {port.name} 输出线向元件体内走: {a}->{b}')
                    if n in ('Decoder', 'Multiplexer') and port.name in ('sel', 'en'):
                        errors.append(
                            f'{n}@{comp.get("loc")} 的 {port.name} 应从下方接入，不能横穿: {a}->{b}')
                elif a[0] == b[0]:
                    top, bot = min(a[1], b[1]), max(a[1], b[1])
                    if n in ('Decoder', 'Multiplexer') and port.name in ('sel', 'en'):
                        if bot <= port.p[1]:
                            errors.append(
                                f'{n}@{comp.get("loc")} 的 {port.name} 应从下方接入: {a}->{b}')

    # Tunnel 宽度一致性
    for label, items in nl.tunnel_labels.items():
        ws = {w for _, _, w in items}
        if len(ws) > 1:
            errors.append(f'Tunnel {label!r} 宽度不一致: {sorted(ws)}')

    # 逐网检查
    for rootp, ps in nl.nets.items():
        widths = {p.width for p in ps if p.width}
        if len(widths) > 1:
            detail = ', '.join(f'{p.comp}.{p.name}={p.width}' for p in ps)
            errors.append(f'位宽冲突 {sorted(widths)}: {detail}')
        drivers = [p for p in ps if p.direction == 'out']
        if len(drivers) > 1:
            detail = ', '.join(f'{p.comp}.{p.name}' for p in drivers)
            errors.append(f'多驱动: {detail}')

    # Splitter 虚拟驱动传播（分支由 bus 驱动）
    driver_nets = {rootp for rootp, ps in nl.nets.items()
                   if any(p.direction == 'out' for p in ps)}
    for comp in nl.comps:
        if comp.get('name') != 'Splitter':
            continue
        ps = component_ports(comp)
        bus = next((p for p in ps if p.name == 'bus'), None)
        if bus is None:
            continue
        if nl.uf.find(bus.p) in driver_nets:
            for p in ps:
                if p.name.startswith('b'):
                    driver_nets.add(nl.uf.find(p.p))

    benign_floating = {('RAM', 'cs'), ('RAM', 'oe'), ('ROM', 'cs'),
                       ('Multiplexer', 'en')}  # 2.7.1：悬空≠FALSE，等价使能

    def benign(p):
        # 门电路未接的输入按“忽略”处理（实测 2.7.1 的 5 输入门只接 2 根线仍正常）
        return (p.comp, p.name) in benign_floating or \
            (p.comp in GATE_NAMES and p.name.startswith('in'))

    for rootp, ps in nl.nets.items():
        if len(ps) == 1 and ps[0].direction == 'in':
            if not benign(ps[0]):
                warnings.append(f'未连接输入: {ps[0].comp}.{ps[0].name} @{ps[0].p}')
        if any(p.direction == 'in' for p in ps) and rootp not in driver_nets:
            if all(benign(p) for p in ps):
                continue
            warnings.append('无驱动网络: ' + ', '.join(f'{p.comp}.{p.name}' for p in ps))
    warnings = [w for w in warnings if not w.startswith('无驱动网络: Pin.')]

    return {
        'file': path,
        'circuit': circuit,
        'wires': len(nl.segs),
        'components': len(nl.comps),
        'errors': sorted(set(errors)),
        'warnings': sorted(set(warnings)),
        'unknown_components': sorted(set(nl.unknown)),
    }


def ports(path, circuit='main', component=None):
    nl = Netlist(path, circuit)
    out = []
    needle = (component or '').lower()
    for comp in nl.comps:
        name = comp.get('name')
        if needle and needle not in name.lower():
            continue
        ps = component_ports(comp)
        if not ps:
            continue
        out.append({
            'component': name,
            'loc': comp.get('loc'),
            'ports': [{'name': p.name, 'at': list(p.p), 'width': p.width,
                       'dir': p.direction} for p in ps],
        })
    return out


# --------------------------------------------------------------------------
# 网表仿真
# --------------------------------------------------------------------------
class Sim:
    def __init__(self, path, circuit_name='main'):
        self.nl = Netlist(path, circuit_name)
        self.net = {}
        self.mem = {}
        self.prev_clk = {}
        self.rom_mem = {}
        self.pin_net = {}
        self.pin_width = {}
        self.clock_loc = None

        for comp in self.nl.comps:
            n = comp.get('name')
            a = attrs(comp)
            if n == 'Pin':
                label = (a.get('label') or '').strip().lower().replace(' ', '')
                port = next(p for p in self.nl.ports
                            if p.comp == 'Pin' and p.p == pt(comp.get('loc')))
                self.pin_net[label] = self.nl.uf.find(port.p)
                self.pin_width[label] = width_of(a, 'width')
            if n == 'ROM':
                self.rom_mem[id(comp)] = parse_contents(
                    attr_text(comp, 'contents'), width_of(a, 'dataWidth'))

    # ---------- 网络读写 ----------
    def nroot(self, port):
        return self.nl.uf.find(port.p)

    def get(self, port):
        return self.net.get(self.nroot(port))

    def drive(self, port, value):
        self.net[self.nroot(port)] = value

    def set_pin(self, label, value):
        key = label.strip().lower().replace(' ', '')
        if key not in self.pin_net:
            raise KeyError(f'pin {label!r} not found; pins={sorted(self.pin_net)}')
        self.net[self.pin_net[key]] = int(value)

    def get_pin(self, label):
        key = label.strip().lower().replace(' ', '')
        return self.net.get(self.pin_net.get(key))

    def pin_labels(self):
        return sorted(self.pin_net)

    # ---------- 求值 ----------
    def settle(self, rounds=80):
        for _ in range(rounds):
            changed = False
            for comp in self.nl.comps:
                if self._eval(comp):
                    changed = True
            if not changed:
                return True
        return False

    def _eval(self, comp):
        n = comp.get('name')
        a = attrs(comp)
        if n in ('Pin', 'Tunnel'):
            return False
        if n == 'Clock':
            return False
        if n == 'Constant':
            v = int(a.get('value', '0x1'), 0) & ((1 << width_of(a, 'width')) - 1)
            root = self.nl.uf.find(pt(comp.get('loc')))
            if self.net.get(root) != v:
                self.net[root] = v
                return True
            return False
        if n == 'Splitter':
            ps = {p.name: p for p in component_ports(comp)}
            incoming = width_of(a, 'incoming')
            fanout = splitter_fanout(a)
            bus = ps['bus']
            busv = self.get(bus)
            branches = [ps[f'b{i}'] for i in range(fanout) if f'b{i}' in ps]
            mapping = []
            for i in range(incoming):
                b = a.get(f'bit{i}', '0')
                if b != 'none':
                    try:
                        mapping.append((i, int(b)))
                    except ValueError:
                        pass
            changed = False
            if busv is not None:
                for br in branches:
                    idx = int(br.name[1:])
                    bits = [i for i, f in mapping if f == idx]
                    v = 0
                    for k, i in enumerate(bits):
                        v |= ((busv >> i) & 1) << k
                    if self.get(br) != v:
                        self.drive(br, v)
                        changed = True
            else:
                vals = [self.get(br) for br in branches]
                if any(v is None for v in vals):
                    return False
                busv = 0
                for i, f in mapping:
                    br = ps.get(f'b{f}')
                    bits = [ii for ii, ff in mapping if ff == f]
                    busv |= ((self.get(br) >> bits.index(i)) & 1) << i
                if self.get(bus) != busv:
                    self.drive(bus, busv)
                    changed = True
            return changed
        if n in GATE_NAMES:
            ps = component_ports(comp)
            ins = [self.get(p) for p in ps if p.direction == 'in']
            out = [p for p in ps if p.direction == 'out'][0]
            if any(v is None for v in ins):
                return False
            if n.startswith('AND'):
                v = 1 if all(ins) else 0
            elif n.startswith('OR'):
                v = 1 if any(ins) else 0
            elif n.startswith('NAND'):
                v = 0 if all(ins) else 1
            elif n.startswith('NOR'):
                v = 0 if any(ins) else 1
            else:
                v = 0
                for x in ins:
                    v ^= x
                if n.startswith('XNOR'):
                    v ^= 1
            if self.get(out) != v:
                self.drive(out, v)
                return True
            return False
        if n == 'NOT Gate':
            ps = {p.name: p for p in component_ports(comp)}
            v = self.get(ps['in'])
            if v is None:
                return False
            v = (~v) & ((1 << ps['out'].width) - 1)
            if self.get(ps['out']) != v:
                self.drive(ps['out'], v)
                return True
            return False
        if n == 'Comparator':
            ps = {p.name: p for p in component_ports(comp)}
            va, vb = self.get(ps['A']), self.get(ps['B'])
            if va is None or vb is None:
                return False
            if a.get('mode', 'twosComplement') == 'unsigned':
                gt, eq, lt = va > vb, va == vb, va < vb
            else:
                w = ps['A'].width
                sa = va - (1 << w) if va >> (w - 1) else va
                sb = vb - (1 << w) if vb >> (w - 1) else vb
                gt, eq, lt = sa > sb, sa == sb, sa < sb
            changed = False
            for name, val in (('gt', gt), ('eq', eq), ('lt', lt)):
                if self.get(ps[name]) != int(val):
                    self.drive(ps[name], int(val))
                    changed = True
            return changed
        if n == 'Decoder':
            ps = {p.name: p for p in component_ports(comp)}
            sel = self.get(ps['sel'])
            en = self.get(ps['en']) if 'en' in ps else 1
            outs = [ps[k] for k in ps if k.startswith('out')]
            if sel is None or en is None:
                return False
            disabled_zero = a.get('disabled') == '0'
            changed = False
            for p in outs:
                idx = int(p.name[3:])
                if en == 1:
                    v = 1 if sel == idx else 0
                else:
                    v = 0 if disabled_zero else None
                if self.get(p) != v:
                    self.drive(p, v)
                    changed = True
            return changed
        if n == 'Multiplexer':
            ps = {p.name: p for p in component_ports(comp)}
            sel = self.get(ps['sel'])
            if sel is None:
                return False
            key = f'in{sel}'
            v = self.get(ps[key]) if key in ps else 0
            if v is None:
                v = 0
            if self.get(ps['out']) != v:
                self.drive(ps['out'], v)
                return True
            return False
        if n in ('RAM', 'ROM'):
            ps = {p.name: p for p in component_ports(comp)}
            key = id(comp)
            mem = self.mem.setdefault(key, {})
            addr = self.get(ps['A'])
            if addr is None:
                return False
            if n == 'ROM':
                v = mem.get(addr, self.rom_mem.get(key, {}).get(addr, 0))
                if self.get(ps['Q']) != v:
                    self.drive(ps['Q'], v)
                    return True
                return False
            clr = self.get(ps['clr'])
            clk = self.get(ps['clk'])
            cs = self.get(ps['cs']) if 'cs' in ps else 1
            oe = self.get(ps['oe']) if 'oe' in ps else 1
            # 2.7.1：引脚 != FALSE 即视为有效，悬空(None)也算有效
            cs_on = cs != 0
            oe_on = oe != 0
            if clr == 1 and mem:
                self.mem[key] = {}
                mem = self.mem[key]
            changed = False
            if not cs_on:
                if self.get(ps['Q']) is not None:
                    self.drive(ps['Q'], None)
                    return True
                return False
            if clk is not None:
                prev = self.prev_clk.get(key, 0)
                if clk == 1 and prev == 0:
                    strv = self.get(ps['str'])
                    data = self.get(ps['D'])
                    if strv != 0 and data is not None:
                        mem[addr] = data
                        changed = True
                self.prev_clk[key] = clk
            v = mem.get(addr, 0) if oe_on else None
            if self.get(ps['Q']) != v:
                self.drive(ps['Q'], v)
                changed = True
            return changed
        if n == 'Register':
            ps = {p.name: p for p in component_ports(comp)}
            key = id(comp)
            st = self.mem.setdefault(key, {'q': 0, 'clk': 0})
            if self.get(ps['clr']) == 1:
                st['q'] = 0
            clk = self.get(ps['clk'])
            if clk == 1 and st['clk'] == 0:
                en = self.get(ps['en'])
                d = self.get(ps['D'])
                if en != 0 and d is not None:  # 2.7.1：仅 FALSE 禁止
                    st['q'] = d
            st['clk'] = clk or 0
            if self.get(ps['Q']) != st['q']:
                self.drive(ps['Q'], st['q'])
                return True
            return False
        return False

    # ---------- 时钟 ----------
    def resolve_clock(self, label=None):
        if label:
            key = label.strip().lower().replace(' ', '')
            if key in self.pin_net:
                return ('pin', key)
            loc = self.nl.tunnel_value_location(label)
            if loc:
                return ('net', self.nl.uf.find(loc))
            raise KeyError(f'clock {label!r} not found')
        for key in ('clk', 'clock', 'cp', 'ck'):
            if key in self.pin_net:
                return ('pin', key)
        for comp in self.nl.comps:
            if comp.get('name') == 'Clock':
                return ('net', self.nl.uf.find(pt(comp.get('loc'))))
        raise KeyError('no clock pin/tunnel/Clock component found')

    def tick(self, clock_target):
        kind, key = clock_target
        setter = self.set_pin if kind == 'pin' else (lambda _k, v: self.net.__setitem__(key, v))
        setter(key, 0)
        self.settle()
        setter(key, 1)
        self.settle()
        setter(key, 0)
        self.settle()


def fmt_value(v, width=1):
    if v is None:
        return 'x'
    if width <= 1:
        return str(v)
    digits = max(1, (width + 3) // 4)
    return '0x' + format(v & ((1 << width) - 1), '0%dx' % digits)


def simulate(path, circuit='main', inputs=None, cycles=0, clock=None, watch=None):
    sim = Sim(path, circuit)
    for k, v in (inputs or {}).items():
        sim.set_pin(k, int(v, 0) if isinstance(v, str) else int(v))
    sim.settle()

    clock_target = sim.resolve_clock(clock)
    labels = [w for w in (watch or [])]

    def read(label):
        key = label.strip().lower().replace(' ', '')
        if key in sim.pin_net:
            return fmt_value(sim.net.get(sim.pin_net[key]), sim.pin_width.get(key, 1))
        loc = sim.nl.tunnel_value_location(label)
        if loc is not None:
            w = next((ww for _, _, ww in sim.nl.tunnel_labels[label]), 1)
            return fmt_value(sim.net.get(sim.nl.uf.find(loc)), w)
        return None

    records = []
    for i in range(max(0, int(cycles))):
        sim.tick(clock_target)
        records.append({'cycle': i + 1, 'values': {lb: read(lb) for lb in labels}})

    final = {lb: read(lb) for lb in labels}
    if not labels:
        final = {k: fmt_value(sim.net.get(net), sim.pin_width.get(k, 1))
                 for k, net in sorted(sim.pin_net.items())}
    return {
        'file': path,
        'circuit': circuit,
        'pins': sim.pin_labels(),
        'clock': clock_target[1],
        'cycles': records,
        'final': final,
        'unknown_components': sorted(set(sim.nl.unknown)),
    }
