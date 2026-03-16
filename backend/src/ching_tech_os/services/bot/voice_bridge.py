"""voice 模組條件載入橋接

extends/voice 模組啟動時會將其目錄加入 sys.path，
之後即可透過 import 載入。模組未安裝時回傳 None。
"""

from __future__ import annotations

import types


def get_voice_stt() -> types.ModuleType | None:
    """取得 voice STT 模組，未安裝時回傳 None"""
    try:
        import voice_stt  # type: ignore[import-not-found]
        return voice_stt
    except ImportError:
        return None


def get_voice_tts() -> types.ModuleType | None:
    """取得 voice TTS 模組，未安裝時回傳 None"""
    try:
        import voice_tts  # type: ignore[import-not-found]
        return voice_tts
    except ImportError:
        return None
