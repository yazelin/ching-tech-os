"""Line Bot AI 處理服務

使用 Claude CLI 處理 Line 訊息（與 AI 助手相同架構）
整合 AI Log 記錄功能
"""

import asyncio
import json
import logging
import re
import time
from uuid import UUID

from .claude_agent import call_claude, compose_prompt_with_history
from .image_fallback import (
    generate_image_with_fallback,
    get_fallback_notification,
)
from .linebot import (
    reply_text,
    reply_messages,
    push_text,
    push_image,
    push_messages,
    get_line_group_external_id,
    create_text_message_with_mention,
    MENTION_PLACEHOLDER,
    mark_message_ai_processed,
    should_trigger_ai,
    is_bot_message,
    save_bot_response,
    save_file_record,
    reset_conversation,
    is_reset_command,
    ensure_temp_image,
    get_image_info_by_line_message_id,
    get_temp_image_path,
    get_message_content_by_line_message_id,
    # 檔案暫存相關
    ensure_temp_file,
    get_file_info_by_line_message_id,
    get_temp_file_path,
    is_readable_file,
    is_legacy_office_file,
    MAX_READABLE_FILE_SIZE,
    # Line 用戶查詢
    get_line_user_record,
)
from . import ai_manager
from .linebot_agents import get_linebot_agent, AGENT_LINEBOT_PERSONAL, AGENT_LINEBOT_GROUP
from ..database import get_connection
from ..models.ai import AiLogCreate

logger = logging.getLogger("linebot_ai")


# ============================================================
# PDF 路徑解析輔助函式
# ============================================================


def parse_pdf_temp_path(temp_path: str) -> tuple[str, str]:
    """
    解析 PDF 特殊格式路徑

    PDF 上傳時會同時保留原始檔和文字版，格式為 "PDF:xxx.pdf|TXT:xxx.txt"

    Args:
        temp_path: 暫存檔路徑（可能是 PDF 特殊格式或一般路徑）

    Returns:
        (pdf_path, txt_path) 元組
        - 若為 PDF 特殊格式：回傳 (PDF 路徑, 文字版路徑)
        - 若為一般路徑：回傳 (原路徑, "")
    """
    if not temp_path.startswith("PDF:"):
        return (temp_path, "")

    parts = temp_path.split("|")
    pdf_path = parts[0].replace("PDF:", "")
    txt_path = parts[1].replace("TXT:", "") if len(parts) > 1 else ""
    return (pdf_path, txt_path)


# ============================================================
# AI 生成圖片自動處理
# ============================================================


def extract_nanobanana_error(tool_calls: list) -> str | None:
    """
    從 tool_calls 中提取 nanobanana 的錯誤訊息

    Args:
        tool_calls: Claude response 的 tool_calls 列表

    Returns:
        錯誤訊息字串，如果沒有錯誤則回傳 None
    """
    if not tool_calls:
        return None

    nanobanana_tools = {
        "mcp__nanobanana__generate_image",
        "mcp__nanobanana__edit_image",
    }

    for tc in tool_calls:
        if tc.name not in nanobanana_tools:
            continue

        try:
            output = tc.output
            if isinstance(output, str):
                output_data = json.loads(output)
            else:
                output_data = output

            if isinstance(output_data, list) and len(output_data) > 0:
                inner_text = output_data[0].get("text", "")
                if inner_text:
                    inner_data = json.loads(inner_text)
                    if not inner_data.get("success") and inner_data.get("error"):
                        return inner_data["error"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return None


def extract_nanobanana_prompt(tool_calls: list) -> str | None:
    """
    從 tool_calls 中提取 nanobanana 的 prompt（用於 fallback）

    Args:
        tool_calls: Claude response 的 tool_calls 列表

    Returns:
        prompt 字串，如果沒有則回傳 None
    """
    if not tool_calls:
        return None

    # 只支援 generate_image，edit_image 需要參考圖片無法用備用服務
    for tc in tool_calls:
        if tc.name != "mcp__nanobanana__generate_image":
            continue

        try:
            # tc.input 是 dict，包含 prompt 等參數
            if hasattr(tc, "input") and isinstance(tc.input, dict):
                return tc.input.get("prompt")
        except (AttributeError, TypeError):
            pass

    return None


def check_nanobanana_timeout(tool_calls: list) -> bool:
    """
    檢測是否有 nanobanana 工具被呼叫但 output 為空（timeout）

    當 Gemini API hang 住時，Claude CLI 會 timeout 並強制終止，
    導致 nanobanana 的 output 為空。

    Args:
        tool_calls: Claude response 的 tool_calls 列表

    Returns:
        True 如果有 nanobanana 呼叫但 output 為空
    """
    if not tool_calls:
        return False

    for tc in tool_calls:
        if tc.name != "mcp__nanobanana__generate_image":
            continue

        # 檢查 output 是否為空
        output = tc.output
        if output is None or output == "" or output == "null":
            return True

        # 檢查是否為空字串或空 list
        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                if not parsed:
                    return True
            except json.JSONDecodeError:
                if not output.strip():
                    return True

    return False


def get_user_friendly_nanobanana_error(error: str) -> str:
    """
    將 nanobanana 錯誤轉換為用戶友善的訊息

    Args:
        error: 原始錯誤訊息

    Returns:
        用戶友善的錯誤訊息
    """
    if "overloaded" in error.lower():
        return (
            "⚠️ 圖片生成服務暫時無法使用\n\n"
            "原因：Google Gemini 伺服器過載（503 錯誤）\n"
            "這是 Google 那邊太忙，不是你用太多！\n\n"
            "建議：等 1-2 分鐘後再試"
        )
    elif "api key" in error.lower():
        return "⚠️ 圖片生成服務設定錯誤，請聯繫管理員檢查 API 金鑰。"
    elif "quota" in error.lower() or "limit" in error.lower():
        return (
            "⚠️ 圖片生成已達使用限制（429 錯誤）\n\n"
            "免費版限制：每分鐘 2 張、每天 100 張\n"
            "每日限制在台灣時間下午 3-4 點重置"
        )
    else:
        return f"⚠️ 圖片生成失敗：{error}"


def extract_generated_images_from_tool_calls(tool_calls: list) -> list[str]:
    """
    從 tool_calls 中提取 nanobanana 生成的圖片路徑

    Args:
        tool_calls: Claude response 的 tool_calls 列表

    Returns:
        生成的圖片檔案路徑列表
    """
    generated_files = []

    if not tool_calls:
        return generated_files

    # 支援 generate_image 和 edit_image
    nanobanana_tools = {
        "mcp__nanobanana__generate_image",
        "mcp__nanobanana__edit_image",
    }

    for tc in tool_calls:
        if tc.name not in nanobanana_tools:
            continue

        # tool_call output 格式: [{"text": "{...json...}", "type": "text"}]
        try:
            output = tc.output
            if isinstance(output, str):
                output_data = json.loads(output)
            else:
                output_data = output

            # 解析外層陣列
            if isinstance(output_data, list) and len(output_data) > 0:
                inner_text = output_data[0].get("text", "")
                if inner_text:
                    inner_data = json.loads(inner_text)
                    if inner_data.get("success") and inner_data.get("generatedFiles"):
                        generated_files.extend(inner_data["generatedFiles"])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"解析 generate_image 輸出失敗: {e}")

    return generated_files


