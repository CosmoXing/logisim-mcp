# -*- coding: utf-8 -*-
"""把 3.9 文件里的一个 <circuit> 块原样拼到另一个 3.9 文件末尾。

用于"学生误删了某个电路"的场景：从生成器产物里取回该电路，塞回他手里的文件，
其余电路一字不动。

用法：
    python restore_block.py 目标.circ 源.circ 电路名 [新名字]

注意：3.9 的电路除了 <circuit name="X">，还有 <a name="circuit" val="X"/>
      （树里显示的名字），改名时必须两处一起换（见 pitfalls M11）。
"""
import io
import sys


def main():
    tgt, src, name = sys.argv[1], sys.argv[2], sys.argv[3]
    new = sys.argv[4] if len(sys.argv) > 4 else name
    t = io.open(tgt, encoding="utf-8").read()
    s = io.open(src, encoding="utf-8").read()
    if ('<circuit name="%s">' % new) in t:
        print("%s 已存在，未修改" % new)
        return
    i = s.index('<circuit name="%s">' % name)
    j = s.index("</circuit>", i) + len("</circuit>")
    block = s[i:j]
    if new != name:
        block = block.replace('name="%s"' % name, 'name="%s"' % new)
        block = block.replace('val="%s"' % name, 'val="%s"' % new)
    k = t.rindex("</project>")
    t = t[:k] + "  " + block.replace("\n", "\n  ") + "\n" + t[k:]
    io.open(tgt, "w", encoding="utf-8", newline="\n").write(t)
    print("inserted %s, bytes=%d" % (new, len(t.encode("utf-8"))))


main()
