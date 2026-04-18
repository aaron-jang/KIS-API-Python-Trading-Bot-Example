"""
V14VwapStrategy 테스트

퀀트 로직, 영속성 캐시(L1/L2), 스냅샷, 자전거래 방어 검증
"""
import os
import json
import math
import pytest


@pytest.fixture
def vwap_strategy(cfg, tmp_data_dir):
    from trading_bot.strategy.v14_vwap import V14VwapStrategy
    # ConfigManager 기본값 사용 (SOXL: seed=6720, split=40, target=12%)
    return V14VwapStrategy(cfg)


class TestGetPlanBasic:
    """get_plan 기본 반환 구조"""

    def test_return_keys(self, vwap_strategy):
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=48.0, qty=10,
            prev_close=49.0, is_snapshot_mode=True
        )
        required_keys = ['core_orders', 'orders', 't_val', 'one_portion',
                         'star_price', 'buy_star_price', 'target_price',
                         'star_ratio', 'is_reverse', 'process_status']
        for key in required_keys:
            assert key in plan, f"Missing key: {key}"

    def test_is_reverse_always_false(self, vwap_strategy):
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=48.0, qty=10,
            prev_close=49.0, is_snapshot_mode=True
        )
        assert plan['is_reverse'] is False


class TestNewStart:
    """0주 새출발"""

    def test_new_start_process_status(self, vwap_strategy):
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=0, qty=0,
            prev_close=49.0, is_snapshot_mode=True
        )
        assert plan['process_status'] == "✨새출발"

    def test_new_start_115_anchor(self, vwap_strategy):
        prev_close = 49.0
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=0, qty=0,
            prev_close=prev_close, is_snapshot_mode=True
        )
        expected_price = math.ceil(prev_close * 1.15 * 100) / 100.0
        assert plan['buy_star_price'] == expected_price

    def test_new_start_generates_buy_order(self, vwap_strategy):
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=0, qty=0,
            prev_close=49.0, is_snapshot_mode=True
        )
        buy_orders = [o for o in plan['core_orders'] if o['side'] == 'BUY']
        assert len(buy_orders) >= 1


class TestSelfTradeDefense:
    """자전거래 방어 (buy_star_price = star_price - $0.01)"""

    def test_buy_star_lower_than_sell_star(self, vwap_strategy):
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=48.0, qty=10,
            prev_close=49.0, is_snapshot_mode=True
        )
        if plan['star_price'] > 0.01:
            assert plan['buy_star_price'] == round(plan['star_price'] - 0.01, 2)


class TestSellOrders:
    """매도 주문 생성"""

    def test_sell_quarter_qty(self, vwap_strategy):
        qty = 20
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=48.0, qty=qty,
            prev_close=49.0, is_snapshot_mode=True
        )
        sell_orders = [o for o in plan['core_orders'] if o['side'] == 'SELL']
        if sell_orders:
            star_sell = sell_orders[0]
            assert star_sell['qty'] == math.ceil(qty / 4)


class TestPersistence:
    """L1/L2 영속성 캐시"""

    def test_state_save_and_reload(self, vwap_strategy):
        vwap_strategy.record_execution("SOXL", "BUY", 5, 50.0)
        # L1 캐시 확인
        assert vwap_strategy.executed["BUY_BUDGET"].get("SOXL", 0) == 250.0

        # 새 인스턴스로 L2 파일 로드 확인
        from trading_bot.strategy.v14_vwap import V14VwapStrategy
        new_strategy = V14VwapStrategy(vwap_strategy.cfg)
        new_strategy._load_state_if_needed("SOXL")
        assert new_strategy.executed["BUY_BUDGET"].get("SOXL", 0) == 250.0

    def test_sell_qty_persisted_as_int(self, vwap_strategy):
        vwap_strategy.record_execution("SOXL", "SELL", 3, 55.0)
        state_file = vwap_strategy._get_state_file("SOXL")
        with open(state_file, 'r') as f:
            data = json.load(f)
        assert isinstance(data["executed"]["SELL_QTY"], int)

    def test_reset_residual_clears_state(self, vwap_strategy):
        vwap_strategy.record_execution("SOXL", "BUY", 5, 50.0)
        vwap_strategy.reset_residual("SOXL")
        assert vwap_strategy.executed["BUY_BUDGET"]["SOXL"] == 0.0
        assert vwap_strategy.executed["SELL_QTY"]["SOXL"] == 0


class TestSnapshot:
    """일일 지시서 스냅샷"""

    def test_snapshot_save_and_load(self, vwap_strategy):
        plan_data = {"star_price": 55.0, "t_val": 2.0}
        vwap_strategy.save_daily_snapshot("SOXL", plan_data)
        loaded = vwap_strategy.load_daily_snapshot("SOXL")
        assert loaded is not None
        assert loaded["star_price"] == 55.0

    def test_snapshot_returns_none_when_missing(self, vwap_strategy):
        assert vwap_strategy.load_daily_snapshot("NONEXIST") is None

    def test_get_plan_uses_cached_snapshot(self, vwap_strategy):
        cached = {"star_price": 99.99, "cached": True}
        vwap_strategy.save_daily_snapshot("SOXL", cached)
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=48.0, qty=10,
            prev_close=49.0, is_snapshot_mode=False
        )
        assert plan.get("cached") is True

    def test_snapshot_mode_skips_cache(self, vwap_strategy):
        cached = {"star_price": 99.99, "cached": True}
        vwap_strategy.save_daily_snapshot("SOXL", cached)
        plan = vwap_strategy.get_plan(
            "SOXL", current_price=50.0, avg_price=48.0, qty=10,
            prev_close=49.0, is_snapshot_mode=True
        )
        assert plan.get("cached") is None


class TestUCurveWeights:
    """U-Curve 가중치 무결성"""

    def test_weights_count(self, vwap_strategy):
        assert len(vwap_strategy.U_CURVE_WEIGHTS) == 30

    def test_weights_sum_approximately_one(self, vwap_strategy):
        total = sum(vwap_strategy.U_CURVE_WEIGHTS)
        assert total == pytest.approx(1.0, abs=0.01)

    def test_last_weight_is_heaviest(self, vwap_strategy):
        weights = vwap_strategy.U_CURVE_WEIGHTS
        assert weights[-1] == max(weights)


class TestDynamicPlan:
    """get_dynamic_plan VWAP 슬라이싱"""

    def test_invalid_min_idx_returns_empty(self, vwap_strategy):
        result = vwap_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=49.0,
            current_weight=0.05, min_idx=-1,
            alloc_cash=1000, qty=10, avg_price=48.0
        )
        assert result["orders"] == []

    def test_min_idx_30_returns_empty(self, vwap_strategy):
        result = vwap_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=49.0,
            current_weight=0.05, min_idx=30,
            alloc_cash=1000, qty=10, avg_price=48.0
        )
        assert result["orders"] == []
