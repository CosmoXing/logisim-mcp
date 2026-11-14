# 2.7.1 32 位 CPU 纠错复盘（DM / ROM / 验证链）

> 场景：用户给了一份 Logisim **2.7.1** 格式的 32 位 CPU（`main` + `IFU` + `Controller` +
> `GRF` + `ALU` + `DM` + `NPC` + `EXT` + 两个逻辑块），要求「在 2.7.1 下修好，所有操作都在
> 2.7.1 完成」。最终交付 `CPU_fixed2.circ`：DM 严格 3×1024×32，整机 9 条测试指令全对。
>
> 本文只记录**与 2.7.1 有关**的结构、坑和验证方法；5.0 的几何/生成器见其他参考。

## 1. 任务要求（验收表）

| 项目 | 要求 | 原文件 | 修复后 |
|---|---|---|---|
| CPU 位宽 | 32 位 | 满足 | 满足 |
| IM | 4096×32，PC 从 0x3000 开始 | 结构对，ROM 无程序 | 写入 9 条测试指令 |
| DM | 3072×32，0x0000–0x2FFF | **单块 4096×32** | 3×1024×32 |
| DM 寻址 | 字节地址按字对齐 | **`ALU[0:11]` 直接当字地址** | `ALU[13:2]` |
| DM 越界 | 仅 0x0000–0x2FFF 可写 | **无保护，0x3000 回绕到 0x0000** | Comparator + AND 门控 |
| DM 端口 | 读/写数据分离 | `bus=separate` | 同 |
| 复位 | 异步 reset，顶层驱动 | 连线通但 Pin 无 label | 加 `label=reset` |
| 时钟 | 单时钟 | 满足 | 满足 |

## 2. 原文件到底错在哪

### 2.1 DM：三个致命错误

原 DM 只有 8 个元件：1 片 4096×32 RAM、6 个接口 Pin、1 个 `fanout=3` 的 Splitter。

| # | 位置 | 症状（2.7.1 实测） | 根因 |
|---|---|---|---|
| 1 | `RAM@(420,260) addrWidth=12` | 容量 4096×32，覆盖到 0x3FFF | 只放了一片 RAM，没实现 3 bank |
| 2 | `Splitter@(180,290)` 分支 0（`bit0..bit11`）→ `RAM.A` | 写 0x0004 读 0x0007 得 0 | 字节地址直接当字索引，未右移 2 位 |
| 3 | `MemWrite Pin@(170,450)` → `RAM.str` | 写 0x3000 后 0x0000 变成 0xFFFFFFFF | 无越界判断；12 位地址截断 `0x3000 & 0xFFF = 0` |
| 4 | Splitter 分支 1/2 | 两条 10 位分支悬空 | `fanout=3` 的拆分方案没接完 |

### 2.2 IFU / ROM

| 位置 | 症状 | 根因 | 处理 |
|---|---|---|---|
| `ROM@(670,120) contents` | 取指恒为 `0x00000000` | 只有 1 个全 0 字 | 写入 9 条测试程序 |
| `Register@(430,220)` 的 `en(400,230)` | 悬空但 PC 仍 +4 | 2.7.1 只在 `en==FALSE` 时禁止加载 | 显式接 1 位常量 1（加固） |

### 2.3 main

`Pin@(60,80)` 没有 label，但导线连到 `Tunnel(80,80)[reset]`，复位网络实际是通的；
补 `label=reset` 属于可观测性/测试向量便利，不是功能修复。

## 3. 修复后的 DM 结构

```
ALU result (32)
   ├─ Splitter  ALU[2:11] → offset(10) ──┬→ RAM0.A / RAM1.A / RAM2.A
   │            ALU[12:13] → bank(2) ────┼→ Decoder.sel
   │                                     └→ MUX.sel
   ├─ Comparator(unsigned)  ALU < 0x3000 ─┐
   │                                      AND → wr → Decoder.en
   └─ MemWrite ───────────────────────────┘

写：RD2(32) → 三片 RAM.D；Decoder(2:4, disabled=0) → str0/1/2
读：RAM.Q → q0/q1/q2 → 4:1 MUX → rdata → ReadData
```

关键属性：

- RAM：`addrWidth=10, dataWidth=32, bus=separate`
- Decoder：`select=2, enable=true, disabled=0`
- Comparator：`width=32, mode=unsigned`
- MUX：`select=2, width=32`，第 4 路接常量 0（bank=3 读 0）

## 4. 验证链（四层，缺一不可）

| 层 | 工具 | 检查内容 | 结果 |
|---|---|---|---|
| 1. 网表 | `circ271_check` | 位宽、驱动、穿体、sel/en 接入、Tunnel 宽度 | 0 error / 0 warning |
| 2. 模块功能 | `circ271_sim` | DM 12 项：同字别名、3 bank、越界、写使能、覆盖写 | 12/12 PASS |
| 3. 引擎模块 | Java `DmTest` | 用 2.7.1 本体引擎跑 DM（真实语义） | 全部读回正确 |
| 4. 引擎整机 | Java `CpuSim` | 12 周期逐拍看 pc/Instr/WA/WD/RegWrite/MemWrite | 9 条指令全对 |

整机最终状态：

```
r1=12340000  r2=12345678  r3=2468ACF0  r4=12345678  r5=12345678  r6=0
DM[0]=12345678（q0），beq 成立跳过 0x301C
```

