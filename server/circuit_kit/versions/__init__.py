# -*- coding: utf-8 -*-
"""按 Logisim 版本归类的几何 / 语义实现入口。

三套几何互相不兼容，混用会出现「每修好一处、另一处又坏」：

| 版本 | 实现模块 | 关键差异 |
|---|---|---|
| 3.9 | `..geometry`（实测与 5.0 一致） | 无差异；仅 CLI 顺序不同 |
| 4.1 | `..geometry` | 门/触发器/分线器同 5.0；**子电路符号**固定 220 宽、20px 间距 |
| 5.0（evolution） | `..geometry` | 门宽 50/60/70，输入口 `x-50`…`x-70` |
| 2.7.1 / 2.16（含 Logisim-ITA） | `..circ271` | 门输入 `x-30, y±10`；Splitter `b0` 是低位组；外观矩形须内缩 |

用法：

    from circuit_kit.versions import get, parse_circ_version

    geo = get("5.0")     # -> geometry 模块
    geo = get("2.16")    # -> circ271 模块
    ver = parse_circ_version("xxx.circ")   # 从 <project source=...> 读版本

`get()` 只做**路由**，不复制代码；两个实现模块仍是唯一真源。
"""
from __future__ import annotations

import re

from .. import circ271 as v271
from .. import geometry as v50

__all__ = ["get", "parse_circ_version", "supported", "VERSIONS"]

VERSIONS = {
    # 3.9 实测与 5.0 几何完全一致（12 类元件逐项比对），直接复用同一实现
    "3.9": v50,
    "3.9.0": v50,
    "5.0": v50,
    "5.0.0": v50,
    # 4.1 的门 / 触发器 / 分线器 / 寄存器 / RAM 与 5.0 相同，只有子电路符号不同；
    # 子电路几何由 vprofile.sub_geometry 按 source 单独处理
    "4.1": v50,
    "4.1.0": v50,
    "2.7.1": v271,
    "2.7": v271,
    "2.16": v271,
    "2.16.1": v271,
    "2.16.1.0": v271,
}

_ALIAS = {
    "3.9": "3.9",
    "3": "5.0",
    "5": "5.0",
    "5.0": "5.0",
    "4": "4.1",
    "4.1": "4.1",
    "2.7": "2.7.1",
    "2.16": "2.16",
}


def supported() -> list[str]:
    """已实现的版本号（不含占位）。"""
    return ["3.9", "4.1", "5.0", "2.7.1", "2.16"]


def get(version: str):
    """按版本号取几何模块；未实现抛 NotImplementedError。"""
    key = str(version).strip()
    mod = VERSIONS.get(key)
    if mod is None and key in _ALIAS:
        mod = VERSIONS.get(_ALIAS[key])
    if mod is None:
        raise NotImplementedError(
            f"版本 {version!r} 尚未落地为代码；已支持：{supported()}。"
            f" 差异表见 docs/VERSIONS.md"
        )
    return mod


def parse_circ_version(path: str) -> str:
    """从 .circ 头部 `<project source="...">` 读出版本号。"""
    with open(path, encoding="utf-8", errors="ignore") as f:
        head = f.read(600)
    m = re.search(r'<project[^>]*\bsource="([^"]+)"', head)
    if not m:
        return ""
    return m.group(1).replace(".exe", "").replace(".jar", "").strip()


def detect(path: str) -> str:
    """版本 -> 路由键（'3.9' / '4.1' / '5.0' / '2.7.1' / '2.16' / ''）。"""
    ver = parse_circ_version(path)
    if not ver:
        return ""
    if ver.startswith("5"):
        return "5.0"
    if ver.startswith("4.1"):
        return "4.1"
    if ver.startswith("2.16"):
        return "2.16"
    if ver.startswith("2.7"):
        return "2.7.1"
    if ver.startswith("3.9"):
        return "3.9"
    return ver
