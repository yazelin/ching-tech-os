"""測試 bot/voice_bridge.py"""

import sys
import types
from unittest.mock import patch, MagicMock

from ching_tech_os.services.bot.voice_bridge import get_voice_stt, get_voice_tts


class TestGetVoiceStt:
    def test_import_success(self):
        """voice_stt 可 import 時回傳模組"""
        fake_module = types.ModuleType("voice_stt")
        with patch.dict(sys.modules, {"voice_stt": fake_module}):
            result = get_voice_stt()
            assert result is fake_module

    def test_import_failure(self):
        """voice_stt 不存在時回傳 None"""
        # 確保 voice_stt 不在 sys.modules
        with patch.dict(sys.modules, {}, clear=False):
            if "voice_stt" in sys.modules:
                del sys.modules["voice_stt"]
            with patch("builtins.__import__", side_effect=_import_raiser("voice_stt")):
                result = get_voice_stt()
                assert result is None


class TestGetVoiceTts:
    def test_import_success(self):
        """voice_tts 可 import 時回傳模組"""
        fake_module = types.ModuleType("voice_tts")
        with patch.dict(sys.modules, {"voice_tts": fake_module}):
            result = get_voice_tts()
            assert result is fake_module

    def test_import_failure(self):
        """voice_tts 不存在時回傳 None"""
        with patch.dict(sys.modules, {}, clear=False):
            if "voice_tts" in sys.modules:
                del sys.modules["voice_tts"]
            with patch("builtins.__import__", side_effect=_import_raiser("voice_tts")):
                result = get_voice_tts()
                assert result is None


def _import_raiser(blocked_name: str):
    """建立一個只阻擋特定模組的 import side_effect"""
    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _side_effect(name, *args, **kwargs):
        if name == blocked_name:
            raise ImportError(f"No module named '{blocked_name}'")
        return original_import(name, *args, **kwargs)

    return _side_effect
