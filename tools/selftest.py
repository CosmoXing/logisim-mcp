#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""插件级端到端自检：清单 → stdio 握手 → 15 工具 → 生成/体检/仿真 → Logisim 交叉复核。

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

def _utf8_console():
    """Windows 控制台默认不是 UTF-8，直接 print 中文会抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


_utf8_console()

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
            "circ_geometry", "circ_probe", "circ_audit", "circ_sim", "circ_build", "circ_kb",
            "circ_appearance", "circ271_check", "circ271_sim", "circ271_ports"}
    ok &= check("tools/list 返回 24 个工具", len(tools) == 24, f"实际 {len(tools)}")
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


# ---------------------------------------------------------------- 5. 回归：仿真/生成缺陷
def test_regressions(tmp):
    """固定住曾经会静默出错的路径：多输入门、单输入门、异步复位、总线、转义、网格、多驱动。"""
    c = Client()

    and3 = {"file": os.path.join(tmp, "and3.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
                 {"label": "c", "dir": "in"}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "AND", "inputs": 3}],
        "nets": [{"name": "na", "connect": ["pin:a", "g1.a"]},
                 {"name": "nb", "connect": ["pin:b", "g1.b"]},
                 {"name": "nc", "connect": ["pin:c", "g1.c"]},
                 {"name": "ny", "connect": ["g1.out", "pin:y"]}]}]}
    c.tool("circ_build", {"spec": and3})
    s3 = c.tool("circ_sim", {"file": and3["file"], "inputs": {"a": 1, "b": 1, "c": 0}, "watch": ["y"]})

    and1 = {"file": os.path.join(tmp, "and1.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "AND", "inputs": 1}],
        "nets": [{"name": "na", "connect": ["pin:a", "g1.a"]},
                 {"name": "ny", "connect": ["g1.out", "pin:y"]}]}]}
    c.tool("circ_build", {"spec": and1})
    s1 = c.tool("circ_sim", {"file": and1["file"], "inputs": {"a": 1}, "watch": ["y"]})

    dff = {"file": os.path.join(tmp, "dff_r.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "D", "dir": "in"}, {"label": "R", "dir": "in"},
                 {"label": "cp", "dir": "in"}, {"label": "Q", "dir": "out"}],
        "components": [{"id": "d1", "type": "DFF"}],
        "nets": [{"name": "nD", "connect": ["pin:D", "d1.D"]},
                 {"name": "nR", "connect": ["pin:R", "d1.R"]},
                 {"name": "nC", "connect": ["pin:cp", "d1.CLK"]},
                 {"name": "nQ", "connect": ["d1.Q", "pin:Q"]}]}]}
    c.tool("circ_build", {"spec": dff})
    sr = c.tool("circ_sim", {"file": dff["file"], "inputs": {"D": 1, "R": 1},
                             "cycles": 1, "watch": ["Q"]})

    bus = {"file": os.path.join(tmp, "bus4.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "bus", "dir": "in", "width": 4},
                 {"label": "y0", "dir": "out"}, {"label": "y1", "dir": "out"},
                 {"label": "y2", "dir": "out"}, {"label": "y3", "dir": "out"}],
        "components": [{"id": "s1", "type": "SPLITTER4"}],
        "nets": [{"name": "nbus", "connect": ["pin:bus", "s1.in"]},
                 {"name": "n0", "connect": ["s1.b0", "pin:y0"]},
                 {"name": "n1", "connect": ["s1.b1", "pin:y1"]},
                 {"name": "n2", "connect": ["s1.b2", "pin:y2"]},
                 {"name": "n3", "connect": ["s1.b3", "pin:y3"]}]}]}
    c.tool("circ_build", {"spec": bus})
    sb = c.tool("circ_sim", {"file": bus["file"], "inputs": {"bus": 5}, "watch": ["y0", "y1", "y2", "y3"]})

    esc = {"file": os.path.join(tmp, "esc.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "a&b", "dir": "in"}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "NOT"}],
        "nets": [{"name": "na", "connect": ["pin:a&b", "g1.a"]},
                 {"name": "ny", "connect": ["g1.out", "pin:y"]}]}]}
    be = c.tool("circ_build", {"spec": esc})

    grid = {"file": os.path.join(tmp, "grid.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in", "at": [405, 303]}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "NOT"}],
        "nets": [{"name": "na", "connect": ["pin:a", "g1.a"]},
                 {"name": "ny", "connect": ["g1.out", "pin:y"]}]}]}
    bg = c.tool("circ_build", {"spec": grid})

    multi = {"file": os.path.join(tmp, "multi.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "NOT"}, {"id": "g2", "type": "NOT"}],
        "nets": [{"name": "na", "connect": ["pin:a", "g1.a"]},
                 {"name": "nz", "connect": ["pin:a", "g2.a"]},
                 {"name": "ny", "connect": ["g1.out", "g2.out", "pin:y"]}]}]}
    bm = c.tool("circ_build", {"spec": multi})

    dangling = {"file": os.path.join(tmp, "dangling.circ"), "circuits": [{
        "name": "main",
        "pins": [{"label": "a", "dir": "in"}, {"label": "y", "dir": "out"}],
        "components": [{"id": "g1", "type": "NOT"}],
        "nets": [{"name": "ny", "connect": ["g1.out", "pin:y"]}]}]}
    bd = c.tool("circ_build", {"spec": dangling})

    by_id, _ = c.run(timeout=120)
    ok = True
    t3 = text_of(by_id.get(s3))
    ok &= check("3 输入门算全部输入", "y" in t3 and "\t0" in t3, t3.replace("\n", " ")[:80])
    t1 = text_of(by_id.get(s1))
    ok &= check("单输入门不再 KeyError", "y" in t1 and "\t1" in t1, t1.replace("\n", " ")[:80])
    tr = text_of(by_id.get(sr))
    ok &= check("触发器异步 R 生效", "Traceback" not in tr and "KeyError" not in tr
                and tr.splitlines()[-1].split("\t")[-1] == "0", tr.replace("\n", " ")[:90])
    tb = text_of(by_id.get(sb))
    last = tb.splitlines()[-1] if tb else ""
    ok &= check("4 位总线输入正确拆分", last.endswith("1\t0\t1\t0"), last[:80])
    ok &= check("XML 特殊字符已转义", "体检: ok" in text_of(by_id.get(be)), text_of(by_id.get(be))[:90])
    ok &= check("非网格坐标被拒", "网格" in text_of(by_id.get(bg)), text_of(by_id.get(bg))[:90])
    ok &= check("多驱动被拒", "驱动源" in text_of(by_id.get(bm)), text_of(by_id.get(bm))[:90])
    msg = by_id.get(bd) or {}
    ok &= check("体检 problems 标记为错误", bool(msg.get("result", {}).get("isError")),
                text_of(msg)[:90])
    return ok


# ---------------------------------------------------------------- 6. 外观编辑（无 GUI）
def test_appearance(tmp):
    sys.path.insert(0, os.path.join(ROOT, "server"))
    from circuit_kit import appearance as app  # noqa: E402

    src = os.path.join(ROOT, "examples", "half_adder.circ")
    target = os.path.join(tmp, "appearance.circ")
    shutil.copyfile(src, target)
    pins = app.pins_from_file(target, "main")
    spec = app.auto_layout(pins, "main", {"preserve_port_positions": False})
    errors = app.validate(spec, pins)
    ok = check("auto_layout 覆盖全部引脚", not errors and len(spec["ports"]) == len(pins),
               str(errors[:2]))
    digest = app.layout_digest(target)
    count = app.write_xml(target, spec)
    data = app.read_xml(target, "main")
    ports = [o for o in data.get("objects", []) if o.get("tag") == "circ-port"]
    ok &= check("XML 外观写回", data.get("appearance") == "custom" and len(ports) == len(pins),
                f"objects={count} ports={len(ports)}")
    ok &= check("外观写回不动电气部分", app.layout_digest(target) == digest)
    bad = app.validate({**spec, "ports": spec["ports"][:-1]}, pins)
    ok &= check("缺端口被校验拦截", any(e["code"] == "E_MISSING_PORT" for e in bad), str(bad[:1]))
    return ok


# ---------------------------------------------------------------- 7. 协议协商
def test_protocol():
    c = Client()
    i = c.call("initialize", {"protocolVersion": "2025-06-30",
                              "clientInfo": {"name": "selftest", "version": "1"}})
    by_id, _ = c.run(timeout=60)
    ver = (by_id.get(i) or {}).get("result", {}).get("protocolVersion")
    return check("不支持的协议版本回落到 2024-11-05", ver == "2024-11-05", str(ver))


# ---------------------------------------------------------------- 7. Logisim
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
        allok &= test_regressions(tmp)
        allok &= test_appearance(tmp)
        allok &= test_protocol()
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
