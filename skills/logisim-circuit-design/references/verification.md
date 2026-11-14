# 验证与运行环境

## 1. 命令行（最可靠，优先用这个）

```bash
JAR=D:/app/logisim-evolution-5.0.0-all.jar

java -jar $JAR -t table  X.circ                    # 真值表（主电路）
java -jar $JAR -t stats  X.circ                    # 元件统计
java -jar $JAR -w main vec.txt X.circ              # 测试向量
```

- `-t table` 会把所有输入引脚的组合枚举一遍（≤8 个输入时最实用），表头带位宽：`a[4]`。
- `-w` 的输出：末行 `通过：7，失败：0`；失败时逐条列出 `s = 0 (expected 1)`。中文在 Windows 上是 GBK 编码，管道里看到乱码就转码。
- `-w` 每一行都从初始状态重新求值，触发器状态传不到下一行——只能验组合逻辑。
  时序电路（计数器/状态机）见第 6 节。另：列名和引脚对不上时 Logisim 会静默跳过，输出里根本没有 `expected` 行，
  容易被误读成"0 失配"。
- 不要给 `-w` 加 `-Djava.awt.headless=true`：内部会 `new Frame`，headless 直接抛 `HeadlessException`。
- `-n`（格式转换）会弹 Swing 对话框，命令行下必崩，别用。

`scripts/verify.py` 已经把上述封装好（自动找 jar、GBK 解码、解析结果）：

```bash
python scripts/verify.py table  fa.circ
python scripts/verify.py stats  demo.circ
python scripts/verify.py vector main bcd4.vec demo_test.circ
```

## 2. 向量文件 `.vec` 格式

```
a3[4] a2[4] a1[4] a0[4] b3[4] b2[4] b1[4] b0[4] cin sum3[4] sum2[4] sum1[4] sum0[4] cout_o
0x1   0x2   0x3   0x4   0x5   0x6   0x7   0x8   0    0x6   0x9   0x1   0x2   0
0x9   0x9   0x9   0x9   0x0   0x0   0x0   0x1   0    0x0   0x0   0x0   0x0   1
```

- 首行表头，格式 `名字[位宽]`，1 位可省略 `[1]`。
- 值：十进制或 `0x..` 十六进制；多位引脚必须写全值。
- 每行一个用例。输出引脚也必须出现在表头并给出期望值，否则不算验证。
- 表头名字必须与电路里引脚的 `label` 完全一致（区分大小写）。

## 3. 测试用例怎么设计

以一个 4 位 BCD 加法器为例，7 条就够覆盖所有边界（判题通常也是这么造的）：

| # | 输入 | 目的 |
|---|---|---|
| 1 | 1234 + 5678 | 常规无进位 |
| 2 | 9999 + 0001 | 全链进位到最高位 |
| 3 | 0 + 0 + cin=1 | 单个进位输入贯通 4 位 |
| 4 | 9999 + 9999 | 每位都产生进位 + 溢出 |
| 5 | 1239 + 1239 | 个位进位后 9+9 |
| 6 | 1999 + 2999 + cin=1 | 进位链与 cin 叠加 |
| 7 | 0 + 0 | 全零 |

原则：常规值 1 条 + 每个边界单独 1 条；边界包括 0、最大值、进位传播最长路径、cin=1、溢出。

## 4. 双工程策略（强烈建议）

| 文件 | 用途 | 内容 |
|---|---|---|
| `demo.circ` | 交作业/展示 | 数码管显示结果，好看 |
| `demo_test.circ` | 验证 | 同一套布线，数码管换成输出引脚 |

两者由同一个生成函数产出（只切换 `probe=True`），保证「好看的那份」和「通过验证的那份」电气完全一致。只验证一份、交另一份，是翻车高发点。

另外给每个测试用例单独做一个「常量写死」的电路（`case1_xxx.circ`）：输入引脚全换成 `Constant`，打开即显示结果，答辩时不用手点引脚。做法是从主工程复制一份，把 `<comp ... name="Pin">` 的输入行替换成 `Constant` 行。

## 5. GUI 运行与截图

> 硬规矩：视觉检查只认 Logisim 本体截图。 自己写的渲染器（PIL/SVG 画线）只能验证
> "你以为的坐标"，画不出元件真实外形、引脚朝向、总线宽度、`E`/`U` 的红色高亮、
> 组件重叠提示。用渲染图定位问题会得出错误结论——要么按它改坏电路，要么改渲染器空转。

