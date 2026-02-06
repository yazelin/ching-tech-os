"""測試 LineBot 工具函式

測試對象：linebot.py 中的純函式（不需要資料庫）
- is_reset_command: 重置對話指令檢查
- is_binding_code_format: 驗證碼格式檢查
- is_readable_file: 可讀取檔案判斷
- is_legacy_office_file: 舊版 Office 格式判斷
- is_document_file: 文件格式判斷
- get_temp_image_path: 圖片暫存路徑
- should_trigger_ai: AI 觸發判斷
- generate_nas_path: NAS 路徑生成

用法：
    cd backend
    uv run pytest tests/test_linebot_utils.py -v
"""

import pytest

from ching_tech_os.services.linebot import (
    is_reset_command,
    is_readable_file,
    is_legacy_office_file,
    is_document_file,
    get_temp_image_path,
    should_trigger_ai,
    generate_nas_path,
)


# ============================================================
# is_reset_command 測試
# ============================================================

class TestIsResetCommand:
    """測試重置對話指令檢查"""

    def test_reset_commands(self):
        """所有重置指令"""
        assert is_reset_command("/新對話") is True
        assert is_reset_command("/新对话") is True
        assert is_reset_command("/reset") is True
        assert is_reset_command("/清除對話") is True
        assert is_reset_command("/清除对话") is True
        assert is_reset_command("/忘記") is True
        assert is_reset_command("/忘记") is True

    def test_case_insensitive(self):
        """大小寫不敏感"""
        assert is_reset_command("/RESET") is True
        assert is_reset_command("/Reset") is True

    def test_with_whitespace(self):
        """前後空白"""
        assert is_reset_command("  /reset  ") is True

    def test_non_reset_commands(self):
        """非重置指令"""
        assert is_reset_command("hello") is False
        assert is_reset_command("/help") is False
        assert is_reset_command("reset") is False  # 缺少斜線


# ============================================================
# is_readable_file 測試
# ============================================================

class TestIsReadableFile:
    """測試可讀取檔案判斷"""

    def test_text_files(self):
        """純文字格式"""
        assert is_readable_file("readme.txt") is True
        assert is_readable_file("doc.md") is True
        assert is_readable_file("data.json") is True
        assert is_readable_file("data.csv") is True
        assert is_readable_file("app.log") is True
        assert is_readable_file("config.xml") is True
        assert is_readable_file("config.yaml") is True
        assert is_readable_file("config.yml") is True

    def test_office_files(self):
        """Office 文件"""
        assert is_readable_file("report.docx") is True
        assert is_readable_file("data.xlsx") is True
        assert is_readable_file("slides.pptx") is True

    def test_pdf(self):
        """PDF 文件"""
        assert is_readable_file("document.pdf") is True

    def test_non_readable_files(self):
        """不可讀取的格式"""
        assert is_readable_file("image.jpg") is False
        assert is_readable_file("video.mp4") is False
        assert is_readable_file("app.exe") is False
        assert is_readable_file("archive.zip") is False

    def test_case_insensitive(self):
        """大小寫不敏感"""
        assert is_readable_file("README.TXT") is True
        assert is_readable_file("Data.JSON") is True

    def test_empty_filename(self):
        """空檔名"""
        assert is_readable_file("") is False
        assert is_readable_file(None) is False

    def test_no_extension(self):
        """無副檔名"""
        assert is_readable_file("Makefile") is False


class TestIsLegacyOfficeFile:
    """測試舊版 Office 格式判斷"""

    def test_legacy_formats(self):
        assert is_legacy_office_file("report.doc") is True
        assert is_legacy_office_file("data.xls") is True
        assert is_legacy_office_file("slides.ppt") is True

    def test_new_formats_not_legacy(self):
        assert is_legacy_office_file("report.docx") is False
        assert is_legacy_office_file("data.xlsx") is False

    def test_empty(self):
        assert is_legacy_office_file("") is False


class TestIsDocumentFile:
    """測試文件格式判斷"""

    def test_document_formats(self):
        assert is_document_file("report.docx") is True
        assert is_document_file("data.xlsx") is True
        assert is_document_file("slides.pptx") is True
        assert is_document_file("doc.pdf") is True

    def test_non_document(self):
        assert is_document_file("readme.txt") is False
        assert is_document_file("image.jpg") is False


# ============================================================
# get_temp_image_path 測試
# ============================================================

class TestGetTempImagePath:
    """測試圖片暫存路徑"""

    def test_normal_path(self):
        path = get_temp_image_path("msg123")
        assert path == "/tmp/bot-images/msg123.jpg"


# ============================================================
# should_trigger_ai 測試
# ============================================================

class TestShouldTriggerAi:
    """測試 AI 觸發判斷"""

    def test_personal_always_triggers(self):
        """個人對話全部觸發"""
        assert should_trigger_ai("hello", is_group=False) is True
        assert should_trigger_ai("", is_group=False) is True

    def test_group_reply_to_bot(self):
        """群組回覆機器人觸發"""
        assert should_trigger_ai("hello", is_group=True, is_reply_to_bot=True) is True

    def test_group_without_mention(self):
        """群組無 @ 不觸發"""
        assert should_trigger_ai("hello everyone", is_group=True) is False


# ============================================================
# generate_nas_path 測試
# ============================================================

class TestGenerateNasPath:
    """測試 NAS 路徑生成"""

    def test_group_image_path(self):
        """群組圖片路徑"""
        path = generate_nas_path(
            line_group_id="Cgroup123",
            message_id="msg456",
            file_type="image",
        )
        assert "Cgroup123" in path
        assert "msg456" in path
        assert "images" in path

    def test_group_file_path(self):
        """群組檔案路徑"""
        path = generate_nas_path(
            line_group_id="Cgroup123",
            message_id="msg456",
            file_type="file",
            file_name="report.pdf",
        )
        assert "Cgroup123" in path
        assert "report.pdf" in path
        assert "files" in path

    def test_user_path(self):
        """個人對話路徑"""
        path = generate_nas_path(
            line_user_id="Uuser123",
            message_id="msg789",
            file_type="image",
        )
        assert "Uuser123" in path
