"""
Phase 2: LedgerStore 단위 테스트

장부 CRUD 및 보유현황 계산 로직의 독립 테스트.
ConfigManager의 장부 관련 메서드 동작을 정확히 보존해야 합니다.
"""
import math
import os
import shutil
import pytest

from trading_bot.storage.ledger_store import LedgerStore
from trading_bot.storage.file_utils import FileUtils

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def store(tmp_path):
    fu = FileUtils()
    ledger_path = str(tmp_path / "manual_ledger.json")
    history_path = str(tmp_path / "manual_history.json")
    split_history_path = str(tmp_path / "split_history.json")
    return LedgerStore(fu, ledger_path, history_path, split_history_path)


@pytest.fixture
def store_with_data(tmp_path):
    fu = FileUtils()
    ledger_path = str(tmp_path / "manual_ledger.json")
    history_path = str(tmp_path / "manual_history.json")
    split_history_path = str(tmp_path / "split_history.json")
    shutil.copy(os.path.join(FIXTURES_DIR, "sample_ledger.json"), ledger_path)
    return LedgerStore(fu, ledger_path, history_path, split_history_path)


class TestLedgerCRUD:
    def test_get_empty_ledger(self, store):
        assert store.get_ledger() == []

    def test_get_ledger_with_data(self, store_with_data):
        ledger = store_with_data.get_ledger()
        assert len(ledger) == 6

    def test_clear_ticker(self, store_with_data):
        store_with_data.clear_for_ticker("TQQQ")
        ledger = store_with_data.get_ledger()
        tqqq = [r for r in ledger if r["ticker"] == "TQQQ"]
        soxl = [r for r in ledger if r["ticker"] == "SOXL"]
        assert len(tqqq) == 0
        assert len(soxl) == 2

    def test_overwrite_genesis_blocks_existing(self, store_with_data, capsys):
        store_with_data.overwrite_genesis("TQQQ", [], 50.0)
        captured = capsys.readouterr()
        assert "보안 차단" in captured.out

    def test_overwrite_genesis_new_ticker(self, store_with_data):
        records = [{"date": "2025-04-01", "side": "BUY", "price": 100.0, "qty": 5}]
        store_with_data.overwrite_genesis("AAPL", records, 100.0)
        ledger = store_with_data.get_ledger()
        aapl = [r for r in ledger if r["ticker"] == "AAPL"]
        assert len(aapl) == 1
        assert "GENESIS" in aapl[0]["exec_id"]

    def test_apply_stock_split(self, store_with_data):
        store_with_data.apply_stock_split("TQQQ", 2)
        ledger = store_with_data.get_ledger()
        first = [r for r in ledger if r["ticker"] == "TQQQ"][0]
        assert first["qty"] == 20   # 10 * 2
        assert first["price"] == 25.0  # 50 / 2


class TestHoldingsCalculation:
    def test_calculate_tqqq(self, store_with_data):
        """TQQQ: BUY 10+14+15=39, SELL 10 → 29"""
        qty, avg, invested, sold = store_with_data.calculate_holdings("TQQQ")
        assert qty == 29
        expected_invested = math.ceil((50*10 + 48.5*14 + 47*15) * 100) / 100.0
        assert invested == expected_invested
        assert sold == math.ceil(520.0 * 100) / 100.0
        assert avg == 48.40

    def test_calculate_soxl(self, store_with_data):
        qty, avg, invested, sold = store_with_data.calculate_holdings("SOXL")
        assert qty == 48
        assert avg == 24.40

    def test_calculate_empty(self, store_with_data):
        qty, avg, invested, sold = store_with_data.calculate_holdings("AAPL")
        assert qty == 0
        assert avg == 0.0

    def test_calibrate_prices(self, store_with_data):
        exec_history = [
            {"sll_buy_dvsn_cd": "02", "ft_ccld_qty": "10",
             "ft_ccld_unpr3": "48.50", "ord_tmd": "170500"},
            {"sll_buy_dvsn_cd": "01", "ft_ccld_qty": "8",
             "ft_ccld_unpr3": "52.00", "ord_tmd": "170400"},
        ]
        changed = store_with_data.calibrate_prices("TQQQ", "2025-03-11", exec_history)
        assert isinstance(changed, int)


class TestV14State:
    def test_empty_ledger(self, store):
        t_val, budget, rem = store.calculate_v14_state("TQQQ", seed=6720.0, split=40.0)
        assert t_val == 0.0
        assert budget == 168.0  # 6720/40

    def test_with_data(self, store_with_data):
        t_val, budget, rem = store_with_data.calculate_v14_state("TQQQ", seed=6720.0, split=40.0)
        assert t_val >= 0.0
        assert budget >= 0.0
        assert rem >= 0.0


class TestSplitHistory:
    def test_get_default(self, store):
        assert store.get_last_split_date("TQQQ") == ""

    def test_set_and_get(self, store):
        store.set_last_split_date("TQQQ", "2025-03-15")
        assert store.get_last_split_date("TQQQ") == "2025-03-15"