async def auto_prepare_generated_images(
    ai_response: str,
    tool_calls: list,
    tenant_id: UUID | None = None,
) -> str:
    """
    自動處理 AI 生成的圖片，確保用戶能收到圖片

    如果 AI 呼叫了 generate_image 但沒有呼叫 prepare_file_message，
    自動補上 FILE_MESSAGE 標記。

    如果圖片生成失敗（如 overloaded），會在回應中加入明確的錯誤提示。

    Args:
        ai_response: AI 回應文字
        tool_calls: Claude response 的 tool_calls 列表
        tenant_id: 租戶 ID（用於檔案處理）

    Returns:
        處理後的 AI 回應（可能包含新增的 FILE_MESSAGE 標記或錯誤提示）
    """
    # 注意：nanobanana 錯誤和 timeout 已在 chat_with_ai() 中處理（包含 fallback 邏輯）
    # 這裡只處理成功生成圖片後的自動發送

    # 提取生成的圖片
    generated_files = extract_generated_images_from_tool_calls(tool_calls)

    if not generated_files:
        return ai_response

    logger.info(f"偵測到 AI 生成圖片: {generated_files}")

    # 檢查 AI 回應是否已包含這些圖片的 FILE_MESSAGE
    # 如果已有 FILE_MESSAGE 標記，跳過
    existing_file_messages = re.findall(r'\[FILE_MESSAGE:(\{.*?\})\]', ai_response)

    # 找出尚未處理的圖片
    unprocessed_files = []
    for file_path in generated_files:
        # 取得檔名（不含路徑）
        file_name = file_path.split("/")[-1]
        # 檢查是否已在 FILE_MESSAGE 中
        already_processed = any(file_name in msg for msg in existing_file_messages)
        if not already_processed:
            unprocessed_files.append(file_path)

    if not unprocessed_files:
        logger.debug("所有生成圖片已由 AI 處理")
        return ai_response

    logger.info(f"自動處理未發送的生成圖片: {unprocessed_files}")

    # 呼叫 prepare_file_message 處理未發送的圖片
    from .mcp_server import prepare_file_message

    file_messages = []
    for file_path in unprocessed_files:
        try:
            # nanobanana 輸出的路徑是完整路徑，需要轉換為相對路徑
            # /tmp/ching-tech-os-cli/nanobanana-output/xxx.jpg -> nanobanana-output/xxx.jpg
            if "nanobanana-output/" in file_path:
                relative_path = "nanobanana-output/" + file_path.split("nanobanana-output/")[-1]
            else:
                relative_path = file_path

            result = await prepare_file_message(relative_path, ctos_tenant_id=str(tenant_id) if tenant_id else None)
            if "[FILE_MESSAGE:" in result:
                file_messages.append(result)
                logger.info(f"自動準備圖片訊息: {relative_path}")
            else:
                logger.warning(f"prepare_file_message 失敗: {result}")
        except Exception as e:
            logger.error(f"自動處理圖片失敗 {file_path}: {e}")

    # 將 FILE_MESSAGE 標記加到回應中
    if file_messages:
        ai_response = ai_response.rstrip() + "\n\n" + "\n".join(file_messages)

    # 移除格式錯誤的 FILE_MESSAGE 標記（AI 有時會自己寫錯誤格式）
    # 正確格式：[FILE_MESSAGE:{...json...}]
    # 錯誤格式：[FILE_MESSAGE:/tmp/...] 或 [FILE_MESSAGE:path/to/file]
    malformed_pattern = r'\[FILE_MESSAGE:[^\{][^\]]*\]'
    ai_response = re.sub(malformed_pattern, '', ai_response)

    # 清理多餘的空行
    ai_response = re.sub(r'\n{3,}', '\n\n', ai_response)

    return ai_response


# ============================================================
# AI 回應解析與發送
# ============================================================


def parse_ai_response(response: str) -> tuple[str, list[dict]]:
    """
    解析 AI 回應，提取文字和檔案訊息

    Args:
        response: AI 回應原始文字

    Returns:
        (text, files): 純文字回覆和檔案訊息列表
    """
    if not response:
        return "", []

    # 匹配 [FILE_MESSAGE:{...}] 標記（非貪婪匹配到最後的 }]）
    pattern = r'\[FILE_MESSAGE:(\{.*?\})\]'
    files = []

    for match in re.finditer(pattern, response):
        try:
            file_info = json.loads(match.group(1))
            files.append(file_info)
        except json.JSONDecodeError as e:
            logger.warning(f"解析 FILE_MESSAGE 失敗: {e}")

    # 移除標記，保留純文字
    text = re.sub(pattern, '', response).strip()

    # 清理多餘的空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text, files


def _append_text_to_first_message(
    messages: list,
    append_text: str,
    mention_line_user_id: str | None = None,
) -> None:
    """將文字附加到訊息列表的第一則文字訊息

    如果第一則訊息帶有 mention，會保留 mention 並附加文字。
    如果沒有現有文字訊息，會建立新的文字訊息。

    Args:
        messages: 訊息列表（會被修改）
        append_text: 要附加的文字
        mention_line_user_id: mention 的 Line 用戶 ID
    """
    from linebot.v3.messaging import TextMessage, TextMessageV2

    if messages and isinstance(messages[0], (TextMessage, TextMessageV2)):
        # 追加到現有文字訊息
        original_text = messages[0].text
        # 處理帶 mention 的情況：移除佔位符前綴，重新建立訊息
        if mention_line_user_id and original_text.startswith(MENTION_PLACEHOLDER):
            base_text = original_text[len(MENTION_PLACEHOLDER):]
            new_text = base_text + "\n\n" + append_text
            messages[0] = create_text_message_with_mention(new_text, mention_line_user_id)
        else:
            new_text = original_text + "\n\n" + append_text
            messages[0] = TextMessage(text=new_text)
    else:
        # 沒有現有文字訊息，建立新的（保留 mention）
        messages.append(create_text_message_with_mention(append_text, mention_line_user_id))


