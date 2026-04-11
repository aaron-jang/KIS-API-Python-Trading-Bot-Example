# ==========================================================
# [trading_bot/app.py]
# 애플리케이션 부트스트래핑 및 스케줄러 등록
# 💡 [V24.20] 듀얼 레퍼런싱(SOXX/SOXL) 인프라 및 스냅샷 파이프라인 증설
# ==========================================================

import os
import logging
import datetime
import pytz
import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv

from trading_bot.config import ConfigManager
from trading_bot.broker import KoreaInvestmentBroker
from trading_bot.strategy import InfiniteStrategy
from trading_bot.telegram import TelegramController

from trading_bot.strategy.queue_ledger import QueueLedger
from trading_bot.strategy.reversion import ReversionStrategy
from trading_bot.strategy.volatility import VolatilityEngine

from trading_bot.scheduler.core_jobs import (
    scheduled_token_check,
    scheduled_auto_sync_summer,
    scheduled_auto_sync_winter,
    scheduled_force_reset,
    scheduled_self_cleaning,
    get_target_hour,
    perform_self_cleaning,
)
from trading_bot.scheduler.trade_jobs import (
    scheduled_regular_trade,
    scheduled_sniper_monitor,
    scheduled_vwap_trade,
    scheduled_vwap_init_and_cancel,
    scheduled_after_market_lottery,
)

# 듀얼 레퍼런싱: 기초자산(Base) ↔ 파생상품(Exec) 1:1 매핑
# data/ticker_profiles.json에서 동적 로드 (사용자 등록 가능)
from trading_bot.storage import ticker_profiles as _ticker_profiles


def get_ticker_base_map():
    """런타임에 최신 프로필을 읽어 base_map 반환"""
    return _ticker_profiles.get_base_map()


async def scheduled_volatility_scan(context):
    """
    10:20 EST (정규장 개장 50분 후) 격발.
    기초자산 기준으로 변동성 지표를 계산하여 브리핑.
    """
    app_data = context.job.data
    cfg = app_data['cfg']
    base_map = app_data.get('base_map') or get_ticker_base_map()

    print("\n" + "=" * 60)
    print("📈 [자율주행 변동성 스캔 완료] (10:20 EST 스냅샷)")

    active_tickers = []
    for r in cfg.get_ledger():
        t = r.get('ticker')
        if t and t not in active_tickers:
            active_tickers.append(t)

    if not active_tickers:
        print("📊 현재 운용 중인 종목이 없습니다.")
    else:
        briefing_lines = []
        vol_engine = VolatilityEngine()

        for ticker in active_tickers:
            target_base = base_map.get(ticker, ticker)
            try:
                weight_data = await asyncio.to_thread(vol_engine.calculate_weight, target_base)
                real_weight = float(weight_data.get('weight', 1.0) if isinstance(weight_data, dict) else weight_data)
            except Exception as e:
                logging.warning(f"[{ticker}] 변동성 지표 산출 실패. 폴백 적용: {e}")
                real_weight = 0.85 if ticker == "TQQQ" else 1.15

            status_text = "OFF 권장" if real_weight <= 1.0 else "ON 권장"
            if ticker != target_base:
                briefing_lines.append(f"{ticker}({target_base}): {real_weight:.2f} ({status_text})")
            else:
                briefing_lines.append(f"{ticker}: {real_weight:.2f} ({status_text})")

        print(f"📊 [자율주행 지표] {' | '.join(briefing_lines)} (상세 게이지: /mode)")
    print("=" * 60 + "\n")


