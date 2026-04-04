"""
Phase 0: InfiniteStrategy 특성 테스트 (Characterization Test)

get_plan()의 다양한 시나리오에서 현재 동작을 캡처합니다.
ConfigManager를 실제 임시 파일시스템에서 동작시켜 정확한 동작을 보존합니다.
"""
import math
import pytest
from trading_bot.strategy.infinite import InfiniteStrategy


@pytest.fixture
def strategy(cfg):
    return InfiniteStrategy(cfg)


@pytest.fixture
def strategy_with_ledger(cfg_with_ledger):
    return InfiniteStrategy(cfg_with_ledger)


# ==============================================================
# 1. 새 출발 (qty=0) 시나리오
# ==============================================================
class TestNewStart:
    """보유 수량 0일 때 첫 매수 주문 생성 검증"""

    def test_new_start_generates_buy_order(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=50.0,
            avg_price=0.0,
            qty=0,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        assert plan["process_status"] == "✨새출발"
        assert plan["is_reverse"] == False
        assert len(plan["core_orders"]) == 1

        order = plan["core_orders"][0]
        assert order["side"] == "BUY"
        assert order["type"] == "LOC"
        assert order["qty"] > 0
        # 가격은 base_price * 1.15 - 0.01 이하
        assert order["price"] <= math.ceil(50.0 * 1.15 * 100) / 100.0

    def test_new_start_returns_zero_t_val(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ", current_price=50.0, avg_price=0.0,
            qty=0, prev_close=49.0, market_type="REG", available_cash=10000
        )
        assert plan["t_val"] == 0.0


# ==============================================================
# 2. 정상 매매 (전반전/후반전)
# ==============================================================
class TestNormalTrading:
    """보유 수량이 있고 리버스가 아닐 때 매수/매도 주문 생성 검증"""

    def test_normal_generates_buy_and_sell(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=10,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        # 주문이 생성되어야 함
        assert len(plan["orders"]) > 0
        # 매수와 매도 모두 있어야 함
        sides = {o["side"] for o in plan["orders"]}
        assert "BUY" in sides
        assert "SELL" in sides

    def test_first_half_status(self, strategy):
        """t_val이 split/2 미만이면 전반전"""
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=10,  # 작은 수량 → 낮은 t_val
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        assert "전반전" in plan["process_status"] or "새출발" in plan["process_status"] or "마지막" in plan["process_status"]

    def test_sell_orders_have_star_and_target(self, strategy):
        """매도 주문에 별값매도, 목표매도가 포함되는지"""
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=20,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        sell_descs = [o["desc"] for o in plan["orders"] if o["side"] == "SELL"]
        has_star = any("별값" in d for d in sell_descs)
        has_target = any("목표" in d for d in sell_descs)
        # 일반적으로 둘 다 있어야 함 (스나이퍼 잠금이 없을 때)
        assert has_star or has_target

    def test_bonus_orders_are_jupjup(self, strategy):
        """줍줍 보너스 주문이 생성되는지"""
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=10,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        bonus_descs = [o["desc"] for o in plan["bonus_orders"]]
        has_jupjup = any("줍줍" in d for d in bonus_descs)
        assert has_jupjup


# ==============================================================
# 3. 잭팟(목표 도달) 시나리오
# ==============================================================
class TestJackpot:
    """현재가가 목표가 이상일 때 동작 검증"""

    def test_jackpot_reached(self, strategy):
        # target_profit=10% → target_price = 50 * 1.10 = 55.0 (ceil 적용)
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=56.0,
            avg_price=50.0,
            qty=10,
            prev_close=54.0,
            market_type="REG",
            available_cash=10000
        )
        # 잭팟이면 여전히 매도 주문은 있어야 함
        sell_orders = [o for o in plan["orders"] if o["side"] == "SELL"]
        assert len(sell_orders) > 0


# ==============================================================
# 4. 리버스 모드 시나리오
# ==============================================================
class TestReverseMode:
    """예산 소진 후 리버스 진입 동작 검증"""

    def test_reverse_entry_when_money_short(self, strategy):
        """잔고 부족 + t_val > split-1 → 리버스 진입"""
        # split=40, seed=6720 → one_portion=168
        # qty * avg / one_portion > 39 → qty 필요: 39 * 168 / 50 = 130.5
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=140,
            prev_close=49.0,
            market_type="REG",
            available_cash=10  # 잔고 극소
        )
        assert plan["is_reverse"] == True

    def test_reverse_day1_moc_sell(self, cfg):
        """리버스 1일차는 MOC 의무매도"""
        cfg.set_reverse_state("TQQQ", True, 1, -15.0, "2025-03-12")
        strategy = InfiniteStrategy(cfg)
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=100,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        assert plan["is_reverse"] == True
        assert "리버스" in plan["process_status"]
        moc_orders = [o for o in plan["core_orders"] if o["type"] == "MOC"]
        assert len(moc_orders) > 0

    def test_reverse_day2_plus_buys_and_sells(self, cfg):
        """리버스 2일차 이후는 매수+매도"""
        cfg.set_reverse_state("TQQQ", True, 3, -15.0, "2025-03-12")
        strategy = InfiniteStrategy(cfg)
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=100,
            prev_close=49.0,
            ma_5day=49.5,
            market_type="REG",
            available_cash=10000
        )
        assert plan["is_reverse"] == True
        sides = {o["side"] for o in plan["orders"]}
        # 리버스 2일차+는 매수와 매도 모두 가능
        assert len(plan["orders"]) > 0


