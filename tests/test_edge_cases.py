"""
Phase 5: 엣지 케이스 테스트 보강

기존 특성 테스트에서 미처 다루지 못한 경계 조건을 검증합니다.
"""
import math
import pytest
from strategy import InfiniteStrategy


# ==============================================================
# 1. 극단적 가격/수량 엣지 케이스
# ==============================================================
class TestExtremeValues:

    def test_very_small_price(self, cfg):
        """0.01달러 페니주식에서도 동작하는지"""
        s = InfiniteStrategy(cfg)
        plan = s.get_plan(
            ticker="TQQQ", current_price=0.01, avg_price=0.02,
            qty=1000, prev_close=0.02, market_type="REG", available_cash=100
        )
        assert plan["process_status"] != "⛔가격오류"
        for o in plan["orders"]:
            if o["type"] not in ["MOC", "MOO"]:
                assert o["price"] >= 0.01

    def test_very_large_qty(self, cfg):
        """매우 큰 수량에서도 크래시 없이 동작"""
        s = InfiniteStrategy(cfg)
        plan = s.get_plan(
            ticker="TQQQ", current_price=50.0, avg_price=50.0,
            qty=100000, prev_close=49.0, market_type="REG", available_cash=10000
        )
        assert "process_status" in plan

    def test_avg_price_higher_than_current(self, cfg):
        """평단가 > 현재가 (손실 상태)에서 정상 동작"""
        s = InfiniteStrategy(cfg)
        plan = s.get_plan(
            ticker="TQQQ", current_price=30.0, avg_price=50.0,
            qty=20, prev_close=31.0, market_type="REG", available_cash=10000
        )
        assert len(plan["orders"]) > 0

    def test_zero_available_cash(self, cfg):
        """잔고 0에서도 매도 주문은 생성"""
        s = InfiniteStrategy(cfg)
        plan = s.get_plan(
            ticker="TQQQ", current_price=50.0, avg_price=48.0,
            qty=20, prev_close=49.0, market_type="REG", available_cash=0
        )
        sell_orders = [o for o in plan["orders"] if o["side"] == "SELL"]
        assert len(sell_orders) > 0


# ==============================================================
# 2. LedgerStore 엣지 케이스
# ==============================================================
class TestLedgerStoreEdge:

    def test_stock_split_zero_ratio(self, cfg_with_ledger):
        """ratio=0이면 아무것도 변경하지 않음"""
        from trading_bot.storage.ledger_store import LedgerStore
        from trading_bot.storage.file_utils import FileUtils
        before = cfg_with_ledger.get_ledger()
        cfg_with_ledger.apply_stock_split("TQQQ", 0)
        after = cfg_with_ledger.get_ledger()
        assert before == after

    def test_calculate_holdings_all_sold(self, cfg):
        """전량 매도 후 qty=0"""
        from trading_bot.storage.file_utils import FileUtils
        from trading_bot.storage.ledger_store import LedgerStore
        import os, json

        fu = FileUtils()
        path = os.path.join(os.getcwd(), "data", "test_ledger.json")
        records = [
            {"id": 1, "ticker": "X", "side": "BUY", "price": 10.0, "qty": 10, "avg_price": 10.0},
            {"id": 2, "ticker": "X", "side": "SELL", "price": 12.0, "qty": 10, "avg_price": 10.0},
        ]
        fu.save_json(path, records)
        store = LedgerStore(fu, path, "h.json", "s.json")

        qty, avg, invested, sold = store.calculate_holdings("X")
        assert qty == 0
        assert avg == 0.0
        assert sold > 0


# ==============================================================
# 3. LockManager 엣지 케이스
# ==============================================================
class TestLockManagerEdge:

    def test_clear_nonexistent_escrow(self, tmp_path):
        """존재하지 않는 에스크로 삭제 시 에러 없음"""
        from trading_bot.storage.lock_manager import LockManager
        from trading_bot.storage.file_utils import FileUtils
        lm = LockManager(FileUtils(), str(tmp_path / "locks.json"))
        lm.clear_escrow("NONEXISTENT")  # 에러 없이 통과
        assert lm.get_escrow("NONEXISTENT") == 0.0

    def test_total_locked_empty(self, tmp_path):
        """잠금 파일이 비어있을 때 total=0"""
        from trading_bot.storage.lock_manager import LockManager
        from trading_bot.storage.file_utils import FileUtils
        lm = LockManager(FileUtils(), str(tmp_path / "locks.json"))
        assert lm.get_total_locked() == 0.0


# ==============================================================
# 4. TradingConfig 엣지 케이스
# ==============================================================
class TestTradingConfigEdge:

    def test_unknown_ticker_seed(self, tmp_path):
        """등록되지 않은 종목도 기본값 반환"""
        from trading_bot.storage.trading_config import TradingConfig
        from trading_bot.storage.file_utils import FileUtils
        tc = TradingConfig(FileUtils(), base_dir=str(tmp_path))
        assert tc.get_seed("UNKNOWN") == 6720.0

    def test_unknown_ticker_split(self, tmp_path):
        from trading_bot.storage.trading_config import TradingConfig
        from trading_bot.storage.file_utils import FileUtils
        tc = TradingConfig(FileUtils(), base_dir=str(tmp_path))
        assert tc.get_split_count("UNKNOWN") == 40.0

    def test_reverse_state_not_leaking(self, tmp_path):
        """한 종목의 리버스 설정이 다른 종목에 영향 없음"""
        from trading_bot.storage.trading_config import TradingConfig
        from trading_bot.storage.file_utils import FileUtils
        tc = TradingConfig(FileUtils(), base_dir=str(tmp_path))
        tc.set_reverse_state("TQQQ", True, 5, -20.0, "2025-04-01")
        state = tc.get_reverse_state("SOXL")
        assert state["is_active"] == False
        assert state["day_count"] == 0


# ==============================================================
# 5. 모델 dict 변환 엣지 케이스
# ==============================================================
class TestModelEdgeCases:

    def test_order_from_dict_missing_desc(self):
        from trading_bot.models.order import Order
        d = {"side": "BUY", "price": 50.0, "qty": 10, "type": "LOC"}
        order = Order.from_dict(d)
        assert order.desc == ""

    def test_ledger_record_amount_zero_qty(self):
        from trading_bot.models.trading_state import LedgerRecord
        rec = LedgerRecord(id=1, date="", ticker="X", side="BUY", price=50.0, qty=0)
        assert rec.amount == 0.0

    def test_holding_unrealized_pnl_empty(self):
        from trading_bot.models.holding import Holding
        h = Holding.empty("X")
        assert h.unrealized_pnl(50.0) == 0.0

    def test_reverse_state_from_dict_partial(self):
        from trading_bot.models.trading_state import ReverseState
        rs = ReverseState.from_dict({"is_active": True})
        assert rs.is_active == True
        assert rs.day_count == 0
        assert rs.exit_target == 0.0
