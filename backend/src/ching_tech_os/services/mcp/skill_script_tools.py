"""Skill Script 執行工具

提供 run_skill_script MCP tool，讓 AI 執行 skill 的 scripts。
"""

import json
import logging

from .server import mcp

logger = logging.getLogger("mcp_server")


@mcp.tool()
async def run_skill_script(
    skill: str, script: str, input: str = "", ctos_user_id: int | None = None,
) -> str:
    """執行 skill 的 script。

    Args:
        skill: skill 名稱（例如 "weather"）
        script: script 檔名不含副檔名（例如 "get_forecast"）
        input: 傳給 script 的輸入字串（透過 stdin 傳入）
        ctos_user_id: CTOS 用戶 ID（由 bot framework 注入，非 LLM 控制）
    """
    # NOTE: ctos_user_id 由 bot framework 在呼叫時注入（見 agents.py），
    # LLM 無法控制此參數。MCP tool 簽名包含它是因為 framework 需要傳入。
    from ...skills import get_skill_manager
    from ...skills.script_runner import ScriptRunner

    sm = get_skill_manager()

    # 驗證 skill 存在
    skill_obj = await sm.get_skill(skill)
    if not skill_obj:
        return json.dumps({"success": False, "error": f"Skill not found: {skill}"}, ensure_ascii=False)

    # 權限檢查：驗證使用者有此 skill 的 requires_app 權限
    if skill_obj.requires_app:
        from ..permissions import get_user_app_permissions, DEFAULT_APP_PERMISSIONS
        if ctos_user_id:
            user_apps = await get_user_app_permissions(ctos_user_id)
            allowed = user_apps.get(skill_obj.requires_app, False)
        else:
            # 未提供使用者 ID，使用預設權限
            allowed = DEFAULT_APP_PERMISSIONS.get(skill_obj.requires_app, False)

        if not allowed:
            return json.dumps({
                "success": False,
                "error": f"無權限使用 skill '{skill}'（需要 {skill_obj.requires_app} 權限）",
            }, ensure_ascii=False)

    # 驗證 skill 有 scripts
    if not await sm.has_scripts(skill):
        return json.dumps({"success": False, "error": f"Skill '{skill}' has no scripts"}, ensure_ascii=False)

    # 驗證 script 存在（路徑穿越驗證在此）
    script_path = await sm.get_script_path(skill, script)
    if not script_path:
        return json.dumps({"success": False, "error": f"Script not found: {skill}/{script}"}, ensure_ascii=False)

    # 取得環境變數覆寫（從 SKILL.md metadata.openclaw.requires.env）
    env_overrides = sm.get_skill_env_overrides(skill_obj)

    # 執行（傳入已驗證的 script_path，避免重複解析）
    runner = ScriptRunner(sm.skills_dir)
    result = await runner.execute_path(script_path, skill, input=input, env_overrides=env_overrides)

    logger.info(
        f"run_skill_script: {skill}/{script} "
        f"success={result['success']} duration={result['duration_ms']}ms"
    )

    # 記錄 ai_log
    try:
        from ...models.ai import AiLogCreate
        from ...services.ai_manager import create_log

        log_data = AiLogCreate(
            model="script",
            input_prompt=f"{skill}/{script}: {input}",
            raw_response=result.get("output"),
            error_message=result.get("error") if not result.get("success") else None,
            duration_ms=result.get("duration_ms"),
            success=result.get("success", False),
            context_type="script",
            agent_id=None,
            prompt_id=None,
            context_id=None,
            input_tokens=0,
            output_tokens=0,
        )
        await create_log(log_data)
    except Exception:
        logger.warning("Failed to create ai_log for script execution", exc_info=True)

    return json.dumps(result, ensure_ascii=False)
