"""Line Bot 多租戶測試

測試 Line Bot 的多租戶功能：
- 簽章驗證 (verify_signature)
- 多租戶簽章驗證 (verify_signature_multi_tenant, verify_webhook_signature)
- 租戶 secrets 快取機制
- Webhook 租戶識別
"""

import base64
import hashlib
import hmac
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

from ching_tech_os.services import linebot as linebot_service


# 測試用租戶資料
TENANT_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

TENANT_A_SECRET = "tenant-a-channel-secret"
TENANT_B_SECRET = "tenant-b-channel-secret"
DEFAULT_SECRET = "default-channel-secret"


def generate_signature(body: bytes, secret: str) -> str:
    """產生有效的 Line Webhook 簽章"""
    hash_value = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(hash_value).decode("utf-8")


# ============================================================
# verify_signature 基本測試
# ============================================================

class TestVerifySignature:
    """verify_signature 函數測試"""

    def test_valid_signature(self):
        """正確簽章應驗證成功"""
        body = b'{"events":[]}'
        secret = "test-secret"
        signature = generate_signature(body, secret)

        result = linebot_service.verify_signature(body, signature, secret)
        assert result is True

    def test_invalid_signature(self):
        """錯誤簽章應驗證失敗"""
        body = b'{"events":[]}'
        secret = "test-secret"
        wrong_signature = "wrong-signature"

        result = linebot_service.verify_signature(body, signature=wrong_signature, channel_secret=secret)
        assert result is False

    def test_wrong_secret(self):
        """使用錯誤 secret 應驗證失敗"""
        body = b'{"events":[]}'
        correct_secret = "correct-secret"
        wrong_secret = "wrong-secret"
        signature = generate_signature(body, correct_secret)

        result = linebot_service.verify_signature(body, signature, wrong_secret)
        assert result is False

    def test_tampered_body(self):
        """竄改過的 body 應驗證失敗"""
        original_body = b'{"events":[]}'
        tampered_body = b'{"events":[{"type":"message"}]}'
        secret = "test-secret"
        signature = generate_signature(original_body, secret)

        result = linebot_service.verify_signature(tampered_body, signature, secret)
        assert result is False

    def test_empty_secret_returns_false(self):
        """空 secret 應回傳 False"""
        body = b'{"events":[]}'

        with patch.object(linebot_service.settings, "line_channel_secret", ""):
            result = linebot_service.verify_signature(body, "any-signature", channel_secret="")
            assert result is False


# ============================================================
# 多租戶簽章驗證測試
# ============================================================

class TestVerifySignatureMultiTenant:
    """verify_signature_multi_tenant 函數測試"""

    @pytest.fixture
    def mock_tenant_secrets(self):
        """模擬租戶 secrets 快取"""
        return [
            {
                "tenant_id": TENANT_A_ID,
                "channel_id": "channel-a",
                "channel_secret": TENANT_A_SECRET,
            },
            {
                "tenant_id": TENANT_B_ID,
                "channel_id": "channel-b",
                "channel_secret": TENANT_B_SECRET,
            },
        ]

    @pytest.mark.asyncio
    async def test_tenant_a_signature_returns_tenant_a_id(self, mock_tenant_secrets):
        """租戶 A 的簽章應回傳租戶 A 的 ID"""
        body = b'{"events":[]}'
        signature = generate_signature(body, TENANT_A_SECRET)

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache:
            mock_cache.return_value = mock_tenant_secrets

            result = await linebot_service.verify_signature_multi_tenant(body, signature)
            assert result == TENANT_A_ID

    @pytest.mark.asyncio
    async def test_tenant_b_signature_returns_tenant_b_id(self, mock_tenant_secrets):
        """租戶 B 的簽章應回傳租戶 B 的 ID"""
        body = b'{"events":[]}'
        signature = generate_signature(body, TENANT_B_SECRET)

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache:
            mock_cache.return_value = mock_tenant_secrets

            result = await linebot_service.verify_signature_multi_tenant(body, signature)
            assert result == TENANT_B_ID

    @pytest.mark.asyncio
    async def test_default_bot_signature_returns_none(self, mock_tenant_secrets):
        """共用 Bot 簽章應回傳 None"""
        body = b'{"events":[]}'
        signature = generate_signature(body, DEFAULT_SECRET)

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache, \
             patch.object(linebot_service.settings, "line_channel_secret", DEFAULT_SECRET):
            mock_cache.return_value = mock_tenant_secrets

            result = await linebot_service.verify_signature_multi_tenant(body, signature)
            # None 表示使用共用 Bot
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_none(self, mock_tenant_secrets):
        """無效簽章應回傳 None"""
        body = b'{"events":[]}'
        invalid_signature = "invalid-signature"

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache, \
             patch.object(linebot_service.settings, "line_channel_secret", DEFAULT_SECRET):
            mock_cache.return_value = mock_tenant_secrets

            result = await linebot_service.verify_signature_multi_tenant(body, invalid_signature)
            assert result is None

    @pytest.mark.asyncio
    async def test_empty_tenant_secrets_falls_back_to_default(self):
        """沒有租戶設定時應 fallback 到預設 Bot"""
        body = b'{"events":[]}'
        signature = generate_signature(body, DEFAULT_SECRET)

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache, \
             patch.object(linebot_service.settings, "line_channel_secret", DEFAULT_SECRET):
            mock_cache.return_value = []  # 沒有租戶設定

            result = await linebot_service.verify_signature_multi_tenant(body, signature)
            assert result is None  # 使用預設 Bot


