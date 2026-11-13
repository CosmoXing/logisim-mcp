#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logisim-mcp — 把本机 Logisim-evolution 3.9.0 接到 MCP 的 stdio 桥接服务。

设计要点
--------
Logisim-evolution 是纯 Java Swing 桌面程序，本身没有任何 MCP / 网络接口，
所以 MCP 不能"装进 Logisim"，只能在外部做一层协议转换：

    MCP Client  <--JSON-RPC/stdio-->  本文件  <--subprocess/CLI+XML-->  Logisim 3.9.0 内核

这样做的好处是零侵入：不需要改 Logisim、不需要插件、不需要开端口，
Logisim 只被当成一个无头计算器（-t table / -t stats / -n）和一个 XML 文件格式来用。

已验证的 Logisim 3.9.0 无头能力（本机实测）：
  java -jar logisim-evolution-3.9.0-all.jar -t table  x.circ   # 真值表
  java -jar logisim-evolution-3.9.0-all.jar -t stats  x.circ   # 元件统计
  java -jar logisim-evolution-3.9.0-all.jar -t speed  x.circ   # 仿真速度
  java -jar logisim-evolution-3.9.0-all.jar -n a.circ b.circ   # 旧格式转新格式
  java -jar logisim-evolution-3.9.0-all.jar -t tty    x.circ   # 需要电路里有 TTY 组件

.circ 格式要点（v5.0.0 源码 + 实测）：
  * Pin 组件：<a name="output" val="true"/> = 输出引脚；没有 output 属性 = 输入引脚
  * 门电路 loc 就是【输出端口】坐标；输入端口 x = loc.x - (size + bonus + 反相圈*10)
    默认 size=50 → 与门/或门 -50，异或 -60，与非/或非/同或 -60；输出口 (0,0)
  * 触发器 classic：D(-40,+20) CLK(-40,0) Q(0,0) ~Q(0,+20) R(-10,+30) S(-30,+30)
  * 子电路实例端口按 facing 分边、10px 间距，锚点落在东边第一个口
  * 两条导线十字交叉不会连通；端点落在导线上才会连通（布线时按这个规则避让）
  * -w 测试向量每行都从初始状态重新求值，不能验证多拍时序，只能验组合逻辑

新增能力层见 circuit_kit/：几何查询、静态体检、网表仿真、声明式生成、经验库。
依赖：Python 3.8+，无第三方库；外部依赖只有 java（PATH 中）和 logisim-evolution-*-all.jar。
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from circuit_kit import audit as kit_audit  # noqa: E402
from circuit_kit import appearance as kit_app  # noqa: E402
from circuit_kit import builder as kit_builder  # noqa: E402
from circuit_kit import geometry as kit_geo  # noqa: E402
from circuit_kit import knowledge as kit_kb  # noqa: E402
from circuit_kit import logisim_bridge as kit_bridge  # noqa: E402
from circuit_kit import netlist as kit_net  # noqa: E402

SERVER_NAME = "logisim"


