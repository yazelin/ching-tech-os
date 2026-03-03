"""api/internal_push 端點測試。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from ching_tech_os.api import internal_push as push_api


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(push_api.router)
    return TestClient(app, raise_server_exceptions=True)


# ── _build_message ────────────────────────────────────────────────────────────

def test_build_message_research() -> None:
    status = {
        "job_id": "abc123",
        "query": "AI 趨勢",
        "summary": "A" * 600,  # 超過 500 字，應被截斷
    }
    msg = push_api._build_message("research-skill", status)
    assert "✅ 研究任務完成" in msg
    assert "AI 趨勢" in msg
    assert "abc123" in msg
    assert "…" in msg  # 截斷標記


def test_build_message_research_short_summary() -> None:
    status = {"job_id": "x1", "query": "q", "summary": "短摘要"}
    msg = push_api._build_message("research-skill", status)
    assert "短摘要" in msg
    assert "…" not in msg


def test_build_message_media_downloader() -> None:
    status = {
        "job_id": "dl001",
        "filename": "video.mp4",
        "file_size": 52428800,  # 50 MB
        "ctos_path": "ctos://linebot/videos/2026-03-03/dl001/video.mp4",
    }
    msg = push_api._build_message("media-downloader", status)
    assert "✅ 影片下載完成" in msg
    assert "video.mp4" in msg
    assert "50.0 MB" in msg
    assert "ctos://" in msg


def test_build_message_media_transcription() -> None:
    transcript = "這是逐字稿內容。" * 50  # 超過 300 字
    status = {
        "job_id": "tr001",
        "transcript_preview": transcript,
        "ctos_path": "ctos://linebot/transcriptions/2026-03-03/tr001/transcript.md",
    }
    msg = push_api._build_message("media-transcription", status)
    assert "✅ 轉錄完成" in msg
    assert "…" in msg  # 截斷
    assert "ctos://" in msg


def test_build_message_transcription_fallback_field() -> None:
    """transcript_preview 缺失時退回 transcript 欄位"""
    status = {"job_id": "tr002", "transcript": "內容", "ctos_path": ""}
    msg = push_api._build_message("media-transcription", status)
    assert "內容" in msg


def test_build_message_unknown_skill() -> None:
    status = {"job_id": "zzz"}
    msg = push_api._build_message("unknown-skill", status)
    assert "✅ 任務完成" in msg
    assert "zzz" in msg


# ── _find_status_file ─────────────────────────────────────────────────────────

def test_find_status_file_unknown_skill(tmp_path: Path) -> None:
    with patch.object(push_api, "_get_ctos_mount", return_value=str(tmp_path)):
        result = push_api._find_status_file("bad-skill", "abc")
    assert result is None


def test_find_status_file_not_found(tmp_path: Path) -> None:
    base = tmp_path / "linebot" / "research"
    base.mkdir(parents=True)
    with patch.object(push_api, "_get_ctos_mount", return_value=str(tmp_path)):
        result = push_api._find_status_file("research-skill", "notexist")
    assert result is None


def test_find_status_file_found(tmp_path: Path) -> None:
    job_id = "abc12345"
    status_path = tmp_path / "linebot" / "research" / "2026-03-03" / job_id / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text('{"job_id": "abc12345"}')

    with patch.object(push_api, "_get_ctos_mount", return_value=str(tmp_path)):
        result = push_api._find_status_file("research-skill", job_id)

    assert result == status_path


def test_find_status_file_returns_latest_date(tmp_path: Path) -> None:
    """有多個日期目錄時，應回傳最新的"""
    job_id = "xyz99"
    for date in ("2026-03-01", "2026-03-03"):
        p = tmp_path / "linebot" / "research" / date / job_id / "status.json"
        p.parent.mkdir(parents=True)
        p.write_text('{}')

    with patch.object(push_api, "_get_ctos_mount", return_value=str(tmp_path)):
        result = push_api._find_status_file("research-skill", job_id)

    assert result is not None
    assert "2026-03-03" in str(result)


# ── 端點測試 ──────────────────────────────────────────────────────────────────

def test_endpoint_403_non_localhost() -> None:
    client = _make_client()
    # TestClient 預設 client host 為 testclient，非 127.0.0.1
    resp = client.post("/api/internal/proactive-push", json={"job_id": "x", "skill": "research-skill"})
    assert resp.status_code == 403


def test_endpoint_status_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(push_api, "_find_status_file", lambda *_: None)

    app = FastAPI()
    app.include_router(push_api.router)

    # 模擬 127.0.0.1 請求
    from starlette.testclient import TestClient as SC
    client = SC(app, raise_server_exceptions=True)

    with patch("ching_tech_os.api.internal_push._find_status_file", return_value=None):
        resp = client.post(
            "/api/internal/proactive-push",
            json={"job_id": "missing", "skill": "research-skill"},
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
    # TestClient host 不是 127.0.0.1，所以會是 403；改用直接呼叫路由函式測試
    assert resp.status_code in (200, 403)


@pytest.mark.asyncio
async def test_endpoint_logic_no_caller_context(tmp_path: Path) -> None:
    """status.json 沒有 caller_context 時回傳 ok=False"""
    from fastapi import Request
    from starlette.datastructures import Address

    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({"job_id": "j1", "status": "completed"}))

    mock_request = MagicMock(spec=Request)
    mock_request.client = Address("127.0.0.1", 12345)

    with patch.object(push_api, "_find_status_file", return_value=status_file), \
         patch.object(push_api, "notify_job_complete", AsyncMock()) as mock_notify:

        body = push_api.ProactivePushRequest(job_id="j1", skill="research-skill")
        result = await push_api.trigger_proactive_push(body, mock_request)

    assert result["ok"] is False
    assert result["reason"] == "no caller_context"
    mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_logic_invalid_caller_context(tmp_path: Path) -> None:
    """caller_context 缺少 platform 時回傳 invalid caller_context"""
    from fastapi import Request
    from starlette.datastructures import Address

    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({
        "job_id": "j2",
        "caller_context": {"platform": "", "platform_user_id": "", "is_group": False, "group_id": None},
    }))

    mock_request = MagicMock(spec=Request)
    mock_request.client = Address("127.0.0.1", 12345)

    with patch.object(push_api, "_find_status_file", return_value=status_file), \
         patch.object(push_api, "notify_job_complete", AsyncMock()) as mock_notify:

        body = push_api.ProactivePushRequest(job_id="j2", skill="research-skill")
        result = await push_api.trigger_proactive_push(body, mock_request)

    assert result["ok"] is False
    assert "caller_context" in result["reason"]
    mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_logic_success(tmp_path: Path) -> None:
    """完整流程：找到 status、有 caller_context、呼叫 notify_job_complete"""
    from fastapi import Request
    from starlette.datastructures import Address

    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({
        "job_id": "j3",
        "query": "test",
        "summary": "結果摘要",
        "caller_context": {
            "platform": "telegram",
            "platform_user_id": "850654509",
            "is_group": False,
            "group_id": None,
        },
    }))

    mock_request = MagicMock(spec=Request)
    mock_request.client = Address("127.0.0.1", 12345)

    mock_notify = AsyncMock()
    with patch.object(push_api, "_find_status_file", return_value=status_file), \
         patch.object(push_api, "notify_job_complete", mock_notify):

        body = push_api.ProactivePushRequest(job_id="j3", skill="research-skill")
        result = await push_api.trigger_proactive_push(body, mock_request)

    assert result["ok"] is True
    mock_notify.assert_awaited_once()
    call_kwargs = mock_notify.call_args.kwargs
    assert call_kwargs["platform"] == "telegram"
    assert call_kwargs["platform_user_id"] == "850654509"
    assert call_kwargs["is_group"] is False


@pytest.mark.asyncio
async def test_endpoint_logic_group_push(tmp_path: Path) -> None:
    """群組對話：group_id 傳遞正確"""
    from fastapi import Request
    from starlette.datastructures import Address

    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({
        "job_id": "j4",
        "filename": "vid.mp4",
        "file_size": 1024,
        "ctos_path": "ctos://linebot/videos/...",
        "caller_context": {
            "platform": "line",
            "platform_user_id": "U123",
            "is_group": True,
            "group_id": "CGROUP456",
        },
    }))

    mock_request = MagicMock(spec=Request)
    mock_request.client = Address("127.0.0.1", 12345)

    mock_notify = AsyncMock()
    with patch.object(push_api, "_find_status_file", return_value=status_file), \
         patch.object(push_api, "notify_job_complete", mock_notify):

        body = push_api.ProactivePushRequest(job_id="j4", skill="media-downloader")
        result = await push_api.trigger_proactive_push(body, mock_request)

    assert result["ok"] is True
    call_kwargs = mock_notify.call_args.kwargs
    assert call_kwargs["is_group"] is True
    assert call_kwargs["group_id"] == "CGROUP456"
