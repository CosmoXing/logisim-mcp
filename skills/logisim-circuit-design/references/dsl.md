# `circ_build` 规格（DSL）参考

`circ_build` 接收一份 JSON，生成一个多电路 `.circ` 工程。你写网表，不写坐标；`at` 全可省略。

```json
{
  "file": "D:/work/demo.circ",
  "circuits": [ { "name": "main", "pins": [...], "components": [...], "nets": [...] } ]
}
```

顶层字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `file` | 是 | 输出 `.circ` 的绝对路径（目录必须存在） |
| `circuits` | 是 | 电路数组；没有名为 `main` 的会自动把第一个改名成 `main` |

## 电路对象

| 字段 | 说明 |
|---|---|
| `name` | 电路名。子电路通过这个名字被引用 |
| `pins` | 对外引脚 |
| `components` | 元件实例 |
| `nets` | 网络（把若干端口连在一起） |

## pins

```json
{"label": "Q", "dir": "out", "width": 4, "at": [1400, 300]}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `label` | 必填 | 引脚名，必须唯一；顶层引脚名就是 MCP 仿真时的信号名 |
| `dir` | `"in"` | `in` / `out`（也接受 `input` / `output`） |
| `width` | `1` | 位宽。4 位引脚要接分线器才能进 1 位门 |
| `at` | 自动 | `[x, y]`。省略时输入排在左列 `x=120`、输出排在最右列 |

## components

```json
{"id": "f0", "type": "DFF", "at": [500, 300]}
{"id": "g1", "type": "NAND", "inputs": 3}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `id` | `c0`、`c1`… | 网络里引用的名字，必须唯一 |
| `type` | 必填 | 见下表 |
| `at` | 自动 | `[x, y]` 元件 loc。省略时按依赖深度分列 |
| `inputs` | 2（NOT 为 1） | 只对门有效，2~8 |

支持的 `type`：

| type | 说明 | 端口 |
|---|---|---|
| `AND` `OR` `NAND` `NOR` `XOR` `XNOR` `NOT` | 门 | `a` `b` `c`… 输入，`out` 输出 |
| `DFF` | D 触发器（上升沿） | `D` `CLK` 输入，`Q` `NQ` 输出，`R` `S` 悬空可用 |
| `TFF` | T 触发器（上升沿，T=1 翻转） | `T` `CLK` 输入，`Q` `NQ` 输出 |
| `SPLITTER4` | 4 位分线器 | `in` 是 4 位总线，`b0`~`b3` 是单线（`b0` 最低位） |
| `CLOCK` | 时钟源 | `p` 输出 |
| `LED` | 指示灯 | `p` 输入 |
| `DISPLAY` | 4 位十六进制数码管 | `p` 输入（4 位） |
| 任意已定义电路名 | 子电路实例（大小写不敏感） | 用它自己的引脚 `label` 当端口名 |

## nets

```json
{"name": "q0", "connect": ["f0.Q", "x0.a", "a1.b", "sp.b0"]}
{"name": "bus", "connect": ["sp.in", "pin:Q"]}
```

- 引用只有两种：`pin:<标签>` 与 `<元件id>.<端口名>`。
- 每个网络 ≥2 个连接点，否则报错。
- 同一网络位宽必须一致：`4 位引脚 + 1 位门输入` 会被拒绝并列出明细。
- 网络名只用于报错定位，不影响生成结果。

## 自动布局规则

省略 `at` 时：

1. 时钟放最左列（x=200）；
2. 门与触发器按依赖深度分列：`x = 340 + 200*depth`（从引脚直接驱动的深度为 0）；
3. LED / 数码管放最右列；
4. 同列内按 `y = 160 + 110*序号` 排，撞坐标自动下移 40；
5. 输出引脚统一放到所有元件右侧 `x = 340 + 200*(maxDepth+2)`。

组合环（`_depth_of` 检测到回环）会直接报 `组合环：<id>`——时序反馈请走触发器，不要用门自环。

## 报错信息含义

