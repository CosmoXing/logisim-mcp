"""Logisim-evolution 4.1 无头探针（g41probe）。

真引擎校验层：把 4.1 的 jar 放进 classpath，直接 `new Loader()` 加载 .circ，
打印加载错误、电路清单、每个元件的真实端口坐标与包围盒。
生成器/解析器的 4.1 几何（子电路固定 220 宽、20px 间距）就是靠它复核的。

依赖：java + 4.1 的 all.jar（jpackage 安装包里的 app/logisim-evolution-4.1.0-all.jar）。
定位顺序：LOGISIM41_JAR > logisim.local.json 的 logisim41_jar > LOGISIM_JAR(4.x) >
          D:/logisim4.1/app/ > 常见安装位置。

注意：4.1 自带运行时是 Java 21，探针用 `javac --release 21` 编译，
      避免用 Java 26 编译出 4.1 JVM 跑不了的 class 版本。
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PLUGIN_ROOT, "server", "java", "src", "g41probe")
BUILD_DIR = os.path.join(PLUGIN_ROOT, "server", "java", "build", "g41probe")
LOCAL_CFG = os.path.join(PLUGIN_ROOT, "logisim.local.json")


def _cfg(key):
    try:
        with open(LOCAL_CFG, encoding="utf-8") as fh:
            return str(json.load(fh).get(key, "")).strip()
    except (OSError, ValueError):
        return ""


def find_jar41() -> str:
    """定位 4.1 内核 jar。"""
    for cand in (os.environ.get("LOGISIM41_JAR", "").strip(),
                 _cfg("logisim41_jar"),
                 os.environ.get("LOGISIM_JAR", "").strip()):
        if cand and os.path.isfile(cand) and "4.1" in os.path.basename(cand):
            return cand
    roots = [
        "D:/logisim4.1/app",
        "C:/logisim4.1/app",
        os.path.join(os.path.expanduser("~"), "logisim4.1", "app"),
        os.path.join(os.environ.get("ProgramFiles", "C:/Program Files"), "logisim-evolution", "app"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "logisim-evolution", "app"),
        PLUGIN_ROOT,
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for jar in sorted(glob.glob(os.path.join(root, "logisim-evolution-4.1*-all.jar")), reverse=True):
            if os.path.isfile(jar):
                return jar
    return ""


def _javac():
    return shutil.which("javac") or ""


def _compile(jar: str):
    stamp = os.path.join(BUILD_DIR, "g41probe.stamp")
    srcs = sorted(glob.glob(os.path.join(SRC_DIR, "*.java")))
    if not srcs:
        raise RuntimeError(f"4.1 探针源码缺失: {SRC_DIR}")
    fingerprint = jar + "|" + "|".join(str(os.path.getmtime(s)) for s in srcs)
    try:
        with open(stamp, encoding="utf-8") as fh:
            if fh.read().strip() == fingerprint and os.path.isdir(os.path.join(BUILD_DIR, "g41probe")):
                return
    except OSError:
        pass
    javac = _javac()
    if not javac:
        raise RuntimeError("未找到 javac（需要 JDK 21+）；无法编译 4.1 探针")
    os.makedirs(BUILD_DIR, exist_ok=True)
    base = [javac, "-nowarn", "-encoding", "UTF-8"]
    # 4.1 自带 JRE 是 21；用 --release 21 保证 class 版本可被它加载
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
    raise RuntimeError("g41probe 编译失败:\n" + ((last.stderr or last.stdout)[-2000:] if last else ""))


def _run(probe: str, args, timeout: int = 120) -> str:
    jar = find_jar41()
    if not jar:
        raise RuntimeError(
            "未找到 Logisim 4.1 内核 jar：设 LOGISIM41_JAR，"
            "或在 logisim.local.json 写 \"logisim41_jar\"，或安装到 D:/logisim4.1/app/")
    _compile(jar)
    java = os.environ.get("JAVA_BIN") or "java"
    cp = jar + os.pathsep + BUILD_DIR
    r = subprocess.run(
        [java, "-Djava.awt.headless=true", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8",
         "-cp", cp, "g41probe." + probe] + [str(x) for x in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    out = r.stdout or ""
    if r.returncode != 0 and not out:
        out = r.stderr or f"探针 {probe} 退出码 {r.returncode}"
    return out.strip()


# ---------------------------------------------------------------- 对外 API
def check(file: str) -> str:
    """真实加载：报错与 GUI 弹窗同款 + 电路清单。"""
    return _run("G41Check", [file])


def ports(file: str, circuit: str = "main", factory: str = "") -> str:
    """列出元件真实端口/包围盒；factory 为空则列全部。"""
    return _run("G41Ports", [file, circuit, factory or ""])


def bounds(file: str, circuit: str = "main") -> str:
    """只列包围盒，检查元件体是否压线。"""
    text = _run("G41Ports", [file, circuit, ""])
    out = []
    for ln in text.splitlines():
        if "@" not in ln:
            continue
        head, _, rest = ln.partition(" bounds=")
        out.append(head + "  " + rest.split(" :")[0])
    return "\n".join(out) if out else text
