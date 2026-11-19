# -*- coding: utf-8 -*-
import os, sys, tempfile
sys.path.insert(0, r"c:\Users\ASUS\.trae-cn\skills\logisim-circuit-design\scripts\v271")
os.environ["LOGISIM_ITA_JAR"] = r"D:\Prigect\logism桥接\tools\Logisim-ITA-2.15.0.2.jar"
import ita_probe

CIRC = r"实验4 控制器模块.circ"

def run(name, header, rows, clk=None):
    vec = os.path.join(tempfile.gettempdir(), "lab4_%s.vec" % abs(hash(name)))
    open(vec, "w", encoding="utf-8").write(" ".join(header) + "\n" + "\n".join(rows) + "\n")
    res = ita_probe.run_vector(CIRC, vec, name, clk=clk)
    print("%-12s rows=%-4s pass=%-4s fail=%-4s" % (name, res["rows"], res["pass"], res["fail"]))
    for l in res["log"].splitlines():
        if "FAIL" in l:
            print("   ", l)
    return res

# ---- ID：8 组 XYZ 穷举
rows = []
exp = {0:(1,0,0,0,0,0,0), 1:(1,1,0,0,0,0,0), 2:(0,0,0,1,0,0,0), 3:(1,0,1,0,0,0,0),
       4:(0,1,0,0,1,0,0), 5:(0,1,0,0,0,1,0), 6:(0,1,0,0,0,0,1), 7:(0,0,0,0,0,0,0)}
for k in range(8):
    x, y, z = (k >> 2) & 1, (k >> 1) & 1, k & 1
    rows.append(" ".join(str(v) for v in (x, y, z) + exp[k]))
run("ID", ["X","Y","Z","R/W","S-B/I","RM","WM","JP","JZ","JC"], rows)

# ---- PC：RST 清 0，TC_en 每次 +1；JSel=1 时加 Offset
rows = ["1 0 0 0 0 0x0", "1 1 0 0 0 0x0", "0 0 0 0 0 0x0"]
for i in range(1, 6):
    rows += [f"0 0 1 0 0 0x{i-1}", f"0 1 1 0 0 0x{i}"]
rows += ["0 0 1 0x10 1 0x5", "0 1 1 0x10 1 0x15"]
run("PC", ["RST","CLK","TC_en","Offset","JSel","P_addr"], rows, clk="CLK")

# ---- IR：TF=1 时，CLK 上升沿锁存 I-in
rows = ["0x1234 0 1 0 <DC>", "0x1234 1 1 0 <DC>", "0x1234 0 1 0 0x1234",
        "0xabcd 0 1 0 0x1234", "0xabcd 1 1 0 <DC>", "0xabcd 0 1 0 0xabcd"]
run("IR", ["I-in","CLK","TF","RST","I_out"], rows, clk="CLK")

# ---- CLK 模块：T0..T3 循环
rows = ["0 0 <DC> <DC> <DC> <DC>", "1 0 <DC> <DC> <DC> <DC>", "0 0 <DC> <DC> <DC> <DC>"]
run("CLK 模块", ["CLK","RST","T0","T1","T2","T3"], rows, clk="CLK")

# ---- S-I/B：sgnl=0 选 B，sgnl=1 选立即数 I（零扩展）
rows = ["0x5a 0x7 0 0x5a", "0x5a 0x7 1 0x07"]
run("S-I/B", ["B","I","sgnl","Out"], rows)

# ---- Flag：en=1 时，CLK 上升沿写入 D
rows = ["0xa 1 0 <DC>", "0xa 1 1 <DC>", "0xa 1 0 0xa", "0x5 1 0 0xa", "0x5 1 1 <DC>", "0x5 1 0 0x5"]
run("Flag", ["D","en","CLK","Q"], rows, clk="CLK")