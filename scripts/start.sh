#!/bin/bash
# 봇 백그라운드 실행
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/.bot.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "⚠️  봇이 이미 실행 중입니다 (PID: $(cat "$PID_FILE"))"
    echo "    중지: $SCRIPT_DIR/stop.sh"
    exit 1
fi

echo "🚀 봇을 시작합니다..."
cd "$PROJECT_DIR"
TZ=Asia/Seoul nohup "$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/main.py" \
    >> "$PROJECT_DIR/logs/nohup.log" 2>&1 &

echo $! > "$PID_FILE"
echo "✅ 봇 시작 완료 (PID: $(cat "$PID_FILE"))"
echo "   로그: $SCRIPT_DIR/logs.sh"
