"""整合測試：未綁定用戶使用受限 agent（杰膚美衛教助理）

測試案例：
1. 查詢「青春痘怎麼處理？」 — 應能在 library/教育訓練/杰膚美衛教 中找到衛教資料
2. 查詢「公司專案有哪些？」 — 應搜不到（projects 被 allowed_shared_sources 排除）

⚠️ 此測試會連接真實資料庫和呼叫 Claude API，屬於整合測試。

執行方式：
  cd backend && BOT_UNBOUND_USER_POLICY=restricted uv run python tests/test_restricted_jfmskin.py
"""

import asyncio
import logging
import os
import sys

# 強制設定環境變數（模擬 restricted 策略）
os.environ["BOT_UNBOUND_USER_POLICY"] = "restricted"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 杰膚美群組的 bot_groups.id
JFMSKIN_GROUP_ID = "06aa5645-48e0-4b6c-8dae-dd42b87f1331"

# 模擬的 Line 使用者（未綁定 CTOS）
FAKE_LINE_USER_ID = "U_test_unbound_user_001"


async def _call_restricted(content: str) -> str | None:
    """呼叫受限模式 AI 並回傳回應"""
    from uuid import UUID
    from ching_tech_os.services.bot.identity_router import handle_restricted_mode

    return await handle_restricted_mode(
        content=content,
        platform_user_id=FAKE_LINE_USER_ID,
        bot_user_id=None,
        is_group=True,
        line_group_id=UUID(JFMSKIN_GROUP_ID),
        message_uuid=None,
        user_display_name="測試用戶",
        bot_group_id=JFMSKIN_GROUP_ID,
    )


def _log_reply(reply: str | None) -> None:
    """印出 AI 回應"""
    logger.info(f"\n{'='*60}")
    logger.info("AI 回應：")
    logger.info(f"{'='*60}")
    if reply:
        for line in reply.split('\n'):
            logger.info(f"  {line}")
    else:
        logger.info("  (None)")
    logger.info(f"{'='*60}")


async def test_in_scope_query():
    """測試 1：範圍內查詢 — 青春痘衛教應能找到"""
    logger.info("\n\n📋 測試 1：範圍內查詢（青春痘衛教）")
    logger.info("=" * 60)

    reply = await _call_restricted("青春痘怎麼處理？")
    _log_reply(reply)

    assert reply is not None, "AI 回應不應為 None"
    assert "系統設定錯誤" not in reply, f"不應出現系統錯誤：{reply}"

    acne_keywords = ["青春痘", "痘痘", "痤瘡", "用藥", "治療", "保養", "照護", "皮膚"]
    found = [kw for kw in acne_keywords if kw in reply]
    logger.info(f"  回應包含關鍵字: {found}")

    if len(found) > 0:
        logger.info("✅ 測試 1 通過：受限模式下可以查到青春痘衛教資料")
    else:
        logger.error(f"❌ 測試 1 失敗：回應中未包含青春痘相關關鍵字")
        logger.error(f"   回應前 300 字：{reply[:300]}")
        return False
    return True


async def test_out_of_scope_query():
    """測試 2：範圍外查詢 — 公司專案應搜不到（projects 被排除）"""
    logger.info("\n\n📋 測試 2：範圍外查詢（公司專案）")
    logger.info("=" * 60)

    reply = await _call_restricted("公司專案有哪些？請列出 NAS 上的專案資料夾")
    _log_reply(reply)

    assert reply is not None, "AI 回應不應為 None"

    # 不應包含真實專案名稱（表示搜尋被正確限制）
    # 回應中不應出現 shared://projects/ 路徑
    if "shared://projects/" in reply:
        logger.error("❌ 測試 2 失敗：回應包含 shared://projects/ 路徑，表示 projects 來源未被過濾")
        return False

    logger.info("✅ 測試 2 通過：回應中不包含 projects 來源的搜尋結果")
    return True


async def main():
    from ching_tech_os.database import init_db_pool, close_db_pool

    # 1. 初始化資料庫
    await init_db_pool()
    logger.info("✅ 資料庫連線池已初始化")

    try:
        from ching_tech_os.services.bot.identity_router import get_unbound_policy
        from ching_tech_os.services.linebot_agents import get_restricted_agent

        # 2. 確認策略是 restricted
        policy = get_unbound_policy()
        assert policy == "restricted", f"期望 restricted，實際為 {policy}"
        logger.info(f"✅ BOT_UNBOUND_USER_POLICY = {policy}")

        # 3. 確認群組有設定 restricted_agent_id 且有 NAS 來源限制
        agent = await get_restricted_agent(bot_group_id=JFMSKIN_GROUP_ID)
        assert agent is not None, "受限 Agent 不應為 None"
        logger.info(f"✅ 受限 Agent: {agent.get('name')} ({agent.get('display_name')})")
        logger.info(f"   工具: {agent.get('tools')}")
        logger.info(f"   Model: {agent.get('model')}")

        agent_settings = agent.get("settings") or {}
        logger.info(f"   allowed_shared_sources: {agent_settings.get('allowed_shared_sources')}")
        logger.info(f"   allowed_library_paths: {agent_settings.get('allowed_library_paths')}")

        # 4. 執行測試
        results = []
        results.append(await test_in_scope_query())
        results.append(await test_out_of_scope_query())

        # 5. 總結
        logger.info(f"\n\n{'='*60}")
        passed = sum(results)
        total = len(results)
        logger.info(f"測試結果：{passed}/{total} 通過")
        logger.info(f"{'='*60}")

        if not all(results):
            sys.exit(1)

    finally:
        await close_db_pool()
        logger.info("✅ 資料庫連線池已關閉")


if __name__ == "__main__":
    asyncio.run(main())
