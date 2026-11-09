---
name: logisim-circuit-design
description: 用代码生成、检查和验证 Logisim-evolution (.circ) 数字电路。适用于门级作业（计数器、分频器、寄存器、加法器、译码器、状态机）、分层子电路设计、「只许门电路和触发器、不许用现成芯片/隧道」这类限制，以及 .circ 打不开、显示 E、位宽冲突、模块引脚接不上的排障。内含 13 进制计数器完整复盘（13 个坑 + 排查决策树）与 5.0 端口坐标表。关键词：logisim、logisim-evolution、.circ、数字电路、电路作业、计数器、模13、触发器、时序电路、真值表、测试向量、子电路、分线器、数码管、netlist。
---

# Logisim 电路设计

两条路，都验证过：

| 路径 | 适合 | 入口 |
|---|---|---|
| **A. MCP 工具（推荐）** | 要交付、要可验证、连线复杂 | `circ_build` / `circ_audit` / `circ_sim` / `circuit_truth_table` |
| **B. 手写脚本** | 环境里没有 MCP、或只想微调一个文件 | `scripts/logisim_gen.py` + `scripts/router.py` + `scripts/verify.py` |

两条路的几何常量、布线规则、踩坑记录是同一套。**先读第 1 节的版本前提**，这是最容易翻车的地方。

## 0. 何时用

- 用户要求用 Logisim 做数字电路（作业、课设、演示），尤其带「只许门电路/触发器」「不许用隧道」「不许用内置计数器」这类限制。
- 已有 `.circ` 打不开、导线显示 `E`、橙色报「位宽不兼容」、子电路引脚接不上、数码管不亮。
- 需要批量生成用例电路、跑真值表、验证一个自己写出来的时序电路。

不适用：模拟电路（SPICE）、Verilog/VHDL 综合。

## 1. 版本前提（先确认，再动手）

```bash
head -3 xxx.circ | grep source        # <project source="5.0.0">
logisim_info                          # MCP：报 jar/Java/无头能力
python server/server.py --doctor      # 插件：报依赖与自检
```

| 项 | 3.9 | 5.0（本 skill 默认） |
|---|---|---|
| 引脚写法 | `<a name="output" val="true"/>` | `<a name="type" val="input"/>` / `val="output"` |
| 门 `size` | 40 | 50 |
| AND/OR 输入口 | `loc.x-20` | **`loc.x-50`** |
| NAND/NOR/XOR 输入口 | `loc.x-20` | **`loc.x-60`** |
| XNOR 输入口 | `loc.x-20` | **`loc.x-70`** |
| NOT 输入口 | `loc.x-20` | **`loc.x-30`**（特例，宽度 30） |
| 子电路端口 | `loc.x-30` 起、10px | 按 facing 分边，锚点落在东边第一个口 |

抄错这 30px 的症状是「每修好一处、另一处又坏」，几乎一定被误判成"布线算法有问题"。
不确定就查 `references/geometry.md`，或用 `circ_geometry` 拿活数据。

## 2. 七条铁律（违反必炸）

| # | 铁律 | 后果 |
|---|---|---|
| 1 | 导线终点必须**精确落在端口像素**上 | 差 10px 就断线，且没有任何报错 |
| 2 | 子电路只做 **≤3 入 / ≤2 出** | 引脚一多，端口被压进 50px，几乎布不通 |
| 3 | **所有元件端口**都是禁入点，不只是子电路 | 竖线穿过触发器 `Q(0,0)` 与 `~Q(0,20)` → 两输出短接，整列 `E` |
| 4 | 位宽严格匹配（数码管数据口恒 4 位） | 橙色「位宽不兼容」，整条网络 `E` |
| 5 | 同网共线相接会**合并**，合并后端点变内点 | 分支静默失效（"看着接上了其实断了"） |
| 6 | 同网"内点×内点"十字交叉**不导通** | 要连接就从交点引一段短线 |
| 7 | 生成的 `.circ` 自带 `<toolbar>`（3.9 需要；5.0 可省） | 用户打开后没有绘图工具条，以为软件坏了 |

## 3. 坐标速查（5.0）

| 对象 | 坐标 |
|---|---|
| AND / OR | `loc` 是**输出**口；输入口 `(loc.x-50, loc.y∓20)` |
| NAND / NOR / XOR | `(loc.x-60, loc.y∓20)` |
| XNOR | `(loc.x-70, loc.y∓20)` |
| NOT | `(loc.x-30, loc.y)` —— **特例，宽度 30** |
| 3 输入以上 | 从 `loc.y-10(n-1)` 起，每 20px 一个 |
| D / T 触发器（classic） | `D(-40,+20) CLK(-40,0) Q(0,0) ~Q(0,+20) R(-10,+30) S(-30,+30)` |
| 子电路实例 | 东口 `(X, Y+10j)`；西口 `(X-30, Y+Δ+10i)`；锚点落在东边第一个口 |
| 分线器·拆位 | 合并侧 `loc`；分线侧 `(loc.x+20, loc.y-20+10i)`，**`b0` 在最上** |
| 分线器·合并 | `loc` 出 4 位；位序 `o = b3 b2 b1 b0`，**最上面的口是最低位** |
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

- 引用只有两种：`pin:<标签>`、`<元件id>.<端口名>`；子电路用**它自己的引脚标签**当端口名。
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

