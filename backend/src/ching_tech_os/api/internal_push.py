"""內部主動推送端點

供背景任務子行程完成時呼叫，觸發推送通知給發起者。
僅限本機存取（127.0.0.1）。
"""

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.proactive_push_service import notify_job_complete

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["Internal"])


def _get_ctos_mount() -> str:
    """取得 CTOS 掛載路徑"""
    try:
        from ..config import settings
        return settings.ctos_mount_path
    except Exception:
        return os.environ.get("CTOS_MOUNT_PATH", "/mnt/nas/ctos")


def _find_status_file(skill: str, job_id: str) -> Path | None:
    """依 skill 名稱和 job_id 搜尋 status.json（掃描最近 7 天）"""
    ctos = _get_ctos_mount()
    skill_subdir = {
        "research-skill": "research",
        "media-downloader": "videos",
        "media-transcription": "transcriptions",
    }.get(skill)

    if not skill_subdir:
        return None

    base = Path(ctos) / "linebot" / skill_subdir
    if not base.exists():
        return None

    for date_dir in sorted(base.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        status_path = date_dir / job_id / "status.json"
        if status_path.exists():
            return status_path

    return None


def _build_message(skill: str, status: dict) -> str:
    """依 skill 組裝推送訊息"""
    job_id = status.get("job_id", "")

    if skill == "research-skill":
        query = status.get("query", "")
        summary = status.get("summary") or status.get("result", "")
        if isinstance(summary, str) and len(summary) > 500:
            summary = summary[:500] + "…"
        lines = ["✅ 研究任務完成"]
        if query:
            lines.append(f"查詢：{query}")
        if summary:
            lines.append(f"\n{summary}")
        lines.append(f"\n（job_id: {job_id}）")
        return "\n".join(lines)

    if skill == "media-downloader":
        filename = status.get("filename", "")
        file_size = status.get("file_size", 0)
        ctos_path = status.get("ctos_path", "")
        size_mb = f"{file_size / 1024 / 1024:.1f} MB" if file_size else ""
        lines = ["✅ 影片下載完成"]
        if filename:
            lines.append(f"檔案：{filename}" + (f"（{size_mb}）" if size_mb else ""))
        if ctos_path:
            lines.append(f"路徑：{ctos_path}")
        lines.append(f"（job_id: {job_id}）")
        return "\n".join(lines)

    if skill == "media-transcription":
        transcript = status.get("transcript_preview") or status.get("transcript", "")
        ctos_path = status.get("ctos_path", "")
        preview = transcript[:300] + "…" if transcript and len(transcript) > 300 else transcript
        lines = ["✅ 轉錄完成"]
        if preview:
            lines.append(f"\n{preview}")
        if ctos_path:
            lines.append(f"\n完整逐字稿：{ctos_path}")
        lines.append(f"（job_id: {job_id}）")
        return "\n".join(lines)

    return f"✅ 任務完成（job_id: {job_id}）"


class ProactivePushRequest(BaseModel):
    job_id: str
    skill: str


@router.post("/proactive-push")
async def trigger_proactive_push(body: ProactivePushRequest, request: Request):
    """背景任務完成後觸發主動推送（僅限本機存取）"""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="僅限本機存取")

    status_path = _find_status_file(body.skill, body.job_id)
    if not status_path:
        logger.warning(f"找不到 status.json: skill={body.skill} job_id={body.job_id}")
        return {"ok": False, "reason": "status not found"}

    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(f"讀取 status.json 失敗: {status_path}", exc_info=True)
        return {"ok": False, "reason": "status read error"}

    caller_context = status.get("caller_context")
    if not caller_context:
        logger.debug(f"無 caller_context，跳過推送: job_id={body.job_id}")
        return {"ok": False, "reason": "no caller_context"}

    platform = caller_context.get("platform", "")
    platform_user_id = caller_context.get("platform_user_id", "")
    is_group = bool(caller_context.get("is_group", False))
    group_id = caller_context.get("group_id")

    # 群組對話只需 group_id，個人對話需要 platform_user_id
    has_target = (is_group and group_id) or platform_user_id
    if not platform or not has_target:
        logger.warning(f"caller_context 缺少必要欄位: {caller_context}")
        return {"ok": False, "reason": "invalid caller_context"}

    message = _build_message(body.skill, status)

    await notify_job_complete(
        platform=platform,
        platform_user_id=platform_user_id,
        is_group=is_group,
        group_id=group_id,
        message=message,
    )

    return {"ok": True}
