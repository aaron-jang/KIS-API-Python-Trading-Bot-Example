FROM python:3.12-slim

# 시스템 폰트 설치 (telegram_view.py의 PIL 이미지 렌더링용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# 타임존 설정 (스케줄러가 KST 기준으로 동작)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 의존성 먼저 설치 (캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY main.py ./
COPY trading_bot/ ./trading_bot/

# 데이터/로그 디렉토리 생성
RUN mkdir -p data logs

CMD ["python", "main.py"]
