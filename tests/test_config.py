"""
Phase 0: ConfigManager 특성 테스트 (Characterization Test)

기존 ConfigManager의 현재 동작을 캡처하여 리팩토링 시 안전망 역할을 합니다.
"""
import json
import os
import math
import pytest


# ==============================================================
# 1. 기본 JSON I/O 테스트
# ==============================================================
class TestConfigIO:
    """_load_json / _save_json 의 원자적 쓰기/읽기 동작 검증"""

    def test_load_json_returns_default_when_file_missing(self, cfg):
        result = cfg._load_json("nonexistent.json", {"key": "default"})
        assert result == {"key": "default"}

    def test_load_json_returns_empty_dict_when_no_default(self, cfg):
        result = cfg._load_json("nonexistent.json")
        assert result == {}

    def test_save_and_load_json_roundtrip(self, cfg, tmp_data_dir):
        path = str(tmp_data_dir / "test_roundtrip.json")
        data = {"hello": "world", "number": 42, "korean": "한글테스트"}
        cfg._save_json(path, data)
        loaded = cfg._load_json(path)
        assert loaded == data

    def test_save_json_creates_directory(self, cfg, tmp_data_dir):
        path = str(tmp_data_dir / "sub" / "deep" / "test.json")
        cfg._save_json(path, {"nested": True})
        loaded = cfg._load_json(path)
        assert loaded == {"nested": True}

    def test_load_file_returns_default_when_missing(self, cfg):
        result = cfg._load_file("nonexistent.dat", "fallback")
        assert result == "fallback"

    def test_save_and_load_file_roundtrip(self, cfg, tmp_data_dir):
        path = str(tmp_data_dir / "test.dat")
        cfg._save_file(path, "hello_value")
        loaded = cfg._load_file(path)
        assert loaded == "hello_value"

    def test_load_json_handles_corrupted_file(self, cfg, tmp_data_dir):
        path = str(tmp_data_dir / "corrupted.json")
        with open(path, "w") as f:
            f.write("{invalid json content!!!")
        result = cfg._load_json(path, {"fallback": True})
        assert result == {"fallback": True}
        # 백업 파일이 생성되었는지 확인
        backups = [f for f in os.listdir(str(tmp_data_dir)) if "corrupted.json.bak_" in f]
        assert len(backups) == 1


# ==============================================================
# 2. 장부(Ledger) CRUD 테스트
# ==============================================================
class TestLedger:
    """장부 조회/저장/계산 동작 캡처"""

    def test_get_ledger_empty(self, cfg):
        assert cfg.get_ledger() == []

    def test_get_ledger_with_data(self, cfg_with_ledger, sample_ledger):
        ledger = cfg_with_ledger.get_ledger()
        assert len(ledger) == len(sample_ledger)
        assert ledger[0]["ticker"] == "TQQQ"
        assert ledger[0]["price"] == 50.00

    def test_clear_ledger_for_ticker(self, cfg_with_ledger):
        cfg_with_ledger.clear_ledger_for_ticker("TQQQ")
        ledger = cfg_with_ledger.get_ledger()
        tqqq_records = [r for r in ledger if r["ticker"] == "TQQQ"]
        soxl_records = [r for r in ledger if r["ticker"] == "SOXL"]
        assert len(tqqq_records) == 0
        assert len(soxl_records) == 2  # SOXL은 그대로

    def test_calculate_holdings_tqqq(self, cfg_with_ledger):
        """TQQQ: BUY 10+14+15=39, SELL 10 → 순보유 29"""
        qty, avg, invested, sold = cfg_with_ledger.calculate_holdings("TQQQ")
        assert qty == 29
        assert invested == math.ceil((50*10 + 48.5*14 + 47*15) * 100) / 100.0
        assert sold == math.ceil((52*10) * 100) / 100.0
        assert avg == 48.40  # 마지막 레코드의 avg_price

    def test_calculate_holdings_soxl(self, cfg_with_ledger):
        """SOXL: BUY 20+28=48, SELL 0 → 순보유 48"""
        qty, avg, invested, sold = cfg_with_ledger.calculate_holdings("SOXL")
        assert qty == 48
        assert sold == 0.0
        assert avg == 24.40  # 마지막 레코드의 avg_price

    def test_calculate_holdings_empty_ticker(self, cfg_with_ledger):
        qty, avg, invested, sold = cfg_with_ledger.calculate_holdings("AAPL")
        assert qty == 0
        assert avg == 0.0

    def test_overwrite_genesis_ledger_blocks_duplicate(self, cfg_with_ledger, capsys):
        """이미 존재하는 종목에 Genesis를 시도하면 차단"""
        cfg_with_ledger.overwrite_genesis_ledger("TQQQ", [], 50.0)
        captured = capsys.readouterr()
        assert "보안 차단" in captured.out

    def test_overwrite_genesis_ledger_new_ticker(self, cfg_with_ledger):
        """새 종목은 Genesis 가능"""
        genesis_records = [
            {"date": "2025-03-15", "side": "BUY", "price": 100.0, "qty": 5}
        ]
        cfg_with_ledger.overwrite_genesis_ledger("AAPL", genesis_records, 100.0)
        ledger = cfg_with_ledger.get_ledger()
        aapl = [r for r in ledger if r["ticker"] == "AAPL"]
        assert len(aapl) == 1
        assert aapl[0]["avg_price"] == 100.0
        assert "GENESIS" in aapl[0]["exec_id"]

    def test_apply_stock_split(self, cfg_with_ledger):
        """2:1 액면 분할 시 수량 2배, 가격 1/2"""
        cfg_with_ledger.apply_stock_split("TQQQ", 2)
        ledger = cfg_with_ledger.get_ledger()
        tqqq = [r for r in ledger if r["ticker"] == "TQQQ"]
        first_buy = tqqq[0]
        assert first_buy["qty"] == 20  # 10 * 2
        assert first_buy["price"] == 25.0  # 50 / 2