async def send_ai_response(
    reply_token: str,
    text: str,
    file_messages: list[dict],
    mention_line_user_id: str | None = None,
    tenant_id: UUID | None = None,
) -> list[str]:
    """
    發送 AI 回應（文字 + 檔案訊息）

    Args:
        reply_token: Line 回覆 token
        text: 文字回覆
        file_messages: 檔案訊息列表
        mention_line_user_id: 要 mention 的 Line 用戶 ID（群組對話時使用）
        tenant_id: 租戶 ID（用於選擇正確的 Line Bot access token）

    Returns:
        發送成功的訊息 ID 列表
    """
    from linebot.v3.messaging import ImageMessage

    messages = []

    # 先加入文字訊息（顯示在上方）
    # 如果有提供 mention_line_user_id，使用 TextMessageV2 帶 mention
    if text:
        messages.append(create_text_message_with_mention(text, mention_line_user_id))

    # 再處理檔案訊息
    for file_info in file_messages:
        file_type = file_info.get("type", "file")
        url = file_info.get("url", "")
        name = file_info.get("name", "")
        size = file_info.get("size", "")

        if file_type == "image" and url:
            # 圖片：使用 ImageMessage（顯示在文字下方）
            messages.append(ImageMessage(
                original_content_url=url,
                preview_image_url=url,
            ))
        elif file_type == "file" and url:
            # 非圖片檔案：加入連結文字
            link_text = f"📎 {name}"
            if size:
                link_text += f"（{size}）"
            link_text += f"\n{url}\n⏰ 連結 24 小時內有效"
            _append_text_to_first_message(messages, link_text, mention_line_user_id)

    # Line 限制每次最多 5 則訊息
    # 如果檔案太多，只發送前 4 張圖片（預留 1 則給文字）
    if len(messages) > 5:
        # 提取超出的圖片訊息
        extra_messages = messages[5:]
        messages = messages[:5]

        # 將超出的圖片轉為連結，追加到文字訊息（文字在最前）
        extra_links = []
        for msg in extra_messages:
            if isinstance(msg, ImageMessage):
                extra_links.append(msg.original_content_url)

        if extra_links:
            extra_text = "其他圖片連結：\n" + "\n".join(extra_links)
            _append_text_to_first_message(messages, extra_text, mention_line_user_id)

    if not messages:
        return []

    # 發送訊息（傳入 tenant_id 以使用正確的 access token）
    return await reply_messages(reply_token, messages, tenant_id=tenant_id)


# ============================================================
# AI 處理主流程
# ============================================================


