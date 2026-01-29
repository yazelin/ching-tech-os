"""多平台綁定測試

測試 fix/multi-platform-binding 分支的修復：
1. verify_binding_code: 已綁 Line 仍可綁 Telegram
2. unbind_line_user: 指定平台只解除該平台
3. Telegram handler: 動態租戶解析
4. Telegram handler: AI 生成圖片儲存 bot_files 記錄

用法：
    cd backend
    uv run pytest tests/test_multi_platform_binding.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4


# 測試用常數
TENANT_ID = UUID("5d59e861-a72f-4dde-9169-647036fae123")
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000000")
CTOS_USER_ID = 31
LINE_BOT_USER_UUID = uuid4()
TELEGRAM_BOT_USER_UUID = uuid4()
LINE_PLATFORM_USER_ID = "U3cf7bc464d58f47236c20587b1808a07"
TELEGRAM_PLATFORM_USER_ID = "850654509"


# ============================================================
# verify_binding_code 平台隔離測試
# ============================================================

class TestVerifyBindingCodePlatformIsolation:
    """verify_binding_code 應該只檢查同平台的綁定，不同平台互不干擾"""

    @pytest.mark.asyncio
    async def test_can_bind_telegram_when_line_already_bound(self):
        """已綁定 Line 的用戶，仍可綁定 Telegram"""
        from ching_tech_os.services.linebot import verify_binding_code

        code_row = {
            "id": uuid4(),
            "user_id": CTOS_USER_ID,
            "tenant_id": TENANT_ID,
        }
        # Telegram 用戶記錄
        line_user_row = {
            "platform_user_id": TELEGRAM_PLATFORM_USER_ID,
            "display_name": "Yaze Lin",
            "platform_type": "telegram",
        }
        # 目標租戶沒有此 Telegram 用戶（首次綁定）
        target_line_user = None
        # 已有 Line 的綁定，但不應影響 Telegram
        # 關鍵：查詢加了 platform_type='telegram'，不會找到 Line 的記錄
        existing_same_platform = None

        conn = AsyncMock()
        # 1. 查詢驗證碼
        conn.fetchrow = AsyncMock(side_effect=[
            code_row,       # bot_binding_codes 查詢
            line_user_row,  # bot_users 查詢（Telegram 用戶）
            target_line_user,  # 目標租戶是否已有此用戶
            existing_same_platform,  # 是否已綁定同平台其他帳號
        ])
        # 建立新用戶記錄
        conn.fetchval = AsyncMock(return_value=uuid4())
        conn.execute = AsyncMock()

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.linebot.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.linebot._get_tenant_id", return_value=DEFAULT_TENANT_ID):
            success, msg = await verify_binding_code(TELEGRAM_BOT_USER_UUID, "123456")

        assert success is True
        assert "綁定成功" in msg

    @pytest.mark.asyncio
    async def test_cannot_bind_same_platform_twice(self):
        """同一平台不能重複綁定"""
        from ching_tech_os.services.linebot import verify_binding_code

        code_row = {
            "id": uuid4(),
            "user_id": CTOS_USER_ID,
            "tenant_id": TENANT_ID,
        }
        line_user_row = {
            "platform_user_id": TELEGRAM_PLATFORM_USER_ID,
            "display_name": "Yaze Lin",
            "platform_type": "telegram",
        }
        # 目標租戶沒有此用戶
        target_line_user = None
        # 已有同平台的綁定
        existing_same_platform = {"id": uuid4()}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[
            code_row,
            line_user_row,
            target_line_user,
            existing_same_platform,
        ])
        conn.fetchval = AsyncMock(return_value=uuid4())
        conn.execute = AsyncMock()

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.linebot.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.linebot._get_tenant_id", return_value=DEFAULT_TENANT_ID):
            success, msg = await verify_binding_code(TELEGRAM_BOT_USER_UUID, "123456")

        assert success is False
        assert "已綁定" in msg


# ============================================================
# unbind_line_user 平台指定測試
# ============================================================

class TestUnbindPlatformSpecific:
    """unbind_line_user 指定平台時只解除該平台"""

    @pytest.mark.asyncio
    async def test_unbind_specific_platform(self):
        """指定 platform_type 時，SQL 應包含 platform_type 條件"""
        from ching_tech_os.services.linebot import unbind_line_user

        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.linebot.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.linebot._get_tenant_id", return_value=TENANT_ID):
            result = await unbind_line_user(CTOS_USER_ID, tenant_id=TENANT_ID, platform_type="telegram")

        assert result is True
        # 確認 SQL 有三個參數（user_id, tenant_id, platform_type）
        call_args = conn.execute.call_args
        sql = call_args[0][0]
        assert "platform_type" in sql
        assert call_args[0][3] == "telegram"

    @pytest.mark.asyncio
    async def test_unbind_all_platforms(self):
        """不指定 platform_type 時，解除所有平台"""
        from ching_tech_os.services.linebot import unbind_line_user

        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 2")

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.linebot.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.linebot._get_tenant_id", return_value=TENANT_ID):
            result = await unbind_line_user(CTOS_USER_ID, tenant_id=TENANT_ID, platform_type=None)

        assert result is True
        # 確認 SQL 只有兩個參數（user_id, tenant_id），沒有 platform_type
        call_args = conn.execute.call_args
        sql = call_args[0][0]
        assert "platform_type" not in sql

    @pytest.mark.asyncio
    async def test_unbind_not_found(self):
        """找不到綁定記錄時回傳 False"""
        from ching_tech_os.services.linebot import unbind_line_user

        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 0")

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.linebot.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.linebot._get_tenant_id", return_value=TENANT_ID):
            result = await unbind_line_user(CTOS_USER_ID, tenant_id=TENANT_ID, platform_type="telegram")

        assert result is False


# ============================================================
# Telegram handler 租戶解析測試
# ============================================================

class TestTelegramTenantResolution:
    """Telegram handler 應動態解析租戶，不使用固定預設租戶"""

    @pytest.mark.asyncio
    async def test_handle_text_uses_resolve_tenant(self):
        """_handle_text 應呼叫 resolve_tenant_for_message 而非 _get_tenant_id"""
        from ching_tech_os.services.bot_telegram.handler import _handle_text

        # 建立 mock 物件
        message = MagicMock()
        message.message_id = 12345
        message.text = "hello"

        chat = MagicMock()
        chat.id = 850654509

        user = MagicMock()
        user.id = 850654509
        user.full_name = "Yaze Lin"

        adapter = AsyncMock()
        adapter.bot_username = "test_bot"

        with patch("ching_tech_os.services.bot_telegram.handler.resolve_tenant_for_message",
                    new_callable=AsyncMock, return_value=TENANT_ID) as mock_resolve, \
             patch("ching_tech_os.services.bot_telegram.handler.get_connection") as mock_conn, \
             patch("ching_tech_os.services.bot_telegram.handler._ensure_bot_user",
                    new_callable=AsyncMock, return_value=TELEGRAM_BOT_USER_UUID), \
             patch("ching_tech_os.services.bot_telegram.handler.check_line_access",
                    new_callable=AsyncMock, return_value=(True, None)), \
             patch("ching_tech_os.services.bot_telegram.handler._get_reply_context",
                    new_callable=AsyncMock, return_value=""), \
             patch("ching_tech_os.services.bot_telegram.handler._handle_text_with_ai",
                    new_callable=AsyncMock):
            # 設定 mock DB
            conn = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.return_value = mock_ctx

            await _handle_text(
                message, "hello", "850654509", chat, user, False, adapter
            )

            # 驗證使用了動態租戶解析
            mock_resolve.assert_called_once_with(None, "850654509")


# ============================================================
# Telegram _save_message tenant_id 傳遞測試
# ============================================================

class TestTelegramSaveMessageTenantId:
    """_save_message 應使用傳入的 tenant_id 而非預設值"""

    @pytest.mark.asyncio
    async def test_save_message_uses_passed_tenant_id(self):
        """傳入 tenant_id 時，不應使用 _get_tenant_id 的預設值"""
        from ching_tech_os.services.bot_telegram.handler import _save_message

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": uuid4()})

        msg_uuid = await _save_message(
            conn,
            message_id="tg_123",
            bot_user_id=TELEGRAM_BOT_USER_UUID,
            bot_group_id=None,
            message_type="text",
            content="test",
            is_from_bot=False,
            tenant_id=TENANT_ID,
        )

        # 確認 INSERT 時使用了正確的 tenant_id
        call_args = conn.fetchrow.call_args[0]
        # 第 7 個參數是 tenant_id（$7）
        assert call_args[7] == TENANT_ID

    @pytest.mark.asyncio
    async def test_save_message_falls_back_to_default(self):
        """不傳 tenant_id 時，應使用預設租戶"""
        from ching_tech_os.services.bot_telegram.handler import _save_message

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": uuid4()})

        with patch("ching_tech_os.services.bot_telegram.handler._get_tenant_id",
                    return_value=DEFAULT_TENANT_ID):
            await _save_message(
                conn,
                message_id="tg_123",
                bot_user_id=TELEGRAM_BOT_USER_UUID,
                bot_group_id=None,
                message_type="text",
                content="test",
                is_from_bot=False,
            )

        call_args = conn.fetchrow.call_args[0]
        assert call_args[7] == DEFAULT_TENANT_ID


# ============================================================
# Telegram _ensure_bot_user tenant_id 傳遞測試
# ============================================================

class TestEnsureBotUserTenantId:
    """_ensure_bot_user 應使用傳入的 tenant_id"""

    @pytest.mark.asyncio
    async def test_ensure_bot_user_uses_passed_tenant_id(self):
        """傳入 tenant_id 時，查詢和建立都應使用該 tenant_id"""
        from ching_tech_os.services.bot_telegram.handler import _ensure_bot_user

        user = MagicMock()
        user.id = 850654509
        user.full_name = "Yaze Lin"

        existing_row = {"id": TELEGRAM_BOT_USER_UUID, "display_name": "Yaze Lin"}
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=existing_row)

        result = await _ensure_bot_user(user, conn, tenant_id=TENANT_ID)

        assert result == TELEGRAM_BOT_USER_UUID
        # 確認查詢使用了正確的 tenant_id
        call_args = conn.fetchrow.call_args[0]
        assert TENANT_ID in call_args


# ============================================================
# 前端 polling 邏輯測試（驗證 API 回應結構）
# ============================================================

class TestBindingStatusPlatformSpecific:
    """binding/status API 回應應包含各平台獨立狀態"""

    @pytest.mark.asyncio
    async def test_binding_status_has_platform_specific_fields(self):
        """回應應包含 line 和 telegram 的獨立 is_bound 狀態"""
        from ching_tech_os.services.linebot import get_binding_status

        # 模擬：Line 已綁定，Telegram 未綁定
        rows = [
            {
                "platform_type": "line",
                "display_name": "林亞澤",
                "picture_url": None,
                "bound_at": None,
            }
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=rows)

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.linebot.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.linebot._get_tenant_id", return_value=TENANT_ID):
            status = await get_binding_status(CTOS_USER_ID, tenant_id=TENANT_ID)

        # 頂層 is_bound 為 True（任一平台已綁定）
        assert status["is_bound"] is True
        # Line 已綁定
        assert status["line"]["is_bound"] is True
        assert status["line"]["display_name"] == "林亞澤"
        # Telegram 未綁定
        assert status["telegram"]["is_bound"] is False
        assert status["telegram"]["display_name"] is None
