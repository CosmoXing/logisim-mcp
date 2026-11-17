---
name: logisim-circuit-design
description: 用代码生成、检查和验证 Logisim（5.0 / 3.9 / 2.7.1 / ITA 2.15·2.16）(.circ) 数字电路。适用于门级作业（计数器、分频器、寄存器、加法器、译码器、状态机）、8 位总线级电路（原码乘法器、ALU、移位寄存器）、64KB ROM/RAM 与低位交叉存储器、32 位 CPU 与 3072×32 数据存储器（DM）、分层子电路设计与子电路展平（paste/canonicalize）、「只许门电路和触发器、不许用现成芯片/隧道」这类限制，以及 .circ 打不开、显示 E/U、位宽冲突、模块引脚接不上、布线短接的排障。内含 102 条实战坑表（A-K 组：13 进制计数器 13 坑 + 8 位乘法器 13 坑 + 八进制加法器 6 坑 + 3.2 存储器 12 坑 + 2.7.1 CPU/DM 14 坑 + ITA 2.15 19 坑）、确定性布线工具（lib8/route8）、时序向量封装（sim，<set><seq>）、GUI 截图工具（gui.py）与 5.0 端口坐标表；2.7.1 用 circ271_check / circ271_sim / circ271_ports；ITA 2.15 用 scripts/v215/board215.py 构建 + ita_probe 验证。关键词：logisim、logisim-evolution、logisim 2.7.1、logisim 2.15、logisim 2.16、Logisim-ITA、.circ、数字电路、电路作业、加法器、半加器、全加器、8位ALU、运算器、比较器、移位器、标志位、先行进位、CLA74182、16位加法器、可控加减、溢出标志、乘法器、原码乘法、计数器、模13、八进制、触发器、时序电路、真值表、测试向量、子电路、展平、分线器、数码管、模块外观、restart、netlist、确定性布线、RAM、ROM、存储器、低位交叉、字节使能、64KB、CPU、DM、数据存储器、3×1024×32、字对齐、越界保护。
---

# Logisim 电路设计

两条路，都验证过：

| 路径 | 适合 | 入口 |
|---|---|---|
| A. MCP 工具（推荐） | 要交付、要可验证、连线复杂 | `circ_build` / `circ_audit` / `circ_sim` / `circuit_truth_table` / `circ_appearance`；**2.7.1 用 `circ271_check` / `circ271_sim` / `circ271_ports`** |
| B. 手写脚本 | 环境里没有 MCP、或只想微调一个文件 | `scripts/v50/logisim_gen.py` + `scripts/v50/router.py` + `scripts/v50/verify.py`；存储器用 `scripts/v50/mem_gen.py` |

两条路的几何常量、布线规则、踩坑记录是同一套。先读第 1 节的版本前提，这是最容易翻车的地方。

## 0. 何时用

- 用户要求用 Logisim 做数字电路（作业、课设、演示），尤其带「只许门电路/触发器」「不许用隧道」「不许用内置计数器」这类限制。
- 已有 `.circ` 打不开、导线显示 `E`、橙色报「位宽不兼容」、子电路引脚接不上、数码管不亮。
- 需要批量生成用例电路、跑真值表、验证一个自己写出来的时序电路。
- 文件是 **Logisim 2.7.1** 格式（`<project source="2.7.1">`），或用户明确要求「在 2.7.1 下修」。

不适用：模拟电路（SPICE）、Verilog/VHDL 综合。

## 1. 版本前提（先确认，再动手）

```bash
head -3 xxx.circ | grep source        # <project source="5.0.0"> / "2.7.1"
logisim_info                          # MCP：报 jar/Java/无头能力
python server/server.py --doctor      # 插件：报依赖与自检
```

| 项 | 3.9 | 5.0（本 skill 默认） | 2.7.1 |
|---|---|---|---|
| 引脚写法 | `<a name="output" val="true"/>` | `<a name="type" val="input"/>` / `val="output"` | `<a name="output" val="true"/>`（输出） |
| 门 `size` | 40 | 50 | 50；输入在 `x-50` |
| AND/OR 输入口 | `loc.x-20` | `loc.x-50` | `loc.x-50`，纵向 40px 均布（2 输入 `y±20`） |
| NAND/NOR/XOR 输入口 | `loc.x-20` | `loc.x-60` | `loc.x-50`（2.7.1 门体宽 40） |
| NOT 输入口 | `loc.x-20` | `loc.x-30` | `loc.x-30` |
| 子电路端口 | `loc.x-30` 起、10px | 按 facing 分边，锚点落在东边第一个口 | 按侧/顺序 10px 打包，与内部 Pin 坐标无关 |
| Splitter 分支 | `(20, -10*(n-i))` | 取决于 appear | east `y-10*fanout+10*i`；west `y+10*(i+1)` |
| 验证工具 | `-t table` | `circ_sim` / `-w` / `circ_audit` | `circ271_check` / `circ271_sim` |

**2.16 / 2.7.1（Logisim-ITA，课程常用）—— 和上面两套都不一样，且有硬限制：**

| 项 | 2.7.1 / 2.16 |
|---|---|
| 门输入口 | `(loc.x-30, loc.y ± step*(n-1)/2)`，2 输入时 `y±10`（**不是 x-50**） |
| 分线器位口 | `b_i=(x+20, y+10*(i-fanout+1))`；**b0 是低位组**，3 位/2 位别搞反 |
| 译码器 | `sel=(x,y)`、`en=(x-10,y)`、`out_i=(x+20, y-10*(cnt-i))` |
| 子电路端口 | `loc + (x + (portW-1)//2 - 2, y + portH//2 - 3)` |
| 外观矩形 | **必须比端口内缩 10px**，否则端口被静默丢弃（J1） |
| 验证 | **没有 `-w` 向量引擎**，用 `scripts/v271/ita_probe.py` |

排线还要记住：**端口落在别的导线上就一定会连**（T 接），主干通道必须避开所有端口坐标。
位宽对不上时跑 `python scripts/v271/netcheck.py file.circ "电路名"`，
它按真实端口坐标建网，一次列全冲突点所属元件（J5）。

**2.15.0.2（实验课实际分发的 Logisim-ITA）实测补充——和上表仍有差异：**

