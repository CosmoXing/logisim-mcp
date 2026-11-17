#!/usr/bin/env python3
"""Logisim-ITA 2.16 / 2.7.1 headless 仿真入口。

2.7.1 分支（含 Logisim-ITA 2.16.1.0）**没有** evolution 那套 `-w` 向量引擎，
`-tty table` 只能跑组合真值表。本模块用 `ITAProbe.java` 直接调 Logisim 的类库：
加载 .circ、按标签设输入引脚、打时钟、读输出引脚。

首次使用会自动 javac 编译到 `ita/classes`。

用法（也可 `import ita_probe` 当库用）：

    python ita_probe.py list   <circ> [circuit]
    python ita_probe.py eval   <circ> [circuit] --set "A=1,B=0x2"
    python ita_probe.py vector <circ> [circuit] <vec>
    python ita_probe.py ends   <circ> [circuit]
    python ita_probe.py errors <circ> [circuit]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ITA_DIR = os.path.join(HERE, "ita")
CLASSES = os.path.join(ITA_DIR, "classes")


def _local_ita_jar() -> str:
    """向上找插件根的 logisim.local.json（已被 gitignore 排除），读 "ita_jar"。"""
    d = HERE
    for _ in range(6):
        path = os.path.join(d, "logisim.local.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    return str(json.load(fh).get("ita_jar") or "")
            except (OSError, ValueError):
                return ""
        d = os.path.dirname(d)
    return ""


def find_jar() -> str:
    # 查找顺序：LOGISIM_ITA_JAR → logisim.local.json 的 ita_jar → 标准安装位置
    for p in (
        os.environ.get("LOGISIM_ITA_JAR", ""),
        _local_ita_jar(),
        "C:/Program Files/Logisim-ITA/Logisim-ITA.jar",
    ):
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError(
        "找不到 Logisim-ITA.jar，请设置环境变量 LOGISIM_ITA_JAR 指向该文件"
    )


def ensure_compiled(jar: str | None = None) -> tuple[str, str]:
    """返回 (jar_path, classpath)。首次调用会编译 ITAProbe.java。"""
    jar = jar or find_jar()
    src = os.path.join(ITA_DIR, "ITAProbe.java")
    cls = os.path.join(CLASSES, "ITAProbe.class")
    if not os.path.isfile(cls) or os.path.getmtime(src) > os.path.getmtime(cls):
        os.makedirs(CLASSES, exist_ok=True)
        javac = shutil.which("javac") or "javac"
        r = subprocess.run(
            [javac, "-encoding", "UTF-8", "-cp", jar, "-d", CLASSES, src],
            capture_output=True,
        )
        if r.returncode != 0:
            raise RuntimeError("ITAProbe 编译失败:\n" + r.stderr.decode("utf-8", "ignore"))
    return jar, os.pathsep.join([jar, CLASSES])


def run(args: list[str], circ: str, circuit: str | None = None,
        jar: str | None = None, timeout: int = 300) -> str:
    """跑一次 ITAProbe，返回 stdout（UTF-8）。"""
    jar, cp = ensure_compiled(jar)
    cmd = ["java", "-Djava.awt.headless=true", "-cp", cp, "ITAProbe",
           "--file", circ]
    if circuit:
        cmd += ["--circuit", circuit]
    cmd += args
    env = dict(os.environ)
    env.setdefault("JAVA_TOOL_OPTIONS", "-Dfile.encoding=UTF-8")
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    out = r.stdout.decode("utf-8", "ignore")
    err = r.stderr.decode("utf-8", "ignore")
    if r.returncode not in (0, 1):        # 1 = 向量有失败行，属正常
        raise RuntimeError(f"ITAProbe 失败 rc={r.returncode}\n{out}\n{err}")
    return out


# ---------------------------------------------------------------- API

def list_pins(circ: str, circuit: str | None = None) -> dict:
    """返回 {'circuit':..., 'pins':[{'name','dir','width','loc'}], 'comps','wires'}"""
    out = run(["--list"], circ, circuit)
    head = re.search(r"CIRCUIT (.+?) pins=(\d+) comps=(\d+) wires=(\d+)", out)
    pins = []
    for m in re.finditer(r"PIN (\S+) (in|out) (\d+) \((\d+),(\d+)\)", out):
        pins.append({"name": m.group(1), "dir": m.group(2),
                     "width": int(m.group(3)),
                     "loc": (int(m.group(4)), int(m.group(5)))})
    return {
        "circuit": head.group(1) if head else circuit,
        "comps": int(head.group(3)) if head else None,
        "wires": int(head.group(4)) if head else None,
        "pins": pins,
    }


def eval_pins(circ: str, circuit: str | None = None,
              set_values: dict | None = None,
              read: list[str] | None = None) -> dict:
    """设输入并读输出。set_values 形如 {'RA1': 5, 'Din': 0xdeadbeef}。"""
    args = []
    if set_values:
        spec = ",".join(f"{k}=0x{v:x}" if v > 9 else f"{k}={v}"
                        for k, v in set_values.items())
        args += ["--set", spec]
    if read:
        args += ["--read", ",".join(read)]
    out = run(args, circ, circuit)
    res = {}
    for m in re.finditer(r"OUT (\S+)=(\S+)", out):
        res[m.group(1)] = m.group(2)
    return res


def run_vector(circ: str, vec: str, circuit: str | None = None,
               clk: str | None = None, trace: bool = False) -> dict:
    """跑向量文件。返回 {'rows','pass','fail','fails':[行号...]}"""
    args = ["--vector", vec]
    if clk:
        args += ["--clk", clk]
    if trace:
        args += ["--trace"]
    out = run(args, circ, circuit)
    s = re.search(r"SUMMARY rows=(\d+) pass=(\d+) fail=(\d+)", out)
    fails = [int(m.group(1)) for m in re.finditer(r"ROW (\d+) FAIL", out)]
    return {
        "rows": int(s.group(1)) if s else None,
        "pass": int(s.group(2)) if s else None,
        "fail": int(s.group(3)) if s else None,
        "fails": fails,
        "log": out,
    }


def ends(circ: str, circuit: str | None = None) -> list[dict]:
    """所有元件的真实端口坐标（Logisim 自己算的，最可靠）。"""
    out = run(["--ends"], circ, circuit)
    result, owner = [], None
    for line in out.splitlines():
        m = re.match(r"COMP (.+) @\((\d+),(\d+)\)", line)
        if m:
            owner = {"comp": m.group(1),
                     "loc": (int(m.group(2)), int(m.group(3))), "ports": []}
            result.append(owner)
            continue
        m = re.match(r"\s+END \((\d+),(\d+)\) w(\d+)(.*)", line)
        if m and owner is not None:
            tail = m.group(4)
            owner["ports"].append({
                "loc": (int(m.group(1)), int(m.group(2))),
                "width": int(m.group(3)),
                "dir": "in" if " in" in tail else ("out" if " out" in tail else "io"),
            })
    return result


def errors(circ: str, circuit: str | None = None) -> list[str]:
    """扫描所有端口上值为 ERROR(E) 的位置。"""
    out = run(["--errors"], circ, circuit)
    return [l.strip() for l in out.splitlines() if l.startswith("ERR")]


# ---------------------------------------------------------------- CLI

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    circ = sys.argv[2]
    circuit = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("-") else None
    rest = sys.argv[4:] if circuit else sys.argv[3:]

    if cmd == "list":
        print(list_pins(circ, circuit))
    elif cmd == "ends":
        for c in ends(circ, circuit):
            print(c["comp"], c["loc"], c["ports"])
    elif cmd == "errors":
        for e in errors(circ, circuit):
            print(e)
    elif cmd == "eval":
        kv = {}
        if "--set" in rest:
            for pair in rest[rest.index("--set") + 1].split(","):
                k, v = pair.split("=")
                kv[k] = int(v, 0)
        print(eval_pins(circ, circuit, kv))
    elif cmd == "vector":
        print(run_vector(circ, rest[0], circuit))
    else:
        print(__doc__)
        sys.exit(1)
