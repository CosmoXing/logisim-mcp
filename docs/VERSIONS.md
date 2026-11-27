# 版本支持矩阵

本仓库同时服务三套互不兼容的 Logisim 几何。**混用必然出错**，先按版本归类再动手。

## 一、先看版本

```bash
head -3 xxx.circ | grep -o 'source="[^"]*"'
```

| `source=` 开头 | 版本 | 用哪套 |
|---|---|---|
| `5.0` | Logisim-evolution 5.0 | **5.0** 几何（默认） |
| `4.1` | Logisim-evolution 4.1 | **4.1** 几何（子电路固定 220 宽；`circ41_*` 真机探针） |
| `4.0` | Logisim-evolution 4.0 | **5.0** 几何（子电路动态宽度；`circ40_*` 真机探针） |
| `3.9` | Logisim 3.9 | **3.9** 几何（`circ39_*` 无头探针，见下表与第七节） |
| `2.16` | Logisim-ITA 2.16.1.0 | **2.7.1** 几何 |
| `2.7` | 经典 Logisim 2.7.1 | **2.7.1** 几何 |

代码里也可以直接路由：

```python
from circuit_kit.versions import get, detect
geo = get("5.0")        # -> geometry
geo = get("2.16")       # -> circ271
ver = detect("xxx.circ")  # -> '5.0' / '2.16' / '2.7.1'
```

## 二、几何差异（抄错就是「修好一处坏一处」）

| 项 | 3.9 | 5.0 | 2.7.1 / 2.16 |
|---|---|---|---|---|
| 引脚方向写法 | `type="input"/"output"` | `type="input"/"output"` | `output="true"` |
| 门 `size` / 宽度 | 50（NAND/OR 60、XOR 60、XNOR 70、NOT 30） | 同左 | 30 |
| 门输入口 | `x-50`（XOR `x-60`、XNOR `x-70`、NOT `x-30`） | 同左 | **`x-30, y±step*(n-1)/2`**，2 输入 `y±10` |
| 分线器位口 | `(20, -40…-10)`（fanout=4） | 同左 | **`b_i=(x+20, y+10*(i-fanout+1))`**；**b0 是低位组** |
| 译码器 | 同 5.0 | `sel=(x,y)`、`en=(x-10,y)`、`out_i=(x+20,y-10*(cnt-i))` | 同左 |
| 子电路外观端口 | 同 5.0 | 按 facing 分边 | **`loc+(x+(w-1)//2-2, y+h//2-3)`**；矩形须比端口**内缩 10px**，否则端口被丢弃 |
| 时序验证 | `-w <电路> <向量> <circ>` | 同左 | **无 `-w`**，用 `scripts/ita_probe.py` |

> **3.9 与 5.0 实测一致**（2026-11-18，用外观桥对 AND/OR/XOR/NOT/Pin/Tunnel/Splitter/Register/
> Counter/D Flip-Flop/Constant/Clock 逐项比对端口坐标，全部相同；`-n` / `-t tty --save` 也在）。
> 早前此表把 3.9 写成「门 size=40、输入口 x-20」，实为 2.7.1 的数值，已作废。
> `source="5.0.0"` 的 `.circ` 可被 3.9 直接打开、无版本告警。
>
> **4.1 的差异只在子电路符号**：门 / 触发器 / 分线器 / 寄存器 / RAM / ROM 端口与 5.0 相同；
> 子电路实例固定 220 宽、端口 20px 间距、锚点在东边第一个输出口（详见
> `skills/logisim-circuit-design/references/logisim41.md`）。
>
> **多输入门纵向排布（3.9 / 4.1 / 5.0 实测一致）**：2 输入 `y±20`；3 输入 `y-20 / y / y+20`；
> n≥4 用 10px 间距、偶数输入跳过 0（4 输入 `y-20/-10/+10/+20`，6 输入 `y±10/±20/±30`）。

## 三、工具归属

### MCP 服务器（`server/server.py`，27 个工具）

| 前缀 | 版本 | 工具 |
|---|---|---|
| `circuit_*` | 5.0（老接口） | `truth_table` `test_vector` `verify` `stats` `summary` `build` `open_gui` |
| `circ_*` | 5.0 | `geometry` `probe` `audit` `build` `sim` `appearance` `kb` |
| `circ271_*` | **2.7.1 / 2.16** | `ports` `check` `sim` |
| `circ39_*` | **3.9** | `check` `save` `run` `debug` |
| `circ40_*` | **4.0** | `check` `ports` `save` |
| `circ41_*` | **4.1** | `check` `ports` |

### 库层（`server/circuit_kit/`）

