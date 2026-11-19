# 实验7 I/O 接口实验 2.15 实战复盘（LED/按键/数码管/哑终端 + CPU 两总电路）

> 交付：`待修/全套210/周企航冶金学院/实验7 IO接口实验.circ`（33 个电路）。
> 工具：`scripts/v215/gen_lab7_io.py`、`verify_lab7_io.py`、`split_cpu_memory.py`、
> `tty_read.py`、`geo_probe.py`、`patch_clock.py`。
> 验证：2.15 原生引擎，`ERRCOUNT 0`；TTY 文本用 `TtyRead` 反射读回；
> 斐波那契 `Prog=2` 显示 `235831459431`，`Prog=0/1` 显示 `6/5`。

## 1. 需求拆解（实验7 共四块）

| 要求 | 实现电路 | 要点 |
|---|---|---|
| LED 计数器 + 按键 | `LED计数`、`实验7 I/O 演示` | 5 键 → 5 LED 的**温度计**编码：LED_k = OR(按键 k..5)，按 4 恰好 4 个亮 |
| 按键编码器 | `按键编码器` | 5 键 → 4 位二进制 1..5：C0=a\|c\|e、C1=b\|c、C2=d\|e、C3=0 |
| 七段显示驱动 | `七段显示驱动` | 4 位（In1=MSB…In4=LSB）→ g/f/a/b/e/d/c，真值表 0~9，A~F 全灭 |
| 哑终端三实验 | `存储器内容显示（TTY）`、`姓名显示（TTY）`、`键盘输入显示（TTY）` | 计数器扫 ROM → TTY；键盘经 AVL 直写 TTY |
| 思考题1 A~F | `七段译码器0~F` 等 | 原有 |
| 思考题2 CPU+TTY | `CPU` + `main` | 见第 3 节 |
| 思考题3 奇校验 | `2k+1奇校验` 等 | 原有 |

## 2. I/O 元件实测几何（2.15.0.2）

| 元件 | 端口（相对 loc） | 属性 |
|---|---|---|
| TTY | D `(0,-10)`、CLK `(0,0)`、**WR `(10,10)`**、**RST `(20,10)`** | `Char bit width` 只接受 **7 / 16**；`trigger=rising` |
| Keyboard | CLK `(0,0)`、RST `(10,10)`、RD `(20,10)`、AVL `(130,10)`、DATA `(140,10)` | `Char bit width` 7/16，`buflen` |
| 7-Segment Display | a `(+20,0)`、b `(+30,0)`、c `(+20,+60)`、d `(+10,+60)`、e `(0,+60)`、f `(+10,0)`、g `(0,0)`、dp `(+30,+60)` | `active=true` 才高电平点亮 |
| Button | `(0,0)`，输出 | — |
| LED | `(0,0)` | `active=true` |
| DotMatrix | 列口 `(10i,0)`，行模式 16 行时 16 个 16 位口 | `inputtype/matrixcols/matrixrows` |

**最容易错的两处**：TTY 的 WR/RST 是 `(10,10)` / `(20,10)`（不是 20/10、10/10 互换），
错接时 TTY 永不出字而 `ERRCOUNT` 仍为 0；`Char bit width` 写 8 会直接 `LOADERR`。

## 3. 两个总电路（CPU 子电路 + 整机测试）

把实验5 的 `系统连接` 拆成两层：

```
CPU（子电路）
  输入：CLK、RST、IR_IN[16]、RAM_Q[8]
  输出：PC[8]、IR[16]、RA[8]、RAM_A[4]、RAM_D[8]、RAM_WE、RAM_RD
        R0~R3、FLAGS、T0~T3、BOP、ALUY（观察口）
  内部：ALU、Regs、PC、IR、ID、CLK、S-I/B、Flag、CU（保留原有隧道命名）

main（整机测试）
  CPU 实例 + 4×16×16 程序 ROM（P0~P3 = 例1~例4，Prog 选择）
  + 4:1 选择器（out→IR_IN）+ RAM(4×8) + 256×7 个位数字 ROM + TTY
  RAM：A=RAM_A、D=RAM_D、str=RAM_WE、clk=T3、cs=0、oe=1、clr=0
  TTY 写使能：WE = T3 ? RAM_WE : 0
```

拆分步骤（`scripts/v215/split_cpu_memory.py`）：

1. 从 `系统连接` 删除 4 片 ROM、4:1 选择器、RAM、`Prog` 引脚；
2. 网络改名：`IRIN→IR_IN`、`RA4→RAM_A`、`RB→RAM_D`、`WM→RAM_WE`、`RM→RAM_RD`、`RAMQ→RAM_Q`；
3. `RAMQ` 输出脚改输入、`RB/WM` 脚改名，新增 `IR_IN/RAM_A/RAM_RD` 引脚；
4. **给新增/改名的引脚补 80px 引出线 + 同名隧道**（K61，必须做，否则整网悬空）；
5. 用实际 Pin 坐标生成 CPU 外观（`circ-port pin="x,y"`），父电路按 `loc+offset` 布线；
6. 程序 ROM 按**首条指令**归位：`2008=例1、200C=例2、2001=例3、2002=例4`（K64）。

验证：`Prog=2` → `235831459431`；`Prog=0` → `6`（0xB0 个位）；`Prog=1` → `5`（0xFF 个位）。

## 4. 哑终端无头验证方法

- `patch_clock.py`：把 Clock 换成 `CLK` 输入引脚（交付文件保留 Clock，测试副本换 Pin）；
- `tty_read.py`（`TtyRead.java`）：
  - 用 `Pin.setValue + propagate + markComponentAsDirty` 打拍，先 `RST=1` 两拍再放开；
  - `--set "Prog=2"` 设其它输入；
  - 结束后 `st.getData(comp)` 取 `TtyState`，反射调 `getRowString(i)` 打印 8 行文本；
  - `--probe "x,y,w;..."` 读任意坐标电平，用于定位中间网络。
- 只靠 `Simulator.tick()` 在无头 `Project` 里不产生 `TtyState`，会报 “TTY no data”（K62）。

## 5. 本组坑点（K61~K72）

见 `references/pitfalls.md`：引脚无引线不与同名隧道并网、2.15 门对 U 输入输出 E、
TTY 位宽只 7/16、TTY WR/RST 位置、程序 ROM 顺序、GB2312 全角数字、D2/D6 重名、
`&` 未转义、PowerShell 写文件带 BOM、无外观子电路端口不可猜、S-Regs 位序、ROM 地址位宽。