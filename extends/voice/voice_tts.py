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

# 預設語音角色（可透過 .env 的 TTS_VOICE 設定覆蓋）
import os
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "zh-TW-HsiaoChenNeural")

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


def _strip_emojis(text: str) -> str:
    """移除 emoji 符號，避免 TTS 將 emoji 唸出來"""
    # 移除常見 Unicode emoji 範圍
    # 注意：不可使用跨越 CJK 漢字區（U+4E00-9FFF）的大範圍
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符號
        "\U0001F300-\U0001F5FF"  # 符號與象形文字
        "\U0001F680-\U0001F6FF"  # 交通與地圖
        "\U0001F1E0-\U0001F1FF"  # 國旗
        "\U0001F900-\U0001F9FF"  # 補充表情
        "\U0001FA00-\U0001FA6F"  # 棋子
        "\U0001FA70-\U0001FAFF"  # 額外符號
        "\U0001F000-\U0001F02F"  # 麻將、撲克牌
        "\U0001F0A0-\U0001F0FF"  # 撲克牌補充
        "\U0001F200-\U0001F251"  # 圈號文字符號（安全範圍，不含 CJK）
        "\U00002600-\U000027BF"  # 雜項符號 + 裝飾符號
        "\U0000FE00-\U0000FE0F"  # 變體選擇器
        "\U0000200D"             # 零寬連接符
        "\U00002B50-\U00002B55"  # 星星、圓圈等
        "\U0000231A-\U0000231B"  # 手錶/沙漏
        "\U000023E9-\U000023F3"  # 播放按鈕等
        "\U000023F8-\U000023FA"  # 暫停/錄音
        "\U0000200B-\U0000200F"  # 零寬空格等
        "\U000020E3"             # Combining Enclosing Keycap（1️⃣ 2️⃣ 等）
        "\U00002934-\U00002935"  # 箭頭
        "\U000025AA-\U000025AB"  # 小方塊
        "\U000025FB-\U000025FE"  # 中方塊
        "\U00002B05-\U00002B07"  # 箭頭
        "\U00002B1B-\U00002B1C"  # 大方塊
        "\U00003030"             # 波浪號
        "\U0000303D"             # 日文符號
        "\U00003297"             # 圈祝
        "\U00003299"             # 圈秘
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def _prepare_text(text: str) -> str:
    """前處理文字：清除 Markdown、emoji、截斷"""
    text = _strip_markdown(text)
    text = _strip_emojis(text)
    # 清理 emoji 移除後可能留下的多餘空格
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n +", "\n", text)
    text = text.strip()
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
