## 这个 PR 做了什么

<!-- 一句话说明 -->

## 类型

- [ ] 修 bug
- [ ] 新元件 / 新能力
- [ ] 文档或示例
- [ ] 重构（不改变行为）

## 检查清单

- [ ] `python tools/check_release.py` 通过
- [ ] `python tools/selftest.py` 通过（无 Java 环境可 `--quick`）
- [ ] 新增能力有对应的 selftest 用例，且**至少覆盖一条失败路径**
- [ ] 若修改了端口几何，`geometry.py` 与 `netlist.py` 两处都改了
- [ ] 若发现新坑，已写进 `knowledge.json` 或 `references/pitfalls.md`
- [ ] 没有提交 `dist/`、`__pycache__`、`logisim.local.json`
- [ ] 版本号与 CHANGELOG 已按需更新

## 相关 issue

<!-- Closes #123 -->
