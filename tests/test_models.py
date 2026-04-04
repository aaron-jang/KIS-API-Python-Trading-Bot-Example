"""
Phase 1: 도메인 모델 단위 테스트 (TDD - 테스트 먼저)

순수 데이터 클래스로 외부 의존성 없이 동작해야 합니다.
기존 코드에서 사용하는 dict 기반 데이터를 타입이 있는 모델로 정의합니다.
"""
import math
import pytest

from trading_bot.models.order import Order, OrderSide, OrderType
from trading_bot.models.holding import Holding
from trading_bot.models.trading_state import ReverseState, LedgerRecord


# ==============================================================
# 1. Order 모델 테스트
# ==============================================================
class TestOrderSide:
    def test_buy_value(self):
        assert OrderSide.BUY == "BUY"

    def test_sell_value(self):
        assert OrderSide.SELL == "SELL"


class TestOrderType:
    def test_loc(self):
        assert OrderType.LOC == "LOC"

    def test_limit(self):
        assert OrderType.LIMIT == "LIMIT"

    def test_moc(self):
        assert OrderType.MOC == "MOC"

    def test_moo(self):
        assert OrderType.MOO == "MOO"


class TestOrder:
    def test_create_buy_order(self):
        order = Order(
            side=OrderSide.BUY,
            price=50.0,
            qty=10,
            order_type=OrderType.LOC,
            desc="⚓평단매수"
        )
        assert order.side == OrderSide.BUY
        assert order.price == 50.0
        assert order.qty == 10
        assert order.order_type == OrderType.LOC
        assert order.desc == "⚓평단매수"

    def test_create_sell_order(self):
        order = Order(
            side=OrderSide.SELL,
            price=55.0,
            qty=5,
            order_type=OrderType.LIMIT,
            desc="🎯목표매도"
        )
        assert order.side == OrderSide.SELL
        assert order.price == 55.0

    def test_moc_order_zero_price(self):
        """MOC 주문은 가격 0 허용"""
        order = Order(
            side=OrderSide.SELL,
            price=0,
            qty=10,
            order_type=OrderType.MOC,
            desc="🛡️의무매도"
        )
        assert order.price == 0

    def test_order_amount(self):
        order = Order(side=OrderSide.BUY, price=50.0, qty=10,
                      order_type=OrderType.LOC, desc="test")
        assert order.amount == 500.0

    def test_order_amount_zero_price(self):
        order = Order(side=OrderSide.SELL, price=0, qty=10,
                      order_type=OrderType.MOC, desc="test")
        assert order.amount == 0.0

    def test_to_dict(self):
        """기존 코드와의 호환을 위한 dict 변환"""
        order = Order(
            side=OrderSide.BUY,
            price=50.0,
            qty=10,
            order_type=OrderType.LOC,
            desc="⚓평단매수"
        )
        d = order.to_dict()
        assert d == {
            "side": "BUY",
            "price": 50.0,
            "qty": 10,
            "type": "LOC",
            "desc": "⚓평단매수"
        }

    def test_from_dict(self):
        """기존 dict 형식에서 Order 생성"""
        d = {"side": "BUY", "price": 50.0, "qty": 10, "type": "LOC", "desc": "test"}
        order = Order.from_dict(d)
        assert order.side == OrderSide.BUY
        assert order.price == 50.0
        assert order.qty == 10
        assert order.order_type == OrderType.LOC
        assert order.desc == "test"

    def test_from_dict_roundtrip(self):
        """dict → Order → dict 왕복 변환"""
        original = {"side": "SELL", "price": 55.0, "qty": 5, "type": "LIMIT", "desc": "🎯목표매도"}
        order = Order.from_dict(original)
        result = order.to_dict()
        assert result == original


# ==============================================================
# 2. Holding 모델 테스트
# ==============================================================
class TestHolding:
    def test_create_holding(self):
        h = Holding(ticker="TQQQ", qty=29, avg_price=48.40,
                    total_invested=1884.0, total_sold=520.0)
        assert h.ticker == "TQQQ"
        assert h.qty == 29
        assert h.avg_price == 48.40

    def test_empty_holding(self):
        h = Holding.empty("SOXL")
        assert h.ticker == "SOXL"
        assert h.qty == 0
        assert h.avg_price == 0.0
        assert h.total_invested == 0.0
        assert h.total_sold == 0.0

    def test_profit(self):
        h = Holding(ticker="TQQQ", qty=0, avg_price=0.0,
                    total_invested=1000.0, total_sold=1200.0)
        assert h.profit == 200.0

    def test_profit_negative(self):
        h = Holding(ticker="TQQQ", qty=0, avg_price=0.0,
                    total_invested=1000.0, total_sold=800.0)
        assert h.profit == -200.0

    def test_yield_pct(self):
        h = Holding(ticker="TQQQ", qty=0, avg_price=0.0,
                    total_invested=1000.0, total_sold=1100.0)
        assert h.yield_pct == pytest.approx(10.0)

    def test_yield_pct_zero_invested(self):
        h = Holding(ticker="TQQQ", qty=0, avg_price=0.0,
                    total_invested=0.0, total_sold=0.0)
        assert h.yield_pct == 0.0

    def test_current_value(self):
        h = Holding(ticker="TQQQ", qty=10, avg_price=50.0,
                    total_invested=500.0, total_sold=0.0)
        assert h.current_value(55.0) == 550.0

    def test_unrealized_pnl(self):
        h = Holding(ticker="TQQQ", qty=10, avg_price=50.0,
                    total_invested=500.0, total_sold=0.0)
        assert h.unrealized_pnl(55.0) == 50.0  # (55-50)*10

    def test_is_empty(self):
        assert Holding.empty("TQQQ").is_empty
        h = Holding(ticker="TQQQ", qty=1, avg_price=50.0,
                    total_invested=50.0, total_sold=0.0)
        assert not h.is_empty


