# 实验3 8位 ALU（带比较器，Logisim-ITA 2.15.0.2）实战复盘

一次完整交付：在实验2 加法器工程上补齐 8 位 ALU（移位 / 比较 / 算术 / 逻辑），
最终 8 个电路、16604 行向量 0 失败，顶层压缩到 **1460×1030**，文件可直接被 2.15.0.2 加载。

## 1. 交付结构

```
ALU 8位（带比较器）                  ← main
├─ 8位可控加减器
│  ├─ 4位全加器 ×2                  ← 复用实验2
│  ├─ 8 × (B ⊕ Sub)
│  ├─ Cin ⊕ Sub
│  └─ OF = ~(A7⊕Bx7) & (A7⊕S7)
├─ 移位器
│  ├─ Shifter(ll/lr/ar) ×3
│  ├─ 4:1 选择（MOF B / SHL / SHR / SAR）
│  └─ SOL：左 8:1 + 右 8:1 + 2:1(S1) + AND(S1|S0)
├─ 逻辑运算器
│  └─ 8 位 AND / OR / NOT / XOR + 4:1
└─ 比较器
   └─ Comparator(8) + 1→8 扩展器 + 4:1
```

顶层 2×2 摆放四个模块，模块间 60~70px；控制字组合器、B_eff、结果/CF/ZF 选择都在模块左侧/右侧就近布置。

## 2. 功能语义与假设

| S3S2 | 操作 | 选择 | 结果 / 标志 |
|---|---|---|---|
| 00 | 移位 | S1S0=00 MOF B；01 SHL/SAL；10 SHR；11 SAR | S=Y，CF=SOL；ZF/OF/SF 无效 |
| 01 | 比较 | 00 A>B；01 A=B；10 A<B | S=0x01/0x00（1→8 扩展）；CF=A<B；ZF=A=B；SF/OF 无效 |
| 10 | 算术 | 1000 A+B；1001 A+B+1；1010 A+1；1011 A-1 | OF/SF/CF/ZF 有效 |
| 11 | 逻辑 | 1100 AND；1101 OR；1110 ~A；1111 XOR | ZF 有效；SF/OF/CF 无效 |

**移位**：数据 = B，次数 = A[2:0]；N=0 时传送 B，CF=0。左移移出位 `X[8-N]`，
右移/算术右移移出位 `X[N-1]`；算术右移补符号位。

**算术**：`B' = B_eff ⊕ Sub`，`Cin' = Cin ⊕ Sub`。
`S1=1`（1010/1011）时 `B_eff=0`，于是
INC（Cin=1, Sub=0）= `A+1`，NEC（Cin=1, Sub=1）= `A+0xFF+0 = A-1`。
OF 用 `(A7==Bx7) & (A7!=S7)`，等价 `C7⊕C8`；CF=Cout；SF=S7；ZF=(S==0)。

**比较**：`CF = (A<B)`、`ZF = (A=B)`，与当前选中的是 >/=/< 无关；
结果位按 PDF 比较器图经 4:1 后由 1→8 扩展器补零，所以是 0x01/0x00，不是“只出标志、S 恒 0”。

## 3. 2.15.0.2 实测几何（本次新增）

| 元件 | 端口（相对 loc） |
|---|---|
| Multiplexer 2:1 | 数据 `(x-30,y-10)/(x-30,y+10)`；sel `(x-20,y+20)`；out `(x,y)` |
| Multiplexer 4:1 | 数据 `(x-40,y-20+10i)` i=0..3；sel `(x-20,y+20)`；out `(x,y)` |
| Multiplexer 8:1 | 数据 `(x-40,y-40+10i)` i=0..7；sel `(x-20,y+40)`；out `(x,y)` |
| Comparator(8) | A `(x-40,y-10)`、B `(x-40,y+10)`；gt `(x,y-10)`、eq `(x,y)`、lt `(x,y+10)` |
| Bit Extender | in `(x-40,y)`、out `(x,y)` |
| Constant | out `(x,y)` |
| Shifter(8) | data `(x-40,y-10)`、distance `(x-40,y+10)` 3 位、out `(x,y)` |
| Splitter 南向 | bus `(x,y)`；bit i `(x+off-10i, y+20)`，`off=(ceil(bits/2)-1)*10`，b0 最右 |
| Splitter 北向 | bus `(x,y)`；bit i `(x+off-10i, y-20)`，位序同南向 |

