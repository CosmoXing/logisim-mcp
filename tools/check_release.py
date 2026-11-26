#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开源前的发布检查：版本一致、无本机痕迹、文件完整、可打包。

用法：
    python tools/check_release.py           # 检查
    python tools/check_release.py --build   # 检查 + 生成 dist/zip
    python tools/check_release.py --strict  # 把警告也当作失败（CI 用）

退出码 0 = 通过。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

def _utf8_console():
    """Windows 控制台默认不是 UTF-8，直接 print 中文会抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


_utf8_console()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL, WARN = [], []

REQUIRED = [
    ".codebuddy-plugin/plugin.json",
    ".mcp.json",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".gitignore",
    ".gitattributes",
    "server/server.py",
    "server/circuit_kit/geometry.py",
    "server/circuit_kit/router.py",
    "server/circuit_kit/netlist.py",
    "server/circuit_kit/builder.py",
    "server/circuit_kit/audit.py",
    "server/circuit_kit/knowledge.py",
    "server/circuit_kit/knowledge.json",
    "server/circuit_kit/appearance.py",
    "server/circuit_kit/logisim_bridge.py",
    "server/circuit_kit/vprofile.py",
    "server/circuit_kit/circ271.py",
    "server/circuit_kit/g39probe.py",
    "server/circuit_kit/v41probe.py",
    "server/circuit_kit/versions/__init__.py",
    "server/java/src/logisim/bridge/BridgeMain.java",
    "server/java/src/logisim/bridge/LogisimAdapter.java",
    "server/java/src/g39probe/G39Inst.java",
    "server/java/src/g41probe/G41Check.java",
    "server/java/src/g41probe/G41Ports.java",
    "server/java/src/g41probe/G41Render.java",
    "tools/build_bridge.py",
    "docs/APPEARANCE.md",
    "skills/logisim-circuit-design/SKILL.md",
    "tools/selftest.py",
    "tools/build_zip.py",
    "tools/install.py",
    "tools/sync_skill.py",
    "tools/check_release.py",
    "logisim.local.example.json",
    "Makefile",
    ".editorconfig",
    "docs/ARCHITECTURE.md",
    "docs/PLUGIN-SPEC.md",
    "docs/DESIGN-NOTES.md",
    "examples/README.md",
    "examples/generate.py",
    "examples/and2.circ",
    "examples/half_adder.circ",
    "examples/ripple2.circ",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
]

# 不应出现在仓库文本里的东西：本机绝对路径、个人标识、密钥样式
SECRET_PATTERNS = [
    (re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"']+"), "Windows 用户目录绝对路径"),
    (re.compile(r"/home/[A-Za-z0-9._-]+/"), "Linux 用户目录绝对路径"),
    (re.compile(r"/Users/[A-Za-z0-9._-]+/"), "macOS 用户目录绝对路径"),
    (re.compile(r"Prigect"), "本机工程路径"),
    (re.compile(r"\bASUS\b"), "本机用户名"),
    (re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"), "疑似密钥"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "私钥"),
]

TEXT_EXT = {".md", ".py", ".json", ".cmd", ".sh", ".yml", ".yaml", ".circ", ".txt", ".toml"}
SKIP_DIRS = {"__pycache__", "dist", ".git", ".github_ignore", "build", "runtime"}


def fail(msg):
    FAIL.append(msg)
    print(f"[FAIL] {msg}")


def warn(msg):
    WARN.append(msg)
    print(f"[WARN] {msg}")


def ok(msg):
    print(f"[ OK ] {msg}")


def walk_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            yield os.path.join(base, name), os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")


def check_required():
    for rel in REQUIRED:
        if not os.path.isfile(os.path.join(ROOT, rel)):
            fail(f"缺少必需文件: {rel}")
    ok(f"必需文件检查完成（{len(REQUIRED)} 项）")


def check_version():
    manifest = json.load(open(os.path.join(ROOT, ".codebuddy-plugin/plugin.json"), encoding="utf-8"))
    version = manifest.get("version", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version or ""):
        fail(f"plugin.json 版本号格式不对: {version!r}")
        return version

    server_src = open(os.path.join(ROOT, "server/server.py"), encoding="utf-8").read()
    m = re.search(r'def _plugin_version\(default="([\d.]+)"\)', server_src)
    if not m:
        warn("server.py 里没找到 _plugin_version 的默认版本")
    elif m.group(1) != version:
        fail(f"server.py 默认版本 {m.group(1)} 与 plugin.json {version} 不一致")

    changelog = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    if f"## {version}" not in changelog:
        fail(f"CHANGELOG.md 缺少 {version} 的小节")

    # 文档里出现的 zip 名应为当前版本
    for rel in ("README.md",):
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for hit in re.findall(r"logisim-mcp-(\d+\.\d+\.\d+)\.zip", text):
            if hit != version:
                warn(f"{rel} 里出现旧版本 zip 名: logisim-mcp-{hit}.zip")

    ok(f"版本一致性: {version}")
    return version


def check_skill(manifest):
    for rel in manifest.get("skills") or []:
        d = os.path.normpath(os.path.join(ROOT, rel))
        sk = os.path.join(d, "SKILL.md")
        if not os.path.isfile(sk):
            fail(f"技能缺少 SKILL.md: {rel}")
            continue
        text = open(sk, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            fail(f"{rel}/SKILL.md 缺少 frontmatter")
            continue
        name = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
        if not name:
            fail(f"{rel}/SKILL.md frontmatter 缺少 name")
        elif name.group(1).strip() != os.path.basename(d):
            fail(f"技能 name({name.group(1).strip()}) 与目录名({os.path.basename(d)}) 不一致")
        for ref in re.findall(r"`((?:references|scripts|assets)/[^`]+)`", text):
            if not os.path.isfile(os.path.join(d, ref)):
                fail(f"{rel}/SKILL.md 引用了不存在的文件: {ref}")
    ok(f"技能检查完成（{len(manifest.get('skills') or [])} 个）")


def check_syntax():
    bad = 0
    for full, rel in walk_files():
        if rel.endswith(".json"):
            try:
                json.load(open(full, encoding="utf-8"))
            except Exception as exc:
                fail(f"JSON 解析失败 {rel}: {exc}")
                bad += 1
        elif rel.endswith(".py"):
            try:
                compile(open(full, encoding="utf-8").read(), full, "exec")
            except SyntaxError as exc:
                fail(f"Python 语法错误 {rel}: {exc}")
                bad += 1
    if not bad:
        ok("JSON / Python 语法检查通过")


def check_secrets():
    hits = 0
    for full, rel in walk_files():
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        if rel == "logisim.local.json":
            continue          # 本机私有配置，已被 .gitignore 排除
        if rel == "tools/check_release.py":
            continue          # 本文件必然包含待检测的模式串
        try:
            text = open(full, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat, label in SECRET_PATTERNS:
                if pat.search(line):
                    fail(f"{rel}:{lineno} 含{label} → {line.strip()[:80]}")
                    hits += 1
    if not hits:
        ok("未发现本机路径 / 个人信息 / 密钥")


def check_cmd():
    for rel in ("bin/run-mcp.cmd",):
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            continue
        data = open(full, "rb").read()
        if any(b > 127 for b in data):
            fail(f"{rel} 含非 ASCII 字节（GBK 控制台下会解析失败）")
        if b"\r\n" not in data:
            warn(f"{rel} 不是 CRLF 换行")
    ok(".cmd 编码检查完成")


def check_local_config_ignored():
    ignore = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    if "logisim.local.json" not in ignore:
        fail(".gitignore 没有排除 logisim.local.json")
    else:
        ok("本机配置已排除在版本控制外")


def changelog_section(version):
    """取出 CHANGELOG.md 里属于该版本的小节正文（不含标题行）。"""
    path = os.path.join(ROOT, "CHANGELOG.md")
    text = open(path, encoding="utf-8").read()
    m = re.search(r"^##\s+%s\b[^\n]*\n" % re.escape(version), text, re.M)
    if not m:
        fail(f"CHANGELOG.md 里没有 {version} 小节（Release 说明会变空）")
        return None
    rest = text[m.end():]
    end = re.search(r"^##\s+", rest, re.M)
    body = (rest[: end.start()] if end else rest).strip()
    if not body:
        fail(f"CHANGELOG.md 的 {version} 小节是空的")
        return None
    ok(f"CHANGELOG 有 {version} 小节（{len(body)} 字）")
    return body


def write_notes(version, body, out_path):
    """把更新说明写成 Release 正文。"""
    text = "\n".join([
        body,
        "",
        "---",
        "",
        "**安装**：下载下方 `logisim-mcp-%s.zip` 解压，运行 `python tools/install.py`；" % version,
        "或直接克隆仓库后执行同一命令。",
        "",
        "**完整记录**：[CHANGELOG.md](https://github.com/{}/{}/blob/main/CHANGELOG.md)".format(
            *repo_slug()),
        "",
    ])
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    ok(f"已写 Release 说明: {os.path.relpath(out_path, ROOT)}")


def repo_slug():
    """从 git remote 推断 owner/repo，失败时给占位符。"""
    try:
        url = subprocess.check_output(
            ["git", "-C", ROOT, "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ("OWNER", "REPO")
    m = re.search(r"[/:]([^/:]+)/([^/]+?)(?:\.git)?$", url)
    return (m.group(1), m.group(2)) if m else ("OWNER", "REPO")


def check_zip(version):
    out = os.path.join(ROOT, "dist", f"logisim-mcp-{version}.zip")
    if not os.path.isfile(out):
        warn(f"dist 里没有 logisim-mcp-{version}.zip（用 --build 生成）")
        return
    import zipfile
    names = zipfile.ZipFile(out).namelist()
    if any(n.endswith(".pyc") or "__pycache__" in n for n in names):
        fail("分发包里混入了 __pycache__ / .pyc")
    if any(n.startswith("dist/") for n in names):
        fail("分发包里混入了 dist/")
    if "logisim.local.json" in names:
        fail("分发包里混入了本机配置 logisim.local.json")
    if ".codebuddy-plugin/plugin.json" not in names:
        fail("分发包缺少 .codebuddy-plugin/plugin.json")
    ok(f"分发包检查完成（{len(names)} 个文件）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="检查后生成 dist zip")
    ap.add_argument("--notes", metavar="PATH", help="把本版 CHANGELOG 写成 Release 说明文件")
    ap.add_argument("--strict", action="store_true", help="警告也视为失败")
    args = ap.parse_args()

    print(f"仓库根目录: {ROOT}\n")
    check_required()
    version = check_version()
    manifest = json.load(open(os.path.join(ROOT, ".codebuddy-plugin/plugin.json"), encoding="utf-8"))
    check_skill(manifest)
    check_syntax()
    check_secrets()
    check_cmd()
    check_local_config_ignored()
    body = changelog_section(version) if version else None
    if args.notes and body:
        write_notes(version, body, os.path.join(ROOT, args.notes)
                    if not os.path.isabs(args.notes) else args.notes)

    if args.build and version:
        rc = subprocess.call([sys.executable, os.path.join(ROOT, "tools", "build_zip.py")])
        if rc != 0:
            fail("build_zip.py 执行失败")
    if version:
        check_zip(version)

    print(f"\n结果：失败 {len(FAIL)}，警告 {len(WARN)}")
    if args.strict and WARN:
        return 1
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
