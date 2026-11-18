#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从截图里识别数码管亮了哪几段（不给肉眼缩放也能复核 A~F）

做法（2.16 截图实测）：
  1) 数码管外框是深灰/近黑细线 → 按「三通道接近且整体偏暗」取边框像素；
  2) 按 x 间隙聚类成一个个管子，用边框求包围盒；
  3) 在盒内按七段位置采样，红色占比 > 0.35 记为亮。

用法：
    python segshot.py shot.png                       # 只报每只管子的亮段
    python segshot.py shot.png --expect A,b,C,d,E,F  # 顺带比对期望字模
    python segshot.py shot.png --band 190,420        # 限定纵向范围（像素）

限制：只认 Logisim 默认红色（#ff0000 系）；若被缩放得很小（管子宽度 < 20px）会跳过。
"""
from __future__ import annotations

import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("需要 Pillow：pip install pillow", file=sys.stderr)
    raise SystemExit(2)

PAT = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
       "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
       "A": "abcefg", "b": "cdefg", "C": "adef", "d": "bcdeg", "E": "adefg", "F": "aefg"}
# 七段在字框内的相对位置 (x0,y0,x1,y1)
REGIONS = {"a": (.22, .04, .78, .22), "f": (.02, .20, .26, .46), "b": (.74, .20, .98, .46),
           "g": (.22, .42, .78, .62), "e": (.02, .58, .26, .84), "c": (.74, .58, .98, .84),
           "d": (.22, .80, .78, .98)}


def is_red(p):
    r, g, b = p
    return r > 150 and g < 120 and b < 120


def is_frame(p):
    r, g, b = p
    lo, hi = min(r, g, b), max(r, g, b)
    return hi - lo < 26 and 25 <= (r + g + b) // 3 <= 120


def analyze(path, band=None, expect=None, thr=0.35):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    y0, y1 = band if band else (0, H)

    cols = [sum(1 for y in range(y0, y1) if is_frame(px[x, y])) for x in range(W)]
    runs, cur = [], None
    for x, n in enumerate(cols):
        if n and cur is None:
            cur = x
        elif not n and cur is not None:
            if x - cur >= 6:
                runs.append((cur, x - 1))
            cur = None
    if cur is not None:
        runs.append((cur, W - 1))

    boxes = []
    for a, b in runs:
        ys = [y for y in range(y0, y1) for x in range(a, b + 1) if is_frame(px[x, y])]
        if not ys:
            continue
        h = max(ys) - min(ys)
        if 20 <= (b - a) <= 260 and 30 <= h <= 320:
            boxes.append((a, min(ys), b, max(ys)))
    if not boxes:
        print("没找到数码管：试试 --band 限定纵向范围，或放大截图")
        return 1

    print(f"找到 {len(boxes)} 个数码管")
    ok_all = True
    for k, (a, t, b, bt) in enumerate(boxes):
        w, h = b - a, bt - t

        def frac(rx0, ry0, rx1, ry1):
            tot = red = 0
            for x in range(int(a + rx0 * w), int(a + rx1 * w) + 1):
                for y in range(int(t + ry0 * h), int(t + ry1 * h) + 1):
                    tot += 1
                    if is_red(px[x, y]):
                        red += 1
            return red / tot if tot else 0.0

        fr = {s: frac(*REGIONS[s]) for s in "abcdefg"}
        on = "".join(s for s in "abcdefg" if fr[s] > thr)
        msg = ""
        if expect and k < len(expect):
            want = "".join(sorted(PAT.get(expect[k], "")))
            good = "".join(sorted(on)) == want
            ok_all &= good
            msg = f"  期望 {expect[k]}={want} {'OK' if good else '✗'}"
        print(f"  #{k + 1} @({a},{t})-({b},{bt}) 亮={on}{msg}")
        print("      " + " ".join(f"{s}={fr[s]:.2f}" for s in "abcdefg"))
    return 0 if ok_all else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    band = None
    if "--band" in sys.argv:
        band = tuple(int(v) for v in sys.argv[sys.argv.index("--band") + 1].split(","))
    expect = None
    if "--expect" in sys.argv:
        expect = sys.argv[sys.argv.index("--expect") + 1].split(",")
    return analyze(path, band, expect)


if __name__ == "__main__":
    sys.exit(main())