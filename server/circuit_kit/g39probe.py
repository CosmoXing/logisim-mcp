"""Logisim 3.9 无头探针（g39probe）——用 3.9 本体内核做加载/重存/功能/布线级调试。

背景：本项目自带的网表仿真器（netlist.py）是按 XML 语义自绘的，分线器方向等
细节可能与真引擎不一致；而 3.9 的 `-t table` / `-w` 只能验组合逻辑。
这一层探针直接 `new Loader()` + `new Project()` 驱动 3.9 的真实内核（无头），
覆盖四类场景：

  1. 加载体检   G39Load   —— 5.0 文件在 3.9 打不开时给出与 GUI 同款的报错
  2. 格式重存   G39Save   —— 5.0 存盘转原生 3.9 格式（元件/导线数不变）
  3. 功能验证   G39Seq    —— 脚本化多拍时序测试（pin=val / t 打拍 / r 读输出）
  4. 布线级调试 G39Wires / G39OneNet / G39NetList / G39Nets / G39Inst /
                           G39Idx / G39Bounds / G39Dump / G39Vals

Java 源码在 server/java/src/g39probe/，首次调用自动 javac 编译到
server/java/build/g39probe（源码或 jar 变化时重编）。运行依赖 java + 3.9 jar：

  * 环境变量 LOGISIM39_JAR
  * 或 logisim.local.json 的 "logisim39_jar"
  * 或常见安装位置自动搜索（D:/logisim3.9/app/... 等）
"""

from __future__ import annotations

import glob
import os
import subprocess
import tempfile

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PLUGIN_ROOT, "server", "java", "src", "g39probe")
BUILD_DIR = os.path.join(PLUGIN_ROOT, "server", "java", "build", "g39probe")
LOCAL_CFG = os.path.join(PLUGIN_ROOT, "logisim.local.json")


def find_jar39() -> str:
    """定位 3.9 内核 jar：环境变量 > 本地配置 > 常见安装位置。"""
    cand = os.environ.get("LOGISIM39_JAR", "").strip()
    if cand and os.path.isfile(cand):
        return cand
    try:
        import json
        with open(LOCAL_CFG, encoding="utf-8") as fh:
            cand = str(json.load(fh).get("logisim39_jar", "")).strip()
    except (OSError, ValueError):
        cand = ""
    if cand and os.path.isfile(cand):
        return cand
    roots = [
        os.path.join(os.path.expanduser("~"), "logisim3.9", "app"),
        "D:/logisim3.9/app",
        "C:/logisim3.9/app",
        os.path.join(os.environ.get("ProgramFiles", "C:/Program Files"), "logisim3.9", "app"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "logisim3.9", "app"),
        PLUGIN_ROOT,
    ]
    for root in roots:
        for jar in sorted(glob.glob(os.path.join(root, "logisim-evolution-3.9*-all.jar")), reverse=True):
            if os.path.isfile(jar):
                return jar
    return ""


