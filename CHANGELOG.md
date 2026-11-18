# 更新记录

## 未发布 — 3.9 内核无头探针工具族（circ39_*）沉淀

- 新增 MCP 工具四件（`server/server.py` + `server/circuit_kit/g39probe.py` +
  `server/java/src/g39probe/` 12 个 Java 探针，首次调用自动 javac，jar 按
  `LOGISIM39_JAR` → `logisim.local.json` 的 `logisim39_jar` → 常见安装位置定位）：
  - `circ39_check`：3.9 内核真实加载体检（报错与 GUI 弹窗同款 + 电路清单）；
  - `circ39_save`：3.9 内核重存（5.0 存盘 → 原生 3.9 格式，out 留空原子覆盖）；
  - `circ39_run`：脚本化多拍时序功能测试（`pin=val` / `t` 打拍 / `r` 读输出，
    watch 坐标逐点观察，比 `-w` 向量强：能验时序）；
  - `circ39_debug`：布线级调试工具箱 wires/onet/multi/nets/insts/ends/bounds/pins/vals/overlap。
    其中 `overlap` 为纯 XML 共线重叠扫描（真短路=加载时被合并导致跨网短路；冗余重叠=共享端点前缀，无害）。
- 探针修出的两个真实缺陷（3.1 重设计版寄存器堆）：
  1. 旁路区重复造 r0 比较器链 → nz 网双驱动（multi 抓到，G39NetList 已把 Splitter/Tunnel 按 io 计排除误报）；
  2. ridx2 合并线与 bank1 ridx1 支线共线重叠 40px → 加载合并后 ridx2 干线断供、
     读口恒 0、bank1 ridx1 被错接（overlap + G39Wires diff 抓到；此前的"写读成功"全是
     wdata 泄漏进读通路的假象）。修复生成器 `tools/gen_rf31_v3.py` 走线后 **32 地址全量
     写读回归 32/32**（两读口独立 + r0 恒 0 + 同拍旁路 + wen 门控全过）。
- 固化 M1~M10（pitfalls）：分线器 incoming=总线位宽、Register D=+30/en=+50/clk=+70、
  共线重叠分类、元件体压线、通道端点 T 短路、Splitter 无源直通、G39Seq 语义四坑
  （markDirty / clk 引脚手动打拍 / U 非 0 / 子电路根不可靠）、XML 导线≠加载后导线、
  迁移收尾六步、GUI 配套（radix / clk 手点 / 画布出界平移）。
- 文档：`references/logisim39-casebook.md` 新增；pitfalls 新增 M 组（102 → 112 条）；
  SKILL.md 的路径表 / 工具表 / description 同步；`docs/VERSIONS.md` 补 3.9 探针；
  README 工具表补 circ39_*；knowledge.json 追加 `g39-*` 条目。

## 未发布 — 实验1 熟悉 Logisim 的基本使用（2.15.0.2）沉淀

- 新增 `scripts/v215/gen_lab1.py`：一次生成实验1 的 10 个电路（时钟LED / CMOS 三极管门 /
  8 位分离器 / 运算器 + 封装 / 计数器 / 扩展器 / 两个逻辑练习 / 3-8 译码器），零隧道；
  内置 2.15 实测几何（三极管、8 位分线器、算术器件、外观锚点），生成阶段跑穿体/共线重叠自检。
- 验收：39 项向量全过（含封装电路 SEL=0..3 → 9/3/0x12/2）、10 电路 `ERRCOUNT 0`、
  `attrprobe` 改属性自检全部 `ATTR_OK`。
- 固化 K53~K60：三极管单向（GND 接 in）、两驱动源别同 x 相接、8 位分线器位口、
  Adder 的 Cout 是输入脚、Mul/Div 附加输入接 0、Counter(max) 向上计数、
  向量引脚名用 ASCII、外观锚点 +3、Text 文本转义。
- 文档：pitfalls 新增 K53~K60；SKILL 的 2.15 表 / 脚本目录 / 资源表同步；
  `docs/VERSIONS.md` 新增「六、2.15 补充（实验1）」；README 补 2.15 说明；
  `knowledge.json` 追加 8 条 `ita215-*`（96 → 104）。

