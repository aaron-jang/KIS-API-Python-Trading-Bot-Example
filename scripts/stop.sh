#!/bin/bash
# 봇 중지
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/.bot.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm "$PID_FILE"
        echo "✅ 봇 중지 완료 (PID: $PID)"
    else
        rm "$PID_FILE"
        echo "⚠️  프로세스가 이미 종료되어 있습니다. PID 파일을 정리했습니다."
    fi
else
    echo "⚠️  실행 중인 봇이 없습니다."
fi