补充：布局用 `OverlapCheck`（`Component.getBounds()` 两两求交）确认 `overlaps=0`。

## 5. 2.7.1 语义坑清单（实现修复时逐个踩中）

| # | 坑 | 结论 |
|---|---|---|
| 1 | Splitter 分支 y | east `y-10*fanout+10*i`；west `y+10*(i+1)` |
| 2 | 门默认 5 输入 | 输入在 `x-50`，纵向 40px 均布（2 输入 `y±20`）；只接 2 根线会输出 x |
| 3 | Decoder 禁用输出 | 默认 `Z`；RAM 的 WE 是「≠0 即写」，悬空会每拍误写 → `disabled=0` |
| 4 | sel/en 接入方向 | 必须从符号下方接入，横穿会悬空/报错 |
| 5 | RAM 五控制脚 | `str/cs/clk/oe/clr`；CS/OE 悬空=使能，WE 悬空=一直写 |
| 6 | Register en | 仅 `FALSE` 禁止加载，悬空=使能 |
| 7 | Pin.setValue | 只存值不传播，必须 `markComponentAsDirty` |
| 8 | 子电路实例端口 | 不等于内部 Pin 坐标平移（按侧/顺序 10px 打包），内部可自由重排 |
| 9 | 保存省略默认属性 | `fanout`、`enable` 会消失，工具要推导/默认 |
| 10 | 无 `-w` 测试向量 | 2.7.1 只能网表仿真或引擎仿真 |

### 5.1 追加案例：GRF 的 $27 写使能缺口（评测器发现）

评测报：`lw $27,0($5)`（0x8c9b0000）得到 `@0x307C: $27 <= 0xffffffff`，
而参考 trace 期望 `@0x3060: $17 <= 0`，并注明“上一条 `lw $15,0($23)` 正确”。

定位过程：

1. 写一个「r1..r31 各写唯一值再读回」的扫描程序（`ori $i,$0,0x100+i`），
   结果**只有 $27 没写进去**，其余 31 个正常。
2. 对照相邻寄存器的写使能走线：

| 寄存器 | AND 门 | 竖线 | en | 横线 |
|---|---|---|---|---|
| $26 @(940,490) | (870,540) | (870,500)→(870,540) | (910,500) | (870,500)→(910,500) ✓ |
| $27 @(940,600) | (870,650) | (870,610)→(870,650) | (910,610) | **缺失** ✗ |

根因：$27 的 `en` 悬空。2.7.1 的 Register 只认 `en == FALSE` 才禁止加载，
悬空(unknown) ≠ FALSE → **等价使能**，$27 每个时钟沿都被写入当前 WD。
评测器逐写事件比对 trace，多出来的 `$27 <= ...` 事件让序列整体错位，
`0xffffffff` 只是错位后对齐到的某一拍 WD。

修复：补 `(870,610)->(910,610)`。验证：

- GRF 静态检查 `0/0`；
- 全寄存器扫描 r1..r31 全部正确（r27 = 0x11b）；
- 时序：`ori $27,$0,0x1B` 后继续执行其它 `ori`，r27 保持 0x1B；
- 整机 9 条指令回归通过。

教训：**有写使能的阵列必须逐单元扫描**。悬空的 `en/cs/oe` 不报错，但会静默多写；
单条指令测试可能“碰巧通过”，只有 trace 级比对才会暴露。

## 6. 排查决策树（2.7.1）

```
读回 x
 ├─ 读地址的 bank/offset 有 x？
 │   ├─ 是 → Splitter 分支坐标是否接对（J1）；fanout 是否被省略（J11）
 │   └─ 否 → 读 MUX 的 sel 是否来自 bank；MUX.en 是否被误接 FALSE
 ├─ RAM 每拍都在变？
 │   ├─ 是 → Decoder 禁用输出悬空（J3）→ disabled=0；str 是否明确为 0
 │   └─ 否 → 看 clk/clr 是否接对（str=-110, clk=-70, clr=-30）
 └─ 越界地址写后把低地址改了？
     └─ 是 → 地址位宽/字对齐 + 越界门控（J12）
```

## 7. 可复用命令

```bash
# MCP（推荐）
circ271_check {"file":"D:/CPU.circ","circuit":"DM"}
circ271_sim   {"file":"D:/CPU.circ","circuit":"DM",
               "inputs":{"MemWrite":1,"ALU result":"0x4","RD2":"0xdeadbeef"},
               "cycles":1,"watch":["ReadData","bank","wr"]}
circ271_ports {"file":"D:/CPU.circ","circuit":"DM","component":"RAM"}

# 引擎级（需要 JDK + Logisim 2.7.1 jar）
javac -cp logisim-generic-2.7.1.jar -d classes DumpPorts.java OverlapCheck.java DmTest.java CpuSim.java
java  -cp "classes;logisim-generic-2.7.1.jar" CpuSim D:/CPU_fixed2.circ 12
```

## 8. 一句话结论

2.7.1 的 CPU 纠错，真正致命的是 **DM 的容量/字对齐/越界** 与 **ROM 无程序**；
`en` 悬空和 `reset` 无 label 属于隐式语义/可观测性。修 2.7.1 电路时，
**几何一律实测、语义一律查引擎**，不要用 5.0 的直觉。