# ============================================================
# verify_webhook_signature 測試
# ============================================================

class TestVerifyWebhookSignature:
    """verify_webhook_signature 函數測試"""

    @pytest.fixture
    def mock_tenant_secrets(self):
        """模擬租戶 secrets 快取"""
        return [
            {
                "tenant_id": TENANT_A_ID,
                "channel_id": "channel-a",
                "channel_secret": TENANT_A_SECRET,
            },
        ]

    @pytest.mark.asyncio
    async def test_valid_tenant_signature_returns_true_with_tenant_id(self, mock_tenant_secrets):
        """有效租戶簽章應回傳 (True, tenant_id, secret)"""
        body = b'{"events":[]}'
        signature = generate_signature(body, TENANT_A_SECRET)

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache:
            mock_cache.return_value = mock_tenant_secrets

            is_valid, tenant_id, secret = await linebot_service.verify_webhook_signature(body, signature)
            assert is_valid is True
            assert tenant_id == TENANT_A_ID
            assert secret == TENANT_A_SECRET

    @pytest.mark.asyncio
    async def test_valid_default_signature_returns_true_with_none(self, mock_tenant_secrets):
        """有效預設 Bot 簽章應回傳 (True, None, None)"""
        body = b'{"events":[]}'
        signature = generate_signature(body, DEFAULT_SECRET)

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache, \
             patch.object(linebot_service.settings, "line_channel_secret", DEFAULT_SECRET):
            mock_cache.return_value = mock_tenant_secrets

            is_valid, tenant_id, secret = await linebot_service.verify_webhook_signature(body, signature)
            assert is_valid is True
            assert tenant_id is None
            assert secret is None

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_false(self, mock_tenant_secrets):
        """無效簽章應回傳 (False, None, None)"""
        body = b'{"events":[]}'
        invalid_signature = "invalid"

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache, \
             patch.object(linebot_service.settings, "line_channel_secret", DEFAULT_SECRET):
            mock_cache.return_value = mock_tenant_secrets

            is_valid, tenant_id, secret = await linebot_service.verify_webhook_signature(body, invalid_signature)
            assert is_valid is False
            assert tenant_id is None
            assert secret is None


# ============================================================
# 租戶 secrets 快取測試
# ============================================================