布线交给 `scripts/router.py`（通道布线，避开共线重叠与端点压线）。**有失败就 `raise`，绝不写出文件**——
断头导线轻则整列 `E`，重则加载时 `WireRepair` 卡死。

```bash
python scripts/verify.py table  fa.circ                 # 真值表
python scripts/verify.py stats  demo.circ               # 元件统计
python scripts/verify.py vector main bcd4.vec demo_test.circ
```

## 6. 验证：先把"验什么"分清

### 组合逻辑

`verify.py table` 或 `circuit_truth_table`。`0/1` 正常，`U` = 无驱动（悬空），`E` = 冲突/短路，两个都不能有。

### 时序逻辑（计数器、状态机）

⚠️ **`-w`（`verify.py vector` / `circuit_test_vector`）每一行都从初始状态重新求值**，
触发器状态传不到下一行。两级 D 触发器链的 `q1` 永远为 0——所以它**只能验组合逻辑**。

两条正确做法：

1. **多拍网表仿真**（`circ_sim`）：逐拍给 `cp` 一个完整脉冲；每拍内**逐个触发器**比较各自 `CLK` 的前后值，
   只有 0→1 才采样 `D`（否则行波级联会算错）。
2. **组合镜像交叉复核**：把触发器换成输入引脚（`Q_i` / `~Q_i`），保留次态组合逻辑，
   做成纯组合电路，用 Logisim 真值表跑 32 行。验的是 Logisim 的真实语义。

两者都过才算过。**报告"0 失配"前先确认向量真的执行了**——列名对不上时 Logisim 静默跳过，输出里没有 `expected` 行。

### 双工程策略

`demo.circ`（数码管展示）与 `demo_test.circ`（数码管换输出引脚）由**同一个生成函数**产出，
只切换一个开关，保证"好看的那份"和"通过验证的那份"电气一致。

## 7. 常见症状 → 修法

| 症状 | 根因 | 修法 |
|---|---|---|
| 输出全 `U` | 端口没接上 / 网络被漏掉 | 按 5.0 公式算；确认总线网真的生成了 |
| **某一位 `E`，其余正常** | 竖线穿过触发器 `Q` 与 `~Q` | 端口列为禁入点 |
| **分支"看着接上了"却没电** | 同网共线合并，端点变内点 | 错开 10px 走 T 型搭接 |
| 输出 `E` +「位宽不兼容」 | 1 位接 4 位数码管 | 分线器补零凑 4 位 |
| **时序"0 失配"但电路是错的** | `-w` 每行重置 / 列名对不上被跳过 | 改多拍仿真 + 组合镜像 |
| **触发器永远 `U`，清不掉** | `U` 沿 `Q→D` 自锁 | 仿真初值置 0；真机 `Ctrl+R` |
| 打开报「加载电路文件出错」 | 目录有 `.circ.autosave` | 删掉再开 |
| 没有绘图工具条 | 3.9 文件缺 `<toolbar>` | 补 `lib="8"` 的 toolbar 块（5.0 可省） |
| 电路贴左上角、引脚被面板挡 | 从 `(0,0)` 起画 | 整体 `translate(+120,+60)` |
| 数码管不亮 | 组件名写成 `HexDigit` | 正确名 `Hex Digit Display`，lib `5` |

## 8. 完整案例：两位十三进制计数器

`references/counter13-casebook.md` 是一次真实交付的复盘：模 13 的次态公式、两位级联与溢出停止，
以及排障中踩到的 **13 个坑**（门端口差 30px、Q/~Q 被竖线短接、共线合并把端点变内点、`-w` 假通过、
触发器 `U` 自锁、子电路端口公式、仿真器统一采样、三元表达式漏网……），
每条都是「现象 → 根因 → 解决 → 怎么验证」，文末有排查决策树。

做计数器、分频器、状态机这类时序电路时**先读它**，能省掉一整轮试错。

## 9. 三条不要做

- 不要用隧道（Tunnel）省事——多数作业明令禁止，且截图看不出真实结构。
- 不要为省元件把多个功能塞进 5 入以上模块——端口会挤爆，且出错无提示。
- 不要只在顶层验证：分层电路必须**每层都验**，否则错误定位成本高 10 倍。

## 10. 资源

| 文件 | 内容 |
|---|---|
| `references/counter13-casebook.md` | **13 进制计数器实战复盘**：13 个坑 + 验证矩阵 + 排查决策树 |
| `references/geometry.md` | 端口/尺寸常量（含 3.9 vs 5.0 对照）、布线语义、布局与压缩 |
| `references/dsl.md` | `circ_build` 的 DSL 完整参考：字段、端口名、自动布局、报错含义 |
| `references/circ-format.md` | `.circ` XML 结构、库索引、组件属性、toolbar、版本差异 |
| `references/verification.md` | CLI 参数、`.vec` 格式、用例设计、双工程策略、GUI 截图 |
| `references/pitfalls.md` | 35 条实战坑：症状 / 根因 / 定位 / 解决 |
| `scripts/logisim_gen.py` | XML 生成器：pin / gate / sub / splitter / display / wire / project |
| `scripts/router.py` | 通道布线器：正交、避让、禁止共线重叠 |
| `scripts/verify.py` | `-t table` / `-t stats` / `-w` 的封装（自动找 jar、GBK 解码） |
| `assets/full-adder.circ` | 已知可用（真值表 8/8）的最小参考工程，5.0 格式 |
