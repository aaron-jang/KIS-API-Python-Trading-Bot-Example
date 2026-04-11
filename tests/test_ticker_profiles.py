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
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2, validate=False)
        assert tp.get_base_ticker("UPRO") == "SPY"
        assert tp.get_reverse_exit("UPRO") == -18.0
        assert tp.get_trailing_stop("UPRO") == 1.2

    def test_add_persists_after_reload(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2, validate=False)
        # 다시 로드해도 존재
        assert "UPRO" in tp.list_tickers()

    def test_add_overwrite_existing(self, tmp_profiles):
        """기존 티커 덮어쓰기"""
        tp.add_ticker("SOXL", "SOXX", -25.0, 2.0, validate=False)
        assert tp.get_reverse_exit("SOXL") == -25.0
        assert tp.get_trailing_stop("SOXL") == 2.0

    def test_add_returns_success_message(self, tmp_profiles):
        success, msg = tp.add_ticker("UPRO", "SPY", -18.0, 1.2, validate=False)
        assert success == True
        assert "UPRO" in msg


class TestValidation:
    def test_validate_invalid_ticker(self, tmp_profiles, monkeypatch):
        """존재하지 않는 티커 검증 실패"""
        def mock_validate(ticker):
            return False  # 항상 실패
        monkeypatch.setattr(tp, "validate_ticker", mock_validate)

        success, msg = tp.add_ticker("FAKEXYZ", "SPY", -18.0, 1.2, validate=True)
        assert success == False
        assert "FAKEXYZ" in msg

    def test_validate_invalid_base_ticker(self, tmp_profiles, monkeypatch):
        """기초자산이 유효하지 않으면 실패"""
        call_count = {"n": 0}
        def mock_validate(ticker):
            call_count["n"] += 1
            return call_count["n"] == 1  # 첫 호출(UPRO)은 통과, 두번째(FAKEBASE)는 실패
        monkeypatch.setattr(tp, "validate_ticker", mock_validate)

        success, msg = tp.add_ticker("UPRO", "FAKEBASE", -18.0, 1.2, validate=True)
        assert success == False
        assert "FAKEBASE" in msg

    def test_connection_error_passes(self, tmp_profiles, monkeypatch):
        """진짜 네트워크 오류(ConnectionError) 시 True 반환"""
        def mock_yf_error(*args, **kwargs):
            raise ConnectionError("Network unreachable")

        import yfinance as yf
        monkeypatch.setattr(yf, "Ticker", mock_yf_error)
        assert tp.validate_ticker("ANYTHING") == True

    def test_generic_exception_fails(self, tmp_profiles, monkeypatch):
        """기타 예외(티커 없음 등)는 False 반환"""
        def mock_yf_error(*args, **kwargs):
            raise KeyError("Not a ticker")

        import yfinance as yf
        monkeypatch.setattr(yf, "Ticker", mock_yf_error)
        assert tp.validate_ticker("FAKE") == False


class TestRemoveTicker:
    def test_remove_existing(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2, validate=False)
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
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2, validate=False)
        base_map = tp.get_base_map()
        assert base_map["UPRO"] == "SPY"


class TestListTickers:
    def test_default_list(self, tmp_profiles):
        tickers = tp.list_tickers()
        assert "SOXL" in tickers
        assert "TQQQ" in tickers

    def test_after_add(self, tmp_profiles):
        tp.add_ticker("UPRO", "SPY", -18.0, 1.2, validate=False)
        assert "UPRO" in tp.list_tickers()
