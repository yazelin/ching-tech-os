"""語音設定 API

提供語音設定 CRUD、語音角色列表、試聽功能。
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from ..database import get_connection
from .auth import get_current_session
from ..services.session import SessionData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# 試聽 rate limiting：使用者 -> 最後一次試聽時間
_preview_timestamps: dict[int, float] = {}
PREVIEW_COOLDOWN_SECONDS = 10


async def _get_user_id(session: SessionData = Depends(get_current_session)) -> int:
    if session.user_id is None:
        raise HTTPException(status_code=401, detail="未登入")
    return session.user_id


# ── 語音角色列表 + config schema ──────────────────────


@router.get("/voices")
async def get_voices(engine: str = Query("", description="引擎名稱（空=目前預設引擎）")):
    """取得可用語音角色列表、設定 schema、可用引擎"""
    from ..services.bot.voice_bridge import get_voice_tts
    voice_tts = get_voice_tts()
    if voice_tts is None:
        raise HTTPException(status_code=503, detail="語音功能未安裝")

    import voice_tts as vtts  # type: ignore[import-not-found]

    target_engine = vtts.get_engine_by_name(engine) if engine else vtts.get_engine()

    try:
        voices = await target_engine.list_voices()
    except NotImplementedError:
        voices = []

    engine_name = engine or __import__("os").environ.get("TTS_ENGINE", "edge")

    return {
        "engine": engine_name,
        "voices": [
            {"id": v.id, "name": v.name, "gender": v.gender, "language": v.language}
            for v in voices
        ],
        "config_schema": target_engine.get_config_schema(),
        "available_engines": vtts.get_available_engines(),
    }


# ── 可用範圍列表 ─────────────────────────────────────


@router.get("/scopes")
async def get_voice_scopes(user_id: int = Depends(_get_user_id)):
    """取得可用的語音設定範圍（群組列表、Agent 列表）"""
    groups = []
    agents = []
    is_admin = False

    async with get_connection() as conn:
        # 查詢使用者角色
        role = await conn.fetchval("SELECT role FROM users WHERE id = $1", user_id)
        is_admin = role == "admin"

        # 查詢使用者綁定的 bot_user_id
        bot_user_row = await conn.fetchrow(
            "SELECT id FROM bot_users WHERE user_id = $1", user_id,
        )

        if bot_user_row:
            bot_user_id = str(bot_user_row["id"])
            # 查詢使用者有互動過的群組（透過 bot_messages）
            rows = await conn.fetch(
                """
                SELECT DISTINCT bg.id, bg.name, bg.platform_type
                FROM bot_groups bg
                JOIN bot_messages bm ON bm.bot_group_id = bg.id
                WHERE bm.bot_user_id = $1::uuid
                  AND bg.is_active = true
                ORDER BY bg.name
                """,
                bot_user_id,
            )
            for r in rows:
                groups.append({
                    "id": str(r["id"]),
                    "name": r["name"] or f"群組 {str(r['id'])[:8]}",
                    "platform": r["platform_type"] or "line",
                })

        # 管理員可以設定 Agent 語音
        if is_admin:
            rows = await conn.fetch(
                "SELECT id, name, display_name FROM ai_agents WHERE is_active = true ORDER BY name",
            )
            for r in rows:
                agents.append({
                    "id": str(r["id"]),
                    "name": r["display_name"] or r["name"],
                })

    return {
        "is_admin": is_admin,
        "groups": groups,
        "agents": agents,
    }


# ── 語音設定 CRUD ────────────────────────────────────


class VoiceSettingsBody(BaseModel):
    scope: str = "user"  # user | group | agent
    scope_id: str | None = None
    tts_engine: str = "edge"
    tts_params: dict = {}


@router.get("/settings")
async def get_voice_settings(
    scope: str = Query("user", description="user|group|agent"),
    scope_id: str = Query("", description="群組/Agent ID"),
    user_id: int = Depends(_get_user_id),
):
    """取得語音設定（指定層級 + 實際生效的繼承設定）"""
    settings_value = None

    async with get_connection() as conn:
        if scope == "user":
            settings_value = await conn.fetchval(
                "SELECT voice_settings FROM users WHERE id = $1", user_id,
            )
        elif scope == "group" and scope_id:
            settings_value = await conn.fetchval(
                "SELECT voice_settings FROM bot_groups WHERE id = $1::uuid", scope_id,
            )
        elif scope == "agent" and scope_id:
            settings_value = await conn.fetchval(
                "SELECT voice_settings FROM ai_agents WHERE id = $1::uuid", scope_id,
            )

    current = None
    if settings_value:
        try:
            current = json.loads(settings_value) if isinstance(settings_value, str) else settings_value
        except (json.JSONDecodeError, TypeError):
            pass

    # 計算實際生效的設定（如果當前層級未設定，顯示繼承來源）
    from ..services.mcp.voice_tools import resolve_voice_settings
    effective = await resolve_voice_settings(
        ctos_user_id=user_id if scope == "user" else None,
        group_id=scope_id if scope == "group" else None,
        agent_id=scope_id if scope == "agent" else None,
    )

    return {
        "scope": scope,
        "current": current,
        "effective": effective,
    }


@router.put("/settings")
async def save_voice_settings(
    body: VoiceSettingsBody,
    user_id: int = Depends(_get_user_id),
):
    """儲存語音設定"""
    settings_json = json.dumps({
        "tts_engine": body.tts_engine,
        "tts_params": body.tts_params,
    })

    async with get_connection() as conn:
        if body.scope == "user":
            await conn.execute(
                "UPDATE users SET voice_settings = $1::json WHERE id = $2",
                settings_json, user_id,
            )
        elif body.scope == "group" and body.scope_id:
            await conn.execute(
                "UPDATE bot_groups SET voice_settings = $1::json WHERE id = $2::uuid",
                settings_json, body.scope_id,
            )
        elif body.scope == "agent" and body.scope_id:
            # Agent 設定需要管理員權限
            role = await conn.fetchval(
                "SELECT role FROM users WHERE id = $1", user_id,
            )
            if role != "admin":
                raise HTTPException(status_code=403, detail="只有管理員可修改 Agent 語音設定")
            await conn.execute(
                "UPDATE ai_agents SET voice_settings = $1::json WHERE id = $2::uuid",
                settings_json, body.scope_id,
            )
        else:
            raise HTTPException(status_code=400, detail="無效的 scope")

    return {"ok": True}


class DeleteSettingsBody(BaseModel):
    scope: str = "user"
    scope_id: str | None = None


@router.delete("/settings")
async def delete_voice_settings(
    body: DeleteSettingsBody,
    user_id: int = Depends(_get_user_id),
):
    """清除語音設定（回退到繼承）"""
    async with get_connection() as conn:
        if body.scope == "user":
            await conn.execute(
                "UPDATE users SET voice_settings = NULL WHERE id = $1", user_id,
            )
        elif body.scope == "group" and body.scope_id:
            await conn.execute(
                "UPDATE bot_groups SET voice_settings = NULL WHERE id = $1::uuid",
                body.scope_id,
            )
        elif body.scope == "agent" and body.scope_id:
            role = await conn.fetchval(
                "SELECT role FROM users WHERE id = $1", user_id,
            )
            if role != "admin":
                raise HTTPException(status_code=403, detail="只有管理員可修改 Agent 語音設定")
            await conn.execute(
                "UPDATE ai_agents SET voice_settings = NULL WHERE id = $1::uuid",
                body.scope_id,
            )

    return {"ok": True}


# ── 試聽 ─────────────────────────────────────────────


class PreviewBody(BaseModel):
    engine: str = ""
    params: dict = {}
    text: str = ""


@router.post("/preview")
async def preview_voice(
    body: PreviewBody,
    user_id: int = Depends(_get_user_id),
):
    """生成語音試聽（直接 stream MP3，不存 NAS）"""
    # Rate limiting
    now = time.time()
    last = _preview_timestamps.get(user_id, 0)
    if now - last < PREVIEW_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="試聽冷卻中，請稍後再試")
    _preview_timestamps[user_id] = now

    from ..services.bot.voice_bridge import get_voice_tts
    voice_tts = get_voice_tts()
    if voice_tts is None:
        raise HTTPException(status_code=503, detail="語音功能未安裝")

    import voice_tts as vtts  # type: ignore[import-not-found]

    text = body.text or "你好，這是語音預覽測試"
    try:
        audio_bytes = await vtts.synthesize_preview(
            text=text,
            engine_name=body.engine,
            **body.params,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

    if audio_bytes is None:
        raise HTTPException(status_code=500, detail="語音生成失敗")

    return Response(
        content=audio_bytes,
        media_type="audio/mp4",
        headers={"Cache-Control": "no-cache"},
    )
