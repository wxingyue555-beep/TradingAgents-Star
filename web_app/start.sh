#!/bin/bash
# TradingAgents Web 快捷启动脚本
# 用法: cd web_app && bash start.sh
#       或直接从项目根目录: bash web_app/start.sh
set -e

# 自动定位项目根目录（相对于本脚本位置）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

PORT="${1:-8000}"

echo "============================================"
echo "  TradingAgents Web Server"
echo "  项目目录: $PROJECT_DIR"
echo "  监听端口: $PORT"
echo "============================================"

# 检查端口是否被占用
if lsof -i ":${PORT}" &>/dev/null; then
    echo "[警告] 端口 ${PORT} 已被占用，尝试终止已有进程..."
    lsof -ti ":${PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# 检查依赖
python3 -c "import fastapi, uvicorn, tradingagents" 2>/dev/null || {
    echo "[错误] 缺少依赖，请先运行: pip install fastapi uvicorn jinja2 && pip install -e ."
    exit 1
}

echo "[启动] $(date '+%H:%M:%S') 服务启动中..."
echo "[访问] http://localhost:${PORT}"
echo "[提示] 按 Ctrl+C 停止服务"
echo ""

python3 -m uvicorn web_app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --reload \
    --log-level info
