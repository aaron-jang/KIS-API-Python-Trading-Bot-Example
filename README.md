# KIS-API-Python-Trading-Bot-Example

[![CI](https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example/actions/workflows/ci.yml/badge.svg)](https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/aaron-jang/c51777029ca0a51c869a27ed671e9dfd/raw/test-results.json)
![Version](https://img.shields.io/badge/version-V28.27-orange)
![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-lightgrey)

> 한국투자증권(KIS) Open API 기반 미국 주식 자동매매 파이썬 봇 (V28.27)

한국투자증권 Open API를 활용하여 미국 주식(SOXL, TQQQ 등)을 자동으로 매매하는 파이썬 트레이딩 봇 예제입니다. 라오어의 무한매수법 퀀트 전략, VWAP 타임 슬라이싱, 텔레그램 봇 제어, Docker 배포를 학습할 수 있는 기술적 레퍼런스로 작성되었습니다.

**Keywords**: 한투 API, 한국투자증권 자동매매, 미국주식 자동매매 봇, 라오어 무한매수법 파이썬, SOXL TQQQ 자동매매, VWAP 알고리즘, 텔레그램 트레이딩봇, KIS Open API Python, US Stock Trading Bot, Raspberry Pi 주식봇

---

## 목차

- [저작권 및 게시 중단 정책](#저작권-및-게시-중단take-down-정책)
- [면책 조항](#면책-조항-disclaimer)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [빠른 시작](#빠른-시작)
  - [Docker Compose](#방법-1-docker-compose-권장)
  - [스크립트 실행](#방법-2-스크립트-실행-linux)
  - [systemd 서비스 등록](#방법-3-systemd-서비스-등록-linux-재부팅-시-자동-실행)
  - [환경 변수](#환경-변수-env)
- [프로젝트 구조](#프로젝트-구조)
- [텔레그램 명령어](#텔레그램-명령어)
  - [조회](#조회)
  - [설정](#설정)
  - [긴급](#긴급)
- [테스트](#테스트)
- [문서](#문서)

---

## 저작권 및 게시 중단(Take-down) 정책

- 본 코드에 구현된 매매 로직(무한매수법)의 모든 아이디어와 저작권, 지적재산권은 원작자인 **'라오어'**님에게 있습니다.
- 무한매수법에 대한 자세한 내용은 [라오어 무한매수법 네이버 카페](https://cafe.naver.com/infinitebuying)를 참고하시기 바랍니다.
- 본 저장소는 순수하게 파이썬과 API를 공부하기 위한 기술적 예제일 뿐이며, 원작자의 공식적인 승인이나 검수를 받은 프로그램이 아닙니다.
- 만약 원작자(라오어님)께서 본 코드의 공유를 원치 않으시거나 삭제를 요청하실 경우, 본 저장소는 어떠한 사전 예고 없이 즉각적으로 삭제(또는 비공개 처리)될 수 있음을 명확히 밝힙니다.

## 면책 조항 (Disclaimer)

- 이 코드는 한국투자증권 Open API의 기능과 파이썬 자동화 로직을 학습하기 위해 작성된 **교육 및 테스트 목적의 순수 예제 코드**입니다.
- 특정 투자 전략이나 종목을 추천하거나 투자를 권유하는 목적이 **절대 아닙니다**.
- 본 코드를 실제 투자에 적용하여 발생하는 모든 금전적 손실 및 시스템 오류에 대한 법적, 도의적 책임은 **전적으로 코드를 실행한 사용자 본인**에게 있습니다.
- 본 코드는 어떠한 형태의 수익도 보장하지 않으므로, 반드시 충분한 모의 테스트 후 본인의 책임하에 사용하시기 바랍니다.

---

## 주요 기능

### 매매 엔진

| 기능 | 설명 |
|------|------|
| **라오어 무한매수법(V14) 퀀트 엔진** | T값, 별값 공식 기반 분할 매수/매도. LOC 단일 타격 또는 VWAP 슬라이싱 선택 가능 |
| **V-REV 역추세 방어 엔진** | LIFO 지층별 독립 익절, 0주 새출발 디커플링(0.999/0.935), 자동/수동 VWAP 모드 |
| **VWAP 타임 슬라이싱** | 장 마감 33분 전부터 U-Curve 유동성 가중치로 1분 단위 분할 매매. 5년 백테스트 기반 30개 가중치 |
| **AVWAP 듀얼 레퍼런싱** | 기초자산(SOXX) 시그널 스캔 + 파생상품(SOXL) 호가창 타격. 3대 강제 청산(하드스탑, 스퀴즈, 타임스탑) |
| **잭팟 스윕 피니셔** | 목표 수익률 도달 시 전량 지정가 덤핑. 거래소 락다운 우회, Daily Buy-Lock 방어 |

### 시스템

| 기능 | 설명 |
|------|------|
| **멀티 코어 스케줄러** | 시스템 관리(core_jobs)와 실전 매매(trade_jobs) SRP 분리 |
| **텔레그램 모바일 UI** | 인라인 버튼으로 장부 조회, 수동 주문, 모드 전환, 졸업 카드 발급 |
| **TrueSync 장부 동기화** | NYSE 영업일 자동 인식, 비파괴 보정(CALIB), 팩트 기반 잔고 교정 |
| **KIS API 토큰 관리** | OAuth2 로컬 캐싱, 만료 전 자동 갱신(Self-Healing), 원자적 쓰기(fsync) |
| **공포지수 기반 Regime-Switching** | ATR/VXN 실시간 스캔으로 하방 매수 차단/상방 익절 전환 자율주행 |
| **졸업 카드 GIF 렌더링** | 전량 익절 달성 시 수익금을 각인한 움짤(.gif) 텔레그램 자동 발급 |

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| **언어** | Python 3.12+ |
| **증권 API** | 한국투자증권(KIS) Open API (REST, OAuth2) |
| **시세 데이터** | yfinance (야후 파이낸스) |
| **봇 프레임워크** | python-telegram-bot (JobQueue 스케줄러) |
| **데이터 처리** | pandas, numpy, pandas_market_calendars |
| **이미지 생성** | Pillow (PIL) |
| **배포** | Docker, Docker Compose, systemd, Raspberry Pi |
| **CI/CD** | GitHub Actions (Python 3.12/3.13, Docker 빌드) |
| **테스트** | pytest, pytest-asyncio (291 tests) |

---

## 빠른 시작

### 필수 환경

- Python 3.12 이상
- 한국투자증권 Open API 발급 (App Key, App Secret)
- Telegram Bot Token 및 Chat ID

### 방법 1: Docker Compose (권장)

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 실제 키 입력

# 2. 빌드 + 백그라운드 실행
docker compose up -d --build

# 3. 실시간 로그 확인
docker compose logs -f

# 4. 중지
docker compose down
```

### 방법 2: 스크립트 실행 (Linux)

```bash
git clone https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example.git
cd KIS-API-Python-Trading-Bot-Example

# 시스템 라이브러리 설치 (Debian/Ubuntu/라즈베리파이)
sudo apt install -y libopenblas-dev

# 초기 설치 (venv 생성 + 패키지 설치)
./scripts/setup.sh

# .env 편집
vi .env

# 실행 / 중지 / 로그
./scripts/start.sh
./scripts/stop.sh
./scripts/logs.sh
```

### 방법 3: systemd 서비스 등록 (Linux, 재부팅 시 자동 실행)

```bash
sudo tee /etc/systemd/system/kis-trading-bot.service << 'EOF'
[Unit]
Description=KIS Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/project/kis-api-python
Environment="TZ=Asia/Seoul"
ExecStart=/home/pi/project/kis-api-python/venv/bin/python /home/pi/project/kis-api-python/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable kis-trading-bot   # 부팅 시 자동 시작
sudo systemctl start kis-trading-bot    # 지금 시작

# 관리
sudo systemctl status kis-trading-bot   # 상태 확인
sudo systemctl restart kis-trading-bot  # 재시작
journalctl -u kis-trading-bot -f        # 실시간 로그
```

> `User`, `WorkingDirectory`, `ExecStart` 경로는 환경에 맞게 수정하세요.

### 환경 변수 (.env)

```
TELEGRAM_TOKEN=나의_텔레그램_봇_토큰
ADMIN_CHAT_ID=나의_텔레그램_채팅방_ID숫자
APP_KEY=나의_한국투자증권_APP_KEY
APP_SECRET=나의_한국투자증권_APP_SECRET
CANO=나의_계좌번호_앞8자리
ACNT_PRDT_CD=01
```

---

## 프로젝트 구조

```
main.py                         # 진입점
trading_bot/
├── app.py                      # 부트스트래핑, 스케줄러 등록
├── config.py                   # 설정/장부/잠금 관리
├── plugin_updater.py           # 시스템 자가 업데이트 엔진
├── version_history.py          # 버전 기록
│
├── broker/                     # 외부 API 통신
│   └── kis_api.py              # KIS REST API, 토큰 관리, 호가 스캔
│
├── strategy/                   # 매매 전략 (4대 집행 모드)
│   ├── infinite.py             # 중앙 라우터 (V14-LOC/VWAP, V-REV Auto/Manual)
│   ├── v14.py                  # V14 무한매수법 LOC 플러그인
│   ├── v14_vwap.py             # V14 VWAP 타임 슬라이싱 플러그인
│   ├── reversion.py            # V-REV 역추세 엔진 (VWAP 내장)
│   ├── v_avwap.py              # AVWAP 듀얼 레퍼런싱 스나이퍼
│   ├── queue_ledger.py         # LIFO 큐 기반 비파괴 장부 (원자적 쓰기, 스레드 안전)
│   └── volatility.py           # ATR/VXN 변동성 계산
│
├── scheduler/                  # 스케줄 실행 (멀티 코어)
│   ├── core_jobs.py            # 토큰 갱신, 장부 동기화, 자정 청소, 확정 정산
│   └── trade_jobs.py           # 정규매매, 스나이퍼, VWAP 실행, 스윕 피니셔
│
├── telegram/                   # UI 계층 (4모듈 분할)
│   ├── commands.py             # 텔레그램 커맨드 라우터
│   ├── telegram_callbacks.py   # 인라인 버튼 콜백 핸들러
│   ├── telegram_states.py      # 대화 상태 머신
│   ├── telegram_sync_engine.py # 장부 동기화 엔진
│   ├── ticker_commands.py      # 티커 프로필 관리 명령어
│   └── views.py                # 메시지/이미지/GIF 렌더링
│
├── models/                     # 도메인 모델 (순수 데이터)
│   ├── order.py                # Order, OrderSide, OrderType
│   ├── holding.py              # Holding (보유현황)
│   └── trading_state.py        # ReverseState, LedgerRecord
│
└── storage/                    # 데이터 계층
    ├── file_utils.py           # 원자적 JSON/텍스트 I/O
    ├── ledger_store.py         # 장부 CRUD + 보유현황 계산
    ├── lock_manager.py         # 매매 잠금 + 에스크로
    ├── ticker_profiles.py      # 티커 프로필 관리
    └── trading_config.py       # 종목별 설정 관리

tests/                          # 테스트 (291개)
docs/                           # 기술 문서
```

---

## 텔레그램 명령어

### 조회

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/start` | 봇 시작 | 운영 스케줄, 명령어 목록, 서머타임 자동 감지 |
| `/sync` | 통합 지시서 | 실시간 KIS + 야후 시세 기반 매매 전략 브리핑. 인라인 버튼 수동 주문 |
| `/record` | 장부 동기화 | TrueSync 비파괴 보정(CALIB). 졸업 자동 감지 → 명예의 전당 |
| `/history` | 졸업 명예의 전당 | 과거 매매 사이클 수익 기록. GIF 졸업 카드 발급 |
| `/version` | 버전 내역 | 코드 업데이트 히스토리 페이징 조회 |

### 설정

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/settlement` | 분할/복리/버전 설정 | 분할 수, 목표 수익률, 복리율, 수수료율, V14/V-REV 전환 |
| `/seed` | 시드머니 관리 | 종목별 운용 시드 금액 조절 (+$100/-$100/직접 입력) |
| `/ticker` | 운용 종목 선택 | 토글 버튼으로 다중 종목 선택/해제 |
| `/mode` | 스나이퍼 ON/OFF | 종목별 상방 익절 스나이퍼 활성화/비활성화 |

### 긴급

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/reset` | 비상 해제 | 매매 잠금 해제, 리버스 탈출, 장부 삼위일체 소각 |
| `/add_q` | V-REV 큐 수동 추가 | 양식: `/add_q SOXL 2026-04-06 20 52.16` |

### 티커 프로필 관리

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/ticker_add` | 신규 티커 등록 | `/ticker_add UPRO SPY -18 1.2` (yfinance 실존 검증) |
| `/ticker_remove` | 티커 프로필 삭제 | `/ticker_remove UPRO` |
| `/ticker_list` | 등록된 티커 목록 | 기초자산, 리버스 탈출, 트레일링 스탑 정보 |

---

## 테스트

```bash
# 전체 테스트 실행 (291개)
python -m pytest tests/ -v

# 특정 모듈만
python -m pytest tests/test_strategy.py -v
python -m pytest tests/test_queue_ledger_core.py -v
```

---

## 문서

- [KST 타임존 영구 고정 가이드](docs/kst-timezone-fix.md) -- 클라우드 서버 시간대 리셋 문제 해결
- [트레이딩 시스템 사양서](docs/trading-system-spec.md) -- 매매 로직 상세 명세 (V26.02)
- [VWAP 알고리즘 연구](docs/vwap-research.md) -- 시장 미시구조 심층 분석

---

## 관련 링크

- [라오어 무한매수법 네이버 카페](https://cafe.naver.com/infinitebuying)
- [한국투자증권 Open API](https://apiportal.koreainvestment.com/)
