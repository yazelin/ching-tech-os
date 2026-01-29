"""測試 LineBot AI 回應解析功能

測試對象：linebot_ai.py 中的純函式
- parse_ai_response: AI 回應解析（FILE_MESSAGE 提取）
- parse_pdf_temp_path: PDF 路徑解析
- extract_nanobanana_error: nanobanana 錯誤提取
- extract_nanobanana_prompt: nanobanana prompt 提取
- check_nanobanana_timeout: nanobanana timeout 檢測
- get_user_friendly_nanobanana_error: 用戶友善錯誤訊息
- extract_generated_images_from_tool_calls: 圖片路徑提取

用法：
    cd backend
    uv run pytest tests/test_linebot_ai_parse.py -v
"""

import json

import pytest

from ching_tech_os.services.linebot_ai import (
    parse_ai_response,
    parse_pdf_temp_path,
    extract_nanobanana_error,
    extract_nanobanana_prompt,
    check_nanobanana_timeout,
    get_user_friendly_nanobanana_error,
    extract_generated_images_from_tool_calls,
)
from dataclasses import dataclass


@dataclass
class MockToolCall:
    """模擬 Claude tool_call 物件"""
    name: str
    input: dict
    output: str | None


# ============================================================
# parse_ai_response 測試
# ============================================================

class TestParseAiResponse:
    """測試 AI 回應解析"""

    def test_empty_response(self):
        """空回應"""
        text, files = parse_ai_response("")
        assert text == ""
        assert files == []

    def test_none_response(self):
        """None 回應"""
        text, files = parse_ai_response(None)
        assert text == ""
        assert files == []

    def test_plain_text_only(self):
        """純文字回應（無 FILE_MESSAGE）"""
        text, files = parse_ai_response("這是一段普通回覆")
        assert text == "這是一段普通回覆"
        assert files == []

    def test_single_image_file_message(self):
        """包含一個圖片 FILE_MESSAGE"""
        response = '好的，圖片已生成！\n\n[FILE_MESSAGE:{"type":"image","url":"https://example.com/img.jpg","name":"test.jpg"}]'
        text, files = parse_ai_response(response)
        assert text == "好的，圖片已生成！"
        assert len(files) == 1
        assert files[0]["type"] == "image"
        assert files[0]["url"] == "https://example.com/img.jpg"

    def test_multiple_file_messages(self):
        """包含多個 FILE_MESSAGE"""
        response = (
            '以下是兩張圖片：\n\n'
            '[FILE_MESSAGE:{"type":"image","url":"https://example.com/1.jpg","name":"1.jpg"}]\n'
            '[FILE_MESSAGE:{"type":"image","url":"https://example.com/2.jpg","name":"2.jpg"}]'
        )
        text, files = parse_ai_response(response)
        assert text == "以下是兩張圖片："
        assert len(files) == 2

    def test_file_type_message(self):
        """包含檔案類型 FILE_MESSAGE"""
        response = '請下載：\n[FILE_MESSAGE:{"type":"file","url":"https://example.com/doc.pdf","name":"report.pdf","size":"2.5MB"}]'
        text, files = parse_ai_response(response)
        assert text == "請下載："
        assert files[0]["type"] == "file"
        assert files[0]["name"] == "report.pdf"

    def test_invalid_json_in_file_message(self):
        """FILE_MESSAGE 中的 JSON 格式無效"""
        response = '回覆文字\n[FILE_MESSAGE:{invalid json}]'
        text, files = parse_ai_response(response)
        assert "回覆文字" in text
        assert files == []

    def test_cleans_extra_newlines(self):
        """清理多餘空行"""
        response = '第一行\n\n\n\n\n第二行'
        text, files = parse_ai_response(response)
        assert text == "第一行\n\n第二行"

    def test_mixed_text_and_file_messages(self):
        """文字和 FILE_MESSAGE 混合"""
        response = (
            '這裡有圖片\n\n'
            '[FILE_MESSAGE:{"type":"image","url":"https://img.com/a.jpg","name":"a.jpg"}]\n\n'
            '還有文字'
        )
        text, files = parse_ai_response(response)
        assert "這裡有圖片" in text
        assert "還有文字" in text
        assert len(files) == 1


# ============================================================
# parse_pdf_temp_path 測試
# ============================================================

class TestParsePdfTempPath:
    """測試 PDF 路徑解析"""

    def test_normal_path(self):
        """一般路徑"""
        pdf, txt = parse_pdf_temp_path("/tmp/linebot-files/abc.txt")
        assert pdf == "/tmp/linebot-files/abc.txt"
        assert txt == ""

    def test_pdf_with_txt(self):
        """PDF 特殊格式（含文字版）"""
        pdf, txt = parse_pdf_temp_path("PDF:/tmp/doc.pdf|TXT:/tmp/doc.txt")
        assert pdf == "/tmp/doc.pdf"
        assert txt == "/tmp/doc.txt"

    def test_pdf_without_txt(self):
        """PDF 特殊格式（無文字版）"""
        pdf, txt = parse_pdf_temp_path("PDF:/tmp/scan.pdf")
        assert pdf == "/tmp/scan.pdf"
        assert txt == ""


# ============================================================
# nanobanana 相關函式測試
# ============================================================

