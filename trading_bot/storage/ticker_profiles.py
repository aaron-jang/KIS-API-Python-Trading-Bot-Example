"""
티커별 프로필 관리 (기초자산 매핑, 리버스 탈출, 트레일링 스탑)

하드코딩된 티커별 값을 JSON 파일로 외부화하여 사용자가 새 종목을
자유롭게 등록할 수 있도록 지원합니다.

레벨 1(자동): 거래소, ATR, 변동성 평균 — 자동 감지
레벨 2(1회 입력): 본 파일에서 관리 — 기초자산, 리버스 탈출, 트레일링 스탑
레벨 3(공통): 하드코딩 유지 — U-Curve, 수수료 기반 트리거
"""
import json
import os
import tempfile
from typing import Optional

PROFILES_FILE = "data/ticker_profiles.json"

# 기존 하드코딩 값과 100% 동일한 기본 프로필 (호환성 보장)
DEFAULT_PROFILES = {
    "SOXL": {
        "base_ticker": "SOXX",
        "reverse_exit": -20.0,
        "trailing_stop": 1.5,
    },
    "TQQQ": {
        "base_ticker": "QQQ",
        "reverse_exit": -15.0,
        "trailing_stop": 1.0,
    },
    "TSLL": {
        "base_ticker": "TSLA",
        "reverse_exit": -20.0,
        "trailing_stop": 1.5,
    },
    "FNGU": {
        "base_ticker": "FNGS",
        "reverse_exit": -20.0,
        "trailing_stop": 1.5,
    },
    "BULZ": {
        "base_ticker": "FNGS",
        "reverse_exit": -20.0,
        "trailing_stop": 1.5,
    },
}

# 등록되지 않은 신규 티커의 기본값
FALLBACK_PROFILE = {
    "base_ticker": None,      # None이면 티커 자기 자신 사용
    "reverse_exit": -18.0,    # 중간값
    "trailing_stop": 1.2,     # 중간값
}


def _load() -> dict:
    """프로필 JSON 로드. 파일 없으면 기본값 반환."""
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_PROFILES)


def _save(data: dict) -> None:
    """프로필 JSON 원자적 저장."""
    dir_name = os.path.dirname(PROFILES_FILE)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(fd)
        os.replace(temp_path, PROFILES_FILE)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def get_profile(ticker: str) -> dict:
    """
    티커의 프로필을 반환. 등록되지 않은 티커는 FALLBACK_PROFILE을 반환.
    (단, base_ticker는 None일 경우 ticker 자기 자신으로 대체)
    """
    profiles = _load()
    if ticker in profiles:
        return profiles[ticker]

    fallback = dict(FALLBACK_PROFILE)
    if fallback["base_ticker"] is None:
        fallback["base_ticker"] = ticker
    return fallback


def get_base_ticker(ticker: str) -> str:
    """기초자산 티커 반환 (듀얼 레퍼런싱)"""
    return get_profile(ticker)["base_ticker"]


def get_reverse_exit(ticker: str) -> float:
    """리버스 모드 탈출 목표 수익률(%) 반환"""
    return float(get_profile(ticker)["reverse_exit"])


def get_trailing_stop(ticker: str) -> float:
    """상방 트레일링 스탑(%) 반환"""
    return float(get_profile(ticker)["trailing_stop"])


def get_base_map() -> dict:
    """전체 티커→기초자산 매핑 딕셔너리 반환"""
    profiles = _load()
    return {t: p["base_ticker"] for t, p in profiles.items()}


def add_ticker(ticker: str, base_ticker: str, reverse_exit: float, trailing_stop: float) -> None:
    """신규 티커를 프로필에 등록"""
    profiles = _load()
    profiles[ticker] = {
        "base_ticker": base_ticker,
        "reverse_exit": float(reverse_exit),
        "trailing_stop": float(trailing_stop),
    }
    _save(profiles)


def remove_ticker(ticker: str) -> bool:
    """티커 프로필 제거. 성공 시 True."""
    profiles = _load()
    if ticker in profiles:
        del profiles[ticker]
        _save(profiles)
        return True
    return False


def list_tickers() -> list[str]:
    """등록된 모든 티커 목록"""
    return list(_load().keys())
