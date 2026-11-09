# 更新记录

## 1.1.0 — 技能并入插件，准备开源

1.0.0 里插件只带了一个精简技能（三份参考）。这一版把它补成**自包含、可单独使用**的完整技能，
并确立「插件技能 = 唯一事实来源，用户目录只是安装副本」。

**技能补齐为 11 个文件**

- `SKILL.md` 重写为**双路径**：路径 A 用 MCP 工具（`circ_build` → `circ_audit` → `circ_sim` → 真值表复核），
  路径 B 用随包脚本手写 XML；两条路共用同一套几何常量、布线规则与坑表。
- 新增 `references/circ-format.md`、`references/verification.md`（原先只在用户技能目录里）。
- 新增 `scripts/logisim_gen.py`、`scripts/router.py`、`scripts/verify.py`——装完插件即可离线写电路，不依赖 MCP。
- 新增 `assets/full-adder.circ`（5.0 格式，真值表 8/8 的已知可用样例）。

**内容合并（消除两份漂移）**

- 两份 `pitfalls.md` 合一：插件精简版的 3 条独有内容（引脚 `type` 写成 `in`/`out`、NOT 的 −30 特例、
  真值表输入爆炸）并入总表，现为 **38 条**。
- `geometry.md` 以含 3.9/5.0 对照表的版本为准，并补上 Clock / LED / Constant / Tunnel 的端口表。
- `verification.md` 的「MCP 桥接」一节改写为插件版 13 工具；新增「时序电路的验证」一节，
  明确 `-w` 只能验组合；交付清单改为「`circ_audit` ok + 组合无 E/U + 时序跑满序列」。

**工具**

- 新增 `tools/sync_skill.py`：插件为源、`~/.workbuddy/skills/` 为目标，默认只对比，
  `--apply` 才写入（覆盖前留 `.bak`），`--prune` 才删多余文件，`--to-plugin` 可反向。

**能力**

- `circ_build` 新增 `GROUND` 元件：数码管数据口固定 4 位时，用它将未使用的高位拉低，
  否则未连接位会显示成 `U`（屏上是乱码）。

**开源准备**

- 新增 `tools/check_release.py`：版本三处一致（清单 / 服务端兜底 / CHANGELOG）、
  无本机路径与个人信息、JSON 与 Python 语法、`.cmd` 必须纯 ASCII、分发包内容干净。
- 仓库卫生：`.gitignore`、`.gitattributes`（`.cmd` 强制 CRLF）、`.editorconfig`、`Makefile`。
- 文档：`CONTRIBUTING.md`、`SECURITY.md`、`docs/ARCHITECTURE.md`、`docs/PLUGIN-SPEC.md`、`docs/DESIGN-NOTES.md`。
- 示例：`examples/` 下三个可直接打开的电路（与门 / 半加器 / 两位行波计数器）+ `generate.py`，生成后自动体检。
- CI：`.github/workflows/ci.yml`（Ubuntu 3.9/3.12 + Windows 3.12，含 `.cmd` 握手测试）、
  `release.yml`（打 tag 自动构建 zip 并发布）、issue / PR 模板。
- 可移植性：jar 查找不再含任何机器专属目录，改为「`LOGISIM_JAR` → `logisim.local.json` →
  `runtime/` → 系统安装位置 → 当前目录」；新增 `logisim.local.example.json` 作为本地配置模板。

**命名与版本**

- 仓库、插件、分发 zip 统一为 `logisim-mcp`（早期内部代号 `logisim-circuit`），
  技能名保留 `logisim-circuit-design`（它描述的是能力，不是产品）。
- `tools/install.py` 改为从 `plugin.json` 读插件名，改名只需要动清单一处；
  安装时会自动清理市场里同名插件的旧目录。
- 清单与服务端版本统一为 `1.1.0`；服务端默认版本号同步提高（读不到 `plugin.json` 时的兜底）。

## 1.0.0 — 封装为插件

首个插件版本。把此前散落在 `logisim_mcp/` 的能力整合成标准插件包，并补齐分发所需的一切。

**新增**

- 标准插件结构：`.codebuddy-plugin/plugin.json` + `.mcp.json` + `skills/`，可用 `${CODEBUDDY_PLUGIN_ROOT}` 占位符安装到任意路径。
- 随插件分发技能 `logisim-circuit-design`：`SKILL.md` + 三份 references（几何 / DSL / 坑表）。
- `server.py --doctor`：一条命令体检 python、java、jar、知识库可写性、清单一致性，并跑一次「生成 → 体检 → 仿真」短路自检。
- 启动器 `bin/run-mcp.cmd` / `bin/run-mcp.sh`：自动定位 python（`LOGISIM_PYTHON` → `python` → `python3`）。
- `tools/selftest.py`：13 个工具的端到端回归，含 5 条失败路径与 Logisim 交叉复核。
- `tools/build_zip.py`：打成可分发的 zip（排除 `__pycache__`、`.in_use` 等）。
- `tools/install.py`：注册本地 directory 市场或直接写入 `~/.workbuddy/mcp.json`，改配置前自动备份。

**改进**

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
