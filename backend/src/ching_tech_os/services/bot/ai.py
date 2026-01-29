"""平台無關的 AI 處理核心

從 linebot_ai.py 抽離的平台無關邏輯。
各平台的 handler 呼叫這裡的函式來處理 AI 相關操作。
"""

import json
import logging
import re

logger = logging.getLogger("bot.ai")


# ============================================================
# AI 回應解析
# ============================================================


def parse_ai_response(response: str) -> tuple[str, list[dict]]:
    """解析 AI 回應，提取文字和檔案訊息

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


# ============================================================
# nanobanana 工具呼叫分析（平台無關）
# ============================================================


def extract_nanobanana_error(tool_calls: list) -> str | None:
    """從 tool_calls 中提取 nanobanana 的錯誤訊息

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
    """從 tool_calls 中提取 nanobanana 的 prompt（用於 fallback）

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
            if hasattr(tc, "input") and isinstance(tc.input, dict):
                return tc.input.get("prompt")
        except (AttributeError, TypeError):
            pass

    return None


def check_nanobanana_timeout(tool_calls: list) -> bool:
    """檢測是否有 nanobanana 工具被呼叫但 output 為空（timeout）

    Returns:
        True 如果有 nanobanana 呼叫但 output 為空
    """
    if not tool_calls:
        return False

    for tc in tool_calls:
        if tc.name != "mcp__nanobanana__generate_image":
            continue

        output = tc.output
        if output is None or output == "" or output == "null":
            return True

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
    """將 nanobanana 錯誤轉換為用戶友善的訊息"""
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
    """從 tool_calls 中提取 nanobanana 生成的圖片路徑

    Returns:
        生成的圖片檔案路徑列表
    """
    generated_files = []

    if not tool_calls:
        return generated_files

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
                    if inner_data.get("success") and inner_data.get("generatedFiles"):
                        generated_files.extend(inner_data["generatedFiles"])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"解析 generate_image 輸出失敗: {e}")

    return generated_files
