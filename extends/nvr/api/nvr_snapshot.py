"""NVR 快照代理 API

代理 ONVIF 快照請求，讓前端瀏覽器能取得攝影機畫面。
"""

import os
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
import httpx

router = APIRouter(tags=["nvr"])

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        user = os.environ.get("NVR_ONVIF_USER", "onvif")
        password = os.environ.get("NVR_ONVIF_PASSWORD", "")
        _client = httpx.AsyncClient(
            auth=httpx.DigestAuth(user, password),
            timeout=10.0,
        )
    return _client


@router.get("/snapshot/{channel}")
async def get_snapshot(channel: int):
    """取得指定頻道的即時快照。

    Args:
        channel: 頻道號碼 (1-16)
    """
    if not 1 <= channel <= 16:
        raise HTTPException(status_code=400, detail="頻道範圍 1-16")

    host = os.environ.get("NVR_HOST", "192.168.68.200")
    url = f"http://{host}:80/onvif/snapshot?token={channel}_0"

    try:
        client = _get_client()
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"NVR 回傳 {resp.status_code}")

        return Response(
            content=resp.content,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            },
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="NVR 連線逾時")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NVR 連線失敗: {e}")
