# Logisim 3.9 单周期 MIPS CPU casebook（复用 3.1/3.3/3.4 部件 + 无头整机验收）

本文记录 2026-11 用 **Logisim-evolution 3.9.0 内核** 完成「9 条指令单周期 MIPS CPU」的完整复盘：
课程给定的 3.1 寄存器堆 / 3.3 ALU / 3.4 控制器如何合并、`stp` 停机与周期计数怎么接、
以及一次真实的「6 个测试程序全过」是怎么验出来的。

配套脚本（本目录）：

| 文件 | 用途 |
|---|---|
| `scripts/v39/gen_cpu39.py` | 从 3.3/3.4 的 `.circ` 提取 `ALUwith9ins`/`Controller`，生成 `Bank8`/`RegFile`/`IM`/`DM`/`main`，可批量生成 6 个测试程序版本 |
| `scripts/v39/Probe39.java` | 3.9 内核无头探针：加载 → 设引脚 → 打拍 → 读顶层输出 → 预装/导出 RAM |
| `scripts/v39/probe39.py` | 探针封装（自动 javac、jar 定位、参数拼装） |

对应 MCP 工具：`circ39_check` / `circ39_run` / `circ39_debug`。**注意**：本 casebook 的探针
额外解决了「RAM 预装 / RAM 导出 / 子状态读数」三件 `circ39_run` 没覆盖的事。

---

## 1. 目标结构与指令语义

9 条指令：`ori/lui/addu/sub/slt/bne/lw/sw/stp`。控制器（3.4 `Controller`）一次译码输出：
`RegDst/ALUSrc/Branch/MemRead/MemWrite/RegWrite/MemtoReg/Expand/Stp/ALUControl(4)/Slt/Imm32(32)`。

实测译码结果（`ALUOp → ALUControl`）：

| 指令 | opcode | func | ALUControl | Slt | Expand | 备注 |
|---|---|---|---|---|---|---|
| addu | 000000 | 100001 | 1 | 0 | 0 | 加 |
| sub | 000000 | 100010 | 2 | 0 | 0 | 减 |
| slt | 000000 | 101010 | 2 | 1 | 0 | 减法符号位回写 |
| ori | 001101 | — | 3 | 0 | 1 | 零扩展（Expand=1） |
| lui | 001111 | — | 4 | 0 | 1 | ALU 内左移 16 |
| bne | 000101 | — | 2 | 0 | 0 | Zero=0 且 Branch=1 跳转 |
| lw | 100011 | — | 1 | 0 | 0 | 符号扩展 |
| sw | 101011 | — | 1 | 0 | 0 | 符号扩展 |
| stp | 111111 | — | 0 | 0 | 0 | 全部控制清零，Stp=1 |

关键点：

- `slt` 不在 ALU 内完成，而是 `ALUControl=2` 做减法 + `Slt=1` 在写回级取 `ALUResult[31]` 零扩展。
- `lui` 的 ALU 码 4 是「source2 << 16」，配合 `ALUSrc=1` 与零扩展立即数。
- ROM/RAM 的字地址都取字节地址 `[15:2]`：PC 与 ALU 结果都是字节地址，PC 每拍 +4。

## 2. 顶层数据通路（main）

```
PC ──► IM(A=PC, 16K×32) ──► split{opcode,rs,rt,rd,func} / split{imm[15:0]}
        │
        ├─► Controller(opcode,func,imm) ──► 控制信号 + Imm32
        ├─► RegFile(raddr1,raddr2,waddr,wdata,wen,clk,reset)
        ├─► ALUwith9ins(src1,src2,ALUControl) ──► ALUResult / Zero
        ├─► DM(A=ALUResult, DIN=rdata2, WE, CLK) ──► DOUT
        └─► wb_mux(MemtoReg) → slt_mux(Slt) → RegFile.wdata
PC+4 ──► br_mux(Branch & ~Zero) ──► PC
```

补充约定：

- **无延迟槽**：`bne` 成立时紧跟的指令不执行；目标 = PC+4+（符号扩展 offset << 2）。
- **写回优先级**：`Slt` 高于 `MemtoReg`（两者互斥，但用两级 2:1 MUX 更稳）。
- **$0**：Bank8 内部译码到 0 号寄存器不接写使能，读恒 0。
- **停机**：`Stp` 置位停机触发器 → `cpu_clk = clk & ~stopped`；同时
  `PC.en = run & ~Stp`，否则 stp 那一拍 PC 仍会前进到下一条指令（见坑 g39-stp-freeze）。
