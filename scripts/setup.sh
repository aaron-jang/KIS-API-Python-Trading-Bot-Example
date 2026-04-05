#!/bin/bash
# ==========================================================
# KIS Trading Bot 초기 설치 스크립트 (라즈베리파이 / Linux)
# ==========================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  KIS Trading Bot 설치 시작"
echo "  프로젝트 경로: $PROJECT_DIR"
echo "============================================"

# 1. venv 생성
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv "$PROJECT_DIR/venv"
    echo "✅ 가상환경 생성 완료"
else
    echo "✅ 가상환경이 이미 존재합니다"
fi

# 2. 패키지 설치
echo "📦 패키지 설치 중..."
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
echo "✅ 패키지 설치 완료"

# 3. .env 파일 확인
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo ""
    echo "⚠️  .env 파일이 생성되었습니다. 실제 키를 입력해주세요:"
    echo "    vi $PROJECT_DIR/.env"
    echo ""
else
    echo "✅ .env 파일이 이미 존재합니다"
fi

# 4. data/logs 디렉토리 생성
mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"

echo ""
echo "============================================"
echo "  설치 완료!"
echo ""
echo "  실행: $PROJECT_DIR/scripts/start.sh"
echo "  중지: $PROJECT_DIR/scripts/stop.sh"
echo "  로그: $PROJECT_DIR/scripts/logs.sh"
echo "============================================"
