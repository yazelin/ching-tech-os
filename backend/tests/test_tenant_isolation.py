"""租戶隔離單元測試

測試多租戶資料隔離功能：
- 租戶解析
- 租戶資料 CRUD
- 租戶管理員權限

注意：多租戶功能已移除，這些測試暫時跳過
"""

import pytest

pytestmark = pytest.mark.skip(reason="多租戶功能已移除，測試待刪除或重構")
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from ching_tech_os.services.tenant import (
    get_tenant_by_code,
    get_tenant_by_id,
    resolve_tenant_id,
    create_tenant,
    update_tenant,
    list_tenants,
    get_tenant_usage,
    add_tenant_admin,
    remove_tenant_admin,
    list_tenant_admins,
    is_tenant_admin,
    TenantNotFoundError,
    TenantCodeExistsError,
    TenantSuspendedError,
)
from ching_tech_os.models.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantSettings,
    TenantAdminCreate,
)
from ching_tech_os.config import DEFAULT_TENANT_UUID


# 模擬租戶資料
MOCK_TENANT_1 = {
    "id": UUID("11111111-1111-1111-1111-111111111111"),
    "code": "tenant1",
    "name": "測試租戶 1",
    "status": "active",
    "plan": "basic",
    "settings": "{}",
    "storage_quota_mb": 1000,
    "storage_used_mb": 100,
    "trial_ends_at": None,
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
}

MOCK_TENANT_2 = {
    "id": UUID("22222222-2222-2222-2222-222222222222"),
    "code": "tenant2",
    "name": "測試租戶 2",
    "status": "suspended",
    "plan": "professional",
    "settings": "{}",
    "storage_quota_mb": 5000,
    "storage_used_mb": 500,
    "trial_ends_at": None,
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
}

MOCK_DEFAULT_TENANT = {
    "id": UUID(DEFAULT_TENANT_UUID),
    "code": "default",
    "name": "預設租戶",
    "status": "active",
    "plan": "enterprise",
    "settings": "{}",
    "storage_quota_mb": 10000,
    "storage_used_mb": 0,
    "trial_ends_at": None,
    "created_at": datetime.now(),
    "updated_at": datetime.now(),
}


# ============================================================
# resolve_tenant_id() 測試
# ============================================================

class TestResolveTenantId:
    """租戶 ID 解析測試"""

    @pytest.mark.asyncio
    async def test_single_tenant_mode_returns_default(self):
        """單租戶模式應返回預設租戶 ID"""
        with patch("ching_tech_os.services.tenant.settings") as mock_settings:
            mock_settings.multi_tenant_mode = False
            mock_settings.default_tenant_id = DEFAULT_TENANT_UUID

            result = await resolve_tenant_id("any_code")
            assert result == UUID(DEFAULT_TENANT_UUID)

    @pytest.mark.asyncio
    async def test_multi_tenant_mode_without_code_returns_default(self):
        """多租戶模式未提供 code 應返回預設租戶"""
        with patch("ching_tech_os.services.tenant.settings") as mock_settings:
            mock_settings.multi_tenant_mode = True
            mock_settings.default_tenant_id = DEFAULT_TENANT_UUID

            result = await resolve_tenant_id(None)
            assert result == UUID(DEFAULT_TENANT_UUID)

    @pytest.mark.asyncio
    async def test_multi_tenant_mode_with_valid_code(self):
        """多租戶模式提供有效 code 應返回對應租戶"""
        with patch("ching_tech_os.services.tenant.settings") as mock_settings, \
             patch("ching_tech_os.services.tenant.get_tenant_by_code", new_callable=AsyncMock) as mock_get:
            mock_settings.multi_tenant_mode = True
            mock_get.return_value = MOCK_TENANT_1

            result = await resolve_tenant_id("tenant1")
            assert result == MOCK_TENANT_1["id"]
            mock_get.assert_called_once_with("tenant1")

    @pytest.mark.asyncio
    async def test_multi_tenant_mode_with_invalid_code(self):
        """多租戶模式提供無效 code 應拋出 TenantNotFoundError"""
        with patch("ching_tech_os.services.tenant.settings") as mock_settings, \
             patch("ching_tech_os.services.tenant.get_tenant_by_code", new_callable=AsyncMock) as mock_get:
            mock_settings.multi_tenant_mode = True
            mock_get.return_value = None

            with pytest.raises(TenantNotFoundError) as exc_info:
                await resolve_tenant_id("invalid_code")
            assert "invalid_code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_suspended_tenant_raises_error(self):
        """停用的租戶應拋出 TenantSuspendedError"""
        with patch("ching_tech_os.services.tenant.settings") as mock_settings, \
             patch("ching_tech_os.services.tenant.get_tenant_by_code", new_callable=AsyncMock) as mock_get:
            mock_settings.multi_tenant_mode = True
            mock_get.return_value = MOCK_TENANT_2  # status = suspended

            with pytest.raises(TenantSuspendedError) as exc_info:
                await resolve_tenant_id("tenant2")
            assert "tenant2" in str(exc_info.value)


