# 版本支持矩阵

本仓库同时服务三套互不兼容的 Logisim 几何。**混用必然出错**，先按版本归类再动手。

## 一、先看版本

```bash
head -3 xxx.circ | grep -o 'source="[^"]*"'
```

| `source=` 开头 | 版本 | 用哪套 |
|---|---|---|
| `5.0` | Logisim-evolution 5.0 | **5.0** 几何（默认） |
| `2.16` | Logisim-ITA 2.16.1.0 | **2.7.1** 几何 |
| `2.7` | 经典 Logisim 2.7.1 | **2.7.1** 几何 |
| `3.9` | Logisim 3.9 | **3.9** 几何（未落地为代码，见下表） |

代码里也可以直接路由：

```python
from circuit_kit.versions import get, detect
geo = get("5.0")        # -> geometry
geo = get("2.16")       # -> circ271
ver = detect("xxx.circ")  # -> '5.0' / '2.16' / '2.7.1'
```

## 二、几何差异（抄错就是「修好一处坏一处」）

| 项 | 3.9 | 5.0 | 2.7.1 / 2.16 |
|---|---|---|---|
| 引脚方向写法 | `<a name="output" val="true"/>` | `type="input"/"output"` | `output="true"` |
| 门 `size` / 宽度 | 40 | 50（NAND/OR 60、XOR 60、XNOR 70、NOT 30） | 30 |
| 门输入口 | `x-20` | `x-50`（XOR `x-60`、XNOR `x-70`、NOT `x-30`） | **`x-30, y±step*(n-1)/2`**，2 输入 `y±10` |
| 分线器位口 | `x-20` 起 10px | 按 `facing` 分边 | **`b_i=(x+20, y+10*(i-fanout+1))`**；**b0 是低位组** |
| 译码器 | — | `sel=(x,y)`、`en=(x-10,y)`、`out_i=(x+20,y-10*(cnt-i))` | 同左 |
| 子电路外观端口 | `loc.x-30` 起 10px | 按 facing 分边 | **`loc+(x+(w-1)//2-2, y+h//2-3)`**；矩形须比端口**内缩 10px**，否则端口被丢弃 |
| 时序验证 | 无 CLI | `-w` 向量引擎 | **无 `-w`**，用 `scripts/ita_probe.py` |

## 三、工具归属

### MCP 服务器（`server/server.py`，16 个工具）

| 前缀 | 版本 | 工具 |
|---|---|---|
| `circuit_*` | 5.0（老接口） | `truth_table` `test_vector` `verify` `stats` `summary` `build` `open_gui` |
| `circ_*` | 5.0 | `geometry` `probe` `audit` `build` `sim` `appearance` `kb` |
| `circ271_*` | **2.7.1 / 2.16** | `ports` `check` `sim` |

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
4. **3.9** → 几何表见上，代码尚未落地；临时用 5.0 逻辑但把门输入口改回 `x-20`。

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