# ==============================================================
# 3. ReverseState 모델 테스트
# ==============================================================
class TestReverseState:
    def test_create_active(self):
        rs = ReverseState(
            is_active=True,
            day_count=3,
            exit_target=-15.0,
            last_update_date="2025-03-12"
        )
        assert rs.is_active == True
        assert rs.day_count == 3
        assert rs.exit_target == -15.0

    def test_default_inactive(self):
        rs = ReverseState.inactive()
        assert rs.is_active == False
        assert rs.day_count == 0
        assert rs.exit_target == 0.0
        assert rs.last_update_date == ""

    def test_to_dict(self):
        rs = ReverseState(is_active=True, day_count=2,
                          exit_target=-10.0, last_update_date="2025-03-12")
        d = rs.to_dict()
        assert d == {
            "is_active": True,
            "day_count": 2,
            "exit_target": -10.0,
            "last_update_date": "2025-03-12"
        }

    def test_from_dict(self):
        d = {"is_active": True, "day_count": 5,
             "exit_target": -20.0, "last_update_date": "2025-03-15"}
        rs = ReverseState.from_dict(d)
        assert rs.is_active == True
        assert rs.day_count == 5

    def test_from_dict_missing_keys_uses_defaults(self):
        """기존 데이터에 키가 없어도 안전하게 생성"""
        rs = ReverseState.from_dict({})
        assert rs.is_active == False
        assert rs.day_count == 0

    def test_is_day_one(self):
        rs = ReverseState(is_active=True, day_count=1,
                          exit_target=-15.0, last_update_date="2025-03-12")
        assert rs.is_day_one == True

        rs2 = ReverseState(is_active=True, day_count=3,
                           exit_target=-15.0, last_update_date="2025-03-12")
        assert rs2.is_day_one == False


# ==============================================================
# 4. LedgerRecord 모델 테스트
# ==============================================================
class TestLedgerRecord:
    def test_create_record(self):
        rec = LedgerRecord(
            id=1, date="2025-03-10", ticker="TQQQ",
            side="BUY", price=50.0, qty=10,
            avg_price=50.0, exec_id="INIT_123",
            desc="최초스냅샷", is_reverse=False
        )
        assert rec.ticker == "TQQQ"
        assert rec.side == "BUY"
        assert rec.amount == 500.0

    def test_to_dict(self):
        rec = LedgerRecord(
            id=1, date="2025-03-10", ticker="TQQQ",
            side="BUY", price=50.0, qty=10,
            avg_price=50.0, exec_id="INIT_123",
            desc="최초스냅샷", is_reverse=False
        )
        d = rec.to_dict()
        assert d["id"] == 1
        assert d["ticker"] == "TQQQ"
        assert d["price"] == 50.0

    def test_from_dict(self):
        d = {
            "id": 1, "date": "2025-03-10", "ticker": "TQQQ",
            "side": "BUY", "price": 50.0, "qty": 10,
            "avg_price": 50.0, "exec_id": "INIT_123",
            "desc": "최초스냅샷", "is_reverse": False
        }
        rec = LedgerRecord.from_dict(d)
        assert rec.id == 1
        assert rec.price == 50.0

    def test_from_dict_missing_optional_fields(self):
        """최소 필드만 있어도 생성 가능"""
        d = {
            "id": 1, "date": "2025-03-10", "ticker": "TQQQ",
            "side": "BUY", "price": 50.0, "qty": 10
        }
        rec = LedgerRecord.from_dict(d)
        assert rec.avg_price == 0.0
        assert rec.exec_id == ""
        assert rec.desc == ""
        assert rec.is_reverse == False

    def test_from_dict_roundtrip(self):
        original = {
            "id": 5, "date": "2025-03-12", "ticker": "SOXL",
            "side": "SELL", "price": 30.0, "qty": 15,
            "avg_price": 25.0, "exec_id": "REG_999",
            "desc": "🌟별값매도", "is_reverse": True
        }
        rec = LedgerRecord.from_dict(original)
        result = rec.to_dict()
        assert result == original

    def test_is_buy(self):
        rec = LedgerRecord(id=1, date="", ticker="TQQQ",
                           side="BUY", price=50.0, qty=10)
        assert rec.is_buy == True
        assert rec.is_sell == False

    def test_is_sell(self):
        rec = LedgerRecord(id=1, date="", ticker="TQQQ",
                           side="SELL", price=55.0, qty=5)
        assert rec.is_buy == False
        assert rec.is_sell == True