## 未发布 — 实验7 IO 接口（Logisim-ITA 2.16.1.0）沉淀

- 新增 `scripts/v271/netmap.py`：端口级网表（并查集 + T 接规则），
  `--comp` 只看某元件的网、`--overlap` 查共线短接、`--grid` 查斜线与非 10 倍长度。
- 新增 `scripts/v271/sevenseg.py`：数码管 `check`（a~g 段位 + `active` 极性）、
  `table`（D=0~15 对标准字模）、`demo`（生成 N 只数码管 A~F 演示电路）。
- 新增 `scripts/v271/segshot.py`：按截图像素识别每个数码管亮了哪几段（`--expect`）。
- 固化 L1~L12：`active="high"` 被布尔解析成 `false` → 数码管整块反相；7-Segment
  Display 8 脚坐标与 `SEGMENTS[]` 顺序；无 `<appear>` 子电路按 10px 打包端口；
  Text 不支持 `&#10;`；中文标签需 CJK 字体；子电路 `clabel` 压在外观上；
  共线重叠=短接而十字交叉不连；端口级核对用 netmap；GUI 按键被抢焦点；
  shift+滚轮缩放方向；斜线导致 `WireRepair` 死循环 OOM；`javap` 拆 jar 查端口与属性类型。
- 修 `实验7 IO接口实验.circ`：`七段显示0~F` 的 7 处 `active` 改布尔值；
  main 里被 WireRepair 拆坏的 1px 短桩 + 斜线恢复成 `(401,200)-(440,200)`；
  新增 `思考题1 A~F显示` 电路（6 组 常数 10~15 → 译码器 → 数码管）。
  验收：`ERRCOUNT 0`、`main 不变式 20/20`、`sevenseg check` 全绿、`table` 16/16。
- 文档：`references/pitfalls.md` 新增 L 组；`SKILL.md` 的 2.16 表 / 症状表 / 脚本表 /
  资源表同步；`docs/VERSIONS.md` 补 2.16 实测项与脚本归属；`knowledge.json`
  追加 12 条 `ita216-*`（83 → 95）。
- 同步入库 `scripts/v215/gen_lab7.py` / `verify_lab7.py`：实验7 的 2.15 版生成器与穷举验证
  （2k+1奇校验 512 组、编码 256 组、解码 512 组、main 逐拍 trace 读随机屏蔽字）。
- 新增 `scripts/v271/attrprobe.py` + `scripts/v271/ita/AttrProbe.java`：直接调用 Logisim 内部
  `SetAttributeAction`（等价于界面里改文字）来判定 `WireRepair` 是否死循环；新增 **L13**
  （端口与导线差 1px → 改任意属性都卡死，栈顶 `WireRepair.doOverlaps:176`）。

## 未发布 — 实验6 存储器实验（2.15.0.2）沉淀

- 新增 `scripts/v215/gen_lab6.py`（素材 2.7.1 工程上完成 D1 字扩展 + 16×16 姓名显示 +
  存储器扩展问答）、`verify_lab6.py`（D1 9 个机内码 + 姓名显示 17 行逐拍向量）。
- D1：4 片 4K×32 → 16K×32；14 位地址拆低 12 位并联 / 高 2 位选 4:1 MUX；
  `ERRCOUNT 0`，D1 与选中 bank 逐例一致。
- 姓名显示：计数器 → 16×16 ROM（东北大学计算机硬件 9 个机内码）→ 机内转区位码
  → 16×16 字库 → 8 个 32→2 分线器 → 16×16 点阵；17/17 行通过。
- 固化 K41~K52：2.7.1 素材 source 头不能改成 2.15、复用素材 ROM 元素、测试引脚中段 T、
  隧道压线、子电路端口起点、Counter Q/carry 短接、D1 低 12/高 2、32→2 分行、
  bank3 不可达、ROM cs 悬空、Clock 换 Pin、问答地址位数。
