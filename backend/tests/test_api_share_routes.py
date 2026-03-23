"""測試 api/share.py 路由"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.share import router, public_router
from ching_tech_os.models.auth import SessionData


# ============================================
# 測試設置
# ============================================


def _create_test_app():
    """建立測試用 FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    app.include_router(public_router)
    return app


def _mock_session(role="user", username="testuser", user_id=1):
    return SessionData(
        session_id="test-session",
        user_id=user_id,
        username=username,
        role=role,
    )


# ============================================
# Public API 測試
# ============================================


class TestGetResource:
    def test_not_found(self):
        """token 不存在"""
        from ching_tech_os.services.share import ShareLinkNotFoundError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            side_effect=ShareLinkNotFoundError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/invalid-token")
            assert resp.status_code == 404

    def test_expired(self):
        """連結已過期"""
        from ching_tech_os.services.share import ShareLinkExpiredError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            side_effect=ShareLinkExpiredError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/expired-token")
            assert resp.status_code == 410

    def test_locked(self):
        """連結已鎖定"""
        from ching_tech_os.services.share import ShareLinkLockedError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            side_effect=ShareLinkLockedError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/locked-token")
            assert resp.status_code == 423

    def test_password_incorrect(self):
        """密碼錯誤"""
        from ching_tech_os.services.share import PasswordIncorrectError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            side_effect=PasswordIncorrectError("密碼錯誤"),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/pw-token?password=wrong")
            assert resp.status_code == 401

    def test_resource_not_found(self):
        """原始內容已刪除"""
        from ching_tech_os.services.share import ResourceNotFoundError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            side_effect=ResourceNotFoundError("已刪除"),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/deleted-token")
            assert resp.status_code == 404

    def test_share_error(self):
        """一般錯誤"""
        from ching_tech_os.services.share import ShareError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            side_effect=ShareError("意外錯誤"),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/error-token")
            assert resp.status_code == 500

    def test_success(self):
        """正常取得資源"""
        from datetime import datetime
        from ching_tech_os.models.share import PublicResourceResponse

        app = _create_test_app()

        mock_result = PublicResourceResponse(
            type="content",
            data={"title": "測試分享", "content": "分享內容"},
            shared_by="testuser",
            shared_at=datetime.now(),
            expires_at=None,
        )

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            client = TestClient(app)
            resp = client.get("/api/public/valid-token")
            assert resp.status_code == 200

    def test_password_required(self):
        """需要密碼"""
        from ching_tech_os.models.share import PasswordRequiredResponse

        app = _create_test_app()

        mock_result = PasswordRequiredResponse(
            requires_password=True,
            message="需要密碼",
        )

        with patch(
            "ching_tech_os.api.share.get_public_resource",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            client = TestClient(app)
            resp = client.get("/api/public/pw-token")
            assert resp.status_code == 401


# ============================================
# 公開附件 API 測試
# ============================================


class TestGetPublicAttachment:
    def test_not_found_token(self):
        """token 不存在"""
        from ching_tech_os.services.share import ShareLinkNotFoundError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            side_effect=ShareLinkNotFoundError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/bad/attachments/file.jpg")
            assert resp.status_code == 404

    def test_expired_token(self):
        """連結已過期"""
        from ching_tech_os.services.share import ShareLinkExpiredError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            side_effect=ShareLinkExpiredError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/expired/attachments/file.jpg")
            assert resp.status_code == 410

    def test_non_knowledge_type(self):
        """非知識庫類型"""
        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            return_value={"resource_type": "content", "resource_id": "123"},
        ):
            client = TestClient(app)
            resp = client.get("/api/public/token/attachments/file.jpg")
            assert resp.status_code == 400

    def test_path_traversal(self):
        """路徑穿越防護"""
        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            return_value={"resource_type": "knowledge", "resource_id": "kb1"},
        ):
            client = TestClient(app)
            # URL 含 .. 的路徑會被攔截
            resp = client.get("/api/public/token/attachments/test/../../../etc/passwd")
            assert resp.status_code in (400, 404)  # 可能 400 或 404


# ============================================
# 下載 API 測試
# ============================================


class TestDownloadSharedFile:
    def test_not_found(self):
        """token 不存在"""
        from ching_tech_os.services.share import ShareLinkNotFoundError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            side_effect=ShareLinkNotFoundError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/bad/download")
            assert resp.status_code == 404

    def test_expired(self):
        """連結已過期"""
        from ching_tech_os.services.share import ShareLinkExpiredError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            side_effect=ShareLinkExpiredError(),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/expired/download")
            assert resp.status_code == 410

    def test_non_file_type(self):
        """非檔案類型"""
        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            return_value={"resource_type": "content", "resource_id": "123"},
        ):
            client = TestClient(app)
            resp = client.get("/api/public/token/download")
            assert resp.status_code in (400, 500)  # HTTPException 或內部錯誤

    def test_nas_file_success(self, tmp_path):
        """NAS 檔案下載成功"""
        from pathlib import Path

        # 建立測試檔案
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            return_value={"resource_type": "nas_file", "resource_id": "/test.txt"},
        ):
            with patch(
                "ching_tech_os.api.share.validate_nas_file_path",
                return_value=test_file,
            ):
                client = TestClient(app)
                resp = client.get("/api/public/token/download")
                assert resp.status_code == 200
                assert resp.content == b"hello"

    def test_nas_file_not_found(self):
        """NAS 檔案不存在"""
        from ching_tech_os.services.share import NasFileNotFoundError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            return_value={"resource_type": "nas_file", "resource_id": "/missing.txt"},
        ):
            with patch(
                "ching_tech_os.api.share.validate_nas_file_path",
                side_effect=NasFileNotFoundError("找不到"),
            ):
                client = TestClient(app)
                resp = client.get("/api/public/token/download")
                assert resp.status_code == 404

    def test_nas_access_denied(self):
        """NAS 存取被拒"""
        from ching_tech_os.services.share import NasFileAccessDenied

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            return_value={"resource_type": "nas_file", "resource_id": "/secret.txt"},
        ):
            with patch(
                "ching_tech_os.api.share.validate_nas_file_path",
                side_effect=NasFileAccessDenied("拒絕"),
            ):
                client = TestClient(app)
                resp = client.get("/api/public/token/download")
                assert resp.status_code == 403
