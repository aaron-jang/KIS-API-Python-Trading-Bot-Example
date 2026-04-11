"""
티커 프로필 관리 텔레그램 명령어

upstream의 commands.py를 건드리지 않고 독립 모듈로 작성하여
upstream 머지 시 충돌을 방지합니다.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from trading_bot.storage import ticker_profiles as tp

logger = logging.getLogger(__name__)


def register(app, bot):
    """
    app.add_handler()로 등록할 수 있는 핸들러를 app에 추가.

    사용법:
        from trading_bot.telegram.ticker_commands import register
        register(app, bot)
    """
    from telegram.ext import CommandHandler

    app.add_handler(CommandHandler("ticker_add", _make_ticker_add(bot)))
    app.add_handler(CommandHandler("ticker_remove", _make_ticker_remove(bot)))
    app.add_handler(CommandHandler("ticker_list", _make_ticker_list(bot)))
    app.add_handler(CommandHandler("ticker_use", _make_ticker_use(bot)))


def _make_ticker_add(bot):
    async def cmd_ticker_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not bot._is_admin(update):
            return

        args = context.args
        if len(args) != 4:
            await update.message.reply_text(
                "❌ <b>양식 오류</b>\n\n"
                "사용법:\n"
                "<code>/ticker_add TICKER BASE REVERSE_EXIT TRAILING_STOP</code>\n\n"
                "예시:\n"
                "<code>/ticker_add UPRO SPY -18 1.2</code>\n\n"
                "▫️ TICKER: 매매할 ETF 티커 (예: UPRO)\n"
                "▫️ BASE: 기초자산 티커 (예: SPY)\n"
                "▫️ REVERSE_EXIT: 리버스 탈출 수익률 % (예: -18)\n"
                "▫️ TRAILING_STOP: 상방 트레일링 스탑 % (예: 1.2)",
                parse_mode='HTML'
            )
            return

        ticker, base_ticker, reverse_exit_str, trailing_stop_str = args
        ticker = ticker.upper()
        base_ticker = base_ticker.upper()

        try:
            reverse_exit = float(reverse_exit_str)
            trailing_stop = float(trailing_stop_str)
        except ValueError:
            await update.message.reply_text(
                "❌ REVERSE_EXIT과 TRAILING_STOP은 숫자여야 합니다."
            )
            return

        await update.message.reply_text(
            f"⏳ <b>{ticker}</b> ({base_ticker}) yfinance 실존 검증 중...",
            parse_mode='HTML'
        )

        import asyncio
        success, msg = await asyncio.to_thread(
            tp.add_ticker, ticker, base_ticker, reverse_exit, trailing_stop, True
        )

        if success:
            result = (
                f"✅ <b>{ticker} 등록 완료</b>\n\n"
                f"▫️ 기초자산: <b>{base_ticker}</b>\n"
                f"▫️ 리버스 탈출: <b>{reverse_exit}%</b>\n"
                f"▫️ 트레일링 스탑: <b>{trailing_stop}%</b>\n\n"
                f"💡 <code>/ticker</code> 메뉴에서 운용 종목으로 활성화하세요.\n"
                f"💡 <code>/seed</code>, <code>/settlement</code>에서 추가 설정 가능합니다."
            )
        else:
            result = msg

        await update.message.reply_text(result, parse_mode='HTML')

    return cmd_ticker_add


def _make_ticker_remove(bot):
    async def cmd_ticker_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not bot._is_admin(update):
            return

        args = context.args
        if len(args) != 1:
            await update.message.reply_text(
                "❌ 사용법: <code>/ticker_remove TICKER</code>\n"
                "예시: <code>/ticker_remove UPRO</code>",
                parse_mode='HTML'
            )
            return

        ticker = args[0].upper()
        if tp.remove_ticker(ticker):
            await update.message.reply_text(
                f"✅ <b>{ticker}</b> 프로필 삭제 완료\n\n"
                f"⚠️ <code>/ticker</code> 활성 종목 목록에서도 제거하세요.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ <b>{ticker}</b>는 등록되지 않은 티커입니다.",
                parse_mode='HTML'
            )

    return cmd_ticker_remove


def _make_ticker_list(bot):
    async def cmd_ticker_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not bot._is_admin(update):
            return

        tickers = tp.list_tickers()
        if not tickers:
            await update.message.reply_text("📋 등록된 티커가 없습니다.")
            return

        active = bot.cfg.get_active_tickers()

        lines = ["📋 <b>[ 등록된 티커 프로필 ]</b>\n"]
        for t in sorted(tickers):
            profile = tp.get_profile(t)
            marker = "✅" if t in active else "⬜"
            lines.append(
                f"{marker} <b>{t}</b> → {profile['base_ticker']}\n"
                f"    리버스 탈출: {profile['reverse_exit']}% / "
                f"트레일링 스탑: {profile['trailing_stop']}%"
            )

        lines.append("\n💡 운용 종목 변경: <code>/ticker_use TICKER1 TICKER2 ...</code>")
        lines.append("   예: <code>/ticker_use SOXL TQQQ UPRO</code>")

        await update.message.reply_text("\n".join(lines), parse_mode='HTML')

    return cmd_ticker_list


def _make_ticker_use(bot):
    async def cmd_ticker_use(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not bot._is_admin(update):
            return

        args = context.args
        if not args:
            active = bot.cfg.get_active_tickers()
            await update.message.reply_text(
                f"📌 <b>현재 운용 종목:</b> {', '.join(active) if active else '(없음)'}\n\n"
                f"사용법:\n"
                f"<code>/ticker_use TICKER1 [TICKER2 ...]</code>\n\n"
                f"예시:\n"
                f"<code>/ticker_use SOXL</code>\n"
                f"<code>/ticker_use SOXL TQQQ</code>\n"
                f"<code>/ticker_use UPRO</code>",
                parse_mode='HTML'
            )
            return

        new_tickers = [t.upper() for t in args]

        # 모든 티커가 프로필에 등록되어 있는지 확인
        registered = set(tp.list_tickers())
        unknown = [t for t in new_tickers if t not in registered]
        if unknown:
            await update.message.reply_text(
                f"❌ 다음 티커는 프로필에 등록되지 않았습니다: <b>{', '.join(unknown)}</b>\n\n"
                f"먼저 <code>/ticker_add</code>로 등록하세요.",
                parse_mode='HTML'
            )
            return

        bot.cfg.set_active_tickers(new_tickers)
        await update.message.reply_text(
            f"✅ <b>운용 종목 변경 완료</b>\n\n"
            f"▫️ 활성 종목: <b>{', '.join(new_tickers)}</b>\n\n"
            f"💡 <code>/sync</code>로 확인하세요.",
            parse_mode='HTML'
        )

    return cmd_ticker_use
