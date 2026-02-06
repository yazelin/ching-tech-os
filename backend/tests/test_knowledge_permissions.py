"""知識庫權限檢查測試

測試：
- 建立全域知識需要 global_write 權限
- 編輯/刪除權限檢查
- 個人知識只有擁有者可操作

"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.knowledge import router
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.auth import SessionData


# 建立測試用 FastAPI 應用程式
def create_test_app():
    app = FastAPI()
    app.include_router(router)
    return app


def create_session_override(username: str, user_id: int = 1):
    """建立 session 覆寫函數"""
    async def override():
        now = datetime.now()
        return SessionData(
            username=username,
            password="test-password",
            nas_host="test-nas",
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
    return override


# 模擬知識資料（使用 dict 而非 MagicMock 以匹配 Pydantic 模型）
def create_mock_knowledge(kb_id: str, scope: str, owner: str | None):
    """建立模擬知識物件"""
    mock = MagicMock()
    mock.id = kb_id
    mock.title = f"知識 {kb_id}"
    mock.content = "內容"
    mock.scope = scope
    mock.owner = owner
    mock.author = owner or "admin"
    mock.type = "knowledge"
    mock.category = "technical"
    mock.slug = kb_id
    mock.updated_at = "2024-01-01T00:00:00"
    mock.attachments = []
    # 建立 tags mock
    mock.tags = MagicMock()
    mock.tags.projects = []
    mock.tags.roles = []
    mock.tags.topics = []
    mock.tags.level = "beginner"
    return mock


# ============================================================
# 知識庫建立權限測試
# ============================================================

class TestKnowledgeCreatePermissions:
    """知識庫建立權限測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def test_user_without_permission_cannot_create_global_knowledge(self):
        """沒有權限的使用者無法建立全域知識"""
        with patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=False):

            mock_prefs.return_value = {}

            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.post(
                "/api/knowledge",
                json={
                    "title": "全域知識",
                    "content": "內容",
                    "scope": "global",
                }
            )
            assert response.status_code == 403
            assert "沒有建立全域知識的權限" in response.json()["detail"]


# ============================================================
# 知識庫更新權限測試
# ============================================================

class TestKnowledgeUpdatePermissions:
    """知識庫更新權限測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def test_non_owner_cannot_update_personal_knowledge(self):
        """非擁有者無法更新他人的個人知識"""
        mock_kb = create_mock_knowledge("kb-002", "personal", "user1")

        with patch("ching_tech_os.api.knowledge.get_knowledge") as mock_get, \
             patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=False):

            mock_get.return_value = mock_kb
            mock_prefs.return_value = {}

            self.app.dependency_overrides[get_current_session] = create_session_override("user2", 3)
            client = TestClient(self.app)

            response = client.put(
                "/api/knowledge/kb-002",
                json={"title": "更新的標題"}
            )
            assert response.status_code == 403
            assert "沒有編輯此知識的權限" in response.json()["detail"]

    def test_user_without_permission_cannot_update_global_knowledge(self):
        """沒有權限的使用者無法更新全域知識"""
        mock_kb = create_mock_knowledge("kb-001", "global", None)

        with patch("ching_tech_os.api.knowledge.get_knowledge") as mock_get, \
             patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=False):

            mock_get.return_value = mock_kb
            mock_prefs.return_value = {}

            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.put(
                "/api/knowledge/kb-001",
                json={"title": "更新的標題"}
            )
            assert response.status_code == 403


# ============================================================
# 知識庫刪除權限測試
# ============================================================

class TestKnowledgeDeletePermissions:
    """知識庫刪除權限測試"""

    def setup_method(self):
        """設置測試環境"""
        self.app = create_test_app()

    def test_owner_can_delete_personal_knowledge(self):
        """擁有者可以刪除自己的個人知識"""
        mock_kb = create_mock_knowledge("kb-002", "personal", "user1")

        with patch("ching_tech_os.api.knowledge.get_knowledge") as mock_get, \
             patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=True), \
             patch("ching_tech_os.api.knowledge.delete_knowledge") as mock_delete, \
             patch("ching_tech_os.api.knowledge.log_message", new_callable=AsyncMock):

            mock_get.return_value = mock_kb
            mock_prefs.return_value = {}

            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.delete("/api/knowledge/kb-002")
            assert response.status_code == 204

    def test_non_owner_cannot_delete_personal_knowledge(self):
        """非擁有者無法刪除他人的個人知識"""
        mock_kb = create_mock_knowledge("kb-002", "personal", "user1")

        with patch("ching_tech_os.api.knowledge.get_knowledge") as mock_get, \
             patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=False):

            mock_get.return_value = mock_kb
            mock_prefs.return_value = {}

            self.app.dependency_overrides[get_current_session] = create_session_override("user2", 3)
            client = TestClient(self.app)

            response = client.delete("/api/knowledge/kb-002")
            assert response.status_code == 403
            assert "沒有刪除此知識的權限" in response.json()["detail"]

    def test_user_without_permission_cannot_delete_global_knowledge(self):
        """沒有權限的使用者無法刪除全域知識"""
        mock_kb = create_mock_knowledge("kb-001", "global", None)

        with patch("ching_tech_os.api.knowledge.get_knowledge") as mock_get, \
             patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=False):

            mock_get.return_value = mock_kb
            mock_prefs.return_value = {}

            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.delete("/api/knowledge/kb-001")
            assert response.status_code == 403

    def test_user_with_permission_can_delete_global_knowledge(self):
        """有權限的使用者可以刪除全域知識"""
        mock_kb = create_mock_knowledge("kb-001", "global", None)

        with patch("ching_tech_os.api.knowledge.get_knowledge") as mock_get, \
             patch("ching_tech_os.api.knowledge.get_user_preferences", new_callable=AsyncMock) as mock_prefs, \
             patch("ching_tech_os.api.knowledge.check_knowledge_permission_async", new_callable=AsyncMock, return_value=True), \
             patch("ching_tech_os.api.knowledge.delete_knowledge") as mock_delete, \
             patch("ching_tech_os.api.knowledge.log_message", new_callable=AsyncMock):

            mock_get.return_value = mock_kb
            mock_prefs.return_value = {"permissions": {"knowledge": {"global_delete": True}}}

            self.app.dependency_overrides[get_current_session] = create_session_override("user1", 2)
            client = TestClient(self.app)

            response = client.delete("/api/knowledge/kb-001")
            assert response.status_code == 204