async def process_message_with_ai(
    message_uuid: UUID,
    content: str,
    line_group_id: UUID | None,
    line_user_id: str | None,
    reply_token: str | None,
    user_display_name: str | None = None,
    quoted_message_id: str | None = None,
    tenant_id: UUID | None = None,
    bot_tenant_id: UUID | None = None,
) -> str | None:
    """
    使用 AI 處理訊息

    Args:
        message_uuid: 訊息的內部 UUID
        content: 訊息內容
        line_group_id: 群組 UUID（個人對話為 None）
        line_user_id: Line 用戶 ID（個人對話用）
        reply_token: Line 回覆 token（可能已過期）
        user_display_name: 發送者顯示名稱
        quoted_message_id: 被回覆的訊息 ID（Line 的 quotedMessageId）
        tenant_id: 租戶 ID（用於業務邏輯：AI、知識庫等）
        bot_tenant_id: Bot 租戶 ID（用於回覆訊息的 credentials）
            - 有值：使用該租戶的 Line Bot credentials
            - None：使用環境變數的 credentials（共用 Bot）

    Returns:
        AI 回應文字，或 None（如果不需處理）
    """
    is_group = line_group_id is not None

    # 檢查是否為重置對話指令（僅限個人對話）
    if is_reset_command(content):
        if is_group:
            # 群組不支援重置，靜默忽略
            return None
        elif line_user_id:
            # 個人對話：執行重置
            await reset_conversation(line_user_id, tenant_id=tenant_id)
            reset_msg = "已清除對話歷史，開始新對話！有什麼可以幫你的嗎？"
            # 儲存 Bot 回應
            await save_bot_response(
                group_uuid=None,
                content=reset_msg,
                responding_to_line_user_id=line_user_id,
                tenant_id=tenant_id,
            )
            # 回覆訊息（reply token 可能過期，失敗時改用 push message）
            # 注意：回覆使用 bot_tenant_id（接收 webhook 的 Bot）
            reply_success = False
            if reply_token:
                try:
                    await reply_text(reply_token, reset_msg, tenant_id=bot_tenant_id)
                    reply_success = True
                except Exception as e:
                    logger.warning(f"回覆重置訊息失敗（reply token 可能過期）: {e}")

            # 如果沒有 reply_token 或回覆失敗，改用 push message
            if not reply_success and line_user_id:
                try:
                    await push_text(line_user_id, reset_msg, tenant_id=bot_tenant_id)
                    logger.info(f"使用 push message 發送重置訊息給 {line_user_id}")
                except Exception as e:
                    logger.error(f"Push 重置訊息也失敗: {e}")

            return reset_msg
        return None

    # 檢查是否回覆機器人訊息（群組對話用）
    is_reply_to_bot = False
    logger.info(f"檢查回覆: is_group={is_group}, quoted_message_id={quoted_message_id}")
    if is_group and quoted_message_id:
        is_reply_to_bot = await is_bot_message(quoted_message_id)
        logger.info(f"is_bot_message({quoted_message_id}) = {is_reply_to_bot}")

    # 檢查是否應該觸發 AI
    should_trigger = should_trigger_ai(content, is_group, is_reply_to_bot)
    logger.info(f"AI 觸發判斷: is_group={is_group}, is_reply_to_bot={is_reply_to_bot}, content={content[:50]!r}, should_trigger={should_trigger}")

    if not should_trigger:
        logger.debug(f"訊息不觸發 AI: {content[:50]}...")
        return None

    try:
        # 取得 Agent 設定
        agent = await get_linebot_agent(is_group, tenant_id=tenant_id)
        agent_name = AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL

        if not agent:
            error_msg = f"⚠️ AI 設定錯誤：Agent '{agent_name}' 不存在"
            logger.error(error_msg)
            if reply_token:
                await reply_text(reply_token, error_msg, tenant_id=bot_tenant_id)
            return error_msg

        # 從 Agent 取得 model 和基礎 prompt
        model = agent["model"].replace("claude-", "")  # claude-sonnet -> sonnet
        # 安全取得 system_prompt（處理 None 和非 dict 情況）
        system_prompt_data = agent.get("system_prompt")
        logger.debug(f"system_prompt type: {type(system_prompt_data)}, value preview: {repr(system_prompt_data)[:100] if system_prompt_data else 'None'}")
        if isinstance(system_prompt_data, dict):
            base_prompt = system_prompt_data.get("content", "")
        else:
            base_prompt = ""
            if system_prompt_data is not None:
                logger.warning(f"system_prompt 不是 dict: {type(system_prompt_data)}")
        # 從 Agent 取得內建工具權限（如 WebSearch, WebFetch）
        agent_tools = agent.get("tools") or []
        logger.info(f"使用 Agent '{agent_name}' 設定，內建工具: {agent_tools}")

        if not base_prompt:
            error_msg = f"⚠️ AI 設定錯誤：Agent '{agent_name}' 沒有設定 system_prompt"
            logger.error(error_msg)
            if reply_token:
                await reply_text(reply_token, error_msg, tenant_id=bot_tenant_id)
            return error_msg

        # 先取得使用者權限（用於動態生成工具說明和過濾工具）
        from .user import get_user_role_and_permissions
        from .permissions import get_mcp_tools_for_user, get_user_app_permissions_sync
        ctos_user_id = None
        user_role = "user"
        user_permissions = None
        app_permissions: dict[str, bool] = {}
        if line_user_id:
            # 同一個 Line 用戶可能在多個租戶有記錄，必須用 tenant_id 過濾
            user_row = await get_line_user_record(line_user_id, tenant_id, "user_id")
            if user_row and user_row["user_id"]:
                ctos_user_id = user_row["user_id"]
                user_info = await get_user_role_and_permissions(ctos_user_id, tenant_id)
                user_role = user_info["role"]
                user_permissions = user_info["permissions"]
                # 計算 App 權限供 prompt 動態生成
                app_permissions = get_user_app_permissions_sync(user_role, user_info.get("user_data"))

        # 若未關聯 CTOS 帳號，使用預設權限（一般使用者）
        if not app_permissions:
            app_permissions = get_user_app_permissions_sync("user", None)

        # 建立系統提示（加入群組資訊、內建工具說明和動態 MCP 工具說明）
        system_prompt = await build_system_prompt(
            line_group_id, line_user_id, base_prompt, agent_tools, tenant_id, app_permissions
        )

        # 取得對話歷史（20 則提供更好的上下文理解，包含圖片和檔案）
        # 排除當前訊息，避免重複（compose_prompt_with_history 會再加一次）
        history, images, files = await get_conversation_context(
            line_group_id, line_user_id, limit=20, exclude_message_id=message_uuid, tenant_id=tenant_id
        )

        # 處理回覆舊訊息（quotedMessageId）- 圖片、檔案或文字
        quoted_image_path = None
        quoted_file_path = None
        quoted_text_content = None
        if quoted_message_id:
            # 先嘗試查詢圖片
            image_info = await get_image_info_by_line_message_id(quoted_message_id, tenant_id=tenant_id)
            if image_info and image_info.get("nas_path"):
                # 確保圖片暫存存在
                temp_path = await ensure_temp_image(quoted_message_id, image_info["nas_path"], tenant_id=tenant_id)
                if temp_path:
                    quoted_image_path = temp_path
                    logger.info(f"用戶回覆圖片: {quoted_message_id} -> {temp_path}")
            else:
                # 嘗試查詢檔案
                file_info = await get_file_info_by_line_message_id(quoted_message_id, tenant_id=tenant_id)
                if file_info and file_info.get("nas_path") and file_info.get("file_name"):
                    file_name = file_info["file_name"]
                    file_size = file_info.get("file_size")
                    if is_readable_file(file_name):
                        if file_size and file_size > MAX_READABLE_FILE_SIZE:
                            logger.info(f"用戶回覆檔案過大: {quoted_message_id} -> {file_name}")
                        else:
                            # 確保檔案暫存存在
                            temp_path = await ensure_temp_file(
                                quoted_message_id, file_info["nas_path"], file_name, file_size, tenant_id=tenant_id
                            )
                            if temp_path:
                                quoted_file_path = temp_path
                                logger.info(f"用戶回覆檔案: {quoted_message_id} -> {temp_path}")
                    else:
                        logger.info(f"用戶回覆檔案類型不支援: {quoted_message_id} -> {file_name}")
                else:
                    # 嘗試查詢文字訊息
                    msg_info = await get_message_content_by_line_message_id(quoted_message_id)
                    if msg_info and msg_info.get("content"):
                        quoted_text_content = {
                            "content": msg_info["content"],
                            "display_name": msg_info.get("display_name", ""),
                            "is_from_bot": msg_info.get("is_from_bot", False),
                        }
                        logger.info(f"用戶回覆文字: {quoted_message_id} -> {msg_info['content'][:50]}...")

        # 註：對話歷史中的圖片/檔案暫存已在 get_conversation_context 中處理

        # 準備用戶訊息（格式：user[發送者]: 內容）
        if user_display_name:
            user_message = f"user[{user_display_name}]: {content}"
        else:
            user_message = f"user: {content}"

        # 如果是回覆圖片、檔案或文字，在訊息開頭標註
        if quoted_image_path:
            user_message = f"[回覆圖片: {quoted_image_path}]\n{user_message}"
        elif quoted_file_path:
            # 使用共用函式解析 PDF 特殊格式
            pdf_path, txt_path = parse_pdf_temp_path(quoted_file_path)
            if pdf_path != quoted_file_path:
                # 是 PDF 特殊格式
                if txt_path:
                    user_message = f"[回覆 PDF: {pdf_path}（文字版: {txt_path}）]\n{user_message}"
                else:
                    user_message = f"[回覆 PDF: {pdf_path}（純圖片，無文字）]\n{user_message}"
            else:
                user_message = f"[回覆檔案: {quoted_file_path}]\n{user_message}"
        elif quoted_text_content:
            # 回覆文字訊息
            sender = quoted_text_content["display_name"] or ("AI" if quoted_text_content["is_from_bot"] else "用戶")
            quoted_text = quoted_text_content["content"]
            # 限制引用文字長度，避免 prompt 過長
            if len(quoted_text) > 2000:
                quoted_text = quoted_text[:2000] + "..."
            user_message = f"[回覆 {sender} 的訊息：「{quoted_text}」]\n{user_message}"

        # MCP 工具列表（動態取得）
        from .mcp_server import get_mcp_tool_names
        mcp_tools = await get_mcp_tool_names(exclude_group_only=not is_group)

        # 過濾 MCP 工具（根據使用者權限，使用前面已取得的 user_role 和 user_permissions）
        mcp_tools = get_mcp_tools_for_user(user_role, user_permissions, mcp_tools)
        logger.info(f"使用者權限過濾後的 MCP 工具數量: {len(mcp_tools)}, role={user_role}")

        # 合併內建工具（從 Agent 設定）、MCP 工具和 Read（用於讀取圖片）
        # 加入 nanobanana 圖片生成/編輯工具
        nanobanana_tools = [
            "mcp__nanobanana__generate_image",
            "mcp__nanobanana__edit_image",
        ]
        all_tools = agent_tools + mcp_tools + nanobanana_tools + ["Read"]

        # 計時開始
        start_time = time.time()

        # 呼叫 Claude CLI（只呼叫一次，不重試）
        # 注意：此 timeout 是整體 Claude CLI 的執行時間，包含所有工具呼叫
        # 當 nanobanana (Gemini Pro) timeout 或回傳錯誤時，會觸發 fallback
        response = await call_claude(
            prompt=user_message,
            model=model,
            history=history,
            system_prompt=system_prompt,
            timeout=480,  # 8 分鐘，支援複雜任務
            tools=all_tools,
        )

        # 計算耗時
        duration_ms = int((time.time() - start_time) * 1000)

        # 記錄 AI Log
        await log_linebot_ai_call(
            message_uuid=message_uuid,
            line_group_id=line_group_id,
            is_group=is_group,
            input_prompt=user_message,
            history=history,
            system_prompt=system_prompt,
            allowed_tools=all_tools,
            model=model,
            response=response,
            duration_ms=duration_ms,
            tenant_id=tenant_id,
        )

        # 檢查 nanobanana 是否有錯誤（overloaded/timeout）
        nanobanana_error = extract_nanobanana_error(response.tool_calls)
        nanobanana_timeout = check_nanobanana_timeout(response.tool_calls)

        if nanobanana_error or nanobanana_timeout:
            # nanobanana (Gemini Pro) 失敗，嘗試三層 fallback
            error_reason = "timeout（無回應）" if nanobanana_timeout else nanobanana_error
            logger.warning(f"Nanobanana (Gemini Pro) 錯誤: {error_reason}")

            # 提取原始 prompt，嘗試 fallback
            original_prompt = extract_nanobanana_prompt(response.tool_calls)
            fallback_path = None
            service_used = None
            fallback_error = None

            if original_prompt:
                logger.info(f"嘗試 fallback: {original_prompt[:50]}...")
                fallback_path, service_used, fallback_error = await generate_image_with_fallback(
                    original_prompt, str(error_reason)
                )

                if fallback_path:
                    # Fallback 成功，準備圖片訊息
                    logger.info(f"Fallback 成功 ({service_used}): {fallback_path}")
                    from .mcp_server import prepare_file_message
                    file_msg = await prepare_file_message(fallback_path, ctos_tenant_id=str(tenant_id) if tenant_id else None)

                    # 加入 fallback 通知
                    notification = get_fallback_notification(service_used)
                    if notification:
                        ai_response = f"圖片已生成{notification}\n\n{file_msg}"
                    else:
                        ai_response = f"圖片已生成：\n\n{file_msg}"

            # 如果沒有 fallback 或所有服務都失敗，顯示錯誤訊息
            if not fallback_path:
                if nanobanana_timeout:
                    error_detail = "Gemini Pro 無回應（超時）"
                else:
                    error_detail = f"Gemini Pro: {nanobanana_error}"

                # 組合錯誤訊息（包含所有失敗的服務）
                if fallback_error:
                    ai_response = (
                        "⚠️ 圖片生成服務暫時無法使用\n\n"
                        f"已嘗試的服務：\n{fallback_error}\n\n"
                        "建議：請稍後再試"
                    )
                else:
                    ai_response = (
                        "⚠️ 圖片生成服務暫時無法使用\n\n"
                        f"原因：{error_detail}\n\n"
                        "建議：請稍後再試"
                    )
        elif not response.success:
            logger.error(f"Claude CLI 失敗: {response.error}")

            # 即使失敗（如 timeout），檢查是否有已完成的圖片生成
            # streaming 讀取讓我們能在 timeout 時保留已完成的 tool_calls
            if response.tool_calls:
                generated_images = extract_generated_images_from_tool_calls(response.tool_calls)
                if generated_images:
                    logger.info(f"失敗但有已生成的圖片: {generated_images}")
                    # 嘗試發送已生成的圖片
                    ai_response = f"抱歉，處理過程遇到問題，但圖片已經生成好了："
                    ai_response = await auto_prepare_generated_images(
                        ai_response, response.tool_calls, tenant_id=tenant_id
                    )
                    # 繼續後續的發送流程（不 return）
                else:
                    return None
            else:
                return None
        else:
            ai_response = response.message

            # 自動處理 AI 生成的圖片（如果 AI 沒有呼叫 prepare_file_message）
            ai_response = await auto_prepare_generated_images(
                ai_response, response.tool_calls, tenant_id=tenant_id
            )

        # 標記訊息已處理
        await mark_message_ai_processed(message_uuid)

        # 解析 AI 回應，提取檔案訊息標記
        text_response, file_messages = parse_ai_response(ai_response)

        # 回覆訊息並取得 Line 訊息 ID（用於回覆觸發功能）
        # 群組對話時，mention 發問的用戶
        line_message_ids = []
        reply_success = False
        if reply_token and (text_response or file_messages):
            try:
                # 回覆時使用 bot_tenant_id（接收 webhook 的 Bot）
                line_message_ids = await send_ai_response(
                    reply_token=reply_token,
                    text=text_response,
                    file_messages=file_messages,
                    mention_line_user_id=line_user_id if is_group else None,
                    tenant_id=bot_tenant_id,
                )
                reply_success = True
            except Exception as e:
                logger.warning(f"回覆訊息失敗（token 可能已過期）: {e}")

        # Reply 失敗時 fallback 到 push message（合併發送）
        if not reply_success and (text_response or file_messages):
            logger.info("嘗試使用 push message 發送訊息...")
            # 取得發送目標（個人對話用 line_user_id，群組用 line_group_external_id）
            push_target = None
            if is_group and line_group_id:
                push_target = await get_line_group_external_id(line_group_id, tenant_id=tenant_id)
            else:
                push_target = line_user_id

            if push_target:
                # 建立訊息列表（合併文字和圖片訊息）
                from linebot.v3.messaging import TextMessage as LBTextMessage, ImageMessage as LBImageMessage

                push_message_list: list[LBTextMessage | LBImageMessage] = []

                # 文字訊息放在前面
                if text_response:
                    push_message_list.append(LBTextMessage(text=text_response))

                # 圖片訊息放在後面
                for file_info in file_messages:
                    if file_info.get("type") == "image" and file_info.get("url"):
                        push_message_list.append(LBImageMessage(
                            original_content_url=file_info["url"],
                            preview_image_url=file_info.get("preview_url") or file_info["url"],
                        ))

                # 合併發送所有訊息
                # Push 時使用 bot_tenant_id（接收 webhook 的 Bot）
                if push_message_list:
                    sent_ids, error = await push_messages(push_target, push_message_list, tenant_id=bot_tenant_id)
                    if sent_ids:
                        line_message_ids.extend(sent_ids)
                        logger.info(f"Push 合併訊息成功，共 {len(sent_ids)} 則: {sent_ids}")
                    if error:
                        logger.warning(f"Push 訊息失敗或部分失敗: {error}")
            else:
                logger.warning("無法取得 push 發送目標")

        # 儲存 Bot 回應到資料庫（包含所有 Line 訊息 ID）
        # 計算文字和圖片訊息的對應關係
        # send_ai_response 順序：先文字（如有），再圖片
        text_msg_count = 1 if text_response else 0
        image_messages = [f for f in file_messages if f.get("type") == "image"]

        for i, msg_id in enumerate(line_message_ids):
            if i == 0 and text_response:
                # 第一則是文字訊息
                await save_bot_response(
                    group_uuid=line_group_id,
                    content=text_response,
                    responding_to_line_user_id=line_user_id if not is_group else None,
                    line_message_id=msg_id,
                    tenant_id=tenant_id,
                )
            else:
                # 圖片訊息
                img_idx = i - text_msg_count
                img_info = image_messages[img_idx] if img_idx < len(image_messages) else {}
                file_name = img_info.get("name", "附件")
                nas_path = img_info.get("nas_path")

                # 儲存訊息記錄
                bot_message_uuid = await save_bot_response(
                    group_uuid=line_group_id,
                    content=f"[Bot 發送的圖片: {file_name}]",
                    responding_to_line_user_id=line_user_id if not is_group else None,
                    line_message_id=msg_id,
                    tenant_id=tenant_id,
                )

                # 儲存圖片檔案記錄（讓用戶可以回覆 Bot 的圖片進行編輯）
                # 傳遞 tenant_id 以支援租戶隔離
                if nas_path:
                    await save_file_record(
                        message_uuid=bot_message_uuid,
                        file_type="image",
                        file_name=file_name,
                        nas_path=nas_path,
                        tenant_id=tenant_id,
                    )
                    logger.debug(f"已儲存 Bot 圖片記錄: {file_name} -> {nas_path}")

        return text_response

    except Exception as e:
        import traceback
        logger.error(f"AI 處理訊息失敗: {e}\n{traceback.format_exc()}")
        return None