def _esc(value):
    """XML 属性转义（标签/引脚名里可能有 & < > " '）。"""
    return _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def _plugin_version(default="1.2.0"):
    """作为插件运行时，版本号取自 .codebuddy-plugin/plugin.json；单文件运行时用默认值。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in ("../.codebuddy-plugin/plugin.json", ".codebuddy-plugin/plugin.json"):
        cand = os.path.normpath(os.path.join(here, rel))
        if os.path.isfile(cand):
            try:
                with open(cand, encoding="utf-8") as fh:
                    return json.load(fh).get("version") or default
            except (OSError, ValueError):
                break
    return default


SERVER_VERSION = _plugin_version()
PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOLS = ("2024-11-05",)
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOGISIM_HOME_HINT = os.environ.get("LOGISIM_HOME", "")


# --------------------------------------------------------------------------
# 环境探测
# --------------------------------------------------------------------------
def find_jar() -> str:
    """定位 logisim-evolution-*-all.jar"""
    cand = os.environ.get("LOGISIM_JAR", "").strip()
    if cand and os.path.isfile(cand):
        return cand
    cand = str(_local_config().get("jar", "")).strip()
    if cand and os.path.isfile(cand):
        return cand
    for jar in find_all_jars():
        return jar
    return ""


def _local_config():
    """可选的本机配置：<plugin>/logisim.local.json（已在 .gitignore 里排除）。

    形如 {"jar": "D:/tools/logisim-evolution-5.0.0-all.jar"}。
    这样仓库本身不含任何机器相关路径，使用者也不必每次导出环境变量。
    """
    path = os.path.join(PLUGIN_ROOT, "logisim.local.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def find_all_jars():
    """按优先级列出本机可用的 logisim 内核 jar（版本高的在前）。

    顺序：LOGISIM_JAR > 本地配置 > 插件 runtime/ > 插件数据目录 > 系统安装位置 > 当前目录。
    """
    local_cfg = _local_config().get("jar", "")
    prog = os.environ.get("ProgramFiles", r"C://Program Files")
    progx = os.environ.get("ProgramFiles(x86)", r"C://Program Files (x86)")
    local_app = os.environ.get("LOCALAPPDATA", "")
    data_dir = os.environ.get("CODEBUDDY_PLUGIN_DATA", "").strip()
    home = os.path.expanduser("~")

    roots = [
        LOGISIM_HOME_HINT,
        os.path.dirname(local_cfg) if local_cfg else "",
        os.path.join(PLUGIN_ROOT, "runtime"),
        os.path.join(data_dir, "runtime") if data_dir else "",
        os.path.join(prog, "logisim-evolution", "app"),
        os.path.join(progx, "logisim-evolution", "app"),
        os.path.join(local_app, "Programs", "logisim-evolution", "app"),
        os.path.join(home, ".logisim"),
        os.path.join(home, "logisim"),
        os.getcwd(),
    ]
    seen, out = set(), []
    if local_cfg and os.path.isfile(local_cfg):
        real = os.path.abspath(local_cfg)
        seen.add(real)
        out.append(real)
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for pattern in ("logisim-evolution-*-all.jar", os.path.join("app", "logisim-evolution-*-all.jar")):
            for hit in glob.glob(os.path.join(root, pattern)):
                real = os.path.abspath(hit)
                if real not in seen:
                    seen.add(real)
                    out.append(real)

    def ver_key(p):
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", os.path.basename(p))
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    return sorted(out, key=ver_key, reverse=True)


def find_java() -> str:
    for exe in ("java", "java.exe"):
        p = shutil.which(exe)
        if p:
            return p
    cands = []
    jh = os.environ.get("JAVA_HOME", "").strip()
    if jh:
        cands += [os.path.join(jh, "bin", "java.exe"), os.path.join(jh, "bin", "java")]
    prog = os.environ.get("ProgramFiles", r"C://Program Files")
    for vendor in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu", "BellSoft", "Amazon Corretto"):
        base = os.path.join(prog, vendor)
        if os.path.isdir(base):
            for name in sorted(os.listdir(base), reverse=True):
                cands += [os.path.join(base, name, "bin", "java.exe"),
                          os.path.join(base, name, "bin", "java")]
    # 插件自带 JRE（<plugin>/runtime/jre/bin/java）
    cands += [os.path.join(PLUGIN_ROOT, "runtime", "jre", "bin", "java.exe"),
              os.path.join(PLUGIN_ROOT, "runtime", "jre", "bin", "java")]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return "java"


def find_launcher() -> str:
    """jpackage 启动器（带 GUI），用于 Open GUI。可用 logisim.local.json 的 launcher 指定。"""
    prog = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates = [
        str(_local_config().get("launcher", "")),
        os.path.join(prog, "logisim-evolution", "Logisim-evolution.exe"),
        os.path.join(prog, "logisim-evolution", "logisim-evolution.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return ""


JAVA = find_java()
JAR = find_jar()


def _decode(raw):
    """Logisim 输出可能是 UTF-8 也可能是系统本地编码（GBK），逐个回退。"""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    return str(raw)


def run_logisim(args, timeout=180, headless=True):
    """调用 Logisim 命令行，返回 (ok, stdout_text)

    headless=False 用于 5.0 的 -w 测试向量：那条路径内部会 new Frame，强制 headless 会抛
    HeadlessException，所以必须借真实显示环境（本机是桌面会话，跑完即退出，不会弹窗阻塞）。
    """
    if not JAR:
        return False, "未找到 logisim-evolution-*-all.jar，请设置环境变量 LOGISIM_JAR"
    cmd = [
        JAVA,
        "-Dstdout.encoding=UTF-8",
        "-Dstderr.encoding=UTF-8",
    ]
    if headless:
        cmd.append("-Djava.awt.headless=true")
    cmd += ["-jar", JAR, *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False, f"Logisim 执行超时（{timeout}s）"
    except FileNotFoundError:
        return False, f"无法启动 java：{JAVA}"
    out = _decode(proc.stdout or b"")
    err = _decode(proc.stderr or b"")
    # Logisim 在 Java 24+ 上会打 native-access 警告，过滤掉
    noise = [ln for ln in (out + "\n" + err).splitlines() if not ln.startswith("WARNING")]
    text = "\n".join(noise).strip()
    return proc.returncode == 0, text


def version_text() -> str:
    ok, txt = run_logisim(["-v"], timeout=60)
    first = txt.splitlines()[0] if txt else ""
    m = re.search(r"v?(\d+\.\d+\.\d+)", first)
    return m.group(1) if m else (first or "unknown")


# --------------------------------------------------------------------------
# .circ 解析
# --------------------------------------------------------------------------
LIB_NAMES = {
    "0": "Wiring(引脚/导线)",
    "1": "Gates(逻辑门)",
    "2": "Plexers(多路选择)",
    "3": "Arithmetic(算术)",
    "4": "Memory(存储)",
    "5": "I/O",
    "6": "TTL",
}


def parse_circuit(path: str):
    """把 .circ 解析成结构化的引脚 / 元件 / 导线信息"""
    tree = ET.parse(path)
    root = tree.getroot()
    circuits = []
    for circ in root.findall("circuit"):
        name = circ.get("name", "?")
        pins, comps = [], []
        for comp in circ.findall("comp"):
            attrs = {a.get("name"): a.get("val") for a in comp.findall("a")}
            loc = comp.get("loc", "")
            if comp.get("name") == "Pin":
                is_out = (str(attrs.get("output", "false")).lower() == "true"
                          or str(attrs.get("type", "")).lower() == "output")
                pins.append(
                    {
                        "label": attrs.get("label") or "(未命名)",
                        "direction": "输出(out)" if is_out else "输入(in)",
                        "width": attrs.get("width", "1"),
                        "loc": loc,
                    }
                )
            else:
                comps.append(
                    {
                        "name": comp.get("name"),
                        "lib": LIB_NAMES.get(comp.get("lib", ""), comp.get("lib")),
                        "loc": loc,
                        "attrs": {k: v for k, v in attrs.items() if k in ("inputs", "label", "width")},
                    }
                )
        wires = circ.findall("wire")
        circuits.append({"name": name, "pins": pins, "components": comps, "wire_count": len(wires)})
    return {"project_source": root.get("source", "?"), "circuits": circuits}


def dump_summary(info, path):
    lines = [f"文件: {path}", f"写入版本: {info['project_source']}"]
    for c in info["circuits"]:
        lines.append("")
        lines.append(f"[电路] {c['name']}  引脚 {len(c['pins'])} / 元件 {len(c['components'])} / 导线段 {c['wire_count']}")
        if c["pins"]:
            lines.append("  引脚:")
            for p in c["pins"]:
                lines.append(f"    - {p['label']:<10} {p['direction']:<12} 位宽 {p['width']}")
        if c["components"]:
            lines.append("  元件:")
            for comp in c["components"]:
                extra = ", ".join(f"{k}={v}" for k, v in comp["attrs"].items()) or "-"
                lines.append(f"    - {comp['name']:<12} @{comp['loc']:<12} {extra}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 真值表
# --------------------------------------------------------------------------
def truth_table(path, timeout=180, max_rows=4096):
    ok, txt = run_logisim(["-t", "table", path], timeout=timeout)
    if not ok:
        return None, txt
    rows = [ln.split() for ln in txt.splitlines() if ln.strip()]
    if not rows:
        return None, "Logisim 没有返回真值表（电路可能没有引脚）"
    total = len(rows) - 1
    if max_rows and total > max_rows:
        head = rows[0]
        marker = ["…"] + [""] * (len(head) - 1)
        rows = [head] + rows[1:max_rows + 1] + [marker]
        txt += f"\n[已截断：共 {total} 行，仅显示前 {max_rows} 行]"
    return rows, txt


def input_pin_count(path):
    info = parse_circuit(path)
    circs = info["circuits"]
    target = next((c for c in circs if c["name"] == "main"), circs[0] if circs else None)
    if not target:
        return 0
    return sum(1 for p in target["pins"] if p["direction"].startswith("输入"))


WIDTH_SUFFIX = re.compile(r"\[\d+\]$")


def base_name(header):
    """5.0.0 起表头会带位宽后缀（a[4]），这里统一还原成信号名用于比对"""
    return WIDTH_SUFFIX.sub("", header)


def fmt_table(rows):
    widths = [max(len(r[i]) for r in rows if i < len(r)) for i in range(max(len(r) for r in rows))]
    out = []
    for idx, r in enumerate(rows):
        out.append("  ".join((c or "").ljust(widths[i]) for i, c in enumerate(r)).rstrip())
        if idx == 0:
            out.append("  ".join("-" * w for w in widths))
    return "\n".join(out)


def verify_table(file_path, vectors):
    """vectors: [{"in": {"a":0,...}, "out": {"y":1}}] 或 [{"a":0,"b":1,"y":0}, ...]

    表头按信号名比对，位宽后缀（5.0.0 的 a[4]）会被忽略，所以 3.9 / 4.x / 5.x 都能用。
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return False, f"文件不存在: {file_path}"
    n = input_pin_count(file_path)
    if n > 16:
        return False, (f"主电路有 {n} 个输入引脚，真值表会有 2^{n} = {2 ** n} 行，已拒绝执行；"
                       f"请输入更少的激励组合，或先用 circuit_truth_table 抽样核对")
    rows, raw = truth_table(file_path, max_rows=0)
    if rows is None:
        return False, raw
    header = rows[0]
    names = [base_name(h) for h in header]
    table_rows = {tuple(r) for r in rows[1:]}
    lines, passed, failed = [], 0, 0
    for vec in vectors:
        flat = {}
        for k, v in vec.items():
            if k in ("in", "out") and isinstance(v, dict):
                flat.update(v)
            else:
                flat[k] = v
        missing = [n for n in names if n not in flat]
        if missing:
            return False, f"期望值里缺少信号 {missing}"
        key = tuple(str(flat[n]) for n in names)
        if key in table_rows:
            passed += 1
        else:
            failed += 1
            lines.append(f"  ✗ 期望 {dict(zip(names, key))} 不在真值表中")
    body = fmt_table(rows)
    summary = f"用例 {len(vectors)}：通过 {passed}，失败 {failed}"
    detail = "\n".join(lines) if lines else "  全部用例命中"
    return failed == 0, f"{summary}\n{detail}\n\n实际真值表:\n{body}"


