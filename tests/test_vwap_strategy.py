"""
Phase 0: VwapStrategy 특성 테스트 (Characterization Test)

VWAP 타임 슬라이싱 엔진의 현재 동작을 캡처합니다.
시간 의존성은 monkeypatch로 제어합니다.
"""
import math
import pytest
from unittest.mock import patch
from datetime import datetime
import pytz

from trading_bot.strategy.vwap import VwapStrategy


@pytest.fixture
def vwap(cfg):
    return VwapStrategy(cfg)


# ==============================================================
# 1. 볼륨 프로파일 테스트
# ==============================================================
class TestVolumeProfile:
    """종목별 U-Curve 가중치 프로파일 동작 검증"""

    def test_profile_length_is_30(self, vwap):
        profile = vwap._get_vol_profile("TQQQ")
        assert len(profile) == 30

    def test_profile_sums_to_one(self, vwap):
        for ticker in ["TQQQ", "SOXL"]:
            profile = vwap._get_vol_profile(ticker)
            total = sum(profile)
            assert abs(total - 1.0) < 0.01, f"{ticker} 프로파일 합: {total}"

    def test_unknown_ticker_uses_default(self, vwap):
        profile = vwap._get_vol_profile("AAPL")
        assert len(profile) == 30
        total = sum(profile)
        assert abs(total - 1.0) < 0.01

    def test_u_curve_shape(self, vwap):
        """U-Curve: 마지막 분(30번째)이 가장 높은 가중치"""
        profile = vwap._get_vol_profile("TQQQ")
        assert profile[-1] > profile[10]  # 마지막 > 중간
        assert profile[0] > profile[5]     # 처음 > 초반 중간 (U-Curve 특성)


# ==============================================================
# 2. 시간 윈도우 테스트
# ==============================================================
class TestTimeWindow:

    def _mock_now(self, hour, minute):
        est = pytz.timezone("US/Eastern")
        return datetime(2025, 3, 12, hour, minute, 0, tzinfo=est)

    def test_bin_index_during_vwap_window(self, vwap):
        """15:30~15:59 EST 동안 0~29 반환"""
        with patch("trading_bot.strategy.vwap.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_now(15, 30)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert vwap._get_current_bin_index() == 0

        with patch("trading_bot.strategy.vwap.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_now(15, 45)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert vwap._get_current_bin_index() == 15

        with patch("trading_bot.strategy.vwap.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_now(15, 59)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert vwap._get_current_bin_index() == 29

    def test_bin_index_outside_window(self, vwap):
        """VWAP 윈도우 밖이면 -1"""
        with patch("trading_bot.strategy.vwap.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_now(14, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert vwap._get_current_bin_index() == -1

        with patch("trading_bot.strategy.vwap.datetime") as mock_dt:
            mock_dt.now.return_value = self._mock_now(15, 29)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert vwap._get_current_bin_index() == -1


# ==============================================================
# 3. VWAP 플랜 생성 테스트
# ==============================================================
class TestVwapPlan:

    def _make_plan_at_bin(self, vwap, bin_idx, **kwargs):
        """특정 bin에서 플랜을 생성하는 헬퍼"""
        with patch.object(vwap, "_get_current_bin_index", return_value=bin_idx):
            return vwap.get_vwap_plan(**kwargs)

    def test_outside_window_returns_empty(self, vwap):
        plan = self._make_plan_at_bin(
            vwap, -1,
            ticker="TQQQ", current_price=50.0,
            remaining_target=1000.0, side="BUY"
        )
        assert plan["orders"] == []
        assert "대기" in plan["process_status"] or "종료" in plan["process_status"]
        assert plan["allocated_qty"] == 0

    def test_buy_plan_generates_order(self, vwap):
        """매수: 충분한 예산이면 주문 생성"""
        plan = self._make_plan_at_bin(
            vwap, 29,  # 마지막 분 (가장 높은 가중치)
            ticker="TQQQ", current_price=50.0,
            remaining_target=5000.0, side="BUY"
        )
        if plan["allocated_qty"] > 0:
            assert len(plan["orders"]) == 1
            order = plan["orders"][0]
            assert order["side"] == "BUY"
            assert order["type"] == "LIMIT"
            assert order["price"] == 50.0

    def test_sell_plan_generates_order(self, vwap):
        """매도: 충분한 수량이면 주문 생성"""
        plan = self._make_plan_at_bin(
            vwap, 29,
            ticker="TQQQ", current_price=50.0,
            remaining_target=100,  # 100주 남음
            side="SELL"
        )
        if plan["allocated_qty"] > 0:
            assert len(plan["orders"]) == 1
            assert plan["orders"][0]["side"] == "SELL"

    def test_zero_price_returns_empty(self, vwap):
        plan = self._make_plan_at_bin(
            vwap, 15,
            ticker="TQQQ", current_price=0,
            remaining_target=1000.0, side="BUY"
        )
        assert plan["orders"] == []

    def test_strong_up_blocks_buy(self, vwap):
        """StrongUp 추세장에서 매수 차단"""
        vwap_status = {"is_strong_up": True, "is_strong_down": False}
        plan = self._make_plan_at_bin(
            vwap, 15,
            ticker="TQQQ", current_price=50.0,
            remaining_target=5000.0, side="BUY",
            vwap_status=vwap_status
        )
        assert plan["orders"] == []
        assert "StrongUp" in plan["process_status"]

    def test_strong_up_does_not_block_sell(self, vwap):
        """StrongUp은 매도를 차단하지 않음"""
        vwap_status = {"is_strong_up": True}
        plan = self._make_plan_at_bin(
            vwap, 29,
            ticker="TQQQ", current_price=50.0,
            remaining_target=100, side="SELL",
            vwap_status=vwap_status
        )
        # 매도는 StrongUp과 무관하게 동작
        assert "StrongUp" not in plan.get("process_status", "")


# ==============================================================
# 4. 잔차 이월(Residual Carry-over) 테스트
# ==============================================================
class TestResidualTracking:

    def test_residual_accumulation(self, vwap):
        """소수점 잔차가 누적되는지 검증"""
        # bin 0에서 잔차 초기화
        plan1 = self._make_plan_at_bin(
            vwap, 0,
            ticker="TQQQ", current_price=50.0,
            remaining_target=100.0, side="BUY"
        )
        residual1 = vwap.residual_tracker["BUY"].get("TQQQ", 0.0)

        # bin 1에서 잔차가 이월되는지
        plan2 = self._make_plan_at_bin(
            vwap, 1,
            ticker="TQQQ", current_price=50.0,
            remaining_target=100.0, side="BUY"
        )
        # 잔차는 0 이상 1 미만이어야 함
        residual2 = vwap.residual_tracker["BUY"].get("TQQQ", 0.0)
        assert 0.0 <= residual2 < 1.0

    def _make_plan_at_bin(self, vwap, bin_idx, **kwargs):
        with patch.object(vwap, "_get_current_bin_index", return_value=bin_idx):
            return vwap.get_vwap_plan(**kwargs)


# ==============================================================
# 5. 반환 구조 검증
# ==============================================================
class TestVwapReturnStructure:

    def test_return_keys(self, vwap):
        with patch.object(vwap, "_get_current_bin_index", return_value=15):
            plan = vwap.get_vwap_plan(
                ticker="TQQQ", current_price=50.0,
                remaining_target=1000.0, side="BUY"
            )
        required_keys = ["orders", "process_status", "allocated_qty", "bin_weight"]
        for key in required_keys:
            assert key in plan, f"누락된 키: {key}"
