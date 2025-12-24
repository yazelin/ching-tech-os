"""權限函數單元測試

測試 permissions.py 中的所有函數：
- is_admin()
- get_full_permissions()
- deep_merge()
- get_user_permissions()
- get_user_permissions_for_admin()
- check_app_permission()
- check_knowledge_permission()
"""

import pytest
from unittest.mock import patch

from ching_tech_os.services.permissions import (
    DEFAULT_APP_PERMISSIONS,
    DEFAULT_KNOWLEDGE_PERMISSIONS,
    DEFAULT_PERMISSIONS,
    is_admin,
    get_full_permissions,
    deep_merge,
    get_user_permissions,
    get_user_permissions_for_admin,
    check_app_permission,
    check_knowledge_permission,
    get_default_permissions,
    get_app_display_names,
)


# ============================================================
# is_admin() 測試
# ============================================================

class TestIsAdmin:
    """is_admin() 函數測試"""

    def test_admin_username_matches(self):
        """管理員帳號應返回 True"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert is_admin("admin") is True

    def test_non_admin_username(self):
        """非管理員帳號應返回 False"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert is_admin("user1") is False
            assert is_admin("test") is False
            assert is_admin("") is False

    def test_case_sensitive(self):
        """帳號比較應區分大小寫"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "Admin"
            assert is_admin("Admin") is True
            assert is_admin("admin") is False
            assert is_admin("ADMIN") is False


# ============================================================
# get_full_permissions() 測試
# ============================================================

class TestGetFullPermissions:
    """get_full_permissions() 函數測試"""

    def test_all_apps_enabled(self):
        """所有應用程式權限應為 True"""
        perms = get_full_permissions()
        for app_id in DEFAULT_APP_PERMISSIONS:
            assert perms["apps"][app_id] is True

    def test_all_knowledge_perms_enabled(self):
        """所有知識庫權限應為 True"""
        perms = get_full_permissions()
        assert perms["knowledge"]["global_write"] is True
        assert perms["knowledge"]["global_delete"] is True

    def test_returns_new_dict(self):
        """應返回新的 dict（不是引用）"""
        perms1 = get_full_permissions()
        perms2 = get_full_permissions()
        assert perms1 is not perms2
        perms1["apps"]["terminal"] = False
        assert perms2["apps"]["terminal"] is True


# ============================================================
# deep_merge() 測試
# ============================================================

class TestDeepMerge:
    """deep_merge() 函數測試"""

    def test_simple_merge(self):
        """簡單合併"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """巢狀合併"""
        base = {"apps": {"terminal": False, "settings": True}}
        override = {"apps": {"terminal": True}}
        result = deep_merge(base, override)
        assert result["apps"]["terminal"] is True
        assert result["apps"]["settings"] is True

    def test_override_adds_new_keys(self):
        """覆蓋可以新增鍵"""
        base = {"apps": {"terminal": False}}
        override = {"apps": {"code-editor": True}, "knowledge": {"global_write": True}}
        result = deep_merge(base, override)
        assert result["apps"]["terminal"] is False
        assert result["apps"]["code-editor"] is True
        assert result["knowledge"]["global_write"] is True

    def test_base_not_modified(self):
        """base 不應被修改"""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"c": 3}}
        deep_merge(base, override)
        assert base["b"]["c"] == 2


# ============================================================
# get_user_permissions() 測試
# ============================================================

class TestGetUserPermissions:
    """get_user_permissions() 函數測試"""

    def test_none_preferences_returns_default(self):
        """None 參數應返回預設權限"""
        perms = get_user_permissions(None)
        assert perms["apps"]["terminal"] is False  # 預設關閉
        assert perms["apps"]["file-manager"] is True  # 預設開放

    def test_empty_preferences_returns_default(self):
        """空 dict 應返回預設權限"""
        perms = get_user_permissions({})
        assert perms["apps"]["terminal"] is False

    def test_custom_permissions_override(self):
        """自訂權限應覆蓋預設值"""
        preferences = {
            "permissions": {
                "apps": {"terminal": True}
            }
        }
        perms = get_user_permissions(preferences)
        assert perms["apps"]["terminal"] is True
        assert perms["apps"]["code-editor"] is False  # 其他保持預設

    def test_partial_override(self):
        """部分覆蓋"""
        preferences = {
            "permissions": {
                "knowledge": {"global_write": True}
            }
        }
        perms = get_user_permissions(preferences)
        # apps 應保持預設
        assert perms["apps"]["terminal"] is False
        # knowledge 應被覆蓋
        assert perms["knowledge"]["global_write"] is True
        assert perms["knowledge"]["global_delete"] is False


# ============================================================
# get_user_permissions_for_admin() 測試
# ============================================================

class TestGetUserPermissionsForAdmin:
    """get_user_permissions_for_admin() 函數測試"""

    def test_admin_gets_full_permissions(self):
        """管理員應取得完整權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            perms = get_user_permissions_for_admin("admin", None)
            assert perms["apps"]["terminal"] is True
            assert perms["apps"]["code-editor"] is True
            assert perms["knowledge"]["global_write"] is True
            assert perms["knowledge"]["global_delete"] is True

    def test_non_admin_gets_merged_permissions(self):
        """非管理員應取得合併後的權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            preferences = {"permissions": {"apps": {"terminal": True}}}
            perms = get_user_permissions_for_admin("user1", preferences)
            assert perms["apps"]["terminal"] is True
            assert perms["apps"]["code-editor"] is False  # 預設關閉

    def test_non_admin_with_none_preferences(self):
        """非管理員且無 preferences 應取得預設權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            perms = get_user_permissions_for_admin("user1", None)
            assert perms["apps"]["terminal"] is False
            assert perms["knowledge"]["global_write"] is False