- 启动：`D:/logisim-evolution.exe <文件.circ>`（jpackage 启动器），或 `java -jar <jar> <文件.circ>`。
- 坑：从工具里启动 GUI，命令一结束进程就被回收，窗口一闪而过。必须用「后台常驻」方式启动（如 `run_in_background`），否则会被误判为「Logisim 崩溃」。
- 标题栏出现「未保存」通常是因为文件在打开后被外部改写，不是用户改的。处理：关掉重开（不要点保存，否则用旧内存覆盖新文件）。
- 截图：
  - `PrintWindow` 抓不到菜单弹窗和缩放按钮的即时变化；
  - 稳妥做法是 `PIL.ImageGrab.grab()` 全屏截，再按窗口坐标裁剪；
  - 截图前先把窗口调到需要的大小，缩放设固定倍数。

封装好的工具：`scripts/gui.py`（ctypes + PIL，沙箱内验证可用；PowerShell 的
Add-Type/COM 路径会被拒）。完整流程一条龙：

```python
import gui
gui.open_circ(r"D:/作业/2.3.circ")         # 后台启动并载入（jar 自动探测）
h, title = gui.wait_window("Logisim", 25)  # 轮询等窗口（约 8~15 秒）
gui.wheel(h, 6, ctrl=True, dy=-120)        # Ctrl+滚轮缩小看全图；Shift 横滚
im = gui.shot("_out.png", h)               # 按窗口矩形截图
gui.key(0x4B, ctrl=True)                   # Ctrl+K 启动时钟模拟
gui.close(h)                               # WM_CLOSE（外部改过文件时别点保存）
```

要点：截图矩形来自 GetWindowRect（物理像素），点击/滚轮的 SetCursorPos 在 DPI 缩放下
需按实测比例换算；`Ctrl+滚轮` = 缩放、`Shift+滚轮` = 横向滚动。

## 6. 时序电路的验证（`-w` 加 `<set> <seq>` 即适用）

`-w` 不加特殊列时每行重置，多拍行为验不了；表头加 `<set>` `<seq>` 两列后就是真正的
时序测试（写法见 `SKILL.md` 第 6 节、H5/G5）。不依赖该特性的两条交叉复核（早期验证过）：

1. 多拍网表仿真：解析 `.circ` 建网表，逐拍给 `cp` 一个完整脉冲；
   每拍内逐个触发器比较各自 `CLK` 的前后值，只有 0→1 才采样 `D`，否则行波级联会算错。
   插件里是 `circ_sim`，用法 `{"file":..., "inputs":{...}, "cycles":N, "watch":[...]}`。
2. 组合镜像：把触发器换成输入引脚（`Q_i` / `~Q_i`），保留次态组合逻辑，
   做成纯组合电路用 `-t table` 让 Logisim 自己跑。验的是 Logisim 的真实语义。

另外，测试模式下触发器初值可能是 `U`，而 `U` 沿 `Q→D` 自环会自锁——同步清零压不住 `U`。
仿真内核要把初值置 0；真机用 `Ctrl+R`（电路复位）。

## 6.1 MCP 工具（插件版）

装了 `logisim-mcp` 插件时可直接调用：

| 工具 | 作用 |
|---|---|
| `logisim_info` | jar / Java / 无头能力 |
| `circuit_summary` / `circuit_stats` | 电路结构、元件统计 |
| `circuit_truth_table` | 真值表（组合；>16 输入会拒绝） |
| `circuit_verify` / `circuit_test_vector` | 向量比对（后者仅组合） |
| `circuit_build` | 旧版生成器（隧道版），兼容用 |
| `circuit_open_gui` | 打开 GUI |
| `circ_geometry` | 端口偏移 / 包围盒（活数据） |
| `circ_build` | 声明式 DSL → 多电路，A* 布线，不用隧道 |
| `circ_audit` | 静态体检：悬空 / 多驱动 / 孤立 / 重叠 |
| `circ_sim` | 多拍网表仿真，逐触发器检测时钟沿 |
| `circ_kb` | 经验库：list / search / add |

没有桥接时，直接用命令行 + Python 生成，效果一样——不要为了「用上 MCP」而绕路。

## 6.2 存储器验证（3.2 实测）

