"""Groq Whisper API 轉錄封裝

優先使用 Groq 雲端 whisper-large-v3 轉錄，
遇到 rate limit 或網路錯誤時回傳 None 讓呼叫端 fallback 到本機 faster-whisper。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger("voice.groq_stt")

# Groq API 設定
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
# 單次請求逾時（秒），Groq 速度極快，60 秒足夠處理長音訊
GROQ_TIMEOUT = 60.0
# Groq 免費 tier 檔案大小上限（25MB）
GROQ_MAX_FILE_SIZE = 25 * 1024 * 1024


def _get_api_key() -> str | None:
    """從環境變數取得 Groq API Key"""
    return os.environ.get("GROQ_API_KEY")


def transcribe_file(file_path: str, language: str = "zh") -> str | None:
    """使用 Groq Whisper API 轉錄音訊檔案（同步）

    Args:
        file_path: 音訊檔案的絕對路徑
        language: 語言代碼（ISO-639-1），預設 zh

    Returns:
        轉錄文字（成功）或 None（失敗，呼叫端應 fallback 到本機）
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("未設定 GROQ_API_KEY，跳過 Groq 轉錄")
        return None

    path = Path(file_path)
    if not path.exists():
        logger.warning("檔案不存在: %s", file_path)
        return None

    # 檔案大小檢查（免費 tier 上限 25MB）
    file_size = path.stat().st_size
    if file_size > GROQ_MAX_FILE_SIZE:
        logger.info("檔案 %.1fMB 超過 Groq 上限 %dMB，跳過", file_size / 1024 / 1024, GROQ_MAX_FILE_SIZE // 1024 // 1024)
        return None

    try:
        with open(file_path, "rb") as f:
            response = httpx.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (path.name, f, "audio/mpeg")},
                data={
                    "model": GROQ_MODEL,
                    "language": language,
                    "response_format": "verbose_json",
                    "temperature": "0.0",
                },
                timeout=GROQ_TIMEOUT,
            )

        if response.status_code == 429:
            logger.warning("Groq API rate limit，fallback 到本機轉錄")
            return None

        if response.status_code != 200:
            logger.warning("Groq API 錯誤 (HTTP %d): %s", response.status_code, response.text[:200])
            return None

        result = response.json()
        text = result.get("text", "").strip()
        segments = result.get("segments", [])

        if segments:
            logger.info("Groq 轉錄完成：%d 個 segments", len(segments))
        else:
            logger.info("Groq 轉錄完成：%d 字元", len(text))

        return text if text else None

    except httpx.TimeoutException:
        logger.warning("Groq API 逾時，fallback 到本機轉錄")
        return None
    except httpx.ConnectError:
        logger.warning("Groq API 連線失敗，fallback 到本機轉錄")
        return None
    except Exception as e:
        logger.warning("Groq API 未預期錯誤: %s，fallback 到本機轉錄", e)
        return None


def transcribe_file_with_segments(
    file_path: str, language: str = "zh"
) -> dict | None:
    """使用 Groq Whisper API 轉錄音訊檔案，回傳含時間戳的 segments（同步）

    用於異步轉錄 pipeline，需要 segments 來產生帶時間戳的逐字稿。

    Args:
        file_path: 音訊檔案的絕對路徑
        language: 語言代碼（ISO-639-1），預設 zh

    Returns:
        {"text": str, "segments": [...], "duration": float} 或 None（失敗）
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("未設定 GROQ_API_KEY，跳過 Groq 轉錄")
        return None

    path = Path(file_path)
    if not path.exists():
        logger.warning("檔案不存在: %s", file_path)
        return None

    # 檔案大小檢查（免費 tier 上限 25MB）
    file_size = path.stat().st_size
    if file_size > GROQ_MAX_FILE_SIZE:
        logger.info("檔案 %.1fMB 超過 Groq 上限 %dMB，跳過", file_size / 1024 / 1024, GROQ_MAX_FILE_SIZE // 1024 // 1024)
        return None

    try:
        with open(file_path, "rb") as f:
            response = httpx.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (path.name, f, "audio/mpeg")},
                data={
                    "model": GROQ_MODEL,
                    "language": language,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                    "temperature": "0.0",
                },
                timeout=GROQ_TIMEOUT,
            )

        if response.status_code == 429:
            logger.warning("Groq API rate limit，fallback 到本機轉錄")
            return None

        if response.status_code != 200:
            logger.warning("Groq API 錯誤 (HTTP %d): %s", response.status_code, response.text[:200])
            return None

        result = response.json()
        text = result.get("text", "").strip()
        segments = result.get("segments", [])
        duration = result.get("duration", 0.0)

        logger.info("Groq 轉錄完成：%d 個 segments，時長 %.1f 秒", len(segments), duration)

        return {
            "text": text,
            "segments": [
                {
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", "").strip(),
                }
                for seg in segments
                if seg.get("text", "").strip()
            ],
            "duration": duration,
        }

    except httpx.TimeoutException:
        logger.warning("Groq API 逾時，fallback 到本機轉錄")
        return None
    except httpx.ConnectError:
        logger.warning("Groq API 連線失敗，fallback 到本機轉錄")
        return None
    except Exception as e:
        logger.warning("Groq API 未預期錯誤: %s，fallback 到本機轉錄", e)
        return None
