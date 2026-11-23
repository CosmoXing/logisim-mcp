#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe39.java 的封装：编译一次，之后直接跑 3.9 内核无头整机测试。

用法：
    python probe39.py <file.circ> [circuit] [cycles] [ram=xxx.hex] [pin=value ...]

示例：
    python probe39.py T1.circ main 10 ram=G1-T1-RAM.hex
    python probe39.py rf.circ main 2 wen=1 waddr=2 wdata=2222 raddr2=2 clk=0
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(os.path.dirname(HERE))
JAVA_SRC = os.path.join(HERE, "Probe39.java")
CLASS_DIR = os.path.join(HERE, "__probe39__")


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def find_jar() -> str | None:
    env = os.environ.get("LOGISIM39_JAR") or os.environ.get("LOGISIM_JAR")
    if env and os.path.exists(env):
        return env
    for name in ("logisim.local.json", "logisim.local.example.json"):
        p = os.path.join(SKILL_ROOT, "..", name)
        p = os.path.abspath(p)
        if os.path.exists(p):
            try:
                cfg = json.load(open(p, encoding="utf-8"))
            except Exception:
                cfg = {}
            for key in ("logisim39_jar", "jar"):
                v = cfg.get(key)
                if v and os.path.exists(v):
                    return v
    for cand in (
        r"D:/logisim3.9/app/logisim-evolution-3.9.0-all.jar",
        r"C:/Program Files/Logisim/logisim-evolution-3.9.0-all.jar",
    ):
        if os.path.exists(cand):
            return cand
    return None


def ensure_compiled(jar: str) -> None:
    out = os.path.join(CLASS_DIR, "Probe39.class")
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(JAVA_SRC):
        return
    os.makedirs(CLASS_DIR, exist_ok=True)
    subprocess.run(["javac", "-cp", jar, "-d", CLASS_DIR, JAVA_SRC], check=True)


def main() -> int:
    _utf8()
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    jar = find_jar()
    if not jar:
        print("未找到 logisim 3.9 jar：设置 LOGISIM39_JAR 或在 logisim.local.json 写 logisim39_jar")
        return 2
    ensure_compiled(jar)
    cp = jar + os.pathsep + CLASS_DIR
    cmd = ["java", "-Djava.awt.headless=true", "-cp", cp, "Probe39"] + sys.argv[1:]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())