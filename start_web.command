#!/bin/bash
# TradingAgents Web — 一键启动 (双击此文件即可)
cd "$(dirname "$0")"

echo ""
echo "   ████████╗██████╗  █████╗ ██████╗ ██╗███╗   ██╗ ██████╗  "
echo "   ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝  "
echo "      ██║   ██████╔╝███████║██║  ██║██║██╔██╗ ██║██║  ███╗ "
echo "      ██║   ██╔══██╗██╔══██║██║  ██║██║██║╚██╗██║██║   ██║ "
echo "      ██║   ██║  ██║██║  ██║██████╔╝██║██║ ╚████║╚██████╔╝ "
echo "      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝  "
echo ""
echo "               Web Server · 一键启动"
echo "   ─────────────────────────────────────────"
echo ""

PORT="${1:-8000}"

# 端口清理
if lsof -i ":${PORT}" &>/dev/null; then
    echo "⚠️  端口 ${PORT} 已被占用，清理中..."
    lsof -ti ":${PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
    echo "✅ 端口已释放"
fi

# 依赖检查
python3 -c "import fastapi, uvicorn, tradingagents" 2>/dev/null || {
    echo "❌ 缺少依赖，正在安装..."
    pip3 install -e . fastapi uvicorn jinja2 2>/dev/null
    echo "✅ 依赖安装完成"
}

echo "🚀 服务启动中..."
echo "🌐 浏览器访问: http://localhost:${PORT}"
echo "🛑 按 Ctrl+C 停止"
echo ""

python3 -m uvicorn web_app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --reload \
    --log-level info
