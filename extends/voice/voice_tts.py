"""文字轉語音（TTS）服務

使用 Edge TTS 將文字轉為 MP3 語音檔。
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("voice.tts")

# 預設語音角色
DEFAULT_VOICE = "zh-TW-HsiaoChenNeural"

# 文字長度上限
MAX_TEXT_LENGTH = 500


@dataclass
class TTSResult:
    """TTS 結果"""
    nas_path: str | None       # 音檔 NAS 相對路徑
    file_id: str | None        # UUID4 音檔 ID
    duration_ms: int | None    # 音檔長度（毫秒）
    audio_bytes: bytes | None  # 音檔二進位（供 Telegram 直接上傳）
    error: str | None          # 錯誤訊息


def _get_ctos_mount_path() -> str:
    """取得 CTOS 掛載路徑"""
    try:
        from ching_tech_os.config import settings
        return settings.ctos_mount_path
    except ImportError:
        import os
        return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _strip_markdown(text: str) -> str:
    """清除 Markdown 標記"""
    # 移除程式碼區塊
    text = re.sub(r"```[\s\S]*?```", "", text)
    # 移除行內程式碼
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 移除粗體/斜體
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # 移除標題標記
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 移除列表標記
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
    # 移除連結
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 移除圖片
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # 移除水平線
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # 壓縮多餘空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _prepare_text(text: str) -> str:
    """前處理文字：清除 Markdown、截斷"""
    text = _strip_markdown(text)
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "...後續請參考文字訊息"
    return text


async def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
) -> TTSResult:
    """將文字轉為語音

    Args:
        text: 要轉語音的文字
        voice: Edge TTS 語音角色

    Returns:
        TTSResult
    """
    text = _prepare_text(text)
    if not text:
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error="文字內容為空",
        )

    try:
        import edge_tts
    except ImportError:
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error="edge-tts 未安裝",
        )

    file_id = str(uuid.uuid4())
    date_str = datetime.now().strftime("%Y-%m-%d")
    nas_rel_path = f"voice/tts/{date_str}/{file_id}.mp3"
    mount = _get_ctos_mount_path()
    abs_path = Path(mount) / nas_rel_path

    try:
        # 確保目錄存在
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # 生成語音
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(abs_path))

        # 讀取二進位（供 Telegram 直接上傳）
        audio_bytes = abs_path.read_bytes()

        # 估算 duration（MP3 ~16KB/s @ 128kbps）
        duration_ms = int(len(audio_bytes) / 16 * 1000 / 1000) if audio_bytes else None

        logger.info("TTS 生成完成: %s (%d bytes)", file_id, len(audio_bytes))

        return TTSResult(
            nas_path=nas_rel_path,
            file_id=file_id,
            duration_ms=duration_ms,
            audio_bytes=audio_bytes,
            error=None,
        )
    except Exception as e:
        logger.error("TTS 生成失敗: %s", e, exc_info=True)
        # 清理可能殘留的檔案
        if abs_path.exists():
            try:
                abs_path.unlink()
            except Exception:
                pass
        return TTSResult(
            nas_path=None, file_id=None, duration_ms=None,
            audio_bytes=None, error=str(e),
        )


def cleanup_old_files() -> None:
    """清理超過 24 小時的 TTS 暫存音檔"""
    mount = _get_ctos_mount_path()
    tts_root = Path(mount) / "voice" / "tts"

    if not tts_root.exists():
        return

    cutoff = datetime.now() - timedelta(hours=24)
    removed = 0

    for date_dir in tts_root.iterdir():
        if not date_dir.is_dir():
            continue
        # 檢查日期目錄名稱（YYYY-MM-DD）
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            if dir_date.date() >= cutoff.date():
                continue
        except ValueError:
            continue

        # 刪除整個日期目錄
        try:
            import shutil
            shutil.rmtree(str(date_dir))
            removed += 1
        except Exception as e:
            logger.warning("清理 TTS 目錄失敗 %s: %s", date_dir, e)

    if removed:
        logger.info("已清理 %d 個過期 TTS 目錄", removed)