| 项 | 2.15.0.2 |
|---|---|
| 门输入口 | AND/OR `x-30`；XOR `x-40`；**NOT `x-20`**（写成 -30 会悬空、输出 `E`） |
| 多输入排布 | 奇数 10px 均布；偶数中间留 20px 空档（4 输入 = -20/-10/+10/+20） |
| 子电路实例端口 | `loc + (端口中心 − 锚点中心)`，中心 = `坐标 + 尺寸//2`，`circ-anchor` 同样取中心 |
| 实例写法 | 子电路 `<comp>` **不写 `lib`**；写了不存在的库编号直接报「库缺失」 |
| 外观 | 每个 Pin 必须恰好一个 `circ-port`；缺的会被自动补到符号顶边（`y-19` 一排） |
| MUX | 必须显式 `enable=false`；2:1 数据 `(x-30,y±10)`、4:1 `(x-40,y-20+10i)`、8:1 `(x-40,y-40+10i)`；sel `(x-20,y+20)` / `(x-20,y+40)`；out `(x,y)` |
| Comparator | A `(x-40,y-10)`、B `(x-40,y+10)`；gt `(x,y-10)`、eq `(x,y)`、lt `(x,y+10)`；`mode` 只有 `unsigned` / `twosComplement`（有符号写后者，写 `signed` 输出全 `U`） |
| Bit Extender | in `(x-40,y)`、out `(x,y)`；属性 `in_width/out_width/type`，`type` 取 `zero` / `sign`（负数扩展用 `sign`） |
| Shifter | data `(x-40,y-10)`、distance `(x-40,y+10)`（3 位）、out `(x,y)`；属性 `shift=ll/lr/ar` |
| Splitter 南/北 | bus `(x,y)`；bit i `(x+off-10i, y±20)`，`off=(ceil(bits/2)-1)*10`，**b0 最右** |
| 多分支 Splitter | `fanout=分支数`、`incoming=总位数`、`bit{i}=第 i 位所属分支`；端口位置只按分支数算 |
| Register | D `(x-30,y)`、en `(x-30,y+10)`、clk `(x-20,y+20)`、clr `(x-10,y+20)`、preset `(x-10,y-20)`、cs `(x-30,y-10)`、Q `(x,y)`；cs=0（默认 low-select）才输出 |
| Counter | `max/goal` 无关紧要：2 位默认 **向下** 计数 `0→3→2→1`；要向上用 1 位 Register 自搭 |
| Adder | 2.15 内置 Adder 的 `Cout` 被声明成输入脚，输出恒 `U`；改用全加器子电路行波进位 |
| RAM | A `(x-140,y)`、D `(x-140,y+20)`、Q `(x,y)`；底部 str/cs/clk/oe/clr = `-110/-90/-70/-50/-30`；**cs=0、oe=1** 才读出 |
| ROM | A `(x-140,y)`、Q `(x,y)`、cs `(x-90,y+40)`；cs=0 输出有效 |
| Tunnel | `facing` 必须写 `east/west/north/south`；写 `e/w` 会加载报错并可能 WireRepair 卡死 |
| 验证 | 2.15 **没有** `-t stats` / `-w`；用 `scripts/v271/ita_probe.py`、`scripts/v215/verify_adder_lab2.py`、`verify_alu_lab3.py` |
| 构建 | `scripts/v215/board215.py`（实测几何 + Board + 六项自检）+ `gen_adder_lab2.py` / `gen_alu_lab3.py` / `gen_ctrl_lab4.py` |
| 内嵌 jar | 2.15 用 Launch4j 打包 exe，可从 `PK\x03\x04` 偏移整段切出 jar 喂探针 |
| 加载报错 | GUI 对话框会吞异常；`ITAProbe` 的 `ProbeLoader` 会打印 `LOADERR`，旧工具用 `LoadTest.java` |

`circ271_check` / `netcheck.py` 对 2.15 有两类固定误报：前者按原始 2.7.1（门输入 x-50）
建模，会把 20px 输入短线判成「导线穿元件体」；后者把 Probe 当 0 位宽。
以 Logisim 自身 `ERRCOUNT` 与 `ita_probe` 功能向量为准。

> 实验3 8位 ALU（移位/比较/算术/逻辑 + 标志）的完整复盘见
> `references/alu215-casebook.md`：8 个电路结构、16604 行验证矩阵、
> K12~K19 的新坑（Tunnel facing、分线器反推、MUX enable、Shifter、比较器 S=1/0、INC/NEC）。
>
> 实验4 控制器模块（Regs/PC/IR/ID/CLK/S-I/B/Flag/CU/系统）见
> `references/controller215-casebook.md`：K20~K29（Register 端口与写使能竞争、
> 内置 Adder 不可用、Counter 向下计数、RAM cs/oe 极性、多分支 Splitter、
> 外观 `pin` 坐标、XYZ 位序、`--set` 不可靠、隧道/引脚可视间距）；
> `verify_ctrl_lab4.py` 112 行全过。
>
> 实验5 指令分析与程序设计（4 个程序 + PC+n + 条件跳转）见
> `references/instruction215-casebook.md`：指令/S-op 编码表、四个程序的机器码、
> 600 行模型化逐拍向量；K30~K40（立即数/偏移符号扩展、S-Regs 位序、移位固定 1 位、
> Comparator `twosComplement`、T1 取指、跳转不更新 Flag、INC 的 SA 字段、
> 4 ROM+Prog 选通、补码模型/向量进制、多层子电路逐拍验证、布局回归）。
>
> 实验6 存储器实验（D1 字扩展 + 16×16 汉字显示）见
> `references/storage215-casebook.md`：4 片 4K×32 → 16K×32（低 12 位并联、
> 高 2 位选 4:1 MUX）、姓名显示链路、K41~K52（2.7.1 素材头、复用 ROM 元素、
> 测试引脚中段 T、隧道压线、子电路端口起点、Counter Q/carry 短接、32→2 分行、
> bank3 不可达、ROM cs 悬空、Clock 换 Pin、问答地址位数）。
>
> 布局间距规范：引脚 `Board.lead()` 80px；同侧多脚 `fan_stub` 横向 20+30i、
> 纵向 ±25；`fan_bits` 30px；MUX out/sel 40px；寄存器用 `wire_reg()`（cs/preset 悬空）。
> 2.15 课程框架本身大量使用 Tunnel；沿用时按框架原样保留，只有用户明确禁用时才全部改实体线。