# --------------------------------------------------------------------------
# 原生测试向量（5.0+）
# --------------------------------------------------------------------------
def run_test_vector(file_path, circuit_name, vectors):
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return False, f"文件不存在: {file_path}"
    ver = version_text()
    m = re.match(r"(\d+)", ver or "")
    major = int(m.group(1)) if m else 0
    if major and major < 5:
        return False, (
            f"当前内核 {ver} 不支持测试向量模式：-w 在 5.0 起才按「<电路名> <向量文件> <电路文件>」解析。\n"
            "改法：用 circuit_verify（真值表比对），或把 LOGISIM_JAR 指向 5.0+ 的 jar。"
        )
    info = parse_circuit(file_path)
    circ = next((c for c in info["circuits"] if c["name"] == circuit_name), None)
    if circ is None:
        return False, f"文件里没有名为 {circuit_name} 的电路，可选: {[c['name'] for c in info['circuits']]}"
    names = [p["label"] for p in circ["pins"]]
    if not names:
        return False, "该电路没有引脚"
    widths = {p["label"]: int(p.get("width") or 1) for p in circ["pins"]}

    def fmt_value(n, v):
        """多位引脚必须写成 0x 十六进制，否则 Logisim 报 Unexpected character。"""
        if isinstance(v, str):
            return v
        w = widths.get(n, 1)
        return f"0x{int(v):x}" if w > 1 else str(int(v))

    lines = [" ".join(names)]
    for i, vec in enumerate(vectors, 1):
        flat = {}
        for k, v in vec.items():
            if k in ("in", "out") and isinstance(v, dict):
                flat.update(v)
            else:
                flat[k] = v
        missing = [n for n in names if n not in flat]
        if missing:
            return False, f"第 {i} 条向量缺少信号 {missing}（电路引脚: {names}）"
        lines.append(" ".join(fmt_value(n, flat[n]) for n in names))

    fd, vec_path = tempfile.mkstemp(prefix="lse_", suffix=".vec")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        _, out = run_logisim(["-w", circuit_name, vec_path, file_path], timeout=120, headless=False)
        clean = "\n".join(ln for ln in out.splitlines() if ln.strip())
        failed_m = re.search(r"(?:失败|Failed?)\s*[:：]?\s*(\d+)", clean, re.I)
        passed_m = re.search(r"(?:通过|Passed?)\s*[:：]?\s*(\d+)", clean, re.I)
        if failed_m and passed_m:
            failed, passed = int(failed_m.group(1)), int(passed_m.group(1))
            return failed == 0, f"通过 {passed} / 失败 {failed}\n\n{clean}"
        return False, f"没拿到通过/失败统计，内核原始输出:\n{clean}"
    finally:
        try:
            os.remove(vec_path)
        except OSError:
            pass



# --------------------------------------------------------------------------
# 电路生成
# --------------------------------------------------------------------------
GATE_NAMES = {
    "AND": "AND Gate",
    "OR": "OR Gate",
    "NAND": "NAND Gate",
    "NOR": "NOR Gate",
    "XOR": "XOR Gate",
    "XNOR": "XNOR Gate",
    "NOT": "NOT Gate",
}
MAX_GATE_INPUTS = 3  # 3.9.0 默认 Narrow 尺寸下已验证：2 输入 y±20，3 输入 y-20/0/+20


def gate_input_offsets(n):
    if n == 1:
        return [0]
    if n == 2:
        return [-20, 20]
    if n == 3:
        return [-20, 0, 20]
    raise ValueError(f"暂只支持 1~3 个输入的门，收到 {n}")


def build_circuit(spec):
    """从网表 JSON 生成 .circ 文本"""
    inputs = spec.get("inputs") or []
    gates = spec.get("gates") or []
    outputs = spec.get("outputs") or []
    if not inputs:
        raise ValueError("spec.inputs 不能为空")

    gl = {g["id"]: g for g in gates}
    for g in gates:
        g["_type"] = str(g.get("type", "AND")).upper()
        if g["_type"] not in GATE_NAMES:
            raise ValueError(f"不支持的门类型 {g['_type']}，可选 {list(GATE_NAMES)}")
        g["_in"] = [str(x) for x in g.get("inputs", [])]
        if not 1 <= len(g["_in"]) <= MAX_GATE_INPUTS:
            raise ValueError(f"门 {g['id']} 的输入数必须在 1~{MAX_GATE_INPUTS}")

    # 拓扑深度决定列，处理循环依赖
    depth_cache = {}

    def depth(gid, stack=()):
        if gid in depth_cache:
            return depth_cache[gid]
        if gid in stack:
            raise ValueError(f"电路存在环路，涉及门 {gid}")
        if gid not in gl:
            return 0
        d = 1 + max(depth(s, stack + (gid,)) for s in gl[gid]["_in"]) if gl[gid]["_in"] else 1
        depth_cache[gid] = d
        return d

    for g in gates:
        g["_depth"] = depth(g["id"])

    xs = lambda d: 60 + 160 * d

    # y 排布：输入按 60 间隔，门按列内 100 间隔
    ymap = {}
    for i, name in enumerate(inputs):
        ymap[str(name)] = 100 + i * 60
    groups = {}
    for g in gates:
        groups.setdefault(g["_depth"], []).append(g)
    for d, group in groups.items():
        for i, g in enumerate(group):
            g["_y"] = 120 + i * 100
            ymap[g["id"]] = g["_y"]

    max_depth = max([g["_depth"] for g in gates], default=0)
    out_x = xs(max_depth + 1) + 40
    out_y = {}
    for i, o in enumerate(outputs):
        out_y[str(o["name"])] = 30 + i * 40  # 输出脚避开门的 y 网格，防止两点叠在一起

    comps, wires = [], []

    def wire(x1, y1, x2, y2):
        if x1 == x2 and y1 == y2:
            return
        wires.append(f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>')

    def tunnel(x, y, label, facing="east"):
        comps.append(
            f'    <comp lib="0" loc="({x},{y})" name="Tunnel">'
            f'<a name="facing" val="{facing}"/><a name="label" val="{_esc(label)}"/></comp>'
        )

    # 连接全部走命名隧道（Tunnel 按标签互通），彻底绕开布线几何陷阱：
    # 只需要极短的直线段，不需要计算拐弯避让，生成结果稳定可复现。
    for name in inputs:
        py = ymap[str(name)]
        comps.append(
            f'    <comp lib="0" loc="(40,{py})" name="Pin">'
            f'<a name="facing" val="east"/><a name="label" val="{_esc(name)}"/></comp>'
        )
        tunnel(90, py, str(name))
        wire(40, py, 90, py)

    for g in gates:
        gx, gy = xs(g["_depth"]), g["_y"]
        n = len(g["_in"])
        ins = f'<a name="inputs" val="{n}"/>' if n > 1 else ""
        comps.append(f'    <comp lib="1" loc="({gx},{gy})" name="{GATE_NAMES[g["_type"]]}">{ins}</comp>')
        tunnel(gx + 50, gy, g["id"])
        wire(gx, gy, gx + 50, gy)
        for idx, src in enumerate(g["_in"]):
            if src not in [str(x) for x in inputs] and src not in gl:
                raise ValueError(f"门 {g['id']} 引用了不存在的信号 {src}")
            py = gy + gate_input_offsets(n)[idx]
            tunnel(gx - 80, py, src, facing="west")
            # 终点取 gx-20：门宽 30 或 40 都会正好穿过输入端口
            wire(gx - 80, py, gx - 20, py)

    for o in outputs:
        src = str(o["from"])
        if src not in gl:
            raise ValueError(f"输出 {o['name']} 引用了不存在的信号 {src}")
        oy = out_y[str(o["name"])]
        comps.append(
            f'    <comp lib="0" loc="({out_x},{oy})" name="Pin">'
            f'<a name="facing" val="west"/><a name="output" val="true"/>'
            f'<a name="label" val="{_esc(o["name"])}"/></comp>'
        )
        tunnel(out_x - 60, oy, src)
        wire(out_x - 60, oy, out_x, oy)

    cname = spec.get("circuit_name", "main")
    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<project source="3.9.0" version="1.0">',
            '  <lib desc="#Wiring" name="0"/>',
            '  <lib desc="#Gates" name="1"/>',
            f'  <main name="{_esc(cname)}"/>',
            "  <options/>",
            "  <mappings/>",
            f'  <circuit name="{_esc(cname)}">',
            f'    <a name="circuit" val="{_esc(cname)}"/>',
            *comps,
            *wires,
            "  </circuit>",
            "</project>",
            "",
        ]
    )
    return body