| 模块 | 归属 | 说明 |
|---|---|---|
| `geometry.py` | **5.0** | 端口偏移 / 包围盒，数据可由 `knowledge.json` 覆盖 |
| `circ271.py` | **2.7.1 / 2.16** | 网表检查 / 网表仿真 / 端口几何（独立实现，与上者不共用） |
| `versions/__init__.py` | 路由 | `get(版本)` → 对应几何模块；`detect(.circ)` |
| `netlist.py` `router.py` `builder.py` `audit.py` `appearance.py` `knowledge.py` `logisim_bridge.py` | 通用 | 按 **5.0** 语义实现；2.7.1 场景请走 `circ271.py` |

### Skill 脚本（`skills/logisim-circuit-design/scripts/`）

| 目录 / 文件 | 归属 | 用途 |
|---|---|---|
| `v50/lib8.py` | 5.0 | 8 位总线生成库（Board / 门 / DFF / 分线器 / 子电路） |
| `v50/route8.py` | 5.0 | 确定性布线 + 六项自检 + 展平 |
| `v50/sim.py` | 5.0 | `-w` 向量封装（`<set> <seq>` 时序） |
| `v50/verify.py` | 5.0 | `-t table/stats` + 向量封装 |
| `v50/router.py` `v50/logisim_gen.py` | 5.0 | 通道布线 / XML 生成（4 位规模） |
| `v271/circ271.py` | 2.7.1 | 2.7.1 语义层（同 `server/circuit_kit/circ271.py`） |
| `v271/ita_probe.py` | 2.7.1 | headless 探针封装（`list/eval/vector/ends/errors`） |
| `v271/netcheck.py` | 2.7.1 | 按真实端口坐标建网 → 位宽冲突定位 |
| `v271/netmap.py` | 2.7.1 / 2.16 | **端口级网表**：谁连到谁；`--overlap` 查共线短接；`--grid` 查斜线/非 10 倍长度（会导致加载 OOM） |
| `v271/sevenseg.py` | 2.7.1 / 2.16 | 数码管：`check` 段位与 `active` 极性、`table` 0~F 真值表、`demo` 生成 A~F 演示电路 |
| `v271/segshot.py` | 2.7.1 / 2.16 | 从截图按像素识别数码管亮了哪几段（PIL） |
| `v271/attrprobe.py` | 2.7.1 / 2.16 | 触发一次「改属性」验证 `WireRepair` 不死循环（「改文字就卡死」自检，L13） |
| `v271/ita/ITAProbe.java` | 2.7.1 | Java 探针源码（自动编译） |
| `common/gui.py` | 通用 | GUI 自动化：找窗口 / 点击 / 滚轮缩放 / 截图（按键会被别的窗口抢焦点，别用来输入文字，见 L9） |

## 四、怎么选

1. **看 `.circ` 的 `source`** —— 这决定几何，不看你手头装的是哪个 Logisim。
2. **5.0** → MCP 的 `circ_*` / `circuit_*`，skill 的 `scripts/v50/`。
3. **2.16 / 2.7.1** → MCP 的 `circ271_*`，skill 的 `scripts/v271/`；
   时序电路必须用 `ita_probe.py`（`-tty table` 只能跑组合）。
4. **3.9** → 几何与 5.0 实测一致，`versions.get("3.9")` 直接路由到 5.0 实现；
   向量 CLI 与 5.0 相同：`-w <电路> <向量> <circ>`（两个版本实测都接受）。
5. **4.1** → 门/触发器/分线器/寄存器同 5.0；只有**子电路符号**是 220 宽 / 20px 间距，
   生成时用 `LOGISIM_PROFILE=4.1`，真机校验用 `circ41_check` / `circ41_ports`。
6. **4.0** → 几何与 5.0 完全一致；只有文件格式不同（`source=4.0.0`、库索引
   Wiring0/Gates1/Memory2/I/O3/Base4、toolbar 的 `<tool>` 必须带 `lib` 属性）。
   生成时用 `LOGISIM_PROFILE=4.0`，真机校验用 `circ40_check` / `circ40_ports`，
   老文件转存用 `circ40_save`。

## 五、2.16 实测补充（本文档新增）

- 外观矩形 100×70、端口落在左边界 → **4 个端口全部消失**（`getEnds()` 返回空，且不报错）。
- 端口连接点偏移实测：`width=32,height=8` → `(+13,+1)`；`width=1` → `(-2,+1)`；`width=5,height=10` → `(0,+2)`。
- **端口落在别的导线上一定会连**（T 接）；主干通道必须避开所有端口 x/y。
- **7-Segment Display（IO 库）8 个输入脚**：`a=(+20,0) b=(+30,0) c=(+20,+60) d=(+10,+60)`
  `e=(0,+60) f=(+10,0) g=(0,0) dp=(+30,+60)`，外框 `Bounds(-5,0,40,60)`；
  `SEGMENTS[]` 顺序 a,b,c,d,e,f,g，值 bit0~bit6，bit7=dp（取自 `SevenSegment.class`）。
