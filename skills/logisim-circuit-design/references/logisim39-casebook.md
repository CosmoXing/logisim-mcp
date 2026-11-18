# Logisim 3.9 内核探针 casebook（无头驱动 + 生成电路布线陷阱）

本文记录 2026-11 用 3.9 本体内核做「加载体检 → 格式迁移 → 无头功能验证 → 布线级调试」的完整经验。
配套 MCP 工具：`circ39_check` / `circ39_save` / `circ39_run` / `circ39_debug`
（mode：wires / onet / multi / nets / insts / ends / bounds / pins / vals / overlap）。
迁移格式本身（toolbar/mappings 补 lib）见 pitfalls L14，这里不重复。

适用场景：自绘网表仿真器（netlist.py）与真引擎结论冲突时、`-t table`/`-w` 只能验组合逻辑时、
GUI 里"看着对但跑不对"时 —— 一律以 3.9 真实内核的探针结论为准。

## 1. 探针工具族（server/java/src/g39probe/，首次调用自动 javac）

| 探针 | 用途 | 一句话 |
|---|---|---|
| G39Load | 加载体检 | 报错与 GUI 弹窗同款 + 电路清单 |
| G39Save | 格式重存 | 5.0 存盘 → 原生 3.9 格式（元件/导线数不变） |
| G39Seq | 功能验证 | 脚本化多拍时序：`pin=val` / `t` 打拍 / `r` 读输出 |
| G39Wires | 布线调试 | 导出**加载后**导线（WireRepair 之后）——与 XML diff 找被裁的线 |
| G39OneNet | 布线调试 | 列出包含 (x,y) 的网络全部成员 |
| G39NetList | 布线调试 | 扫多驱动网（同一网 ≥2 输出端）＝真实短路 |
| G39Nets | 接线检查 | 未接线端口扫描（circuit 可传 all） |
| G39Inst | 几何测量 | 某类元件实例的端口索引/坐标/位宽（可查子电路实例） |
| G39Idx / G39Bounds / G39Dump / G39Vals | 几何/取值 | 子串过滤端口 / 包围盒 / Pin 属性 / 坐标线值 |

jar 定位：`LOGISIM39_JAR` > `logisim.local.json` 的 `logisim39_jar` > 常见安装位置。
运行环境变量 `W="(x,y);(x,y)"` 可让 G39Seq 在每个 `r` 步附加打印坐标线值。

## 2. G39Seq 探针语义的四个坑（结果不对先查这些，别怀疑电路）

1. **设值后必须 `markComponentAsDirty` + `markPointAsDirty` 再 propagate**，
   否则新值不生效，电路会被误判成坏的。多个引脚要**全部设完再统一 propagate 一次**。
2. **`t` 打拍的语义**：clk 是 Pin → 手动 0→1→0；有 Clock 组件 → `toggleClocks` 两次。
   `toggleClocks` 只在有 Clock 组件时有效。
3. **未设引脚 = U 不是 0**。clk 初值是 U 时，第一次 `t` 的 U→1 **不算上升沿**。
   脚本第一步先 `clk=0` 归零再开始。
4. **子电路作为根时，引脚驱动不完全可靠**（初始化时序问题）。正式功能验证一律走顶层 main；
   子电路内部观察用坐标级 `G39Vals` / `W` 环境变量。

另一个容易踩的观察坑：**中段坐标读不出值**。Logisim 传播图节点只在导线端点/结点上，
`cs.getValue()` 对线中间的点返回 null（探针打印 `-`）。这不是断线，换端点读。

## 3. 生成电路的布线陷阱（全部由探针定位过，代价惨痛）

按"症状 → 根因 → 规则"记。共同背景：Logisim 加载时会做 WireRepair，
**XML 里的 `<wire>` 与加载后的真实导线可能不同**——所以布线争议一律 `circ39_debug wires` 导出
加载后导线与 XML diff。

### M-规则1：分线器 `incoming` 必须 = 总线位宽
写 1 会把整条总线当 1 位，全断。`fanout` 是分支数、`incoming` 是总线位宽，两个字段别混。

### M-规则2：Register 端口几何（3.9 实测）
`D=+30、en=+50、clk=+70`（同一侧从上到下），`clr=+30/+90`、`Q=+60/+30`。
en 和 clk 极易接反——接反的表现是"写了永远不生效"。用 `circ39_debug insts Register` 量，别凭记忆。

### M-规则3：共线重叠 = 合并 = 跨网短路
两根同向同线坐标的导线哪怕只重叠 1px，加载时会被合并成一根：
- 若共享端点（一根是另一根的前缀/后缀）→ 冗余，无害；
- **不共享端点 → 真短路**，且往往表现为"一条线断供（U）+ 另一条线被错接"。

实例（3.1 重设计版）：raddr2 合并线 `(400,540)-(540,540)` 与 bank1 的 ridx1 支线
`(500,540)-(600,540)` 重叠 40px → 加载后合并成 `(400,540)-(600,540)`：
ridx2 干线断供（全 U，B 读口恒 0），bank1 的 ridx1 被错接到 raddr2 位线上。
检查：`circ39_debug overlap`（纯 XML 扫描，区分真短路/冗余重叠）。

### M-规则4：元件体压线 → WireRepair 直接裁线
Ground 放在时钟干线上（横线从元件体里穿出去），加载后干线被裁断。
元件要么放在两干线之间的空档，要么横线绕开元件体。

### M-规则5：通道竖线的**端点**落在别的线上 = T 短路
端点落在别的位线/干线上会连过去（十字交叉不算，端点/端口才算）。
布通道时先查终点的 (x,y) 是不是别人的端点。

### M-规则6：Splitter 是无源直通，两端都标 isOutput
3.9 里 Splitter 的 EndData 两端 `isOutput()==true`。扇出分线器 → 合并分线器同网是**正常接法**，
不是双驱动。扫多驱动网时必须把 Splitter/Tunnel 端按 io 计，否则全是误报。

### M-规则7：走线永远别跟干线/支线同行（同 y 的横线、同 x 的竖线）
横向通道选 y 时，先列出所有已有水平线的 y；竖向通道选 x 同理。
生成器布线前先跑 `circ39_debug overlap`，真短路=0 再往下走。

## 4. 迁移收尾的标准动作

1. `circ39_check`：加载无报错（L14 的 lib 问题在这里暴露）。
2. 修 lib 后 `circ39_save` 重存 → `source="3.9.0"`、引脚 `output="true"`。
3. `circ39_debug overlap`：真短路=0。
4. `circ39_debug multi`（逐电路）：多驱动网=0（Splitter 已按 io 排除）。
5. `circ39_debug nets all`：未接线端口只允许是"设计上就不用"的（如 Comparator 的 gt/lt）。
6. `circ39_run` 走顶层 main 验功能；多比特引脚建议设 radix
   （数据 `radix=16`、地址 `radix=10unsigned`），否则 GUI 里 32 位二进制既难输也难读。

## 5. GUI 侧的配套经验

- `clk` 是输入引脚（无 Clock 组件）时，**Ctrl+K / 自动仿真不产生时钟沿**，
  必须手动点 clk 0→1 再点回 0。要在说明文档里写给用户。
- 画布内容整体跑出可视区（如全部在 (1070,1290) 之外）→ 打开像空文件；
  整体平移所有坐标即可（只动 `<circuit name="main">` 块内的坐标）。
- GUI 里电路树双击进不去时：复制文件把 `<main name="X"/>` 改成目标电路即可直接查看该电路。
