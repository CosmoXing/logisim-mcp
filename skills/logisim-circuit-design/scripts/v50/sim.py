"""用 Logisim 本体跑向量测试的小工具（时序用 <set> <seq> 列）。

用法：
    from sim import run, verify_alive
    res = run("2.3.circ", "mul", "a[8] b[8] q[8] <set> <seq>", rows)
    ok, bad, txt = res          # ok/bad 为 None 表示向量根本没被执行

JAR 自动探测顺序：LOGISIM_JAR 环境变量 → D:/app/ → C:/Program Files/ → PATH。
"""
import os
import re
import shutil
import subprocess


def find_jar():
    env = os.environ.get("LOGISIM_JAR")
    if env and os.path.exists(env):
        return env
    for base in ("D:/app", "D:/", "C:/app"):
        if os.path.isdir(base):
            hits = sorted(f for f in os.listdir(base)
                          if f.lower().startswith("logisim") and f.endswith(".jar"))
            if hits:
                return os.path.join(base, hits[-1])
    p = shutil.which("logisim") or shutil.which("logisim-evolution")
    return p


def run(circ_file, circ_name, header, rows, timeout=300, jar=None):
    """跑一遍向量。返回 (通过数, 失败数, 原始输出)；前两个为 None = 没执行。

    ⚠️ 即使返回 通过=N 失败=0，也要确认 N == len(rows)：
    列数不匹配时 Logisim 会静默跳过整行，`通过` 依然出现（假通过）。
    """
    jar = jar or find_jar()
    open("_t.vec", "w", encoding="utf-8", newline="\n").write(
        header + "\n" + "\n".join(rows) + "\n")
    r = subprocess.run(["java", "-jar", jar, "-w", circ_name, "_t.vec", circ_file],
                       capture_output=True, timeout=timeout)
    txt = r.stdout.decode("gbk", "ignore")
    m = re.search(r"通过：(\d+)，失败：(\d+)", txt)
    if m:
        return int(m.group(1)), int(m.group(2)), txt
    return None, None, txt


def verify_alive(res, n_rows):
    """防假通过：通过数必须等于行数，否则视为向量没真正比对。"""
    ok, bad, _ = res
    if ok is None:
        raise RuntimeError("向量未被执行（列名不匹配或文件加载失败）")
    if ok != n_rows:
        raise RuntimeError(f"通过数 {ok} != 行数 {n_rows}，存在被静默跳过的行")


def clk_seq(rows):
    """把每行 (向量, 期望) 展开成 clk=0 / clk=1 两行，返回可直接喂 run() 的列表。

    输入元素形如 "a b c 期望..." 的字符串，自动追加 0/1 到 clk 列
    （clk 列必须紧跟输入、在期望列之前——自己拼表头时注意列序）。
    """
    out = []
    for r in rows:
        out.append(r + " 0")
        out.append(r + " 1")
    return out
