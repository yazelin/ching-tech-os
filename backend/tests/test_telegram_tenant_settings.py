"""Telegram Bot 租戶級設定測試

測試 feature/telegram-tenant-settings 分支的功能：
1. TenantSettings model 的 Telegram 欄位
2. 加密/解密/遮蔽 Telegram 憑證
3. get_tenant_telegram_credentials / update_tenant_telegram_settings
4. 租戶管理 API endpoints
5. 平台管理 API endpoints

用法：
    cd backend
    uv run pytest tests/test_telegram_tenant_settings.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4


TENANT_ID = UUID("5d59e861-a72f-4dde-9169-647036fae123")
BOT_TOKEN = "8294724422:AAGcyzWUMVagdOuYBQUuoAWYcknQiK3SjGo"
ADMIN_CHAT_ID = "850654509"


# ============================================================
# 加密/解密/遮蔽函式測試
# ============================================================

class TestEncryptDecryptTelegramCredentials:
    """加密/解密/遮蔽函式應正確處理 Telegram 欄位"""

    def test_encrypt_telegram_bot_token(self):
        """telegram_bot_token 應被加密"""
        from ching_tech_os.services.tenant import _encrypt_settings_credentials

        settings = {"telegram_bot_token": BOT_TOKEN, "telegram_admin_chat_id": ADMIN_CHAT_ID}

        with patch("ching_tech_os.services.tenant.encrypt_credential", return_value="encrypted_token") as mock_enc:
            result = _encrypt_settings_credentials(settings)

        mock_enc.assert_called_once_with(BOT_TOKEN)
        assert result["telegram_bot_token"] == "encrypted_token"
        # admin_chat_id 不加密
        assert result["telegram_admin_chat_id"] == ADMIN_CHAT_ID

    def test_decrypt_telegram_bot_token(self):
        """telegram_bot_token 應被解密"""
        from ching_tech_os.services.tenant import _decrypt_settings_credentials

        settings = {"telegram_bot_token": "encrypted_token"}

        with patch("ching_tech_os.services.tenant.decrypt_credential", return_value=BOT_TOKEN) as mock_dec:
            result = _decrypt_settings_credentials(settings)

        mock_dec.assert_called_once_with("encrypted_token")
        assert result["telegram_bot_token"] == BOT_TOKEN

    def test_decrypt_telegram_bot_token_failure(self):
        """解密失敗時應設為 None"""
        from ching_tech_os.services.tenant import _decrypt_settings_credentials

        settings = {"telegram_bot_token": "bad_encrypted"}

        with patch("ching_tech_os.services.tenant.decrypt_credential", side_effect=ValueError("bad")):
            result = _decrypt_settings_credentials(settings)

        assert result["telegram_bot_token"] is None

    def test_mask_telegram_bot_token(self):
        """遮蔽函式應清除 telegram_bot_token"""
        from ching_tech_os.services.tenant import _mask_settings_credentials

        settings = {
            "telegram_bot_token": "encrypted_token",
            "telegram_admin_chat_id": ADMIN_CHAT_ID,
            "line_channel_secret": "enc_secret",
            "line_channel_access_token": "enc_token",
        }
        result = _mask_settings_credentials(settings)

        assert result["telegram_bot_token"] is None
        assert result["line_channel_secret"] is None
        assert result["line_channel_access_token"] is None
        # admin_chat_id 不遮蔽
        assert result["telegram_admin_chat_id"] == ADMIN_CHAT_ID


# ============================================================
# get_tenant_telegram_credentials 測試
# ============================================================

class TestGetTenantTelegramCredentials:
    """取得租戶 Telegram Bot 憑證"""

    @pytest.mark.asyncio
    async def test_returns_credentials_when_configured(self):
        """已設定時回傳解密後的憑證"""
        from ching_tech_os.services.tenant import get_tenant_telegram_credentials

        settings_data = {
            "telegram_bot_token": "encrypted_token",
            "telegram_admin_chat_id": ADMIN_CHAT_ID,
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"settings": json.dumps(settings_data)})

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.tenant.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.tenant.decrypt_credential", return_value=BOT_TOKEN):
            result = await get_tenant_telegram_credentials(TENANT_ID)

        assert result is not None
        assert result["bot_token"] == BOT_TOKEN
        assert result["admin_chat_id"] == ADMIN_CHAT_ID

    @pytest.mark.asyncio
    async def test_returns_none_when_not_configured(self):
        """未設定時回傳 None"""
        from ching_tech_os.services.tenant import get_tenant_telegram_credentials

        settings_data = {}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"settings": json.dumps(settings_data)})

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.tenant.get_connection", return_value=MockCtxMgr()):
            result = await get_tenant_telegram_credentials(TENANT_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_tenant_not_found(self):
        """租戶不存在時回傳 None"""
        from ching_tech_os.services.tenant import get_tenant_telegram_credentials

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.tenant.get_connection", return_value=MockCtxMgr()):
            result = await get_tenant_telegram_credentials(TENANT_ID)

        assert result is None


# ============================================================
# update_tenant_telegram_settings 測試
# ============================================================

class TestUpdateTenantTelegramSettings:
    """更新租戶 Telegram Bot 設定"""

    @pytest.mark.asyncio
    async def test_update_with_token(self):
        """更新 Bot Token 時應加密儲存"""
        from ching_tech_os.services.tenant import update_tenant_telegram_settings

        existing_settings = {"line_channel_id": "some_id"}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"settings": json.dumps(existing_settings)})
        conn.execute = AsyncMock()

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.tenant.get_connection", return_value=MockCtxMgr()), \
             patch("ching_tech_os.services.tenant.encrypt_credential", return_value="encrypted_token"):
            result = await update_tenant_telegram_settings(
                TENANT_ID, bot_token=BOT_TOKEN, admin_chat_id=ADMIN_CHAT_ID
            )

        assert result is True
        # 確認 execute 被呼叫（儲存設定）
        conn.execute.assert_called_once()
        saved_json = conn.execute.call_args[0][2]
        saved = json.loads(saved_json)
        assert saved["telegram_bot_token"] == "encrypted_token"
        assert saved["telegram_admin_chat_id"] == ADMIN_CHAT_ID
        # 原有設定不受影響
        assert saved["line_channel_id"] == "some_id"

    @pytest.mark.asyncio
    async def test_clear_settings(self):
        """清除設定時 token 和 chat_id 都設為 None"""
        from ching_tech_os.services.tenant import update_tenant_telegram_settings

        existing_settings = {
            "telegram_bot_token": "encrypted_token",
            "telegram_admin_chat_id": ADMIN_CHAT_ID,
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"settings": json.dumps(existing_settings)})
        conn.execute = AsyncMock()

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.tenant.get_connection", return_value=MockCtxMgr()):
            result = await update_tenant_telegram_settings(
                TENANT_ID, bot_token=None, admin_chat_id=None
            )

        assert result is True
        saved_json = conn.execute.call_args[0][2]
        saved = json.loads(saved_json)
        assert saved["telegram_bot_token"] is None
        assert saved["telegram_admin_chat_id"] is None

    @pytest.mark.asyncio
    async def test_tenant_not_found(self):
        """租戶不存在時回傳 False"""
        from ching_tech_os.services.tenant import update_tenant_telegram_settings

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        class MockCtxMgr:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, *args):
                pass

        with patch("ching_tech_os.services.tenant.get_connection", return_value=MockCtxMgr()):
            result = await update_tenant_telegram_settings(
                TENANT_ID, bot_token=BOT_TOKEN, admin_chat_id=ADMIN_CHAT_ID
            )

        assert result is False


# ============================================================
# build_system_prompt platform_type 測試
# ============================================================

class TestBuildSystemPromptPlatformType:
    """build_system_prompt 應根據 platform_type 顯示正確的對話識別"""

    @pytest.mark.asyncio
    async def test_telegram_platform_label(self):
        """platform_type=telegram 時，對話識別應顯示 Telegram"""
        from ching_tech_os.services.linebot_ai import build_system_prompt

        with patch("ching_tech_os.services.linebot_ai.get_line_user_record",
                    new_callable=AsyncMock, return_value={"id": uuid4(), "user_id": 31}), \
             patch("ching_tech_os.services.linebot.get_active_user_memories",
                    new_callable=AsyncMock, return_value=[]):
            result = await build_system_prompt(
                line_group_id=None,
                line_user_id="850654509",
                base_prompt="你是助手",
                platform_type="telegram",
                tenant_id=TENANT_ID,
            )

        assert "平台：Telegram" in result
        assert "telegram_user_id: 850654509" in result
        assert f"ctos_tenant_id: {TENANT_ID}" in result

    @pytest.mark.asyncio
    async def test_line_platform_label(self):
        """platform_type=line（預設）時，對話識別應顯示 Line"""
        from ching_tech_os.services.linebot_ai import build_system_prompt

        with patch("ching_tech_os.services.linebot_ai.get_line_user_record",
                    new_callable=AsyncMock, return_value={"id": uuid4(), "user_id": 31}), \
             patch("ching_tech_os.services.linebot.get_active_user_memories",
                    new_callable=AsyncMock, return_value=[]):
            result = await build_system_prompt(
                line_group_id=None,
                line_user_id="U3cf7bc464d58f47236c20587b1808a07",
                base_prompt="你是助手",
                platform_type="line",
                tenant_id=TENANT_ID,
            )

        assert "平台：Line" in result
        assert "line_user_id: U3cf7bc464d58f47236c20587b1808a07" in result


# ============================================================
# 未綁定用戶提示訊息測試
# ============================================================

class TestUnboundUserShowsTelegramId:
    """未綁定用戶的提示訊息應包含 Telegram ID"""

    @pytest.mark.asyncio
    async def test_deny_message_includes_telegram_id(self):
        """user_not_bound 時回覆應包含用戶的 Telegram ID"""
        from ching_tech_os.services.bot_telegram.handler import _handle_text

        message = MagicMock()
        message.message_id = 12345
        message.text = "hello"
        message.reply_to_message = None

        chat = MagicMock()
        chat.id = 850654509
        chat.type = "private"

        user = MagicMock()
        user.id = 850654509
        user.full_name = "Yaze Lin"

        adapter = AsyncMock()
        adapter.bot_username = "test_bot"

        with patch("ching_tech_os.services.bot_telegram.handler.resolve_tenant_for_message",
                    new_callable=AsyncMock, return_value=TENANT_ID), \
             patch("ching_tech_os.services.bot_telegram.handler.get_connection") as mock_conn, \
             patch("ching_tech_os.services.bot_telegram.handler._ensure_bot_user",
                    new_callable=AsyncMock, return_value=uuid4()), \
             patch("ching_tech_os.services.bot_telegram.handler.check_line_access",
                    new_callable=AsyncMock, return_value=(False, "user_not_bound")):
            conn = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_conn.return_value = mock_ctx

            await _handle_text(
                message, "hello", "850654509", chat, user, False, adapter
            )

            # 驗證回覆包含 Telegram ID
            adapter.send_text.assert_called_once()
            reply_text = adapter.send_text.call_args[0][1]
            assert "850654509" in reply_text
            assert "Telegram ID" in reply_text