def _compile(jar: str):
    """懒编译：源码或 jar 变化才重编（stamp 文件记录指纹）。"""
    stamp = os.path.join(BUILD_DIR, "g39probe.stamp")
    srcs = sorted(glob.glob(os.path.join(SRC_DIR, "*.java")))
    if not srcs:
        raise RuntimeError(f"探针源码缺失: {SRC_DIR}")
    fingerprint = jar + "|" + "|".join(str(os.path.getmtime(s)) for s in srcs)
    try:
        with open(stamp, encoding="utf-8") as fh:
            if fh.read().strip() == fingerprint and os.path.isdir(os.path.join(BUILD_DIR, "g39probe")):
                return
    except OSError:
        pass
    import shutil
    javac = shutil.which("javac")
    if not javac:
        raise RuntimeError("未找到 javac（需要 JDK）；无法编译 3.9 探针")
    os.makedirs(BUILD_DIR, exist_ok=True)
    cp = jar + os.pathsep + BUILD_DIR
    r = subprocess.run(
        [javac, "-nowarn", "-encoding", "UTF-8", "-cp", jar, "-d", BUILD_DIR] + srcs,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    if r.returncode != 0:
        raise RuntimeError("g39probe 编译失败:\n" + (r.stderr or r.stdout)[-2000:])
    with open(stamp, "w", encoding="utf-8") as fh:
        fh.write(fingerprint)


def _run(probe: str, args: list, timeout: int = 120, env_extra: dict | None = None) -> str:
    jar = find_jar39()
    if not jar:
        raise RuntimeError(
            "未找到 Logisim 3.9 内核 jar：设 LOGISIM39_JAR，"
            "或在 logisim.local.json 写 \"logisim39_jar\"，"
            "或安装到 D:/logisim3.9/app/")
    java = os.environ.get("JAVA_BIN") or "java"
    _compile(jar)
    cp = jar + os.pathsep + BUILD_DIR
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(
        [java, "-Djava.awt.headless=true", "-Dstdout.encoding=UTF-8", "-cp", cp,
         "g39probe." + probe] + [str(x) for x in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, env=env,
    )
    out = (r.stdout or "")
    if r.returncode != 0 and not out:
        out = r.stderr or f"探针 {probe} 退出码 {r.returncode}"
    return out


# ---------------------------------------------------------------- 对外 API

def check(file: str) -> str:
    """真实加载：报错与 GUI 弹窗同款（缺 lib 的 tool 等）+ 电路清单。"""
    return _run("G39Load", [file])


def save(file: str, out: str = "") -> str:
    """用 3.9 内核重存（5.0 → 原生 3.9 格式）。out 为空则原子覆盖原文件。"""
    out = out or file
    if not out:
        return "输出路径为空"
    if os.path.abspath(out) == os.path.abspath(file):
        fd, tmp = tempfile.mkstemp(suffix=".circ", dir=os.path.dirname(os.path.abspath(file)))
        os.close(fd)
        text = _run("G39Save", [file, tmp])
        if "saved=true" in text:
            os.replace(tmp, file)
            return text.replace(tmp, file)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return text
    return _run("G39Save", [file, out])


def run(file: str, circuit: str, steps: str, watch: list | None = None,
        timeout: int = 300) -> str:
    """脚本化功能测试。steps 形如 "clk=0,wen=1;clk=1;clk=0;r"；watch 为坐标列表。"""
    env = {"W": ";".join(watch)} if watch else None
    return _run("G39Seq", [file, circuit, steps], timeout=timeout, env_extra=env)


def wires(file: str, circuit: str) -> str:
    """导出 3.9 加载后的导线（WireRepair 之后）——与 XML diff 找被裁掉的线。"""
    return _run("G39Wires", [file, circuit])


def onet(file: str, circuit: str, x: int, y: int) -> str:
    """列出包含 (x,y) 的网络全部成员。"""
    return _run("G39OneNet", [file, circuit, f"{x},{y}"])


def multi(file: str, circuit: str) -> str:
    """扫多驱动网（同一网 ≥2 个输出端）＝真实短路。"""
    return _run("G39NetList", [file, circuit])


def nets(file: str, circuit: str = "all") -> str:
    """未接线端口扫描（端口没落任何导线且不与其它端口同点）。"""
    return _run("G39Nets", [file, circuit or "all"])


def insts(file: str, circuit: str, factory: str) -> str:
    """某类元件实例的端口索引/坐标/位宽（精确工厂名，可查子电路实例）。"""
    return _run("G39Inst", [file, circuit, factory])


def ends(file: str, circuit: str, name: str) -> str:
    """按工厂名子串过滤元件并打印端口（模糊匹配，如 Gate）。"""
    return _run("G39Idx", [file, circuit, name])


def bounds(file: str, circuit: str) -> str:
    """全部元件包围盒（查元件体压线）。"""
    return _run("G39Bounds", [file, circuit])


def pins(file: str, circuit: str) -> str:
    """全部 Pin 加载后的真实属性（确认 output/radix 是否被 3.9 正确读入）。"""
    return _run("G39Dump", [file, circuit])


def vals(file: str, circuit: str, inputs: str, points: list) -> str:
    """设引脚后读指定坐标的线值（位宽 + err 标记）。inputs 形如 "wen=1,waddr=5"。"""
    return _run("G39Vals", [file, circuit, inputs, ";".join(points)])


def overlap(file: str) -> str:
    """扫描全部电路的共线重叠导线（纯 XML 分析，不需要 jar）。

    真短路：两根同向同线导线重叠且不共享端点 —— Logisim 加载时会合并成一根，
    造成跨网短路/断供（曾致寄存器堆写入全失效）。
    冗余重叠：共享端点的重复段（无害，加载时自动合并），仅提示。
    """
    import re as _re
    with open(file, encoding="utf-8") as fh:
        text = fh.read()
    out = []
    real_total = redundant_total = 0
    for cn, body in _re.findall(r'<circuit name="([^"]+)">(.*?)</circuit>', text, _re.S):
        segs = []
        for m in _re.finditer(r'from="\((-?\d+),(-?\d+)\)" to="\((-?\d+),(-?\d+)\)"', body):
            x1, y1, x2, y2 = map(int, m.groups())
            if y1 == y2:
                segs.append(("H", y1, min(x1, x2), max(x1, x2)))
            elif x1 == x2:
                segs.append(("V", x1, min(y1, y2), max(y1, y2)))
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                a, b = segs[i], segs[j]
                if a[0] != b[0] or a[1] != b[1]:
                    continue
                lo, hi = max(a[2], b[2]), min(a[3], b[3])
                if lo >= hi:
                    continue
                axis = "x" if a[0] == "H" else "y"
                ends_share = (lo in (a[2], a[3]) and lo in (b[2], b[3])) or \
                             (hi in (a[2], a[3]) and hi in (b[2], b[3]))
                if ends_share:
                    redundant_total += 1
                    out.append(f"[{cn}] 冗余重叠（无害，加载时合并）: {a} 与 {b}，{axis}={a[1]} {lo}..{hi}")
                else:
                    real_total += 1
                    out.append(f"[{cn}] ★真短路: {a} 与 {b}，{axis}={a[1]} 重叠 {lo}..{hi}"
                               f"（两端点都不共享，Logisim 会合并成一根导致跨网短路）")
    head = (f"共线重叠扫描: 真短路 {real_total} 处，冗余重叠 {redundant_total} 处"
            f"（冗余=共享端点的前缀/后缀重复，加载时合并不影响功能）")
    return "\n".join([head] + out) if out else head