- **周期计数**：16 位寄存器 + 1 个 16 位加法器，每个 `cpu_clk` 上升沿 +1；
  4 个数码管按**十六进制**显示，程序 5 的 583 拍显示为 `0247`。

## 3. 交付与验证

生成物：

```
单周期CPU.circ                  空白设计（ROM 一个 0 字）
测试程序/G1-T1..T6.circ          ROM 已按程序装好（RAM 需运行前载入 hex）
测试程序/RAM初始化数据/*.hex      原始 RAM/ROM hex
```

RAM 初值**不随 .circ 保存**（Logisim 的 RAM 没有 contents 属性），运行时：
双击 `DM` → 右键 `RAM` → Edit Contents → Load Image → 选 `G1-Tx-RAM.hex`。

无头验收（`probe39.py`）：

1. 复位：`Reset=1` 传播（异步清 PC/RegFile/计数器/停机触发器），再 `Reset=0`；
2. 预装 RAM：`ram=G1-Tx-RAM.hex`（探针内部 `Ram.getContents(state).set(i,v)`）；
3. 逐拍：读取 `PC/instr/ALU/MemWrite/cycle/stop`，`clk=1→0` 打一拍；
4. 停机后导出 RAM 非零字，与测试文档逐字比对。

实测结果（全部通过）：

| 程序 | 周期（hex） | RAM 关键结果 |
|---|---|---|
| T1 lw/sw/stp | 0x0003 | 0x1=0000eeee，0x2=00001111 |
| T2 addu/sub/slt | 0x000f | 0x2=3333，0x3=ffffeeef，0x4=1，0x5=0，0x6=ffffffff |
| T3 lui/ori | 0x0006 | 0x1=66660000，0x2=6666ffff，0x3=ffffffff |
| T4 bne | 0x0005 | 0x2=0，0x3=bbbbbbbb，0x4=0 |
| T5 斐波那契 | 0x0247（583） | 0x00..0x3f 为第 3~66 项，0x3f=8b44a658 |
| T6 学号分支 | 0x0013 | 偶数 0x78966a00：0x1=78965c23，0x2=ddd，0x3=78964e46，0x4=0 |

## 4. 本次踩到的坑（编号与 knowledge.json 对应）

### 4.1 生成/外观/端口

- **g39-pin-output-attr**：3.9 的 Pin 输出属性是 `<a name="output" val="true"/>`；
  写成 `type="output"` 不报错但被当输入，子电路输出脚变成「输入驱动内部导线」，
  整条网显示 `E`/`U`。本次 `IM.DOUT`、`dbg_*` 全中招。
- **g39-circ-anchor**：自定义外观的 `<appear>` 必须补
  `<circ-anchor facing="east" x="0" y="0"/>`。缺省时实例锚点落在右中，
  实测 `IM` 端口从 `loc+(0,30)` 变成 `loc-(270,30)`，父电路全部脱线。
- **g39-inst-port-offset**：实例端口 = `loc + circ-port(x,y)`（3.9 与 5.0 一致）。
  端口坐标必须从 `<circ-port pin="x,y">` 反查；外观改过就要重布父电路。
- **g39-port-map-swap**：3.1 `FourEights` 的 `circ-port` 顺序是
  `raddr1(0,30) / raddr2(0,50) / waddr(0,70)`，按内部 PIN 列表顺序猜会三口错位，
  表现为「写 $2 却改到 $1」。
- **g39-offgrid-port**：`ALUwith9ins` 的 `ALUResult` 在 `(x+220, y+45)`，**不在 10px 网格**。
  lib8 的 A* 布线按 10px 网格取整，会把线走到 `y+40`，留下 5px 断口；
  必须先用一段 5px 短桩把端口拉到网格点，再从网格点布线。

### 4.2 布线器（lib8/route8）

- **g39-router-samename**：`b.w()` 把「端点落在另一条线上」判为共线重叠，
  但**同名网络**会跳过检查。干线 + 分支必须统一用同一个 net 名（`r1`/`wdata`…），
  否则每个 T 接都报错。
- **g39-collinear-overlap**（已有）：跨网水平线不能共线；干线通道要错开 10px。
- 本次 4 个 bank 的输入总线采用「x=560..650 六条干线 + 横向 tap」：
  tap 只与干线 T 接、与其它干线**垂直交叉**（Logisim 内点交叉不导通），
  比 A* 更可控；32 条 Q 输出用 x=950..1030 的独立竖井接到 4:1。

### 4.3 存储与仿真语义

