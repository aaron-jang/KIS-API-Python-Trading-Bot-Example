"""
Phase 2: FileUtils 단위 테스트

원자적 JSON/텍스트 파일 I/O의 독립 테스트.
ConfigManager._load_json/_save_json 동작을 그대로 보존해야 합니다.
"""
import json
import os
import pytest

from trading_bot.storage.file_utils import FileUtils


@pytest.fixture
def fu(tmp_path):
    return FileUtils()


class TestJsonIO:
    def test_load_missing_returns_default(self, fu, tmp_path):
        result = fu.load_json(str(tmp_path / "missing.json"), {"x": 1})
        assert result == {"x": 1}

    def test_load_missing_no_default_returns_empty_dict(self, fu, tmp_path):
        result = fu.load_json(str(tmp_path / "missing.json"))
        assert result == {}

    def test_save_and_load_roundtrip(self, fu, tmp_path):
        path = str(tmp_path / "test.json")
        fu.save_json(path, {"hello": "world", "num": 42})
        result = fu.load_json(path)
        assert result == {"hello": "world", "num": 42}

    def test_save_creates_parent_dirs(self, fu, tmp_path):
        path = str(tmp_path / "a" / "b" / "test.json")
        fu.save_json(path, {"nested": True})
        assert fu.load_json(path) == {"nested": True}

    def test_corrupted_json_returns_default_and_backups(self, fu, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("NOT JSON!!!")
        result = fu.load_json(path, {"fallback": True})
        assert result == {"fallback": True}
        backups = [f for f in os.listdir(str(tmp_path)) if "bad.json.bak_" in f]
        assert len(backups) == 1

    def test_unicode_roundtrip(self, fu, tmp_path):
        path = str(tmp_path / "unicode.json")
        fu.save_json(path, {"한글": "테스트", "emoji": "🚀"})
        result = fu.load_json(path)
        assert result["한글"] == "테스트"

    def test_atomic_write_no_partial_file(self, fu, tmp_path):
        """정상 저장 후 임시 파일이 남지 않아야 함"""
        path = str(tmp_path / "atomic.json")
        fu.save_json(path, {"data": True})
        tmp_files = [f for f in os.listdir(str(tmp_path)) if f.startswith("tmp")]
        assert len(tmp_files) == 0


class TestFileIO:
    def test_load_missing_returns_default(self, fu, tmp_path):
        result = fu.load_file(str(tmp_path / "missing.dat"), "fallback")
        assert result == "fallback"

    def test_load_missing_no_default_returns_none(self, fu, tmp_path):
        result = fu.load_file(str(tmp_path / "missing.dat"))
        assert result is None

    def test_save_and_load_roundtrip(self, fu, tmp_path):
        path = str(tmp_path / "test.dat")
        fu.save_file(path, "hello_value")
        assert fu.load_file(path) == "hello_value"

    def test_save_creates_parent_dirs(self, fu, tmp_path):
        path = str(tmp_path / "sub" / "test.dat")
        fu.save_file(path, "nested")
        assert fu.load_file(path) == "nested"
