"""Socket.IO 連線身分工具

連線（connect）時把 token 解析成身分存進 sio session，之後各事件一律以
連線身分為準，不再相信 client payload 裡的 user_id／userId。
"""

from typing import Any
from urllib.parse import parse_qs


def extract_token(auth: Any, environ: Any) -> str | None:
    """從 client 的 auth dict 或連線 query string 取 token

    Args:
        auth: Socket.IO client 傳來的 auth（dict 或 None）
        environ: ASGI／WSGI environ，帶 QUERY_STRING

    Returns:
        token 字串；取不到回 None
    """
    if isinstance(auth, dict):
        token = auth.get("token")
        if isinstance(token, str) and token.strip():
            return token.strip()

    query_string = ""
    if isinstance(environ, dict):
        raw = environ.get("QUERY_STRING")
        if isinstance(raw, str):
            query_string = raw

    if query_string:
        for value in parse_qs(query_string).get("token", []):
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


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