async def log_linebot_ai_call(
    message_uuid: UUID,
    line_group_id: UUID | None,
    is_group: bool,
    input_prompt: str,
    history: list[dict] | None,
    system_prompt: str,
    allowed_tools: list[str] | None,
    model: str,
    response,
    duration_ms: int,
    tenant_id: UUID | None = None,
) -> None:
    """
    記錄 Line Bot AI 調用到 AI Log

    Args:
        message_uuid: 訊息 UUID
        line_group_id: 群組 UUID
        is_group: 是否為群組對話
        input_prompt: 輸入的 prompt（當前訊息）
        history: 對話歷史
        system_prompt: 系統提示
        allowed_tools: 允許使用的工具列表
        model: 使用的模型
        response: Claude 回應物件
        duration_ms: 耗時（毫秒）
        tenant_id: 租戶 ID
    """
    try:
        # 根據對話類型取得對應的 Agent
        agent_name = AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL
        agent = await ai_manager.get_agent_by_name(agent_name, tenant_id=tenant_id)
        agent_id = agent["id"] if agent else None
        prompt_id = agent.get("system_prompt", {}).get("id") if agent else None

        # 將 tool_calls 和 tool_timings 轉換為可序列化的格式
        parsed_response = None
        if response.tool_calls or response.tool_timings:
            parsed_response = {}
            if response.tool_calls:
                parsed_response["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                        "output": tc.output,
                    }
                    for tc in response.tool_calls
                ]
            if response.tool_timings:
                parsed_response["tool_timings"] = response.tool_timings

        # 組合完整輸入（含歷史對話）
        if history:
            full_input = compose_prompt_with_history(history, input_prompt)
        else:
            full_input = input_prompt

        # 建立 Log
        log_data = AiLogCreate(
            agent_id=agent_id,
            prompt_id=prompt_id,
            context_type="linebot-group" if is_group else "linebot-personal",
            context_id=str(message_uuid),
            input_prompt=full_input,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            raw_response=response.message if response.success else None,
            parsed_response=parsed_response,
            model=model,
            success=response.success,
            error_message=response.error if not response.success else None,
            duration_ms=duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            tenant_id=tenant_id,
        )

        await ai_manager.create_log(log_data, tenant_id=tenant_id)
        logger.debug(f"已記錄 AI Log: agent={agent_name}, message_uuid={message_uuid}, success={response.success}")

    except Exception as e:
        # Log 記錄失敗不影響主流程
        logger.warning(f"記錄 AI Log 失敗: {e}")


