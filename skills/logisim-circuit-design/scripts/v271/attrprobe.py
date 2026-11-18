#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""触发一次「改属性」（等价于在界面里改文字），验证 WireRepair 不会死循环。

背景（pitfalls L13）：TextTool 提交文字走的是
    SetAttributeAction → CircuitTransaction → WireRepair.run → doOverlaps
`doOverlaps` 按 Wire.iterator() 逐点建 HashMap；只要电路里有「端口与导线差 1px」
「斜线」「长度非 10 倍数」的线，修复会反复拆出 1px 短桩 / 斜线段，点表无限膨胀，
表现就是「改一个字，Logisim 立刻卡死」并把内存吃到几个 GB。本探针用 8 秒超时判定。

用法：
    python attrprobe.py file.circ            # 默认查 main
    python attrprobe.py file.circ "电路名"
    python attrprobe.py file.circ "电路名" --timeout 15

输出：ATTR_OK <ms> → 正常；超时 → 退出码 1（说明该电路改属性会卡死）。
注意：Logisim 的 Simulator 线程是非 daemon，main 结束后进程不会退出，
      所以这里轮询输出而不是等进程结束。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ita_probe  # noqa: E402

SRC = os.path.join(HERE, "ita", "AttrProbe.java")
CLS = os.path.join(HERE, "ita", "classes")
NAME = "AttrProbe"


def ensure_compiled(jar: str) -> str:
    os.makedirs(CLS, exist_ok=True)
    cls = os.path.join(CLS, NAME + ".class")
    if not os.path.isfile(cls) or os.path.getmtime(SRC) > os.path.getmtime(cls):
        javac = shutil.which("javac") or "javac"
        r = subprocess.run([javac, "-encoding", "UTF-8", "-cp", jar, "-d", CLS, SRC],
                           capture_output=True)
        if r.returncode != 0:
            raise SystemExit("AttrProbe 编译失败:\n" + r.stderr.decode("utf-8", "ignore"))
    return os.pathsep.join([jar, CLS])


def probe(circ: str, circuit: str = "main", timeout: float = 8.0) -> bool:
    jar = ita_probe.find_jar()
    cp = ensure_compiled(jar)
    java = shutil.which("java") or "java"
    out_path = os.path.join(tempfile.gettempdir(), "_attrprobe.out")
    with open(out_path, "w", encoding="utf-8") as fh:
        p = subprocess.Popen([java, "-Xmx256m", "-Djava.awt.headless=true", "-cp", cp,
                              NAME, circ, circuit],
                             stdout=fh, stderr=subprocess.DEVNULL)
    ok = False
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            time.sleep(0.2)
            try:
                txt = open(out_path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if "ATTR_OK" in txt:
                ok = True
                print(txt.strip().splitlines()[-1])
                break
            if "NO_TEXT" in txt:
                print(txt.strip().splitlines()[-1] + "（该电路没有 Text 组件，改用别的电路）")
                return True
    finally:
        p.kill()
    if not ok:
        print("[!] %s: %.0f 秒内没有返回 —— 改属性会卡死（见 pitfalls L13）" % (circuit, timeout))
    return ok


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    circ = sys.argv[1]
    circuit = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else "main"
    timeout = float(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 8.0
    sys.exit(0 if probe(circ, circuit, timeout) else 1)


if __name__ == "__main__":
    main()