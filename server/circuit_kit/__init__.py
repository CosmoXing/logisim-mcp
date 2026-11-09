"""Logisim 电路工具包（MCP 桥接的新增能力层）。

模块分工：
  geometry  元件几何（端口偏移 / 包围盒），数据可由 knowledge.json 覆盖
  router    声明式网络 → 自动布线 → .circ 文本（无隧道）
  netlist   .circ 解析 → 网表重建 → 仿真（独立于 router 的第二套几何实现）
  builder   声明式 JSON 规格 → 多电路工程
  audit     静态连接体检（悬空 / 多驱动 / 端口未接）
  knowledge 经验库（几何事实与踩坑记录），可持续追加
"""

from . import geometry, router, netlist, builder, audit, knowledge  # noqa: F401

__all__ = ["geometry", "router", "netlist", "builder", "audit", "knowledge"]