- **`active` 是布尔属性**（`Attributes.forBoolean`）：只能写 `true` / `false`；
  写 `high` / `low` 会被解析成 `false` → 数码管整块反相，且 `ERRCOUNT` 仍为 0。
- **没有 `<appear>` 的子电路**：实例端口在左右两边按 **10px 打包**，顺序 = 内部 Pin 按 y 排序，
  与内部 Pin 坐标（可能是 20px 步长）无关，**不能用平移公式推算**。
- **导线必须横平竖直、长度为 10 的倍数**：斜线或非 10 倍长度的线会让 `WireRepair.doOverlaps`
  死循环，2.16 加载直接 `OutOfMemoryError`（GUI 里只是「卡一下」）。用
  `scripts/v271/netmap.py --grid` 先扫一遍。
- 新增工具（2.16/2.7.1 通用）：`scripts/v271/netmap.py`（端口级网表 / `--overlap` 短接 /
  `--grid` 网格）、`sevenseg.py`（数码管 `check` / `table` / `demo`）、
  `segshot.py`（截图像素识别数码管亮段）。

## 六、2.15 实测补充（实验1 新增）

- **三极管是单向开关**：`in=(x-40,y)`、`out=(x,y)`、`gate=(x-20,y-20)`，值只从 in→out；
  CMOS 下拉网络必须 **GND 接 in**（否则 Q 永远拉不到 0），上拉同理 VCC 接 in（K53）。
- **两个晶体管的输出侧不要同 x / 同 y 相接**：会被并成一整条，一个驱动源是 `Z`、另一个是有效值，
  整网变 `U`——每个驱动源给独立通道（K54）。
- **8 位分线器位口**：南向 `x+80-10i`、北向 `x-10-10i`（均 `y±20`）；**≤4 位才是 `x+10-10i`**（K55）。
- **Adder / Subtractor**：A=(x-40,y-10)、B=(x-40,y+10)、S=(x,y)、Cin=(x-20,y-20)，
  **Cout 也是输入脚**；求和可用，进位别指望（K56）。
- **Multiplier / Divider**：A/B 同上、Out=(x,y)，另有 **width 位宽**的附加输入 (x-20,y-20)
  （C / Upper）与附加输出 (x-20,y+20)；附加输入悬空 → 输出 `U`，接 Constant 0（K56）。
- **Counter(width=4, max=0x9)** 实测 0→9→0 **向上**计数（K57）。
- **向量引脚名用 ASCII**：`.vec` 是 UTF-8，Java 按 GBK 读，中文名会被截断（K58）。
- **自定义外观锚点**：`circ-anchor` 存 6×6 框**左上角**，Logisim 以中心为原点 →
  端口 = `loc + (端口中心 − (anchor+3))`；差 3px 整块端口悬空（K59）。
- 新增工具：`scripts/v215/gen_lab1.py` —— 实验1 十个电路（时钟LED / CMOS 三极管门 / 8 位分离器 /
  运算器+封装 / 计数器 / 扩展器 / 两个逻辑练习 / 3-8 译码器），零隧道，几何全部实测。

---

## 七、3.9 内核探针（circ39_*，2026-11-18 沉淀）

3.9 几何与 5.0 实测一致（见上表），但格式迁移与布线陷阱有独立坑（pitfalls L14 + M 组）。
新增 `server/java/src/g39probe/` 12 个 Java 探针（首次调用自动 javac）+ `circuit_kit/g39probe.py` 封装：

| 工具 | 作用 |
|---|---|
| `circ39_check` | 3.9 内核真实加载体检（报错与 GUI 同款） |
| `circ39_save` | 3.9 内核重存（5.0 → 原生 3.9 格式，原子覆盖可选） |
| `circ39_run` | 脚本化多拍时序：`pin=val` / `t` / `r`，watch 坐标 |
| `circ39_debug` | wires / onet / multi / nets / insts / ends / bounds / pins / vals / **overlap** |

jar 定位：`LOGISIM39_JAR` → `logisim.local.json` 的 `logisim39_jar` → 常见安装位置。
`overlap` 为纯 XML 扫描（真短路 / 冗余重叠分类）；`multi` 已把 Splitter/Tunnel 端按 io 计。
关键实测：Register 端口 D=+30、en=+50、clk=+70；WireRepair 会裁穿体线、合并共线重叠、拆 T 结点。