抄错这 30px 的症状是「每修好一处、另一处又坏」，几乎一定被误判成"布线算法有问题"。
不确定就查 `references/geometry.md`，或用 `circ_geometry`（5.0）/ `circ271_ports`（2.7.1）拿活数据。

## 2. 七条铁律（违反必炸）

| # | 铁律 | 后果 |
|---|---|---|
| 1 | 导线终点必须精确落在端口像素上 | 差 10px 就断线，且没有任何报错 |
| 2 | 子电路只做 ≤3 入 / ≤2 出 | 引脚一多，端口被压进 50px，几乎布不通 |
| 3 | 所有元件端口都是禁入点，不只是子电路 | 竖线穿过触发器 `Q(0,0)` 与 `~Q(0,20)` → 两输出短接，整列 `E` |
| 4 | 位宽严格匹配（数码管数据口恒 4 位） | 橙色「位宽不兼容」，整条网络 `E` |
| 5 | 同网共线相接会合并，合并后端点变内点 | 分支静默失效（"看着接上了其实断了"） |
| 6 | 同网"内点×内点"十字交叉不导通 | 要连接就从交点引一段短线 |
| 7 | 生成的 `.circ` 自带 `<toolbar>`（3.9 需要；5.0 可省） | 用户打开后没有绘图工具条，以为软件坏了 |

### 2.1 默认风格：模块化 + 紧凑（用户长期偏好，不必再问）

任何电路默认按这两条设计，除非用户明确要单层/大图：

1. 模块化：功能块拆成子电路，每层 ≤3 入 / ≤2 出；`main` 只放「输入引脚 → 模块实例 → 输出/显示」，
   连线控制在 20 段以内，复杂布线全部封装进子电路。每个子电路都配自定义外观
   （名称牌 + 端口标签），父电路按外观端口坐标布线（`loc + circ-port`）。
2. 紧凑：信号从左到右一条线走完，不留大段空走线。
   - 相邻元件间距 40~80px；模块到显示器件 ≤200px；
   - 扇出通道按「目标越靠下 → 通道越靠左」选，保证零交叉；
   - 整图横向尽量 ≤800px、纵向 ≤300px；
   - 引脚整体离画布左边缘 ≥100px，否则多位引脚标签会被侧栏切掉（H17）。
3. 紧凑是视觉指标，不是坐标数字指标：交付前必须用 Logisim 本体截图确认。
4. 禁止隧道（写死）：`main` 与所有子电路一律用实体正交线，生成器不得产生 `Tunnel`。
   连线复杂时用「干线 + 等距分支 + 反向车道」解决，不靠隧道省事。
5. 自检必须查整网连通性：只验证“端口碰到某段线”不够，还要用并查集确认同一网络的所有线段
   属于一个连通块——10px 断口会让整条读地址悬空，而端口检查看不出来（H21）。

## 3. 坐标速查（5.0）

| 对象 | 坐标 |
|---|---|
| AND / OR | `loc` 是输出口；输入口 `(loc.x-50, loc.y∓20)` |
| NAND / NOR / XOR | `(loc.x-60, loc.y∓20)` |
| XNOR | `(loc.x-70, loc.y∓20)` |
| NOT | `(loc.x-30, loc.y)` —— 特例，宽度 30 |
| 3 输入以上 | 从 `loc.y-10(n-1)` 起，每 20px 一个 |
| D / T 触发器（classic） | `D(-40,+20) CLK(-40,0) Q(0,0) ~Q(0,+20) R(-10,+30) S(-30,+30)` |
| 子电路实例 | 东口 `(X, Y+10j)`；西口 `(X-30, Y+Δ+10i)`；锚点落在东边第一个口 |
| 分线器·拆位 | 合并侧 `loc`；分线侧 `(loc.x+20, loc.y-10*(n-i))`，`b0` 在最上；`incoming` 缺省恒为 2 |
| 分线器·appear | `center` 起点 `-10*floor(n/2)`、`right` 起点 `+10`（默认 `left` 才是 `-10n`）；west 镜像 |
| 分线器·合并 | 合并侧 `loc`；位序 `o = b3 b2 b1 b0`，最上面的口是最低位 |
| 分线器·西向 | `facing="west"`：bus `(0,0)`，分线 `(-20, 10*(k+1))`，b0 仍在最上 |
| Register(32) | `D(0,30) en(0,50) clk(0,70) clr(30,90) Q(60,30)`，体 `60×90`，clr 异步 |
| Decoder n | 输出 `(20, -10*(2^n-i))`（最上 out0），`sel(0,0)`、`en(-10,0)` 都在底部 |
| MUX 8:1 | 输入 `(-40,-40..30)` 步长 10，`sel(-20,40)`，`out(0,0)` |
| MUX 4:1 | 输入 `(-40,-20..10)`，`sel(-20,20)`，`out(0,0)` |
| MUX 2:1 | 输入 `(-30,-10)/(-30,10)`，`sel(-20,20)`，`out(0,0)` |
| Comparator | `a(-40,-10) b(-40,10)`，`gt(0,-10) eq(0,0) lt(0,10)` |
| Constant | `out(0,0)`，体 `(-35,-8,35,16)` |
| Pin | 端口 = `loc`；朝东体 `(-50,-10,50,20)`，朝西体 `(0,-10,50,20)` |
| Hex Digit Display | `loc` = 数据口（固定 4 位）；小数点口 `(loc.x+20, loc.y)` |

## 4. 路径 A：MCP 工具

### 4.1 声明式生成

`circ_build` 收 `{"file","circuits":[...]}`，你写网表，不写坐标：

```json
{
  "file": "D:/work/demo.circ",
  "circuits": [{
    "name": "main",
    "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
             {"label": "y", "dir": "out"}],
    "components": [{"id": "g1", "type": "AND"}],
    "nets": [{"name": "a", "connect": ["pin:a", "g1.a"]},
             {"name": "b", "connect": ["pin:b", "g1.b"]},
             {"name": "y", "connect": ["g1.out", "pin:y"]}]
  }]
}
```

