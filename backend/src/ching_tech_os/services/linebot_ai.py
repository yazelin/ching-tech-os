"""Line Bot AI 處理服務

使用 Claude CLI 處理 Line 訊息（與 AI 助手相同架構）
整合 AI Log 記錄功能

注意：平台無關的純函式已遷移至 services/bot/ai.py，
此模組透過 re-export 保持向後相容。
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
from .bot_line import (
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

# 從 bot.ai 匯入平台無關的純函式（向後相容 re-export）
from .bot.ai import (
    parse_ai_response,
    extract_nanobanana_error,
    extract_nanobanana_prompt,
    check_nanobanana_timeout,
    get_user_friendly_nanobanana_error,
    extract_generated_images_from_tool_calls,
)
from .bot.media import parse_pdf_temp_path

logger = logging.getLogger("linebot_ai")



async def auto_prepare_generated_images(
    ai_response: str,
    tool_calls: list,
) -> str:
    """
    自動處理 AI 生成的圖片，確保用戶能收到圖片

    如果 AI 呼叫了 generate_image 但沒有呼叫 prepare_file_message，
    自動補上 FILE_MESSAGE 標記。

    如果圖片生成失敗（如 overloaded），會在回應中加入明確的錯誤提示。

    Args:
        ai_response: AI 回應文字
        tool_calls: Claude response 的 tool_calls 列表

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
    from .mcp.nas_tools import prepare_file_message

    file_messages = []
    for file_path in unprocessed_files:
        try:
            # nanobanana 輸出的路徑是完整路徑，需要轉換為相對路徑
            # /tmp/ching-tech-os-cli/nanobanana-output/xxx.jpg -> nanobanana-output/xxx.jpg
            if "nanobanana-output/" in file_path:
                relative_path = "nanobanana-output/" + file_path.split("nanobanana-output/")[-1]
            else:
                relative_path = file_path

            result = await prepare_file_message(relative_path)
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
# parse_ai_response 已遷移至 services/bot/ai.py，透過頂部 import 保持相容


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


LINE_TEXT_MAX_CHARS = 5000


def _split_long_text(text: str, max_chars: int = LINE_TEXT_MAX_CHARS) -> list[str]:
    """將超過 LINE 上限的長文字分割成多段（在換行處斷開）。"""
    if not text or len(text) <= max_chars:
        return [text] if text else []

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        # 在 max_chars 以內找最後一個換行位置
        cut = remaining.rfind("\n", 0, max_chars)
        if cut <= 0:
            # 沒有換行，找空白
            cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            # 都沒有，硬切
            cut = max_chars
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n ")
    return chunks


