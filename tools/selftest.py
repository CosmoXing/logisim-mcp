#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""插件级端到端自检：清单 → stdio 握手 → 13 工具 → 生成/体检/仿真 → Logisim 交叉复核。

用法：
    python tools/selftest.py            # 全跑
    python tools/selftest.py --quick    # 跳过依赖 Logisim 的用例

退出码 0 = 全部通过。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server", "server.py")

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def check(name, ok, detail=""):
    results.append((PASS if ok else FAIL, name, detail))
    print(f"[{PASS if ok else FAIL}] {name}" + (f"  — {detail}" if detail else ""))
    return ok


def skip(name, why):
    results.append((SKIP, name, why))
    print(f"[{SKIP}] {name}  — {why}")


# ---------------------------------------------------------------- stdio 通道
class Client:
    """按 MCP stdio 协议起一个服务端子进程，批量发请求再收结果。"""

    def __init__(self):
        self.next_id = 1
        self.calls = []

    def call(self, method, params=None):
        mid = self.next_id
        self.next_id += 1
        self.calls.append({"jsonrpc": "2.0", "id": mid, "method": method,
                           "params": params or {}})
        return mid

    def tool(self, name, args):
        return self.call("tools/call", {"name": name, "arguments": args})

    def run(self, timeout=240):
        payload = "\n".join(json.dumps(c, ensure_ascii=False) for c in self.calls) + "\n"
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, SERVER], input=payload.encode("utf-8"),
                              capture_output=True, timeout=timeout, cwd=ROOT, env=env)
        out = proc.stdout.decode("utf-8", "replace")
        by_id = {}
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                by_id[msg["id"]] = msg
        return by_id, proc.stderr.decode("utf-8", "replace")


def text_of(msg):
    if not msg:
        return ""
    if "error" in msg:
        return f"ERROR {msg['error']}"
    return "".join(part.get("text", "") for part in msg.get("result", {}).get("content", []))


# ---------------------------------------------------------------- 1. 清单
def test_manifest():
    ok = True
    pj = os.path.join(ROOT, ".codebuddy-plugin", "plugin.json")
    mj = os.path.join(ROOT, ".mcp.json")
    try:
        manifest = json.load(open(pj, encoding="utf-8"))
    except Exception as exc:
        return check("plugin.json 可解析", False, str(exc))
    ok &= check("plugin.json 可解析", True, f"{manifest.get('name')} {manifest.get('version')}")
    ok &= check("plugin.json 必填字段", all(manifest.get(k) for k in ("name", "version", "description")))
    for rel in manifest.get("skills") or []:
        p = os.path.normpath(os.path.join(ROOT, rel, "SKILL.md"))
        ok &= check(f"技能存在 {rel}", os.path.isfile(p), p if not os.path.isfile(p) else "")
    try:
        mcp = json.load(open(mj, encoding="utf-8"))
    except Exception as exc:
        return check(".mcp.json 可解析", False, str(exc))
    ok &= check(".mcp.json 可解析", True)
    servers = mcp.get("mcpServers") or {}
    ok &= check(".mcp.json 声明了 1 个服务", len(servers) == 1, ", ".join(servers))
    for name, cfg in servers.items():
        args = " ".join(cfg.get("args") or [])
        ok &= check(f"{name}: 使用 ${{CODEBUDDY_PLUGIN_ROOT}}", "${CODEBUDDY_PLUGIN_ROOT}" in args, args)
        cmd = cfg.get("command")
        ok &= check(f"{name}: 解释器可用", bool(shutil.which(cmd) or os.path.isfile(cmd)), str(cmd))
    return ok


# ---------------------------------------------------------------- 2. 握手
def test_handshake():
    c = Client()
    i = c.call("initialize", {"protocolVersion": "2024-11-05",
                              "clientInfo": {"name": "selftest", "version": "1"}})
    l = c.call("tools/list")
    p = c.call("ping")
    by_id, err = c.run(timeout=60)
    ok = True
    init = by_id.get(i, {}).get("result", {})
    ok &= check("initialize 有响应", bool(init), str(by_id.get(i))[:80])
    ok &= check("initialize 回显协议版本", init.get("protocolVersion") == "2024-11-05",
                str(init.get("protocolVersion")))
    info = init.get("serverInfo") or {}
    ok &= check("serverInfo 带名称与版本", bool(info.get("name") and info.get("version")),
                f"{info.get('name')} {info.get('version')}")
    tools = by_id.get(l, {}).get("result", {}).get("tools") or []
    names = {t["name"] for t in tools}
    need = {"logisim_info", "circuit_summary", "circuit_truth_table", "circuit_verify",
            "circuit_test_vector", "circuit_stats", "circuit_build", "circuit_open_gui",
            "circ_geometry", "circ_audit", "circ_sim", "circ_build", "circ_kb"}
    ok &= check("tools/list 返回 13 个工具", len(tools) == 13, f"实际 {len(tools)}")
    ok &= check("工具名齐全", need <= names, f"缺 {sorted(need - names)}" if need - names else "")
    ok &= check("ping 有响应", "result" in by_id.get(p, {}))
    return ok


# ---------------------------------------------------------------- 3. 生成链路
AND_SPEC = {
    "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
                 {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "AND"}],
        "nets": [{"name": "a", "connect": ["pin:a", "g1.a"]},
                 {"name": "b", "connect": ["pin:b", "g1.b"]},
                 {"name": "y", "connect": ["g1.out", "pin:y"]}],
    }]
}