要点：

- **MUX 必须显式 `enable=false`**。默认 true 会多一个使能脚，悬空时输出 `U/E`。
- 8:1 MUX 的数据口只有 10px 间距，`fan_stub` 要把每个隧道先横走 `20+20i` 再竖走
  `20(i+1)`，否则隧道标签互相压住。
- Shifter 的距离口宽度 = `ceil(log2(width))`，8 位数据固定 3 位。
- 分线器位口 b0 在**最右**（南/北向时的 x 最大），不是最左；这与 5.0 的 east 分线不同。

## 4. 工具链

| 工具 | 用途 |
|---|---|
| `scripts/v215/board215.py` | 2.15 几何 + Board；本次新增 `mux/cmp/const/ext/shifter/split` 与 `fan_bits/fan_stub` |
| `scripts/v215/gen_alu_lab3.py` | 生成 5 个新电路（含紧凑坐标），六项自检不过不落盘 |
| `scripts/v215/calib_lab3.py` | 用实验2 工程头生成临时标定电路，`ita_probe.ends` 读 MUX/Comparator/Extender/Shifter/Splitter 真实端口 |
| `scripts/v215/verify_alu_lab3.py` | 模块级 + ALU 顶层向量，16604 行 |
| `scripts/v215/probe_points.py` | 按坐标读运行值 / `--dump`，排查中间网络（注意第 6 节 K15） |
| `scripts/v215/test_wide.py` | 最小复现：宽 Pin、分线器、隧道驱动关系 |
| `scripts/v271/ita/ITAProbe.java` | 本次新增 `ProbeLoader`，打印 `LOADERR` 而不是 HeadlessException |

```bash
cd 待修/全套210                 # 脚本默认读当前目录的实验2/3 文件
python <skill>/scripts/v215/gen_alu_lab3.py
python <skill>/scripts/v215/verify_alu_lab3.py
```

也可以显式指定：`gen_alu_lab3.py --src 实验2 构建加法器.circ --out 实验3 ALU设计.circ`；
验证脚本用环境变量 `LAB3_CIRC` 指向目标 `.circ`。

## 5. 验证矩阵

| 电路 | 行数 | 结果 |
|---|---|---|
| 8位可控加减器 | 3436 | 0 失败 |
| 移位器 | 1984 | 0 失败 |
| 逻辑运算器 | 1936 | 0 失败 |
| 比较器 | 1452 | 0 失败 |
| ALU-移位 | 704 | 0 失败 |
| ALU-比较 | 1452 | 0 失败 |
| ALU-算术（ADD/ADC/SUB/SBB/INC/NEC） | 3704 | 0 失败 |
| ALU-逻辑 | 1936 | 0 失败 |
| **合计** | **16604** | **0 失败** |

判定：每个电路单独 `ERRCOUNT 0`，顶层向量 `pass == rows`，文件能被 2.15 加载。

## 6. 本次踩到的坑（对应 pitfalls K12–K19）

### K12 Tunnel 的 facing 必须写全称
`east/west/north/south`；写 `e/w` 会报
`attribute value (e) is not valid for facing [Tunnel(...)]`，该隧道不参与连网，
后续还可能触发 `WireRepair` 死循环，探针 300s 超时。
所有 side 短码必须在生成器里映射成完整单词后再写 XML。

### K13 分线器位口悬空会反推总线
分线器不是纯扇出：位口悬空时它会从位侧向总线反推 0/U，和输入 Pin 抢驱动。
只拆低 3 位时，其余 5 位必须接假负载（如 5 输入 OR，输出不接），
或者干脆不要用分线器，直接给总线打隧道分支。

### K14 无头加载会吞真实错误
`Loader.showError` 在 headless 下弹 `JOptionPane` → `HeadlessException`。
探针里用 `ProbeLoader extends Loader` 覆写 `showError`，把真实原因打成 `LOADERR ...`。
“能打开但结果怪 / 超时”先看 LOADERR，不要先怀疑布线。

