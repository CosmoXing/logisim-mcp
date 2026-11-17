# -*- coding: utf-8 -*-
"""最小化排查：2.15 宽引脚 + 分线器 + 隧道 的驱动关系。"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v271"))
import ita_probe  # noqa: E402

LAB2 = "实验2 构建加法器.circ"
OUT = os.path.join(os.environ.get("TEMP", "."), "lab3wide.circ")

CIRCUITS = """
  <circuit name="t_direct">
    <comp lib="0" loc="(120,100)" name="Pin">
      <a name="facing" val="east"/><a name="output" val="false"/><a name="width" val="8"/>
      <a name="label" val="A"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(400,100)" name="Pin">
      <a name="facing" val="west"/><a name="output" val="true"/><a name="width" val="8"/>
      <a name="label" val="S"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <wire from="(120,100)" to="(400,100)"/>
  </circuit>
  <circuit name="t_split">
    <comp lib="0" loc="(120,100)" name="Pin">
      <a name="facing" val="east"/><a name="output" val="false"/><a name="width" val="8"/>
      <a name="label" val="A"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(600,100)" name="Pin">
      <a name="facing" val="west"/><a name="output" val="true"/><a name="width" val="8"/>
      <a name="label" val="S"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(300,100)" name="Splitter">
      <a name="facing" val="south"/><a name="fanout" val="8"/><a name="incoming" val="8"/>
      <a name="appear" val="center"/>
      <a name="bit0" val="0"/><a name="bit1" val="1"/><a name="bit2" val="2"/><a name="bit3" val="3"/>
      <a name="bit4" val="4"/><a name="bit5" val="5"/><a name="bit6" val="6"/><a name="bit7" val="7"/>
    </comp>
    <comp lib="1" loc="(500,300)" name="OR Gate">
      <a name="inputs" val="8"/><a name="width" val="1"/>
    </comp>
    <wire from="(120,100)" to="(300,100)"/>
    <wire from="(300,100)" to="(600,100)"/>
    <wire from="(330,120)" to="(330,250)"/><wire from="(330,250)" to="(470,250)"/>
    <wire from="(320,120)" to="(320,260)"/><wire from="(320,260)" to="(470,260)"/>
    <wire from="(310,120)" to="(310,270)"/><wire from="(310,270)" to="(470,270)"/>
    <wire from="(300,120)" to="(300,280)"/><wire from="(300,280)" to="(470,280)"/>
    <wire from="(290,120)" to="(290,290)"/><wire from="(290,290)" to="(470,290)"/>
    <wire from="(280,120)" to="(280,300)"/><wire from="(280,300)" to="(470,300)"/>
    <wire from="(270,120)" to="(270,310)"/><wire from="(270,310)" to="(470,310)"/>
    <wire from="(260,120)" to="(260,320)"/><wire from="(260,320)" to="(470,320)"/>
  </circuit>
  <circuit name="t_same">
    <comp lib="0" loc="(120,100)" name="Pin">
      <a name="facing" val="east"/><a name="output" val="false"/><a name="width" val="8"/>
      <a name="label" val="A"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(700,100)" name="Pin">
      <a name="facing" val="west"/><a name="output" val="true"/><a name="width" val="8"/>
      <a name="label" val="S"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(300,100)" name="Tunnel">
      <a name="facing" val="north"/><a name="width" val="8"/><a name="label" val="A"/>
    </comp>
    <comp lib="0" loc="(500,100)" name="Tunnel">
      <a name="facing" val="north"/><a name="width" val="8"/><a name="label" val="A"/>
    </comp>
    <wire from="(120,100)" to="(300,100)"/>
    <wire from="(500,100)" to="(700,100)"/>
  </circuit>
  <circuit name="t_diff">
    <comp lib="0" loc="(120,100)" name="Pin">
      <a name="facing" val="east"/><a name="output" val="false"/><a name="width" val="8"/>
      <a name="label" val="A"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(700,100)" name="Pin">
      <a name="facing" val="west"/><a name="output" val="true"/><a name="width" val="8"/>
      <a name="label" val="S"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(300,100)" name="Tunnel">
      <a name="facing" val="north"/><a name="width" val="8"/><a name="label" val="Abus"/>
    </comp>
    <comp lib="0" loc="(500,100)" name="Tunnel">
      <a name="facing" val="north"/><a name="width" val="8"/><a name="label" val="Abus"/>
    </comp>
    <wire from="(120,100)" to="(300,100)"/>
    <wire from="(500,100)" to="(700,100)"/>
  </circuit>
  <circuit name="t_branch">
    <comp lib="0" loc="(120,100)" name="Pin">
      <a name="facing" val="east"/><a name="output" val="false"/><a name="width" val="8"/>
      <a name="label" val="A"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(600,100)" name="Pin">
      <a name="facing" val="west"/><a name="output" val="true"/><a name="width" val="8"/>
      <a name="label" val="S"/><a name="labelloc" val="north"/><a name="labelfont" val="Dialog plain 12"/>
    </comp>
    <comp lib="0" loc="(300,100)" name="Tunnel">
      <a name="facing" val="north"/><a name="width" val="8"/><a name="label" val="Abus"/>
    </comp>
    <wire from="(120,100)" to="(200,100)"/>
    <wire from="(200,100)" to="(300,100)"/>
    <wire from="(300,100)" to="(600,100)"/>
  </circuit>
"""


def main():
    src = open(LAB2, encoding="utf-8").read()
    head = src.split("<circuit name=")[0]
    head = re.sub(r'<main name="[^"]*"/>', '<main name="t_direct"/>', head)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + CIRCUITS + "</project>\n")
    for name in ("t_direct", "t_split", "t_same", "t_diff", "t_branch"):
        print(name, ita_probe.eval_pins(OUT, name, {"A": 0x12}))
        print(name, "errors", ita_probe.errors(OUT, name))


if __name__ == "__main__":
    main()
