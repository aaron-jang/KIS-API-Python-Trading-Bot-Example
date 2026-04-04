"""
원자적 파일 I/O 유틸리티

ConfigManager._load_json/_save_json/_load_file/_save_file을
독립 클래스로 추출한 것입니다.
"""
import copy
import json
import os
import shutil
import tempfile
import time


class FileUtils:
    def load_json(self, filename: str, default=None):
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ [Config] JSON 로드 에러 ({filename}): {e}")
                try:
                    shutil.copy(filename, filename + f".bak_{int(time.time())}")
                except Exception as backup_e:
                    print(f"⚠️ [Config] 백업 실패: {backup_e}")
                return copy.deepcopy(default) if default is not None else {}
        return copy.deepcopy(default) if default is not None else {}

    def save_json(self, filename: str, data):
        try:
            dir_name = os.path.dirname(filename)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(fd)

            os.replace(temp_path, filename)
        except Exception as e:
            print(f"❌ [Config] JSON 저장 중 치명적 에러 발생 ({filename}): {e}")
            if "temp_path" in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def load_file(self, filename: str, default=None):
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                print(f"⚠️ [Config] 파일 로드 에러 ({filename}): {e}")
        return default

    def save_file(self, filename: str, content):
        try:
            dir_name = os.path.dirname(filename)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(content))
                f.flush()
                os.fsync(fd)
            os.replace(temp_path, filename)
        except Exception as e:
            print(f"❌ [Config] 텍스트 파일 저장 에러 ({filename}): {e}")