# ==============================================================
# 3. 설정값 (Seed/Split/Target/Version) 테스트
# ==============================================================
class TestTradingConfig:
    """종목별 설정 읽기/쓰기 동작 캡처"""

    def test_default_seed(self, cfg):
        assert cfg.get_seed("TQQQ") == 6720.0
        assert cfg.get_seed("SOXL") == 6720.0

    def test_set_and_get_seed(self, cfg):
        cfg.set_seed("TQQQ", 10000.0)
        assert cfg.get_seed("TQQQ") == 10000.0
        # SOXL은 변경되지 않아야 함
        assert cfg.get_seed("SOXL") == 6720.0

    def test_default_split_count(self, cfg):
        assert cfg.get_split_count("TQQQ") == 40.0

    def test_default_target_profit(self, cfg):
        assert cfg.get_target_profit("TQQQ") == 10.0
        assert cfg.get_target_profit("SOXL") == 12.0

    def test_default_version(self, cfg):
        assert cfg.get_version("TQQQ") == "V14"

    def test_set_and_get_version(self, cfg):
        cfg.set_version("TQQQ", "V17")
        assert cfg.get_version("TQQQ") == "V17"

    def test_default_compound_rate(self, cfg):
        assert cfg.get_compound_rate("TQQQ") == 70.0

    def test_set_and_get_compound_rate(self, cfg):
        cfg.set_compound_rate("SOXL", 50.0)
        assert cfg.get_compound_rate("SOXL") == 50.0

    def test_default_sniper_multiplier(self, cfg):
        assert cfg.get_sniper_multiplier("TQQQ") == 0.9
        assert cfg.get_sniper_multiplier("SOXL") == 1.0

    def test_set_sniper_multiplier(self, cfg):
        cfg.set_sniper_multiplier("TQQQ", 1.5)
        assert cfg.get_sniper_multiplier("TQQQ") == 1.5


# ==============================================================
# 4. 잠금(Lock) / 에스크로(Escrow) 테스트
# ==============================================================
class TestLocksAndEscrow:
    """매매 잠금 및 에스크로 동작 캡처"""

    def test_escrow_default_zero(self, cfg):
        assert cfg.get_escrow_cash("TQQQ") == 0.0

    def test_set_and_get_escrow(self, cfg):
        cfg.set_escrow_cash("TQQQ", 500.0)
        assert cfg.get_escrow_cash("TQQQ") == 500.0

    def test_add_escrow(self, cfg):
        cfg.set_escrow_cash("TQQQ", 100.0)
        cfg.add_escrow_cash("TQQQ", 200.0)
        assert cfg.get_escrow_cash("TQQQ") == 300.0

    def test_clear_escrow(self, cfg):
        cfg.set_escrow_cash("TQQQ", 500.0)
        cfg.clear_escrow_cash("TQQQ")
        assert cfg.get_escrow_cash("TQQQ") == 0.0

    def test_total_locked_cash(self, cfg):
        cfg.set_escrow_cash("TQQQ", 300.0)
        cfg.set_escrow_cash("SOXL", 200.0)
        total = cfg.get_total_locked_cash()
        assert total == 500.0

    def test_total_locked_cash_exclude(self, cfg):
        cfg.set_escrow_cash("TQQQ", 300.0)
        cfg.set_escrow_cash("SOXL", 200.0)
        total = cfg.get_total_locked_cash(exclude_ticker="TQQQ")
        assert total == 200.0

    def test_reset_locks_preserves_escrow(self, cfg):
        cfg.set_escrow_cash("TQQQ", 500.0)
        cfg.set_lock("TQQQ", "REG")
        cfg.reset_locks()
        # 에스크로는 보존
        assert cfg.get_escrow_cash("TQQQ") == 500.0


