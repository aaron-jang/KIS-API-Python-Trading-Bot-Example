#!/bin/bash
# 실시간 로그 확인
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

LOG_FILE=$(ls -t "$PROJECT_DIR"/logs/bot_app_*.log 2>/dev/null | head -1)

if [ -n "$LOG_FILE" ]; then
    echo "📋 로그 파일: $LOG_FILE"
    echo "   (Ctrl+C로 종료)"
    echo "---"
    tail -f "$LOG_FILE"
else
    echo "⚠️  로그 파일이 없습니다. 봇을 먼저 실행해주세요."
fi
