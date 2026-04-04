"""
Phase 0: volatility_engine 특성 테스트 (Characterization Test)

캐시 I/O와 순수 계산 로직을 검증합니다.
yfinance 외부 호출은 모킹합니다.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np


# ==============================================================
# 1. 캐시 I/O 테스트
# ==============================================================
class TestVolatilityCache:

    def test_load_cache_returns_default_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        result = ve._load_cache("MISSING_KEY", 99.9)
        assert result == 99.9

    def test_save_and_load_cache(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        cache_path = str(tmp_path / "data" / "volatility_cache.json")
        monkeypatch.setattr(ve, "CACHE_FILE", cache_path)

        ve._save_cache("TEST_KEY", 42.5)
        result = ve._load_cache("TEST_KEY", 0.0)
        assert result == 42.5

    def test_cache_preserves_existing_keys(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        cache_path = str(tmp_path / "data" / "volatility_cache.json")
        monkeypatch.setattr(ve, "CACHE_FILE", cache_path)

        ve._save_cache("KEY_A", 1.0)
        ve._save_cache("KEY_B", 2.0)

        assert ve._load_cache("KEY_A", 0.0) == 1.0
        assert ve._load_cache("KEY_B", 0.0) == 2.0


# ==============================================================
# 2. ATR 계산 테스트 (yfinance 모킹)
# ==============================================================
class TestATRCalculation:

    def _make_mock_df(self, n_days=300):
        """yfinance 응답을 흉내내는 DataFrame 생성"""
        dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(n_days) * 0.5)
        high = close + np.abs(np.random.randn(n_days)) * 0.5
        low = close - np.abs(np.random.randn(n_days)) * 0.5

        df = pd.DataFrame({
            "Open": close + np.random.randn(n_days) * 0.1,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.random.randint(1000000, 10000000, n_days)
        }, index=dates)
        return df

    def test_calculate_1y_atr_with_valid_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        mock_df = self._make_mock_df()
        with patch("trading_bot.strategy.volatility.yf.download", return_value=mock_df):
            result = ve._calculate_1y_atr("QQQ", "QQQ_ATR_1Y", 1.65)

        assert isinstance(result, float)
        assert result > 0

    def test_calculate_1y_atr_fallback_on_empty_df(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        with patch("trading_bot.strategy.volatility.yf.download", return_value=pd.DataFrame()):
            result = ve._calculate_1y_atr("QQQ", "QQQ_ATR_1Y", 1.65)

        assert result == 1.65  # 기본값 폴백


# ==============================================================
# 3. 타겟 드롭 함수 테스트 (yfinance 모킹)
# ==============================================================
class TestTargetDrop:

    def _make_vxn_df(self, n_days=300):
        dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
        np.random.seed(42)
        close = 20 + np.cumsum(np.random.randn(n_days) * 0.3)
        close = np.abs(close)  # VXN은 항상 양수
        return pd.DataFrame({"Close": close}, index=dates)

    def test_tqqq_target_drop_returns_negative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        mock_vxn = self._make_vxn_df()
        mock_qqq = TestATRCalculation()._make_mock_df()

        with patch("trading_bot.strategy.volatility.yf.download", side_effect=[mock_vxn, mock_qqq]):
            result = ve.get_tqqq_target_drop()

        assert result < 0  # 하락폭은 항상 음수

    def test_tqqq_target_drop_fallback(self, tmp_path, monkeypatch):
        """yfinance 실패 시 기본값 반환"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        with patch("trading_bot.strategy.volatility.yf.download", side_effect=Exception("Network error")):
            result = ve.get_tqqq_target_drop()

        assert result == round(-(1.65 * 3), 2)

    def test_soxl_target_drop_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        with patch("trading_bot.strategy.volatility.yf.download", side_effect=Exception("Network error")):
            result = ve.get_soxl_target_drop()

        assert result == round(-(2.93 * 3), 2)

    def test_tqqq_full_returns_4_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        with patch("trading_bot.strategy.volatility.yf.download", side_effect=Exception("err")):
            result = ve.get_tqqq_target_drop_full()

        assert len(result) == 4
        # fallback: (0.0, 1.0, fallback_amp, fallback_amp)
        assert result[0] == 0.0
        assert result[1] == 1.0

    def test_soxl_full_returns_4_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        import trading_bot.strategy.volatility as ve
        monkeypatch.setattr(ve, "CACHE_FILE", str(tmp_path / "data" / "volatility_cache.json"))

        with patch("trading_bot.strategy.volatility.yf.download", side_effect=Exception("err")):
            result = ve.get_soxl_target_drop_full()

        assert len(result) == 4
        assert result[0] == 0.0