## 八、3.9 存储器实验（3.2）实测补充

- **大端**：32→4 分线器 bit24-31→bank0 … bit0-7→bank3，字读拼回才是 `12345678`。
- **字节写**：每个 bank 的 D 恒取自己那一路字节，用 `A[1:0]` 经 2→4 译码分别选通写使能；
  不能"先按 A[1:0] 选字节再送所有 bank"。
- **字节读**：Bit Extender 用 `sign`（手册要 `00000012` / `FFFFFFEE`）。
- **Except** = `(MemRead ∨ MemWrite) ∧ ¬MCntrl ∧ (A[1] ∨ A[0])`；只拨地址不报，读写才报。
- **写使能** = `MemWrite ∧ ¬MemRead ∧ ¬Except`（两个控制信号同时为 1 时不写，防误触）。
- **输出寄存器** 只读锁存 `en = MemRead ∧ ¬Except`，写操作不刷新数码管。
- 多比特引脚一律 `radix="16"`（地址/数据），否则二进制输入与手册对不上。
- 生成器：`scripts/v39/gen32.py`（5 电路：main / RAMModule / rom64k / bank8 / rom_test）。
- 工具：`scripts/v39/restore_block.py`（把某电路块从一个 3.9 文件拼回另一个）。
- 已知未解：把 ROM 经 SEL+32 位 Mux 并入 `main` 后写使能网变 E（见 pitfalls M13）。

## 九、2.15 I/O 库（实验7）实测补充

- **TTY**：D(0,-10)、CLK(0,0)、WR(10,10)、RST(20,10)；`Char bit width` 只接受 7/16（写 8 直接 LOADERR）。
- **Keyboard**：CLK(0,0)、RST(10,10)、RD(20,10)、AVL(130,10)、DATA(140,10)。
- **7-Segment Display**：a(+20,0) b(+30,0) c(+20,60) d(+10,60) e(0,60) f(+10,0) g(0,0) dp(+30,60)；`active=true`。
- **Button/LED** 端口都在 (0,0)；**DotMatrix** 列口 (10i,0)，16×16 行模式是 16 个 16 位口。
- **无头读 TTY**：Clock 换 `CLK` Pin 打拍，反射 `TtyState.getRowString`；`Simulator.tick()` 不产生状态。
- **门遇 U 输出 E**（非 U）：TTY 写使能用 `T3 ? WM : 0` 的 MUX，别用 AND。
- **新增/改名引脚必须引线再挂同名 Tunnel**，只写 label 不会并网。
- 工具：`scripts/v215/geo_probe.py`、`tty_read.py`、`patch_clock.py`；
  生成/拆分：`gen_lab7_io.py`、`gen_lab7_tty.py`、`split_cpu_1/2/3_*.py`。

## 十、3.9 单周期 MIPS CPU（2026-11 实测补充）

| 对象 | 端口/宽度 | 备注 |
|---|---|---|
| Pin 输出 | `<a name="output" val="true"/>` | 写 `type="output"` 会被当输入 |
| 自定义外观 | `<circ-anchor facing="east" x="0" y="0"/>` | 缺省锚点右中，端口整体偏 |
| 实例端口 | `loc + circ-port(x,y)` | 与 5.0 一致 |
| Register(32) | D(0,30) en(0,50) clk(0,70) clr(30,90) Q(60,30) | body 60x90 |
| MUX 2:1 | in0(x-30,y-10) in1(x-30,y+10) sel(x-20,y+20) | sel=0 选 in0 |
| MUX 8:1 | 输入 (x-40,y-40..30) sel(x-20,y+40) | — |
| MUX 32:1 | 输入 (x-40,y-160..150) sel(x-20,y+160) | 可做 32 寄存器堆 |
| Decoder(n) | out_i (x+20,-10*(2^n-i)) sel(0,0) en(-10,0) | `disabled=0` |
| Adders | A(x-40,y-10) B(x-40,y+10) S(x,y) Cin(x-20,y-20) | Cout 是输入脚，别接 |
| RAM(14x32) | A(0,10) WE(0,50) EN(0,60) CLK(0,70) D(0,90) Q(240,90) | EN 悬空 Q=U |
| ROM(14x32) | A(0,10) Q(240,60) | contents 不能为空 |

整机语义：stp 要 `cpu_clk=clk&~stopped` 且 `PC.en=run&~(stopped|Stp)`；
周期计数用 16 位寄存器 +4 位十六进制显示；RAM 初值不随 `.circ` 保存。
详见 `skills/logisim-circuit-design/references/logisim39-cpu-casebook.md`。
