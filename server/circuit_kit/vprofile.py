"""版本档位（profile）：把各 Logisim-evolution 版本之间的几何/格式差异集中到一处。

为什么要这一层
--------------
3.9 / 5.0 的门、触发器、分线器几何基本一致，但 **4.1 的子电路符号是另一套规则**：
DefaultEvolutionAppearance 在 `circuitnamedboxfixedsize=true` 时把符号框固定成
220×20n+20，端口沿左右两边、**20px 间距**排布；而 5.0 是动态宽度、10px 间距。
另外 4.1 的库索引是 Wiring0 / Gates1 / Plexers2 / Arithmetic3 / Memory5 / I/O6 / Base9，
5.0 早期生成的工程用的是 Memory4 / I/O5 / Base8。

这一层只描述"差异"，几何/布线/生成三处共用，避免各写一份常量后互相漂移。

选择顺序
--------
1. 环境变量 `LOGISIM_PROFILE`（"4.1" / "5.0" / "3.9"）
2. `LOGISIM_JAR` / `logisim.local.json` 的文件名里出现的版本号
3. 默认 5.0（保持原有行为）
"""

from __future__ import annotations

import os
import re

# --------------------------------------------------------------------------
# 档位定义
# --------------------------------------------------------------------------
PROFILES = {
    "5.0": {
        "label": "5.0",
        "version": "5.0.0",
        "note": "子电路按 facing 分边、10px 间距、动态宽度；库索引 Memory4 / I/O5 / Base8",
        "libs": {"wire": "0", "gate": "1", "plexer": "2", "arith": "3",
                 "mem": "4", "io": "5", "base": "8"},
        "lib_decls": [("#Wiring", "0"), ("#Gates", "1"), ("#Plexers", "2"),
                      ("#Arithmetic", "3"), ("#Memory", "4"), ("#I/O", "5"),
                      ("#Base", "8")],
        "sub": "classic50",       # 5.0 公式（宽 30、间距 10）
        "named_box_fixed": False,  # 是否写 circuitnamedboxfixedsize
        "pin_attr": "type",        # 引脚输出方向写法：type=output / output=true
        "speed": True,             # -t speed 有输出
        "w": True,                 # -w 测试向量可用
    },
    "4.1": {
        "label": "4.1",
        "version": "4.1.0",
        "note": "子电路符号固定 220 宽、端口 20px 间距（DefaultEvolutionAppearance）；"
                "库索引 Memory5 / I/O6 / Base9；-t speed 无输出",
        "libs": {"wire": "0", "gate": "1", "plexer": "2", "arith": "3",
                 "mem": "5", "io": "6", "base": "9"},
        "lib_decls": [("#Wiring", "0"), ("#Gates", "1"), ("#Plexers", "2"),
                      ("#Arithmetic", "3"), ("#Memory", "5"), ("#I/O", "6"),
                      ("#Base", "9")],
        "sub": "evolution41",
        "named_box_fixed": True,
        "pin_attr": "type",
        "speed": False,
        "w": True,
    },
    "4.0": {
        "label": "4.0",
        "version": "4.0.0",
        "note": "元件/子电路几何与 5.0 经典布局相同（动态宽度、10px 间距）；"
                "库索引 Wiring0 / Gates1 / Memory2 / I/O3 / Base4；"
                "toolbar/mappings 的 <tool> 必须带 lib 属性",
        "libs": {"wire": "0", "gate": "1", "plexer": "5", "arith": "6",
                 "mem": "2", "io": "3", "base": "4"},
        "lib_decls": [("#Wiring", "0"), ("#Gates", "1"), ("#Memory", "2"),
                      ("#I/O", "3"), ("#Base", "4"), ("#Plexers", "5"),
                      ("#Arithmetic", "6")],
        "sub": "classic50",
        "named_box_fixed": False,
        "pin_attr": "type",
        "speed": False,
        "w": True,
    },
}

# 3.9 与 5.0 的生成几何一致（门 50、触发器 classic、分线器 20），
# 但写出的 source 仍保留 3.9.0，避免老版本打开时被标成未来版本。
PROFILES["3.9"] = dict(PROFILES["5.0"], label="3.9", version="3.9.0",
                       note="与 5.0 同一套几何；source 写 3.9.0")

_ALIASES = {"3.9": "3.9", "3.9.0": "3.9", "5": "5.0", "5.0": "5.0", "5.0.0": "5.0",
            "4.0": "4.0", "4.0.0": "4.0",
            "4": "4.1", "4.1": "4.1", "4.1.0": "4.1"}

_ACTIVE = None