async def get_conversation_context(
    line_group_id: UUID | None,
    line_user_id: str | None,
    limit: int = 20,
    exclude_message_id: UUID | None = None,
    tenant_id: UUID | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    取得對話上下文（包含圖片和檔案訊息）

    Args:
        line_group_id: 群組 UUID（None 表示個人對話）
        line_user_id: Line 用戶 ID（個人對話用）
        limit: 取得的訊息數量
        exclude_message_id: 要排除的訊息 ID（避免當前訊息重複）
        tenant_id: 租戶 ID

    Returns:
        (context, images, files) tuple:
        - context: 訊息列表 [{"role": "user/assistant", "content": "..."}]
        - images: 圖片資訊列表 [{"line_message_id": "...", "nas_path": "..."}]
        - files: 檔案資訊列表 [{"line_message_id": "...", "nas_path": "...", "file_name": "...", "file_size": ...}]
    """
    from .linebot import get_temp_image_path

    async with get_connection() as conn:
        if line_group_id:
            # 群組對話（包含 text、image 和 file）
            rows = await conn.fetch(
                """
                SELECT m.content, m.is_from_bot, u.display_name,
                       m.message_type, m.message_id as line_message_id,
                       f.nas_path, f.file_name, f.file_size, f.file_type as actual_file_type
                FROM line_messages m
                LEFT JOIN line_users u ON m.line_user_id = u.id
                LEFT JOIN line_files f ON f.message_id = m.id
                WHERE m.line_group_id = $1
                  AND ($3::uuid IS NULL OR m.id != $3)
                  AND m.message_type IN ('text', 'image', 'file')
                  AND (m.content IS NOT NULL OR m.message_type IN ('image', 'file'))
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                line_group_id,
                limit,
                exclude_message_id,
            )
        elif line_user_id:
            # 個人對話：查詢該用戶的對話歷史，考慮對話重置時間
            rows = await conn.fetch(
                """
                SELECT m.content, m.is_from_bot, u.display_name,
                       m.message_type, m.message_id as line_message_id,
                       f.nas_path, f.file_name, f.file_size, f.file_type as actual_file_type
                FROM line_messages m
                LEFT JOIN line_users u ON m.line_user_id = u.id
                LEFT JOIN line_files f ON f.message_id = m.id
                WHERE u.line_user_id = $1
                  AND ($3::uuid IS NULL OR m.id != $3)
                  AND m.line_group_id IS NULL
                  AND m.message_type IN ('text', 'image', 'file')
                  AND (m.content IS NOT NULL OR m.message_type IN ('image', 'file'))
                  AND (
                    u.conversation_reset_at IS NULL
                    OR m.created_at > u.conversation_reset_at
                  )
                ORDER BY m.created_at DESC
                LIMIT $2
                """,
                line_user_id,
                limit,
                exclude_message_id,
            )
        else:
            return [], [], []

        # 反轉順序（從舊到新）
        rows = list(reversed(rows))

        # 找出最新的圖片訊息 ID（用於標記）
        latest_image_id = None
        for row in reversed(rows):  # 從新到舊找第一張有 nas_path 的圖片
            if row["message_type"] == "image" and row["nas_path"]:
                latest_image_id = row["line_message_id"]
                break

        # 找出最新的檔案訊息 ID（用於標記）
        latest_file_id = None
        for row in reversed(rows):
            if row["message_type"] == "file" and row["nas_path"]:
                latest_file_id = row["line_message_id"]
                break

        context = []
        images = []
        files = []

        for row in rows:
            role = "assistant" if row["is_from_bot"] else "user"

            if row["message_type"] == "image" and row["nas_path"]:
                # 圖片訊息：確保暫存存在並格式化為特殊標記
                temp_path = await ensure_temp_image(
                    row["line_message_id"], row["nas_path"], tenant_id=tenant_id
                )
                if temp_path:
                    # 暫存成功，標記最新的圖片
                    if row["line_message_id"] == latest_image_id:
                        content = f"[上傳圖片（最近）: {temp_path}]"
                    else:
                        content = f"[上傳圖片: {temp_path}]"
                    # 記錄圖片資訊（暫存成功才加入）
                    images.append({
                        "line_message_id": row["line_message_id"],
                        "nas_path": row["nas_path"],
                    })
                else:
                    # 暫存失敗，提示使用 MCP 工具
                    content = "[圖片暫存已過期，若要加入知識庫請使用 get_message_attachments]"
            elif row["message_type"] == "file" and row["nas_path"]:
                # 檔案訊息：根據是否可讀取決定顯示方式
                file_name = row["file_name"] or "unknown"
                file_size = row["file_size"]

                if is_readable_file(file_name):
                    if file_size and file_size > MAX_READABLE_FILE_SIZE:
                        # 檔案過大
                        content = f"[上傳檔案: {file_name}（檔案過大）]"
                    else:
                        # 可讀取的檔案：確保暫存存在
                        temp_path = await ensure_temp_file(
                            row["line_message_id"], row["nas_path"], file_name, file_size, tenant_id=tenant_id
                        )
                        if temp_path:
                            # 使用共用函式解析 PDF 特殊格式
                            pdf_path, txt_path = parse_pdf_temp_path(temp_path)
                            is_recent = row["line_message_id"] == latest_file_id

                            if pdf_path != temp_path:
                                # 是 PDF 特殊格式
                                if txt_path:
                                    prefix = "上傳 PDF（最近）" if is_recent else "上傳 PDF"
                                    content = f"[{prefix}: {pdf_path}（文字版: {txt_path}）]"
                                else:
                                    prefix = "上傳 PDF（最近）" if is_recent else "上傳 PDF"
                                    content = f"[{prefix}: {pdf_path}（純圖片，無文字）]"
                            else:
                                # 一般檔案
                                prefix = "上傳檔案（最近）" if is_recent else "上傳檔案"
                                content = f"[{prefix}: {temp_path}]"
                            # 記錄檔案資訊（暫存成功才加入）
                            files.append({
                                "line_message_id": row["line_message_id"],
                                "nas_path": row["nas_path"],
                                "file_name": file_name,
                                "file_size": file_size,
                            })
                        else:
                            # 暫存失敗
                            content = f"[檔案 {file_name} 暫存已過期，若要加入知識庫請使用 get_message_attachments]"
                else:
                    # 不可讀取的檔案類型
                    if is_legacy_office_file(file_name):
                        # 舊版 Office 格式，提示轉檔
                        content = f"[上傳檔案: {file_name}（不支援舊版格式，請轉存為 .docx/.xlsx/.pptx）]"
                    else:
                        content = f"[上傳檔案: {file_name}（無法讀取此類型）]"
            else:
                content = row["content"]

            # 群組對話才記錄發送者名稱，個人對話不需要
            sender = None
            if line_group_id and not row["is_from_bot"] and row["display_name"]:
                sender = row["display_name"]

            context.append({"role": role, "content": content, "sender": sender})

        return context, images, files


