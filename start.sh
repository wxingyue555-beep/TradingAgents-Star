#!/bin/bash
# TradingAgents 一键启动（Linux）
# 用法: bash start.sh [端口号，默认8000]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8000}"
VENV="$SCRIPT_DIR/.venv"
RESULT_DIR="/media/star-linux/文件盘/BaiduSyncdisk/data/outroport"

# 激活虚拟环境
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
else
    echo "[错误] 未找到虚拟环境，请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -e . && pip install fastapi uvicorn jinja2"
    exit 1
fi

# 环境变量
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-sk-632324e1b33e4728b28232c50142be27}"

# 结果目录
mkdir -p "$RESULT_DIR"

# 端口占用处理
if lsof -i ":${PORT}" &>/dev/null; then
    echo "[提示] 端口 ${PORT} 被占用，清理中..."
    lsof -ti ":${PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo "============================================"
echo "  TradingAgents Web 服务"
echo "  地址: http://localhost:${PORT}"
echo "  结果: ${RESULT_DIR}"
echo "  模型: deepseek-v4-pro"
echo "  Ctrl+C 停止"
echo "============================================"

exec python3 -m uvicorn web_app.main:app --host 0.0.0.0 --port "${PORT}" --reload --log-level info
