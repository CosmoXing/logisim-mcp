#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 examples/ 下的示例电路（用插件自己的 circ_build 能力）。

用法：
    python examples/generate.py          # 重新生成全部示例
    python examples/generate.py --check  # 只体检已有示例，不重新生成
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))

from circuit_kit import audit, builder, netlist  # noqa: E402

OUT = HERE


def and2(path):
    """最小冒烟电路：2 输入与门。"""
    return {"file": path, "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
                 {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "AND"}],
        "nets": [{"name": "a", "connect": ["pin:a", "g1.a"]},
                 {"name": "b", "connect": ["pin:b", "g1.b"]},
                 {"name": "y", "connect": ["g1.out", "pin:y"]}],
    }]}


def half_adder(path):
    """半加器：XOR 出和，AND 出进位；结果接十六进制数码管。"""
    return {"file": path, "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
                 {"label": "s", "dir": "out"}],
        "components": [
            {"id": "x1", "type": "XOR"},
            {"id": "a1", "type": "AND"},
            {"id": "sp", "type": "SPLITTER4"},
            {"id": "d1", "type": "DISPLAY"},
            {"id": "g2", "type": "GROUND"},
            {"id": "g3", "type": "GROUND"},
        ],
        "nets": [
            {"name": "a", "connect": ["pin:a", "x1.a", "a1.a"]},
            {"name": "b", "connect": ["pin:b", "x1.b", "a1.b"]},
            {"name": "sum", "connect": ["x1.out", "pin:s", "sp.b0"]},
            {"name": "carry", "connect": ["a1.out", "sp.b1"]},
            {"name": "lo2", "connect": ["g2.p", "sp.b2"]},
            {"name": "lo3", "connect": ["g3.p", "sp.b3"]},
            {"name": "bus", "connect": ["sp.in", "d1.p"]},
        ],
    }]}


def ripple2(path):
    """两位行波计数器：~Q 接回 D，Q0 当时钟驱动第二级。"""
    return {"file": path, "circuits": [{
        "name": "main",
        "pins": [{"label": "cp", "dir": "in"},
                 {"label": "q0", "dir": "out"}, {"label": "q1", "dir": "out"}],
        "components": [{"id": "f0", "type": "DFF"}, {"id": "f1", "type": "DFF"}],
        "nets": [
            {"name": "cp", "connect": ["pin:cp", "f0.CLK"]},
            {"name": "n0", "connect": ["f0.NQ", "f0.D"]},
            {"name": "q0", "connect": ["f0.Q", "pin:q0", "f1.CLK"]},
            {"name": "n1", "connect": ["f1.NQ", "f1.D"]},
            {"name": "q1", "connect": ["f1.Q", "pin:q1"]},
        ],
    }]}


EXAMPLES = [
    ("and2.circ", and2, {"a": 0, "b": 0}, None),
    ("half_adder.circ", half_adder, {"a": 0, "b": 0}, None),
    ("ripple2.circ", ripple2, {}, 4),
]


def build_all():
    for name, fn, inputs, cycles in EXAMPLES:
        path = os.path.join(OUT, name)
        builder.build(fn(path))
        rep = audit.audit(path)
        circuits, top = netlist.parse(path)
        sim = netlist.Sim(circuits, top)
        snaps = sim.run(inputs, cycles or 0)
        tail = snaps[-1]
        brief = ", ".join(f"{k}={''.join(str(x) for x in reversed(v)) if isinstance(v, tuple) and len(v) > 1 else v}"
                          for k, v in tail.items())
        print(f"{name:18s} 体检={rep['verdict']:3s} 末态 {brief}")


def check_all():
    bad = 0
    for name, _, _, _ in EXAMPLES:
        path = os.path.join(OUT, name)
        if not os.path.isfile(path):
            print(f"{name:18s} 缺失")
            bad += 1
            continue
        rep = audit.audit(path)
        print(f"{name:18s} 体检={rep['verdict']}")
        if rep["verdict"] != "ok":
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check_all())
    build_all()