# ============================================================
# check_app_permission() 測試
# ============================================================

class TestCheckAppPermission:
    """check_app_permission() 函數測試"""

    def test_admin_has_all_permissions(self):
        """管理員應有所有應用程式權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_app_permission("admin", None, "terminal") is True
            assert check_app_permission("admin", None, "code-editor") is True
            assert check_app_permission("admin", None, "settings") is True

    def test_user_default_closed_app(self):
        """一般使用者應無法存取預設關閉的應用程式"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_app_permission("user1", None, "terminal") is False
            assert check_app_permission("user1", None, "code-editor") is False

    def test_user_default_open_app(self):
        """一般使用者應可存取預設開放的應用程式"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_app_permission("user1", None, "file-manager") is True
            assert check_app_permission("user1", None, "settings") is True

    def test_user_with_custom_permission(self):
        """使用者自訂權限應生效"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            preferences = {"permissions": {"apps": {"terminal": True}}}
            assert check_app_permission("user1", preferences, "terminal") is True

    def test_unknown_app_defaults_to_true(self):
        """未知應用程式預設應允許"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_app_permission("user1", None, "unknown-app") is True


# ============================================================
# check_knowledge_permission() 測試
# ============================================================

class TestCheckKnowledgePermission:
    """check_knowledge_permission() 函數測試"""

    def test_admin_has_all_permissions(self):
        """管理員應有所有知識庫權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            # 全域知識
            assert check_knowledge_permission("admin", None, None, "global", "read") is True
            assert check_knowledge_permission("admin", None, None, "global", "write") is True
            assert check_knowledge_permission("admin", None, None, "global", "delete") is True
            # 個人知識
            assert check_knowledge_permission("admin", None, "user1", "personal", "read") is True
            assert check_knowledge_permission("admin", None, "user1", "personal", "write") is True
            assert check_knowledge_permission("admin", None, "user1", "personal", "delete") is True

    def test_personal_knowledge_owner_has_full_control(self):
        """個人知識擁有者應有完全控制權"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_knowledge_permission("user1", None, "user1", "personal", "read") is True
            assert check_knowledge_permission("user1", None, "user1", "personal", "write") is True
            assert check_knowledge_permission("user1", None, "user1", "personal", "delete") is True

    def test_personal_knowledge_non_owner_denied(self):
        """非擁有者應無法存取他人的個人知識"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_knowledge_permission("user2", None, "user1", "personal", "read") is False
            assert check_knowledge_permission("user2", None, "user1", "personal", "write") is False
            assert check_knowledge_permission("user2", None, "user1", "personal", "delete") is False

    def test_global_knowledge_read_allowed_for_all(self):
        """全域知識所有人可讀"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            assert check_knowledge_permission("user1", None, None, "global", "read") is True
            assert check_knowledge_permission("user2", None, None, "global", "read") is True

    def test_global_knowledge_write_requires_permission(self):
        """全域知識寫入需要權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            # 無權限
            assert check_knowledge_permission("user1", None, None, "global", "write") is False
            # 有權限
            preferences = {"permissions": {"knowledge": {"global_write": True}}}
            assert check_knowledge_permission("user1", preferences, None, "global", "write") is True

    def test_global_knowledge_delete_requires_permission(self):
        """全域知識刪除需要權限"""
        with patch("ching_tech_os.services.permissions.settings") as mock_settings:
            mock_settings.admin_username = "admin"
            # 無權限
            assert check_knowledge_permission("user1", None, None, "global", "delete") is False
            # 有權限
            preferences = {"permissions": {"knowledge": {"global_delete": True}}}
            assert check_knowledge_permission("user1", preferences, None, "global", "delete") is True


# ============================================================
# 輔助函數測試
# ============================================================

class TestHelperFunctions:
    """輔助函數測試"""

    def test_get_default_permissions(self):
        """get_default_permissions() 應返回預設權限副本"""
        perms = get_default_permissions()
        assert perms == DEFAULT_PERMISSIONS
        # 確認是副本
        perms["apps"]["terminal"] = True
        assert DEFAULT_PERMISSIONS["apps"]["terminal"] is False

    def test_get_app_display_names(self):
        """get_app_display_names() 應返回應用程式名稱"""
        names = get_app_display_names()
        assert names["terminal"] == "終端機"
        assert names["file-manager"] == "檔案管理"
        assert len(names) == len(DEFAULT_APP_PERMISSIONS)