class TestTenantSecretsCache:
    """租戶 secrets 快取機制測試"""

    def setup_method(self):
        """每個測試前清除快取"""
        linebot_service.invalidate_tenant_secrets_cache()

    @pytest.mark.asyncio
    async def test_cache_loads_on_first_call(self):
        """第一次呼叫應載入快取"""
        mock_secrets = [{"tenant_id": TENANT_A_ID, "channel_secret": TENANT_A_SECRET}]

        with patch.object(linebot_service, "_load_tenant_secrets", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = mock_secrets

            result = await linebot_service.get_cached_tenant_secrets()

            assert result == mock_secrets
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_reuses_on_second_call(self):
        """第二次呼叫應重用快取"""
        mock_secrets = [{"tenant_id": TENANT_A_ID, "channel_secret": TENANT_A_SECRET}]

        with patch.object(linebot_service, "_load_tenant_secrets", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = mock_secrets

            # 第一次呼叫
            await linebot_service.get_cached_tenant_secrets()
            # 第二次呼叫
            await linebot_service.get_cached_tenant_secrets()

            # 應只載入一次
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self):
        """快取應在 TTL 後過期"""
        mock_secrets = [{"tenant_id": TENANT_A_ID, "channel_secret": TENANT_A_SECRET}]

        with patch.object(linebot_service, "_load_tenant_secrets", new_callable=AsyncMock) as mock_load, \
             patch.object(linebot_service, "TENANT_SECRETS_CACHE_TTL", 0.1):  # 設定短 TTL
            mock_load.return_value = mock_secrets

            # 第一次呼叫
            await linebot_service.get_cached_tenant_secrets()
            # 等待 TTL 過期
            time.sleep(0.15)
            # 第二次呼叫（應重新載入）
            await linebot_service.get_cached_tenant_secrets()

            # 應載入兩次
            assert mock_load.call_count == 2

    def test_invalidate_cache_clears_cache(self):
        """invalidate_tenant_secrets_cache 應清除快取"""
        # 設定快取
        linebot_service._tenant_secrets_cache = [{"test": "data"}]
        linebot_service._tenant_secrets_cache_time = time.time()

        # 清除快取
        linebot_service.invalidate_tenant_secrets_cache()

        # 確認已清除
        assert linebot_service._tenant_secrets_cache is None
        assert linebot_service._tenant_secrets_cache_time == 0


# ============================================================
# Webhook 路由整合測試
# ============================================================

class TestWebhookIntegration:
    """Webhook 端點整合測試"""

    @pytest.mark.asyncio
    async def test_webhook_identifies_tenant_from_signature(self):
        """Webhook 應從簽章識別租戶"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ching_tech_os.api import linebot_router

        app = FastAPI()
        app.include_router(linebot_router.line_router, prefix="/api/bot/line")
        client = TestClient(app)

        body = b'{"events":[]}'
        signature = generate_signature(body, TENANT_A_SECRET)

        # 直接 patch verify_webhook_signature 來模擬驗證成功
        with patch.object(linebot_router, "verify_webhook_signature", new_callable=AsyncMock) as mock_verify, \
             patch.object(linebot_router, "get_webhook_parser") as mock_parser:
            # 模擬簽章驗證成功，識別為租戶 A
            mock_verify.return_value = (True, TENANT_A_ID, TENANT_A_SECRET)

            # Mock parser 回傳空事件列表
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse.return_value = []
            mock_parser.return_value = mock_parser_instance

            response = client.post(
                "/api/bot/line/webhook",
                content=body,
                headers={"X-Line-Signature": signature},
            )

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            # 確認 verify_webhook_signature 被呼叫
            mock_verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_signature(self):
        """Webhook 應拒絕無效簽章"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ching_tech_os.api.linebot_router import line_router

        app = FastAPI()
        app.include_router(line_router, prefix="/api/bot/line")
        client = TestClient(app)

        body = b'{"events":[]}'
        invalid_signature = "invalid-signature"

        with patch.object(linebot_service, "get_cached_tenant_secrets", new_callable=AsyncMock) as mock_cache, \
             patch.object(linebot_service.settings, "line_channel_secret", DEFAULT_SECRET):
            mock_cache.return_value = []

            response = client.post(
                "/api/bot/line/webhook",
                content=body,
                headers={"X-Line-Signature": invalid_signature},
            )

            assert response.status_code == 400
            assert "Invalid signature" in response.json()["detail"]


# ============================================================
# get_messaging_api 多租戶測試
# ============================================================

class TestGetMessagingApi:
    """get_messaging_api 多租戶支援測試"""

    @pytest.mark.asyncio
    async def test_uses_tenant_token_when_specified(self):
        """指定租戶時應使用該租戶的 access token"""
        # Mock tenant credentials
        mock_credentials = {"access_token": "decrypted-tenant-token"}

        # 需要 patch tenant 模組中的函數（因為是 lazy import）
        with patch("ching_tech_os.services.tenant.get_tenant_line_credentials", new_callable=AsyncMock) as mock_get, \
             patch("ching_tech_os.services.linebot.get_line_config") as mock_config, \
             patch("ching_tech_os.services.linebot.AsyncApiClient") as mock_client, \
             patch("ching_tech_os.services.linebot.AsyncMessagingApi") as mock_api:

            mock_get.return_value = mock_credentials
            mock_config.return_value = MagicMock()

            await linebot_service.get_messaging_api(tenant_id=TENANT_A_ID)

            # 應呼叫 get_tenant_line_credentials
            mock_get.assert_called_once()
            # 應使用租戶的 token（位置參數）
            mock_config.assert_called_once_with("decrypted-tenant-token")

    @pytest.mark.asyncio
    async def test_uses_default_token_when_tenant_not_found(self):
        """找不到租戶設定時應使用預設 token"""
        with patch("ching_tech_os.services.tenant.get_tenant_line_credentials", new_callable=AsyncMock) as mock_get, \
             patch("ching_tech_os.services.linebot.get_line_config") as mock_config, \
             patch("ching_tech_os.services.linebot.AsyncApiClient") as mock_client, \
             patch("ching_tech_os.services.linebot.AsyncMessagingApi") as mock_api:

            mock_get.return_value = None  # 找不到租戶設定
            mock_config.return_value = MagicMock()

            await linebot_service.get_messaging_api(tenant_id=TENANT_A_ID)

            # 應使用預設 token（None）
            mock_config.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_uses_default_token_when_tenant_id_none(self):
        """未指定租戶時應使用預設 token"""
        with patch("ching_tech_os.services.linebot.get_line_config") as mock_config, \
             patch("ching_tech_os.services.linebot.AsyncApiClient") as mock_client, \
             patch("ching_tech_os.services.linebot.AsyncMessagingApi") as mock_api:

            mock_config.return_value = MagicMock()

            await linebot_service.get_messaging_api(tenant_id=None)

            # 應使用預設 token（None as positional arg）
            mock_config.assert_called_once_with(None)
