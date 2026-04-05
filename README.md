# KIS-API-Python-Trading-Bot-Example

[![CI](https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example/actions/workflows/ci.yml/badge.svg)](https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/aaron-jang/c51777029ca0a51c869a27ed671e9dfd/raw/test-results.json)
![Version](https://img.shields.io/badge/version-V23.14-orange)
![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-lightgrey)

> KIS Open API 기반 미국 주식 자동매매 봇 (V23.14 VWAP 자율주행 에디션)

한국투자증권(KIS) Open API를 활용하여 미국 주식 자동매매 시스템을 구축해보는 파이썬 예제 코드입니다. 증권사 API 통신, 스케줄러 자동화, 텔레그램 봇 제어 등을 학습하기 위한 기술적 레퍼런스로 작성되었습니다.

---

## 저작권 및 게시 중단(Take-down) 정책

- 본 코드에 구현된 매매 로직(무한매수법)의 모든 아이디어와 저작권, 지적재산권은 원작자인 **'라오어'**님에게 있습니다.
- 본 저장소는 순수하게 파이썬과 API를 공부하기 위한 기술적 예제일 뿐이며, 원작자의 공식적인 승인이나 검수를 받은 프로그램이 아닙니다.
- 만약 원작자(라오어님)께서 본 코드의 공유를 원치 않으시거나 삭제를 요청하실 경우, 본 저장소는 어떠한 사전 예고 없이 즉각적으로 삭제(또는 비공개 처리)될 수 있음을 명확히 밝힙니다.

## 면책 조항 (Disclaimer)

- 이 코드는 한국투자증권 Open API의 기능과 파이썬 자동화 로직을 학습하기 위해 작성된 **교육 및 테스트 목적의 순수 예제 코드**입니다.
- 특정 투자 전략이나 종목을 추천하거나 투자를 권유하는 목적이 **절대 아닙니다**.
- 본 코드를 실제 투자에 적용하여 발생하는 모든 금전적 손실 및 시스템 오류에 대한 법적, 도의적 책임은 **전적으로 코드를 실행한 사용자 본인**에게 있습니다.
- 본 코드는 어떠한 형태의 수익도 보장하지 않으므로, 반드시 충분한 모의 테스트 후 본인의 책임하에 사용하시기 바랍니다.

---

## 주요 기술적 특징

| 기능 | 설명 |
|------|------|
| **VWAP 자율주행 엔진** | 장 마감 30분 전 U-Curve 유동성 프로파일을 추종하여 예산/수량을 1분 단위로 분할. 실시간 1호가(Bid/Ask) 스캔 후 지정가 즉결 체결 |
| **공수 분리 & 타점 방어막** | 12% 잭팟 등 상방 익절 텐트 보존, LOC 덫만 핀셋 철거. 매수 시 Ceiling, 매도 시 Floor 락인으로 고점 불타기/저점 손절 차단 |
| **멀티 코어 스케줄러** | 시스템 관리(core_jobs)와 실전 매매(trade_jobs)를 분리하여 SRP 준수 |
| **텔레그램 스마트 UI** | 모바일에서 인라인 버튼으로 장부 조회, 퀀트 엔진 스위칭 |
| **TrueSync 장부 동기화** | NYSE 영업일 자동 인식, API 체결 내역으로 가상 장부와 실제 잔고 오차 동기화 |
| **KIS API 토큰 관리** | OAuth2 토큰 로컬 캐싱, 만료 전 자동 갱신(Self-Healing), 원자적 쓰기(fsync) |

---

## 필수 환경

- Python 3.12 이상
- 한국투자증권 Open API 발급 (App Key, App Secret)
- Telegram Bot Token 및 Chat ID

---

## 설치 및 실행

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

### 방법 2: 직접 실행

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 실제 키 입력

# 3. 실행
python main.py

# (서버 백그라운드 실행)
nohup python main.py &
```

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
main.py                         # 진입점 (3줄)
trading_bot/
├── app.py                      # 부트스트래핑, 스케줄러 등록
├── config.py                   # 설정 Facade (storage 계층에 위임)
├── version_history.py          # 버전 기록
│
├── broker/                     # 외부 API 통신
│   └── kis_api.py              # KIS REST API, 토큰 관리, 호가 스캔
│
├── strategy/                   # 매매 전략 (순수 로직)
│   ├── infinite.py             # 무한매수법 알고리즘
│   ├── vwap.py                 # VWAP 타임 슬라이싱 엔진
│   └── volatility.py           # ATR/VXN 변동성 계산
│
├── scheduler/                  # 스케줄 실행
│   ├── core_jobs.py            # 토큰 갱신, 장부 동기화, 자정 청소
│   └── trade_jobs.py           # 정규매매, 스나이퍼, VWAP 실행
│
├── telegram/                   # UI 계층
│   ├── commands.py             # 텔레그램 커맨드 라우터
│   └── views.py                # 메시지/이미지 렌더링
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
    └── trading_config.py       # 종목별 설정 관리

tests/                          # 테스트 (217개)
docs/                           # 문서
```

---

## 텔레그램 명령어

| 명령어 | 기능 |
|--------|------|
| `/start` | 봇 시작 및 운영 스케줄 표시 |
| `/sync` | 통합 지시서 조회 |
| `/record` | 장부 동기화 및 조회 |
| `/history` | 졸업 명예의 전당 |
| `/settlement` | 분할/복리/액면 설정 |
| `/seed` | 개별 시드머니 관리 |
| `/ticker` | 운용 종목 선택 |
| `/mode` | 상방 스나이퍼 ON/OFF |
| `/version` | 버전 및 업데이트 내역 |
| `/reset` | 비상 해제 메뉴 (락/리버스) |

---

## 테스트

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# 특정 모듈만
python -m pytest tests/test_strategy.py -v
```

---

## 문서

- [KST 타임존 영구 고정 가이드](docs/kst-timezone-fix.md) — 클라우드 서버 시간대 리셋 문제 해결
- [트레이딩 시스템 사양서](docs/trading-system-spec.md) — V23.14 매매 로직 상세 명세
- [VWAP 알고리즘 연구](docs/vwap-research.md) — 시장 미시구조 심층 분석