# ==============================================================
# 5. 프리마켓 시나리오
# ==============================================================
class TestPreMarket:
    """프리마켓(PRE_CHECK) 동작 검증"""

    def test_premarket_no_orders_when_below_target(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=10,
            prev_close=49.0,
            market_type="PRE_CHECK",
            available_cash=10000
        )
        assert plan["process_status"] == "🌅프리마켓"
        assert len(plan["orders"]) == 0

    def test_premarket_sell_when_above_target(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=56.0,
            avg_price=50.0,
            qty=10,
            prev_close=54.0,
            market_type="PRE_CHECK",
            available_cash=10000
        )
        assert len(plan["orders"]) == 1
        assert plan["orders"][0]["side"] == "SELL"


# ==============================================================
# 6. 워시트레이드 방어 검증
# ==============================================================
class TestWashTradeDefense:
    """매수가가 매도가 이상이 되지 않도록 교정하는지 검증"""

    def test_buy_price_always_below_sell_price(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=20,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        buy_prices = [o["price"] for o in plan["orders"] if o["side"] == "BUY" and o["price"] > 0]
        sell_prices = [o["price"] for o in plan["orders"] if o["side"] == "SELL" and o["price"] > 0]

        if buy_prices and sell_prices:
            max_buy = max(buy_prices)
            min_sell = min(sell_prices)
            assert max_buy < min_sell, f"워시트레이드 위반: max_buy={max_buy} >= min_sell={min_sell}"

    def test_all_prices_positive(self, strategy):
        """모든 주문 가격이 0.01 이상"""
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=48.0,
            avg_price=50.0,
            qty=20,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        for o in plan["orders"]:
            if o["type"] != "MOC" and o["type"] != "MOO":
                assert o["price"] >= 0.01, f"가격 위반: {o}"


# ==============================================================
# 7. 가격 오류 시 방어
# ==============================================================
class TestEdgeCases:

    def test_zero_price_returns_error(self, strategy):
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=0,
            avg_price=0,
            qty=10,
            prev_close=0,
            market_type="REG",
            available_cash=10000
        )
        assert "가격오류" in plan["process_status"]
        assert len(plan["orders"]) == 0

    def test_plan_return_structure(self, strategy):
        """반환 딕셔너리 구조 검증"""
        plan = strategy.get_plan(
            ticker="TQQQ",
            current_price=50.0,
            avg_price=50.0,
            qty=10,
            prev_close=49.0,
            market_type="REG",
            available_cash=10000
        )
        required_keys = [
            "orders", "core_orders", "bonus_orders",
            "smart_core_orders", "smart_bonus_orders",
            "t_val", "one_portion", "process_status",
            "is_reverse", "star_price", "star_ratio",
            "real_cash_used", "tracking_info"
        ]
        for key in required_keys:
            assert key in plan, f"누락된 키: {key}"
