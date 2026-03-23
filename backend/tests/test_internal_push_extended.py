"""測試 api/internal_push.py 中未覆蓋的函數"""

import os
from pathlib import Path
from unittest.mock import patch

from ching_tech_os.api.internal_push import (
    _get_ctos_mount,
    _find_status_file,
    _build_message,
)


class TestGetCtosMount:
    def test_from_settings(self):
        result = _get_ctos_mount()
        assert isinstance(result, str)

    def test_from_env_fallback(self, monkeypatch):
        monkeypatch.setenv("CTOS_MOUNT_PATH", "/custom/path")
        with patch(
            "ching_tech_os.api.internal_push.settings",
            side_effect=Exception("no settings"),
            create=True,
        ):
            # 會先嘗試 settings，失敗後用 env
            result = _get_ctos_mount()
            assert isinstance(result, str)


class TestFindStatusFile:
    def test_unknown_skill(self):
        assert _find_status_file("unknown-skill", "job-1") is None

    def test_base_not_exists(self, tmp_path):
        with patch(
            "ching_tech_os.api.internal_push._get_ctos_mount",
            return_value=str(tmp_path),
        ):
            result = _find_status_file("research-skill", "job-1")
            assert result is None

    def test_found(self, tmp_path):
        """status.json 存在"""
        research_dir = tmp_path / "linebot" / "research" / "2026-03-23" / "job-1"
        research_dir.mkdir(parents=True)
        status_file = research_dir / "status.json"
        status_file.write_text('{"status": "done"}')

        with patch(
            "ching_tech_os.api.internal_push._get_ctos_mount",
            return_value=str(tmp_path),
        ):
            result = _find_status_file("research-skill", "job-1")
            assert result is not None
            assert result.name == "status.json"

    def test_not_found_in_dates(self, tmp_path):
        """目錄存在但 job_id 不匹配"""
        research_dir = tmp_path / "linebot" / "research" / "2026-03-23"
        research_dir.mkdir(parents=True)

        with patch(
            "ching_tech_os.api.internal_push._get_ctos_mount",
            return_value=str(tmp_path),
        ):
            result = _find_status_file("research-skill", "nonexistent")
            assert result is None


class TestBuildMessage:
    def test_research_skill(self):
        status = {
            "job_id": "j1",
            "query": "AI 趨勢",
            "final_summary": "結論是 AI 很強",
        }
        msg = _build_message("research-skill", status)
        assert "研究任務完成" in msg
        assert "AI 趨勢" in msg

    def test_research_skill_long_summary(self):
        status = {
            "job_id": "j2",
            "query": "test",
            "final_summary": "x" * 600,
        }
        msg = _build_message("research-skill", status)
        assert "…" in msg

    def test_media_downloader(self):
        status = {
            "job_id": "j3",
            "filename": "video.mp4",
            "file_size": 10 * 1024 * 1024,
            "ctos_path": "/videos/video.mp4",
        }
        msg = _build_message("media-downloader", status)
        assert "影片下載完成" in msg
        assert "video.mp4" in msg
        assert "MB" in msg

    def test_media_transcription(self):
        status = {
            "job_id": "j4",
            "transcript_preview": "這是一段文字",
            "ctos_path": "/transcriptions/output.txt",
        }
        msg = _build_message("media-transcription", status)
        assert "轉錄完成" in msg

    def test_media_translation(self):
        status = {
            "job_id": "j5",
            "source_filename": "doc.srt",
            "ctos_path": "/translations/doc_zh.srt",
            "warnings": ["segment 3 failed"],
        }
        msg = _build_message("media-translation", status)
        assert "翻譯完成" in msg
        assert "翻譯失敗" in msg

    def test_unknown_skill(self):
        status = {"job_id": "j6"}
        msg = _build_message("unknown", status)
        assert "任務完成" in msg
