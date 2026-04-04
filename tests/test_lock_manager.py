"""
Phase 2: LockManager 단위 테스트

매매 잠금 + 에스크로 관리 로직의 독립 테스트.
"""
import pytest
from unittest.mock import patch
import datetime
import pytz

from trading_bot.storage.lock_manager import LockManager
from trading_bot.storage.file_utils import FileUtils


@pytest.fixture
def lm(tmp_path):
    fu = FileUtils()
    locks_path = str(tmp_path / "trade_locks.json")
    return LockManager(fu, locks_path)


class TestEscrow:
    def test_default_zero(self, lm):
        assert lm.get_escrow("TQQQ") == 0.0

    def test_set_and_get(self, lm):
        lm.set_escrow("TQQQ", 500.0)
        assert lm.get_escrow("TQQQ") == 500.0

    def test_add_escrow(self, lm):
        lm.set_escrow("TQQQ", 100.0)
        lm.add_escrow("TQQQ", 200.0)
        assert lm.get_escrow("TQQQ") == 300.0

    def test_clear_escrow(self, lm):
        lm.set_escrow("TQQQ", 500.0)
        lm.clear_escrow("TQQQ")
        assert lm.get_escrow("TQQQ") == 0.0

    def test_total_locked(self, lm):
        lm.set_escrow("TQQQ", 300.0)
        lm.set_escrow("SOXL", 200.0)
        assert lm.get_total_locked() == 500.0

    def test_total_locked_exclude(self, lm):
        lm.set_escrow("TQQQ", 300.0)
        lm.set_escrow("SOXL", 200.0)
        assert lm.get_total_locked(exclude_ticker="TQQQ") == 200.0


class TestTradeLocks:
    def test_check_unlocked(self, lm):
        assert lm.check_lock("TQQQ", "REG") == False

    def test_set_and_check(self, lm):
        lm.set_lock("TQQQ", "REG")
        assert lm.check_lock("TQQQ", "REG") == True

    def test_reset_preserves_escrow(self, lm):
        lm.set_escrow("TQQQ", 500.0)
        lm.set_lock("TQQQ", "REG")
        lm.reset_all()
        assert lm.get_escrow("TQQQ") == 500.0
        # 잠금은 해제되어야 함 (날짜 기반이므로 새 날짜로 체크)
        # reset_all은 ESCROW_ 제외 전부 삭제

    def test_reset_for_ticker(self, lm):
        lm.set_lock("TQQQ", "REG")
        lm.set_lock("SOXL", "REG")
        lm.reset_for_ticker("TQQQ")
        # SOXL 잠금은 유지
        assert lm.check_lock("SOXL", "REG") == True