- 引用只有两种：`pin:<标签>`、`<元件id>.<端口名>`；子电路用它自己的引脚标签当端口名。
- 元件类型：`AND OR NAND NOR XOR XNOR NOT`、`DFF TFF`、`SPLITTER4`、`CLOCK`、`LED`、`DISPLAY`，或任意已定义子电路名。
- 端口名：门 `a/b/c…` + `out`；触发器 `D/T/CLK/Q/NQ/R/S`；分线器 `in` + `b0..b3`；时钟/LED/数码管 `p`。
- 每个网络 ≥2 个连接点；位宽必须一致（4 位接 1 位门输入会被拒）。
- `at` 可省略，按依赖深度分列排布。

完整 DSL 见 `references/dsl.md`。

### 4.2 生成后必须体检

`circ_audit` 报四类问题：`floating`（有读无驱动）、`conflict`（多驱动/短接）、`dangling`（孤立端口）、
`body_overlap`（元件体重叠）。`verdict` 必须是 `ok` 才继续。

### 4.3 验证

| 目的 | 工具 |
|---|---|
| 组合逻辑 | `circ_sim`（快，纯 Python）+ `circuit_truth_table`（Logisim 自己跑，交叉复核） |
| 时序 | `circ_sim`，用 `cycles` 跑满状态序列 |
| 查几何 | `circ_geometry` |
| 查历史坑 | `circ_kb search <关键词>` |
| **2.7.1 静态体检** | `circ271_check`（按 2.7.1 几何/语义） |
| **2.7.1 网表仿真** | `circ271_sim`（原始元件电路：DM/GRF/Controller） |
| **2.7.1 端口几何** | `circ271_ports`（Splitter 分支、RAM 五脚、门输入位置） |

### 4.4 子电路外观编辑

`circ_appearance` 在运行中的 Logisim JVM 里调用 `CircuitAppearance`，GUI 实时刷新：

```json
{"action":"auto",   "file":"D:/work/2.3.circ", "circuit":"mul"}
{"action":"preview","file":"D:/work/2.3.circ", "circuit":"mul"}
{"action":"save",   "file":"D:/work/2.3.circ", "circuit":"mul"}
```

- 需要 JDK 21+：先 `python tools/build_bridge.py` 生成 `runtime/bridge/logisim-bridge.jar`。
- `auto` 默认 `preserve_port_positions=true`，只重画框体/名称牌/标签，父电路导线不动；
  要均匀重排端口，传 `"layout":{"preserve_port_positions":false}`，并检查返回的 `impact`。
- 每个 Pin 必须恰好一个 `circ-port`；`pin` 重名时用 `pin_at`（Pin 的 `loc`）消歧。
- `save` 前自动备份 `.bak-时间戳`；保存后用 `java -jar … -t stats` 确认 Logisim 能重新加载。
- 详见 `references/appearance.md`。

交付门禁（必须）：只要外观改了端口位置，就必须回归父电路（通常是 `main`）：

1. 改前先 `get` 记录旧端口坐标和 `impact`；
2. 改后在父电路里打开 Logisim 截图，逐个确认该子电路的每个引脚都还有导线；
3. 截图仍是最终依据：`circ_audit` / `circ_sim` 现在会读 `<appear>` 的 `circ-port`
   符号坐标，能发现“外观端口移动、父电路导线仍停在旧位置”；但端口与内部 Pin 是否对齐、
   符号是否压住元件，仍要在父电路截图里逐个确认；
4. 需要重布时，删掉落在旧端口位置的旧线，按新端口走正交线；右侧/总线端口要绕开分线器的
   `b0..bN` 位端口，压在位端口上会短路并触发「位宽不兼容」；
5. 修完再截图确认：无橙色短接、无悬空线头，最后保存并保留备份。

内部紧凑重排（符号太小 / 布线太大）：用户要求把子电路内部「压紧、放大元件、重排布线」时：

1. 坐标系分开看：`circ-port x y` 是符号坐标（决定父电路实例引脚位置）；`circ-port pin="x,y"`
   指向内部 Pin 绝对坐标。移动内部 Pin 后只同步 `pin`、不动 `x y`，父电路导线就不会脱开。
2. 别整块替换 `<circuit>`：会丢 `<a>` 属性和 `<appear>`；重排后必须恢复外观并同步 `pin`。
3. `lib` 编号照抄原文件：触发器是 `lib="2"`，写成 `"4"` 打开就报「库“4”中缺少组件」；
   重排后先做 (lib, name) 组合 diff 再打开。
4. 行为回归用 Logisim 自己：`java -jar … -w <电路> <vec> <file>`（带 `<set> <seq>`），
   对保存前 `.bak` 逐行 diff，0 差异才算过。`netlist.Sim` 会因分线器方向启发式给出全 `U` 假象。
5. 父电路仍要截图：子电路内部 Pin 动过，父电路连到它的线必须落在子电路外观端口上；
   典型症状是父电路线都在、子电路内部却全 `U`。全文细则见 `references/appearance.md`
   「内部紧凑重排」。

## 5. 路径 B：手写脚本

```python
import sys; sys.path.insert(0, "<skill>/scripts")
import logisim_gen as G

body  = G.pin(120, 60, "a")                 # 输入引脚
body += G.pin(120, 160, "s", "output")      # 输出引脚
body += G.gate(320, 100, "XOR")             # loc 是输出口
body += G.path((120, 60), (300, 100))       # 走线，可多段折线
open("demo.circ", "w", encoding="utf-8", newline="\n").write(
    G.project([("main", body)]))            # 自动补齐 lib / options / toolbar
```

生成器提供：`pin gate sub splitter display constant power ground wire path translate strip_pins project`。

布线交给 `scripts/v50/router.py`（通道布线，避开共线重叠与端点压线）。有失败就 `raise`，绝不写出文件——
断头导线轻则整列 `E`，重则加载时 `WireRepair` 卡死。

### 5.1 v6 工具链：8 位总线级项目（推荐用于多比特/大规模电路）

logisim_gen/router 是 4 位小电路时代的工具。8 位总线、几十个模块、2 万+ 导线的规模，
用 `scripts/v50/lib8.py` + `scripts/v50/route8.py` + `scripts/v50/sim.py`（原码乘法器项目沉淀，已在本插件目录独立验证）：