def run():
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists('logs'):
        os.makedirs('logs')

    load_dotenv()

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    try:
        ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None
    except ValueError:
        ADMIN_CHAT_ID = None

    APP_KEY = os.getenv("APP_KEY")
    APP_SECRET = os.getenv("APP_SECRET")
    CANO = os.getenv("CANO")
    ACNT_PRDT_CD = os.getenv("ACNT_PRDT_CD", "01")

    if not all([TELEGRAM_TOKEN, APP_KEY, APP_SECRET, CANO]):
        print("❌ [치명적 오류] .env 파일에 봇 구동 필수 키(TELEGRAM_TOKEN, APP_KEY, APP_SECRET, CANO)가 누락되었습니다. 봇을 종료합니다.")
        exit(1)

    log_filename = f"logs/bot_app_{datetime.datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    TARGET_HOUR, season_msg = get_target_hour()

    cfg = ConfigManager()
    latest_version = cfg.get_latest_version()

    print("=" * 60)
    print(f"🚀 앱솔루트 스노우볼 퀀트 엔진 {latest_version} (초경량 2대 코어 아키텍처 탑재)")
    print(f"📅 날짜 정보: {season_msg}")
    print(f"⏰ 자동 동기화: 08:30(여름) / 09:30(겨울) 자동 변경")
    print(f"🛡️ 1-Tier 자율주행 지표 스캔 대기 중... (매일 10:20 EST 격발)")
    print("=" * 60)

    perform_self_cleaning()

    if ADMIN_CHAT_ID: cfg.set_chat_id(ADMIN_CHAT_ID)

    broker = KoreaInvestmentBroker(APP_KEY, APP_SECRET, CANO, ACNT_PRDT_CD)
    strategy = InfiniteStrategy(cfg)

    queue_ledger = QueueLedger()
    strategy_rev = ReversionStrategy()

    tx_lock = asyncio.Lock()

    bot = TelegramController(
        cfg, broker, strategy, tx_lock,
        queue_ledger=queue_ledger,
        strategy_rev=strategy_rev
    )

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .connect_timeout(30.0)
        .pool_timeout(30.0)
        .connection_pool_size(512)
        .build()
    )
    app.job_queue.scheduler.configure(job_defaults={'misfire_grace_time': 120})

    # 텔레그램 타임아웃/네트워크 에러 핸들러
    async def error_handler(update, context):
        import telegram.error
        if isinstance(context.error, (telegram.error.TimedOut, telegram.error.NetworkError)):
            logging.warning(f"텔레그램 네트워크 에러 (자동 복구 대기): {context.error}")
        else:
            logging.error(f"처리되지 않은 에러: {context.error}")
    app.add_error_handler(error_handler)

    for cmd, handler in [
        ("start", bot.cmd_start),
        ("record", bot.cmd_record),
        ("history", bot.cmd_history),
        ("sync", bot.cmd_sync),
        ("settlement", bot.cmd_settlement),
        ("seed", bot.cmd_seed),
        ("ticker", bot.cmd_ticker),
        ("mode", bot.cmd_mode),
        ("reset", bot.cmd_reset),
        ("version", bot.cmd_version),
    ]:
        app.add_handler(CommandHandler(cmd, handler))

    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # 티커 프로필 관리 명령어 (독립 모듈, upstream 충돌 방지)
    from trading_bot.telegram.ticker_commands import register as register_ticker_cmds
    register_ticker_cmds(app, bot)

    # 텔레그램 / 입력 시 자동완성 메뉴 등록
    async def post_init(application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("start", "봇 시작 및 운영 스케줄 표시"),
            BotCommand("sync", "통합 지시서 조회"),
            BotCommand("record", "장부 동기화 및 조회"),
            BotCommand("history", "졸업 명예의 전당"),
            BotCommand("settlement", "분할/복리/액면 설정"),
            BotCommand("seed", "개별 시드머니 관리"),
            BotCommand("ticker", "운용 종목 선택"),
            BotCommand("mode", "상방 스나이퍼 ON/OFF"),
            BotCommand("version", "버전 및 업데이트 내역"),
            BotCommand("reset", "비상 해제 메뉴"),
            BotCommand("add_q", "V-REV 큐 수동 추가"),
            BotCommand("ticker_add", "신규 티커 프로필 등록"),
            BotCommand("ticker_remove", "티커 프로필 삭제"),
            BotCommand("ticker_list", "등록된 티커 프로필 목록"),
        ])
    app.post_init = post_init

    if cfg.get_chat_id():
        jq = app.job_queue
        app_data = {
            'cfg': cfg,
            'broker': broker,
            'strategy': strategy,
            'queue_ledger': queue_ledger,
            'strategy_rev': strategy_rev,
            'bot': bot,
            'tx_lock': tx_lock,
            'base_map': get_ticker_base_map(),
        }
        est = pytz.timezone('US/Eastern')

        # 1. 시스템 관리 스케줄러 — EST 기준 통일
        for tt in [datetime.time(18,0,tzinfo=est), datetime.time(22,0,tzinfo=est), datetime.time(3,30,tzinfo=est), datetime.time(9,0,tzinfo=est)]:
            jq.run_daily(scheduled_token_check, time=tt, days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_auto_sync_summer, time=datetime.time(19, 30, tzinfo=est), days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)
        jq.run_daily(scheduled_auto_sync_winter, time=datetime.time(19, 30, tzinfo=est), days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_force_reset, time=datetime.time(4, 0, tzinfo=est), days=(1,2,3,4,5), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_volatility_scan, time=datetime.time(10, 20, tzinfo=est), days=(1,2,3,4,5), chat_id=cfg.get_chat_id(), data=app_data)

        # 2. 실전 전투 매매 스케줄러
        jq.run_daily(scheduled_regular_trade, time=datetime.time(4, 5, tzinfo=est), days=(1,2,3,4,5), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_vwap_init_and_cancel, time=datetime.time(15, 30, tzinfo=est), days=(1,2,3,4,5), chat_id=cfg.get_chat_id(), data=app_data)

        # 스나이퍼 감시 및 V-REV 슬라이싱 (cron, 서로 20초 간격 분산)
        jq.run_custom(scheduled_sniper_monitor, job_kwargs={"trigger": "cron", "second": "20"},
                       chat_id=cfg.get_chat_id(), data=app_data)
        jq.run_custom(scheduled_vwap_trade, job_kwargs={"trigger": "cron", "second": "40"},
                       chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_after_market_lottery, time=datetime.time(16, 5, tzinfo=est), days=(1,2,3,4,5), chat_id=cfg.get_chat_id(), data=app_data)

        # 3. 자정 청소
        jq.run_daily(scheduled_self_cleaning, time=datetime.time(17, 0, tzinfo=est), days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)

    app.run_polling()