async def build_system_prompt(
    line_group_id: UUID | None,
    line_user_id: str | None,
    base_prompt: str,
    builtin_tools: list[str] | None = None,
    tenant_id: UUID | None = None,
    app_permissions: dict[str, bool] | None = None,
) -> str:
    """
    建立系統提示

    Args:
        line_group_id: 群組 UUID（群組對話用）
        line_user_id: Line 用戶 ID（個人對話用）
        base_prompt: 從 Agent 取得的基礎 prompt
        builtin_tools: 內建工具列表（如 WebSearch, WebFetch）
        tenant_id: 租戶 ID
        app_permissions: 使用者的 App 權限設定（用於動態生成工具說明）

    Returns:
        系統提示文字
    """
    # 添加內建工具說明（根據啟用的工具動態組合）
    # Read 工具永遠啟用
    all_tools = set(builtin_tools or [])
    all_tools.add("Read")

    tool_sections = []

    # WebFetch 工具說明（包含 Google 文件處理）
    if "WebFetch" in all_tools:
        tool_sections.append("""【網頁讀取】
- 網頁連結（http/https）→ 使用 WebFetch 工具讀取
- Google 文件連結處理：
  · Google Docs: https://docs.google.com/document/d/{id}/... → 轉成 https://docs.google.com/document/d/{id}/export?format=txt
  · Google Sheets: https://docs.google.com/spreadsheets/d/{id}/... → 轉成 https://docs.google.com/spreadsheets/d/{id}/export?format=csv
  · Google Slides: https://docs.google.com/presentation/d/{id}/... → 轉成 https://docs.google.com/presentation/d/{id}/export?format=txt
  · 轉換後再用 WebFetch 讀取""")

    # WebSearch 工具說明
    if "WebSearch" in all_tools:
        tool_sections.append("""【網路搜尋】
- WebSearch - 搜尋網路資訊，可用於查詢天氣、新聞、公司資訊等""")

    # Read 工具說明（用戶上傳內容處理）
    if "Read" in all_tools:
        tool_sections.append("""【用戶上傳內容處理】
對話歷史中可能包含用戶上傳的圖片或檔案：
- [上傳圖片: /tmp/...] → 使用 Read 工具檢視圖片內容
- [上傳檔案: /tmp/...] → 使用 Read 工具讀取檔案內容
- [上傳 PDF: /tmp/xxx.pdf（文字版: /tmp/xxx.txt）] → PDF 檔案
  · 讀取文字內容：用 Read 工具讀取「文字版」路徑（.txt）
  · 轉成圖片：用 convert_pdf_to_images 處理 PDF 路徑（.pdf）
- [上傳 PDF: /tmp/xxx.pdf（純圖片，無文字）] → 掃描版 PDF，沒有文字可提取
  · 只能用 convert_pdf_to_images 轉成圖片
- [回覆 PDF: ...] → 同上，用戶回覆的 PDF
- [圖片暫存已過期...] 或 [檔案...暫存已過期...] → 暫存已清理，無法直接檢視
- [上傳檔案: filename（無法讀取此類型）] → 告知用戶此類型不支援
- [上傳檔案: filename（不支援舊版格式...）] → 建議用戶轉存為新版格式

支援的檔案類型：
- 純文字：txt, md, json, csv, log, xml, yaml, yml
- Office 文件：docx, xlsx, pptx（自動轉換為純文字）
- PDF 文件：pdf（同時提供原始檔和純文字版）
注意：Office 文件會自動轉換為純文字，可能遺失格式資訊。
舊版格式（.doc, .xls, .ppt）不支援，請建議用戶轉存為新版格式。

重要：Read 工具僅用於「檢視」圖片/檔案內容（例如「這張圖是什麼？」）。
若要將圖片/檔案「加入知識庫」，請使用 get_message_attachments 查詢 NAS 路徑，
再使用 add_note_with_attachments 或 add_attachments_to_knowledge。""")

    # 分享連結工具說明
    tool_sections.append("""【公開分享連結】
當用戶想要分享知識庫或專案給其他人（例如沒有帳號的人）查看時，使用 create_share_link 工具：
- resource_type: "knowledge"（知識庫）或 "project"（專案）
- resource_id: 知識庫 ID（如 kb-001）或專案 UUID
- expires_in: 有效期限，可選 "1h"、"24h"、"7d"、"null"（永久），預設 24h

使用情境：
- 「幫我產生 kb-001 的分享連結」
- 「我想分享這個知識給客戶看」
- 「產生一個永久的專案連結」
- 「給我一個 7 天有效的連結」

連結可以讓沒有帳號的人直接在瀏覽器查看內容。""")

    if tool_sections:
        base_prompt += "\n\n" + "\n\n".join(tool_sections)

    # 動態生成 MCP 工具說明（根據使用者權限）
    if app_permissions:
        from .linebot_agents import generate_tools_prompt, generate_usage_tips_prompt
        is_group = line_group_id is not None
        tools_prompt = generate_tools_prompt(app_permissions, is_group)
        if tools_prompt:
            base_prompt += "\n\n你可以使用以下工具：\n\n" + tools_prompt
        # 加入使用說明
        usage_tips = generate_usage_tips_prompt(app_permissions, is_group)
        if usage_tips:
            base_prompt += "\n\n" + usage_tips

    # 加入對話識別資訊（供 MCP 工具使用）
    # 查詢用戶的 CTOS user_id（用於權限檢查）
    # 注意：同一個 Line 用戶可能在多個租戶有記錄，必須用 tenant_id 過濾
    ctos_user_id = None
    line_user_uuid = None
    if line_user_id:
        user_row = await get_line_user_record(line_user_id, tenant_id, "id, user_id")
        if user_row:
            line_user_uuid = user_row["id"]
            if user_row["user_id"]:
                ctos_user_id = user_row["user_id"]

    # 載入並整合自訂記憶
    from .linebot import get_active_group_memories, get_active_user_memories

    memories = []
    if line_group_id:
        # 群組對話：載入群組記憶
        memories = await get_active_group_memories(line_group_id)
    elif line_user_uuid:
        # 個人對話：載入個人記憶
        memories = await get_active_user_memories(line_user_uuid)

    if memories:
        memory_lines = [f"{i+1}. {m['content']}" for i, m in enumerate(memories)]
        memory_block = """

【自訂記憶】
以下是此對話的自訂記憶，請在回應時遵循這些規則：
""" + "\n".join(memory_lines) + """

請自然地遵循上述規則，不需要特別提及或確認。"""
        base_prompt += memory_block

    if line_group_id:
        async with get_connection() as conn:
            group = await conn.fetchrow(
                """
                SELECT g.name, g.project_id, p.name as project_name
                FROM line_groups g
                LEFT JOIN projects p ON g.project_id = p.id
                WHERE g.id = $1
                """,
                line_group_id,
            )
            if group:
                base_prompt += f"\n\n目前群組：{group['name'] or '未命名群組'}"
                if group["project_name"]:
                    base_prompt += f"\n綁定專案：{group['project_name']}"
                    base_prompt += f"\n專案 ID（供工具查詢用）：{group['project_id']}"
        # 加入群組 ID 和用戶身份識別
        base_prompt += f"\n\n【對話識別】\nline_group_id: {line_group_id}"
        if tenant_id:
            base_prompt += f"\nctos_tenant_id: {tenant_id}"
        if ctos_user_id:
            base_prompt += f"\nctos_user_id: {ctos_user_id}"
        else:
            base_prompt += "\nctos_user_id: （未關聯）"
    elif line_user_id:
        # 個人對話：加入用戶 ID 和身份識別
        base_prompt += f"\n\n【對話識別】\nline_user_id: {line_user_id}"
        if tenant_id:
            base_prompt += f"\nctos_tenant_id: {tenant_id}"
        if ctos_user_id:
            base_prompt += f"\nctos_user_id: {ctos_user_id}"
        else:
            base_prompt += "\nctos_user_id: （未關聯，無法進行專案更新操作）"

    return base_prompt