```python
import lib8, route8, sim
from lib8 import Board, PINS

b = Board("mul")
b.pin((80, 160), "mult_op1", "input", 8)        # width 可省（默认 1）
sp = b.splitter((300, 300), 8)                  # 8 位分线器，端口 (20, -40+10i)
sp2 = b.splitter((300, 600), 8, "west")         # 朝向镜像：分线口在 (-20, ...)
n1 = b.sub((800, 300), "neg8")                  # 子电路实例，返回 {引脚名: (x,y)}
ff = b.dff((900, 700), "ff0")                   # D(-40,20) CLK(-40,0) Q(0,0) R(-10,30) S(-30,30)
k0 = b.const((700, 700), "0x00", 8)             # 8 位常量 0（别再用 Ground 阵列拼）
clk = b.clock((350, 320))                       # Clock 组件（Ctrl+K 只驱动它）
b.z("net", p1, p2, track)                       # 确定性布线：独占通道 + 折线
b.w("net", [p1, (x1,y1), p2])                   # 任意折线（逐段轴对齐自检）
b.paste(other, dx, dy, "prefix", link={...})    # 子电路展平进当前板（丢引脚、并网）
b.verify_nets(); b.verify_short()               # 连通性 + 电气短接检查
open("out.circ", "w", encoding="utf-8", newline="\n").write(lib8.project([b]))

res = sim.run("out.circ", "mul", "a[8] b[8] q[8] <set> <seq>", rows)
sim.verify_alive(res, len(rows))                # 防假通过：通过数必须 == 行数
```

与 v5 的关键差异：

- 布线前自检，不带病落盘：跨网共线重叠、端点互压（双向）、T 型搭接、网络分裂、
  穿元件体、压引脚、非 10px 网格——全部当场 `raise`（H1/H2）。
- 通道必须在端口正确侧（≥30px 边距）：反侧回折会短接相邻线，且输入网短接不显示 E。
- 几何都有出处：DFF 端口对源码 `AbstractFlipFlop` 逐个核过；8 位分线器、
  4 入 2 出 / 3 入 1 出子电路实例、Clock、Constant、Hex Display 全部用本体实测。
- ≥4 输入门不可用：自家多输入间距公式只验证到 3 输入，4 输入拆两级 2 输入门（H3）。
- 子电路引脚注册在 `PINS[name]`：`(名字, x, y, facing)` 列表；实例端口按 y 排序 10px 密排。
  顶层连线永远读 `b.sub()` 返回的坐标，不硬编码偏移（H6）。

```bash
python scripts/v50/verify.py table  fa.circ                 # 真值表
python scripts/v50/verify.py stats  demo.circ               # 元件统计
python scripts/v50/verify.py vector main bcd4.vec demo_test.circ
```

## 6. 验证：先把"验什么"分清

### 组合逻辑

`verify.py table` 或 `circuit_truth_table`。`0/1` 正常，`U` = 无驱动（悬空），`E` = 冲突/短路，两个都不能有。

### 时序逻辑（计数器、状态机）

默认情况下 `-w`（`verify.py vector` / `circuit_test_vector`）每一行都从初始状态重新求值，
触发器状态传不到下一行。但只要加 `<set>` / `<seq>` 两列，就变成真正的时序测试：
Logisim 按 `set` 分组、按 `seq` 递增执行，组内保留电路状态（`seq` 为 0 或缺省仍按组合处理）。

```
d[8] clk r q[8] <set> <seq>
0x00 0 1 0x00   1   1
0x5a 0 0 0x00   1   2
0x5a 1 0 0x5a   1   3
```

- `clk` 写成普通列、给 0/1，靠 0→1 那一行产生上升沿；别指望它自动打拍。
- 期望值要逐行写全（这一版不认 `x`）；无关输出写 `<DC>`，高阻写 `<float>`。
- 列名对不上时 Logisim 静默跳过，输出里没有 `expected` 行——这种"全过"是假的，先确认向量真的跑了。

补充手段（建议保留，用于交叉复核）：

1. 多拍网表仿真（`circ_sim`）：逐拍给 `cp` 一个完整脉冲；每拍内逐个触发器比较各自 `CLK` 的前后值，
   只有 0→1 才采样 `D`（否则行波级联会算错）。
2. 组合镜像交叉复核：把触发器换成输入引脚（`Q_i` / `~Q_i`），保留次态组合逻辑，
   做成纯组合电路，用 Logisim 真值表跑 32 行。验的是 Logisim 的真实语义。

两者都过才算过。报告"0 失配"前先确认向量真的执行了——列名对不上时 Logisim 静默跳过，输出里没有 `expected` 行。

### 双工程策略

`demo.circ`（数码管展示）与 `demo_test.circ`（数码管换输出引脚）由同一个生成函数产出，
只切换一个开关，保证"好看的那份"和"通过验证的那份"电气一致。

## 7. 常见症状 → 修法

