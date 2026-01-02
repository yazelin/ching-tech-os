"""AI 對話 Socket.IO 事件處理"""

import time
from uuid import UUID

from socketio import AsyncServer

from ..models.ai import AiLogCreate
from ..services import ai_chat, ai_manager
from ..services.claude_agent import call_claude, call_claude_for_summary
from ..services.message import log_message


def register_events(sio: AsyncServer):
    """註冊 AI 相關的 Socket.IO 事件

    Args:
        sio: Socket.IO AsyncServer 實例
    """

    @sio.event
    async def ai_chat_event(sid, data):
        """處理 AI 對話請求（自己管理歷史，不用 session）

        Args:
            sid: Socket.IO session ID
            data: {
                chatId: str,        # 對話 ID (UUID)
                message: str,       # 使用者訊息
                model: str,         # 模型名稱 (claude-opus/sonnet/haiku)
            }
        """
        chat_id_str = data.get("chatId")
        message = data.get("message", "")
        model = data.get("model", "claude-sonnet")

        # 驗證必要欄位
        if not chat_id_str or not message:
            await sio.emit(
                "ai_error",
                {
                    "chatId": chat_id_str,
                    "error": "缺少必要欄位 (chatId, message)",
                },
                to=sid,
            )
            return

        try:
            chat_id = UUID(chat_id_str)
        except ValueError:
            await sio.emit(
                "ai_error",
                {
                    "chatId": chat_id_str,
                    "error": "無效的 chatId 格式",
                },
                to=sid,
            )
            return

        # 從 DB 載入對話
        chat = await ai_chat.get_chat(chat_id)
        if chat is None:
            await sio.emit(
                "ai_error",
                {
                    "chatId": chat_id_str,
                    "error": "對話不存在",
                },
                to=sid,
            )
            return

        # 發送 typing 狀態
        await sio.emit(
            "ai_typing",
            {
                "chatId": chat_id_str,
                "typing": True,
            },
            to=sid,
        )

        # 讀取 system prompt（prompt_name 存的是 agent name）
        agent_name = chat.get("prompt_name", "web-chat-default")
        system_prompt = await ai_chat.get_agent_system_prompt(agent_name)

        # 取得對話歷史
        history = chat.get("messages", [])

        # 取得 agent 資訊（用於 log 和 tools）
        agent_config = await ai_chat.get_agent_config(agent_name)
        agent_id = agent_config.get("id") if agent_config else None
        agent_tools = agent_config.get("tools") if agent_config else None

        # 記錄開始時間
        start_time = time.time()

        # 呼叫 Claude CLI（自己管理歷史）
        response = await call_claude(
            prompt=message,
            model=model,
            history=history,
            system_prompt=system_prompt,
            tools=agent_tools,
        )

        # 計算耗時
        duration_ms = int((time.time() - start_time) * 1000)

        # 結束 typing 狀態
        await sio.emit(
            "ai_typing",
            {
                "chatId": chat_id_str,
                "typing": False,
            },
            to=sid,
        )

        if response.success:
            # 更新 DB 中的 messages
            new_messages = history.copy()

            # 加入使用者訊息
            new_messages.append(
                {
                    "role": "user",
                    "content": message,
                    "timestamp": int(time.time()),
                }
            )

            # 加入 AI 回應
            new_messages.append(
                {
                    "role": "assistant",
                    "content": response.message,
                    "timestamp": int(time.time()),
                }
            )

            await ai_chat.update_chat_messages(chat_id, new_messages)

            # 首次訊息時自動更新標題（取訊息前 20 字）
            if len(history) == 0:
                auto_title = message[:20] + ("..." if len(message) > 20 else "")
                await ai_chat.update_chat_title(chat_id, auto_title)

            # 發送回應
            await sio.emit(
                "ai_response",
                {
                    "chatId": chat_id_str,
                    "message": response.message,
                },
                to=sid,
            )

            # 記錄到 AI Log（含工具調用詳情）
            if agent_id:
                try:
                    # 將 tool_calls 轉換為可序列化的格式
                    parsed_response = None
                    if response.tool_calls:
                        parsed_response = {
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "name": tc.name,
                                    "input": tc.input,
                                    "output": tc.output,
                                }
                                for tc in response.tool_calls
                            ]
                        }

                    log_data = AiLogCreate(
                        agent_id=agent_id,
                        context_type="web-chat",
                        context_id=chat_id_str,
                        input_prompt=message,
                        system_prompt=system_prompt,
                        raw_response=response.message,
                        parsed_response=parsed_response,
                        model=model,
                        success=True,
                        duration_ms=duration_ms,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                    )
                    await ai_manager.create_log(log_data)
                except Exception as e:
                    print(f"[ai] create_log error: {e}")

            # 記錄 AI 對話訊息到訊息中心
            user_id = chat.get("user_id")
            if user_id:
                try:
                    await log_message(
                        severity="info",
                        source="ai-assistant",
                        title="AI 助手回應",
                        content=f"對話: {chat.get('title', '新對話')}\n回應摘要: {response.message[:100]}...",
                        category="user",
                        user_id=user_id,
                        metadata={"chat_id": chat_id_str, "model": model}
                    )
                except Exception as e:
                    print(f"[ai] log_message error: {e}")
        else:
            # 記錄失敗到 AI Log
            if agent_id:
                try:
                    log_data = AiLogCreate(
                        agent_id=agent_id,
                        context_type="web-chat",
                        context_id=chat_id_str,
                        input_prompt=message,
                        system_prompt=system_prompt,
                        model=model,
                        success=False,
                        error_message=response.error,
                        duration_ms=duration_ms,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                    )
                    await ai_manager.create_log(log_data)
                except Exception as e:
                    print(f"[ai] create_log error: {e}")

            # 發送錯誤
            await sio.emit(
                "ai_error",
                {
                    "chatId": chat_id_str,
                    "error": response.error,
                },
                to=sid,
            )

    @sio.event
    async def compress_chat(sid, data):
        """處理對話壓縮請求

        Args:
            sid: Socket.IO session ID
            data: {
                chatId: str,        # 對話 ID (UUID)
            }
        """
        chat_id_str = data.get("chatId")

        if not chat_id_str:
            await sio.emit(
                "compress_error",
                {
                    "chatId": chat_id_str,
                    "error": "缺少 chatId",
                },
                to=sid,
            )
            return

        try:
            chat_id = UUID(chat_id_str)
        except ValueError:
            await sio.emit(
                "compress_error",
                {
                    "chatId": chat_id_str,
                    "error": "無效的 chatId 格式",
                },
                to=sid,
            )
            return

        # 從 DB 載入對話
        chat = await ai_chat.get_chat(chat_id)
        if chat is None:
            await sio.emit(
                "compress_error",
                {
                    "chatId": chat_id_str,
                    "error": "對話不存在",
                },
                to=sid,
            )
            return

        messages = chat.get("messages", [])

        # 檢查訊息數量（至少要有 12 則才需要壓縮）
        if len(messages) < 12:
            await sio.emit(
                "compress_error",
                {
                    "chatId": chat_id_str,
                    "error": "訊息數量不足，無需壓縮",
                },
                to=sid,
            )
            return

        # 發送開始壓縮狀態
        await sio.emit(
            "compress_started",
            {
                "chatId": chat_id_str,
            },
            to=sid,
        )

        # 分割訊息：保留最近 10 則，壓縮其餘
        messages_to_keep = messages[-10:]
        messages_to_compress = messages[:-10]

        # 取得 summarizer prompt ID（用於 log）
        summarizer_prompt = await ai_manager.get_prompt_by_name("summarizer")
        prompt_id = summarizer_prompt.get("id") if summarizer_prompt else None

        # 組合輸入內容（用於 log）
        input_text = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in messages_to_compress
        ])

        # 記錄開始時間
        start_time = time.time()

        # 呼叫 Claude 產生摘要
        response = await call_claude_for_summary(messages_to_compress)

        # 計算耗時
        duration_ms = int((time.time() - start_time) * 1000)

        # 記錄到 AI Log（含 token 統計）
        try:
            log_data = AiLogCreate(
                prompt_id=prompt_id,
                context_type="compress",
                context_id=chat_id_str,
                input_prompt=input_text[:2000],  # 限制長度
                raw_response=response.message if response.success else None,
                model="claude-haiku",
                success=response.success,
                error_message=response.error if not response.success else None,
                duration_ms=duration_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            await ai_manager.create_log(log_data)
        except Exception as e:
            print(f"[ai] compress create_log error: {e}")

        if response.success:
            # 建立新的 messages 陣列：[摘要] + [最近 10 則]
            new_messages = [
                {
                    "role": "system",
                    "content": f"[對話摘要]\n{response.message}",
                    "timestamp": int(time.time()),
                    "is_summary": True,
                }
            ] + messages_to_keep

            # 更新 DB
            await ai_chat.update_chat_messages(chat_id, new_messages)

            # 發送完成
            await sio.emit(
                "compress_complete",
                {
                    "chatId": chat_id_str,
                    "messages": new_messages,
                    "compressed_count": len(messages_to_compress),
                },
                to=sid,
            )
        else:
            await sio.emit(
                "compress_error",
                {
                    "chatId": chat_id_str,
                    "error": response.error or "壓縮失敗",
                },
                to=sid,
            )