# ==============================================================
# 5. 리버스(Reverse) 상태 관리 테스트
# ==============================================================
class TestReverseState:
    """리버스 매매 상태 관리 동작 캡처"""

    def test_default_reverse_state(self, cfg):
        state = cfg.get_reverse_state("TQQQ")
        assert state["is_active"] == False
        assert state["day_count"] == 0
        assert state["exit_target"] == 0.0

    def test_set_reverse_state(self, cfg):
        cfg.set_reverse_state("TQQQ", True, 3, -15.0, "2025-03-12")
        state = cfg.get_reverse_state("TQQQ")
        assert state["is_active"] == True
        assert state["day_count"] == 3
        assert state["exit_target"] == -15.0
        assert state["last_update_date"] == "2025-03-12"

    def test_reverse_state_independent_per_ticker(self, cfg):
        cfg.set_reverse_state("TQQQ", True, 2, -10.0, "2025-03-12")
        state_soxl = cfg.get_reverse_state("SOXL")
        assert state_soxl["is_active"] == False  # SOXL은 영향 없음


# ==============================================================
# 6. 스나이퍼 / 티커 / 시크릿 모드 테스트
# ==============================================================
class TestMiscConfig:
    """기타 설정 동작 캡처"""

    def test_upward_sniper_default(self, cfg):
        assert cfg.get_upward_sniper_mode("TQQQ") == False

    def test_set_upward_sniper(self, cfg):
        cfg.set_upward_sniper_mode("TQQQ", True)
        assert cfg.get_upward_sniper_mode("TQQQ") == True
        assert cfg.get_upward_sniper_mode("SOXL") == False  # 독립

    def test_active_tickers_default(self, cfg):
        assert cfg.get_active_tickers() == ["SOXL", "TQQQ"]

    def test_set_active_tickers(self, cfg):
        cfg.set_active_tickers(["TQQQ"])
        assert cfg.get_active_tickers() == ["TQQQ"]

    def test_secret_mode_default(self, cfg):
        assert cfg.get_secret_mode() == False

    def test_set_secret_mode(self, cfg):
        cfg.set_secret_mode(True)
        assert cfg.get_secret_mode() == True

    def test_chat_id_default_none(self, cfg):
        assert cfg.get_chat_id() is None

    def test_set_chat_id(self, cfg):
        cfg.set_chat_id(123456789)
        assert cfg.get_chat_id() == 123456789


# ==============================================================
# 7. T값 / V14 상태 계산 테스트
# ==============================================================
class TestCalculations:
    """핵심 계산 로직 동작 캡처"""

    def test_get_absolute_t_val(self, cfg):
        # seed=6720, split=40 → one_portion=168
        # qty=10, avg=50 → invested=500 → t_val = 500/168 = 2.9762
        t_val, one_portion = cfg.get_absolute_t_val("TQQQ", 10, 50.0)
        assert one_portion == 168.0  # 6720 / 40
        assert t_val == round(500.0 / 168.0, 4)

    def test_calculate_v14_state_empty(self, cfg):
        """장부가 비어있을 때"""
        t_val, budget, rem = cfg.calculate_v14_state("TQQQ")
        assert t_val == 0.0
        assert budget == 168.0  # base_portion = 6720/40

    def test_calculate_v14_state_with_data(self, cfg_with_ledger):
        """장부 데이터가 있을 때 V14 상태 계산"""
        t_val, budget, rem = cfg_with_ledger.calculate_v14_state("TQQQ")
        # 계산이 0 이상인지 기본 sanity check
        assert t_val >= 0.0
        assert budget >= 0.0
        assert rem >= 0.0

    def test_calibrate_ledger_prices(self, cfg_with_ledger, sample_execution_history):
        """체결 내역으로 장부 가격 보정"""
        changed = cfg_with_ledger.calibrate_ledger_prices(
            "TQQQ", "2025-03-11", sample_execution_history
        )
        # INIT 레코드는 보정 건너뜀, BUY/SELL 레코드만 대상
        assert isinstance(changed, int)


# ==============================================================
# 8. P매매 데이터 테스트
# ==============================================================
class TestPTradeData:
    def test_p_trade_default_empty(self, cfg):
        assert cfg.get_p_trade_data() == {}

    def test_set_and_get_p_trade_data(self, cfg):
        data = {"ticker": "TQQQ", "targets": [{"side": "BUY", "price": 45.0, "qty": 10}]}
        cfg.set_p_trade_data(data)
        assert cfg.get_p_trade_data() == data

    def test_clear_p_trade_data(self, cfg):
        cfg.set_p_trade_data({"some": "data"})
        cfg.clear_p_trade_data()
        assert cfg.get_p_trade_data() == {}
