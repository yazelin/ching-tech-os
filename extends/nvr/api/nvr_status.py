"""NVR 錄製狀態 API"""

import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter

router = APIRouter(tags=["nvr"])

RECORDINGS_DIR = Path("/tmp/consultation-recordings")


@router.get("/recording-status")
async def get_recording_status():
    """取得各頻道的錄製狀態。"""
    try:
        # 動態 import consultation_monitor 取得狀態
        import sys
        extends_his = os.path.join(os.environ.get("CTOS_PROJECT_ROOT", ""), "extends", "his")
        if extends_his not in sys.path:
            sys.path.insert(0, extends_his)

        from core.consultation_monitor import CONSULTATION_CHANNELS, _channel_sessions

        channels = []
        for ch in CONSULTATION_CHANNELS:
            session = _channel_sessions.get(ch)
            channels.append({
                "channel": ch,
                "recording": session is not None,
                "seconds": session.buffer_seconds if session else 0,
                "since": session.start_time.isoformat() if session else None,
            })
        return {"channels": channels}

    except Exception:
        # fallback: 從檔案推斷
        channels = []
        for ch in [6, 8, 10, 11]:
            pattern = f"ch{ch:02d}_*.txt"
            files = sorted(RECORDINGS_DIR.glob(pattern), reverse=True)
            latest = files[0].name if files else None
            channels.append({
                "channel": ch,
                "recording": False,
                "seconds": 0,
                "since": None,
                "latest_file": latest,
            })
        return {"channels": channels}
