"""
Phase 0: 특성 테스트(Characterization Test) 공통 Fixture

기존 코드의 동작을 캡처하기 위해 임시 data/ 디렉토리를 생성하고
ConfigManager가 그 디렉토리를 사용하도록 패치합니다.
"""
import os
import sys
import json
import shutil
import tempfile
import pytest

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def tmp_data_dir(tmp_path):
    """테스트용 임시 data/ 디렉토리를 생성하고 경로를 반환"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def cfg(tmp_data_dir, monkeypatch):
    """
    ConfigManager를 임시 디렉토리에서 동작하도록 패치.
    실제 파일시스템 I/O를 하되, 테스트 격리를 보장.
    모든 파일 경로를 절대 경로로 변환하여 CWD 오염을 방지.
    """
    work_dir = str(tmp_data_dir.parent)
    monkeypatch.chdir(work_dir)

    from trading_bot.config import ConfigManager
    config = ConfigManager()

    # FILES 딕셔너리의 모든 경로를 절대 경로로 변환하여 완전 격리
    for key in config.FILES:
        config.FILES[key] = os.path.join(work_dir, config.FILES[key])

    # 내부 위임 객체도 동일한 절대 경로 기반으로 재설정
    data_dir = str(tmp_data_dir)
    config._ledger._ledger_path = config.FILES["LEDGER"]
    config._ledger._history_path = config.FILES["HISTORY"]
    config._ledger._split_history_path = config.FILES["SPLIT_HISTORY"]
    config._locks._path = config.FILES["LOCKS"]
    # TradingConfig 경로를 ConfigManager.FILES 기반 절대 경로로 재매핑
    files = config.FILES
    config._config._paths = {
        "SEED": files["SEED_CFG"],
        "SPLIT": files["SPLIT"],
        "PROFIT": files["PROFIT_CFG"],
        "COMPOUND": files["COMPOUND_CFG"],
        "VERSION": files["VERSION_CFG"],
        "SNIPER_MULT": files["SNIPER_MULTIPLIER_CFG"],
        "REVERSE": files["REVERSE_CFG"],
        "UPWARD_SNIPER": files["UPWARD_SNIPER"],
        "TICKER": files["TICKER"],
        "SECRET": files["SECRET_MODE"],
        "CHAT_ID": files["CHAT_ID"],
        "P_TRADE": files["P_TRADE_DATA"],
    }

    return config


@pytest.fixture
def cfg_with_ledger(cfg, tmp_data_dir):
    """샘플 장부가 로드된 ConfigManager"""
    src = os.path.join(FIXTURES_DIR, "sample_ledger.json")
    dst = tmp_data_dir / "manual_ledger.json"
    shutil.copy(src, dst)
    return cfg


@pytest.fixture
def cfg_with_history(cfg, tmp_data_dir):
    """샘플 히스토리가 로드된 ConfigManager"""
    # 장부도 함께 로드
    shutil.copy(
        os.path.join(FIXTURES_DIR, "sample_ledger.json"),
        tmp_data_dir / "manual_ledger.json"
    )
    shutil.copy(
        os.path.join(FIXTURES_DIR, "sample_history.json"),
        tmp_data_dir / "manual_history.json"
    )
    return cfg


@pytest.fixture
def sample_ledger():
    """fixture JSON을 파이썬 객체로 반환"""
    with open(os.path.join(FIXTURES_DIR, "sample_ledger.json"), "r") as f:
        return json.load(f)


@pytest.fixture
def sample_execution_history():
    """KIS API 체결 내역 응답 모킹 데이터"""
    return [
        {
            "sll_buy_dvsn_cd": "02",  # BUY
            "ft_ccld_qty": "10",
            "ft_ccld_unpr3": "48.50",
            "ord_tmd": "170500"
        },
        {
            "sll_buy_dvsn_cd": "02",  # BUY
            "ft_ccld_qty": "5",
            "ft_ccld_unpr3": "48.00",
            "ord_tmd": "170300"
        },
        {
            "sll_buy_dvsn_cd": "01",  # SELL
            "ft_ccld_qty": "8",
            "ft_ccld_unpr3": "52.00",
            "ord_tmd": "170400"
        }
    ]
