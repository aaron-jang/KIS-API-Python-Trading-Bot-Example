# ==========================================================
# [volatility_engine.py]
# ⚠️ V3.2 패치: 기초지수 1년 ATR 절대 진폭 고정 및 공포지수 방향타 스위치 엔진 탑재
# ==========================================================
import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
import tempfile

CACHE_FILE = "data/volatility_cache.json"

# ==========================================================
# 종목별 설정 레지스트리
# ==========================================================
_TICKER_PROFILES = {
    "TQQQ": {
        "vol_ticker": "^VXN",         # 변동성 지표 소스
        "atr_ticker": "QQQ",          # ATR 기초지수
        "atr_cache_key": "QQQ_ATR_1Y",
        "vol_cache_key": "VXN_MEAN",
        "default_atr": 1.65,
        "default_vol_mean": 20.0,
        "leverage": 3,
        "min_data_len": 1,            # 최소 데이터 길이
        "vol_method": "direct_close",  # VXN은 종가를 직접 사용
    },
    "SOXL": {
        "vol_ticker": "SOXX",
        "atr_ticker": "SOXX",
        "atr_cache_key": "SOXX_ATR_1Y",
        "vol_cache_key": "SOXX_HV_MEAN",
        "default_atr": 2.93,
        "default_vol_mean": 25.0,
        "leverage": 3,
        "min_data_len": 21,
        "vol_method": "hv_20d",        # SOXX는 20일 HV 계산
    },
}


def _load_cache(key, default_val):
    """ 🛡️ 통신 장애 시 직전 영업일의 1년 평균값을 로드하는 1차 방어막 """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                val = data.get(key)
                if val is not None and float(val) > 0:
                    return float(val)
        except Exception:
            pass
    return default_val

def _save_cache(key, value):
    """ 🛡️ 원자적 쓰기(fsync)를 통해 무결성이 보장된 로컬 캐시 저장 """
    data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
        except Exception:
            pass

    data[key] = value

    try:
        dir_name = os.path.dirname(CACHE_FILE)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(fd)
        os.replace(temp_path, CACHE_FILE)
    except Exception as e:
        print(f"⚠️ [Engine] 캐시 저장 실패: {e}")

def _calculate_1y_atr(ticker, cache_key, default_atr):
    """ 💡 기초지수의 최근 1년(252일) ATR14 평균값을 동적으로 연산하여 반환 """
    try:
        df = yf.download(ticker, period="2y", interval="1d", progress=False)
        if df.empty:
            return _load_cache(cache_key, default_atr)

        if hasattr(df.columns, 'droplevel'):
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

        df['Prev_Close'] = df['Close'].shift(1)

        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()

        df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR14'] = df['TR'].rolling(window=14).mean()
        df['ATR14_pct'] = (df['ATR14'] / df['Close']) * 100

        df_valid = df.dropna(subset=['ATR14_pct'])
        df_1y = df_valid.tail(252)

        if df_1y.empty:
            return _load_cache(cache_key, default_atr)

        atr_1y_avg = float(df_1y['ATR14_pct'].mean())
        if pd.isna(atr_1y_avg) or atr_1y_avg <= 0:
            raise ValueError("Invalid ATR")

        _save_cache(cache_key, atr_1y_avg)
        return atr_1y_avg

    except Exception as e:
        print(f"⚠️ [Engine] {ticker} ATR 연산 오류: {e}")
        return _load_cache(cache_key, default_atr)


def _normalize_columns(df):
    """yfinance MultiIndex 컬럼 정규화"""
    if hasattr(df.columns, 'droplevel'):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
    return df


def _fetch_volatility_metric(profile):
    """
    종목 프로필에 따라 변동성 지표(current_val, mean_val)를 계산.
    - direct_close: VXN처럼 종가를 직접 사용
    - hv_20d: SOXX처럼 20일 HV를 계산
    """
    vol_ticker = profile["vol_ticker"]
    vol_cache_key = profile["vol_cache_key"]
    default_mean = profile["default_vol_mean"]
    min_len = profile["min_data_len"]

    df = yf.download(vol_ticker, period="2y", interval="1d", progress=False)
    if df.empty or len(df) < min_len:
        return None, None

    df = _normalize_columns(df)

    if profile["vol_method"] == "direct_close":
        valid_series = df['Close'].dropna().tail(252)
        if valid_series.empty:
            return None, None
        current_val = float(valid_series.iloc[-1])
        raw_mean = valid_series.mean()
    else:  # hv_20d
        closes = df['Close'].dropna()
        log_returns = np.log(closes / closes.shift(1))
        hv_20d = log_returns.rolling(window=20).std() * np.sqrt(252) * 100
        valid_series = hv_20d.dropna().tail(252)
        if valid_series.empty:
            return None, None
        current_val = float(valid_series.iloc[-1])
        raw_mean = valid_series.mean()

    try:
        mean_val = float(raw_mean)
        if pd.isna(mean_val) or mean_val <= 0:
            raise ValueError("Invalid Mean")
        _save_cache(vol_cache_key, mean_val)
    except Exception:
        mean_val = _load_cache(vol_cache_key, default_mean)

    return current_val, mean_val


# ==========================================================
# 통합 엔진: 파라미터화된 타겟 드롭 계산
# ==========================================================
def _get_target_drop(ticker, full=False):
    """
    종목별 스나이퍼 타격선을 계산하는 통합 엔진.

    Args:
        ticker: "TQQQ" 또는 "SOXL"
        full: True이면 (current_val, weight, target_drop, base_amp) 4-tuple 반환

    Returns:
        full=False: target_drop (float, 음수)
        full=True: (current_val, weight, target_drop, base_amp) tuple
    """
    profile = _TICKER_PROFILES.get(ticker)
    if profile is None:
        raise ValueError(f"Unknown ticker: {ticker}")

    fallback_amp = round(-(profile["default_atr"] * profile["leverage"]), 2)

    try:
        current_val, mean_val = _fetch_volatility_metric(profile)

        if current_val is None:
            if full:
                return 0.0, 1.0, fallback_amp, fallback_amp
            return fallback_amp

        weight = current_val / mean_val

        atr_1y = _calculate_1y_atr(
            profile["atr_ticker"],
            profile["atr_cache_key"],
            profile["default_atr"]
        )
        base_amp = round(-(atr_1y * profile["leverage"]), 2)
        target_drop = base_amp

        if full:
            return current_val, weight, target_drop, base_amp
        return target_drop

    except Exception as e:
        print(f"❌ {ticker} 변동성 스캔 오류: {e}")
        if full:
            return 0.0, 1.0, fallback_amp, fallback_amp
        return fallback_amp


# ==========================================================
# 기존 호환 API (기존 코드가 호출하는 함수명 유지)
# ==========================================================
def get_tqqq_target_drop():
    return _get_target_drop("TQQQ", full=False)

def get_soxl_target_drop():
    return _get_target_drop("SOXL", full=False)

def get_tqqq_target_drop_full():
    return _get_target_drop("TQQQ", full=True)

def get_soxl_target_drop_full():
    return _get_target_drop("SOXL", full=True)