### K15 --probe / --dump 在 Pin/Tunnel 上可能读到旧值
`CircuitState.getValue(loc)` 在输入 Pin、Tunnel 端口上不一定是网络真值；
本次 A/B 输入 Pin 处 dump 恒 0，导致误判为总线断线。
判断功能用 `--vector` 比输出引脚，或对子电路单独 `--set` 验证。

### K16 内置 Shifter 有可变距离口，但不输出移出位
`shift=ll/lr/ar/rl/rr`，8 位数据对应 3 位距离。移位器模块用 3 个 Shifter + 4:1；
SOL 要另算：左移 `X[8-N]`、右移 `X[N-1]`，N=0 为 0，用两个 8:1 + 2:1(S1) + AND(S1|S0)。

### K17 MUX 忘记 enable=false
2.15 Multiplexer 默认有使能脚；不显式关掉时，悬空的 en 会让输出 `U/E`。
关掉后的端口见第 3 节。

### K18 比较结果不是“只出标志”
按 PDF 比较器图，>`、`=`、`<` 经 4:1 后还要过 1→8 扩展器，所以 ALU 的 S=0x01/0x00；
CF=A<B、ZF=A=B。把 S 固定 0 会漏掉实验要求的“输出比较结果”。

### K19 INC/NEC 要先把 B 置 0
算术 1010/1011 不是 `A+B`：`zero_b = S3 & ~S2 & S1`，把 B_eff 置 0，
再走 `B'=B_eff⊕Sub`、`Cin'=Cin⊕Sub`。否则 INC 会变成 A+B、NEC 会变成 A-B。
OF 仍用 `(A7==Bx7)&(A7!=S7)`，CF=Cout。

## 7. 排查决策树

```
打不开 / 卡死
 ├─ 先看 LOADERR（ProbeLoader）
 ├─ Tunnel facing 是否全称？
 ├─ MUX/其他实例属性是否完整（enable=false、width、select）？
 └─ lib 编号是否照抄原文件？

输出 U / E
 ├─ 先跑模块级向量，定位是子电路还是顶层
 ├─ 分线器位口是否全部接负载？
 ├─ MUX enable 是否悬空？
 ├─ 1 位/多位是否接到同一端口？
 └─ 是否用 --probe 在 Pin/Tunnel 上误读？

算术错、逻辑对
 ├─ B_eff / Sub / Cin 映射
 ├─ INC/NEC 是否 B_eff=0
 └─ OF 公式是否用 A7/Bx7/S7

比较错
 ├─ S 是否 0x01/0x00
 ├─ CF 是否 A<B
 └─ ZF 是否 A=B

布局太散
 └─ 模块 2×2、60~70px 间距；控制/输出就近；隧道扇出错开
```

## 8. 布局压缩记录

| 电路 | 初版 | 紧凑版 |
|---|---|---|
| 8位可控加减器 | 2280×2200 | 1500×1300 |
| 移位器 | 2000×1580 | 1380×1030 |
| 逻辑运算器 | 1480×920 | 1080×670 |
| 比较器 | 1480×820 | 1080×720 |
| ALU 顶层 | 2480×1780 | **1460×1030** |

手段：门列 70px 间距、4位全加器上下 330px、模块 2×2 只留 60~70px 缝、
S32/S10/N3 组合器下移贴近模块、输出引脚从 x=2000 收到 x=1580。
压缩后重新跑全量向量，16604 行仍全过。

## 9. 可复用结论

1. 先做**模块级向量**，再做顶层；错误定位成本差一个数量级。
2. 2.15 的 Tunnel 很好用，但 facing 必须全称、每个标签位宽一致。
3. 分线器要么全接、要么别用；悬空位会反推总线。
4. MUX 一律显式 `enable=false`，端口按第 3 节算。
5. 移位器优先用内置 Shifter 的可变距离口；SOL 单独算。
6. 比较器结果是 8 位 0/1，不是只出标志。
7. 布局压缩后必须重跑向量，不能只看自检。
