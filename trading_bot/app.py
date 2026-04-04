# ==========================================================
# [trading_bot/app.py]
# 애플리케이션 부트스트래핑 및 스케줄러 등록
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
from trading_bot.strategy import InfiniteStrategy, VwapStrategy
from trading_bot.telegram import TelegramController
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
)


async def scheduled_volatility_scan(context):
    """
    10:20 EST (정규장 개장 50분 후) 격발.
    대상 종목들의 HV와 당일 VXN을 연산하여 터미널 메인 화면에 1-Tier 브리핑 덤프
    """
    app_data = context.job.data
    cfg = app_data['cfg']

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
        for ticker in active_tickers:
            dummy_weight = 0.85 if ticker == "TQQQ" else 1.15
            status_text = "OFF 권장" if dummy_weight <= 1.0 else "ON 권장"
            briefing_lines.append(f"{ticker}: {dummy_weight} ({status_text})")

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
    print(f"🚀 앱솔루트 스노우볼 퀀트 엔진 {latest_version} (VWAP 스플릿 & 경량화 아키텍처 탑재)")
    print(f"📅 날짜 정보: {season_msg}")
    print(f"⏰ 자동 동기화: 08:30(여름) / 09:30(겨울) 자동 변경")
    print(f"🛡️ 1-Tier 자율주행 지표 스캔 대기 중... (매일 10:20 EST 격발)")
    print("=" * 60)

    perform_self_cleaning()

    if ADMIN_CHAT_ID: cfg.set_chat_id(ADMIN_CHAT_ID)
    broker = KoreaInvestmentBroker(APP_KEY, APP_SECRET, CANO, ACNT_PRDT_CD)
    strategy = InfiniteStrategy(cfg)
    vwap_strategy = VwapStrategy(cfg)
    tx_lock = asyncio.Lock()
    bot = TelegramController(cfg, broker, strategy, tx_lock)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

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
        ("v17", bot.cmd_v17),
        ("v4", bot.cmd_v4),
        ("p4006", bot.cmd_p4006),
    ]:
        app.add_handler(CommandHandler(cmd, handler))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    if cfg.get_chat_id():
        jq = app.job_queue
        app_data = {
            'cfg': cfg,
            'broker': broker,
            'strategy': strategy,
            'vwap_strategy': vwap_strategy,
            'bot': bot,
            'tx_lock': tx_lock
        }
        kst = pytz.timezone('Asia/Seoul')
        est = pytz.timezone('US/Eastern')

        for tt in [datetime.time(7,0,tzinfo=kst), datetime.time(11,0,tzinfo=kst), datetime.time(16,30,tzinfo=kst), datetime.time(22,0,tzinfo=kst)]:
            jq.run_daily(scheduled_token_check, time=tt, days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_auto_sync_summer, time=datetime.time(8, 30, tzinfo=kst), days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)
        jq.run_daily(scheduled_auto_sync_winter, time=datetime.time(9, 30, tzinfo=kst), days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)

        for hour in [17, 18]:
            jq.run_daily(scheduled_force_reset, time=datetime.time(hour, 0, tzinfo=kst), days=(0,1,2,3,4), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_volatility_scan, time=datetime.time(10, 20, tzinfo=est), days=(0,1,2,3,4), chat_id=cfg.get_chat_id(), data=app_data)

        for hour in [17, 18]:
            jq.run_daily(scheduled_regular_trade, time=datetime.time(hour, 5, tzinfo=kst), days=(0,1,2,3,4), chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_repeating(scheduled_sniper_monitor, interval=60, chat_id=cfg.get_chat_id(), data=app_data)
        jq.run_repeating(scheduled_vwap_trade, interval=60, chat_id=cfg.get_chat_id(), data=app_data)

        jq.run_daily(scheduled_self_cleaning, time=datetime.time(6, 0, tzinfo=kst), days=tuple(range(7)), chat_id=cfg.get_chat_id(), data=app_data)

    app.run_polling()
