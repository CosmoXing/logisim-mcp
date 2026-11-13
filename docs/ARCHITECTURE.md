# 架构

## 一句话

MCP 客户端通过 stdio 发 JSON-RPC，服务端把请求翻译成"读 XML / 写 XML / 调用 java"三类动作；
中间夹一层自己实现的网表模型，负责生成、体检、仿真。

## 分层

```
server.py                 14 个工具的定义与分发；jar/java 探测；调用 Logisim CLI
  └── circuit_kit/
        geometry.py       元件端口偏移与包围盒（生成侧唯一数据源）
        router.py         10px 网格 A* 布线 + 元件发射 + 线段合并 + .circ 输出
        netlist.py        .circ 解析 → 网表 → 多拍仿真（解析侧独立几何实现）
        builder.py        声明式 DSL → 多电路工程（布局、位宽校验、子电路）
        audit.py          静态连接体检（悬空 / 多驱动 / 孤立 / 重叠）
        knowledge.py      经验库读写（原子写 + 结构自愈）
        appearance.py     子电路外观 spec / 自动排版 / XML 兜底 / 连通性校验
        logisim_bridge.py Java 桥会话管理（启动、复用、NDJSON 请求）
  └── java/               logisim.bridge：在 Logisim JVM 内操作 CircuitAppearance
```

## 数据流

### 生成

```
spec(JSON) ──builder──▶ 元件布局 ──router──▶ 线段集合 ──▶ .circ
                              │
                              └─ 位宽校验 / 组合环检测 / 端口存在性校验
```

布线器把这三类东西当作禁入区：元件包围盒、所有元件端口、已有线段。
最后一条包含两个特例：异网不允许共线重叠（会短路），同网共线允许但会在输出前合并。

### 读取与验证

```
.circ ──netlist.parse──▶ 电路对象 ──Sim──▶ 网表（DSU 合并线段）──▶ 逐拍求值
```

`Sim` 的求值关键点：

1. 连通性：只有"端点落在别人身上"才算连接；纯内点交叉不连通；同网共线先合并再判。
2. 位宽：网络是多位时按元组存值，分线器负责拆/合。
3. 时钟：`Clock` 组件或名为 `cp/clk/clock/ck` 的根层引脚；每拍给一个完整脉冲。
4. 触发器：一拍内循环，逐个比较各自 `CLK` 的前后值，只有 0→1 才采样 `D`，然后重新收敛。
   这样同步与行波级联都对。
5. 冲突：同一网络被两个源写入 → `E`；只被读没有源 → `U`。

## 为什么两套几何

`geometry.py` 和 `netlist.py` 各自实现了一遍端口公式，这是故意的：

- 生成侧算错 → 线接不到端口 → 回读时该网络上只有孤立的端口 → 体检报悬空；
- 解析侧算错 → 生成的文件被误读成"多驱动/悬空" → 仿真结果与 Logisim 对不上。

两边同时错成一样的概率很低。这套交叉校验在开发中抓出过 `NAND` 反相圈少算 10px、
`NOT` 不符合加宽规律、子电路锚点位置等一批错误。

## 为什么不用隧道

隧道（Tunnel）能大幅简化布线，但：

- 多数课程作业明令禁止；
- 截图看不出真实连接，审阅者无法判断；
- 一旦标签写错，网络静默断开，且体检也难定位。

所以 `circ_build` 走真实导线；旧版 `circuit_build`（隧道版）只为兼容保留。

## 为什么失败要显性

早期版本遇到不认识的元件会返回空端口表，于是该元件"从网表里消失"，仿真照常给出一个看起来合理的结果——
这是最危险的一类 bug。现在 `netlist.py` 会抛 `UnsupportedComponent`，体检返回 `verdict=unsupported`，
`circ_build` 遇到位宽不符直接拒绝并列出明细。

同一原则体现在：

- `-w` 列名对不上时 Logisim 会静默跳过 → `circ_sim` 不依赖它，且文档反复标注；
- 布线失败 → 抛错，绝不写出半成品文件；
- 知识库 JSON 损坏 → 备份为 `.corrupt` 后重建，不吞异常。

## 关键常量从哪来

| 常量 | 来源 |
|---|---|
| 门宽度 `50/60/60/70/30` | v5.0.0 `AbstractGate` 的 `size + bonus + negatedOutput*10`，NOT 走 `NotGate` 自己的画法 |
| 触发器端口 | `AbstractFlipFlop` 的 classic 外观 `Port(...)` 构造 |
| 分线器 | `Splitter` 的端口布局，`b0` 在最上 |
| 子电路端口 | `DefaultClassicAppearance` 的 placePins：按 facing 分边、10px 间距、锚点落在东边第一个口 |

每一条都用真值表或最小电路实测复核过，记录在 `skills/.../references/geometry.md`。
