"""Skill Script 執行工具

提供 run_skill_script MCP tool，讓 AI 執行 skill 的 scripts。
"""

import json
import logging

from .server import mcp

logger = logging.getLogger("mcp_server")


@mcp.tool()
async def run_skill_script(
    skill: str, script: str, input_str: str = "", ctos_user_id: int | None = None,
) -> str:
    """執行 skill 的 script。

    Args:
        skill: skill 名稱（例如 "weather"）
        script: script 檔名不含副檔名（例如 "get_forecast"）
        input_str: 傳給 script 的輸入字串（透過 stdin 傳入）
        ctos_user_id: CTOS 用戶 ID（用於權限檢查）
    """
    from ...skills import get_skill_manager
    from ...skills.script_runner import ScriptRunner

    sm = get_skill_manager()

    # 驗證 skill 存在
    skill_obj = await sm.get_skill(skill)
    if not skill_obj:
        return json.dumps({"success": False, "error": f"Skill not found: {skill}"}, ensure_ascii=False)

    # 權限檢查：驗證使用者有此 skill 的 requires_app 權限
    if skill_obj.requires_app and ctos_user_id:
        from ..permissions import get_user_app_permissions
        user_apps = await get_user_app_permissions(ctos_user_id)
        if not user_apps.get(skill_obj.requires_app, False):
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
    result = await runner.execute_path(script_path, skill, input_str=input_str, env_overrides=env_overrides)

    logger.info(
        f"run_skill_script: {skill}/{script} "
        f"success={result['success']} duration={result['duration_ms']}ms"
    )

    return json.dumps(result, ensure_ascii=False)