| 症状 | 根因 | 修法 |
|---|---|---|
| 输出全 `U` | 端口没接上 / 网络被漏掉 | 按 5.0 公式算；确认总线网真的生成了 |
| 某一位 `E`，其余正常 | 竖线穿过触发器 `Q` 与 `~Q` | 端口列为禁入点 |
| 个别位 `E`，换布局失败位漂移 | A* 布线 T 型搭接/共线重叠（H1） | 换确定性布线 lib8+route8 |
| clk/reset 有线没电，后半区不动 | 通道回折短接，输入网短接不显示 E（H2） | verify_nets + verify_short 自检 |
| 分支"看着接上了"却没电 | 同网共线合并，端点变内点 | 错开 10px 走 T 型搭接 |
| 输出 `E` +「位宽不兼容」 | 1 位接 4 位数码管 | 分线器补零凑 4 位 |
| 数码管恒 0、向量大面积失败 | 8 位门的另一个输入接了 1 位信号（`width` 是整片 Data Bits） | 分线器把 1 位复制成 8 位全 0/全 1 掩码（H14） |
| 外观改完 main 里子电路少线/线头悬空 | 只改了 appearance 端口，父电路导线仍停在旧端口 | 改后必须打开父电路截图并重布；audit/sim 不读 appearance |
| 重布后导线橙色/位宽不兼容 | 绕线压到分线器 `b0..bN` 位端口 | 从总线端口外侧绕行，避开所有位端口 |
| 父电路线都在，子电路内部却全 `U` | 子电路加了自定义外观后端口挪位，父电路导线仍按旧（默认）端口落点 | 按子电路外观端口重布父电路；网表按内部 Pin 建模，查不出来 |
| 时序"0 失配"但电路是错的 | `-w` 每行重置 / 列数不匹配被静默跳过 | 加 `<set> <seq>` 列 + verify_alive 断言 |
| 选择器不报错但逻辑反 | mux 语义是 `y = s ? b : a`，接反（H8） | 加探针引脚逐拍看中间寄存器 |
| 正数用例全对、负数全错 | 求补控制端接了别人的符号位（H9） | 逐个核对多实例块的 s 端来源 |
| 结果正好是真值的 2 倍 | 迭代少一次：装载占 1 拍（H10） | 终止条件 = 数据拍数 + 装载拍数 |
| 触发器永远 `U`，清不掉 | `U` 沿 `Q→D` 自锁 | 仿真初值置 0；真机 `Ctrl+R` |
| 展平后整块输出 `U` | 源电路内部残留子电路实例（H6） | 先展平到纯门级再 paste |
| 打开报「库“4”中缺少组件“D Flip-Flop”」 | 生成的 `lib` 编号错：5.0 里触发器属存储库 lib="2"（4 是别的库） | 把该组件 `lib` 改回 `2`；整文件按原文件的 (lib,name) 组合对齐后再打开 |
| 打开报「加载电路文件出错」 | 目录有 `.circ.autosave` | 删掉再开 |
| 没有绘图工具条 | 3.9 文件缺 `<toolbar>` | 补 `lib="8"` 的 toolbar 块（5.0 可省） |
| 电路贴左上角、引脚被面板挡 | 从 `(0,0)` 起画 | 整体 `translate(+120,+60)` |
| 数码管不亮 | 组件名写成 `HexDigit` | 正确名 `Hex Digit Display`，5.0 的 lib 是 `3`（I/O）；旧 3.9 文件可能写 5 |
| 全 `U`，GUI 报「找不到库 5」 | 工程头缺 `#Plexers`，mux/decoder 未识别 | 补 `<lib desc="#Plexers" name="5"/>`（I1） |
| 全 `U`，引脚都在但地址/数据没驱动 | `add_pin()` 建了 Pin 却没加入任何 net | 断言每个 Pin 至少出现在一条 net（I2） |
| 生成器自检通过，功能却断线 | `connect()` 不写 `_net_terms`，`verify_nets` 空验证 | 记录端点 + 并查集连通性检查（I3） |
| RAM 写不进、读回全 `FF` | `DIN/WE/CLK` 没真正到 bank，或地址/数据 `U` | 先单 bank 直连测，再查 mux/使能扇出（I2/I9） |
| 字节读「错位」，像 mux 接反 | bank0 是 LSB，测试期望值按大端写了 | 先定字节序再写期望值（I4） |
| `-t stats` 报加载失败，`-w` 却能跑 | 同目录有 `.circ.autosave` | 关 GUI、删 autosave（I5） |
| `circ_audit` 报一堆 dangling，但电路能跑 | RAM/ROM/Bit Extender 不在网表支持范围，结论 partial | 以生成器自检 + `-w` 功能向量为准（I6） |
| `circ_appearance preview` 只截到空框 | preview 切到外观视图，不是 circuit view | 主布局用 GUI + 窗口截图（I8） |
| 16 位地址想拆成 14+2 拆不出来 | Splitter 分支等宽，不能直接拆 2+14 | 8×2 拆分 + 7×2 合并（I10） |
| 2.7.1 文件里 `lw` 读回 x、`bank` 显示 x | Splitter 2 位分支接到错误的 y，网络悬空 | 按 `circ271_ports` 的 `b0/b1` 坐标接线（J1） |
| 2.7.1 `MemWrite=0` 内存仍被改写 | Decoder 禁用输出默认 Z，RAM WE 判「≠0 即写」 | Decoder 加 `disabled=0`（J3） |
| 写 `0x3000` 后 `0x0000` 被改 | 单块 12 位地址 RAM + 无越界门控，地址回绕 | 3×1024×32 + `ALU<0x3000` 门控 + `ALU[13:2]`（J12） |
| `circ_audit` 对 2.7.1 报大量不支持 | 5.0 几何/语义不适用 | 换 `circ271_check` / `circ271_sim` / `circ271_ports` |
| 评测 trace 错位、某寄存器“多写” | 写使能线漏一段，`en` 悬空=每拍写（J14） | 逐寄存器扫描定位，补齐 en 走线 |

## 8. 完整案例：两位十三进制计数器

`references/counter13-casebook.md` 是一次真实交付的复盘：模 13 的次态公式、两位级联与溢出停止，
以及排障中踩到的 13 个坑（门端口差 30px、Q/~Q 被竖线短接、共线合并把端点变内点、`-w` 假通过、
触发器 `U` 自锁、子电路端口公式、仿真器统一采样、三元表达式漏网……），
每条都是「现象 → 根因 → 解决 → 怎么验证」，文末有排查决策树。

做计数器、分频器、状态机这类时序电路时先读它，能省掉一整轮试错。

## 8.5 存储器设计：64KB ROM + 64KB RAM（低位交叉）

`references/memory-casebook.md` 是 3.2 存储器实验的完整复盘：32 位字长、16 位字节地址、
64KB ROM + 64KB RAM、字/字节访问都必须单周期。核心结构：

```
main
 ├─ rom64k   1 × 16K×32 ROM = 64KB
 └─ ram64k   4 × 16K×8 RAM 低位交叉 = 64KB
     ├─ bank0..bank3
     ├─ 字节使能 BE_i = ~BYTE | (A[1:0]==i)
     └─ 字/字节读选择
```

关键规则：