- 文档：新增 `references/storage215-casebook.md`；`SKILL.md` 2.15 段与资源表补实验6；
  `knowledge.json` 同步 12 条（71 → 83）。

## 未发布 — 实验5 指令分析和程序设计（2.15.0.2）沉淀

- 新增 `scripts/v215/gen_lab5.py`（指令格式 + 4 程序 ROM + 4 选 1 + Regs Q0~Q3 +
  符号扩展 S-I/B + A 通道移位 MUX + Flag 门控）、`verify_lab5.py`（ISA 模型 +
  六场景 600 行逐拍向量，含例4 三分支 ROM 变体）。
- `board215.py` 的 `Board.ext()` 新增 `sign=True`（Bit Extender `type="sign"`）。
- 固化 K30~K40：立即数/偏移符号扩展、S-Regs 位序、移位固定 1 位、
  Comparator `twosComplement`、T1 取指、跳转不更新 Flag、INC 的 SA 字段、
  4 ROM+Prog、模型化验证的补码/进制/文件名、多层子电路逐拍向量、布局回归。
- 实验5 交付 `实验5 指令分析.circ`（17 电路）：600 行全过，ERRCOUNT 0，
  六项布线自检 0 错误。
- 文档：新增 `references/instruction215-casebook.md`；`SKILL.md` 2.15 段与资源表补实验5；
  `knowledge.json` 同步 K30~K40 共 11 条（连同实验4 K20~K29，两批合计 50 → 71）。

## 未发布 — 实验4 控制器模块（2.15.0.2）沉淀

- 新增 `scripts/v215/calib_lab4.py`（Register/Counter/DFF/RAM/ROM/Decoder/多分支 Splitter
  标定）、`gen_ctrl_lab4.py`（Regs/PC/IR/ID/CLK/S-I/B/Flag/CU/系统连接 9 电路 +
  六项自检 + 紧凑布局）、`verify_ctrl_lab4.py`（9 电路 112 行时序/组合向量）。
- `board215.py` 扩展：`dff / adder / register / counter / ram / rom / decoder / splitn`
  及 `lead()`；`fan_stub` 改为横向 20+30i、纵向交替 ±25；`fan_bits` 30px 步进；
  `gate_io` 输入自动扇出，消除隧道压盖。
- `ITAProbe.java` 新增 `--trace`，逐行打印所有引脚值；`ita_probe.run_vector(trace=True)`。
- 固化 K20~K29：Register 端口与写使能边沿竞争、2.15 内置 Adder 的 Cout 是输入脚、
  Counter 向下计数、RAM cs 低有效 / oe 高有效、ROM cs、多分支 Splitter 的 bit 分组、
  子电路外观 `pin` 必须写真实 Pin 坐标、XYZ 位序（bit15/14/13）、手工 `--set` 不可靠、
  隧道/引脚视觉间距与重叠检查；`knowledge.json` 补 K20~K29 共 10 条。
- 实验3 电路同步按新间距规则重排（3436/1984/1936/1452 行全过）；实验4 112 行全过，
  ERRCOUNT 0，系统连接 1630×1100 量级。
- 文档：新增 `references/controller215-casebook.md`；`SKILL.md` 2.15 表补
  Register/Counter/Adder/RAM/ROM 与布局间距，资源表补实验4 工具；
  `tools/sync_skill.py` 支持 `--home ~/.trae-cn` 同步到 Trae 技能目录。

## 未发布 — 实验3 8位 ALU（带比较器，2.15.0.2）沉淀

- `scripts/v215/board215.py` 扩展：新增 `mux / cmp / const / ext / shifter / split`
  与 `fan_bits / fan_stub`；固化 2.15 的 MUX（`enable=false`）、Comparator、Bit Extender、
  Constant、Shifter、2/3/8 位 Splitter（南/北向）实测几何。
- 新增 `scripts/v215/calib_lab3.py`（元件端口标定）、`gen_alu_lab3.py`（8 位 ALU 生成 +
  紧凑布局 + 六项自检）、`verify_alu_lab3.py`（模块级 + 顶层 16604 行向量）、
  `probe_points.py`（按坐标读运行值）、`test_wide.py`（宽 Pin/分线器/隧道最小复现）。
