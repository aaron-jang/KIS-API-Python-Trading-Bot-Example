"""
QueueLedger 핵심 기능 테스트

LIFO 로트 관리, 원자적 쓰기, 자가 치유, 스레드 안전성 검증
"""
import os
import json
import threading
import pytest


@pytest.fixture
def ql(tmp_path):
    from trading_bot.strategy.queue_ledger import QueueLedger
    file_path = str(tmp_path / "data" / "queue_ledger.json")
    return QueueLedger(file_path=file_path)


class TestAddLotBasic:
    """add_lot 기본 동작"""

    def test_add_single_lot(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        q = ql.get_queue("SOXL")
        assert len(q) == 1
        assert q[0]["qty"] == 10
        assert q[0]["price"] == 50.0

    def test_add_lot_returns_none(self, ql):
        result = ql.add_lot("SOXL", 5, 30.0)
        assert result is None

    def test_get_total_qty(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        assert ql.get_total_qty("SOXL") == 10

    def test_empty_ticker_returns_empty(self, ql):
        assert ql.get_queue("TQQQ") == []
        assert ql.get_total_qty("TQQQ") == 0

    def test_add_zero_qty_ignored(self, ql):
        ql.add_lot("SOXL", 0, 50.0)
        assert ql.get_queue("SOXL") == []

    def test_add_negative_qty_ignored(self, ql):
        ql.add_lot("SOXL", -5, 50.0)
        assert ql.get_queue("SOXL") == []

    def test_add_zero_price_rejected(self, ql):
        ql.add_lot("SOXL", 10, 0.0)
        assert ql.get_queue("SOXL") == []

    def test_add_none_price_rejected(self, ql):
        ql.add_lot("SOXL", 10, None)
        assert ql.get_queue("SOXL") == []


class TestSameDayMerge:
    """동일 일자 로트 병합"""

    def test_same_day_merge_qty(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        ql.add_lot("SOXL", 5, 40.0)
        q = ql.get_queue("SOXL")
        assert len(q) == 1
        assert q[0]["qty"] == 15

    def test_same_day_merge_weighted_avg_price(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        ql.add_lot("SOXL", 10, 40.0)
        q = ql.get_queue("SOXL")
        assert q[0]["price"] == 45.0

    def test_same_day_merge_unequal_qty(self, ql):
        ql.add_lot("SOXL", 10, 100.0)
        ql.add_lot("SOXL", 5, 50.0)
        q = ql.get_queue("SOXL")
        expected_price = (10 * 100.0 + 5 * 50.0) / 15
        assert q[0]["price"] == pytest.approx(expected_price, abs=0.01)


class TestPopLots:
    """LIFO pop 동작"""

    def test_pop_exact_qty(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        popped = ql.pop_lots("SOXL", 10)
        assert popped == 10
        assert ql.get_total_qty("SOXL") == 0

    def test_pop_partial(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        popped = ql.pop_lots("SOXL", 3)
        assert popped == 3
        q = ql.get_queue("SOXL")
        assert q[0]["qty"] == 7

    def test_pop_zero_returns_zero(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        assert ql.pop_lots("SOXL", 0) == 0
        assert ql.get_total_qty("SOXL") == 10

    def test_pop_more_than_available(self, ql):
        ql.add_lot("SOXL", 5, 50.0)
        popped = ql.pop_lots("SOXL", 10)
        assert popped == 5
        assert ql.get_total_qty("SOXL") == 0

    def test_pop_from_empty_queue(self, ql):
        popped = ql.pop_lots("SOXL", 5)
        assert popped == 0


class TestGhostLotCleaning:
    """유령 로트(0주) 자동 청소"""

    def test_ghost_lot_filtered_on_get(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        # 직접 0주 로트 주입
        with ql._lock:
            data = ql._load_unsafe()
            data["SOXL"].append({"qty": 0, "price": 30.0, "date": "2026-01-01", "type": "GHOST"})
            ql._save_unsafe(data)

        q = ql.get_queue("SOXL")
        assert all(int(float(lot.get("qty", 0))) > 0 for lot in q)


class TestSyncWithBroker:
    """브로커 잔고 동기화 (CALIB)"""

    def test_sync_no_change_needed(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        changed = ql.sync_with_broker("SOXL", 10, 50.0)
        assert changed is False

    def test_sync_add_missing_qty(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        changed = ql.sync_with_broker("SOXL", 15, 48.0)
        assert changed is True
        assert ql.get_total_qty("SOXL") == 15

    def test_sync_remove_excess_qty(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        changed = ql.sync_with_broker("SOXL", 7, 50.0)
        assert changed is True
        assert ql.get_total_qty("SOXL") == 7

    def test_sync_add_rejects_zero_price(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        changed = ql.sync_with_broker("SOXL", 15, 0.0)
        assert changed is True
        # 가격 불명이면 기존 로트의 가격을 사용
        assert ql.get_total_qty("SOXL") == 15

    def test_sync_from_empty_to_new(self, ql):
        changed = ql.sync_with_broker("SOXL", 5, 45.0)
        assert changed is True
        assert ql.get_total_qty("SOXL") == 5

    def test_sync_to_zero(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        changed = ql.sync_with_broker("SOXL", 0)
        assert changed is True
        assert ql.get_total_qty("SOXL") == 0


class TestAtomicWriteAndBackup:
    """원자적 쓰기 및 백업 자가 치유"""

    def test_file_persists_after_add(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        assert os.path.exists(ql.file_path)
        with open(ql.file_path, 'r') as f:
            data = json.load(f)
        assert "SOXL" in data

    def test_backup_created_after_save(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        assert os.path.exists(ql.file_path + ".bak")

    def test_self_healing_from_backup(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        # 원본 파일 손상
        with open(ql.file_path, 'w') as f:
            f.write("{invalid json")
        # 백업에서 복원되어야 함
        q = ql.get_queue("SOXL")
        assert len(q) == 1
        assert q[0]["qty"] == 10

    def test_both_corrupted_raises_error(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        with open(ql.file_path, 'w') as f:
            f.write("{bad")
        with open(ql.file_path + ".bak", 'w') as f:
            f.write("{bad")
        with pytest.raises(RuntimeError, match="FATAL ERROR"):
            ql.get_queue("SOXL")


class TestThreadSafety:
    """스레드 안전성"""

    def test_concurrent_add_lots(self, ql):
        errors = []

        def add_lots(ticker, count):
            try:
                for _ in range(count):
                    ql.add_lot(ticker, 1, 50.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_lots, args=("SOXL", 50)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        total = ql.get_total_qty("SOXL")
        assert total == 200

    def test_concurrent_add_and_pop(self, ql):
        ql.add_lot("SOXL", 100, 50.0)
        errors = []

        def pop_lots():
            try:
                ql.pop_lots("SOXL", 10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=pop_lots) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert ql.get_total_qty("SOXL") == 50


class TestMultiTicker:
    """다중 종목 격리"""

    def test_tickers_independent(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        ql.add_lot("TQQQ", 20, 30.0)
        assert ql.get_total_qty("SOXL") == 10
        assert ql.get_total_qty("TQQQ") == 20

    def test_pop_one_ticker_no_affect_other(self, ql):
        ql.add_lot("SOXL", 10, 50.0)
        ql.add_lot("TQQQ", 20, 30.0)
        ql.pop_lots("SOXL", 5)
        assert ql.get_total_qty("SOXL") == 5
        assert ql.get_total_qty("TQQQ") == 20