- **地址**：`A[15:2]` 送 4 个 bank 和 ROM，`A[1:0]` 选字节通道；`bank i` 存地址 `4k+i` 的字节。
- **字节序**：bank0 是 LSB；`0x11223344` 的 byte0=0x44、byte1=0x33、byte2=0x22、byte3=0x11。
- **单周期**：字写 4 bank 并行；字节写只使能 `A[1:0]` 选中的 bank；读用异步 RAM/ROM + 组合 mux。
- **RAM 5.0 配置**：`addrWidth=14,dataWidth=8,enables=byte,type=volatile,trigger=rising,`
  `asyncread=true,databus=bibus,clearpin=false`；`EN` 是 OE，接 1。
- **ROM contents**：`addr/data: 14 32` 后跟十六进制值列表，少写地址按 0 填充。
- **横线拆分**：Splitter 分支等宽，16→14+2 要 8×2 拆分 + 7×2 合并，不能直接拆 2+14。
- **外观**：`bank8` / `rom64k` / `ram64k` 都用圆角框 + 名称牌 + 端口标签；父电路按外观端口布线。
- **验证**：分层跑 `bank8 → 数据通路 → 控制逻辑 → ram64k → rom64k → main`；
  3.2 实测 `main` 37/37、`ram64k` 16/16、`bank8` 7/7。

最常用的排查顺序：全 `U` 先查 `#Plexers` 库和 Pin 是否入网；写不进先单 bank 直连；
字节错位先查字节序；`stats` 加载失败先删 autosave；`audit` partial 时以 `-w` 为准。

## 8.6 Logisim 2.7.1：32 位 CPU / 3072×32 DM

`references/cpu271-casebook.md` 是一次 2.7.1 CPU 纠错的完整复盘。要点：

- **版本隔离**：`<project source="2.7.1">` 的文件不要用 5.0 的 `circ_audit/circ_sim/circ_geometry`，
  改用 `circ271_check/circ271_sim/circ271_ports`。
- **DM 三错**：单块 4096×32（容量不对）、`ALU[0:11]` 字节地址当字地址（0x4/0x7 不同字）、
  无越界门控（写 0x3000 回绕覆盖 0x0000）。
- **DM 正确结构**：3×1024×32；`ALU[13:2]` = 10 位 offset + 2 位 bank；写用 2:4 Decoder（`disabled=0`），
  读用 4:1 MUX；`ALU<0x3000` 与 `MemWrite` 过 AND 产生 `wr`。
- **典型隐藏坑**：Splitter 分支 y 坐标、门默认 5 输入、Decoder 禁用输出悬空导致 RAM 每拍误写、
  Register `en` 悬空等价使能、保存省略 `fanout/enable`。
- **写使能阵列必须逐单元扫描**：GRF/RAM 的 `en` 悬空=每拍都写，评测 trace 会整体错位（J14）；
  只测前几个寄存器不够，要给 r1..r31 各写唯一值再读回。
- **验证链**：`circ271_check`（0 error）→ `circ271_sim`（DM 12 项）→ 2.7.1 引擎 `DmTest` →
  2.7.1 引擎 `CpuSim`（整机 12 周期）。四层都过再交付。

常用调用：

```json
circ271_check {"file":"D:/CPU.circ","circuit":"DM"}
circ271_sim   {"file":"D:/CPU.circ","circuit":"DM",
               "inputs":{"MemWrite":1,"ALU result":"0x4","RD2":"0xdeadbeef"},
               "cycles":1,"watch":["ReadData","bank","wr"]}
circ271_ports {"file":"D:/CPU.circ","circuit":"DM","component":"Splitter"}
```

## 9. 四条不要做

- 不要用自己画的渲染图判断电路长什么样。视觉检查一律打开 Logisim 本体截图：
  自绘渲染器只能反映"你以为的几何"，元件外形、引脚朝向、总线粗细、`E`/`U` 红色标记、
  组件重叠提示全都不在里面——照着渲染图改，改的是渲染器不是电路。
  具体做法见 `references/verification.md` 第 5 节。
- 不要用隧道（Tunnel）省事——多数作业明令禁止，且截图看不出真实结构。
- 不要为省元件把多个功能塞进 5 入以上模块——端口会挤爆，且出错无提示。
- 不要只在顶层验证：分层电路必须每层都验，否则错误定位成本高 10 倍。

## 9.5 脚本目录按版本归类（不要跨目录混用）

```
scripts/
  v50/      evolution 5.0 专用：lib8 / route8 / sim / verify / router / logisim_gen / mem_gen
  v271/     2.7.1 与 2.16(ITA) 专用：circ271 / ita_probe / netcheck / ita/ITAProbe.java
  common/   与版本无关：gui.py（找窗口、点击、截图）
```

**判据是 `.circ` 的 `source=`，不是你装的 Logisim 版本。**
`source="5.0"` → 只能用 `v50/`；`source="2.16..."` 或 `2.7.x` → 只能用 `v271/`。
两套几何的端口偏移完全不同，混用会出现「修好一处、另一处又坏」。
版本矩阵与各版本几何对照见仓库 `docs/VERSIONS.md`。

## 10. 资源

