"""
티커 프로필 관리 텔레그램 명령어

upstream의 commands.py를 건드리지 않고 독립 모듈로 작성하여
upstream 머지 시 충돌을 방지합니다.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from trading_bot.storage import ticker_profiles as tp

logger = logging.getLogger(__name__)

# 채팅방별 토글 선택 임시 상태 저장소
# { chat_id: set[str] } — 현재 선택된 티커 집합
_toggle_state: dict[int, set] = {}


def register(app, bot):
    """app에 핸들러 등록"""
    from telegram.ext import CommandHandler, CallbackQueryHandler

    app.add_handler(CommandHandler("ticker_add", _make_ticker_add(bot)))
    app.add_handler(CommandHandler("ticker_remove", _make_ticker_remove(bot)))
    app.add_handler(CommandHandler("ticker_list", _make_ticker_list(bot)))
    app.add_handler(CommandHandler("ticker", _make_ticker_menu(bot)))

    # TSEL: 접두사 콜백 핸들러를 group=-1로 등록하여 upstream의 generic
    # CallbackQueryHandler(모든 콜백 캐치)보다 먼저 실행되도록 함
    app.add_handler(
        CallbackQueryHandler(_make_ticker_callback(bot), pattern=r"^TSEL:"),
        group=-1
    )


# ==========================================================
# /ticker — 토글 기반 다중 선택 메뉴
# ==========================================================
def _build_menu(selected: set, profiled: list) -> tuple:
    """
    토글 메뉴 메시지와 InlineKeyboard 생성.

    Args:
        selected: 현재 선택된 티커 집합
        profiled: 프로필에 등록된 모든 티커 리스트

    Returns:
        (message_text, InlineKeyboardMarkup)
    """
    lines = ["📋 <b>[ 운용 종목 선택 ]</b>\n"]
    lines.append("각 티커를 눌러서 선택/해제한 후 <b>✔️ 확정</b>을 누르세요.\n")

    if selected:
        lines.append(f"🎯 <b>선택됨:</b> {', '.join(sorted(selected))}")
    else:
        lines.append("⚠️ <b>선택된 종목이 없습니다</b>")

    keyboard = []
    for t in profiled:
        profile = tp.get_profile(t)
        marker = "✅" if t in selected else "⬜"
        keyboard.append([InlineKeyboardButton(
            f"{marker} {t} ({profile['base_ticker']})",
            callback_data=f"TSEL:TOGGLE:{t}"
        )])

    keyboard.append([
        InlineKeyboardButton("✔️ 확정", callback_data="TSEL:CONFIRM"),
        InlineKeyboardButton("❌ 취소", callback_data="TSEL:CANCEL"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def _make_ticker_menu(bot):
    async def cmd_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not bot._is_admin(update):
            return

        chat_id = update.effective_chat.id
        profiled = sorted(tp.list_tickers())

        if not profiled:
            await update.message.reply_text(
                "⚠️ 등록된 티커가 없습니다.\n\n"
                "먼저 <code>/ticker_add</code>로 티커를 등록하세요.",
                parse_mode='HTML'
            )
            return

        # 현재 활성 종목을 초기 선택 상태로 로드
        current = set(bot.cfg.get_active_tickers())
        _toggle_state[chat_id] = current & set(profiled)  # 프로필에 있는 것만

        msg, markup = _build_menu(_toggle_state[chat_id], profiled)
        await update.message.reply_text(msg, reply_markup=markup, parse_mode='HTML')

    return cmd_ticker


def _make_ticker_callback(bot):
    from telegram.ext import ApplicationHandlerStop

    async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        chat_id = update.effective_chat.id
        data = query.data.split(":")
        action = data[1] if len(data) > 1 else ""

        profiled = sorted(tp.list_tickers())
        selected = _toggle_state.setdefault(chat_id, set(bot.cfg.get_active_tickers()) & set(profiled))

        if action == "TOGGLE":
            ticker = data[2]
            if ticker in selected:
                selected.remove(ticker)
            else:
                selected.add(ticker)

            msg, markup = _build_menu(selected, profiled)
            try:
                await query.edit_message_text(msg, reply_markup=markup, parse_mode='HTML')
            except Exception:
                pass  # 같은 내용이면 무시

        elif action == "CONFIRM":
            if selected:
                new_list = sorted(selected)
                bot.cfg.set_active_tickers(new_list)
                _toggle_state.pop(chat_id, None)
                await query.edit_message_text(
                    f"✅ <b>운용 종목 변경 완료</b>\n\n"
                    f"▫️ 활성 종목: <b>{', '.join(new_list)}</b>\n\n"
                    f"💡 <code>/sync</code>로 확인하세요.",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    "❌ <b>최소 1개 이상의 종목을 선택해야 합니다.</b>",
                    parse_mode='HTML'
                )

        elif action == "CANCEL":
            _toggle_state.pop(chat_id, None)
            await query.edit_message_text("🚫 운용 종목 변경이 취소되었습니다.")

        # upstream의 generic CallbackQueryHandler(group=0)가 같은 콜백을
        # 중복 처리하지 않도록 전파 중단
        raise ApplicationHandlerStop

    return on_callback


# ==========================================================
# /ticker_add — 신규 티커 등록 (yfinance 검증)
# ==========================================================
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
                f"💡 <code>/ticker</code>에서 운용 종목으로 활성화하세요.\n"
                f"💡 <code>/seed</code>, <code>/settlement</code>에서 추가 설정 가능합니다."
            )
        else:
            result = msg

        await update.message.reply_text(result, parse_mode='HTML')

    return cmd_ticker_add


# ==========================================================
# /ticker_remove — 프로필 삭제
# ==========================================================
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
            # 활성 종목에서도 제거
            active = bot.cfg.get_active_tickers()
            if ticker in active:
                new_active = [t for t in active if t != ticker]
                bot.cfg.set_active_tickers(new_active)

            await update.message.reply_text(
                f"✅ <b>{ticker}</b> 프로필 삭제 완료",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ <b>{ticker}</b>는 등록되지 않은 티커입니다.",
                parse_mode='HTML'
            )

    return cmd_ticker_remove


# ==========================================================
# /ticker_list — 등록 목록 (활성 상태 표시)
# ==========================================================
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

        lines.append("\n💡 운용 종목 변경: <code>/ticker</code>")

        await update.message.reply_text("\n".join(lines), parse_mode='HTML')

    return cmd_ticker_list