存储器是「组合读 + 时序写」的混合体，按层验证最快：

| 层 | 验什么 | 3.2 结果 |
|---|---|---|
| `bank8` | 单 bank 的 WE/CLK 写时序、地址保持 | 7/7 |
| 数据通路 | `DIN[32]` → 4×8 拆分 → 4 个 2:1 mux | 3/3 |
| 控制逻辑 | 2:4 译码 + `~BYTE` + OR/AND 的 `WE_i` | 9/9 |
| `ram64k` | 字写读、字节写读、相邻字节保护 | 16/16 |
| `main` | ROM/RAM 选择、SEL 隔离 | 37/37 |

要点：

- `<set>/<seq>` 的状态保留**能穿过子电路实例**：`bank8` 在父电路里仍能跨行写读；
  不是“只有顶层 RAM 才能测”。
- 同一 `<set>`、递增 `<seq>`；CLK 用 0→1 两行制造上升沿；写行期望值用 `<DC>`。
- 必须断言「通过数 == 数据行数」；列名不匹配时 Logisim 静默跳过，看起来全过。
- RAM 的字节写测试要覆盖：写 byte0 后 byte1..3 不变；四个 lane 各写一次再读整字。
- `-t stats` 前先删同目录 `.circ.autosave`，否则会出现「`-w` 能跑、`stats` 报加载失败」。
- `circ_audit` 对 RAM/ROM/Bit Extender 只给 `partial`，`dangling` 不可全信；
  以 `-w` 功能向量 + 生成器几何自检为准。
- 顶层截图用 GUI + 窗口截图；`circ_appearance preview` 截的是外观视图，`main` 会显示空框。

## 6.3 Logisim 2.7.1 验证（无 `-w`，靠网表 + 引擎）

2.7.1 没有 5.0 的原生测试向量，`-t` 能力也有限。按四层验证：

| 层 | 工具 | 说明 |
|---|---|---|
| 1. 静态 | `circ271_check {"file","circuit"}` | 0 error 才继续；`unknown_components` 只说明覆盖范围 |
| 2. 网表功能 | `circ271_sim {"file","circuit","inputs","cycles","watch"}` | 原始元件电路（DM/GRF/Controller）；输出引脚和 Tunnel 都能看 |
| 3. 引擎模块 | Java `DmTest`（2.7.1 jar） | 真实语义，覆盖 `str/cs/oe/clk/clr` 等细节 |
| 4. 引擎整机 | Java `CpuSim`（2.7.1 jar） | 驱动 reset/时钟，逐拍读 `pc/Instr/WA/WD/RegWrite/MemWrite` |

要点：

- 2.7.1 的时钟是普通 Pin `clk`（或 Clock 组件）；`circ271_sim` 自动找 `clk/clock/cp/ck`。
- 写操作要在上升沿发生：`cycles` 每拍是一个完整 0→1→0 脉冲。
- 观察多位信号用 Tunnel label（如 `bank`、`ReadData`），比在画布上找线可靠。
- 整机含子电路/Adder 时 `circ271_sim` 会列 `unknown_components`，此时必须用引擎级仿真。
- `Pin.setValue` 后必须 `markComponentAsDirty` + `propagate`，否则值不会进入电路（J7）。

## 7. 交付检查清单

- [ ] `circ_audit` 对纯门/触发器电路 `verdict` 是 `ok`；含 RAM/ROM/Bit Extender 时允许 `partial`，以 `-w` 为准
- [ ] 组合部分：真值表无 `E`、无 `U`
- [ ] 时序部分：多拍仿真跑满整个状态序列 + 溢出/回绕后的若干拍
- [ ] 存储器：`-t stats` 退出码 0；`-w` 通过数 == 数据行数
- [ ] 存储器：字节写只改选中 bank，相邻 3 字节保持原值
- [ ] 用了 mux/decoder 时工程头含 `<lib desc="#Plexers" name="5"/>`
- [ ] 每层子电路单独跑过真值表
- [ ] 顶层无隧道（`grep -c "<comp.*Tunnel"` 为 0）
- [ ] 3.9 文件自带 toolbar；5.0 可省
- [ ] 无 `.autosave` 残留
- [ ] 顶层缩放到 ×1 能一屏看全；子电路展开不需要缩到 0.5 以下
- [ ] 模块图 + 展开图各一张截图
- [ ] 用例电路双击即显示结果
