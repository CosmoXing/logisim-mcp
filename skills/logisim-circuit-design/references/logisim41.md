# Logisim-evolution 4.1 适配手册（实测）

> 适用：`<project source="4.1.0">`、jpackage 安装版 `D:/logisim4.1/logisim-evolution.exe`、
> 内核 jar `D:/logisim4.1/app/logisim-evolution-4.1.0-all.jar`（Java 21）。
> 本文所有坐标都是 2026-11-23 用 4.1 内核 `Loader` 实测 + 源码复核，不是从 5.0 推的。

## 1. 一句话差异

**门、触发器、分线器、多路器、译码器、寄存器、RAM/ROM 的端口几何与 5.0 相同；
唯一会翻车的是子电路实例——4.1 是固定 220 宽、20px 间距，5.0 是动态宽度、10px 间距。**

另外两处格式差异：

| 项 | 4.1 | 5.0 |
|---|---|---|
| 库索引 | Wiring0 / Gates1 / Plexers2 / Arithmetic3 / Memory5 / I/O6 / Base9 / TTL7 | 早期生成器常用 Memory4 / I/O5 / Base8 |
| `-t speed` | 无控制台输出（别当失败，是没实现） | 有输出 |
| `-b <file>` | 新增：无头加载并返回成功/失败 | 无 |

`-t table` / `-t stats` / `-w` / `-n` 在 4.1 上都可用（实测）。
`-t` 在 `-h` 里被写成 `--tty`，但传 `table`/`stats` 仍走测试分支，别被帮助文本误导。

## 2. 子电路符号：固定 220 宽

源码：`circuit/appear/DefaultEvolutionAppearance.java`

```text
dy       = 20                       # 端口纵向间距
thight   = 20
width    = 25 * 8 / 10 * 10 + 20 = 220     # fixedSize=true
height   = max(nIn, nOut) * 20 + 20
anchor   = (width, 10)              # 有输出脚：锚点在右边缘第一个输出口
```

因此实例 `loc` 就是**第一个输出口**：

```text
输出口  (0, 0) (0,20) (0,40) ...
输入口  (-220, 0) (-220,20) ...
body    (-220, -10) .. (0, 20*max + 10)
```

`1120.circ` 实测（可直接对照）：

```text
HA@(350,240)  #0=(130,240) in   #1=(130,260) in   #2=(350,240) OUT  #3=(350,260) OUT
FA@(420,940)  #0..2=(200,940/960/980) in          #3..4=(420,940/960) OUT
bounds: HA 221x62，FA 221x82
```

- 输入/输出按子电路内部 Pin 的 **y 坐标排序**，从 0 开始每 20px 一个。
- 想要稳定 220 宽，电路里必须写 `<a name="circuitnamedboxfixedsize" val="true"/>`，
  否则宽度会随引脚标签长度和电路名变化。
- 没有输出脚时锚点落在西边缘（`ax=0`），输入口变成 `x=0`，框向右延伸。

## 3. 其余元件实测表（相对 loc）

| 元件 | 端口 |
|---|---|
| AND/OR | out(0,0)，in(-50,±20) |
| XOR | out(0,0)，in(-60,±20) |
| NAND/NOR | out(0,0)，in(-60,±20) |
| XNOR | out(0,0)，in(-70,±20) |
| NOT | out(0,0)，in(-30,0) |
| D/T Flip-Flop（**必须 classic**） | D/T(-40,20) CLK(-40,0) Q(0,0) ~Q(0,20) R(-10,30) S(-30,30) |
| DFF 默认 evolution 外观 | D(-10,10) CLK(-10,50) Q(50,10) ~Q(50,50) R(20,60) S(20,0)，框 60×60 —— **不要用** |
| Register | Q(60,30) D(0,30) EN(0,50) CK(0,70) CLR(30,90)，框 60×90 |
| Splitter(4,east,left) | in(0,0)，b0..b3 = (20,-40/-30/-20/-10) |
| Splitter(4,west) | in(0,0)，b0..b3 = (-20,10/20/30/40) |
| MUX 2:1 | in0(-30,-10) in1(-30,10) sel(-20,20) out(0,0) |
| MUX 4:1 | in0..3(-40,-20..10) sel(-20,20) out(0,0) |
| Decoder(2) | out0..3(20,-40..-10)，sel(0,0)，en(-10,0) |
| Adder/Subtractor | a(-40,-10) b(-40,10) out(0,0) cin(-20,-20) cout(-20,20) |
| Comparator | a(-40,-10) b(-40,10) gt(0,-10) eq(0,0) lt(0,10) |
| Bit Extender | in(-40,0) out(0,0) |
| RAM(8×8) | A(0,10) D(0,90) Q(240,90) WE(0,50) EN(0,60) CLK(0,70) |
| ROM | A(0,10) Q(240,60)，框 240×220 |
| Hex Digit Display | 数据(0,0) w4，使能(20,0) w1 |
| Pin/Clock/LED/Ground | 端口就是 loc |

