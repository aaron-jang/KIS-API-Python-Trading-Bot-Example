# ==========================================================
# [config.py] - Part 1
# ⚠️ 이 주석 및 파일명 표기는 절대 지우지 마세요.
# ==========================================================
import json
import os
import datetime
import pytz
import math
import time
import shutil
import tempfile
import pandas_market_calendars as mcal

from trading_bot.storage.file_utils import FileUtils
from trading_bot.storage.ledger_store import LedgerStore
from trading_bot.storage.lock_manager import LockManager
from trading_bot.storage.trading_config import TradingConfig

try:
    from trading_bot.version_history import VERSION_HISTORY
except ImportError:
    VERSION_HISTORY = ["V14.x [-] 버전 기록 파일(version_history.py)을 찾을 수 없습니다."]

class ConfigManager:
    """
    Facade: 기존 인터페이스를 100% 유지하면서 내부는 분리된 클래스에 위임합니다.
    기존 코드(strategy, broker, telegram_bot, scheduler 등)는 변경 없이 동작합니다.
    """
    def __init__(self):
        self.FILES = {
            "TOKEN": "data/token.dat",
            "CHAT_ID": "data/chat_id.dat",
            "LEDGER": "data/manual_ledger.json",
            "HISTORY": "data/manual_history.json",
            "SPLIT": "data/split_config.json",
            "TICKER": "data/active_tickers.json",
            "UPWARD_SNIPER": "data/upward_sniper.json",
            "SECRET_MODE": "data/secret_mode.dat",
            "PROFIT_CFG": "data/profit_config.json",
            "LOCKS": "data/trade_locks.json",
            "SEED_CFG": "data/seed_config.json",
            "COMPOUND_CFG": "data/compound_config.json",
            "VERSION_CFG": "data/version_config.json",
            "REVERSE_CFG": "data/reverse_config.json",
            "SNIPER_MULTIPLIER_CFG": "data/sniper_multiplier.json",
            "SPLIT_HISTORY": "data/split_history.json",
            "P_TRADE_DATA": "data/p_trade_data.json"
        }

        # ── 내부 위임 객체 초기화 ──
        self._fu = FileUtils()
        self._ledger = LedgerStore(
            self._fu,
            self.FILES["LEDGER"],
            self.FILES["HISTORY"],
            self.FILES["SPLIT_HISTORY"],
        )
        self._locks = LockManager(self._fu, self.FILES["LOCKS"])
        self._config = TradingConfig(self._fu, base_dir="data")

        # 기존 코드 호환용
        self.DEFAULT_SEED = TradingConfig.DEFAULT_SEED
        self.DEFAULT_SPLIT = TradingConfig.DEFAULT_SPLIT
        self.DEFAULT_TARGET = TradingConfig.DEFAULT_TARGET
        self.DEFAULT_COMPOUND = TradingConfig.DEFAULT_COMPOUND
        self.DEFAULT_VERSION = TradingConfig.DEFAULT_VERSION
        self.DEFAULT_SNIPER_MULTIPLIER = TradingConfig.DEFAULT_SNIPER_MULTIPLIER

    # ==========================================================
    # I/O 유틸 (기존 코드가 직접 호출하는 경우를 위해 유지)
    # ==========================================================
    def _load_json(self, filename, default=None):
        return self._fu.load_json(filename, default)

    def _save_json(self, filename, data):
        self._fu.save_json(filename, data)

    def _load_file(self, filename, default=None):
        return self._fu.load_file(filename, default)

    def _save_file(self, filename, content):
        self._fu.save_file(filename, content)

    # ==========================================================
    # 장부(Ledger) → LedgerStore 위임
    # ==========================================================
    def get_ledger(self):
        return self._ledger.get_ledger()

    def get_last_split_date(self, ticker):
        return self._ledger.get_last_split_date(ticker)

    def set_last_split_date(self, ticker, date_str):
        self._ledger.set_last_split_date(ticker, date_str)

    def apply_stock_split(self, ticker, ratio):
        self._ledger.apply_stock_split(ticker, ratio)

    def overwrite_genesis_ledger(self, ticker, genesis_records, actual_avg):
        self._ledger.overwrite_genesis(ticker, genesis_records, actual_avg)

    def overwrite_incremental_ledger(self, ticker, temp_recs, new_today_records):
        current_rev_state = self.get_reverse_state(ticker).get("is_active", False)
        self._ledger.overwrite_incremental(ticker, temp_recs, new_today_records, current_rev_state)

    def overwrite_ledger(self, ticker, actual_qty, actual_avg):
        """최초 스냅샷 — 교차 의존이 있어 Facade에 유지"""
        ledger = self.get_ledger()
        target_recs = [r for r in ledger if r['ticker'] == ticker]

        if len(target_recs) > 0:
            print(f"⚠️ [보안 차단] {ticker}의 장부 기록이 이미 존재하여 파괴적 INIT 덮어쓰기를 차단했습니다.")
            return

        kst = pytz.timezone('Asia/Seoul')
        today_str = datetime.datetime.now(kst).strftime('%Y-%m-%d')
        new_id = 1 if not ledger else max(r.get('id', 0) for r in ledger) + 1

        ledger.append({
            "id": new_id, "date": today_str, "ticker": ticker, "side": "BUY",
            "price": actual_avg, "qty": actual_qty, "avg_price": actual_avg,
            "exec_id": f"INIT_{int(time.time())}", "desc": "✨최초스냅샷", "is_reverse": False
        })
        self._fu.save_json(self.FILES["LEDGER"], ledger)

    def calibrate_avg_price(self, ticker, actual_avg):
        ledger = self.get_ledger()
        target_recs = [r for r in ledger if r['ticker'] == ticker]
        if target_recs:
            for r in target_recs:
                r['avg_price'] = actual_avg
            self._fu.save_json(self.FILES["LEDGER"], ledger)

    def calibrate_ledger_prices(self, ticker, target_date_str, exec_history):
        return self._ledger.calibrate_prices(ticker, target_date_str, exec_history)

    def clear_ledger_for_ticker(self, ticker):
        """교차 의존: 장부 삭제 + 리버스 초기화 + 에스크로 해제"""
        self._ledger.clear_for_ticker(ticker)
        self.set_reverse_state(ticker, False, 0, 0.0)
        self.clear_escrow_cash(ticker)

    def calculate_holdings(self, ticker, records=None):
        return self._ledger.calculate_holdings(ticker, records)

    def calculate_v14_state(self, ticker):
        seed = self.get_seed(ticker)
        split = self.get_split_count(ticker)
        return self._ledger.calculate_v14_state(ticker, seed, split)

    def get_absolute_t_val(self, ticker, actual_qty, actual_avg_price):
        seed = self.get_seed(ticker)
        split = self.get_split_count(ticker)
        one_portion = seed / split if split > 0 else 1
        t_val = (actual_qty * actual_avg_price) / one_portion if one_portion > 0 else 0.0
        return round(t_val, 4), one_portion

    def archive_graduation(self, ticker, end_date, prev_close=0.0):
        """교차 의존이 많아 Facade에 유지"""
        ledger = self.get_ledger()
        target_recs = [r for r in ledger if r['ticker'] == ticker]
        if not target_recs:
            return None, 0

        ledger_qty, avg_price, _, _ = self.calculate_holdings(ticker, target_recs)

        if ledger_qty > 0:
            split = self.get_split_count(ticker)
            is_reverse = self.get_reverse_state(ticker).get("is_active", False)

            if is_reverse:
                divisor = 10 if split <= 20 else 20
                loc_qty = math.floor(ledger_qty / divisor)
            else:
                loc_qty = math.ceil(ledger_qty / 4)

            limit_qty = ledger_qty - loc_qty
            if limit_qty < 0:
                loc_qty = ledger_qty
                limit_qty = 0

            target_ratio = self.get_target_profit(ticker) / 100.0
            target_price = math.ceil(avg_price * (1 + target_ratio) * 100) / 100.0
            loc_price = prev_close if prev_close > 0 else avg_price

            new_id = max((r.get('id', 0) for r in ledger), default=0) + 1

            if loc_qty > 0:
                rec_loc = {"id": new_id, "date": end_date, "ticker": ticker, "side": "SELL", "price": loc_price, "qty": loc_qty, "avg_price": avg_price, "exec_id": f"GRAD_LOC_{int(time.time())}", "is_reverse": is_reverse}
                ledger.append(rec_loc)
                target_recs.append(rec_loc)
                new_id += 1

            if limit_qty > 0:
                rec_limit = {"id": new_id, "date": end_date, "ticker": ticker, "side": "SELL", "price": target_price, "qty": limit_qty, "avg_price": avg_price, "exec_id": f"GRAD_LMT_{int(time.time())}", "is_reverse": is_reverse}
                ledger.append(rec_limit)
                target_recs.append(rec_limit)

            self._fu.save_json(self.FILES["LEDGER"], ledger)

        total_buy = math.ceil(sum(r['price']*r['qty'] for r in target_recs if r['side']=='BUY') * 100) / 100.0
        total_sell = math.ceil(sum(r['price']*r['qty'] for r in target_recs if r['side']=='SELL') * 100) / 100.0

        profit = math.ceil((total_sell - total_buy) * 100) / 100.0
        yield_pct = math.ceil(((profit / total_buy * 100) if total_buy > 0 else 0.0) * 100) / 100.0

        compound_rate = self.get_compound_rate(ticker) / 100.0
        added_seed = 0
        if profit > 0 and compound_rate > 0:
            added_seed = math.floor(profit * compound_rate)
            current_seed = self.get_seed(ticker)
            self.set_seed(ticker, current_seed + added_seed)

        history = self._fu.load_json(self.FILES["HISTORY"], [])
        new_hist = {
            "id": len(history) + 1, "ticker": ticker, "end_date": end_date,
            "profit": profit, "yield": yield_pct, "revenue": total_sell, "invested": total_buy, "trades": target_recs
        }
        history.append(new_hist)
        self._fu.save_json(self.FILES["HISTORY"], history)

        self.clear_ledger_for_ticker(ticker)

        return new_hist, added_seed

    def get_history(self):
        return self._ledger.get_history()

    # ==========================================================
    # 잠금/에스크로 → LockManager 위임
    # ==========================================================
    def get_escrow_cash(self, ticker):
        return self._locks.get_escrow(ticker)

    def set_escrow_cash(self, ticker, amount):
        self._locks.set_escrow(ticker, amount)

    def add_escrow_cash(self, ticker, amount):
        self._locks.add_escrow(ticker, amount)

    def clear_escrow_cash(self, ticker):
        self._locks.clear_escrow(ticker)

    def get_total_locked_cash(self, exclude_ticker=None):
        return self._locks.get_total_locked(exclude_ticker)

    def check_lock(self, ticker, market_type):
        return self._locks.check_lock(ticker, market_type)

    def set_lock(self, ticker, market_type):
        self._locks.set_lock(ticker, market_type)

    def reset_locks(self):
        self._locks.reset_all()

    def reset_lock_for_ticker(self, ticker):
        self._locks.reset_for_ticker(ticker)

    # ==========================================================
    # 설정 → TradingConfig 위임
    # ==========================================================
    def get_seed(self, t):
        return self._config.get_seed(t)

    def set_seed(self, t, v):
        self._config.set_seed(t, v)

    def get_compound_rate(self, t):
        return self._config.get_compound_rate(t)

    def set_compound_rate(self, t, v):
        self._config.set_compound_rate(t, v)

    def get_version(self, t):
        return self._config.get_version(t)

    def set_version(self, t, v):
        self._config.set_version(t, v)

    def get_split_count(self, t):
        return self._config.get_split_count(t)

    def get_target_profit(self, t):
        return self._config.get_target_profit(t)

    def get_sniper_multiplier(self, t):
        return self._config.get_sniper_multiplier(t)

    def set_sniper_multiplier(self, t, v):
        self._config.set_sniper_multiplier(t, v)

    def get_reverse_state(self, ticker):
        return self._config.get_reverse_state(ticker)

    def set_reverse_state(self, ticker, is_active, day_count, exit_target=0.0, last_update_date=None):
        self._config.set_reverse_state(ticker, is_active, day_count, exit_target, last_update_date)

    def update_reverse_day_if_needed(self, ticker):
        return False

    def increment_reverse_day(self, ticker):
        state = self.get_reverse_state(ticker)
        if state.get("is_active"):
            est = pytz.timezone('US/Eastern')
            now_est = datetime.datetime.now(est)
            today_est_str = now_est.strftime('%Y-%m-%d')

            if state.get("last_update_date") != today_est_str:
                is_trading_day = False
                try:
                    nyse = mcal.get_calendar('NYSE')
                    schedule = nyse.schedule(start_date=now_est.date(), end_date=now_est.date())
                    is_trading_day = not schedule.empty
                except Exception as e:
                    print(f"⚠️ [Config] 달력 라이브러리 에러 발생. 평일 강제 개장 처리합니다: {e}")
                    is_trading_day = now_est.weekday() < 5

                if is_trading_day:
                    new_day = state.get("day_count", 0) + 1
                    self.set_reverse_state(ticker, True, new_day, state.get("exit_target", 0.0), today_est_str)
                    return True
                else:
                    self.set_reverse_state(ticker, True, state.get("day_count", 0), state.get("exit_target", 0.0), today_est_str)
                    return False
        return False

    # ==========================================================
    # 스나이퍼/티커/시크릿/챗ID → TradingConfig 위임
    # ==========================================================
    def get_upward_sniper_mode(self, ticker):
        return self._config.get_upward_sniper_mode(ticker)

    def set_upward_sniper_mode(self, ticker, v):
        self._config.set_upward_sniper_mode(ticker, v)

    def get_secret_mode(self):
        return self._config.get_secret_mode()

    def set_secret_mode(self, v):
        self._config.set_secret_mode(v)

    def get_active_tickers(self):
        return self._config.get_active_tickers()

    def set_active_tickers(self, v):
        self._config.set_active_tickers(v)

    def get_chat_id(self):
        return self._config.get_chat_id()

    def set_chat_id(self, v):
        self._config.set_chat_id(v)

    # ==========================================================
    # P매매 → TradingConfig 위임
    # ==========================================================
    def get_p_trade_data(self):
        return self._config.get_p_trade_data()

    def set_p_trade_data(self, data):
        self._config.set_p_trade_data(data)

    def clear_p_trade_data(self):
        self._config.clear_p_trade_data()

    # ==========================================================
    # 버전 히스토리 (변경 없음)
    # ==========================================================
    def get_full_version_history(self):
        return VERSION_HISTORY

    def get_version_history(self):
        return VERSION_HISTORY

    def get_latest_version(self):
        history = self.get_version_history()
        if history and len(history) > 0:
            latest_entry = history[-1]
            if isinstance(latest_entry, dict):
                return latest_entry.get("version", "V14.x")
            elif isinstance(latest_entry, str):
                return latest_entry.split(' ')[0]
        return "V14.x"
