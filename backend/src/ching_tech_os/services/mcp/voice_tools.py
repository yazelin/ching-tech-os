"""語音相關 MCP 工具

提供 text_to_speech 工具，讓 AI 可主動生成語音回覆。
"""

from __future__ import annotations

import json
import os

import sys
from pathlib import Path

from .server import mcp, logger, ensure_db_connection
from ...database import get_connection


def _get_voice_tts_module():
    """取得 voice_tts 模組（處理 MCP server 獨立進程的路徑問題）"""
    try:
        import voice_tts  # type: ignore[import-not-found]
        return voice_tts
    except ImportError:
        pass

    # MCP server 進程中 extends/voice 可能不在 sys.path，嘗試加入
    try:
        from ...config import settings
        voice_dir = Path(settings.extends_dir) / "voice"
        if voice_dir.is_dir():
            voice_dir_str = str(voice_dir)
            if voice_dir_str not in sys.path:
                sys.path.insert(0, voice_dir_str)
            import voice_tts  # type: ignore[import-not-found]
            return voice_tts
    except Exception:
        pass

    return None


async def resolve_voice_settings(
    ctos_user_id: int | None = None,
    group_id: str | None = None,
    agent_id: str | None = None,
) -> dict:
    """階層式解析語音設定

    優先級：
      私訊：使用者設定 > Agent 設定 > 系統預設
      群組：群組設定 > Agent 設定 > 系統預設

    Returns:
        {"tts_engine": "edge", "tts_params": {"voice": "zh-TW-HsiaoChenNeural"}}
    """
    await ensure_db_connection()

    # 系統預設
    default_engine = os.environ.get("TTS_ENGINE", "edge")
    default_voice = os.environ.get("TTS_VOICE", "zh-TW-HsiaoChenNeural")
    system_default = {
        "tts_engine": default_engine,
        "tts_params": {"voice": default_voice},
    }

    is_group = group_id is not None

    async with get_connection() as conn:
        if is_group:
            # 群組場景：群組設定 > Agent 設定 > 系統預設
            if group_id:
                row = await conn.fetchval(
                    "SELECT voice_settings FROM bot_groups WHERE id = $1::uuid",
                    group_id,
                )
                if row:
                    try:
                        settings = json.loads(row) if isinstance(row, str) else row
                        if settings.get("tts_engine"):
                            return settings
                    except (json.JSONDecodeError, TypeError):
                        pass
        else:
            # 私訊場景：使用者設定 > Agent 設定 > 系統預設
            if ctos_user_id:
                row = await conn.fetchval(
                    "SELECT voice_settings FROM users WHERE id = $1",
                    ctos_user_id,
                )
                if row:
                    try:
                        settings = json.loads(row) if isinstance(row, str) else row
                        if settings.get("tts_engine"):
                            return settings
                    except (json.JSONDecodeError, TypeError):
                        pass

        # Agent 設定（群組和私訊共用的中間層）
        if agent_id:
            row = await conn.fetchval(
                "SELECT voice_settings FROM ai_agents WHERE id = $1::uuid",
                agent_id,
            )
            if row:
                try:
                    settings = json.loads(row) if isinstance(row, str) else row
                    if settings.get("tts_engine"):
                        return settings
                except (json.JSONDecodeError, TypeError):
                    pass

    return system_default


@mcp.tool()
async def text_to_speech(
    text: str,
    ctos_user_id: int | None = None,
) -> str:
    """將文字轉換為語音檔案，用於語音回覆使用者。

    使用時機：
    - 使用者用語音訊息發問時，優先使用語音回覆
    - 可自訂要唸出的內容（摘要、口語化表達等）
    - 回覆主要是圖片/檔案/程式碼時不需要語音

    Args:
        text: 要轉換為語音的文字內容（上限 500 字，超過會截斷）
    """
    # MCP server 是獨立進程，extends/voice 路徑可能不在 sys.path
    vtts = _get_voice_tts_module()
    if vtts is None:
        return "❌ 語音功能未安裝"

    # 解析 ctos_user_id（支援環境變數 fallback）
    from .server import resolve_ctos_user_id
    user_id = resolve_ctos_user_id(ctos_user_id)

    # 從環境變數取得 group_id 和 agent_id
    group_id = os.environ.get("CTOS_GROUP_ID")
    agent_id = os.environ.get("CTOS_AGENT_ID")

    # 階層式解析語音設定
    settings = await resolve_voice_settings(
        ctos_user_id=user_id,
        group_id=group_id,
        agent_id=agent_id,
    )

    tts_engine = settings.get("tts_engine", "")
    tts_params = settings.get("tts_params", {})

    # 呼叫 TTS（傳入使用者設定的引擎名稱）
    result = await vtts.synthesize(text, engine_name=tts_engine, **tts_params)

    if result.error:
        logger.warning("TTS 生成失敗: %s", result.error)
        return f"❌ 語音生成失敗：{result.error}"

    # 回傳包含標記的成功訊息
    engine_label = tts_engine or "edge"
    voice_label = tts_params.get("voice") or tts_params.get("style") or "default"

    voice_data = json.dumps({
        "file_id": result.file_id,
        "duration_ms": result.duration_ms,
        "engine": engine_label,
        "voice": voice_label,
    }, ensure_ascii=False)

    return f"✅ 語音已生成（{result.duration_ms}ms）\n[VOICE_MESSAGE:{voice_data}]"
