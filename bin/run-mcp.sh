#!/bin/sh
# ---------------------------------------------------------------
# logisim-circuit 插件的 stdio 启动器（macOS / Linux）
# 用法：./run-mcp.sh            正常启动 MCP 服务
#       ./run-mcp.sh --doctor  查看环境体检
# ---------------------------------------------------------------
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd) || exit 1

PY=${LOGISIM_PYTHON:-}
if [ -z "$PY" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PY=$c; break; fi
  done
fi
[ -z "$PY" ] && PY=python

PYTHONUTF8=1
PYTHONIOENCODING=utf-8
export PYTHONUTF8 PYTHONIOENCODING

exec "$PY" "$ROOT/server/server.py" "$@"
