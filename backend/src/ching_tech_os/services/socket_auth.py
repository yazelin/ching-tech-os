"""Socket.IO 連線身分工具

連線（connect）時把 token 解析成身分存進 sio session，之後各事件一律以
連線身分為準，不再相信 client payload 裡的 user_id／userId。

高風險事件（跑 AI、開終端機）另外在進入時重新解析一次 token，
連線後才被登出或撤銷的 token 不能繼續用。
"""

import logging
from typing import Any

from socketio.exceptions import ConnectionRefusedError as SioConnectionRefused

logger = logging.getLogger(__name__)


def extract_token(auth: Any) -> str | None:
    """從 client 的 auth 取 token

    只認 `auth["token"]`。query string 會留在 nginx／瀏覽器歷史紀錄裡，不接受。

    Args:
        auth: Socket.IO client 傳來的 auth（dict 或 None）

    Returns:
        token 字串；取不到回 None
    """
    if isinstance(auth, dict):
        token = auth.get("token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    return None


async def authenticate_connect(sio: Any, sid: str, auth: Any) -> dict:
    """Socket.IO connect：驗 token，通過就把身分存進 sio session

    token 只從 client 的 `auth.token` 取（query string 會留在 nginx log 與
    瀏覽器歷史紀錄，不接受）。驗不過一律 raise ConnectionRefusedError；
    通過則回存進 session 的身分 dict。

    放在 service 而不是 main.py，是讓測試不必 import main（main 一載入就掛靜態目錄）。
    """
    from ..api.auth import _resolve_session

    token = extract_token(auth)
    if not token:
        raise SioConnectionRefused("unauthorized")

    try:
        session = await _resolve_session(token)
    except Exception as e:
        logger.warning("Socket.IO 連線解析 token 失敗（sid=%s）: %s", sid, e)
        raise SioConnectionRefused("unauthorized")

    if session is None:
        raise SioConnectionRefused("unauthorized")

    identity = {
        "user_id": session.user_id,
        "username": session.username,
        "role": session.role,
        "app_permissions": session.app_permissions or {},
        "read_only": session.read_only,
        # 高風險事件會拿它重新解析一次，確認 token 還有效
        "token": token,
    }
    await sio.save_session(sid, identity)
    return identity


async def get_socket_identity(sio: Any, sid: str) -> dict | None:
    """取得連線時存下的身分

    取不到（例如 sio 沒有 get_session、或連線已消失）回 None，
    由呼叫端回錯誤事件，不讓事件處理直接炸掉。
    """
    getter = getattr(sio, "get_session", None)
    if getter is None:
        return None

    try:
        data = await getter(sid)
    except Exception:
        return None

    return data if isinstance(data, dict) else None


async def get_socket_user_id(sio: Any, sid: str) -> int | None:
    """取得連線身分的 user_id（取不到回 None）"""
    identity = await get_socket_identity(sio, sid)
    if not identity:
        return None
    user_id = identity.get("user_id")
    return user_id if isinstance(user_id, int) else None


async def revalidate_socket_session(sio: Any, sid: str):
    """用連線時存下的 token 重新解析一次身分

    給跑 AI、開終端機這類高風險事件用：連線可能掛著很久，
    中途登出或 token 被撤銷時不該還能繼續用。

    Returns:
        SessionData；token 不在、解析失敗或出錯回 None
    """
    identity = await get_socket_identity(sio, sid)
    token = identity.get("token") if identity else None
    if not isinstance(token, str) or not token:
        return None

    from ..api.auth import _resolve_session

    try:
        return await _resolve_session(token)
    except Exception as e:
        logger.warning("Socket.IO 重新驗證 token 失敗（sid=%s）: %s", sid, e)
        return None


async def disconnect_socket(sio: Any, sid: str) -> None:
    """中斷連線（sio 沒有 disconnect 或呼叫失敗都不影響呼叫端）"""
    disconnect = getattr(sio, "disconnect", None)
    if disconnect is None:
        return
    try:
        await disconnect(sid)
    except Exception as e:
        logger.warning("Socket.IO 中斷連線失敗（sid=%s）: %s", sid, e)
