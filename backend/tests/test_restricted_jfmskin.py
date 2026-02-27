"""整合測試：未綁定用戶使用受限 agent（杰膚美衛教助理）查詢青春痘

模擬 Line webhook 中未綁定 CTOS 帳號的使用者，
在設定了 jfmskin-edu 受限 Agent 的群組中發問「青春痘怎麼處理？」，
驗證能正確查到衛教資料。

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


async def main():
    from uuid import UUID
    from ching_tech_os.database import init_db_pool, close_db_pool

    # 1. 初始化資料庫
    await init_db_pool()
    logger.info("✅ 資料庫連線池已初始化")

    try:
        from ching_tech_os.services.bot.identity_router import (
            handle_restricted_mode,
            get_unbound_policy,
        )

        # 2. 確認策略是 restricted
        policy = get_unbound_policy()
        assert policy == "restricted", f"期望 restricted，實際為 {policy}"
        logger.info(f"✅ BOT_UNBOUND_USER_POLICY = {policy}")

        # 3. 確認群組有設定 restricted_agent_id
        from ching_tech_os.services.linebot_agents import get_restricted_agent
        agent = await get_restricted_agent(bot_group_id=JFMSKIN_GROUP_ID)
        assert agent is not None, "受限 Agent 不應為 None"
        logger.info(f"✅ 受限 Agent: {agent.get('name')} ({agent.get('display_name')})")
        logger.info(f"   工具: {agent.get('tools')}")
        logger.info(f"   Model: {agent.get('model')}")

        # 4. 呼叫受限模式 AI 處理
        logger.info(f"\n正在呼叫 handle_restricted_mode...")
        logger.info(f"  問題: 青春痘怎麼處理？")
        logger.info(f"  群組 ID: {JFMSKIN_GROUP_ID}")
        logger.info(f"  模擬用戶: {FAKE_LINE_USER_ID}")

        reply = await handle_restricted_mode(
            content="青春痘怎麼處理？",
            platform_user_id=FAKE_LINE_USER_ID,
            bot_user_id=None,
            is_group=True,
            line_group_id=UUID(JFMSKIN_GROUP_ID),
            message_uuid=None,
            user_display_name="測試用戶",
            bot_group_id=JFMSKIN_GROUP_ID,
        )

        logger.info(f"\n{'='*60}")
        logger.info("AI 回應：")
        logger.info(f"{'='*60}")
        if reply:
            for line in reply.split('\n'):
                logger.info(f"  {line}")
        else:
            logger.info("  (None)")
        logger.info(f"{'='*60}")

        # 5. 驗證
        assert reply is not None, "AI 回應不應為 None"
        assert "系統設定錯誤" not in reply, f"不應出現系統錯誤：{reply}"

        # 檢查是否包含青春痘相關內容
        acne_keywords = ["青春痘", "痘痘", "痤瘡", "用藥", "治療", "保養", "照護", "皮膚"]
        found = [kw for kw in acne_keywords if kw in reply]
        logger.info(f"✅ 回應包含關鍵字: {found}")

        if len(found) > 0:
            logger.info("✅ 測試通過：受限模式下杰膚美 agent 可以正確查到青春痘衛教資料")
        else:
            logger.warning(f"⚠️ 回應中未包含青春痘相關關鍵字，回應前 300 字：{reply[:300]}")
            sys.exit(1)

    finally:
        await close_db_pool()
        logger.info("✅ 資料庫連線池已關閉")


if __name__ == "__main__":
    asyncio.run(main())