# ============================================================
# get_tenant_by_code() 測試
# ============================================================

class TestGetTenantByCode:
    """根據代碼取得租戶測試"""

    @pytest.mark.asyncio
    async def test_existing_code_returns_tenant(self):
        """存在的代碼應返回租戶資料"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = MOCK_TENANT_1

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_tenant_by_code("tenant1")
            assert result == dict(MOCK_TENANT_1)
            mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_nonexistent_code_returns_none(self):
        """不存在的代碼應返回 None"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_tenant_by_code("nonexistent")
            assert result is None


# ============================================================
# get_tenant_by_id() 測試
# ============================================================

class TestGetTenantById:
    """根據 ID 取得租戶測試"""

    @pytest.mark.asyncio
    async def test_existing_id_returns_tenant(self):
        """存在的 ID 應返回租戶資料"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = MOCK_TENANT_1

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_tenant_by_id(MOCK_TENANT_1["id"])
            assert result == dict(MOCK_TENANT_1)

    @pytest.mark.asyncio
    async def test_string_id_converted_to_uuid(self):
        """字串 ID 應被轉換為 UUID"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = MOCK_TENANT_1

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_tenant_by_id("11111111-1111-1111-1111-111111111111")
            assert result == dict(MOCK_TENANT_1)

    @pytest.mark.asyncio
    async def test_nonexistent_id_returns_none(self):
        """不存在的 ID 應返回 None"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await get_tenant_by_id(UUID("99999999-9999-9999-9999-999999999999"))
            assert result is None


# ============================================================
# create_tenant() 測試
# ============================================================

class TestCreateTenant:
    """建立租戶測試"""

    @pytest.mark.asyncio
    async def test_create_tenant_success(self):
        """成功建立租戶"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [
            None,  # 檢查代碼不存在
            MOCK_TENANT_1,  # 返回新建立的租戶
        ]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantCreate(
                code="tenant1",
                name="測試租戶 1",
                plan="basic",
            )
            result = await create_tenant(data)

            assert result.code == "tenant1"
            assert result.name == "測試租戶 1"

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_code_raises_error(self):
        """重複的代碼應拋出 TenantCodeExistsError"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"id": "existing"}  # 代碼已存在

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantCreate(
                code="tenant1",
                name="測試租戶",
                plan="basic",
            )

            with pytest.raises(TenantCodeExistsError) as exc_info:
                await create_tenant(data)
            assert "tenant1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_tenant_with_trial_days(self):
        """建立試用租戶應設定試用結束時間"""
        mock_conn = AsyncMock()
        trial_end = datetime.now() + timedelta(days=30)
        mock_tenant = {
            **MOCK_TENANT_1,
            "status": "trial",
            "trial_ends_at": trial_end,
        }
        mock_conn.fetchrow.side_effect = [
            None,  # 代碼不存在
            mock_tenant,
        ]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantCreate(
                code="trial_tenant",
                name="試用租戶",
                plan="basic",
                trial_days=30,
            )
            result = await create_tenant(data)
            assert result.status == "trial"


# ============================================================
# update_tenant() 測試
# ============================================================

class TestUpdateTenant:
    """更新租戶測試"""

    @pytest.mark.asyncio
    async def test_update_tenant_name(self):
        """更新租戶名稱"""
        updated_tenant = {**MOCK_TENANT_1, "name": "新名稱"}
        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [
            MOCK_TENANT_1,  # 取得現有資料
            updated_tenant,  # 更新後的資料
        ]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantUpdate(name="新名稱")
            result = await update_tenant(MOCK_TENANT_1["id"], data)
            assert result.name == "新名稱"

    @pytest.mark.asyncio
    async def test_update_nonexistent_tenant_raises_error(self):
        """更新不存在的租戶應拋出錯誤"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantUpdate(name="新名稱")

            with pytest.raises(TenantNotFoundError):
                await update_tenant(UUID("99999999-9999-9999-9999-999999999999"), data)

    @pytest.mark.asyncio
    async def test_update_with_no_changes(self):
        """沒有變更時應返回現有資料"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = MOCK_TENANT_1

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantUpdate()  # 沒有任何欄位
            result = await update_tenant(MOCK_TENANT_1["id"], data)
            assert result.code == MOCK_TENANT_1["code"]


# ============================================================
# 租戶管理員測試
# ============================================================

class TestTenantAdmin:
    """租戶管理員功能測試"""

    @pytest.mark.asyncio
    async def test_add_tenant_admin_success(self):
        """成功新增租戶管理員"""
        mock_user = {
            "id": 1,
            "username": "admin_user",
            "display_name": "管理員",
        }
        mock_admin_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        mock_admin = {
            "id": mock_admin_id,
            "tenant_id": MOCK_TENANT_1["id"],
            "user_id": 1,
            "role": "admin",
            "created_at": datetime.now(),
        }
        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [
            mock_user,  # 使用者存在
            None,  # 尚未是管理員
            mock_admin,  # 新增結果
        ]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantAdminCreate(user_id=1, role="admin")
            result = await add_tenant_admin(MOCK_TENANT_1["id"], data)

            # result 是 TenantAdminCreateResponse
            assert result.success is True
            assert result.admin is not None
            assert result.admin.user_id == 1
            assert result.admin.role == "admin"
            assert result.admin.id == mock_admin_id

    @pytest.mark.asyncio
    async def test_add_admin_user_not_found(self):
        """使用者不存在應拋出錯誤"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # 使用者不存在

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantAdminCreate(user_id=999, role="admin")

            with pytest.raises(ValueError) as exc_info:
                await add_tenant_admin(MOCK_TENANT_1["id"], data)
            assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_admin_already_exists(self):
        """已是管理員應拋出錯誤"""
        mock_user = {"id": 1, "username": "admin", "display_name": "管理員"}
        mock_existing = {"id": 1}  # 已存在

        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = [mock_user, mock_existing]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            data = TenantAdminCreate(user_id=1, role="admin")

            with pytest.raises(ValueError) as exc_info:
                await add_tenant_admin(MOCK_TENANT_1["id"], data)
            assert "已是" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_remove_tenant_admin_success(self):
        """成功移除租戶管理員"""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "DELETE 1"

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await remove_tenant_admin(MOCK_TENANT_1["id"], 1)
            assert result is True

    @pytest.mark.asyncio
    async def test_remove_tenant_admin_not_found(self):
        """移除不存在的管理員應返回 False"""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "DELETE 0"

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await remove_tenant_admin(MOCK_TENANT_1["id"], 999)
            assert result is False

    @pytest.mark.asyncio
    async def test_is_tenant_admin_true(self):
        """使用者是管理員應返回 True"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"id": 1}

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await is_tenant_admin(MOCK_TENANT_1["id"], 1)
            assert result is True

    @pytest.mark.asyncio
    async def test_is_tenant_admin_false(self):
        """使用者不是管理員應返回 False"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            result = await is_tenant_admin(MOCK_TENANT_1["id"], 999)
            assert result is False


