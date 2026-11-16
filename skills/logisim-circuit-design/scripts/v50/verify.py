"""Logisim-evolution 命令行验证包装器（真值表 / 统计 / 测试向量）。

用法：
    python verify.py table  fa.circ
    python verify.py stats  demo.circ
    python verify.py vector main bcd4.vec demo_test.circ

⚠️ vector 模式（Logisim -w）每一行都从初始状态重新求值，**只能验组合逻辑**。
   时序电路（计数器/状态机）请改用多拍网表仿真，见 references/counter13-casebook.md。

要点：
- 自动寻找最高版本的 logisim-evolution-*-all.jar（可用 --jar 或 $LOGISIM_JAR 覆盖）。
- 输出是 GBK 中文，这里统一解码后再打印，便于 grep「失败」。
- **不要**加 -Djava.awt.headless=true：-w 内部会 new Frame，headless 直接抛 HeadlessException。
"""

import argparse
import glob
import os
import re
import subprocess
import sys

CANDIDATES = [
    os.environ.get("LOGISIM_JAR", ""),
    r"D:/app/logisim-evolution-*-all.jar",
    os.path.expanduser("~/logisim*/logisim-evolution-*-all.jar"),
    os.path.expanduser("~/Downloads/logisim-evolution-*-all.jar"),
]


def _ver_key(path):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", os.path.basename(path))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def find_jar(explicit=None):
    if explicit:
        return explicit
    for pattern in CANDIDATES:
        if not pattern:
            continue
        hits = [p for p in glob.glob(pattern) if os.path.isfile(p)]
        if hits:
            return max(hits, key=_ver_key)
    raise SystemExit("找不到 logisim-evolution-*-all.jar，请用 --jar 指定")


def find_java():
    home = os.environ.get("JAVA_HOME")
    if home:
        exe = os.path.join(home, "bin", "java.exe" if os.name == "nt" else "java")
        if os.path.isfile(exe):
            return exe
    return "java"          # 交给 PATH；jpackage 自带 runtime 里常常没有 java.exe


def run(args, timeout=600):
    cmd = [find_java()] + args
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    raw = proc.stdout or b""
    for enc in ("gbk", "utf-8", "latin-1"):
        try:
            return proc.returncode, raw.decode(enc), proc.stderr.decode(enc, "ignore")
        except UnicodeDecodeError:
            continue
    return proc.returncode, "", ""


def summarize(text):
    """从 -w 输出里抓「通过：N，失败：M」。"""
    m = re.search(r"通过[：:]\s*(\d+)[，,\s]*失败[：:]\s*(\d+)", text)
    if not m:
        return None
    return {"pass": int(m.group(1)), "fail": int(m.group(2))}


def main():
    ap = argparse.ArgumentParser(description="Logisim 电路验证")
    ap.add_argument("mode", choices=["table", "stats", "vector"])
    ap.add_argument("file", help=".circ 工程文件")
    ap.add_argument("extra", nargs="*", help="vector 模式：<电路名> <向量文件>")
    ap.add_argument("--jar", default=None)
    args = ap.parse_args()

    jar = find_jar(args.jar)

    if args.mode == "table":
        code, out, err = run(["-jar", jar, "-t", "table", args.file])
    elif args.mode == "stats":
        code, out, err = run(["-jar", jar, "-t", "stats", args.file])
    else:
        if len(args.extra) < 2:
            raise SystemExit("vector 模式需要：verify.py vector <工程.circ> <电路名> <向量文件>")
        circuit, vec = args.extra[0], args.extra[1]
        code, out, err = run(["-jar", jar, "-w", circuit, vec, args.file])

    print(out.rstrip())
    if err.strip():
        print("--- stderr ---")
        print(err.rstrip())

    if args.mode == "vector":
        s = summarize(out)
        if s is None:
            print("[!] 没解析到结果行，检查电路名/向量表头是否对得上")
            return 2
        print(f"[结果] 通过 {s['pass']}，失败 {s['fail']}")
        return 0 if s["fail"] == 0 else 1
    return code


if __name__ == "__main__":
    sys.exit(main())