async def send_ai_response(
    reply_token: str,
    text: str,
    file_messages: list[dict],
    mention_line_user_id: str | None = None,
) -> list[str]:
    """
    發送 AI 回應（文字 + 檔案訊息）

    Args:
        reply_token: Line 回覆 token
        text: 文字回覆
        file_messages: 檔案訊息列表
        mention_line_user_id: 要 mention 的 Line 用戶 ID（群組對話時使用）

    Returns:
        發送成功的訊息 ID 列表
    """
    from linebot.v3.messaging import ImageMessage

    messages = []

    # 先加入文字訊息（顯示在上方）
    # 如果有提供 mention_line_user_id，使用 TextMessageV2 帶 mention
    # LINE 單則訊息上限 5000 字，超過時自動分割
    if text:
        text_chunks = _split_long_text(text)
        for chunk in text_chunks:
            messages.append(create_text_message_with_mention(chunk, mention_line_user_id))

    # 再處理檔案訊息
    for file_info in file_messages:
        file_type = file_info.get("type", "file")
        url = file_info.get("url", "")
        name = file_info.get("name", "")
        size = file_info.get("size", "")

        if file_type == "image" and url:
            # 圖片：使用 ImageMessage（顯示在文字下方）
            # 優先使用 original_url（HTTPS），Line API 要求必須是 HTTPS URL
            image_url = file_info.get("original_url") or url
            messages.append(ImageMessage(
                original_content_url=image_url,
                preview_image_url=image_url,
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

    # 發送訊息
    return await reply_messages(reply_token, messages)


# ============================================================
# research-skill 輔助
# ============================================================


def _parse_json_object(text: str) -> dict | None:
    """解析 JSON 物件字串，失敗回傳 None。"""
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _extract_research_job_id_from_text(text: str) -> str:
    """從使用者文字中提取 research job_id（8 碼十六進位）。"""
    if not text:
        return ""
    match = re.search(r"\b([0-9a-fA-F]{8})\b", text)
    if not match:
        return ""
    return match.group(1).lower()


def _should_force_research_check_mode(text: str) -> bool:
    """判斷是否為研究進度查詢語意（需禁用同步 WebSearch/WebFetch）。"""
    job_id = _extract_research_job_id_from_text(text)
    if not job_id:
        return False
    lowered = (text or "").lower()
    keywords = ("research", "check-research", "job_id", "研究", "進度")
    return any(keyword in lowered for keyword in keywords)



def _summarize_for_line(
    final_summary: str,
    payload: dict,
    max_chars: int = 3000,
) -> str:
    """從 final_summary 萃取重點摘要，控制在 LINE 安全字數內。

    策略：
    1. 若 final_summary 為空，fallback 到 partial_results snippets
    2. 若 final_summary 有 Markdown 結構，擷取「統整摘要」之後的內容
    3. 最後截斷到 max_chars
    """
    if not final_summary:
        # fallback：從 partial_results 組合
        partial_results = payload.get("partial_results") or []
        lines = []
        for item in partial_results[:5]:
            if not isinstance(item, dict):
                continue
            snippet = str(item.get("snippet") or "").strip()
            if snippet:
                title = str(item.get("title") or item.get("url") or "來源")
                lines.append(f"• {title}：{snippet[:200]}")
        if lines:
            return "\n".join(lines)
        return "研究已完成，但未能產生摘要。"

    # 嘗試擷取「統整摘要」區段（result.md 的結構是 ## 統整摘要 → 內容 → ## 來源）
    summary_section = final_summary
    match = re.search(r"(?:^|\n)##\s*統整摘要\s*\n(.*?)(?:\n##\s|$)", final_summary, re.DOTALL)
    if match:
        summary_section = match.group(1).strip()

    # 若仍太長，截斷
    if len(summary_section) > max_chars:
        # 在句尾斷開
        cut = summary_section.rfind("。", 0, max_chars)
        if cut <= 0:
            cut = summary_section.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        summary_section = summary_section[:cut + 1] + "\n\n…（略）"

    # 附加參考來源（最多 3 筆）
    sources = payload.get("sources") or []
    if sources:
        source_lines = []
        for src in sources[:3]:
            if not isinstance(src, dict):
                continue
            title = str(src.get("title") or src.get("url") or "來源")
            url = str(src.get("url") or "").strip()
            source_lines.append(f"• {title}" + (f"\n  {url}" if url else ""))
        if source_lines:
            summary_section += "\n\n參考來源：\n" + "\n".join(source_lines)

    return summary_section


def _extract_research_tool_feedback(tool_calls: list) -> dict | None:
    """從 run_skill_script(research-skill) 的工具輸出組合可回覆訊息。"""
    for tool_call in reversed(tool_calls or []):
        tool_name = getattr(tool_call, "name", "")
        if tool_name != "mcp__ching-tech-os__run_skill_script":
            continue

        tool_input = getattr(tool_call, "input", {}) or {}
        if tool_input.get("skill") != "research-skill":
            continue

        script_name = str(tool_input.get("script") or "")
        raw_output = str(getattr(tool_call, "output", "") or "")
        wrapper = _parse_json_object(raw_output)
        if not wrapper:
            continue

        # 逐層展開巢狀 JSON（可能有 "output" 或 "result" key 包裝）
        payload = wrapper
        for _depth in range(3):  # 最多展開 3 層
            unwrapped = False
            for key in ("output", "result"):
                nested = payload.get(key)
                if isinstance(nested, str):
                    parsed_nested = _parse_json_object(nested)
                    if parsed_nested:
                        payload = parsed_nested
                        unwrapped = True
                        break
            if not unwrapped:
                break

        # start-research: 確保 job_id 一定回到使用者
        if script_name == "start-research":
            if payload.get("success") is True:
                job_id = str(payload.get("job_id") or "").strip()
                if job_id:
                    message = (
                        f"✅ 研究任務已受理（job_id: {job_id}）。\n"
                        f"請稍後提供 job_id 或輸入「查詢研究進度 {job_id}」，我會幫你查最新狀態。"
                    )
                else:
                    message = "✅ 研究任務已受理，請稍後再查詢進度。"
                return {
                    "script": script_name,
                    "job_id": job_id,
                    "message": message,
                }

            error = payload.get("error") or wrapper.get("error") or "未知錯誤"
            return {
                "script": script_name,
                "job_id": "",
                "message": f"⚠️ 研究任務啟動失敗：{error}",
            }

        # check-research: 依狀態回覆進度/完成/失敗
        if script_name == "check-research":
            if payload.get("success") is False:
                error = payload.get("error") or wrapper.get("error") or "未知錯誤"
                return {
                    "script": script_name,
                    "job_id": str(payload.get("job_id") or ""),
                    "message": f"⚠️ 查詢研究進度失敗：{error}",
                }

            status = str(payload.get("status") or "").strip()
            job_id = str(payload.get("job_id") or "").strip()

            if status == "completed":
                summary = str(payload.get("final_summary") or "").strip()
                result_ctos_path = str(payload.get("result_ctos_path") or "").strip()

                # 若 final_summary 是 API Error（合成階段失敗），改用來源摘要
                if not summary or summary.startswith("API Error:"):
                    summary = ""

                # 萃取重點摘要（控制在 LINE 字數安全範圍）
                key_points = _summarize_for_line(summary, payload)

                # 計算完整報告長度（用於告知使用者）
                full_len = len(summary) if summary else 0

                # 組合訊息：重點摘要 + 詢問是否存知識庫
                message = f"✅ 研究完成\n\n{key_points}"
                if full_len > 0:
                    save_hint = (
                        f"\n\n---\n"
                        f"以上為重點摘要（完整報告約 {full_len} 字）。\n"
                        f"如需保存完整報告，請回覆「存知識庫」，"
                        f"我會將完整內容存入知識庫並產生 24 小時暫存連結。"
                    )
                    if result_ctos_path:
                        save_hint += f"\n[result_path:{result_ctos_path}]"
                    message += save_hint

                return {
                    "script": script_name,
                    "job_id": job_id,
                    "message": message,
                }

            if status == "failed":
                error = payload.get("error") or "研究任務失敗"
                return {
                    "script": script_name,
                    "job_id": job_id,
                    "message": f"⚠️ 研究任務失敗：{error}",
                }
            if status == "canceled":
                return {
                    "script": script_name,
                    "job_id": job_id,
                    "message": "⚠️ 研究任務已取消。",
                }

            status_label = str(payload.get("status_label") or status or "進行中")
            stage_label = str(payload.get("stage_label") or "").strip()
            progress = payload.get("progress")
            progress_text = ""
            if isinstance(progress, (int, float)):
                progress_text = f" {int(progress)}%"

            partial_lines = []
            partial_results = payload.get("partial_results") or []
            for item in partial_results[:2]:
                if not isinstance(item, dict):
                    continue
                snippet = str(item.get("snippet") or "").strip()
                if not snippet:
                    continue
                title = str(item.get("title") or item.get("url") or "來源")
                partial_lines.append(f"- {title}：{snippet[:120]}" + ("..." if len(snippet) > 120 else ""))

            stage_text = f"｜{stage_label}" if stage_label else ""
            message = f"⏳ 研究任務進行中（{status_label}{stage_text}{progress_text}）。"
            if job_id:
                message += f"\njob_id: {job_id}"
            if partial_lines:
                message += "\n\n目前已取得資料：\n" + "\n".join(partial_lines)
            return {
                "script": script_name,
                "job_id": job_id,
                "message": message,
            }

    return None


# ============================================================
# 超時 Fallback：從已完成的工具結果中組合回覆
# ============================================================


async def _fallback_summarize_from_tools(response) -> str:
    """超時時，從已完成的工具結果中提取有用內容作為 fallback 回覆。

    Claude CLI 多輪工具呼叫時，前幾輪可能已完成並有結果，
    但最後一輪的工具（如 WebFetch）卡住導致整體超時。
    此函數從已完成的 WebSearch/WebFetch 結果中組合出有用回覆。
    """
    # 收集 WebSearch/WebFetch 的 output
    search_outputs = []
    for tc in response.tool_calls:
        if tc.name in ("WebSearch", "WebFetch") and tc.output:
            search_outputs.append(tc.output)

    if search_outputs:
        # 取最後一個 WebSearch/WebFetch 的結果（通常是最詳細的）
        # 截取前 1500 字元避免 Line 訊息太長
        best_output = search_outputs[-1]
        if len(best_output) > 1500:
            best_output = best_output[:1500] + "..."

        logger.info(
            f"超時 fallback：從 {len(search_outputs)} 個搜尋結果中組合回覆"
        )
        return f"（處理過程較久，以下是目前查到的資料）\n\n{best_output}"

    # 沒有搜尋結果，檢查是否有部分文字回應
    if response.message and response.message.strip():
        logger.info(
            f"失敗但有部分文字回應（{len(response.message)} 字元），嘗試發送"
        )
        return response.message.strip()

    # 完全沒有可用內容
    return "⚠️ 抱歉，處理時間過長，請稍後再試一次。"


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
    bot_user_id: str | None = None,
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

    Returns:
        AI 回應文字，或 None（如果不需處理）
    """
    is_group = line_group_id is not None

    # 重置對話指令已由 CommandRouter 在 handle_text_message 中攔截處理

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
        # 群組 ID 轉換為字串（bot_groups.id 是 UUID）
        bot_group_id_str = str(line_group_id) if line_group_id else None
        agent = await get_linebot_agent(
            is_group,
            bot_user_id=bot_user_id,
            bot_group_id=bot_group_id_str,
        )

        if not agent:
            fallback_name = AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL
            error_msg = f"⚠️ AI 設定錯誤：Agent '{fallback_name}' 不存在"
            logger.error(error_msg)
            if reply_token:
                await reply_text(reply_token, error_msg)
            return error_msg

        # agent 保證非 None
        agent_name = agent.get("name", "")

        # 從 Agent 取得 model 和基礎 prompt
        model = agent.get("model", "opus").replace("claude-", "")  # claude-sonnet -> sonnet
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
                await reply_text(reply_token, error_msg)
            return error_msg

        # 先取得使用者權限（用於動態生成工具說明和過濾工具）
        from .user import get_user_role_and_permissions
        from .permissions import get_mcp_tools_for_user, get_user_app_permissions_sync
        ctos_user_id = None
        user_role = "user"
        user_permissions = None
        app_permissions: dict[str, bool] = {}
        if line_user_id:
            user_row = await get_line_user_record(line_user_id, "user_id")
            if user_row and user_row["user_id"]:
                ctos_user_id = user_row["user_id"]
                user_info = await get_user_role_and_permissions(ctos_user_id)
                user_role = user_info["role"]
                user_permissions = user_info["permissions"]
                # 計算 App 權限供 prompt 動態生成
                app_permissions = get_user_app_permissions_sync(user_role, user_info.get("user_data"))

        # 若未關聯 CTOS 帳號，使用預設權限（一般使用者）
        if not app_permissions:
            app_permissions = get_user_app_permissions_sync("user", None)

        # 建立系統提示（加入群組資訊、內建工具說明和動態 MCP 工具說明）
        system_prompt = await build_system_prompt(
            line_group_id, line_user_id, base_prompt, agent_tools, app_permissions,
            role=user_role,
        )

        # 取得對話歷史（20 則提供更好的上下文理解，包含圖片和檔案）
        # 排除當前訊息，避免重複（compose_prompt_with_history 會再加一次）
        history, images, files = await get_conversation_context(
            line_group_id, line_user_id, limit=20, exclude_message_id=message_uuid
        )

        # 處理回覆舊訊息（quotedMessageId）- 圖片、檔案或文字
        quoted_image_path = None
        quoted_file_path = None
        quoted_text_content = None
        if quoted_message_id:
            # 先嘗試查詢圖片
            image_info = await get_image_info_by_line_message_id(quoted_message_id)
            if image_info and image_info.get("nas_path"):
                # 確保圖片暫存存在
                temp_path = await ensure_temp_image(quoted_message_id, image_info["nas_path"])
                if temp_path:
                    quoted_image_path = temp_path
                    logger.info(f"用戶回覆圖片: {quoted_message_id} -> {temp_path}")
            else:
                # 嘗試查詢檔案
                file_info = await get_file_info_by_line_message_id(quoted_message_id)
                if file_info and file_info.get("nas_path") and file_info.get("file_name"):
                    file_name = file_info["file_name"]
                    file_size = file_info.get("file_size")
                    if is_readable_file(file_name):
                        if file_size and file_size > MAX_READABLE_FILE_SIZE:
                            logger.info(f"用戶回覆檔案過大: {quoted_message_id} -> {file_name}")
                        else:
                            # 確保檔案暫存存在
                            temp_path = await ensure_temp_file(
                                quoted_message_id, file_info["nas_path"], file_name, file_size
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

        # 內建 MCP 工具（ching-tech-os server）
        from .mcp import get_mcp_tool_names
        mcp_tools = await get_mcp_tool_names(exclude_group_only=not is_group)
        mcp_tools = get_mcp_tools_for_user(user_role, user_permissions, mcp_tools)
        logger.info(f"使用者權限過濾後的 MCP 工具數量: {len(mcp_tools)}, role={user_role}")

        # 外部 MCP 工具（由 SkillManager 動態產生，含 fallback）
        from .linebot_agents import (
            get_tools_for_user,
            get_mcp_servers_for_user,
            get_tool_routing_for_user,
        )
        tool_routing = await get_tool_routing_for_user(app_permissions, role=user_role)
        suppressed_tools = set(tool_routing.get("suppressed_mcp_tools") or [])
        if suppressed_tools:
            mcp_tools = [tool for tool in mcp_tools if tool not in suppressed_tools]
        skill_tools = await get_tools_for_user(app_permissions, role=user_role)
        all_tools = list(dict.fromkeys(agent_tools + mcp_tools + skill_tools))

        # 研究進度查詢模式：避免模型在 check-research 後又切回同步網頁重抓
        if _should_force_research_check_mode(content):
            all_tools = [tool for tool in all_tools if tool not in {"WebSearch", "WebFetch"}]
            logger.info("研究進度查詢模式：已禁用 WebSearch/WebFetch（避免重複抓網頁）")

        # 取得需要的 MCP server 集合（按需載入）
        required_mcp_servers = await get_mcp_servers_for_user(app_permissions, role=user_role)

        # 計時開始
        start_time = time.time()

        # 呼叫 Claude CLI（只呼叫一次，不重試）
        # 注意：此 timeout 是整體 Claude CLI 的執行時間，包含所有工具呼叫
        # 當 nanobanana MCP 完全失敗時（timeout/錯誤），會觸發 FLUX fallback
        # Gemini 模型間的 fallback（Pro → Flash）由 nanobanana MCP 內部自動處理
        response = await call_claude(
            prompt=user_message,
            model=model,
            history=history,
            system_prompt=system_prompt,
            timeout=480,  # 8 分鐘，支援複雜任務
            tools=all_tools,
            required_mcp_servers=required_mcp_servers,
            ctos_user_id=ctos_user_id,
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
            tool_routing=tool_routing,
            actual_agent_name=agent_name,
        )

        # 檢查 nanobanana 是否有錯誤（overloaded/timeout）
        nanobanana_error = extract_nanobanana_error(response.tool_calls)
        nanobanana_timeout = check_nanobanana_timeout(response.tool_calls)
        research_feedback = _extract_research_tool_feedback(response.tool_calls)

        if nanobanana_error or nanobanana_timeout:
            # nanobanana MCP 完全失敗（timeout/錯誤），嘗試 FLUX fallback
            # 注意：Gemini 模型間的 fallback（Pro → Flash）由 nanobanana MCP 內部處理
            error_reason = "timeout（無回應）" if nanobanana_timeout else nanobanana_error
            logger.warning(f"Nanobanana MCP 錯誤: {error_reason}")

            # 提取原始 prompt，嘗試 fallback
            original_prompt = extract_nanobanana_prompt(response.tool_calls)
            fallback_path = None
            service_used = None
            fallback_error = None

            if original_prompt:
                logger.info(f"嘗試 fallback: {original_prompt[:50]}...")
                fallback_path, service_used, fallback_error = await generate_image_with_fallback(
                    original_prompt, error_reason
                )

                if fallback_path:
                    # Fallback 成功，準備圖片訊息
                    logger.info(f"Fallback 成功 ({service_used}): {fallback_path}")
                    from .mcp.nas_tools import prepare_file_message
                    file_msg = await prepare_file_message(fallback_path)

                    # 加入 fallback 通知
                    notification = get_fallback_notification(service_used)
                    if notification:
                        ai_response = f"圖片已生成{notification}\n\n{file_msg}"
                    else:
                        ai_response = f"圖片已生成：\n\n{file_msg}"

            # 如果沒有 fallback 或所有服務都失敗，顯示錯誤訊息
            if not fallback_path:
                if nanobanana_timeout:
                    error_detail = "圖片生成服務無回應（超時）"
                else:
                    error_detail = f"圖片生成服務: {nanobanana_error}"

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

            if research_feedback:
                ai_response = research_feedback["message"]
            # 即使失敗（如 timeout），檢查是否有已完成的圖片生成
            # streaming 讀取讓我們能在 timeout 時保留已完成的 tool_calls
            elif response.tool_calls:
                generated_images = extract_generated_images_from_tool_calls(response.tool_calls)
                if generated_images:
                    logger.info(f"失敗但有已生成的圖片: {generated_images}")
                    # 嘗試發送已生成的圖片
                    ai_response = f"抱歉，處理過程遇到問題，但圖片已經生成好了："
                    ai_response = await auto_prepare_generated_images(
                        ai_response, response.tool_calls
                    )
                    # 繼續後續的發送流程（不 return）
                else:
                    # 超時但有已完成的工具結果，嘗試用結果做 fallback 總結
                    ai_response = await _fallback_summarize_from_tools(response)
            else:
                # 沒有 tool_calls，用 fallback 處理部分文字或錯誤提示
                ai_response = await _fallback_summarize_from_tools(response)
        else:
            ai_response = response.message

            if research_feedback:
                script_name = research_feedback.get("script")
                feedback_text = str(research_feedback.get("message") or "").strip()
                job_id = str(research_feedback.get("job_id") or "").strip()

                # start-research：確保回覆一定包含 job_id
                if script_name == "start-research" and feedback_text:
                    if not ai_response:
                        ai_response = feedback_text
                    elif job_id and job_id not in ai_response:
                        ai_response = ai_response.rstrip() + "\n\n" + feedback_text
                # check-research：一律使用已摘要的 feedback_text（已控制在 LINE 安全字數內）
                elif script_name == "check-research" and feedback_text:
                    ai_response = feedback_text
                elif feedback_text and not str(ai_response or "").strip():
                    ai_response = feedback_text

            # 自動處理 AI 生成的圖片（如果 AI 沒有呼叫 prepare_file_message）
            ai_response = await auto_prepare_generated_images(
                ai_response, response.tool_calls
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
                line_message_ids = await send_ai_response(
                    reply_token=reply_token,
                    text=text_response,
                    file_messages=file_messages,
                    mention_line_user_id=line_user_id if is_group else None,
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
                push_target = await get_line_group_external_id(line_group_id)
            else:
                push_target = line_user_id

            if push_target:
                # 建立訊息列表（合併文字和圖片訊息）
                from linebot.v3.messaging import TextMessage as LBTextMessage, ImageMessage as LBImageMessage

                push_message_list: list[LBTextMessage | LBImageMessage] = []

                # 文字訊息放在前面（超過 LINE 上限時自動分割）
                if text_response:
                    for chunk in _split_long_text(text_response):
                        push_message_list.append(LBTextMessage(text=chunk))

                # 圖片訊息放在後面
                for file_info in file_messages:
                    if file_info.get("type") == "image" and file_info.get("url"):
                        # 優先使用 original_url（HTTPS），Line API 要求必須是 HTTPS URL
                        img_url = file_info.get("original_url") or file_info["url"]
                        push_message_list.append(LBImageMessage(
                            original_content_url=img_url,
                            preview_image_url=file_info.get("preview_url") or img_url,
                        ))

                # 合併發送所有訊息
                if push_message_list:
                    sent_ids, error = await push_messages(push_target, push_message_list)
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
                )

                # 儲存圖片檔案記錄（讓用戶可以回覆 Bot 的圖片進行編輯）
                if nas_path:
                    await save_file_record(
                        message_uuid=bot_message_uuid,
                        file_type="image",
                        file_name=file_name,
                        nas_path=nas_path,
                    )
                    logger.debug(f"已儲存 Bot 圖片記錄: {file_name} -> {nas_path}")

        return text_response

    except Exception as e:
        import traceback
        logger.error(f"AI 處理訊息失敗: {e}\n{traceback.format_exc()}")
        return None


async def log_linebot_ai_call(
    message_uuid: UUID | None,
    line_group_id: UUID | None,
    is_group: bool,
    input_prompt: str,
    history: list[dict] | None,
    system_prompt: str,
    allowed_tools: list[str] | None,
    model: str,
    response,
    duration_ms: int,
    context_type_override: str | None = None,
    tool_routing: dict | None = None,
    actual_agent_name: str | None = None,
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
        tool_routing: 工具路由決策資訊（script-first / fallback）
        actual_agent_name: 實際使用的 Agent 名稱（如 jfmskin_edu），用於記錄正確的 agent_id
    """
    try:
        # 優先用實際使用的 Agent，否則依對話類型取得預設 Agent
        agent_name = actual_agent_name or (AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL)
        agent = await ai_manager.get_agent_by_name(agent_name)
        agent_id = agent["id"] if agent else None
        prompt_id = agent.get("system_prompt", {}).get("id") if agent else None

        # 將 tool_calls 和 tool_timings 轉換為可序列化的格式
        parsed_response = None
        if response.tool_calls or response.tool_timings or tool_routing:
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
            if tool_routing:
                parsed_response["tool_routing"] = tool_routing

        # 組合完整輸入（含歷史對話）
        if history:
            full_input = compose_prompt_with_history(history, input_prompt)
        else:
            full_input = input_prompt

        # 建立 Log
        log_data = AiLogCreate(
            agent_id=agent_id,
            prompt_id=prompt_id,
            context_type=context_type_override or ("linebot-group" if is_group else "linebot-personal"),
            context_id=str(message_uuid) if message_uuid else None,
            input_prompt=full_input,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            raw_response=response.message or None,
            parsed_response=parsed_response,
            model=model,
            success=response.success,
            error_message=response.error if not response.success else None,
            duration_ms=duration_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        await ai_manager.create_log(log_data)
        logger.debug(f"已記錄 AI Log: agent={agent_name}, message_uuid={message_uuid}, success={response.success}")

    except Exception as e:
        # Log 記錄失敗不影響主流程
        logger.warning(f"記錄 AI Log 失敗: {e}")


async def get_conversation_context(
    line_group_id: UUID | None,
    line_user_id: str | None,
    limit: int = 20,
    exclude_message_id: UUID | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    取得對話上下文（包含圖片和檔案訊息）

    Args:
        line_group_id: 群組 UUID（None 表示個人對話）
        line_user_id: Line 用戶 ID（個人對話用）
        limit: 取得的訊息數量
        exclude_message_id: 要排除的訊息 ID（避免當前訊息重複）

    Returns:
        (context, images, files) tuple:
        - context: 訊息列表 [{"role": "user/assistant", "content": "..."}]
        - images: 圖片資訊列表 [{"line_message_id": "...", "nas_path": "..."}]
        - files: 檔案資訊列表 [{"line_message_id": "...", "nas_path": "...", "file_name": "...", "file_size": ...}]
    """
    from .bot_line import get_temp_image_path

    async with get_connection() as conn:
        if line_group_id:
            # 群組對話（包含 text、image 和 file）
            rows = await conn.fetch(
                """
                SELECT m.content, m.is_from_bot, u.display_name,
                       m.message_type, m.message_id as line_message_id,
                       f.nas_path, f.file_name, f.file_size, f.file_type as actual_file_type
                FROM bot_messages m
                LEFT JOIN bot_users u ON m.bot_user_id = u.id
                LEFT JOIN bot_files f ON f.message_id = m.id
                WHERE m.bot_group_id = $1
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
                FROM bot_messages m
                LEFT JOIN bot_users u ON m.bot_user_id = u.id
                LEFT JOIN bot_files f ON f.message_id = m.id
                WHERE u.platform_user_id = $1
                  AND ($3::uuid IS NULL OR m.id != $3)
                  AND m.bot_group_id IS NULL
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
                    row["line_message_id"], row["nas_path"]
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
                        # 檔案過大無法讀取內容，但仍提供 NAS 路徑供歸檔等操作
                        size_mb = file_size / 1024 / 1024
                        content = (
                            f"[上傳檔案: {file_name}（{size_mb:.1f} MB，"
                            f"過大無法讀取內容，NAS 路徑: {row['nas_path']}）]"
                        )
                    else:
                        # 可讀取的檔案：確保暫存存在
                        temp_path = await ensure_temp_file(
                            row["line_message_id"], row["nas_path"], file_name, file_size
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

            # 記錄發送者名稱（群組和個人對話都顯示）
            sender = None
            if not row["is_from_bot"] and row["display_name"]:
                sender = row["display_name"]

            context.append({"role": role, "content": content, "sender": sender})

        return context, images, files


async def build_system_prompt(
    line_group_id: UUID | None,
    line_user_id: str | None,
    base_prompt: str,
    builtin_tools: list[str] | None = None,
    app_permissions: dict[str, bool] | None = None,
    platform_type: str = "line",
    *,
    role: str = "user",
) -> str:
    """
    建立系統提示

    Args:
        line_group_id: 群組 UUID（群組對話用）
        line_user_id: Line 用戶 ID（個人對話用）
        base_prompt: 從 Agent 取得的基礎 prompt
        builtin_tools: 內建工具列表（如 WebSearch, WebFetch）
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

    # 非同步任務通用規則 + 長時外部研究規則（避免同步多輪超時）
    if app_permissions and app_permissions.get("file-manager", False):
        tool_sections.append("""【非同步任務通用規則（嚴格遵守）】
所有 start/check 兩段式 skill（research-skill、media-transcription、media-downloader 等）：
- 啟動後回覆 job_id 給使用者，然後結束本次回應。
- 查詢一次若未完成 → 告知使用者目前進度，請稍後再問，結束回應。
- 嚴禁使用 sleep 等待任務完成，嚴禁在同一回應中反覆 sleep + check。
- 這些任務可能需要數分鐘，反覆等待必定導致整體超時。
- 呼叫 start-research、download-video、transcribe 時，必須在 input JSON 附帶 caller_context 欄位（格式見【對話識別】末端），讓任務完成後系統可主動通知發起者。

【長時外部研究（規則）】
- 需要「搜尋 + 擷取 + 統整」多個來源時，必須使用 research-skill（start/check）：
  · run_skill_script(skill="research-skill", script="start-research", input='{"query":"..."}')
  · run_skill_script(skill="research-skill", script="check-research", input='{"job_id":"..."}')
- 啟動後先回覆 job_id，稍後再查詢結果。
- check-research 若回傳 failed：同主題應重新 start-research 建立新 job_id。
- 已啟動 research-skill 的同主題，禁止改用 WebSearch/WebFetch 重做。
- WebSearch/WebFetch 僅可用於單一簡短查詢（例如天氣、即時單點資訊）。""")

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
        tools_prompt = await generate_tools_prompt(app_permissions, is_group, role=role)
        if tools_prompt:
            base_prompt += "\n\n你可以使用以下工具：\n\n" + tools_prompt
        # 加入使用說明
        usage_tips = generate_usage_tips_prompt(app_permissions, is_group)
        if usage_tips:
            base_prompt += "\n\n" + usage_tips

    # 加入對話識別資訊（供 MCP 工具使用）
    # 查詢用戶的 CTOS user_id（用於權限檢查）
    ctos_user_id = None
    line_user_uuid = None
    if line_user_id:
        user_row = await get_line_user_record(line_user_id, "id, user_id")
        if user_row:
            line_user_uuid = user_row["id"]
            if user_row["user_id"]:
                ctos_user_id = user_row["user_id"]

    # 載入並整合自訂記憶
    from .bot_line import get_active_group_memories, get_active_user_memories

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

    # 平台標籤
    platform_label = "Telegram" if platform_type == "telegram" else "Line"

    if line_group_id:
        platform_group_id: str | None = None
        async with get_connection() as conn:
            group = await conn.fetchrow(
                "SELECT name, platform_group_id FROM bot_groups WHERE id = $1",
                line_group_id,
            )
            if group:
                if group["name"]:
                    base_prompt += f"\n\n目前群組：{group['name']}"
                platform_group_id = group["platform_group_id"]
        # 加入群組 ID 和用戶身份識別
        base_prompt += f"\n\n【對話識別】\n平台：{platform_label}"
        base_prompt += f"\ngroup_id: {line_group_id}"
        if platform_group_id:
            base_prompt += f"\nplatform_group_id: {platform_group_id}"
        if line_user_id:
            base_prompt += f"\nplatform_user_id: {line_user_id}"
        if ctos_user_id:
            base_prompt += f"\nctos_user_id: {ctos_user_id}"
        else:
            base_prompt += "\nctos_user_id: （未關聯）"
        # caller_context 範本（供背景任務附帶）
        import json as _json
        _caller_ctx = {
            "platform": platform_type,
            "platform_user_id": line_user_id or "",
            "is_group": True,
            "group_id": platform_group_id or "",
        }
        base_prompt += f"\ncaller_context（呼叫背景任務時附帶此值）: {_json.dumps(_caller_ctx, ensure_ascii=False)}"
    elif line_user_id:
        # 個人對話：加入用戶 ID 和身份識別
        base_prompt += f"\n\n【對話識別】\n平台：{platform_label}"
        base_prompt += f"\n{platform_label.lower()}_user_id: {line_user_id}"
        if ctos_user_id:
            base_prompt += f"\nctos_user_id: {ctos_user_id}"
        else:
            base_prompt += "\nctos_user_id: （未關聯，無法進行專案更新操作）"
        # caller_context 範本（供背景任務附帶）
        import json as _json
        _caller_ctx = {
            "platform": platform_type,
            "platform_user_id": line_user_id,
            "is_group": False,
            "group_id": None,
        }
        base_prompt += f"\ncaller_context（呼叫背景任務時附帶此值）: {_json.dumps(_caller_ctx, ensure_ascii=False)}"

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
    """
    # === 斜線指令攔截（在 AI 處理之前） ===
    from .bot.commands import CommandContext, router as command_router

    # 查詢用戶資訊（指令和一般訊息都需要，只查一次）
    user_row = await get_line_user_record(
        line_user_id, "id, user_id, display_name"
    )
    ctos_user_id = None
    is_admin = False
    bot_user_id = None
    user_display_name = None
    if user_row:
        bot_user_id = str(user_row["id"]) if user_row["id"] else None
        user_display_name = user_row.get("display_name")
        if user_row["user_id"]:
            ctos_user_id = user_row["user_id"]
            from .user import get_user_role_and_permissions
            user_info = await get_user_role_and_permissions(ctos_user_id)
            is_admin = user_info["role"] == "admin"

    parsed = command_router.parse(content)
    if parsed is not None:
        command, args = parsed
        ctx = CommandContext(
            platform_type="line",
            platform_user_id=line_user_id,
            bot_user_id=bot_user_id,
            ctos_user_id=ctos_user_id,
            is_admin=is_admin,
            is_group=line_group_id is not None,
            group_id=str(line_group_id) if line_group_id else None,
            reply_token=reply_token,
            raw_args=args,
        )
        reply = await command_router.dispatch(command, args, ctx)
        if reply is not None:
            # reply_token 可能在長時間指令（如 /debug 3 分鐘）後過期，
            # 先嘗試 reply，失敗則 fallback 到 push
            if reply_token:
                try:
                    await reply_text(reply_token, reply)
                except Exception:
                    await push_text(line_user_id, reply)
            else:
                await push_text(line_user_id, reply)
        # 指令已處理，不進入 AI 流程
        return

    # === 一般訊息，進入 AI 處理 ===
    # 處理訊息
    await process_message_with_ai(
        message_uuid=message_uuid,
        content=content,
        line_group_id=line_group_id,
        line_user_id=line_user_id,
        reply_token=reply_token,
        user_display_name=user_display_name,
        quoted_message_id=quoted_message_id,
        bot_user_id=bot_user_id,
    )
