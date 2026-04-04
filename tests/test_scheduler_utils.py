"""
Phase 0: scheduler_core 유틸리티 함수 특성 테스트

순수 함수(시간/달력 의존 없는 것)와 계산 로직을 검증합니다.
"""
import math
import pytest
from unittest.mock import MagicMock, patch
import datetime
import pytz


# ==============================================================
# 1. 예산 배분 로직 테스트
# ==============================================================
class TestBudgetAllocation:

    def test_single_ticker_gets_all_cash(self, cfg):
        from trading_bot.scheduler.core_jobs import get_budget_allocation
        sorted_t, allocated = get_budget_allocation(10000, ["TQQQ"], cfg)
        assert sorted_t == ["TQQQ"]
        assert allocated["TQQQ"] == 10000

    def test_multi_ticker_allocation_order(self, cfg):
        """SOXL이 항상 먼저 배분"""
        from trading_bot.scheduler.core_jobs import get_budget_allocation
        sorted_t, allocated = get_budget_allocation(10000, ["TQQQ", "SOXL"], cfg)
        assert sorted_t[0] == "SOXL"
        assert sorted_t[1] == "TQQQ"

    def test_multi_ticker_both_get_cash(self, cfg):
        from trading_bot.scheduler.core_jobs import get_budget_allocation
        sorted_t, allocated = get_budget_allocation(10000, ["TQQQ", "SOXL"], cfg)
        assert allocated["SOXL"] > 0
        assert allocated["TQQQ"] > 0

    def test_zero_cash(self, cfg):
        from trading_bot.scheduler.core_jobs import get_budget_allocation
        sorted_t, allocated = get_budget_allocation(0, ["TQQQ", "SOXL"], cfg)
        # 잔고 0이면 portion(168)보다 작으므로 0 배정
        assert allocated["SOXL"] == 0
        assert allocated["TQQQ"] == 0

    def test_reverse_ticker_gets_zero_portion(self, cfg):
        """리버스 중인 종목은 portion=0"""
        cfg.set_reverse_state("TQQQ", True, 3, -15.0, "2025-03-12")
        from trading_bot.scheduler.core_jobs import get_budget_allocation
        sorted_t, allocated = get_budget_allocation(10000, ["TQQQ", "SOXL"], cfg)
        # SOXL(정상)은 잔고 전체, TQQQ(리버스)는 남은 잔고
        assert allocated["SOXL"] == 10000


# ==============================================================
# 2. 체결 가격 매칭 테스트
# ==============================================================
class TestExecutionPriceMatching:

    def test_exact_match(self):
        from trading_bot.scheduler.core_jobs import get_actual_execution_price
        execs = [
            {"sll_buy_dvsn_cd": "02", "ft_ccld_qty": "10", "ft_ccld_unpr3": "50.00", "ord_tmd": "170500"},
        ]
        price = get_actual_execution_price(execs, 10, "02")
        assert price == 50.0

    def test_partial_match(self):
        from trading_bot.scheduler.core_jobs import get_actual_execution_price
        execs = [
            {"sll_buy_dvsn_cd": "02", "ft_ccld_qty": "5", "ft_ccld_unpr3": "50.00", "ord_tmd": "170500"},
            {"sll_buy_dvsn_cd": "02", "ft_ccld_qty": "5", "ft_ccld_unpr3": "48.00", "ord_tmd": "170300"},
        ]
        price = get_actual_execution_price(execs, 10, "02")
        # 가중 평균: (5*50 + 5*48) / 10 = 49.0
        assert price == math.floor(49.0 * 100) / 100.0

    def test_empty_execs_returns_zero(self):
        from trading_bot.scheduler.core_jobs import get_actual_execution_price
        assert get_actual_execution_price([], 10, "02") == 0.0

    def test_no_matching_side(self):
        from trading_bot.scheduler.core_jobs import get_actual_execution_price
        execs = [
            {"sll_buy_dvsn_cd": "01", "ft_ccld_qty": "10", "ft_ccld_unpr3": "50.00", "ord_tmd": "170500"},
        ]
        # side_cd "02" (BUY)를 찾는데 데이터는 "01" (SELL)
        price = get_actual_execution_price(execs, 10, "02")
        assert price == 0.0

    def test_overflow_qty_capped(self):
        """target_qty보다 체결량이 많으면 target까지만"""
        from trading_bot.scheduler.core_jobs import get_actual_execution_price
        execs = [
            {"sll_buy_dvsn_cd": "02", "ft_ccld_qty": "20", "ft_ccld_unpr3": "50.00", "ord_tmd": "170500"},
        ]
        price = get_actual_execution_price(execs, 5, "02")
        assert price == 50.0


# ==============================================================
# 3. DST / 시간대 유틸리티 테스트
# ==============================================================
class TestTimeUtils:

    def test_get_target_hour_returns_tuple(self):
        from trading_bot.scheduler.core_jobs import get_target_hour
        hour, msg = get_target_hour()
        assert hour in [17, 18]
        assert isinstance(msg, str)

    def test_is_dst_active_returns_bool(self):
        from trading_bot.scheduler.core_jobs import is_dst_active
        result = is_dst_active()
        assert isinstance(result, bool)


# ==============================================================
# 4. VWAP Dominance 분석 테스트 (strategy.py의 순수 계산)
# ==============================================================
class TestVwapDominance:
    """strategy.py의 analyze_vwap_dominance() 순수 계산 검증"""

    def test_with_valid_dataframe(self, cfg):
        import pandas as pd
        import numpy as np
        from trading_bot.strategy.infinite import InfiniteStrategy

        strategy = InfiniteStrategy(cfg)

        np.random.seed(42)
        n = 30
        dates = pd.date_range("2025-03-12 09:30", periods=n, freq="1min")
        close = 50 + np.cumsum(np.random.randn(n) * 0.1)

        df = pd.DataFrame({
            "Open": close + np.random.randn(n) * 0.05,
            "High": close + np.abs(np.random.randn(n)) * 0.2,
            "Low": close - np.abs(np.random.randn(n)) * 0.2,
            "Close": close,
            "Volume": np.random.randint(10000, 100000, n)
        }, index=dates)

        result = strategy.analyze_vwap_dominance(df)
        assert "vwap_price" in result
        assert "is_strong_up" in result
        assert "is_strong_down" in result
        assert result["vwap_price"] > 0

    def test_with_insufficient_data(self, cfg):
        import pandas as pd
        from trading_bot.strategy.infinite import InfiniteStrategy

        strategy = InfiniteStrategy(cfg)

        df = pd.DataFrame({
            "Open": [50], "High": [51], "Low": [49],
            "Close": [50], "Volume": [1000]
        })
        result = strategy.analyze_vwap_dominance(df)
        assert result["vwap_price"] == 0.0

    def test_with_none_input(self, cfg):
        from trading_bot.strategy.infinite import InfiniteStrategy
        strategy = InfiniteStrategy(cfg)
        result = strategy.analyze_vwap_dominance(None)
        assert result["vwap_price"] == 0.0
        assert result["is_strong_up"] == False
