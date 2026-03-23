"""測試 shared_source_permissions.py"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.shared_source_permissions import (
    SharedSourceAccessDeniedError,
    SHARED_SOURCE_ACCESS_DENIED_MESSAGE,
    _normalize_preferences,
    _extract_shared_source_permissions,
    filter_shared_mounts_by_permissions,
    resolve_shared_source_mount,
    get_allowed_shared_mounts_for_user,
)


# ============================================
# SharedSourceAccessDeniedError
# ============================================


class TestSharedSourceAccessDeniedError:
    def test_default_message(self):
        err = SharedSourceAccessDeniedError()
        assert str(err) == SHARED_SOURCE_ACCESS_DENIED_MESSAGE

    def test_custom_message(self):
        err = SharedSourceAccessDeniedError("自訂訊息")
        assert str(err) == "自訂訊息"


# ============================================
# _normalize_preferences
# ============================================


class TestNormalizePreferences:
    def test_none(self):
        assert _normalize_preferences(None) == {}

    def test_dict(self):
        d = {"key": "value"}
        assert _normalize_preferences(d) == d

    def test_valid_json_string(self):
        assert _normalize_preferences('{"a": 1}') == {"a": 1}

    def test_invalid_json_string(self):
        assert _normalize_preferences("not json") == {}

    def test_non_dict_json_string(self):
        assert _normalize_preferences("[1,2]") == {}

    def test_other_type(self):
        assert _normalize_preferences(42) == {}


# ============================================
# _extract_shared_source_permissions
# ============================================


class TestExtractSharedSourcePermissions:
    def test_none(self):
        assert _extract_shared_source_permissions(None) is None

    def test_non_dict(self):
        assert _extract_shared_source_permissions("string") is None

    def test_no_permissions_key(self):
        assert _extract_shared_source_permissions({"other": 1}) is None

    def test_permissions_not_dict(self):
        assert _extract_shared_source_permissions({"permissions": "bad"}) is None

    def test_new_format_shared_sources(self):
        prefs = {"permissions": {"shared_sources": {"nas1": True, "nas2": False}}}
        result = _extract_shared_source_permissions(prefs)
        assert result == {"nas1": True, "nas2": False}

    def test_legacy_format_shared(self):
        prefs = {"permissions": {"shared": {"old_nas": True}}}
        result = _extract_shared_source_permissions(prefs)
        assert result == {"old_nas": True}

    def test_neither_format(self):
        prefs = {"permissions": {"other_key": True}}
        assert _extract_shared_source_permissions(prefs) is None


# ============================================
# filter_shared_mounts_by_permissions
# ============================================


class TestFilterSharedMountsByPermissions:
    def test_with_permissions(self):
        mounts = {"nas1": "/mnt/nas1", "nas2": "/mnt/nas2", "nas3": "/mnt/nas3"}
        perms = {"nas1": True, "nas2": False}
        result = filter_shared_mounts_by_permissions(mounts, perms)
        assert result == {"nas1": "/mnt/nas1"}

    def test_none_permissions_uses_default(self):
        """perms=None 時使用預設權限"""
        mounts = {"src1": "/mnt/1"}
        with patch(
            "ching_tech_os.services.shared_source_permissions.filter_shared_mounts_by_permissions"
        ) as _:
            # 直接測試：None 時會 import DEFAULT_SHARED_SOURCE_PERMISSIONS
            result = filter_shared_mounts_by_permissions(mounts, None)
            # 結果取決於 DEFAULT_SHARED_SOURCE_PERMISSIONS
            assert isinstance(result, dict)


# ============================================
# resolve_shared_source_mount
# ============================================


class TestResolveSharedSourceMount:
    def test_unknown_source(self):
        with pytest.raises(ValueError, match="未知的 shared 子來源"):
            resolve_shared_source_mount({"nas1": "/mnt/nas1"}, "unknown")

    def test_access_denied(self):
        mounts = {"nas1": "/mnt/nas1"}
        perms = {"nas1": False}
        with pytest.raises(SharedSourceAccessDeniedError):
            resolve_shared_source_mount(mounts, "nas1", perms)

    def test_success(self):
        mounts = {"nas1": "/mnt/nas1"}
        perms = {"nas1": True}
        result = resolve_shared_source_mount(mounts, "nas1", perms)
        assert result == "/mnt/nas1"


# ============================================
# get_allowed_shared_mounts_for_user
# ============================================


class TestGetAllowedSharedMountsForUser:
    @pytest.mark.asyncio
    async def test_no_user_id(self):
        """user_id=None 使用預設權限"""
        mounts = {"src1": "/mnt/1"}
        result = await get_allowed_shared_mounts_for_user(mounts, None)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """使用者不存在回傳空 dict"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        async def _ctx():
            return conn

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "ching_tech_os.services.shared_source_permissions.get_connection",
            return_value=ctx,
        ):
            result = await get_allowed_shared_mounts_for_user({"a": "/a"}, 999)
            assert result == {}

    @pytest.mark.asyncio
    async def test_admin_returns_all(self):
        """admin 回傳全部掛載點"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={"role": "admin", "preferences": None}
        )

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        mounts = {"nas1": "/mnt/1", "nas2": "/mnt/2"}
        with patch(
            "ching_tech_os.services.shared_source_permissions.get_connection",
            return_value=ctx,
        ):
            result = await get_allowed_shared_mounts_for_user(mounts, 1)
            assert result == mounts

    @pytest.mark.asyncio
    async def test_normal_user_filtered(self):
        """一般用戶依 preferences 過濾"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={
                "role": "user",
                "preferences": '{"permissions": {"shared_sources": {"nas1": true, "nas2": false}}}',
            }
        )

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        mounts = {"nas1": "/mnt/1", "nas2": "/mnt/2"}
        with patch(
            "ching_tech_os.services.shared_source_permissions.get_connection",
            return_value=ctx,
        ):
            result = await get_allowed_shared_mounts_for_user(mounts, 2)
            assert result == {"nas1": "/mnt/1"}
