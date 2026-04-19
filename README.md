# KIS-API-Python-Trading-Bot-Example

[![CI](https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example/actions/workflows/ci.yml/badge.svg)](https://github.com/aaron-jang/KIS-API-Python-Trading-Bot-Example/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/aaron-jang/c51777029ca0a51c869a27ed671e9dfd/raw/test-results.json)
![Version](https://img.shields.io/badge/version-V28.27-orange)
![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-lightgrey)

> KIS Open API 기반 미국 주식 자동매매 봇 (V28.22 4대 집행 모드 통합 에디션)

한국투자증권(KIS) Open API를 활용하여 미국 주식 자동매매 시스템을 구축해보는 파이썬 예제 코드입니다. 증권사 API 통신, 스케줄러 자동화, 텔레그램 봇 제어 등을 학습하기 위한 기술적 레퍼런스로 작성되었습니다.

---

## 목차

- [저작권 및 게시 중단 정책](#저작권-및-게시-중단take-down-정책)
- [면책 조항](#면책-조항-disclaimer)
- [주요 기술적 특징](#주요-기술적-특징)
- [필수 환경](#필수-환경)
- [설치 및 실행](#설치-및-실행)
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
| **2대 코어 아키텍처** | V14(순수 공격) + V-REV(역추세 방어, VWAP 내장) 2개 엔진만으로 구성된 초경량 플러그인 구조 |
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
main.py                         # 진입점 (3줄)
trading_bot/
├── app.py                      # 부트스트래핑, 스케줄러 등록
├── config.py                   # 설정/장부/잠금 관리
├── version_history.py          # 버전 기록
│
├── broker/                     # 외부 API 통신
│   └── kis_api.py              # KIS REST API, 토큰 관리, 호가 스캔
│
├── strategy/                   # 매매 전략 (2대 코어 + AVWAP 하이브리드)
│   ├── infinite.py             # 중앙 라우터 (V14/V-REV 분기)
│   ├── v14.py                  # V14 무한매수법 플러그인
│   ├── reversion.py            # V-REV 역추세 엔진 (VWAP 내장)
│   ├── v_avwap.py              # AVWAP 듀얼 레퍼런싱 스나이퍼
│   ├── queue_ledger.py         # LIFO 큐 기반 비파괴 장부
│   └── volatility.py           # ATR/VXN 변동성 계산
│
├── scheduler/                  # 스케줄 실행
│   ├── core_jobs.py            # 토큰 갱신, 장부 동기화, 자정 청소
│   └── trade_jobs.py           # 정규매매, 스나이퍼, VWAP 실행
│
├── telegram/                   # UI 계층
│   ├── commands.py             # 텔레그램 커맨드 라우터
│   ├── ticker_commands.py      # 티커 프로필 관리 명령어
│   └���─ views.py                # 메시지/이미지 렌더링
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
    ├── ticker_profiles.py      # 티커 프로필 관리 (등록/삭제/조회)
    └── trading_config.py       # 종목별 설정 관리

tests/                          # 테스트 (197개)
docs/                           # 문서
```

---

## 텔레그램 명령어

### 조회

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/start` | 봇 시작 | - 운영 스케줄(토큰 갱신, 동기화, 주문 시각) 표시<br>- 주요 명령어 목록 안내<br>- 서머타임/겨울시간 자동 감지 정보 |
| `/sync` | 통합 지시서 | - 실시간 KIS API + 야후 시세 기반 매매 전략 브리핑<br>- 종목별 T값, 별값, 1회분 예산, 스나이퍼 타격선 표시<br>- 현재 보유 수량, 평단가, 손익률 실시간 계산<br>- 인라인 버튼으로 수동 주문 즉시 실행 가능<br>- 외화 RP 권장 금액 자동 산출 |
| `/record` | 장부 동기화 | - KIS API 실잔고와 가상 장부를 비교하여 자동 보정 (TrueSync)<br>- 수량/평단가 오차 감지 시 비파괴 보정(CALIB) 자동 적용<br>- 보유 종목별 거래 내역 대시보드 렌더링<br>- 졸업(전량 매도) 자동 감지 → 명예의 전당 박제 + 자동 복리 |
| `/history` | 졸업 명예의 전당 | - 과거 완료된 매매 사이클(졸업) 기록 조회<br>- 졸업별 수익금, 수익률, 투자금, 매도금 상세 확인<br>- 인라인 버튼으로 개별 졸업 거래 내역 펼치기<br>- 수익 리포트 이미지(배경 이미지 포함) 자동 생성 |
| `/version` | 버전 내역 | - 코드 업데이트 히스토리를 5개씩 페이징하여 조회<br>- 인라인 버튼으로 이전/다음 페이지 탐색 |

### 설정

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/settlement` | 분할/복리/버전 설정 | - 종목별 분할 수 변경 (20/40/60)<br>- 목표 수익률(%) 설정 (SOXL 12%, TQQQ 10% 등)<br>- 복리율(%) 조절 (졸업 수익의 몇 %를 시드에 재투자)<br>- 매매 엔진 버전 전환 (V14 ↔ V_REV)<br>- 실시간 변동성 지표(HV/VXN) 연산 결과 표시 |
| `/seed` | 시드머니 관리 | - 종목별 운용 시드머니 금액 조절<br>- 추가(+$100), 감소(-$100), 고정(직접 입력) 3가지 방식<br>- 현재 설정된 시드 금액 실시간 표시 |
| `/ticker` | 운용 종목 선택 | - 프로필에 등록된 모든 티커를 토글 버튼으로 다중 선택<br>- ✅/⬜ 클릭으로 선택/해제, ✔️ 확정으로 저장<br>- 기존 활성 종목을 초기 선택 상태로 로드 |
| `/mode` | 스나이퍼 ON/OFF | - 종목별 상방 익절 스나이퍼 기능을 개별적으로 활성화/비활성화<br>- 현재 ON/OFF 상태 표시 |

### 긴급

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/reset` | 비상 해제 | - 매매 잠금(REG/SNIPER) 강제 해제<br>- 리버스 모드 강제 탈출<br>- 장부 초기화 (본장부 + 에스크로 + 큐 삼위일체 소각)<br>- 인라인 버튼으로 종목 선택 → 확인 단계 필요 (오작동 방지) |
| `/add_q` | V-REV 큐 수동 추가 | - V-REV 엔진의 LIFO 큐에 수동으로 매수 기록 추가<br>- 양식: `/add_q SOXL 2026-04-06 20 52.16`<br>- 기존 보유분을 V-REV 큐에 수동 등록할 때 사용 |

### 티커 프로필 관리 (신규 종목 등록)

| 명령어 | 기능 | 상세 |
|--------|------|------|
| `/ticker_add` | 신규 티커 등록 | - 양식: `/ticker_add TICKER BASE REVERSE_EXIT TRAILING_STOP`<br>- 예시: `/ticker_add UPRO SPY -18 1.2`<br>- yfinance로 티커/기초자산 실존 검증<br>- 기초자산 매핑, 리버스 탈출 수익률(%), 트레일링 스탑(%) 설정<br>- 시드/분할/목표는 `/seed`, `/settlement`로 별도 설정 |
| `/ticker_remove` | 티커 프로필 삭제 | - 양식: `/ticker_remove TICKER`<br>- 예시: `/ticker_remove UPRO` |
| `/ticker_list` | 등록된 티커 목록 | - 현재 프로필에 등록된 모든 티커 표시<br>- 활성 종목은 ✅로 표시<br>- 기초자산, 리버스 탈출, 트레일링 스탑 정보 포함 |

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
- [트레이딩 시스템 사양서](docs/trading-system-spec.md) — 매매 로직 상세 명세
- [VWAP 알고리즘 연구](docs/vwap-research.md) — 시장 미시구조 심층 분석
