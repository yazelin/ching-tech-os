"""訊息中心 Socket.IO 事件處理"""

from socketio import AsyncServer

from ..services.message import get_unread_count
from ..models.message import MessageSeverity, MessageSource

# 儲存 sio 實例供外部使用
_sio: AsyncServer | None = None


def get_sio() -> AsyncServer | None:
    """取得 Socket.IO 實例"""
    return _sio


def register_events(sio: AsyncServer):
    """註冊訊息中心相關的 Socket.IO 事件

    Args:
        sio: Socket.IO AsyncServer 實例
    """
    global _sio
    _sio = sio

    @sio.event
    async def join_user_room(sid, data):
        """使用者加入個人房間（用於接收訊息通知）

        Args:
            sid: Socket.IO session ID
            data: {
                userId: int  # 使用者 ID
            }
        """
        user_id = data.get("userId")
        if user_id:
            room_name = f"user:{user_id}"
            await sio.enter_room(sid, room_name)
            print(f"Client {sid} joined room {room_name}")

            # 發送當前未讀數量
            count = await get_unread_count(user_id)
            await sio.emit(
                "message:unread_count",
                {"count": count},
                to=sid,
            )

    @sio.event
    async def leave_user_room(sid, data):
        """使用者離開個人房間

        Args:
            sid: Socket.IO session ID
            data: {
                userId: int
            }
        """
        user_id = data.get("userId")
        if user_id:
            room_name = f"user:{user_id}"
            await sio.leave_room(sid, room_name)
            print(f"Client {sid} left room {room_name}")

    @sio.event
    async def get_unread_count_event(sid, data):
        """取得未讀訊息數量

        Args:
            sid: Socket.IO session ID
            data: {
                userId: int | None
            }
        """
        user_id = data.get("userId")
        count = await get_unread_count(user_id)
        await sio.emit(
            "message:unread_count",
            {"count": count},
            to=sid,
        )


async def emit_new_message(
    message_id: int,
    severity: MessageSeverity | str,
    source: MessageSource | str,
    title: str,
    created_at: str,
    category: str | None = None,
    user_id: int | None = None,
):
    """推送新訊息通知

    Args:
        message_id: 訊息 ID
        severity: 嚴重程度
        source: 來源
        title: 標題
        created_at: 建立時間 (ISO 格式)
        category: 分類
        user_id: 目標使用者 ID（若為 None 則廣播）
    """
    if _sio is None:
        return

    # 轉換 enum 為字串
    if isinstance(severity, MessageSeverity):
        severity = severity.value
    if isinstance(source, MessageSource):
        source = source.value

    event_data = {
        "id": message_id,
        "severity": severity,
        "source": source,
        "category": category,
        "title": title,
        "created_at": created_at,
    }

    if user_id:
        # 發送給特定使用者
        await _sio.emit(
            "message:new",
            event_data,
            room=f"user:{user_id}",
        )
    else:
        # 廣播給所有人
        await _sio.emit("message:new", event_data)


async def emit_unread_count(user_id: int | None = None, count: int | None = None):
    """推送未讀數量更新

    Args:
        user_id: 目標使用者 ID（若為 None 則廣播）
        count: 未讀數量（若為 None 則自動查詢）
    """
    if _sio is None:
        return

    if count is None:
        count = await get_unread_count(user_id)

    event_data = {"count": count}

    if user_id:
        await _sio.emit(
            "message:unread_count",
            event_data,
            room=f"user:{user_id}",
        )
    else:
        await _sio.emit("message:unread_count", event_data)
