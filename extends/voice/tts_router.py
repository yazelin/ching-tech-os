"""TTS 音檔下載 API

提供 TTS 生成的 M4A 音檔供 Line 伺服器抓取。
支援 .m4a 和 .mp3 副檔名（向後相容）。
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# UUID4 格式驗證
_UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _get_ctos_mount_path() -> str:
    """取得 CTOS 掛載路徑"""
    try:
        from ching_tech_os.config import settings
        return settings.ctos_mount_path
    except ImportError:
        import os
        return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _find_tts_file(file_id: str) -> Path | None:
    """在 TTS 目錄中搜尋音檔（支援 .m4a 和 .mp3）"""
    mount = _get_ctos_mount_path()
    tts_root = Path(mount) / "voice" / "tts"

    if not tts_root.exists():
        return None

    for ext in (".m4a", ".mp3"):
        target = f"{file_id}{ext}"
        for date_dir in tts_root.iterdir():
            if not date_dir.is_dir():
                continue
            file_path = date_dir / target
            if file_path.exists():
                return file_path
    return None


@router.get("/tts/{file_id}.m4a")
async def get_tts_audio_m4a(file_id: str):
    """下載 TTS M4A 音檔"""
    if not _UUID4_PATTERN.match(file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    file_path = _find_tts_file(file_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    mime = "audio/mp4" if file_path.suffix == ".m4a" else "audio/mpeg"
    return FileResponse(
        path=str(file_path),
        media_type=mime,
        filename=f"{file_id}{file_path.suffix}",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/tts/{file_id}.mp3")
async def get_tts_audio_mp3(file_id: str):
    """下載 TTS MP3 音檔（向後相容）"""
    if not _UUID4_PATTERN.match(file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    file_path = _find_tts_file(file_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    mime = "audio/mp4" if file_path.suffix == ".m4a" else "audio/mpeg"
    return FileResponse(
        path=str(file_path),
        media_type=mime,
        filename=f"{file_id}{file_path.suffix}",
        headers={"Cache-Control": "public, max-age=86400"},
    )
