# 示例电路

四个可以直接用 Logisim 打开的小电路，用来确认安装成功、也当作 DSL 的活样例。

| 文件 | 内容 | 看点 |
|---|---|---|
| `and2.circ` | 2 输入与门 | 最小冒烟：生成的坐标、引脚朝向、连线是否正常 |
| `half_adder.circ` | 半加器 + 十六进制数码管 | XOR/AND 组合、分线器合并、用 `GROUND` 补齐未用位 |
| `ripple2.circ` | 两位行波计数器 | 两个 D 触发器，`~Q` 接回 `D`，`Q0` 当时钟驱动第二级 |
| `counter13.circ` | 两位 13 进制计数器（README 首页那张图） | 三层结构、不用隧道、到 `CC` 停住并点亮 LED；26 个门与触发器全部由 DSL 生成 |

`counter13.circ` 的验证方式和别的不一样——它有时序，`-w` 验不了：

```bash
python server/server.py --doctor                 # 先确认 jar 找到了
# 用 MCP 工具跑 172 拍，看两位数字是不是 00 → CC 后停住
```

## 怎么用

看：用 Logisim 打开任意 `.circ`，按 `Ctrl+R` 复位，点引脚或启用时钟仿真。

重新生成：

```bash
python examples/generate.py           # 重新生成并体检
python examples/generate.py --check   # 只体检
```

生成脚本用的是插件自己的 `circ_build` 能力（`builder` + `audit` + `netlist`），
每个示例生成后都会自动跑一次体检，并打印末态：

```
and2.circ          体检=ok  末态 a=(0,), b=(0,), y=(0,)
half_adder.circ    体检=ok  末态 a=(0,), b=(0,), s=(0,), disp:d1=0000
ripple2.circ       体检=ok  末态 cp=(0,), q0=(0,), q1=(0,)
```

## 对应的 spec

`half_adder.circ` 的 spec 长这样（详见 `skills/logisim-circuit-design/references/dsl.md`）：

```json
{
  "name": "main",
  "pins": [{"label": "a", "dir": "in"}, {"label": "b", "dir": "in"},
           {"label": "s", "dir": "out"}],
  "components": [
    {"id": "x1", "type": "XOR"},
    {"id": "a1", "type": "AND"},
    {"id": "sp", "type": "SPLITTER4"},
    {"id": "d1", "type": "DISPLAY"},
    {"id": "g2", "type": "GROUND"},
    {"id": "g3", "type": "GROUND"}
  ],
  "nets": [
    {"name": "a", "connect": ["pin:a", "x1.a", "a1.a"]},
    {"name": "b", "connect": ["pin:b", "x1.b", "a1.b"]},
    {"name": "sum", "connect": ["x1.out", "pin:s", "sp.b0"]},
    {"name": "carry", "connect": ["a1.out", "sp.b1"]},
    {"name": "lo2", "connect": ["g2.p", "sp.b2"]},
    {"name": "lo3", "connect": ["g3.p", "sp.b3"]},
    {"name": "bus", "connect": ["sp.in", "d1.p"]}
  ]
}
```

注意 `GROUND`：数码管数据口固定 4 位，只用了 `b0/b1` 时要把 `b2/b3` 拉低，
否则未连接的高位会显示成 `U`，屏上是乱码。
