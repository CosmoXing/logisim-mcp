# -*- coding: utf-8 -*-
import os, sys, tempfile
sys.path.insert(0, r"c:\Users\ASUS\.trae-cn\skills\logisim-circuit-design\scripts\v271")
os.environ["LOGISIM_ITA_JAR"] = r"D:\Prigect\logism桥接\tools\Logisim-ITA-2.15.0.2.jar"
import ita_probe

CIRC = r"实验7 IO接口实验.circ"
SEGMENTS = {
    "g": {0, 2, 3, 5, 6, 8, 9}, "f": {0, 1, 3, 4, 5, 6, 7, 8, 9},
    "a": {0, 2, 3, 5, 6, 7, 8, 9}, "b": {0, 1, 2, 3, 4, 7, 8, 9},
    "e": {0, 2, 6, 8}, "d": {0, 2, 3, 5, 6, 8, 9}, "c": {0, 1, 3, 4, 5, 6, 7, 8, 9},
}

def run(name, header, rows):
    vec = os.path.join(tempfile.gettempdir(), "lab7a_%s.vec" % name)
    open(vec, "w", encoding="utf-8").write(" ".join(header) + "\n" + "\n".join(rows) + "\n")
    res = ita_probe.run_vector(CIRC, vec, name)
    print("%-10s rows=%-4s pass=%-4s fail=%-4s" % (name, res["rows"], res["pass"], res["fail"]))
    for l in res["log"].splitlines():
        if "FAIL" in l:
            print("   ", l)
    return res

# LED计数
rows = []
for k in range(32):
    bits = [(k >> i) & 1 for i in range(5)]  # a..e
    outs = [int(any(bits[i:])) for i in range(5)]
    rows.append(" ".join(str(v) for v in bits + outs))
run("LED计数", ["a", "b", "c", "d", "e", "w", "x", "y", "z", "u"], rows)

# 按键编码器（真值表只定义一个按键按下的情况）
rows = []
rows.append("0 0 0 0 0 0 0 0 0")
for i in range(5):
    bits = [0] * 5
    bits[i] = 1
    code = i + 1
    rows.append(" ".join(str(v) for v in bits + [(code >> b) & 1 for b in range(4)]))
run("按键编码器", ["a", "b", "c", "d", "e", "C0", "C1", "C2", "C3"], rows)

# 七段显示驱动
rows = []
for v in range(16):
    bits = [(v >> i) & 1 for i in range(4, -1, -1)][1:]  # In1..In4 = b3..b0
    vals = [1 if v in SEGMENTS[s] else 0 for s in "gfabedc"]
    rows.append(" ".join(str(x) for x in bits + vals))
run("七段显示驱动", ["In1", "In2", "In3", "In4", "g", "f", "a", "b", "e", "d", "c"], rows)