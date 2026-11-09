#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把插件装到本机 WorkBuddy：注册本地市场，或直接写 mcp.json。

用法：
    python tools/install.py                 # 注册本地市场 logisim-local（推荐）
    python tools/install.py --mcp-only      # 只往 ~/.workbuddy/mcp.json 里加一条
    python tools/install.py --uninstall     # 撤销上面两种安装
    python tools/install.py --dry-run       # 只看会改什么，不落盘

安全约定：
  * 改任何配置文件前都会在同目录留 <文件名>.bak-<时间戳>；
  * 只增删自己那一条，绝不重写别人的条目；
  * 不删除插件源码目录，只删安装副本与注册项。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
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
MARKET_NAME = "logisim-local"


def plugin_name():
    """插件名以 .codebuddy-plugin/plugin.json 为准，避免改名后这里忘记同步。"""
    path = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["name"]
    except (OSError, KeyError, ValueError) as exc:
        raise SystemExit(f"读取插件清单失败: {exc}")

EXCLUDE_DIRS = {"__pycache__", "dist", ".git", ".in_use"}
EXCLUDE_EXT = {".pyc", ".pyo"}


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path):
    if os.path.isfile(path):
        dst = f"{path}.bak-{stamp()}"
        shutil.copy2(path, dst)
        return dst
    return ""


def load_json(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"读取失败 {path}: {exc}\n请先修好这个文件再运行安装。")


def save_json(path, data, dry):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if dry:
        print(f"  [dry-run] 将写入 {path}")
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bak = backup(path)
    if bak:
        print(f"  备份: {bak}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
    print(f"  写入: {path}")


def copy_plugin(dst, dry):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    if dry:
        print(f"  [dry-run] 将复制插件到 {dst}")
        return
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(base, ROOT)
        target = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for name in files:
            if os.path.splitext(name)[1] in EXCLUDE_EXT:
                continue
            shutil.copy2(os.path.join(base, name), os.path.join(target, name))
    print(f"  复制: {ROOT} -> {dst}")


def pin_python(installed_dir, dry):
    """把安装副本的 command 固定成本机 python 绝对路径，避免 PATH 差异。"""
    path = os.path.join(installed_dir, ".mcp.json")
    data = load_json(path, {})
    cmd = sys.executable
    changed = False
    for cfg in (data.get("mcpServers") or {}).values():
        if cfg.get("command") != cmd:
            cfg["command"] = cmd
            changed = True
    if changed:
        if dry:
            print(f"  [dry-run] 将把 command 固定为 {cmd}")
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            print(f"  command 固定为 {cmd}")


def install_marketplace(home, dry, pin):
    name = plugin_name()
    market_dir = os.path.join(home, "plugins", "marketplaces", MARKET_NAME)
    plugin_dir = os.path.join(market_dir, "plugins", name)
    print("注册本地市场：")
    plugins_dir = os.path.join(market_dir, "plugins")
    if os.path.isdir(plugins_dir):
        for stale in sorted(os.listdir(plugins_dir)):
            if stale == name or stale.startswith("."):
                continue
            stale_path = os.path.join(plugins_dir, stale)
            if os.path.isdir(stale_path) and os.path.isfile(
                    os.path.join(stale_path, ".codebuddy-plugin", "plugin.json")):
                if dry:
                    print(f"  [dry-run] 将清理旧版本目录 {stale_path}")
                else:
                    shutil.rmtree(stale_path)
                    print(f"  清理旧版本目录: {stale_path}")
    copy_plugin(plugin_dir, dry)
    if pin:
        pin_python(plugin_dir, dry)

    manifest = load_json(os.path.join(ROOT, ".codebuddy-plugin", "plugin.json"), {})
    market = {
        "name": MARKET_NAME,
        "description": "本地插件市场（由 logisim-mcp 的 install.py 创建）",
        "owner": {"name": "local"},
        "plugins": [{
            "name": name,
            "description": manifest.get("description", ""),
            "version": manifest.get("version", "0.0.0"),
            "source": f"./plugins/{name}",
            "category": manifest.get("category", ""),
        }],
    }
    save_json(os.path.join(market_dir, ".codebuddy-plugin", "marketplace.json"), market, dry)

    known_path = os.path.join(home, "plugins", "known_marketplaces.json")
    known = load_json(known_path, {})
    known[MARKET_NAME] = {
        "manifestName": MARKET_NAME,
        "type": "directory",
        "source": {"source": "directory", "path": market_dir},
        "installLocation": market_dir,
        "description": "本地插件市场（logisim-mcp）",
        "lastUpdated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "autoUpdate": False,
        "isBuiltIn": False,
    }
    save_json(known_path, known, dry)

    print("\n下一步（必须手动做）：")
    print("  1. 打开插件/连接器管理页，在市场列表里选 logisim-local，安装 logisim-mcp；")
    print("  2. 到右上角「自定义连接器」入口，对 logisim 点一次「信任（Trust）」；")
    print("  3. 新会话里说「用 logisim 工具体检 xxx.circ」即可。")


def install_mcp(home, dry, pin):
    path = os.path.join(home, "mcp.json")
    data = load_json(path, {"mcpServers": {}})
    data.setdefault("mcpServers", {})["logisim"] = {
        "type": "stdio",
        "command": sys.executable if pin else "python",
        "args": [os.path.join(ROOT, "server", "server.py")],
        "cwd": ROOT,
        "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    }
    print(f"写入 MCP 配置（{path}）：")
    save_json(path, data, dry)
    print("\n下一步：保存后 MCP 不会自动生效，去连接器管理页右上角「自定义连接器」点一次 Trust。")


def uninstall(home, dry):
    print("撤销安装：")
    known_path = os.path.join(home, "plugins", "known_marketplaces.json")
    known = load_json(known_path, {})
    if MARKET_NAME in known:
        known.pop(MARKET_NAME)
        save_json(known_path, known, dry)
    market_dir = os.path.join(home, "plugins", "marketplaces", MARKET_NAME)
    if os.path.isdir(market_dir):
        if dry:
            print(f"  [dry-run] 将删除 {market_dir}")
        else:
            shutil.rmtree(market_dir)
            print(f"  删除: {market_dir}")
    mcp_path = os.path.join(home, "mcp.json")
    data = load_json(mcp_path, {"mcpServers": {}})
    if "logisim" in (data.get("mcpServers") or {}):
        data["mcpServers"].pop("logisim")
        save_json(mcp_path, data, dry)
    print("  插件源码目录未动：" + ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=os.path.expanduser("~/.workbuddy"),
                    help="WorkBuddy 配置根目录，默认 ~/.workbuddy")
    ap.add_argument("--mcp-only", action="store_true", help="只写 mcp.json，不注册市场")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--no-pin-python", action="store_true", help="不把 command 固定为当前解释器")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    home = os.path.abspath(os.path.expanduser(args.home))
    if not os.path.isdir(home):
        raise SystemExit(f"没有找到 {home}，请确认 WorkBuddy 已安装，或用 --home 指定。")
    pin = not args.no_pin_python
    print(f"插件根目录: {ROOT}")
    print(f"配置根目录: {home}\n")

    if args.uninstall:
        uninstall(home, args.dry_run)
    elif args.mcp_only:
        install_mcp(home, args.dry_run, pin)
    else:
        install_marketplace(home, args.dry_run, pin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
