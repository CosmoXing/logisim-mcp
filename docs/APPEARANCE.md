# 子电路外观编辑（circ_appearance）

在 Logisim 自己的 JVM 里修改 `CircuitAppearance`，界面实时刷新；Python 侧负责 spec、自动排版与校验。

## 前置条件

- Logisim-evolution 5.0（3.9 没有 `CircuitAppearance` / `AppearancePort`）。
- JDK 21+（编译 Java 桥）：

```bash
python tools/build_bridge.py
```

产物：`runtime/bridge/logisim-bridge.jar`。只运行不修改时，分发预编译 jar 即可，不需要 JDK。

## MCP 用法

```json
{"action":"get",    "file":"D:/work/2.3.circ", "circuit":"mul"}
{"action":"auto",   "file":"D:/work/2.3.circ", "circuit":"mul"}
{"action":"preview","file":"D:/work/2.3.circ", "circuit":"mul", "out":"D:/work/mul.png"}
{"action":"save",   "file":"D:/work/2.3.circ", "circuit":"mul"}
{"action":"close",  "file":"D:/work/2.3.circ"}
```

- `auto` 默认 `layout.preserve_port_positions=true`：只重画框体、名称牌、标签，端口坐标保持原样，父电路导线不会脱开。
- 想要「左入右出、均匀排布」的整洁符号，传：

```json
{"action":"auto", "file":"...", "circuit":"mul",
 "layout":{"preserve_port_positions": false}}
```

  返回里的 `impact` 会给出受影响的父电路与导线数（移动端口会让这些导线端点脱开，需要重新布线）。
- `apply` 接收完整 spec；`preview` 会切到 Appearance 视图并截图；`save` 先备份 `.bak-时间戳`，保存后校验 `appearance=custom`、`circ-port` 数 == Pin 数，并用 `java -jar … -t stats` 确认 Logisim 能重新加载。

## spec

```json
{
  "circuit": "mul",
  "layout": {
    "preserve_port_positions": true,
    "width": 120, "height": 140, "corner_radius": 10,
    "anchor": {"x": 0, "y": 0, "facing": "east"},
    "box": {"stroke": "#000000", "fill": "none", "stroke_width": 2},
    "nameplate": {"enabled": true, "height": 20, "fill": "#000000",
                  "text_color": "#FFFFFF", "text": "mul", "font_size": 12, "bold": true},
    "port_labels": {"enabled": true, "offset": 8, "font_size": 11,
                    "show_width": true, "template": "{label}[{width}]"}
  },
  "ports": [
    {"pin": "mult_op1", "pin_at": "80,200", "side": "left", "x": 0, "y": 20, "dir": "in", "width": 8}
  ],
  "texts": [],
  "shapes": []
}
```

- 坐标是相对 `circ-anchor` 的外观坐标，必须是 10 的倍数。
- `pin` 是原理图 Pin 的标签；同名 Pin 需要用 `pin_at`（Pin 的 `loc`，形如 `"80,200"`）消歧。
- 每个 Pin 必须恰好有一个 `circ-port`，否则 `E_MISSING_PORT`。

## 校验与错误

- `E_PORT_OFF_EDGE`：端口不在框边（保端口模式会自动放宽）。
- `E_PORT_IN_NAMEPLATE`：端口落进名称牌。
- `E_PORT_OVERLAP` / `E_GRID` / `E_BAD_BOX`。
- `E_NO_PIN` / `E_AMBIGUOUS_PIN`：标签匹配失败或重名。
- `E_EDT_TIMEOUT`：Logisim 界面被模态框挡住或响应超时。

## 已知限制

- 第一版只编辑外观，不放置元件/连线。
- 保存通过 `LogisimFile.write` 完成；Logisim 会顺手规范化导线分段与默认属性，因此不要拿保存前后的原始 XML 做 diff，电气一致性以 Logisim 重新加载与 `circ_audit` 为准。
- 移动端口会改变父电路实例的端口位置；`impact` 只是端点计数，不会自动重布线。