| 文件 | 内容 |
|---|---|
| `references/counter13-casebook.md` | 13 进制计数器实战复盘：13 个坑 + 验证矩阵 + 排查决策树 |
| `references/memory-casebook.md` | 64KB ROM/RAM 低位交叉：结构、RAM/ROM 5.0 端口、生成器、37/37 验证、12 坑 |
| `references/cpu271-casebook.md` | 2.7.1 32 位 CPU 纠错复盘：DM 三错、ROM、四层验证链、10 条语义坑、决策树 |
| `references/geometry.md` | 端口/尺寸常量（含 3.9 vs 5.0 对照）、布线语义、布局与压缩 |
| `references/dsl.md` | `circ_build` 的 DSL 完整参考：字段、端口名、自动布局、报错含义 |
| `references/circ-format.md` | `.circ` XML 结构、库索引、组件属性、toolbar、版本差异 |
| `references/verification.md` | CLI 参数、`.vec` 格式、用例设计、双工程策略、GUI 截图 |
| `references/appearance.md` | 子电路外观：spec、自动排版、保端口/重排、保存校验 |
| `references/pitfalls.md` | 实战坑表：A-G 组（4 位规模）+ H 组（8 位总线/展平/Windows 环境/外观与 GUI 自动化）+ I 组（存储器/工程头/connect 盲区）+ J 组（Logisim 2.7.1）+ K 组（Logisim-ITA 2.15，K1~K19 + K30~K52；K20~K29 见 controller215-casebook） |
| `references/adder215-casebook.md` | 实验2「串行 + 快速加法器」2.15 实战：半加/全加/4位/8位可控加减、CLA、16 位级联、C15/C16 语义、验证矩阵 |
| `references/alu215-casebook.md` | 实验3 8位 ALU（带比较器）2.15 实战：移位/比较/算术/逻辑、标志语义、16604 行验证、K12~K19 新坑、布局压缩记录 |
| `scripts/v50/logisim_gen.py` | XML 生成器：pin / gate / sub / splitter / display / wire / project |
| `scripts/v50/router.py` | 通道布线器：正交、避让、禁止共线重叠（4 位规模） |
| `scripts/v50/verify.py` | `-t table` / `-t stats` / `-w` 的封装（自动找 jar、GBK 解码） |
| `scripts/v50/lib8.py` | 8 位总线生成库：Board / 门/DFF/分线器/子电路/Constant/Clock 几何 + project |
| `scripts/v50/route8.py` | 确定性布线：z/w 折线 + 六项自检 + verify_nets/verify_short + paste/canonicalize |
| `scripts/v50/sim.py` | 向量测试封装：`<set> <seq>` 时序、jar 自动探测、verify_alive 防假通过 |
| `scripts/v50/mem_gen.py` | 64KB ROM + 64KB RAM 生成器：bank8/ram64k/rom64k/main + 自定义外观 + 自检 |
| `scripts/v271/ita/ITAProbe.java` | **2.16/2.7.1 headless 探针**：加载/设引脚/打时钟/读输出（`--list/--set/--vector/--trace/--ends/--errors`）；`ProbeLoader` 把加载异常打成 `LOADERR` |
| `scripts/v271/ita_probe.py` | 探针 Python 封装：自动编译，`list_pins/eval_pins/run_vector(trace=True)/ends/errors` |
| `scripts/v271/netcheck.py` | **位宽冲突定位**：真实端口坐标 + 导线图建网，一次列全冲突点 |
| `scripts/v215/board215.py` | 2.15.0.2 实测几何 + Board 追加式构建器 + 六项正交布线自检；含 mux/cmp/const/ext/shifter/split 与 fan_bits/fan_stub |
| `scripts/v215/gen_adder_lab2.py` | 实验2 加法器生成器：7 个电路，在原验证框架上追加（不覆盖原元件） |
| `scripts/v215/verify_adder_lab2.py` | 加法器功能向量：穷举 + 随机，走 2.15 引擎 |
| `scripts/v215/calib_lab3.py` | 实验3 元件标定：MUX 2/4/8:1、Comparator、Bit Extender、Shifter、2/3/8 位 Splitter 真实端口 |
| `scripts/v215/gen_alu_lab3.py` | 实验3 8位 ALU 生成器：5 个新电路 + 紧凑布局 + 六项自检 |
| `scripts/v215/verify_alu_lab3.py` | 实验3 功能向量：模块级 + ALU 顶层，16604 行 |
| `references/controller215-casebook.md` | 实验4 控制器 2.15 复盘：9 个模块、指令字段/真值表、T0~T3 时序、K20~K29、布局间距与重叠检查 |
| `scripts/v215/calib_lab4.py` | 实验4 元件标定：Register/Counter/DFF/RAM/ROM/Decoder/多分支 Splitter |
| `scripts/v215/gen_ctrl_lab4.py` | 实验4 生成器：Regs/PC/IR/ID/CLK/S-I/B/Flag/CU/系统连接 |
| `scripts/v215/verify_ctrl_lab4.py` | 实验4 验证：9 个电路 112 行向量 |
| `references/instruction215-casebook.md` | 实验5 指令分析 2.15 复盘：指令/S-op 编码表、四个程序机器码、PC+n/条件跳转、600 行逐拍向量、K30~K40 |
| `scripts/v215/gen_lab5.py` | 实验5 生成器：Regs+Q0~Q3、符号扩展 S-I/B、4 ROM+Prog、A 通道移位 MUX、Flag 门控 |
| `scripts/v215/verify_lab5.py` | 实验5 验证：ISA 模型 + 六场景逐拍向量（600 行），含例4 三分支 ROM 变体 |
| `references/storage215-casebook.md` | 实验6 存储器 2.15 复盘：D1 4×4K×32→16K×32、16×16 姓名显示、存储器问答、K41~K52 |
| `scripts/v215/gen_lab6.py` | 实验6 生成器：在 2.7.1 素材上补 D1 字扩展、姓名显示、问答电路 |
| `scripts/v215/verify_lab6.py` | 实验6 验证：D1 9 个机内码 + 姓名显示 17 行逐拍向量 + ERRCOUNT |
| `scripts/v215/probe_points.py` | 按坐标读运行值 / `--dump`，排查中间网络 |
| `scripts/v215/test_wide.py` | 最小复现：宽 Pin、分线器、隧道驱动关系 |
| `scripts/v215/LoadTest.java` | 加载错误探针：覆写 `Loader.showError`，打印被 GUI 吞掉的真实异常 |
| `scripts/common/gui.py` | GUI 自动化：ctypes+PIL 找窗口/点击/送键/滚轮缩放/截图/启动载入（沙箱内可用） |
| `assets/full-adder.circ` | 已知可用（真值表 8/8）的最小参考工程，5.0 格式 |

### 测试向量的静默陷阱（务必自检）

`-w` 的行字段数必须等于列数（`<set>`/`<seq>` 各算一列）。少写一个 `<DC>` 时 Logisim
可能只打印「正在加载测试向量」就结束，或者把该行当空通过——`通过：N` 依然会出现，
看起来全过，实际一行都没比对。

自检办法（三选一，至少做一条）：

- 输出里必须出现 `expected` 字样（失败行才打印，全过时看不到）→ 于是改用下一条；
- 把某一行的期望值故意写错，确认它报 `失败：1`，再改回来；
- 确认 `通过数 == 表格行数`，且首行表头字段数与每行字段数一致（写脚本断言）。