class TestExtractNanobananaError:
    """測試 nanobanana 錯誤提取"""

    def test_no_tool_calls(self):
        """無 tool_calls"""
        assert extract_nanobanana_error(None) is None
        assert extract_nanobanana_error([]) is None

    def test_no_nanobanana_call(self):
        """tool_calls 中無 nanobanana"""
        tc = MockToolCall(name="other_tool", input={}, output='{"result": "ok"}')
        assert extract_nanobanana_error([tc]) is None

    def test_successful_generation(self):
        """nanobanana 成功生成（無錯誤）"""
        output = json.dumps([{"text": json.dumps({"success": True, "generatedFiles": ["/tmp/img.jpg"]}), "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=output)
        assert extract_nanobanana_error([tc]) is None

    def test_overloaded_error(self):
        """nanobanana 回傳 overloaded 錯誤"""
        output = json.dumps([{"text": json.dumps({"success": False, "error": "model is overloaded"}), "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=output)
        assert extract_nanobanana_error([tc]) == "model is overloaded"

    def test_edit_image_error(self):
        """edit_image 也能提取錯誤"""
        output = json.dumps([{"text": json.dumps({"success": False, "error": "quota exceeded"}), "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__edit_image", input={}, output=output)
        assert extract_nanobanana_error([tc]) == "quota exceeded"


class TestExtractNanobananaPrompt:
    """測試 nanobanana prompt 提取"""

    def test_no_tool_calls(self):
        assert extract_nanobanana_prompt(None) is None
        assert extract_nanobanana_prompt([]) is None

    def test_extract_prompt(self):
        """提取 generate_image 的 prompt"""
        tc = MockToolCall(
            name="mcp__nanobanana__generate_image",
            input={"prompt": "A cute cat"},
            output=None,
        )
        assert extract_nanobanana_prompt([tc]) == "A cute cat"

    def test_edit_image_not_extracted(self):
        """edit_image 不提取 prompt（需要參考圖片）"""
        tc = MockToolCall(
            name="mcp__nanobanana__edit_image",
            input={"prompt": "edit this"},
            output=None,
        )
        assert extract_nanobanana_prompt([tc]) is None


class TestCheckNanobananaTimeout:
    """測試 nanobanana timeout 檢測"""

    def test_no_tool_calls(self):
        assert check_nanobanana_timeout(None) is False
        assert check_nanobanana_timeout([]) is False

    def test_normal_output(self):
        """正常輸出"""
        output = json.dumps([{"text": "ok", "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=output)
        assert check_nanobanana_timeout([tc]) is False

    def test_none_output(self):
        """output 為 None（timeout）"""
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=None)
        assert check_nanobanana_timeout([tc]) is True

    def test_empty_string_output(self):
        """output 為空字串"""
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output="")
        assert check_nanobanana_timeout([tc]) is True

    def test_null_string_output(self):
        """output 為 "null" 字串"""
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output="null")
        assert check_nanobanana_timeout([tc]) is True

    def test_non_nanobanana_tool(self):
        """非 nanobanana 工具不檢測"""
        tc = MockToolCall(name="other_tool", input={}, output=None)
        assert check_nanobanana_timeout([tc]) is False


class TestGetUserFriendlyNanobananaError:
    """測試用戶友善錯誤訊息"""

    def test_overloaded(self):
        msg = get_user_friendly_nanobanana_error("model is overloaded")
        assert "503" in msg
        assert "過載" in msg

    def test_api_key(self):
        msg = get_user_friendly_nanobanana_error("invalid api key")
        assert "管理員" in msg

    def test_quota(self):
        msg = get_user_friendly_nanobanana_error("quota exceeded")
        assert "429" in msg or "限制" in msg

    def test_rate_limit(self):
        msg = get_user_friendly_nanobanana_error("rate limit reached")
        assert "限制" in msg

    def test_unknown_error(self):
        msg = get_user_friendly_nanobanana_error("some unknown error")
        assert "some unknown error" in msg


class TestExtractGeneratedImages:
    """測試圖片路徑提取"""

    def test_no_tool_calls(self):
        assert extract_generated_images_from_tool_calls(None) == []
        assert extract_generated_images_from_tool_calls([]) == []

    def test_successful_generation(self):
        """成功生成的圖片"""
        inner = json.dumps({"success": True, "generatedFiles": ["/tmp/nanobanana-output/img.jpg"]})
        output = json.dumps([{"text": inner, "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=output)
        result = extract_generated_images_from_tool_calls([tc])
        assert result == ["/tmp/nanobanana-output/img.jpg"]

    def test_multiple_images(self):
        """多張圖片"""
        files = ["/tmp/nanobanana-output/1.jpg", "/tmp/nanobanana-output/2.jpg"]
        inner = json.dumps({"success": True, "generatedFiles": files})
        output = json.dumps([{"text": inner, "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=output)
        result = extract_generated_images_from_tool_calls([tc])
        assert len(result) == 2

    def test_failed_generation(self):
        """生成失敗"""
        inner = json.dumps({"success": False, "error": "failed"})
        output = json.dumps([{"text": inner, "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__generate_image", input={}, output=output)
        result = extract_generated_images_from_tool_calls([tc])
        assert result == []

    def test_edit_image_also_extracted(self):
        """edit_image 也能提取圖片"""
        inner = json.dumps({"success": True, "generatedFiles": ["/tmp/edited.jpg"]})
        output = json.dumps([{"text": inner, "type": "text"}])
        tc = MockToolCall(name="mcp__nanobanana__edit_image", input={}, output=output)
        result = extract_generated_images_from_tool_calls([tc])
        assert result == ["/tmp/edited.jpg"]
