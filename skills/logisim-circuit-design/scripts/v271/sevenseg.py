#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数码管（7-Segment Display）工具：段位核对 / 真值表核对 / 生成 A~F 演示
适用：Logisim-ITA 2.16（也适用 2.7.1，几何取自 SevenSegment.class 反编译）

三条子命令：
    python sevenseg.py check  file.circ "七段显示0~F"
        核对「译码器 a~g → 数码管 a~g」是否一一对应，并检查 active 属性
        （active 是布尔属性，写 high/low 会被当成 false → 整块反相，see pitfalls L1）

    python sevenseg.py table  file.circ "七段译码器0~F"
        用 ita_probe 跑 D=0..15，与标准十六进制字模逐行比对

    python sevenseg.py demo   file.circ "思考题1 A~F显示"  [--from 10 --to 15]
        追加一个「N 个数码管并排、常数直接驱动译码器」的演示电路（无隧道）

端口坐标（2.16 实测，相对元件 loc）：
    a=(+20,0)  b=(+30,0)  c=(+20,+60)  d=(+10,+60)
    e=(0,+60)  f=(+10,0)  g=(0,0)      dp=(+30,+60)      外框 Bounds(-5,0,40,60)
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ita_probe  # noqa: E402
import netmap  # noqa: E402

SEG = {"a": (20, 0), "b": (30, 0), "c": (20, 60), "d": (10, 60),
       "e": (0, 60), "f": (10, 0), "g": (0, 0), "dp": (30, 60)}
GLYPH = (-5, 0, 40, 60)
# 标准十六进制字模（七段：a 上横、b 右上、c 右下、d 下横、e 左下、f 左上、g 中横）
HEX = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg", 5: "acdfg",
       6: "acdefg", 7: "abc", 8: "abcdefg", 9: "abcdfg",
       10: "abcefg", 11: "cdefg", 12: "adef", 13: "bcdeg", 14: "adefg", 15: "aefg"}
LETTER = {10: "A", 11: "b", 12: "C", 13: "d", 14: "E", 15: "F"}
DECODER = "七段译码器0~F"
DISPLAY = "7-Segment Display"


def _pair(circ: str, circuit: str, decoder: str, display: str):
    comps = ita_probe.ends(circ, circuit)
    decs = sorted([c for c in comps if c["comp"] == decoder], key=lambda c: c["loc"][0])
    disps = sorted([c for c in comps if c["comp"] == display], key=lambda c: c["loc"][0])
    return decs, disps


def _decoder_out_names(comp) -> list[tuple[str, tuple[int, int]]]:
    """默认外观按内部 Pin 的 y 排序、10px 打包 → 输出脚自上而下就是 a..g。"""
    outs = sorted([p["loc"] for p in comp["ports"] if p["dir"] == "out"], key=lambda q: q[1])
    return list(zip("abcdefg", outs))


def check(circ: str, circuit: str, decoder: str = DECODER, display: str = DISPLAY) -> bool:
    decs, disps = _pair(circ, circuit, decoder, display)
    if not decs or not disps:
        print(f"[!] {circuit}: 找到译码器 {len(decs)} 个、数码管 {len(disps)} 个，无法配对")
        return False
    net = netmap.Net(netmap.read_wires(circ, circuit))
    ok_all = True
    for k, (d, s) in enumerate(zip(decs, disps)):
        dx, dy = s["loc"]
        loc2name = {(dx + o[0], dy + o[1]): nm for nm, o in SEG.items()}
        row, ok = [], True
        for nm, pl in _decoder_out_names(d):
            hit = [loc2name[q] for q in loc2name if net.at(q) & net.at(pl)]
            good = hit == [nm]
            ok &= good
            row.append(f"{nm}→{hit[0] if hit else '×'}{'' if good else '✗'}")
        ok_all &= ok
        print(f"  第{k + 1}组 @{d['loc']} → @{s['loc']}: " + " ".join(row) + ("" if ok else "  [错]"))

    # active 属性（布尔；high/low 会被解析成 false → 反相）
    s = io.open(circ, encoding="utf-8").read()
    i = s.index(f'<circuit name="{circuit}">')
    blk = s[i:s.index("</circuit>", i)]
    vals = set()
    for m in re.finditer(r'name="7-Segment Display">(.*?)</comp>', blk, re.S):
        a = re.search(r'name="active" val="([^"]*)"', m.group(1))
        vals.add(a.group(1) if a else "(未写=默认 true)")
    print("  active 取值:", ", ".join(sorted(vals)))
    for v in vals:
        if v not in ("true", "false", "(未写=默认 true)", "True", "False"):
            print(f"  [!] active=\"{v}\" 不是合法布尔值 → 会被当成 false，数码管反相（见 L1）")
            ok_all = False
    print("  →", "全部正确" if ok_all else "存在问题")
    return ok_all


