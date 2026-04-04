"""
종목별 매매 설정 관리

ConfigManager의 seed/split/target/version/compound/sniper/reverse/misc 설정을
독립 클래스로 추출한 것입니다.
"""
import os
import datetime
from typing import Any, Optional

import pytz

from trading_bot.storage.file_utils import FileUtils


class TradingConfig:
    DEFAULT_SEED = {"SOXL": 6720.0, "TQQQ": 6720.0}
    DEFAULT_SPLIT = {"SOXL": 40.0, "TQQQ": 40.0}
    DEFAULT_TARGET = {"SOXL": 12.0, "TQQQ": 10.0}
    DEFAULT_COMPOUND = {"SOXL": 70.0, "TQQQ": 70.0}
    DEFAULT_VERSION = {"SOXL": "V14", "TQQQ": "V14"}
    DEFAULT_SNIPER_MULTIPLIER = {"SOXL": 1.0, "TQQQ": 0.9}

    def __init__(self, fu: FileUtils, base_dir: str = "data"):
        self._fu = fu
        self._paths = {
            "SEED": os.path.join(base_dir, "seed_config.json"),
            "SPLIT": os.path.join(base_dir, "split_config.json"),
            "PROFIT": os.path.join(base_dir, "profit_config.json"),
            "COMPOUND": os.path.join(base_dir, "compound_config.json"),
            "VERSION": os.path.join(base_dir, "version_config.json"),
            "SNIPER_MULT": os.path.join(base_dir, "sniper_multiplier.json"),
            "REVERSE": os.path.join(base_dir, "reverse_config.json"),
            "UPWARD_SNIPER": os.path.join(base_dir, "upward_sniper.json"),
            "TICKER": os.path.join(base_dir, "active_tickers.json"),
            "SECRET": os.path.join(base_dir, "secret_mode.dat"),
            "CHAT_ID": os.path.join(base_dir, "chat_id.dat"),
            "P_TRADE": os.path.join(base_dir, "p_trade_data.json"),
        }

    # ── Seed ──
    def get_seed(self, t: str) -> float:
        return float(self._fu.load_json(self._paths["SEED"], self.DEFAULT_SEED).get(t, 6720.0))

    def set_seed(self, t: str, v: float):
        d = self._fu.load_json(self._paths["SEED"], self.DEFAULT_SEED)
        d[t] = v
        self._fu.save_json(self._paths["SEED"], d)

    # ── Split ──
    def get_split_count(self, t: str) -> float:
        return self._fu.load_json(self._paths["SPLIT"], self.DEFAULT_SPLIT).get(t, 40.0)

    # ── Target Profit ──
    def get_target_profit(self, t: str) -> float:
        return self._fu.load_json(self._paths["PROFIT"], self.DEFAULT_TARGET).get(t, 10.0)

    # ── Compound ──
    def get_compound_rate(self, t: str) -> float:
        return float(self._fu.load_json(self._paths["COMPOUND"], self.DEFAULT_COMPOUND).get(t, 70.0))

    def set_compound_rate(self, t: str, v: float):
        d = self._fu.load_json(self._paths["COMPOUND"], self.DEFAULT_COMPOUND)
        d[t] = v
        self._fu.save_json(self._paths["COMPOUND"], d)

    # ── Version ──
    def get_version(self, t: str) -> str:
        return self._fu.load_json(self._paths["VERSION"], self.DEFAULT_VERSION).get(t, "V14")

    def set_version(self, t: str, v: str):
        d = self._fu.load_json(self._paths["VERSION"], self.DEFAULT_VERSION)
        d[t] = v
        self._fu.save_json(self._paths["VERSION"], d)

    # ── Sniper Multiplier ──
    def get_sniper_multiplier(self, t: str) -> float:
        default_val = self.DEFAULT_SNIPER_MULTIPLIER.get(t, 1.0)
        return float(self._fu.load_json(self._paths["SNIPER_MULT"], self.DEFAULT_SNIPER_MULTIPLIER).get(t, default_val))

    def set_sniper_multiplier(self, t: str, v: float):
        d = self._fu.load_json(self._paths["SNIPER_MULT"], self.DEFAULT_SNIPER_MULTIPLIER)
        d[t] = float(v)
        self._fu.save_json(self._paths["SNIPER_MULT"], d)

    # ── Reverse State ──
    def get_reverse_state(self, ticker: str) -> dict:
        d = self._fu.load_json(self._paths["REVERSE"], {})
        return d.get(ticker, {"is_active": False, "day_count": 0, "exit_target": 0.0, "last_update_date": ""})

    def set_reverse_state(self, ticker: str, is_active: bool, day_count: int,
                          exit_target: float = 0.0, last_update_date: str = None):
        if last_update_date is None:
            est = pytz.timezone("US/Eastern")
            last_update_date = datetime.datetime.now(est).strftime("%Y-%m-%d")
        d = self._fu.load_json(self._paths["REVERSE"], {})
        d[ticker] = {
            "is_active": is_active,
            "day_count": day_count,
            "exit_target": exit_target,
            "last_update_date": last_update_date,
        }
        self._fu.save_json(self._paths["REVERSE"], d)

    # ── Upward Sniper ──
    def get_upward_sniper_mode(self, ticker: str) -> bool:
        return self._fu.load_json(self._paths["UPWARD_SNIPER"], {}).get(ticker, False)

    def set_upward_sniper_mode(self, ticker: str, v: bool):
        d = self._fu.load_json(self._paths["UPWARD_SNIPER"], {})
        d[ticker] = bool(v)
        self._fu.save_json(self._paths["UPWARD_SNIPER"], d)

    # ── Active Tickers ──
    def get_active_tickers(self) -> list:
        return self._fu.load_json(self._paths["TICKER"], ["SOXL", "TQQQ"])

    def set_active_tickers(self, v: list):
        self._fu.save_json(self._paths["TICKER"], v)

    # ── Secret Mode ──
    def get_secret_mode(self) -> bool:
        return self._fu.load_file(self._paths["SECRET"]) == "True"

    def set_secret_mode(self, v: bool):
        self._fu.save_file(self._paths["SECRET"], str(v))

    # ── Chat ID ──
    def get_chat_id(self):
        v = self._fu.load_file(self._paths["CHAT_ID"])
        return int(v) if v else None

    def set_chat_id(self, v):
        self._fu.save_file(self._paths["CHAT_ID"], v)

    # ── P-Trade ──
    def get_p_trade_data(self) -> dict:
        return self._fu.load_json(self._paths["P_TRADE"], {})

    def set_p_trade_data(self, data: dict):
        self._fu.save_json(self._paths["P_TRADE"], data)

    def clear_p_trade_data(self):
        self._fu.save_json(self._paths["P_TRADE"], {})
