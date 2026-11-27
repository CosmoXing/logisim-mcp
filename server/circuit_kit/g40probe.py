"""Logisim-evolution 4.0 无头探针（g40probe）。

真引擎校验层：把 4.0 的 jar 放进 classpath，直接 `new Loader()` 加载 .circ，
打印加载错误、电路清单、每个元件的真实端口坐标与包围盒。

4.0 与 4.1 的差异（实测 D:/logisim4.0，2025-09-07 构建）：
  - 文件头 source="4.0.0"
  - 库索引 Wiring0 / Gates1 / Memory2 / I/O3 / Base4（4.1 是 Memory5 / I/O6 / Base9）
  - <toolbar> / <mappings> 里的 <tool> 必须带 lib 属性，否则加载报「在库中找不到工具」
  - 元件几何（门/触发器/分线器/引脚/时钟/子电路）与 5.0 经典布局一致，
    子电路是动态宽度、10px 间距（不是 4.1 的 220 宽）

依赖：java + 4.0 的 all.jar（jpackage 安装包里的 app/logisim-evolution-4.0.0-all.jar）。
定位顺序：LOGISIM40_JAR > logisim.local.json 的 logisim40_jar > LOGISIM_JAR(4.0) >
          D:/logisim4.0/app/ > 常见安装位置。

4.0 自带运行时是 Java 21，探针用 `javac --release 21` 编译。
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PLUGIN_ROOT, "server", "java", "src", "g40probe")
BUILD_DIR = os.path.join(PLUGIN_ROOT, "server", "java", "build", "g40probe")
LOCAL_CFG = os.path.join(PLUGIN_ROOT, "logisim.local.json")


def _cfg(key):
    try:
        with open(LOCAL_CFG, encoding="utf-8") as fh:
            return str(json.load(fh).get(key, "")).strip()
    except (OSError, ValueError):
        return ""


def find_jar40() -> str:
    """定位 4.0 内核 jar。"""
    for cand in (os.environ.get("LOGISIM40_JAR", "").strip(),
                 _cfg("logisim40_jar"),
                 os.environ.get("LOGISIM_JAR", "").strip()):
        if cand and os.path.isfile(cand) and "4.0" in os.path.basename(cand):
            return cand
    roots = [
        "D:/logisim4.0/app",
        "C:/logisim4.0/app",
        os.path.join(os.path.expanduser("~"), "logisim4.0", "app"),
        os.path.join(os.environ.get("ProgramFiles", "C:/Program Files"), "logisim-evolution", "app"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "logisim-evolution", "app"),
        PLUGIN_ROOT,
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for jar in sorted(glob.glob(os.path.join(root, "logisim-evolution-4.0*-all.jar")), reverse=True):
            if os.path.isfile(jar):
                return jar
    return ""


def _javac():
    return shutil.which("javac") or ""


def _compile(jar: str):
    stamp = os.path.join(BUILD_DIR, "g40probe.stamp")
    srcs = sorted(glob.glob(os.path.join(SRC_DIR, "*.java")))
    if not srcs:
        raise RuntimeError(f"4.0 探针源码缺失: {SRC_DIR}")
    fingerprint = jar + "|" + "|".join(str(os.path.getmtime(s)) for s in srcs)
    try:
        with open(stamp, encoding="utf-8") as fh:
            if fh.read().strip() == fingerprint and os.path.isdir(os.path.join(BUILD_DIR, "g40probe")):
                return
    except OSError:
        pass
    javac = _javac()
    if not javac:
        raise RuntimeError("未找到 javac（需要 JDK 21+）；无法编译 4.0 探针")
    os.makedirs(BUILD_DIR, exist_ok=True)
    base = [javac, "-nowarn", "-encoding", "UTF-8"]
    # 4.0 自带 JRE 是 21；用 --release 21 保证 class 版本可被它加载
    attempts = [base + ["--release", "21"], base]
    last = None
    for cmd in attempts:
        r = subprocess.run(cmd + ["-cp", jar, "-d", BUILD_DIR] + srcs,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        if r.returncode == 0:
            with open(stamp, "w", encoding="utf-8") as fh:
                fh.write(fingerprint)
            return
        last = r
    raise RuntimeError("g40probe 编译失败:\n" + ((last.stderr or last.stdout)[-2000:] if last else ""))


def _run(probe: str, args, timeout: int = 120) -> str:
    jar = find_jar40()
    if not jar:
        raise RuntimeError(
            "未找到 Logisim 4.0 内核 jar：设 LOGISIM40_JAR，"
            "或在 logisim.local.json 写 \"logisim40_jar\"，或安装到 D:/logisim4.0/app/")
    _compile(jar)
    java = os.environ.get("JAVA_BIN") or "java"
    cp = jar + os.pathsep + BUILD_DIR
    r = subprocess.run(
        [java, "-Djava.awt.headless=true", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8",
         "-cp", cp, "g40probe." + probe] + [str(x) for x in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = r.stdout or ""
    if r.returncode != 0 and not out:
        out = r.stderr or f"探针 {probe} 退出码 {r.returncode}"
    return out.strip()


# ---------------------------------------------------------------- 对外 API
def check(file: str) -> str:
    """真实加载：报错与 GUI 弹窗同款 + 电路清单。"""
    return _run("G40Check", [file])


def ports(file: str, circuit: str = "main", factory: str = "") -> str:
    """列出元件真实端口/包围盒；factory 为空则列全部。"""
    return _run("G40Ports", [file, circuit, factory or ""])


def bounds(file: str, circuit: str = "main") -> str:
    """只列包围盒，检查元件体是否压线。"""
    text = _run("G40Ports", [file, circuit, ""])
    out = []
    for ln in text.splitlines():
        if "@" not in ln:
            continue
        head, _, rest = ln.partition(" bounds=")
        out.append(head + "  " + rest.split(" :")[0])
    return "\n".join(out) if out else text


def _repair_toolbar(raw: str):
    """4.0 的 <tool> 必须带 lib 属性；老文件（5.0/4.1）转换后 toolbar 会变空，补回标准工具条。"""
    import re

    def _insert_tools(match):
        block = match.group(0)
        if "<tool " in block:
            return block
        tools = "".join(f'    <tool lib="4" name="{n}"/>\n'
                        for n in ("Poke Tool", "Edit Tool", "Wiring Tool", "Text Tool"))
        return "<toolbar>\n" + tools + "    <sep/>\n  </toolbar>"

    if "<toolbar>" not in raw:
        raw = raw.replace("  <circuit ", '  <toolbar>\n    <sep/>\n  </toolbar>\n  <circuit ', 1)
    raw = re.sub(r"<toolbar>.*?</toolbar>", _insert_tools, raw, flags=re.S)
    mapping = ('<mappings>\n    <tool lib="4" name="Poke Tool" map="Button2"/>\n'
               '    <tool lib="4" name="Menu Tool" map="Button3"/>\n  </mappings>')
    if "<mappings/>" in raw:
        raw = raw.replace("<mappings/>", mapping, 1)
    else:
        m = re.search(r"<mappings>(.*?)</mappings>", raw, flags=re.S)
        if m and "<tool " not in m.group(1):
            raw = raw[:m.start()] + mapping + raw[m.end():]
    return raw


def save(file: str, out: str = "") -> str:
    """用 4.0 内核重新加载并保存，产出原生 4.0 格式（source=4.0.0、库索引 0~4）。"""
    if not out:
        base, ext = os.path.splitext(file)
        out = base + "-40" + (ext or ".circ")
    text = _run("G40Save", [file, out])
    note = ""
    if os.path.isfile(out):
        try:
            with open(out, encoding="utf-8") as fh:
                raw = fh.read()
            fixed = _repair_toolbar(raw)
            if fixed != raw:
                with open(out, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(fixed)
                note = "\n已补齐 4.0 toolbar/mappings（源文件的 <tool> 缺少 lib 属性）"
        except OSError:
            pass
    return text + note