def table(circ: str, circuit: str) -> bool:
    vec = os.path.join(tempfile.gettempdir(), "sevenseg.vec")
    with io.open(vec, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("D a b c d e f g\n")
        for i in range(16):
            fh.write("%d x x x x x x x\n" % i)
    res = ita_probe.run_vector(circ, vec, circuit, trace=True)
    ok_all, n = True, 0
    for line in res["log"].splitlines():
        if not line.startswith("TRACE"):
            continue
        d = dict(re.findall(r"(\S+)=(\S+)", line))
        v = int(d["D"], 16)
        on = "".join(s_ for s_ in "abcdefg" if int(d.get(s_, "0"), 16))
        exp = "".join(sorted(HEX[v]))
        good = "".join(sorted(on)) == exp
        ok_all &= good
        n += 1
        print("  %s D=%2d(%s) 亮=%s 期望=%s" % ("OK " if good else "BAD", v,
                                               LETTER.get(v, str(v)), on, exp))
    print(f"  → {n}/16 行通过" if ok_all else "  → 有错")
    return ok_all and n == 16


def demo(circ_path: str, name: str, decoder: str = DECODER,
         v0: int = 10, v1: int = 15) -> None:
    s = io.open(circ_path, encoding="utf-8").read()
    if f'<circuit name="{name}">' in s:
        raise SystemExit(f"电路 {name} 已存在")
    Y, step, n = 200, 320, v1 - v0 + 1
    parts = [f'    <a name="circuit" val="{name}"/>',
             '    <a name="clabel" val=""/>',
             '    <a name="clabelup" val="east"/>',
             '    <a name="clabelfont" val="SansSerif plain 12"/>',
             '    <a name="clabelcolor" val="#000000"/>']
    # 7 段走线：译码器输出脚(a..g) → 数码管脚，各自独立通道 + 独立水平层
    routes = [("a", 0, 80, -30, 280, 30), ("b", 1, 90, -40, 290, 30),
              ("c", 2, 100, 150, 280, 90), ("d", 3, 110, 160, 270, 90),
              ("e", 4, 120, 170, 260, 90), ("f", 5, 130, -50, 270, 30),
              ("g", 6, 140, -60, 260, 30)]
    for i in range(n):
        X, v = 200 + i * step, v0 + i
        parts += [
            f'    <comp lib="0" loc="({X},{Y + 30})" name="Constant">',
            '      <a name="width" val="4"/>',
            f'      <a name="value" val="0x{v:X}"/>',
            '    </comp>',
            f'    <comp loc="({X + 60},{Y + 30})" name="{decoder}"/>',
            f'    <comp lib="5" loc="({X + 260},{Y + 30})" name="{DISPLAY}">',
            '      <a name="active" val="true"/>',          # 必须布尔 true（L1）
            '      <a name="color" val="#ff0000"/>',
            '      <a name="offcolor" val="#c8c8c8"/>',
            '      <a name="background" val="#ffffff"/>',
            '    </comp>',
            f'    <comp lib="6" loc="({X + 275},{Y + 130})" name="Text">',
            f'      <a name="text" val="{v:04b} → {LETTER.get(v, str(v))}"/>',
            '      <a name="font" val="SansSerif plain 14"/>',
            '      <a name="color" val="#000000"/>',
            '      <a name="halign" val="center"/>',
            '      <a name="valign" val="base"/>',
            '    </comp>',
            f'    <wire from="({X},{Y + 30})" to="({X},{Y + 60})"/>',
            f'    <wire from="({X},{Y + 60})" to="({X + 30},{Y + 60})"/>',
        ]
        for _nm, k, ch, lvl, px, py in routes:
            oy = Y + 30 + 10 * k
            parts += [
                f'    <wire from="({X + 60},{oy})" to="({X + ch},{oy})"/>',
                f'    <wire from="({X + ch},{oy})" to="({X + ch},{Y + lvl})"/>',
                f'    <wire from="({X + ch},{Y + lvl})" to="({X + px},{Y + lvl})"/>',
                f'    <wire from="({X + px},{Y + lvl})" to="({X + px},{Y + py})"/>',
            ]
    parts += [
        '    <comp lib="6" loc="(%d,120)" name="Text">' % (200 + (n - 1) * step // 2 + 275),
        f'      <a name="text" val="数码管驱动真值表扩充：显示 {LETTER.get(v0, str(v0))}~{LETTER.get(v1, str(v1))}'
        '（b、d 为七段管通用的小写写法）"/>',
        '      <a name="font" val="SansSerif bold 14"/>',
        '      <a name="color" val="#000000"/>',
        '      <a name="halign" val="center"/>',
        '      <a name="valign" val="base"/>',
        '    </comp>',
    ]
    block = f'<circuit name="{name}">\n' + "\n".join(parts) + "\n</circuit>\n"
    s = s.replace("</project>", block + "</project>")
    io.open(circ_path, "w", encoding="utf-8", newline="\n").write(s)
    print(f"已追加电路 {name}（{n} 组，{v0}~{v1}）")
    print("  errors:", ita_probe.errors(circ_path, name)[:2])


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, circ, circuit = sys.argv[1], sys.argv[2], sys.argv[3]
    decoder = sys.argv[sys.argv.index("--decoder") + 1] if "--decoder" in sys.argv else DECODER
    if cmd == "check":
        sys.exit(0 if check(circ, circuit, decoder) else 1)
    elif cmd == "table":
        sys.exit(0 if table(circ, circuit) else 1)
    elif cmd == "demo":
        v0 = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 10
        v1 = int(sys.argv[sys.argv.index("--to") + 1]) if "--to" in sys.argv else 15
        demo(circ, circuit, decoder, v0, v1)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()