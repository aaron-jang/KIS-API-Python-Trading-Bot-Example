"""
매매 잠금 + 에스크로 관리

ConfigManager의 check_lock/set_lock/reset_locks/escrow 메서드를
독립 클래스로 추출한 것입니다.
"""
import datetime
from typing import Optional

import pytz

from trading_bot.storage.file_utils import FileUtils


class LockManager:
    def __init__(self, fu: FileUtils, locks_path: str):
        self._fu = fu
        self._path = locks_path

    def _load(self) -> dict:
        return self._fu.load_json(self._path, {})

    def _save(self, data: dict) -> None:
        self._fu.save_json(self._path, data)

    def _today_est(self) -> str:
        est = pytz.timezone("US/Eastern")
        return datetime.datetime.now(est).strftime("%Y-%m-%d")

    # ── 에스크로 ──
    def get_escrow(self, ticker: str) -> float:
        return float(self._load().get(f"ESCROW_{ticker}", 0.0))

    def set_escrow(self, ticker: str, amount: float) -> None:
        locks = self._load()
        locks[f"ESCROW_{ticker}"] = float(amount)
        self._save(locks)

    def add_escrow(self, ticker: str, amount: float) -> None:
        self.set_escrow(ticker, self.get_escrow(ticker) + float(amount))

    def clear_escrow(self, ticker: str) -> None:
        locks = self._load()
        if f"ESCROW_{ticker}" in locks:
            del locks[f"ESCROW_{ticker}"]
            self._save(locks)

    def get_total_locked(self, exclude_ticker: Optional[str] = None) -> float:
        locks = self._load()
        total = 0.0
        for k, v in locks.items():
            if k.startswith("ESCROW_"):
                ticker_in_lock = k.replace("ESCROW_", "")
                if ticker_in_lock != exclude_ticker:
                    total += float(v)
        return total

    # ── 매매 잠금 ──
    def check_lock(self, ticker: str, market_type: str) -> bool:
        today = self._today_est()
        return self._load().get(f"{today}_{ticker}_{market_type}", False)

    def set_lock(self, ticker: str, market_type: str) -> None:
        today = self._today_est()
        locks = self._load()
        locks[f"{today}_{ticker}_{market_type}"] = True
        self._save(locks)

    def reset_all(self) -> None:
        locks = self._load()
        surviving = {k: v for k, v in locks.items() if k.startswith("ESCROW_")}
        self._save(surviving)

    def reset_for_ticker(self, ticker: str) -> None:
        today = self._today_est()
        locks = self._load()
        keys_to_delete = [k for k in locks if k.startswith(f"{today}_{ticker}")]
        if keys_to_delete:
            for k in keys_to_delete:
                del locks[k]
            self._save(locks)
