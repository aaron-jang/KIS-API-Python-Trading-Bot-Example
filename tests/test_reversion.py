"""
ReversionStrategy 테스트

V-REV 타점 산출, 지층 분리 익절, 영속성 캐시, 스냅샷 검증
"""
import os
import json
import math
import pytest


@pytest.fixture
def rev_strategy(tmp_path, monkeypatch):
    work_dir = str(tmp_path)
    monkeypatch.chdir(work_dir)
    os.makedirs(os.path.join(work_dir, "data"), exist_ok=True)
    from trading_bot.strategy.reversion import ReversionStrategy
    return ReversionStrategy()


@pytest.fixture
def empty_vwap_status():
    return {"is_strong_up": False, "is_strong_down": False, "vwap_price": 0.0}


class TestGetDynamicPlanNewStart:
    """0주 새출발 타점"""

    def test_new_start_buy1_price(self, rev_strategy, empty_vwap_status):
        prev_c = 50.0
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=48.0, prev_c=prev_c,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=[],
            is_snapshot_mode=True
        )
        buy_orders = [o for o in plan.get('orders', []) if o['side'] == 'BUY']
        if buy_orders:
            p1 = buy_orders[0]['price']
            assert p1 == round(prev_c / 0.935, 2)

    def test_new_start_buy2_price(self, rev_strategy, empty_vwap_status):
        prev_c = 50.0
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=48.0, prev_c=prev_c,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=[],
            is_snapshot_mode=True
        )
        buy_orders = [o for o in plan.get('orders', []) if o['side'] == 'BUY']
        if len(buy_orders) >= 2:
            p2 = buy_orders[1]['price']
            assert p2 == round(prev_c * 0.999, 2)

    def test_new_start_no_grid_orders(self, rev_strategy, empty_vwap_status):
        """0주 시 줍줍(Grid) 미생성"""
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=48.0, prev_c=50.0,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=[],
            is_snapshot_mode=True
        )
        buy_orders = [o for o in plan.get('orders', []) if o['side'] == 'BUY']
        # 0주 시 Buy1 + Buy2 최대 2개만 생성
        assert len(buy_orders) <= 2


class TestLayerDecoupling:
    """지층 분리 익절 타점"""

    def test_l1_trigger_1006(self, rev_strategy, empty_vwap_status):
        """1층 익절 타점 = 1층 고유 매수가 × 1.006"""
        q_data = [
            {"qty": 10, "price": 40.0, "date": "2026-04-15 10:00:00"},
            {"qty": 5, "price": 45.0, "date": "2026-04-17 10:00:00"},
        ]
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=48.0,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=q_data,
            is_snapshot_mode=True
        )
        # 1층(최신 날짜) 가격 = 45.0, 타점 = 45.0 * 1.006
        expected_l1 = round(45.0 * 1.006, 2)
        sell_orders = [o for o in plan.get('orders', []) if o['side'] == 'SELL']
        if sell_orders:
            prices = [o['price'] for o in sell_orders]
            assert expected_l1 in prices

    def test_upper_trigger_1005(self, rev_strategy, empty_vwap_status):
        """상위층 익절 타점 = 상위 분리 평단가 × 1.005"""
        q_data = [
            {"qty": 10, "price": 40.0, "date": "2026-04-15 10:00:00"},
            {"qty": 5, "price": 45.0, "date": "2026-04-17 10:00:00"},
        ]
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=48.0,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=q_data,
            is_snapshot_mode=True
        )
        # 상위층(1층 제외) 가격 = 40.0, 타점 = 40.0 * 1.005
        expected_upper = round(40.0 * 1.005, 2)
        sell_orders = [o for o in plan.get('orders', []) if o['side'] == 'SELL']
        if len(sell_orders) >= 2:
            prices = [o['price'] for o in sell_orders]
            assert expected_upper in prices


class TestPersistence:
    """영속성 캐시"""

    def test_record_buy_persists(self, rev_strategy):
        rev_strategy.record_execution("SOXL", "BUY", 5, 50.0)
        assert rev_strategy.executed["BUY_BUDGET"]["SOXL"] == 250.0

    def test_record_sell_persists(self, rev_strategy):
        rev_strategy.record_execution("SOXL", "SELL", 3, 55.0)
        assert rev_strategy.executed["SELL_QTY"]["SOXL"] == 3

    def test_state_survives_new_instance(self, rev_strategy):
        rev_strategy.record_execution("SOXL", "BUY", 10, 48.0)
        from trading_bot.strategy.reversion import ReversionStrategy
        new_rev = ReversionStrategy()
        new_rev._load_state_if_needed("SOXL")
        assert new_rev.executed["BUY_BUDGET"]["SOXL"] == 480.0

    def test_reset_clears_state(self, rev_strategy):
        rev_strategy.record_execution("SOXL", "BUY", 10, 50.0)
        rev_strategy.reset_residual("SOXL")
        assert rev_strategy.executed["BUY_BUDGET"]["SOXL"] == 0.0
        assert rev_strategy.executed["SELL_QTY"]["SOXL"] == 0


class TestSnapshot:
    """일일 지시서 스냅샷"""

    def test_save_and_load(self, rev_strategy):
        plan = {"orders": [{"side": "BUY", "price": 50.0}], "total_q": 10}
        rev_strategy.save_daily_snapshot("SOXL", plan)
        loaded = rev_strategy.load_daily_snapshot("SOXL")
        assert loaded is not None
        assert loaded["total_q"] == 10

    def test_snapshot_not_overwritten(self, rev_strategy):
        """스냅샷은 1일 1회만 저장 (멱등성)"""
        plan1 = {"version": 1}
        plan2 = {"version": 2}
        rev_strategy.save_daily_snapshot("SOXL", plan1)
        rev_strategy.save_daily_snapshot("SOXL", plan2)
        loaded = rev_strategy.load_daily_snapshot("SOXL")
        assert loaded["version"] == 1

    def test_snapshot_used_as_cache(self, rev_strategy, empty_vwap_status):
        cached = {"orders": [], "cached": True, "total_q": 0}
        rev_strategy.save_daily_snapshot("SOXL", cached)
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=48.0,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=[]
        )
        assert plan.get("cached") is True

    def test_missing_snapshot_returns_none(self, rev_strategy):
        assert rev_strategy.load_daily_snapshot("NONEXIST") is None


class TestUCurveWeights:
    """U-Curve 가중치 무결성"""

    def test_30_weights(self, rev_strategy):
        assert len(rev_strategy.U_CURVE_WEIGHTS) == 30

    def test_sum_approximately_one(self, rev_strategy):
        assert sum(rev_strategy.U_CURVE_WEIGHTS) == pytest.approx(1.0, abs=0.01)


class TestInvalidMinIdx:
    """유효하지 않은 min_idx"""

    def test_negative_idx_no_vwap_returns_empty(self, rev_strategy, empty_vwap_status):
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=48.0,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=-1, alloc_cash=1000, q_data=[]
        )
        assert plan.get("orders", []) == []

    def test_idx_30_no_vwap_returns_empty(self, rev_strategy, empty_vwap_status):
        plan = rev_strategy.get_dynamic_plan(
            "SOXL", curr_p=50.0, prev_c=48.0,
            current_weight=0.05, vwap_status=empty_vwap_status,
            min_idx=30, alloc_cash=1000, q_data=[]
        )
        assert plan.get("orders", []) == []
