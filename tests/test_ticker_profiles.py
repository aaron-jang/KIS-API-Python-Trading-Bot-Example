"""
티커 프로필 관리 모듈 테스트
"""
import os
import pytest
from trading_bot.storage import ticker_profiles as tp


@pytest.fixture
def tmp_profiles(tmp_path, monkeypatch):
    """테스트마다 임시 JSON 파일로 격리"""
    path = str(tmp_path / "ticker_profiles.json")
    monkeypatch.setattr(tp, "PROFILES_FILE", path)
    return path


class TestDefaultProfiles:
    def test_soxl_default(self, tmp_profiles):
        profile = tp.get_profile("SOXL")
        assert profile["base_ticker"] == "SOXX"
        assert profile["reverse_exit"] == -20.0
        assert profile["trailing_stop"] == 1.5

    def test_tqqq_default(self, tmp_profiles):
        profile = tp.get_profile("TQQQ")
        assert profile["base_ticker"] == "QQQ"
        assert profile["reverse_exit"] == -15.0
        assert profile["trailing_stop"] == 1.0

    def test_tsll_default(self, tmp_profiles):
        assert tp.get_base_ticker("TSLL") == "TSLA"

    def test_fngu_bulz_default(self, tmp_profiles):
        assert tp.get_base_ticker("FNGU") == "FNGS"
        assert tp.get_base_ticker("BULZ") == "FNGS"


class TestUnknownTicker:
    def test_unknown_base_is_self(self, tmp_profiles):
        """등록되지 않은 티커의 base_ticker는 자기 자신"""
        assert tp.get_base_ticker("UNKNOWN") == "UNKNOWN"

    def test_unknown_reverse_exit_fallback(self, tmp_profiles):
        assert tp.get_reverse_exit("UNKNOWN") == -18.0

    def test_unknown_trailing_stop_fallback(self, tmp_profiles):
        assert tp.get_trailing_stop("UNKNOWN") == 1.2


class TestAddTicker:
    def test_add_new_ticker(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2)
        assert tp.get_base_ticker("UPRO") == "SPY"
        assert tp.get_reverse_exit("UPRO") == -18.0
        assert tp.get_trailing_stop("UPRO") == 1.2

    def test_add_persists_after_reload(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2)
        # 다시 로드해도 존재
        assert "UPRO" in tp.list_tickers()

    def test_add_overwrite_existing(self, tmp_profiles):
        """기존 티커 덮어쓰기"""
        tp.add_ticker("SOXL", "SOXX", -25.0, 2.0)
        assert tp.get_reverse_exit("SOXL") == -25.0
        assert tp.get_trailing_stop("SOXL") == 2.0


class TestRemoveTicker:
    def test_remove_existing(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2)
        assert tp.remove_ticker("UPRO") == True
        # 제거 후엔 fallback 반환
        assert tp.get_base_ticker("UPRO") == "UPRO"

    def test_remove_nonexistent(self, tmp_profiles):
        assert tp.remove_ticker("NONEXISTENT") == False


class TestBaseMap:
    def test_base_map_contains_defaults(self, tmp_profiles):
        base_map = tp.get_base_map()
        assert base_map["SOXL"] == "SOXX"
        assert base_map["TQQQ"] == "QQQ"

    def test_base_map_includes_added(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2)
        base_map = tp.get_base_map()
        assert base_map["UPRO"] == "SPY"


class TestListTickers:
    def test_default_list(self, tmp_profiles):
        tickers = tp.list_tickers()
        assert "SOXL" in tickers
        assert "TQQQ" in tickers

    def test_after_add(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2)
        assert "UPRO" in tp.list_tickers()