# ============================================================
# get_tenant_usage() 測試
# ============================================================

class TestGetTenantUsage:
    """租戶使用量統計測試"""

    @pytest.mark.asyncio
    async def test_get_usage_success(self):
        """成功取得租戶使用量"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "storage_quota_mb": 1000,
            "storage_used_mb": 100,
        }
        mock_conn.fetchval.side_effect = [5, 10, 50, 200]  # users, projects, ai_today, ai_month

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant.calculate_tenant_storage", new_callable=AsyncMock) as mock_storage:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            mock_storage.return_value = 100

            result = await get_tenant_usage(MOCK_TENANT_1["id"])

            assert result.storage_used_mb == 100
            assert result.storage_quota_mb == 1000
            assert result.storage_percentage == 10.0
            assert result.user_count == 5
            assert result.project_count == 10
            assert result.ai_calls_today == 50
            assert result.ai_calls_this_month == 200

    @pytest.mark.asyncio
    async def test_get_usage_tenant_not_found(self):
        """租戶不存在應拋出錯誤"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn, \
             patch("ching_tech_os.services.tenant.calculate_tenant_storage", new_callable=AsyncMock):
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            with pytest.raises(TenantNotFoundError):
                await get_tenant_usage(UUID("99999999-9999-9999-9999-999999999999"))


# ============================================================
# 租戶列表測試
# ============================================================

class TestListTenants:
    """租戶列表功能測試"""

    @pytest.mark.asyncio
    async def test_list_all_tenants(self):
        """列出所有租戶"""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 2
        mock_conn.fetch.return_value = [MOCK_TENANT_1, MOCK_TENANT_2]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            tenants, total = await list_tenants()

            assert total == 2
            assert len(tenants) == 2

    @pytest.mark.asyncio
    async def test_list_tenants_with_filter(self):
        """根據條件篩選租戶"""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1
        mock_conn.fetch.return_value = [MOCK_TENANT_1]

        with patch("ching_tech_os.services.tenant.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn

            tenants, total = await list_tenants(status="active", plan="basic")

            assert total == 1
            assert len(tenants) == 1