- `scripts/v271/ita/ITAProbe.java` 新增 `ProbeLoader`：覆写 `Loader.showError`，
  加载异常打印 `LOADERR`，不再被 HeadlessException 吞掉。
- 固化 K12~K19 八条新坑：Tunnel facing 必须全称、分线器位口悬空反推总线、
  无头加载吞错误、`--probe/--dump` 在 Pin/Tunnel 上可能读旧值、Shifter 可变距离与 SOL、
  MUX `enable=false`、比较结果 S=0x01/0x00、INC/NEC 先把 B 置 0。
- 文档：新增 `references/alu215-casebook.md`；`SKILL.md` 2.15 表补 MUX/Comparator/
  BitExtender/Shifter/Splitter/Tunnel 几何与 ALU 工具，坑表 94→102、2.15 11→19 坑；
  `geometry.md` 新增第 11 节 2.15 实测补充；README 坑数与 2.15 说明同步。
- 验证：8 个电路、16604 行向量 0 失败；ALU 顶层 2480×1780 → 1460×1030。

## 未发布 — Logisim-ITA 2.15.0.2 支持（实验2 加法器沉淀）

- 技能新增 `scripts/v215/`：`board215.py`（2.15 实测几何 + Board 追加式构建 + 六项正交布线自检）、
  `gen_adder_lab2.py`（加法器生成）、`verify_adder_lab2.py`（穷举/随机向量）、
  `LoadTest.java`（覆写 `Loader.showError` 打印加载异常）。
- 固化 2.15.0.2 几何：AND/OR 输入 `x-30`、XOR `x-40`、**NOT `x-20`**、偶数输入中间留 20px 空档；
  子电路实例端口 = `loc + (端口中心 − 锚点中心)`；实例 `<comp>` 不写 `lib`。
- `circ271_check` / `circ271_sim` / `circ271_ports` 标注同时适用 ITA 2.15/2.16；
  `circ271_check` 遇到 `source="2.15/2.16"` 会在输出首行提示“门体按原始 2.7.1 建模，可能误判穿体”。
- `logisim_info` 增加「2.15/2.16支持」块，报告 `logisim.local.json` 的 `ita_jar`。
- 技能文档：`SKILL.md` 增加 2.15 实测表；新增 `references/adder215-casebook.md`；
  `pitfalls.md` 增加 K 组 11 条（83 → 94 条）；经验库 `knowledge.json` 同步 11 条。

## 未发布 — Logisim 2.7.1 独立语义层（CPU / DM 纠错沉淀）

- 新增 `server/circuit_kit/circ271.py`：按 2.7.1 实测几何与语义实现网表重建、静态检查、
  网表仿真与端口几何，独立于 5.0 的 `netlist.py` / `geometry.py`。
- 新增 MCP 工具 `circ271_check` / `circ271_sim` / `circ271_ports`（工具总数 15 → 18）：
  - `circ271_check`：位宽冲突、多驱动、悬空、导线穿体、Decoder/Mux 的 sel/en 接入方向；
  - `circ271_sim`：驱动输入 Pin → 打时钟 N 拍 → 读引脚/Tunnel，RAM 按 `str≠0 即写` 建模；
  - `circ271_ports`：Splitter 分支、门输入排布、RAM 五控制脚等实测坐标。
- 固化 2.7.1 语义：Splitter 分支 `y-10*fanout+10*i`（east）、门默认 5 输入、Decoder
  禁用输出默认 Z（`disabled=0` 才为 0）、RAM CS/OE 悬空=使能、Register en 悬空=使能、
  保存时省略 `fanout`/`enable` 默认属性。
- 文档：README 增加「Logisim 2.7.1 支持」；技能新增 `references/cpu271-casebook.md`，
  `pitfalls.md` 增加 J 组 13 条（69 → 82 条），`geometry.md` / `verification.md` 增加 2.7.1 章节。