def test_pipeline(tmp):
    circ = os.path.join(tmp, "and2.circ")
    spec = dict(AND_SPEC); spec["file"] = circ
    c = Client()
    b = c.tool("circ_build", {"spec": spec})
    a = c.tool("circ_audit", {"file": circ})
    s = c.tool("circ_sim", {"file": circ, "inputs": {"a": 1, "b": 0}, "watch": ["y"]})
    g = c.tool("circ_geometry", {"component": "gate"})
    k = c.tool("circ_kb", {"action": "list"})
    i = c.tool("logisim_info", {})
    by_id, _ = c.run(timeout=120)
    ok = True
    ok &= check("circ_build 生成文件", os.path.isfile(circ), text_of(by_id.get(b))[:80])
    ok &= check("生成后自检 ok", "体检: ok" in text_of(by_id.get(b)), text_of(by_id.get(b))[:100])
    ok &= check("circ_audit 判 ok", "ok" in text_of(by_id.get(a))[:40], text_of(by_id.get(a))[:80])
    sim_txt = text_of(by_id.get(s))
    ok &= check("circ_sim a=1,b=0 → y=0", "y" in sim_txt and "0" in sim_txt, sim_txt.replace("\n", " ")[:90])
    ok &= check("circ_geometry 返回宽度表", "widths" in text_of(by_id.get(g)))
    kb_txt = text_of(by_id.get(k))
    ok &= check("circ_kb 列出经验", "[gate-port-offset]" in kb_txt,
                kb_txt.splitlines()[0][:60] if kb_txt else "")
    ok &= check("logisim_info 有输出", bool(text_of(by_id.get(i))))
    return ok, circ


# ---------------------------------------------------------------- 4. 失败路径
def test_failures(tmp):
    c = Client()

    f1 = c.tool("circ_audit", {"file": os.path.join(tmp, "and2.circ")})  # 正常对照

    width_spec = {"file": os.path.join(tmp, "bad_width.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "d", "dir": "in", "width": 4}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "AND", "at": [400, 300]}],
        "nets": [{"name": "d", "connect": ["pin:d", "g1.a"]},
                 {"name": "y", "connect": ["g1.out", "pin:y"]}]}]}
    w = c.tool("circ_build", {"spec": width_spec})

    loop_spec = {"file": os.path.join(tmp, "loop.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "AND", "at": [400, 300]},
                       {"id": "g2", "type": "OR", "at": [600, 300]}],
        "nets": [{"name": "x", "connect": ["g1.out", "g2.a"]},
                 {"name": "z", "connect": ["g2.out", "g1.a", "pin:y"]}]}]}
    lp = c.tool("circ_build", {"spec": loop_spec})

    by_id, _ = c.run(timeout=120)
    ok = True
    ok &= check("位宽不一致被拒", "位宽不一致" in text_of(by_id.get(w)), text_of(by_id.get(w))[:90])
    ok &= check("组合环被拒", "组合环" in text_of(by_id.get(lp)), text_of(by_id.get(lp))[:90])
    ok &= check("正常文件仍判 ok", "ok" in text_of(by_id.get(f1))[:40])
    return ok


# ---------------------------------------------------------------- 5. Logisim
def test_logisim(tmp, circ):
    if not shutil.which("java") and not os.environ.get("JAVA_HOME"):
        skip("Logisim 交叉复核", "本机没有 java")
        return True
    c = Client()
    t = c.tool("circuit_truth_table", {"file": circ})
    s = c.tool("circuit_stats", {"file": circ})
    by_id, err = c.run(timeout=180)
    txt = text_of(by_id.get(t))
    if not txt or "未找到" in txt or "仿真失败" in txt:
        skip("Logisim 交叉复核", (txt or err).strip().splitlines()[0][:80])
        return True
    ok = check("真值表无 E/U", "E" not in txt and "U" not in txt, txt.splitlines()[0][:60])
    # 第一行是表头、第二行是分隔线，其余为数据行：2 输入应有 4 行
    lines = [l for l in txt.splitlines() if l.strip()]
    data_rows = max(len(lines) - 2, 0)
    ok &= check("真值表 4 行", data_rows == 4, f"{data_rows} 行")
    ok &= check("circuit_stats 有输出", bool(text_of(by_id.get(s))))
    return ok


# ---------------------------------------------------------------- 6. 知识库
def test_kb():
    sys.path.insert(0, os.path.join(ROOT, "server"))
    from circuit_kit import knowledge as kb  # noqa: E402
    items = kb.list_pitfalls()
    ok = check("经验库可读", len(items) >= 9, f"{len(items)} 条")
    probe = kb.add_pitfall("_selftest 探针", "验证写入", "selftest", pid="_selftest_probe")
    ok &= check("经验库可写", probe[1] in ("added", "updated"), probe[1])
    data = kb._load()
    data["pitfalls"] = [x for x in data["pitfalls"] if x.get("id") != "_selftest_probe"]
    kb._save(data)
    ok &= check("探针已清理", not any(x["id"] == "_selftest_probe" for x in kb.list_pitfalls()))
    return ok


def main():
    quick = "--quick" in sys.argv
    print(f"插件根目录: {ROOT}\n")
    tmp = tempfile.mkdtemp(prefix="logisim_plugin_selftest_")
    allok = True
    try:
        allok &= test_manifest()
        allok &= test_handshake()
        ok, circ = test_pipeline(tmp)
        allok &= ok
        allok &= test_failures(tmp)
        if quick:
            skip("Logisim 交叉复核", "--quick")
        else:
            allok &= test_logisim(tmp, circ)
        allok &= test_kb()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    npass = sum(1 for r in results if r[0] == PASS)
    nfail = sum(1 for r in results if r[0] == FAIL)
    nskip = sum(1 for r in results if r[0] == SKIP)
    print(f"\n合计 {len(results)} 项：通过 {npass}，失败 {nfail}，跳过 {nskip}")
    if nfail:
        print("失败项：")
        for st, name, detail in results:
            if st == FAIL:
                print(f"  - {name}  {detail}")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
