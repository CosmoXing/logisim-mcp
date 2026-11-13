# `.circ` 文件格式（Logisim-evolution 5.0 实测）

## 1. 文件骨架

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="5.0.0" version="1.0">
  <lib desc="#Wiring" name="0"/>
  <lib desc="#Gates"  name="1"/>
  <lib desc="#I/O"    name="5"/>
  <lib desc="#Base"   name="8"/>
  <main name="main"/>
  <options/>
  <mappings>
    <tool lib="8" name="Poke Tool" map="Button2"/>
    <tool lib="8" name="Menu Tool" map="Button3"/>
  </mappings>
  <toolbar>
    <tool lib="8" name="Poke Tool"/>
    <tool lib="8" name="Edit Tool"/>
    <tool lib="8" name="Wiring Tool"/>
    <tool lib="8" name="Text Tool"/>
    <sep/>
  </toolbar>
  <circuit name="main">
    <a name="circuit" val="main"/>
    ... 元件与导线 ...
  </circuit>
  <circuit name="FA"> ... </circuit>
</project>
```

规则：

- `<main name="...">` 决定打开文件时先显示哪个电路。想做「一打开就看到结果」的演示文件，就把 `<main>` 指向那个电路。
- 子电路只要在同文件里有 `<circuit name="X">` 定义，实例用 `<comp loc=... name="X">` 引用，无需 lib。
- 元件顺序无关；导线可以写在元件前也可以后。
- `<options/>` 可以为空。toolbar 不能写在 options 里，必须在 `<project>` 下直接作为子节点。
- 没有 `<toolbar>` 的文件打开后没有绘图工具条（工具条配置是逐文件保存的，不是全局设置）。`<tool>` 必须带 `lib="8"`（#Base），否则报「在库中找不到该工具」。

## 2. 库索引（实测）

| 索引 | 库 | 常用组件 |
|---|---|---|
| `0` | #Wiring | Pin / Splitter / Constant / Power / Ground / Tunnel / Probe |
| `1` | #Gates | `AND Gate` / `OR Gate` / `NOT Gate` / `XOR Gate` / `NAND Gate` / `NOR Gate` / `XNOR Gate` |
| `5` | #I/O | `Hex Digit Display` / Button / LED / 7-Segment |
| `8` | #Base | 工具和基础件（toolbar 里的 tool 用这个库） |

> 其它库（Plexers / Arithmetic / Memory / TTL）的索引未实测。可靠做法：在 GUI 里手动放一个该组件、保存一次，读回文件看它写了什么 lib 数字和组件名，然后照着写。不要猜。

## 3. 组件写法

```xml
<!-- 引脚：loc 是连线接点。5.0 用 type，不写 output="true" -->
<comp lib="0" loc="(120,60)" name="Pin">
  <a name="type" val="input"/>      <!-- input / output -->
  <a name="facing" val="east"/>     <!-- input 朝东，output 朝西 -->
  <a name="width" val="4"/>         <!-- 省略即 1 位 -->
  <a name="label" val="a3"/>
</comp>

<!-- 门：loc 是输出口 -->
<comp lib="1" loc="(320,100)" name="XOR Gate"><a name="inputs" val="2"/></comp>
<comp lib="1" loc="(320,140)" name="NOT Gate"></comp>

<!-- 子电路实例：不带 lib -->
<comp loc="(720,160)" name="BCD1"><a name="label" val="digit3"/></comp>

<!-- 分线器：合并侧在 loc，分线侧在 (x+20, y-20+10i) -->
<comp lib="0" loc="(860,100)" name="Splitter">
  <a name="fanout" val="4"/><a name="incoming" val="4"/>
  <a name="appear" val="center"/>
  <a name="bit0" val="0"/><a name="bit1" val="1"/>
  <a name="bit2" val="2"/><a name="bit3" val="3"/>
</comp>

<!-- 十六进制数码管：组件名一个空格都不能错 -->
<comp lib="5" loc="(980,160)" name="Hex Digit Display">
  <a name="label" val="digit3"/>
</comp>

<!-- 常量 / 电源 / 地 -->
<comp lib="0" loc="(200,160)" name="Constant">
  <a name="width" val="4"/><a name="value" val="5"/>
</comp>
<comp lib="0" loc="(660,380)" name="Ground"/>
<comp lib="0" loc="(660,340)" name="Power"/>

<!-- 导线 -->
<wire from="(0,0)" to="(190,0)"/>
```

要点：

- `value` 属性按十六进制解析，写 `a` 表示 10；生成时用 `f"{v:x}"`。
- 组件名写错（如 `HexDigit`）时，Logisim 静默丢弃该元件，它所在的整条网络变成 `E`，不报具体错误。遇到「莫名其妙全 E」先查组件名。
- `Hex Digit Display` 的数据口固定 4 位；写 `width="1"` 不会生效，只会造成「位宽不兼容」。
- 3.9 的老文件用 `<a name="output" val="true"/>`，5.0 仍能读，但子电路外观计算里不可靠（端口位置会错），新写一律用 `type`。

## 4. autosave 陷阱

同目录下若存在 `.xxx.circ.autosave`（Logisim 异常退出留下的恢复文件），打开 `xxx.circ` 时会尝试恢复，命令行下直接报「加载电路文件出错」。

排查手法：把 `.circ` 复制成另一个名字能正常打开 → 问题就在 autosave。删掉 `.xxx.circ.autosave` 即可。

## 5. 版本差异速记

| 项 | 3.9 | 5.0 |
|---|---|---|
| 引脚方向 | `output="true"` | `type="input"/"output"` |
| 组件库 | #Base 索引 8 | 同 |
| 数码管 | `Hex Digit Display` | 同 |
| 命令行 `-w` | 无 | 有（`-w <电路> <向量> <文件>`） |
| 真值表表头 | `a` | `a[4]`（带位宽） |
| 工具栏 | 全局偏好 | 逐文件保存 |