## 未发布 — 网表支持寄存器/复用器/译码器/比较器；体检补连通性与位宽

- 网表支持 `Multiplexer` / `Decoder` / `Register` / `Comparator`：按 5.0 实测端口建模；
  寄存器支持 clk 边沿 + en + 异步 clr，比较器支持 unsigned / twosComplement。
- 子电路端口 读取 `<appear>` 的 `circ-port` 符号坐标：自定义外观不再按经典布局错位
  （H15「跨电路串名」与 H24 的根因）。
- 审计：新增位宽冲突、断头线（10px 断口）检查；遇到不认识的元件返回 `partial` + 清单，
  MCP 不再把它当作成功。
- 几何 `circ_geometry` 支持 register / mux / decoder / comparator / constant / pin /
  splitter 等，修正分线器公式（east 为 `-10*(n-k)`，`incoming` 缺省恒为 2，并支持
  `appear=left/center/right`）；多路选择器/译码器补 `facing=west` 与 `enable` 变体。
- 新增 `circ_probe`：把 Java 桥的 `probe_libraries` / `probe_component` 暴露成 MCP 工具。
- 经验库 `_SEED` 改为直接读取随包 `knowledge.json`，加载时把缺失条目并回运行时副本，
  消除内联副本漂移；`circ_kb add` 只写运行时副本，要发布需手动搬进仓库 JSON。

## 1.3.0 — 32×32 寄存器堆：全实体布线 + 元件探测

- 新增 Java 桥命令 `probe_libraries` / `probe_component`：向运行中的 Logisim 询问任意元件的
  包围盒、端口偏移与位宽，补齐 5.0 的 Register / Decoder / MUX 2:1·4:1·8:1 / Comparator /
  Constant / Pin / Splitter 正反朝向数据。
- 经验库新增 9 条坑（H20–H28）：空 `<toolbar/>` 导致工具条消失、10px 断口与整网连通性、
  译码器底部 sel/en、分线器朝向与 b0 位序、外观 `pin=` 两套坐标、探针假 `U`、
  复位释放与时钟沿同拍、引脚 40px 间距、子电路旁路冗余。
- 几何表新增 `register32 / decoder / mux / comparator / constant / pin / splitter`。
- 规则：禁止隧道写死到所有层级；交付自检必须包含整网连通性（并查集），
  只验证“端口碰到线”不算过。
- 修正 生成的 `.circ` 补全 `<toolbar>`，否则打开后顶部没有 Poke/Edit/Wiring/Text 工具。

## 1.2.0 — 子电路外观编辑

- 新增 MCP 工具 `circ_appearance`：在 Logisim 自己的 JVM 里调用 `CircuitAppearance`，支持
  `get / auto / apply / preview / save / reset / close`，界面实时刷新，保存前备份、保存后用
  `-t stats` 重新加载校验。
- 新增 Java 桥（`server/java/`，`tools/build_bridge.py` 编译为 `runtime/bridge/logisim-bridge.jar`）：
  通过 127.0.0.1 NDJSON 控制，模型操作在 EDT 上执行，所有电路加写锁后修改外观。
- 新增 `server/circuit_kit/appearance.py`：外观 spec、左入右出自动排版、10px 网格/端口覆盖/名称牌校验、
  XML 兜底读写与父电路影响面统计。
- 默认保端口：`preserve_port_positions=true` 只重画框体与标签，避免父电路导线脱开；
  重排模式会返回受影响的父电路与导线数。
- 修正十六进制数码管的包围盒：此前按 `62×56` 算，实际（5.0 源码 `HexDigit.setOffsetBounds`）是
  `Bounds.create(-15, -60, 40, 60)`——`loc` 在底边上。间距 50px 的两个数码管因此被 `circ_audit`
  误报「元件体重叠」，`geometry.md` 的数字也一起改对了。
- 新增 `examples/counter13.circ`：两位 13 进制计数器，三层结构、不使用隧道，26 个门与触发器全部由网表生成。
- 文档 README 增加电路截图与 `circ_sim` 的逐拍输出。

