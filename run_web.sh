#!/bin/bash
# TradingAgents Web Server — auto-restart on crash
cd /Users/star_mac/Documents/GitHub/TradingAgents

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting server..."
    python3 -m uvicorn web_app.main:app --host 0.0.0.0 --port 8000 --reload 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Server stopped. Restarting in 3s..."
    sleep 3
done