| 报错 | 含义 / 处理 |
|---|---|
| `未定义的元件 x（引用 x.y）` | `components` 里没有这个 `id`，或子电路名拼错 |
| `元件 x(AND) 没有端口 z，可用 [...]` | 端口名写错，看提示里的可用列表 |
| `引脚 a 未定义` | `pin:a` 里的 `a` 不在 `pins` 里 |
| `网络 n 少于两个连接点` | 单端点网络无意义，删掉或补连接 |
| `网络 n 位宽不一致：pin:d=4位、g1.a=1位` | 4 位信号必须经 `SPLITTER4` 拆开 |
| `组合环：g1` | 门的输出又喂回自己的输入链，改用触发器 |
| `布线失败：网络 n 从 ... 到 ... 无解` | 该网络被已放置的元件挡住，给相关元件加 `at` 挪开，或调换端口顺序 |

## 完整示例 1：两位行波计数器（自包含，可 audit 通过）

```json
{
  "file": "D:/work/ripple2.circ",
  "circuits": [{
    "name": "main",
    "pins": [{"label": "cp", "dir": "in"},
             {"label": "q0", "dir": "out"},
             {"label": "q1", "dir": "out"}],
    "components": [
      {"id": "f0", "type": "DFF"},
      {"id": "f1", "type": "DFF"}
    ],
    "nets": [
      {"name": "cp", "connect": ["pin:cp", "f0.CLK"]},
      {"name": "n0", "connect": ["f0.NQ", "f0.D"]},
      {"name": "q0", "connect": ["f0.Q", "pin:q0", "f1.CLK"]},
      {"name": "n1", "connect": ["f1.NQ", "f1.D"]},
      {"name": "q1", "connect": ["f1.Q", "pin:q1"]}
    ]
  }]
}
```

跑 `circ_sim {"file": ..., "cycles": 4}`，`q1q0` 应当是 `01 → 10 → 11 → 00`。
注意这里第二级用 `Q0` 当时钟（行波）——同步设计应当共用 `cp`、用使能控制，行波只适合演示。

## 完整示例 2：子电路 + 分线器（全加器）

```json
{
  "file": "D:/work/adder.circ",
  "circuits": [
    {
      "name": "main",
      "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
               {"label": "cin", "dir": "in"},
               {"label": "s", "dir": "out"}, {"label": "cout", "dir": "out"}],
      "components": [{"id": "u1", "type": "fa"}],
      "nets": [
        {"name": "a",   "connect": ["pin:a", "u1.a"]},
        {"name": "b",   "connect": ["pin:b", "u1.b"]},
        {"name": "cin", "connect": ["pin:cin", "u1.ci"]},
        {"name": "s",   "connect": ["u1.s", "pin:s"]},
        {"name": "co",  "connect": ["u1.co", "pin:cout"]}
      ]
    },
    {
      "name": "fa",
      "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
               {"label": "ci", "dir": "in"},
               {"label": "s", "dir": "out"}, {"label": "co", "dir": "out"}],
      "components": [
        {"id": "x1", "type": "XOR"},
        {"id": "x2", "type": "XOR"},
        {"id": "a1", "type": "AND"},
        {"id": "a2", "type": "AND"},
        {"id": "o1", "type": "OR"}
      ],
      "nets": [
        {"name": "a",    "connect": ["pin:a", "x1.a", "a2.a"]},
        {"name": "b",    "connect": ["pin:b", "x1.b", "a1.a"]},
        {"name": "ci",   "connect": ["pin:ci", "x2.b", "a2.b"]},
        {"name": "sum1", "connect": ["x1.out", "x2.a", "a1.b"]},
        {"name": "s",    "connect": ["x2.out", "pin:s"]},
        {"name": "p1",   "connect": ["a1.out", "o1.a"]},
        {"name": "p2",   "connect": ["a2.out", "o1.b"]},
        {"name": "co",   "connect": ["o1.out", "pin:co"]}
      ]
    }
  ]
}
```

注意 `fa` 是 3 入 2 出——刚好在可布线范围内。再多一个引脚，实例端口就会挤到 10px 间距。

## 常见组合模式

| 需求 | 写法 |
|---|---|
| 4 位结果送数码管 | `{"name":"bus","connect":["sp.in","pin:Q","disp.p"]}`（`disp` 是 `DISPLAY`，位宽 4） |
| 时钟接多个触发器 | 同一个网络里列全：`["clk.p","f0.CLK","f1.CLK"]` |
| 取反 | 直接用 `f0.NQ`，或 `NAND` 两输入短接（`NOT` 端口是特例，少用） |
| 级联进位 | 低位的 `CARR` 输出接高位的 `EN` 输入，不要拿它当时钟 |