## 1.1.0 — 技能并入插件，准备开源

1.0.0 里插件只带了一个精简技能（三份参考）。这一版把它补成自包含、可单独使用的完整技能，
并确立「插件技能 = 唯一事实来源，用户目录只是安装副本」。

技能补齐为 11 个文件

- `SKILL.md` 重写为双路径：路径 A 用 MCP 工具（`circ_build` → `circ_audit` → `circ_sim` → 真值表复核），
  路径 B 用随包脚本手写 XML；两条路共用同一套几何常量、布线规则与坑表。
- 新增 `references/circ-format.md`、`references/verification.md`（原先只在用户技能目录里）。
- 新增 `scripts/logisim_gen.py`、`scripts/router.py`、`scripts/verify.py`——装完插件即可离线写电路，不依赖 MCP。
- 新增 `assets/full-adder.circ`（5.0 格式，真值表 8/8 的已知可用样例）。

内容合并（消除两份漂移）

- 两份 `pitfalls.md` 合一：插件精简版的 3 条独有内容（引脚 `type` 写成 `in`/`out`、NOT 的 −30 特例、
  真值表输入爆炸）并入总表，现为 38 条。
- `geometry.md` 以含 3.9/5.0 对照表的版本为准，并补上 Clock / LED / Constant / Tunnel 的端口表。
- `verification.md` 的「MCP 桥接」一节改写为插件版 13 工具；新增「时序电路的验证」一节，
  明确 `-w` 只能验组合；交付清单改为「`circ_audit` ok + 组合无 E/U + 时序跑满序列」。

工具

- 新增 `tools/sync_skill.py`：插件为源、`~/.workbuddy/skills/` 为目标，默认只对比，
  `--apply` 才写入（覆盖前留 `.bak`），`--prune` 才删多余文件，`--to-plugin` 可反向。

能力

- `circ_build` 新增 `GROUND` 元件：数码管数据口固定 4 位时，用它将未使用的高位拉低，
  否则未连接位会显示成 `U`（屏上是乱码）。

开源准备

- 新增 `tools/check_release.py`：版本三处一致（清单 / 服务端兜底 / CHANGELOG）、
  无本机路径与个人信息、JSON 与 Python 语法、`.cmd` 必须纯 ASCII、分发包内容干净。
- 仓库卫生：`.gitignore`、`.gitattributes`（`.cmd` 强制 CRLF）、`.editorconfig`、`Makefile`。
- 文档：`CONTRIBUTING.md`、`SECURITY.md`、`docs/ARCHITECTURE.md`、`docs/PLUGIN-SPEC.md`、`docs/DESIGN-NOTES.md`。
- 示例：`examples/` 下三个可直接打开的电路（与门 / 半加器 / 两位行波计数器）+ `generate.py`，生成后自动体检。
- CI：`.github/workflows/ci.yml`（Ubuntu 3.9/3.12 + Windows 3.12，含 `.cmd` 握手测试）、
  `release.yml`（打 tag 自动构建 zip 并发布）、issue / PR 模板。
- 可移植性：jar 查找不再含任何机器专属目录，改为「`LOGISIM_JAR` → `logisim.local.json` →
  `runtime/` → 系统安装位置 → 当前目录」；新增 `logisim.local.example.json` 作为本地配置模板。

命名与版本

- 仓库、插件、分发 zip 统一为 `logisim-mcp`（早期内部代号 `logisim-circuit`），
  技能名保留 `logisim-circuit-design`（它描述的是能力，不是产品）。
- `tools/install.py` 改为从 `plugin.json` 读插件名，改名只需要动清单一处；
  安装时会自动清理市场里同名插件的旧目录。
- 清单与服务端版本统一为 `1.1.0`；服务端默认版本号同步提高（读不到 `plugin.json` 时的兜底）。

## 1.0.0 — 封装为插件

首个插件版本。把此前散落在 `logisim_mcp/` 的能力整合成标准插件包，并补齐分发所需的一切。

新增