def normalize(value) -> str:
    """把 "logisim-evolution-4.1.0-all.jar" / "4.1.0" / 4.1 归一成档位键。"""
    if value is None:
        return ""
    text = str(value)
    m = re.search(r"(\d+)\.(\d+)", text)
    if m:
        key = f"{m.group(1)}.{m.group(2)}"
    else:
        m = re.search(r"\b(\d+)\b", text)
        key = m.group(1) if m else ""
    return _ALIASES.get(key, "")


def detect(jar_path: str = "") -> str:
    """按 环境变量 > jar 文件名 > 默认 5.0 选出档位键。"""
    for cand in (os.environ.get("LOGISIM_PROFILE", ""), jar_path):
        key = normalize(cand)
        if key:
            return key
    return "5.0"


def set_active(key: str):
    """显式设定档位；key 可以是 "4.1" / "4.1.0" / jar 路径。"""
    global _ACTIVE
    norm = normalize(key)
    if norm:
        _ACTIVE = norm
    return active()


def set_from_jar(jar_path: str):
    """服务器启动时用实际 kernel jar 校准档位（环境变量优先）。"""
    return set_active(detect(jar_path))


def active_key() -> str:
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = detect(os.environ.get("LOGISIM_JAR", ""))
    return _ACTIVE


def active() -> dict:
    return PROFILES[active_key()]


def get(key: str, default=None):
    return active().get(key, default)


def lib(kind: str) -> str:
    return active()["libs"][kind]


def version_string() -> str:
    return active()["version"]


def sub_style(key: str = "") -> str:
    k = normalize(key) if key else ""
    if not k:
        k = active_key()
    return PROFILES[k]["sub"]


def is_41(key: str = "") -> bool:
    return sub_style(key) == "evolution41"


def is_40(key: str = "") -> bool:
    k = normalize(key) if key else ""
    if not k:
        k = active_key()
    return k == "4.0"


# --------------------------------------------------------------------------
# 子电路实例几何
# --------------------------------------------------------------------------
def sub_geometry(pins, key: str = ""):
    """pins: [(label, x, y, facing)] → (body, {label: (dx,dy)})，相对实例 loc。

    4.1（DefaultEvolutionAppearance，fixedSize=true）：
        width  = 220
        height = 20 * max(nIn, nOut) + 20
        anchor = (width, 10)  —— 有输出脚时锚点在右边缘第一个输出口
        西侧输入 x = -220，东侧输出 x = 0，纵向从 0 起每 20px 一个
    5.0：沿用原公式（宽 30、间距 10、动态宽度）。
    """
    west = sorted([p for p in pins if p[3] == "east"], key=lambda p: (p[2], p[1]))
    east = sorted([p for p in pins if p[3] == "west"], key=lambda p: (p[2], p[1]))
    nw, ne = len(west), len(east)

    if is_41(key):
        width, pitch = 220, 20
        maxv = max(nw, ne)
        height = maxv * pitch + 20 if maxv else 30
        ax = width if ne > 0 else 0
        ay = 10 if maxv else 0
        ports = {}
        for i, p in enumerate(west):
            ports[p[0]] = (0 - ax, 10 + i * pitch - ay)
        for j, p in enumerate(east):
            ports[p[0]] = (width - ax, 10 + j * pitch - ay)
        return (-ax, -ay, -ax + width, -ay + height), ports

    # ---- 5.0 / 3.9 ----
    import math

    def _r10(v):
        return int(math.floor(v / 10.0 + 0.5)) * 10

    def _dim(mx, others):
        if mx < 3:
            return 30
        return 10 * mx if others == 0 else 10 * mx + 10

    def _offs(n, opp, max_others):
        mx = max(n, opp)
        if mx <= 1:
            base = 15 if max_others == 0 else 10
        elif mx == 2:
            base = 10
        else:
            base = 5 if max_others == 0 else 10
        return base + 10 * ((mx - n) // 2)

    mh = max(nw, ne)
    oe, ow = _offs(ne, nw, 0), _offs(nw, ne, 0)
    width, height = _dim(0, mh), _dim(mh, 0)
    ax = width if ne > 0 else 0
    ay = oe if ne > 0 else 0
    rx, ry = _r10(50 + ax), _r10(50 + ay)
    ports = {}
    for i, p in enumerate(west):
        ports[p[0]] = (rx - (rx + ax), ry + ow + 10 * i - (ry + ay))
    for j, p in enumerate(east):
        ports[p[0]] = (rx + width - (rx + ax), ry + oe + 10 * j - (ry + ay))
    return (-ax, -ay, -ax + width, -ay + height), ports


def sub_pitch(key: str = "") -> int:
    return 20 if is_41(key) else 10


def sub_width(key: str = "") -> int:
    return 220 if is_41(key) else 30