# ============================================================
# Webhook 處理入口
# ============================================================


async def handle_text_message(
    message_id: str,
    message_uuid: UUID,
    content: str,
    line_user_id: str,
    line_group_id: UUID | None,
    reply_token: str | None,
    quoted_message_id: str | None = None,
    tenant_id: UUID | None = None,
    bot_tenant_id: UUID | None = None,
) -> None:
    """
    處理文字訊息的 Webhook 入口

    Args:
        message_id: Line 訊息 ID
        message_uuid: 內部訊息 UUID
        content: 訊息內容
        line_user_id: Line 用戶 ID
        line_group_id: 內部群組 UUID（個人對話為 None）
        reply_token: Line 回覆 token
        quoted_message_id: 被回覆的訊息 ID（用戶回覆舊訊息時）
        tenant_id: 租戶 ID（用於業務邏輯：AI、知識庫等）
        bot_tenant_id: Bot 租戶 ID（用於回覆訊息的 credentials）
            - 有值：使用該租戶的 Line Bot credentials
            - None：使用環境變數的 credentials（共用 Bot）
    """
    # 取得用戶顯示名稱（同一個 Line 用戶可能在多個租戶有記錄，用 tenant_id 過濾）
    user_display_name = None
    user_row = await get_line_user_record(line_user_id, tenant_id, "display_name")
    if user_row:
        user_display_name = user_row["display_name"]

    # 處理訊息
    await process_message_with_ai(
        message_uuid=message_uuid,
        content=content,
        line_group_id=line_group_id,
        line_user_id=line_user_id,
        reply_token=reply_token,
        user_display_name=user_display_name,
        quoted_message_id=quoted_message_id,
        tenant_id=tenant_id,
        bot_tenant_id=bot_tenant_id,
    )
