"""
Phase 2: TradingConfig 단위 테스트

종목별 설정, 리버스 상태, 기타 설정의 독립 테스트.
"""
import pytest

from trading_bot.storage.trading_config import TradingConfig
from trading_bot.storage.file_utils import FileUtils


@pytest.fixture
def tc(tmp_path):
    fu = FileUtils()
    return TradingConfig(fu, base_dir=str(tmp_path))


class TestSeedConfig:
    def test_default_seed(self, tc):
        assert tc.get_seed("TQQQ") == 6720.0
        assert tc.get_seed("SOXL") == 6720.0

    def test_set_and_get(self, tc):
        tc.set_seed("TQQQ", 10000.0)
        assert tc.get_seed("TQQQ") == 10000.0
        assert tc.get_seed("SOXL") == 6720.0  # 독립


class TestSplitConfig:
    def test_default(self, tc):
        assert tc.get_split_count("TQQQ") == 40.0

    def test_default_soxl(self, tc):
        assert tc.get_split_count("SOXL") == 40.0


class TestTargetProfit:
    def test_default(self, tc):
        assert tc.get_target_profit("TQQQ") == 10.0
        assert tc.get_target_profit("SOXL") == 12.0


class TestVersion:
    def test_default(self, tc):
        assert tc.get_version("TQQQ") == "V14"

    def test_set_and_get(self, tc):
        tc.set_version("TQQQ", "V17")
        assert tc.get_version("TQQQ") == "V17"


class TestCompoundRate:
    def test_default(self, tc):
        assert tc.get_compound_rate("TQQQ") == 70.0

    def test_set_and_get(self, tc):
        tc.set_compound_rate("SOXL", 50.0)
        assert tc.get_compound_rate("SOXL") == 50.0


class TestSniperMultiplier:
    def test_default(self, tc):
        assert tc.get_sniper_multiplier("TQQQ") == 0.9
        assert tc.get_sniper_multiplier("SOXL") == 1.0

    def test_set_and_get(self, tc):
        tc.set_sniper_multiplier("TQQQ", 1.5)
        assert tc.get_sniper_multiplier("TQQQ") == 1.5


class TestReverseState:
    def test_default(self, tc):
        state = tc.get_reverse_state("TQQQ")
        assert state["is_active"] == False
        assert state["day_count"] == 0

    def test_set_and_get(self, tc):
        tc.set_reverse_state("TQQQ", True, 3, -15.0, "2025-03-12")
        state = tc.get_reverse_state("TQQQ")
        assert state["is_active"] == True
        assert state["day_count"] == 3
        assert state["exit_target"] == -15.0

    def test_independent_per_ticker(self, tc):
        tc.set_reverse_state("TQQQ", True, 2, -10.0, "2025-03-12")
        assert tc.get_reverse_state("SOXL")["is_active"] == False


class TestUpwardSniper:
    def test_default(self, tc):
        assert tc.get_upward_sniper_mode("TQQQ") == False

    def test_set_and_get(self, tc):
        tc.set_upward_sniper_mode("TQQQ", True)
        assert tc.get_upward_sniper_mode("TQQQ") == True
        assert tc.get_upward_sniper_mode("SOXL") == False


class TestActiveTickers:
    def test_default(self, tc):
        assert tc.get_active_tickers() == ["SOXL", "TQQQ"]

    def test_set_and_get(self, tc):
        tc.set_active_tickers(["TQQQ"])
        assert tc.get_active_tickers() == ["TQQQ"]


class TestMiscSettings:
    def test_secret_mode_default(self, tc):
        assert tc.get_secret_mode() == False

    def test_set_secret_mode(self, tc):
        tc.set_secret_mode(True)
        assert tc.get_secret_mode() == True

    def test_chat_id_default(self, tc):
        assert tc.get_chat_id() is None

    def test_set_chat_id(self, tc):
        tc.set_chat_id(123456789)
        assert tc.get_chat_id() == 123456789


class TestPTradeData:
    def test_default_empty(self, tc):
        assert tc.get_p_trade_data() == {}

    def test_set_and_get(self, tc):
        data = {"ticker": "TQQQ", "targets": []}
        tc.set_p_trade_data(data)
        assert tc.get_p_trade_data() == data

    def test_clear(self, tc):
        tc.set_p_trade_data({"some": "data"})
        tc.clear_p_trade_data()
        assert tc.get_p_trade_data() == {}
