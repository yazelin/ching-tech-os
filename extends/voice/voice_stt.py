"""語音轉文字（STT）服務

短音訊（≤ 60 秒）使用 faster-whisper base 模型同步轉錄；
長音訊（> 60 秒）委派給 media-transcription skill 非同步處理。
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("voice.stt")

# 同步轉錄的時間門檻（秒）
SYNC_DURATION_THRESHOLD = 60

# 檔案大小估算比率（bytes/秒），用於 duration 缺失時的 fallback
_SIZE_RATE = {
    "line": 16_000,     # M4A ~128kbps ≈ 16KB/s
    "telegram": 2_000,  # OGG Opus ~16kbps ≈ 2KB/s
}

# Whisper 模型（全域快取，warmup 時載入）
_whisper_model = None
_semaphore = asyncio.Semaphore(1)


@dataclass
class TranscribeResult:
    """轉錄結果"""
    mode: str               # "sync" | "async"
    text: str | None        # 轉錄文字（sync 模式下有值）
    job_id: str | None      # 非同步 job ID（async 模式下有值）
    error: str | None       # 錯誤訊息（失敗時有值）


def _get_ctos_mount_path() -> str:
    """取得 CTOS 掛載路徑"""
    try:
        from ching_tech_os.config import settings
        return settings.ctos_mount_path
    except ImportError:
        import os
        return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _get_duration_seconds(
    nas_path: str,
    duration_ms: int | None,
    file_size: int | None,
    platform: str,
) -> float | None:
    """取得音訊長度（秒）

    優先順序：平台提供 → ffprobe → 檔案大小估算
    """
    # 1. 平台提供的 duration
    if duration_ms is not None and duration_ms > 0:
        return duration_ms / 1000.0

    # 2. ffprobe 讀取 header
    mount = _get_ctos_mount_path()
    abs_path = f"{mount}/{nas_path}"
    if Path(abs_path).exists() and shutil.which("ffprobe"):
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    abs_path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            logger.debug("ffprobe 取得 duration 失敗: %s", e)

    # 3. 檔案大小估算
    if file_size is not None and file_size > 0:
        rate = _SIZE_RATE.get(platform, _SIZE_RATE["line"])
        return file_size / rate

    return None


def _do_sync_transcribe(abs_path: str) -> str:
    """在 thread 中執行同步轉錄（blocking）"""
    global _whisper_model
    if _whisper_model is None:
        _load_model()

    segments, _info = _whisper_model.transcribe(abs_path, language="zh")

    # 簡轉繁
    converter = None
    try:
        from opencc import OpenCC
        converter = OpenCC("s2twp")
    except ImportError:
        pass

    parts = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            if converter:
                text = converter.convert(text)
            parts.append(text)

    return "".join(parts)


def _load_model() -> None:
    """載入 whisper base 模型"""
    global _whisper_model
    from faster_whisper import WhisperModel

    device = "cpu"
    compute_type = "int8"
    if shutil.which("nvidia-smi"):
        device = "cuda"
        compute_type = "float16"

    _whisper_model = WhisperModel("base", device=device, compute_type=compute_type)
    logger.info("Whisper base 模型已載入 (device=%s)", device)


async def transcribe_for_bot(
    nas_path: str,
    duration_ms: int | None = None,
    file_size: int | None = None,
    platform: str = "line",
) -> TranscribeResult:
    """Bot 語音訊息轉錄入口

    Args:
        nas_path: 音訊檔在 NAS 上的相對路徑
        duration_ms: 音訊長度（毫秒），由平台提供
        file_size: 檔案大小（bytes），作為 duration 的備選判斷
        platform: 來源平台（"line" | "telegram"）

    Returns:
        TranscribeResult
    """
    mount = _get_ctos_mount_path()
    abs_path = f"{mount}/{nas_path}"

    if not Path(abs_path).exists():
        return TranscribeResult(mode="sync", text=None, job_id=None, error="音訊檔案不存在")

    # 判斷 duration
    duration = _get_duration_seconds(nas_path, duration_ms, file_size, platform)

    # 長音訊走非同步
    if duration is not None and duration > SYNC_DURATION_THRESHOLD:
        return await _async_transcribe(nas_path)

    # 短音訊走同步（或 duration 未知時預設走同步）
    try:
        async with _semaphore:
            text = await asyncio.to_thread(_do_sync_transcribe, abs_path)
        if not text:
            return TranscribeResult(mode="sync", text=None, job_id=None, error="語音內容為空")
        return TranscribeResult(mode="sync", text=text, job_id=None, error=None)
    except Exception as e:
        logger.error("同步轉錄失敗: %s", e, exc_info=True)
        return TranscribeResult(mode="sync", text=None, job_id=None, error=str(e))


async def _async_transcribe(nas_path: str) -> TranscribeResult:
    """委派給 media-transcription skill 非同步轉錄"""
    try:
        from ching_tech_os.services.mcp.skill_script_tools import run_skill_script
        input_data = json.dumps({
            "source_path": f"ctos://{nas_path}",
            "model": "small",
        }, ensure_ascii=False)
        result = await run_skill_script(
            skill="media-transcription",
            script="transcribe",
            input=input_data,
        )
        # 解析回傳的 JSON
        if isinstance(result, str):
            parsed = json.loads(result)
        else:
            parsed = result
        if parsed.get("success"):
            return TranscribeResult(
                mode="async",
                text=None,
                job_id=parsed.get("job_id"),
                error=None,
            )
        return TranscribeResult(
            mode="async", text=None, job_id=None,
            error=parsed.get("error", "非同步轉錄啟動失敗"),
        )
    except Exception as e:
        logger.error("非同步轉錄委派失敗: %s", e, exc_info=True)
        return TranscribeResult(mode="async", text=None, job_id=None, error=str(e))


async def warmup() -> None:
    """啟動時預載 whisper base 模型（在 thread pool 中執行）"""
    try:
        await asyncio.to_thread(_load_model)
    except Exception as e:
        logger.warning("Whisper 模型預載失敗（首次轉錄時會再嘗試）: %s", e)


def cleanup() -> None:
    """釋放 whisper 模型資源"""
    global _whisper_model
    if _whisper_model is not None:
        _whisper_model = None
        logger.info("Whisper 模型已釋放")
