"""
ConfigManager 수동 VWAP 모드 설정 테스트

V26.00에서 추가된 get/set_manual_vwap_mode 메서드 검증
"""
import pytest


class TestManualVwapMode:
    """수동 VWAP 모드 get/set"""

    def test_default_is_false(self, cfg):
        assert cfg.get_manual_vwap_mode("SOXL") is False

    def test_set_true(self, cfg):
        cfg.set_manual_vwap_mode("SOXL", True)
        assert cfg.get_manual_vwap_mode("SOXL") is True

    def test_set_false(self, cfg):
        cfg.set_manual_vwap_mode("SOXL", True)
        cfg.set_manual_vwap_mode("SOXL", False)
        assert cfg.get_manual_vwap_mode("SOXL") is False

    def test_independent_per_ticker(self, cfg):
        cfg.set_manual_vwap_mode("SOXL", True)
        cfg.set_manual_vwap_mode("TQQQ", False)
        assert cfg.get_manual_vwap_mode("SOXL") is True
        assert cfg.get_manual_vwap_mode("TQQQ") is False

    def test_unknown_ticker_default(self, cfg):
        assert cfg.get_manual_vwap_mode("UNKNOWN") is False

    def test_persists_to_file(self, cfg):
        cfg.set_manual_vwap_mode("SOXL", True)
        # 파일에서 직접 읽어서 확인
        import json
        with open(cfg.FILES["MANUAL_VWAP_CFG"], 'r') as f:
            data = json.load(f)
        assert data["SOXL"] is True