- 标准插件结构：`.codebuddy-plugin/plugin.json` + `.mcp.json` + `skills/`，可用 `${CODEBUDDY_PLUGIN_ROOT}` 占位符安装到任意路径。
- 随插件分发技能 `logisim-circuit-design`：`SKILL.md` + 三份 references（几何 / DSL / 坑表）。
- `server.py --doctor`：一条命令体检 python、java、jar、知识库可写性、清单一致性，并跑一次「生成 → 体检 → 仿真」短路自检。
- 启动器 `bin/run-mcp.cmd` / `bin/run-mcp.sh`：自动定位 python（`LOGISIM_PYTHON` → `python` → `python3`）。
- `tools/selftest.py`：13 个工具的端到端回归，含 5 条失败路径与 Logisim 交叉复核。
- `tools/build_zip.py`：打成可分发的 zip（排除 `__pycache__`、`.in_use` 等）。
- `tools/install.py`：注册本地 directory 市场或直接写入 `~/.workbuddy/mcp.json`，改配置前自动备份。

改进

- jar 查找顺序扩展：`LOGISIM_JAR` → `<插件>/runtime/` → 插件数据目录 → `Program Files` → `LOCALAPPDATA` → `~/.logisim` → `D:/app` → 当前目录。
- java 查找扩展：`PATH` → `JAVA_HOME` → 常见 JDK 厂商目录 → `<插件>/runtime/jre/`。
- 服务端版本号自动读取 `plugin.json`，不再有两处版本号各说各话的问题。
- 知识库落盘位置支持 `LOGISIM_KB` 与 `${CODEBUDDY_PLUGIN_DATA}`，首次运行自动从随包 `knowledge.json` 播种，升级不丢用户新增的经验。
- 知识库种子修正：`NOT` 宽度由 50 改为实测的 30，并补齐 `not-default-inputs`、`wire-repair-snap`、`ripple-edge-detection` 三条。

## 0.3.0 — 审计问题全量修复

- 未知元件不再被静默忽略，改为显式报错并列出元件名与坐标；体检返回 `verdict=unsupported`。
- 实现 Tunnel（按 label 同层合并）、T 触发器（按 T 翻转）、Constant（按十六进制驱动）。
- 时钟自动识别：Clock 组件，或名为 `cp` / `clk` / `clock` / `ck` 的根层引脚；也可用 `clock` 参数指定。
- 自动布局改为分列放置（时钟最左、门按深度、LED/数码管最右），撞坐标自动下移。
- Clock / LED / 数码管补上包围盒，`body_overlap` 从此能查出重叠。
- 体检白名单收紧：只豁免触发器 `R/S/~Q` 与分线器空位。
- `circ_build` 新增网络位宽一致性校验；新增 `verify` 选项，生成后自动跑真值表并报 E/U 单元数。
- 真值表保护：输入 >16 直接拒绝，行数默认截断 4096（`max_rows` 可调）。
- 知识库改原子写（tmp + `os.replace`）+ `schema_version` + 结构自愈，坏文件自动备份为 `.corrupt`。
- 输出解码改 UTF-8 → GBK → latin-1 逐级回退，不再依赖 JDK 的 `-Dstdout.encoding`。
- `initialize` 回显客户端请求的 `protocolVersion`；GUI 子进程使用独立进程组。
- `-w` 描述纠正为"只能验组合逻辑"。

## 0.2.0 — 能力层整合

- 新增 5 个工具：`circ_geometry`、`circ_audit`、`circ_sim`、`circ_build`、`circ_kb`。
- 新增 `circuit_kit/`：geometry、router（10px 网格 A*）、netlist（解析 + 仿真）、builder（DSL）、audit、knowledge。
- 布线器把元件端口列为禁入点，修掉"竖线穿过 Q 与 ~Q 造成短接"。
- 仿真器改逐触发器边沿检测，支持异步/行波级联。

## 0.1.0 — 初始桥接

- stdio MCP 服务端，包装 `-t table` / `-t stats` / `-w` / `-n` 等无头能力。
- 8 个基础工具：info、summary、truth_table、verify、test_vector、stats、build（隧道版）、open_gui。