# --------------------------------------------------------------------------
# MCP 工具定义
# --------------------------------------------------------------------------
TOOLS = [
    {
        "name": "logisim_info",
        "description": "探测本机 Logisim-evolution 版本、jar 路径、Java 运行时，以及可用的无头能力。接入后先调这个确认环境。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "circuit_summary",
        "description": "解析 .circ 文件（XML），列出所有电路、引脚（名称/输入输出/位宽）、元件与导线数量。用于在仿真前了解电路接口。",
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string", "description": ".circ 文件绝对路径"}},
            "required": ["file"],
        },
    },
    {
        "name": "circuit_truth_table",
        "description": (
            "调用 Logisim 无头模式仿真，输出电路真值表。0/1 为确定值，U 为未知，E 为浮空/冲突（通常是漏接线）。"
            "行数默认截断到 4096 行（max_rows 可调），输入超过 16 个会直接拒绝，避免指数爆炸。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": ".circ 文件绝对路径"},
                "timeout": {"type": "integer", "description": "超时秒数，默认 180"},
                "max_rows": {"type": "integer", "description": "真值表最多显示多少行，默认 4096"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "circuit_verify",
        "description": "把电路真值表与期望向量逐条比对，返回通过/失败明细。适合验证 AI 自己生成或修改的电路。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "vectors": {
                    "type": "array",
                    "description": '期望用例，如 [{"a":0,"b":1,"y":0}] 或 [{"in":{"a":0,"b":1},"out":{"y":0}}]',
                    "items": {"type": "object"},
                },
            },
            "required": ["file", "vectors"],
        },
    },
    {
        "name": "circuit_test_vector",
        "description": (
            "用 Logisim 5.0+ 的原生测试向量引擎跑用例（-w），返回通过/失败计数与失败明细。"
            "注意：实测 -w 每一行都从初始状态重新求值，因此**只能验证组合逻辑**；"
            "时序电路请用 circ_sim（网表仿真）。3.9 会直接报版本不支持。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "circuit_name": {"type": "string", "description": "电路名，默认 main"},
                "vectors": {
                    "type": "array",
                    "description": '用例列表，如 [{"a":0,"b":1,"s":1,"cout":0}]',
                    "items": {"type": "object"},
                },
            },
            "required": ["file", "vectors"],
        },
    },
    {
        "name": "circuit_stats",
        "description": "调用 Logisim 统计电路元件（引脚/门/导线等）数量，用于快速评估复杂度。",
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"],
        },
    },
    {
        "name": "circuit_build",
        "description": (
            "按网表生成可被 Logisim 打开的 .circ 文件（自动布局布线）。"
            "spec 示例：{\"file\":\"D:/x.circ\",\"inputs\":[\"a\",\"b\"],"
            "\"gates\":[{\"id\":\"g1\",\"type\":\"XOR\",\"inputs\":[\"a\",\"b\"]}],"
            "\"outputs\":[{\"name\":\"y\",\"from\":\"g1\"}]}；门类型支持 AND/OR/NAND/NOR/XOR/XNOR/NOT，每门 1~3 输入。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "object", "description": "网表定义，含 file/inputs/gates/outputs"}},
            "required": ["spec"],
        },
    },
    {
        "name": "circuit_open_gui",
        "description": "用 Logisim 图形界面打开电路（供人工编辑）。注意：GUI 打开后本工具立即返回，不会阻塞。",
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"],
        },
    },
    {
        "name": "circ_geometry",
        "description": (
            "查询元件真实端口偏移与包围盒（v5.0 probe_component 实测，数据源 knowledge.json）。"
            "component 支持 gate/and[2]/or/not/nand/xor/xnor、dff/tff、splitter[4][west]、"
            "mux[4|4:1]、decoder[3]、register[32]、comparator[3]、pin/constant/tunnel/clock/led/ground/sub；"
            "留空返回全表。select 表示选择位宽（n 位 → 2^n 路），width 表示数据位宽。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "component": {"type": "string", "description": "元件名，可省略"},
                "select": {"type": "integer", "description": "mux/decoder 的选择位宽（可选）"},
                "width": {"type": "integer", "description": "register/comparator/mux 的数据位宽（可选）"},
            },
        },
    },
    {
        "name": "circ_probe",
        "description": (
            "用 Logisim 自身的 Java 桥探测任意元件的真实几何：包围盒、端口坐标/位宽、属性表。"
            "component 留空则列出所有已加载库与元件名。首次调用会打开 Logisim GUI 会话（可复用）。"
            "circ_geometry 只覆盖常用元件，TTL/算术库等冷门元件用这个。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": ".circ 文件绝对路径（用于加载库）"},
                "component": {"type": "string", "description": "元件名，如 Register/Comparator；留空列库"},
                "lib": {"type": "string", "description": "库名/显示名（可选，重名时用）"},
                "attrs": {"type": "object", "description": "属性覆盖，如 {\"select\":\"3\",\"width\":\"32\"}"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "circ_audit",
        "description": (
            "静态连接体检：解析 .circ 重建网表（支持寄存器/多路选择器/译码器/比较器），报告"
            "悬空网络、多驱动冲突、孤立端口、位宽冲突、10px 断口、元件体重叠。"
            "遇到不认识的元件时给出部分结果并标 partial，不再当作成功。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string", "description": ".circ 文件绝对路径"}},
            "required": ["file"],
        },
    },
    {
        "name": "circ_sim",
        "description": (
            "网表级时序仿真（可多拍）。读入 .circ 重建网表后按拍推进：每拍先给 cp 一个完整脉冲，"
            "再读所有引脚/数码管/LED。用于验证计数器等时序电路（Logisim 的 -w 每行会重置，不可用）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "inputs": {"type": "object", "description": '输入引脚取值，如 {"EN":1}'},
                "cycles": {"type": "integer", "description": "时钟脉冲数，默认 0"},
                "clock": {"type": "string",
                          "description": "时钟信号名；留空时自动识别 Clock 组件或名为 cp/clk/clock/ck 的引脚"},
                "watch": {"type": "array", "items": {"type": "string"},
                          "description": "只看这些信号：引脚名、数码管 disp:<标签>、LED 用 led；留空则全给"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "circ_build",
        "description": (
            "声明式生成多电路 .circ（自动布局 + 迷宫布线，不使用隧道）。"
            "spec 示例：{\"file\":\"D:/x.circ\",\"circuits\":[{\"name\":\"main\","
            "\"pins\":[{\"label\":\"a\",\"dir\":\"in\"},{\"label\":\"y\",\"dir\":\"out\"}],"
            "\"components\":[{\"id\":\"g1\",\"type\":\"AND\",\"at\":[400,300]}],"
            "\"nets\":[{\"name\":\"a\",\"connect\":[\"pin:a\",\"g1.a\"]},"
            "{\"name\":\"y\",\"connect\":[\"g1.out\",\"pin:y\"]}]}]}；"
            "元件类型：AND/OR/NAND/NOR/XOR/XNOR/NOT/DFF/TFF/SPLITTER4/CLOCK/LED/DISPLAY 或子电路名；"
            "引用写法 pin:标签、元件id.端口。生成后会自动跑一次静态体检。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": {"type": "object", "description": "含 file / circuits 的规格对象"},
                "write": {"type": "boolean", "description": "是否落盘，默认 true"},
                "verify": {"type": "boolean", "description": "生成后跑一次 Logisim 真值表，检查是否出现 E/U（组合电路适用）"},
            },
            "required": ["spec"],
        },
    },
    {
        "name": "circ_kb",
        "description": (
            "经验库：action=list 列出已知坑；action=search 按关键词查；action=add 追加一条新经验"
            "（title/detail/evidence）。add 只写入运行时副本（LOCALAPPDATA 或 runtime/kb），"
            "不会改仓库里的 server/circuit_kit/knowledge.json；要随仓库发布，需手动把条目搬进该文件。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "search", "add"]},
                "keyword": {"type": "string"},
                "id": {"type": "string", "description": "条目短 id（可选，默认由标题生成）"},
                "title": {"type": "string"},
                "detail": {"type": "string"},
                "evidence": {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "circ_appearance",
        "description": (
            "编辑子电路外观（Logisim 5.0 的 Edit Circuit Appearance）。"
            "action=get 读取当前外观；auto 自动生成左入右出、带名称牌的整齐框体并应用；"
            "apply 应用自定义 spec；preview 切到外观视图并截图；save 写回 .circ（带备份与校验）；"
            "reset 恢复默认外观；close 关闭 Logisim 会话。"
            "默认保留现有端口坐标，避免父电路导线脱开；spec 里的 pin 可用标签或 pin_at 指定。"
            "注意：一旦移动端口，父电路导线不会自动跟随，必须在父电路（通常是 main）里打开"
            "Logisim 截图确认每个引脚仍连着线并完成重布，不能只用 circ_audit/circ_sim 代替。"
            "重排子电路内部（紧凑布局）时：circ-port 的 x/y 是符号坐标、pin 才是内部 Pin 坐标，"
            "移动内部 Pin 只需同步 pin；不要整块替换 circuit（会丢 a/appear）；lib 编号照抄原文件"
            "（触发器 lib=2，写成 4 会报「库4中缺少组件」）；改完用 Logisim 自身 -w 测试向量"
            "（含 <set><seq>）对保存前 .bak 逐行 diff，0 差异才算通过。"
            "需要 JDK 21+ 编译 Java 桥（tools/build_bridge.py）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                           "enum": ["get", "auto", "apply", "preview", "save", "reset", "close", "status"]},
                "file": {"type": "string", "description": ".circ 文件绝对路径"},
                "circuit": {"type": "string", "description": "电路名，默认 main"},
                "spec": {"type": "object", "description": "apply/preview 使用的外观 spec"},
                "layout": {"type": "object", "description": "auto 的排版参数（pitch/margin/nameplate 等）"},
                "mode": {"type": "string", "description": "auto/apply: gui（默认）或 xml 兜底"},
                "dry_run": {"type": "boolean", "description": "auto 只返回 spec，不应用"},
                "out": {"type": "string", "description": "preview 截图输出路径"},
                "save": {"type": "boolean", "description": "close 时是否先保存，默认 false"},
            },
            "required": ["action", "file"],
        },
    },
]


def _json_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _appearance_ports(data, pins):
    widths = {(p.get("label"), p.get("at")): int(p.get("width", 1) or 1) for p in pins}
    by_at = {p.get("at"): p for p in pins}
    out = []
    for obj in data.get("objects") or []:
        if obj.get("tag") != "circ-port":
            continue
        attrs = obj.get("attrs") or {}
        at = attrs.get("pin")
        label = obj.get("pin_label") or (by_at.get(at) or {}).get("label", "")
        out.append({
            "label": label,
            "at": at,
            "x": int(attrs.get("x", 0) or 0),
            "y": int(attrs.get("y", 0) or 0),
            "dir": "in" if attrs.get("dir", "in") == "in" else "out",
            "width": widths.get((label, at), int((by_at.get(at) or {}).get("width", 1) or 1)),
        })
    return out


def _backup(path):
    dst = path + time.strftime(".bak-%Y%m%d-%H%M%S")
    shutil.copy2(path, dst)
    return dst


def _verify_saved(path, circuit, pins, digest_before=None, require_digest=False):
    data = kit_app.read_xml(path, circuit)
    ports = [o for o in data.get("objects") or [] if o.get("tag") == "circ-port"]
    load_ok, load_text = run_logisim(["-t", "stats", path], timeout=120)
    report = {
        "appearance": data.get("appearance"),
        "ports": len(ports),
        "expected_ports": len(pins),
        "logisim_load": load_ok,
        "audit": kit_audit.audit(path).get("verdict"),
    }
    ok = (report["appearance"] == "custom" and report["ports"] == len(pins) and load_ok)
    if require_digest:
        report["digest_unchanged"] = kit_app.layout_digest(path) == digest_before
        ok = ok and report["digest_unchanged"]
    else:
        report["digest_unchanged"] = None
    if not load_ok:
        report["logisim_message"] = load_text[:200]
    return ok, report


def _circ_appearance(args):
    action = args.get("action")
    f = os.path.abspath(args["file"])
    if not os.path.isfile(f):
        return False, f"文件不存在: {f}"
    try:
        circuits, main = kit_net.parse(f)
    except Exception as exc:
        return False, f"解析 .circ 失败: {exc}"
    circuit = args.get("circuit") or main
    pins = kit_app.pins_from_file(f, circuit)
    mode = (args.get("mode") or "gui").lower()

    if action == "get":
        sess = kit_bridge.peek_session(f)
        if sess is not None:
            try:
                data = sess.send("appearance_get", {"circuit": circuit})
                data["via"] = "gui"
                return True, _json_text(data)
            except kit_bridge.BridgeError:
                pass
        data = kit_app.read_xml(f, circuit)
        data["pins"] = pins
        data["via"] = "xml"
        return True, _json_text(data)

    if action == "status":
        sess = kit_bridge.peek_session(f)
        if sess is not None:
            data = sess.send("status")
            data["via"] = "gui"
            return True, _json_text(data)
        return True, _json_text({
            "file": f, "circuit": circuit, "pins": len(pins),
            "appearance": kit_app.read_xml(f, circuit).get("appearance"),
            "bridge": "not running", "via": "xml",
        })

    if action in ("auto", "apply"):
        if action == "auto":
            if mode == "xml":
                return False, ("auto 需要 GUI 桥读取现有端口坐标（默认外观不在 .circ 里）。"
                               "请先运行 tools/build_bridge.py 并安装 JDK 21+。")
            try:
                sess = kit_bridge.get_session(f, JAVA, JAR)
                live = sess.send("appearance_get", {"circuit": circuit})
                current = _appearance_ports(live, pins)
                old_anchor = (0, 0)
                for obj in live.get("objects") or []:
                    if obj.get("tag") == "circ-anchor":
                        a = obj.get("attrs") or {}
                        old_anchor = (int(a.get("x", 0) or 0), int(a.get("y", 0) or 0))
                        break
            except kit_bridge.BridgeError as exc:
                return False, f"{exc.code}: {exc}\n{exc.hint}".strip()
            spec = kit_app.auto_layout(pins, circuit, args.get("layout") or {},
                                       current_ports=current)
            layout_opt = spec.get("layout") or {}
            if not layout_opt.get("preserve_port_positions", True):
                new_anchor = layout_opt.get("anchor") or {}
                spec["impact"] = kit_app.parent_impact(
                    f, circuit, current, spec.get("ports") or [],
                    old_anchor, (int(new_anchor.get("x", 0) or 0),
                                 int(new_anchor.get("y", 0) or 0)))
        else:
            spec = args.get("spec")
            if not isinstance(spec, dict):
                return False, f"{action} 需要 spec 对象"
            spec.setdefault("circuit", circuit)

        check = dict(spec)
        check["strict"] = bool((spec.get("layout") or {}).get("strict_ports", True))
        errors = kit_app.validate(check, pins)
        if errors:
            return False, "外观 spec 校验失败：\n" + _json_text(errors)
        if action == "auto" and args.get("dry_run"):
            return True, _json_text({"via": "dry-run", "spec": spec})

        try:
            sess = kit_bridge.get_session(f, JAVA, JAR)
            res = sess.send("appearance_apply", {"spec": spec})
            res["via"] = "gui"
            res["warnings"] = res.get("warnings", [])
            if isinstance(spec.get("impact"), dict):
                res["impact"] = spec["impact"]
            return True, _json_text(res)
        except kit_bridge.BridgeError as exc:
            if mode != "xml":
                return False, (f"{exc.code}: {exc}\n{exc.hint}\n"
                               f"（需要 headless 兜底请传 mode=\"xml\"）").strip()
            backup = _backup(f)
            count = kit_app.write_xml(f, spec)
            return True, _json_text({"via": "xml", "objects": count, "backup": backup})

    if action == "preview":
        try:
            sess = kit_bridge.get_session(f, JAVA, JAR)
            if isinstance(args.get("spec"), dict):
                spec = args["spec"]
                spec.setdefault("circuit", circuit)
                sess.send("appearance_apply", {"spec": spec})
            sess.send("select_circuit", {"circuit": circuit})
            sess.send("show_view", {"view": "appearance"})
            out = args.get("out") or (os.path.splitext(f)[0] + ".appearance.png")
            res = sess.send("screenshot", {"out": os.path.abspath(out), "kind": "window"})
            res["via"] = "gui"
            return True, _json_text(res)
        except kit_bridge.BridgeError as exc:
            return False, f"{exc.code}: {exc}\n{exc.hint}".strip()

    if action == "save":
        sess = kit_bridge.peek_session(f)
        if sess is not None:
            backup = _backup(f)
            try:
                res = sess.send("save")
            except kit_bridge.BridgeError as exc:
                return False, f"{exc.code}: {exc}\n{exc.hint}".strip()
            ok, report = _verify_saved(f, circuit, pins)
            res.update({"backup": backup, "verify": report})
            res["via"] = "gui"
            return ok, _json_text(res)
        spec = args.get("spec")
        if not isinstance(spec, dict):
            return False, "没有打开的 GUI 会话，也没有 spec；无法保存"
        spec.setdefault("circuit", circuit)
        digest = kit_app.layout_digest(f)
        backup = _backup(f)
        kit_app.write_xml(f, spec)
        ok, report = _verify_saved(f, circuit, pins, digest, require_digest=True)
        return ok, _json_text({"via": "xml", "backup": backup, "verify": report})

    if action == "reset":
        sess = kit_bridge.peek_session(f)
        if sess is not None:
            res = sess.send("appearance_reset",
                            {"circuit": circuit, "mode": args.get("mode") or "logisim"})
            res["via"] = "gui"
            return True, _json_text(res)
        root = ET.parse(f).getroot()
        target = next((c for c in root.findall("circuit") if c.get("name") == circuit), None)
        if target is None:
            return False, f"电路 {circuit} 不存在"
        for a in target.findall("a"):
            if a.get("name") == "appearance":
                a.set("val", "logisim_evolution")
        old = target.find("appear")
        if old is not None:
            target.remove(old)
        ET.indent(root, space="  ")
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
            fh.write(ET.tostring(root, encoding="unicode"))
            fh.write("\n")
        return True, _json_text({"via": "xml", "appearance": "logisim_evolution"})

    if action == "close":
        kit_bridge.close_session(f)
        return True, "已关闭 Logisim 外观会话"

    return False, f"未知 action {action}"


def call_tool(name, args):
    if name == "logisim_info":
        ver = version_text()
        java_ver = ""
        try:
            java_ver = _decode(subprocess.run([JAVA, "-version"], capture_output=True,
                                          timeout=30).stderr).splitlines()[0]
        except Exception:
            java_ver = "未知"
        caps = ["-t table 真值表", "-t stats 统计", "-t speed 仿真速度", "-t tty 需电路含 TTY 组件"]
        major = 0
        try:
            major = int(ver.split(".")[0])
        except Exception:
            pass
        if major >= 5:
            caps.append("-w 原生测试向量（只能验组合逻辑：每行都从初始状态重算）")
        else:
            caps.append("-w 需要 5.0+，当前版本不支持")
        info = {
            "版本": ver,
            "当前选用": JAR or "未找到（设置 LOGISIM_JAR）",
            "本机其他内核": [j for j in find_all_jars() if os.path.abspath(j) != os.path.abspath(JAR)] or "无",
            "java": JAVA,
            "java_runtime": java_ver,
            "gui启动器": find_launcher() or "无（将用 java -jar 启动）",
            "无头能力": caps,
            "原生MCP": "不支持（官方各版本都没有 MCP/网络接口，本桥接为外部封装）",
            "切换内核": "设置环境变量 LOGISIM_JAR 指向目标 jar 即可",
            "扩展工具": ["circ_geometry", "circ_probe", "circ_audit", "circ_sim", "circ_build",
                         "circ_kb", "circ_appearance"],
            "经验库": f"{len(kit_kb.list_pitfalls())} 条（用 circ_kb list 查看）",
            "外观桥": {
                "jar": (kit_bridge.BRIDGE_JAR if os.path.isfile(kit_bridge.BRIDGE_JAR)
                        else "未构建（python tools/build_bridge.py）"),
                "javac": shutil.which("javac") or "未找到（需要 JDK 21+）",
            },
        }
        return True, json.dumps(info, ensure_ascii=False, indent=2)

    if name == "circuit_summary":
        f = os.path.abspath(args["file"])
        if not os.path.isfile(f):
            return False, f"文件不存在: {f}"
        return True, dump_summary(parse_circuit(f), f)

    if name == "circuit_truth_table":
        f = os.path.abspath(args["file"])
        if not os.path.isfile(f):
            return False, f"文件不存在: {f}"
        n = input_pin_count(f)
        if n > 16:
            return False, (f"主电路有 {n} 个输入引脚，真值表会有 2^{n} = {2 ** n} 行，已拒绝执行；"
                           f"请改用 circ_sim 抽样，或把无关引脚去掉后再验")
        rows, raw = truth_table(f, timeout=int(args.get("timeout", 180)),
                                max_rows=int(args.get("max_rows", 4096)))
        if rows is None:
            return False, f"仿真失败: {raw}"
        text = fmt_table(rows)
        if "已截断" in raw:
            text += "\n" + [ln for ln in raw.splitlines() if "已截断" in ln][-1]
        return True, text

    if name == "circuit_verify":
        ok, txt = verify_table(args["file"], args["vectors"])
        return ok, txt

    if name == "circuit_test_vector":
        return run_test_vector(args["file"], args.get("circuit_name", "main"), args["vectors"])

    if name == "circuit_stats":
        f = os.path.abspath(args["file"])
        ok, txt = run_logisim(["-t", "stats", f])
        if not ok:
            return False, txt
        lines = ["数量\t唯一\t元件\t类别"]
        for ln in txt.splitlines():
            if ln.strip():
                lines.append(ln.replace("\t", "  "))
        return True, "\n".join(lines)

    if name == "circuit_build":
        spec = args["spec"]
        if not spec.get("file"):
            return False, "spec.file 必填"
        body = build_circuit(spec)
        with open(spec["file"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        rows, raw = truth_table(spec["file"])
        table = fmt_table(rows) if rows else f"(真值表生成失败: {raw})"
        return True, f"已生成 {spec['file']}\n\n{table}"

    if name == "circuit_open_gui":
        f = os.path.abspath(args["file"])
        launcher = find_launcher()
        # 启动器版本和当前内核版本不一致时（比如启动器是 3.9、内核切到 5.0），
        # 用 java -jar 直接开，避免两个版本互相写坏文件。
        kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        if launcher:
            bundled = glob.glob(os.path.join(os.path.dirname(launcher), "app", "logisim-evolution-*-all.jar"))
            same = bundled and os.path.basename(bundled[0]) == os.path.basename(JAR)
            if same:
                subprocess.Popen([launcher, f], close_fds=True, **kwargs)
                return True, f"已用 GUI 启动器打开: {f}"
        if not JAR:
            return False, "未找到 jar，无法启动"
        subprocess.Popen([JAVA, "-jar", JAR, f], close_fds=True, **kwargs)
        note = "" if not launcher else f"（启动器版本与当前内核不一致，改用 {os.path.basename(JAR)}）"
        return True, f"已用 java -jar 打开: {f}{note}"

    if name == "circ_geometry":
        res = kit_geo.describe(args.get("component"), args.get("select"), args.get("width"))
        return not (isinstance(res, dict) and res.get("error")), \
            json.dumps(res, ensure_ascii=False, indent=2)

    if name == "circ_probe":
        f = os.path.abspath(args["file"])
        if not os.path.isfile(f):
            return False, f"文件不存在: {f}"
        try:
            sess = kit_bridge.get_session(f, JAVA, JAR)
            comp = str(args.get("component") or "").strip()
            if not comp:
                return True, _json_text(sess.send("probe_libraries"))
            res = sess.send("probe_component", {
                "name": comp,
                "lib": args.get("lib"),
                "attrs": args.get("attrs") or {},
            })
            return True, _json_text(res)
        except kit_bridge.BridgeError as exc:
            return False, f"{exc.code}: {exc}\n{exc.hint}".strip()

    if name == "circ_audit":
        f = os.path.abspath(args["file"])
        if not os.path.isfile(f):
            return False, f"文件不存在: {f}"
        rep = kit_audit.audit(f)
        head = f"体检结论: {rep['verdict']}  电路={rep['circuits']} 网络={rep['nets']} 端口={rep['ports']}"
        if rep.get("unsupported"):
            names = [f"{u['component']}(lib={u['lib']})" for u in rep["unsupported"]]
            head += "\n警告: 以下元件不在网表支持范围内，结论只覆盖其余部分: " + \
                    "、".join(names[:8]) + ("…" if len(names) > 8 else "")
        detail = json.dumps(
            {k: v for k, v in rep.items() if k not in ("file", "circuits", "nets", "ports", "verdict")},
            ensure_ascii=False, indent=2)
        return rep.get("verdict") == "ok", head + "\n" + detail

    if name == "circ_sim":
        f = os.path.abspath(args["file"])
        if not os.path.isfile(f):
            return False, f"文件不存在: {f}"
        circuits, main = kit_net.parse(f)
        try:
            sim = kit_net.Sim(circuits, main)
        except kit_net.UnsupportedComponent as exc:
            return False, f"{exc}\n（请改用 circuit_truth_table 或删除不支持的元件后再仿真）"
        clock = args.get("clock")
        if clock and not sim.bind_clock(clock):
            avail = sorted(lbl for (path, lbl) in sim.pin_at if path == "r")
            return False, f"找不到时钟信号 {clock}；根层引脚有: {avail}"
        cycles = int(args.get("cycles", 0))
        snaps = sim.run(args.get("inputs") or {}, cycles)
        watch = args.get("watch") or []
        rows = []
        for i, s in enumerate(snaps):
            row = {"t": i}
            for k, v in s.items():
                if watch and k not in watch:
                    continue
                if isinstance(v, tuple):
                    seq = list(v)
                    row[k] = "".join(str(x) for x in (reversed(seq) if len(seq) > 1 else seq))
                else:
                    row[k] = str(v)
            rows.append(row)
        if not rows:
            return True, "（无快照）"
        cols = ["t"] + [c for c in rows[0] if c != "t"]
        out = ["\t".join(cols)]
        for r in rows:
            out.append("\t".join(str(r.get(c, "")) for c in cols))
        note = ""
        if cycles and sim.clk_net is None:
            note = (f"\n警告: 未找到时钟（Clock 组件或名为 cp/clk/clock/ck 的引脚），"
                    f"{cycles} 拍内不会有触发器被推进")
        return True, f"共 {len(rows)} 拍（t=0 为上电初始态）\n" + "\n".join(out) + note

    if name == "circ_build":
        spec = dict(args["spec"])
        if spec.get("file"):
            spec["file"] = os.path.abspath(spec["file"])
        try:
            text, stats = kit_builder.build(spec, write=bool(args.get("write", True)))
        except kit_builder.BuildError as exc:
            return False, f"生成失败: {exc}"
        out = spec.get("file")
        head = f"已生成 {out}\n" + json.dumps(stats, ensure_ascii=False)
        ok = True
        if out and os.path.isfile(out):
            rep = kit_audit.audit(out)
            if rep.get("verdict") == "partial":
                head += f"\n体检: 部分覆盖（{rep.get('unsupported')}）"
                ok = False
            else:
                head += (f"\n体检: {rep['verdict']}（悬空 {len(rep['floating'])}，"
                         f"冲突 {len(rep['conflict'])}，孤立 {len(rep['dangling'])}，"
                         f"位宽 {len(rep.get('width_conflict') or [])}，"
                         f"断头线 {len(rep.get('dangling_wire') or [])}，"
                         f"重叠 {len(rep['body_overlap'])}）")
                if rep.get("verdict") == "problems":
                    ok = False
        if args.get("verify") and out and os.path.isfile(out):
            rows, raw = truth_table(out, max_rows=512)
            if rows is None:
                head += f"\n真值表复核: 失败（{raw[:100]}）"
            else:
                bad = sum(1 for r in rows[1:] for c in r if any(ch in "EU" for ch in c))
                head += f"\n真值表复核: {'通过，无 E/U' if bad == 0 else f'发现 {bad} 个 E/U 单元'}"
                if bad:
                    ok = False
        return ok, head

    if name == "circ_appearance":
        return _circ_appearance(args)

    if name == "circ_kb":
        act = args.get("action")
        if act == "list":
            items = kit_kb.list_pitfalls()
            return True, "\n".join(f"- [{p['id']}] {p['title']}\n    {p['detail']}" for p in items) or "（空）"
        if act == "search":
            items = kit_kb.list_pitfalls(args.get("keyword", ""))
            return True, "\n".join(f"- [{p['id']}] {p['title']}\n    {p['detail']}" for p in items) or "（无匹配）"
        if act == "add":
            if not args.get("title") or not args.get("detail"):
                return False, "add 需要 title 与 detail"
            item, how = kit_kb.add_pitfall(args["title"], args["detail"],
                                           args.get("evidence", ""), args.get("id"))
            return True, f"已{how}: [{item['id']}] {item['title']}"
        return False, "action 只支持 list / search / add"

    return False, f"未知工具 {name}"


# --------------------------------------------------------------------------
# MCP / JSON-RPC 主循环
# --------------------------------------------------------------------------
def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": mid, "error": err}


def dispatch(msg):
    """处理一条 JSON-RPC 消息，返回响应对象；通知返回 None。"""
    if not isinstance(msg, dict):
        return _error(None, -32600, "Invalid Request")
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return _result(mid, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return _result(mid, {}) if mid is not None else None

    if method == "tools/list":
        return _result(mid, {"tools": TOOLS})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            ok, text = call_tool(name, args)
        except Exception as exc:  # 工具内部异常也要回成 MCP 结果，不能让客户端挂住
            ok, text = False, f"{type(exc).__name__}: {exc}"
        return _result(mid, {"content": [{"type": "text", "text": text}], "isError": not ok})

    if mid is not None:
        return _error(mid, -32601, f"Method not found: {method}")
    return None


def handle(msg):
    resp = dispatch(msg)
    if resp is not None:
        send(resp)


def doctor():
    """环境体检：不启动 MCP，只打印依赖与自检结果。"""
    out = []
    out.append(f"插件根目录 : {PLUGIN_ROOT}")
    out.append(f"服务端版本 : {SERVER_NAME} {SERVER_VERSION}")
    out.append(f"Python     : {sys.version.split()[0]} ({sys.executable})")
    out.append(f"Java       : {JAVA}")
    ok_java = os.path.isfile(JAVA) or bool(shutil.which(JAVA))
    out.append(f"  java 可用: {'是' if ok_java else '否（-t table / -w 都会失败）'}")
    out.append(f"内核 jar   : {JAR or '未找到'}")
    if JAR:
        out.append(f"  jar 可用 : 是 ({os.path.basename(JAR)})")
    else:
        out.append("  jar 可用 : 否 → 设置 LOGISIM_JAR，或把 jar 放到 <plugin>/runtime/")
    out.append(f"其他内核   : {[j for j in find_all_jars() if os.path.abspath(j) != os.path.abspath(JAR)] or '无'}")
    out.append(f"外观桥     : {kit_bridge.BRIDGE_JAR if os.path.isfile(kit_bridge.BRIDGE_JAR) else '未构建 → python tools/build_bridge.py'}")
    out.append(f"  javac    : {shutil.which('javac') or '未找到（需要 JDK 21+）'}")
    out.append(f"经验库     : {kit_kb.KB_PATH}")
    pits = kit_kb.list_pitfalls()
    out.append(f"  条目数   : {len(pits)}")
    try:
        parent = os.path.dirname(os.path.abspath(kit_kb.KB_PATH))
        os.makedirs(parent, exist_ok=True)
        probe = kit_kb.KB_PATH + ".probe"
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        out.append("  可写     : 是")
    except Exception as exc:
        out.append(f"  可写     : 否（{exc}）")
    try:
        with open(os.path.join(PLUGIN_ROOT, ".codebuddy-plugin", "plugin.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        out.append(f"插件清单   : {manifest.get('name')} {manifest.get('version')} "
                   f"（skills={len(manifest.get('skills') or [])}）")
    except Exception as exc:
        out.append(f"插件清单   : 读取失败（{exc}）")
    # 生成 → 体检 → 仿真的短路自检（不依赖 Logisim，纯 Python 侧）
    try:
        tmp = os.path.join(tempfile.gettempdir(), "_logisim_plugin_doctor.circ")
        spec = {"file": tmp, "circuits": [{
            "name": "main",
            "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
                     {"label": "y", "dir": "out"}],
            "components": [{"id": "g1", "type": "AND", "at": [400, 300]}],
            "nets": [{"name": "a", "connect": ["pin:a", "g1.a"]},
                     {"name": "b", "connect": ["pin:b", "g1.b"]},
                     {"name": "y", "connect": ["g1.out", "pin:y"]}]}]}
        kit_builder.build(spec)
        rep = kit_audit.audit(tmp)
        circuits, top = kit_net.parse(tmp)
        sim = kit_net.Sim(circuits, top)
        y = sim.run({"a": 1, "b": 1}, 0)[0].get("y")
        os.remove(tmp)
        out.append(f"生成/体检  : {rep['verdict']}（悬空 {len(rep['floating'])}，冲突 {len(rep['conflict'])}）")
        out.append(f"网表仿真   : a=1,b=1 → y={y[0] if isinstance(y, tuple) else y}（应为 1）")
    except Exception as exc:
        out.append(f"生成/仿真  : 失败（{type(exc).__name__}: {exc}）")
    return "\n".join(out)


def main():
    if "--doctor" in sys.argv[1:]:
        print(doctor())
        return
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(f"[{SERVER_NAME}] jar={JAR or '未找到'} java={JAVA}", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            send(_error(None, -32700, "Parse error", str(exc)))
            continue
        try:
            if isinstance(msg, list):
                out = []
                for item in msg:
                    try:
                        resp = dispatch(item)
                    except Exception as exc:
                        resp = _error(None, -32603, f"Internal error: {exc}")
                    if resp is not None:
                        out.append(resp)
                if out:
                    send(out)
            else:
                handle(msg)
        except Exception as exc:
            print(f"[{SERVER_NAME}] error: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
