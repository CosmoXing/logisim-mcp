#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编译并打包 Logisim Java 桥（零第三方依赖，用 zipfile 写 jar）。

用法：
    python tools/build_bridge.py                 # 有缓存就跳过
    python tools/build_bridge.py --force         # 强制重编
    python tools/build_bridge.py --logisim D:/app/logisim-evolution-5.0.0-all.jar
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "server", "java", "src")
CLASS_DIR = os.path.join(ROOT, "server", "java", "build", "classes")
OUT_DIR = os.path.join(ROOT, "runtime", "bridge")
OUT_JAR = os.path.join(OUT_DIR, "logisim-bridge.jar")
BUILD_INFO = os.path.join(OUT_DIR, "build.json")
MANIFEST = "Manifest-Version: 1.0\r\nMain-Class: logisim.bridge.BridgeMain\r\n\r\n"


def find_javac():
    env = os.environ.get("JAVA_HOME", "").strip()
    cands = []
    if env:
        cands += [os.path.join(env, "bin", "javac.exe"), os.path.join(env, "bin", "javac")]
    found = shutil.which("javac")
    if found:
        cands.insert(0, found)
    # Oracle javapath 的 javac 是 shim，真正的 JDK 可能在同级或注册表路径
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return ""


def find_jar(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("LOGISIM_JAR", "").strip()
    if env and os.path.isfile(env):
        return env
    local = os.path.join(ROOT, "logisim.local.json")
    if os.path.isfile(local):
        try:
            with open(local, encoding="utf-8") as fh:
                cand = str(json.load(fh).get("jar", "")).strip()
            if cand and os.path.isfile(cand):
                return cand
        except (OSError, ValueError):
            pass
    for pattern in (
        os.path.join(ROOT, "runtime", "*.jar"),
        "D:/app/logisim-evolution-*-all.jar",
        "C:/app/logisim-evolution-*-all.jar",
        "C:/Program Files/logisim-evolution/app/*.jar",
        "C:/Program Files (x86)/logisim-evolution/app/*.jar",
    ):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return ""


def source_hash():
    h = hashlib.sha256()
    for base, _, files in os.walk(SRC_DIR):
        for f in sorted(files):
            if not f.endswith(".java"):
                continue
            p = os.path.join(base, f)
            h.update(os.path.relpath(p, SRC_DIR).replace("\\", "/").encode("utf-8"))
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def build(force=False, logisim_jar=None):
    javac = find_javac()
    if not javac:
        raise SystemExit("找不到 javac：需要 JDK 21+（JRE 不够）")
    jar = find_jar(logisim_jar)
    if not jar or not os.path.isfile(jar):
        raise SystemExit("找不到 logisim-evolution jar：设置 LOGISIM_JAR 或 logisim.local.json")
    digest = source_hash()
    if not force and os.path.isfile(OUT_JAR) and os.path.isfile(BUILD_INFO):
        try:
            info = json.load(open(BUILD_INFO, encoding="utf-8"))
            if info.get("source_hash") == digest and info.get("logisim") == jar:
                print(f"缓存命中：{OUT_JAR}")
                return OUT_JAR
        except (OSError, ValueError):
            pass
    os.makedirs(CLASS_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    sources = []
    for base, _, files in os.walk(SRC_DIR):
        for f in sorted(files):
            if f.endswith(".java"):
                sources.append(os.path.join(base, f))
    cmd = [javac, "--release", "21", "-encoding", "UTF-8", "-cp", jar, "-d", CLASS_DIR, *sources]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    if proc.returncode != 0:
        raise SystemExit("javac 失败：\n" + out + err)
    tmp = OUT_JAR + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/MANIFEST.MF", MANIFEST)
        for base, _, files in os.walk(CLASS_DIR):
            for f in files:
                if f.endswith(".class"):
                    p = os.path.join(base, f)
                    z.write(p, os.path.relpath(p, CLASS_DIR).replace("\\", "/"))
    os.replace(tmp, OUT_JAR)
    info = {
        "source_hash": digest,
        "logisim": jar,
        "javac": javac,
        "jar": OUT_JAR,
        "bytes": os.path.getsize(OUT_JAR),
    }
    with open(BUILD_INFO, "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"已构建：{OUT_JAR}（{info['bytes']} bytes）")
    return OUT_JAR


def main():
    args = sys.argv[1:]
    force = "--force" in args
    jar = None
    if "--logisim" in args:
        i = args.index("--logisim")
        if i + 1 < len(args):
            jar = args[i + 1]
    build(force=force, logisim_jar=jar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
