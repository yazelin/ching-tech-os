"""AI 對話 Socket.IO 事件處理"""

from socketio import AsyncServer

from ..services.claude_agent import call_claude


def register_events(sio: AsyncServer):
    """註冊 AI 相關的 Socket.IO 事件

    Args:
        sio: Socket.IO AsyncServer 實例
    """

    @sio.event
    async def ai_chat(sid, data):
        """處理 AI 對話請求

        Args:
            sid: Socket.IO session ID
            data: {
                chatId: str,        # 對話 ID
                sessionId: str,     # Claude CLI session ID (UUID)
                message: str,       # 使用者訊息
                model: str,         # 模型名稱 (claude-opus/sonnet/haiku)
            }
        """
        chat_id = data.get("chatId")
        session_id = data.get("sessionId")
        message = data.get("message", "")
        model = data.get("model", "claude-sonnet")

        # 驗證必要欄位
        if not chat_id or not session_id or not message:
            await sio.emit("ai_error", {
                "chatId": chat_id,
                "error": "缺少必要欄位 (chatId, sessionId, message)",
            }, to=sid)
            return

        # 發送 typing 狀態
        await sio.emit("ai_typing", {
            "chatId": chat_id,
            "typing": True,
        }, to=sid)

        # 呼叫 Claude CLI
        response = await call_claude(
            prompt=message,
            session_id=session_id,
            model=model,
        )

        # 結束 typing 狀態
        await sio.emit("ai_typing", {
            "chatId": chat_id,
            "typing": False,
        }, to=sid)

        if response.success:
            # 發送回應
            await sio.emit("ai_response", {
                "chatId": chat_id,
                "message": response.message,
            }, to=sid)
        else:
            # 發送錯誤
            await sio.emit("ai_error", {
                "chatId": chat_id,
                "error": response.error,
            }, to=sid)