> 触发器如果只写 `<comp lib="5" ... name="D Flip-Flop"/>`，4.1 会用 **evolution 外观**（60×60、
> 端口全变）。生成时务必带 `<a name="appearance" val="classic"/>`。

## 4. 工程文件骨架

```xml
<project source="4.1.0" version="1.0">
  <lib desc="#Wiring" name="0"/>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Plexers" name="2"/>
  <lib desc="#Arithmetic" name="3"/>
  <lib desc="#Memory" name="5"/>
  <lib desc="#I/O" name="6"/>
  <lib desc="#Base" name="9"/>
  <main name="main"/>
  <options/>
  <mappings>
    <tool lib="9" name="Poke Tool" map="Button2"/>
    <tool lib="9" name="Menu Tool" map="Button3"/>
  </mappings>
  <circuit name="main">
    <a name="circuit" val="main"/>
    <a name="appearance" val="logisim_evolution"/>
    <a name="circuitnamedboxfixedsize" val="true"/>
    <comp lib="0" loc="(100,100)" name="Pin">
      <a name="type" val="input"/><a name="facing" val="east"/><a name="label" val="a"/>
    </comp>
    ...
  </circuit>
</project>
```

引脚输出方向写 `type="output"`（1120.circ 的写法）。`output="true"` 也能读，但新文件统一用 `type`。

## 5. MCP 用法

不新增第二个 MCP 入口，直接把现有的 `logisim` 指到 4.1（`~/.workbuddy/mcp.json`）：

```json
"logisim": {
  "command": "<python>",
  "args": ["<logisim-mcp>/server/server.py"],
  "env": {
    "LOGISIM_JAR": "D:/logisim4.1/app/logisim-evolution-4.1.0-all.jar",
    "LOGISIM_PROFILE": "4.1"
  }
}
```

换回 5.0/3.9 时只改这两个环境变量，工具名不变。

工具：

| 工具 | 用途 |
|---|---|
| `logisim_info` | 看 `几何档位` 是否为 4.1、写入 source=4.1.0 |
| `circ_geometry component=sub` | 返回 220/20 规则与示例坐标 |
| `circ_build` | 声明式网表生成 4.1 工程（自动用 220 子电路几何） |
| `circ_audit` / `circ_sim` | 按文件自身的 `source` 选几何，4.1 文件不会误报悬空 |
| `circ41_check` | 4.1 真机加载，给出 GUI 同款报错 + 电路清单 |
| `circ41_ports` | 4.1 真机端口/包围盒；`factory` 可精确到 `HA`、`D Flip-Flop` |
| `circuit_truth_table` / `circuit_test_vector` | 组合逻辑复核（`-t table` / `-w` 在 4.1 都可用） |

命令行等价（不接 MCP 时）：

```bash
"D:/logisim4.1/logisim-evolution.exe" -o en -t table  x.circ
"D:/logisim4.1/logisim-evolution.exe" -o en -t stats  x.circ
"D:/logisim4.1/logisim-evolution.exe" -w main vec.txt x.circ
```

`-o en` 只影响提示语言；不加时输出是 GBK，Python 端要按 gbk 解码。

## 6. 排错顺序

1. 文件打不开：先 `circ41_check`。多数是 lib 索引写成 4/5/8（那是 5.0 的编号）或 `<toolbar>` 的
   `<tool>` 缺 `lib`。
2. 子电路引脚接不上：量 `circ41_ports factory=<子电路名>`，确认输入在 `loc.x-220`、输出在 `loc.x`、
   间距 20；再看电路有没有 `circuitnamedboxfixedsize=true`。
3. 触发器端口全错：检查是不是漏了 `appearance=classic`。
4. 真值表全 U：先看 `circ_audit` 是否报悬空；再用 `circ41_ports` 核对导线端点是否真的落在端口上
   （4.1 的门输入在 `loc.x-50/-60/-70`，不是 `-20`）。
5. 时序电路：`-w` 每行都从初态重算，验不了多拍；用 `circ_sim`（自绘网表，逐拍）或
   GUI 里手动打拍。