- **g39-rom-empty-contents**：`<a name="contents"/>` 为空时 3.9 加载直接
  `NullPointerException: MemContents is null`。空白工程至少写 `addr/data: 14 32\n00000000`。
- **g39-ram-no-persist**：RAM 没有 contents 属性，初值不写进 `.circ`；GUI 要
  Edit Contents→Load Image，无头用 `Ram.getContents(InstanceState).set()`。
- **g39-ram32-geometry**：3.9 RAM(14×32) 端口
  `A(0,10) WE(0,50) EN(0,60) CLK(0,70) D(0,90) Q(240,90)`，body 240×250；
  ROM 为 `A(0,10) Q(240,60)`。`EN` 悬空会让读出口变 U。
- **g39-decoder5-geometry**：5 位 Decoder 输出 `(20, -10*(2^n-i))`（out0 最上），
  `sel(0,0)`、`en(-10,0)`；`disabled=0` 才能在 en=0 时输出 0。
  32:1 MUX 输入 `(x-40, y-160..150)`、`sel(-20,160)`、`out(0,0)`。
- **g39-propagate-until-stable**：`propagate()` 调 1~3 次可能仍在中途，
  会读到 ALU 的瞬态 `E`。应循环到返回 `false`（上限 20 次）再采样。
- **g39-pin-set-dirty**：无头设引脚必须
  `Pin.setValue → setPort → markComponentAsDirty → propagate`；
  只 `setPort` 会被 `Pin.propagate` 用旧 intendedValue 覆盖（表现为「设了 0 仍读 1」）。
- **g39-subcircuit-pin-unreliable**：把子电路当根电路设引脚不可靠（初始化时序），
  功能验证一律走顶层 `main`；子电路内部值通过 `cs.getSubStates()` 逐层读坐标。
- **g39-clock-headless**：电路里有 `Clock` 组件时，`Simulator.tick()` 会走
  `ComponentSelector`→`JTable`，无头直接抛异常。方案：测试副本把 Clock 换成 `clk` Pin
  手动 0→1→0；或 `Propagator.toggleClocks()` 连调两次。
- **g39-cycle-hex**：周期数码管是十六进制；583 要显示 `0247`。
- **g39-stp-freeze**：只门控时钟不够——stp 那一拍 PC 仍会前进，导致控制信号不为 0。
  `PC.en` 必须同时受 `~Stp` 控制。

### 4.4 复用 3.1 寄存器堆的致命问题

- **g39-rf-writethrough**：3.1 `FourEights` 在 `wen=1 && raddr==waddr` 时
  读口直接返回 `wdata`（写穿透）。单周期里 `addu $2,$1,$2` 形成
  `ALU→wdata→rdata→ALU` 组合环，结果随传播顺序漂移（实测 0x002ebb8d 等怪值，
  且 `ALUResult ≠ src1 + src2`）。
  解决：同接口重建 `RegFile`（4×`Bank8`，上升沿写、组合读、无穿透），
  保留 3.1/3.2/3.3/3.4 原文件备查。

## 5. 无头探针的最小可用骨架

```java
Loader loader = new Loader(null);
LogisimFile file = loader.openLogisimFile(new File(path));
Circuit circuit = file.getCircuit(name);
Project proj = new Project(file);
CircuitState cs = proj.getCircuitState(circuit);

// 设输入
Pin pin = (Pin) Instance.getInstanceFor(comp).getFactory();
pin.setValue(state, Value.createKnown(width, v));
state.setPort(0, Value.createKnown(width, v), 1);
cs.markComponentAsDirty(comp);
cs.getPropagator().propagate();

// 时钟：clk Pin 0→1→0（每次 propagate）
// 读输出：cs.getValue(pin.getLocation())
// RAM 预装/导出：((Ram) factory).getContents(subState.getInstanceState(ramInstance))
```

完整实现见 `scripts/v39/Probe39.java`（含 RAM hex 预装与导出、逐拍 trace）。

## 6. 验收清单（下单周期 CPU 前逐条打勾）

1. `circ39_check` 无加载报错；`circ39_debug nets` 只允许设计上有意悬空的端口。
2. `circ39_debug insts`：`IM/DM/RegFile/ALU/Controller` 的端口坐标与父电路导线一致。
3. `probe39` 复位后：PC=0、RegFile 读 0、计数器=0、stop=0。
4. 单条指令冒烟：`lw` 后 wdata=RAM[addr]；`sw` 后 RAM 改写；`stp` 后 PC 冻结、时钟停。
5. 6 个程序逐字比对 RAM（本文第 3 节表）。
6. 周期显示 = 指令条数（T5=583=0x247）。