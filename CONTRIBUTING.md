# 贡献指南

感谢愿意帮忙。这个项目的核心价值是**准确**：几何常量、连通规则、仿真语义都必须经得起实测。
所以下面的要求都围绕一件事——**结论要有证据**。

## 可以贡献什么

| 类型 | 说明 |
|---|---|
| 🐛 Bug | 生成的电路打不开 / 仿真结果与 Logisim 不一致 / 体检漏报或误报 |
| 📐 几何修正 | 某个元件在某个版本下的端口偏移不对 |
| 🕳️ 新的坑 | 你踩过的坑，用 `circ_kb add` 记一条，或改 `server/circuit_kit/knowledge.json` |
| 🧩 新元件 | 支持更多组件（如 Register、Counter、Multiplexer）——注意不要和"禁用现成器件"的作业冲突 |
| 📝 文档 | 错别字、表述不清、示例跑不通 |
| 🌐 平台 | macOS / Linux 上的路径与编码问题 |

## 开发环境

```bash
git clone <仓库地址>
cd logisim-mcp
python --version          # 3.8+
python tools/selftest.py  # 应该 29/29 通过
```

没有 Java 也能开发：`python tools/selftest.py --quick` 会跳过依赖 Logisim 的 3 个用例。

## 提交前必跑

```bash
python tools/check_release.py     # 版本一致性 / 本机路径 / 语法 / 打包内容
python tools/selftest.py          # 端到端回归
```

CI 会在 Ubuntu（3.9 / 3.12）和 Windows（3.12）上跑 `--quick`。**不要提交 `dist/`、`__pycache__`、`logisim.local.json`。**

## 代码约定

- **只用标准库**。引入第三方依赖需要先在 issue 里讨论。
- 4 空格缩进、UTF-8、LF 换行（`.editorconfig` 已配好）。
- `bin/run-mcp.cmd` **必须保持纯 ASCII + CRLF**：UTF-8 中文注释在 GBK 控制台下会让 `rem` 行被当命令执行。
- 报错要带**可操作的信息**：网络名 + 坐标 + 建议，而不是只抛一个 `E`。
- 宁可显式失败，也不要静默降级——这是本项目最重要的一条设计原则。

## 加一个元件支持

1. `server/circuit_kit/geometry.py`：加端口偏移与包围盒（**两处独立实现**：
   `geometry.py` 供生成用，`netlist.py` 的 `_ports()` 供解析用，两处都要改）。
2. `server/circuit_kit/router.py`：加发射函数（如果需要新外观）。
3. `server/circuit_kit/builder.py`：加入 `SPECIAL` 集合与 `_port_map` / `_dir_of` / `_port_width`。
4. `server/circuit_kit/netlist.py`：加入 `SUPPORTED`、`_ports`、`_widths`、`_settle` 的行为。
5. `server/circuit_kit/audit.py`：补包围盒（否则重叠检测不到）。
6. `server/circuit_kit/knowledge.json` + `geometry.md`：记录实测到的端口表。
7. `tools/selftest.py`：加一条用例，**必须包含至少一个失败路径**。

## 报 bug 时请附上

- Logisim 版本（`head -3 xxx.circ | grep source`）
- `python server/server.py --doctor` 的输出
- 能复现的最小 `.circ` 或 `circ_build` 的 spec
- 期望结果 vs 实际结果（贴 `circ_audit` / `circ_sim` 的原文）

## 提交信息

用 Conventional Commits 的简化版：

```
fix(geometry): NOT 门输入口按 -30 处理
feat(netlist): 支持 Register 组件
docs(skill): 补充 5.0 与 3.9 的引脚写法差异
```

## 许可

提交 PR 即表示同意以 [MIT](LICENSE) 许可发布你的贡献。
