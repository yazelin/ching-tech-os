"""TTS 音檔下載 API

提供 TTS 生成的 MP3 檔案供 Line 伺服器抓取。
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


@router.get("/tts/{file_id}.mp3")
async def get_tts_audio(file_id: str):
    """下載 TTS 音檔

    Line 伺服器會透過此端點抓取語音回覆的音檔。
    file_id 必須為 UUID4 格式，防止路徑穿越。
    """
    # UUID4 格式驗證
    if not _UUID4_PATTERN.match(file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    # 搜尋音檔（在所有日期目錄中）
    mount = _get_ctos_mount_path()
    tts_root = Path(mount) / "voice" / "tts"

    if not tts_root.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # 在日期子目錄中搜尋
    target_filename = f"{file_id}.mp3"
    for date_dir in tts_root.iterdir():
        if not date_dir.is_dir():
            continue
        file_path = date_dir / target_filename
        if file_path.exists():
            return FileResponse(
                path=str(file_path),
                media_type="audio/mpeg",
                filename=target_filename,
                headers={"Cache-Control": "public, max-age=86400"},
            )

    raise HTTPException(status_code=404, detail="File not found")
