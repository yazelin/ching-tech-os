"""測試 api/share.py 路由（補充覆蓋：需登入 API 與公開附件分支）"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.auth import get_current_session
from ching_tech_os.api.share import router, public_router
from ching_tech_os.config import settings
from ching_tech_os.models.auth import SessionData
from ching_tech_os.models.share import ShareLinkResponse, ShareLinkListResponse


# ============================================
# 測試設置
# ============================================


def _create_test_app(session=None):
    """建立測試用 FastAPI app（可注入假 session）"""
    app = FastAPI()
    app.include_router(router)
    app.include_router(public_router)
    if session is not None:
        app.dependency_overrides[get_current_session] = lambda: session
    return app


def _mock_session(role="user", username="testuser", user_id=1):
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    return SessionData(
        username=username,
        password="test-password",
        nas_host="127.0.0.1",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
    )


def _link_response(**kwargs):
    """建立假的 ShareLinkResponse"""
    base = dict(
        token="abc123",
        url="/s/abc123",
        full_url="https://example.com/s/abc123",
        resource_type="content",
        resource_id="",
        resource_title="分享內容",
        expires_at=None,
        access_count=0,
        created_at=datetime.now(timezone.utc),
        is_expired=False,
    )
    base.update(kwargs)
    return ShareLinkResponse(**base)


# ============================================
# 建立分享連結 API 測試
# ============================================


class TestCreateLink:
    def test_content_without_content(self):
        """content 類型缺少 content 參數 -> 400"""
        app = _create_test_app(_mock_session())
        client = TestClient(app)
        resp = client.post("/api/share", json={"resource_type": "content"})
        assert resp.status_code == 400

    def test_content_success(self):
        """content 類型建立成功 -> 201"""
        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.create_share_link",
            new_callable=AsyncMock,
            return_value=_link_response(),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "content", "content": "哈囉", "filename": "a.txt"},
            )
            assert resp.status_code == 201
            assert resp.json()["token"] == "abc123"

    def test_knowledge_no_permission(self):
        """知識庫類型無分享權限 -> 403"""
        app = _create_test_app(_mock_session())

        knowledge = SimpleNamespace(owner="other", scope="private", title="KB")
        with (
            patch("ching_tech_os.api.share.get_knowledge", return_value=knowledge),
            patch(
                "ching_tech_os.api.share.get_user_preferences",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ching_tech_os.api.share.check_knowledge_permission",
                return_value=False,
            ),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "knowledge", "resource_id": "kb-1"},
            )
            assert resp.status_code == 403

    def test_knowledge_not_found(self):
        """知識庫不存在 -> 404"""
        from ching_tech_os.services.knowledge import KnowledgeNotFoundError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.get_knowledge",
            side_effect=KnowledgeNotFoundError("不存在"),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "knowledge", "resource_id": "kb-x"},
            )
            assert resp.status_code == 404

    def test_knowledge_success(self):
        """知識庫類型有權限建立成功 -> 201"""
        app = _create_test_app(_mock_session())

        knowledge = SimpleNamespace(owner="testuser", scope="private", title="KB")
        with (
            patch("ching_tech_os.api.share.get_knowledge", return_value=knowledge),
            patch(
                "ching_tech_os.api.share.get_user_preferences",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "ching_tech_os.api.share.check_knowledge_permission",
                return_value=True,
            ),
            patch(
                "ching_tech_os.api.share.create_share_link",
                new_callable=AsyncMock,
                return_value=_link_response(resource_type="knowledge", resource_id="kb-1"),
            ),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "knowledge", "resource_id": "kb-1"},
            )
            assert resp.status_code == 201

    def test_nas_file_not_found(self):
        """NAS 檔案不存在 -> 404"""
        from ching_tech_os.services.share import NasFileNotFoundError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.validate_nas_file_path",
            side_effect=NasFileNotFoundError("找不到"),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "nas_file", "resource_id": "/missing.txt"},
            )
            assert resp.status_code == 404

    def test_nas_file_access_denied(self):
        """NAS 檔案存取被拒 -> 403"""
        from ching_tech_os.services.share import NasFileAccessDenied

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.validate_nas_file_path",
            side_effect=NasFileAccessDenied("拒絕"),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "nas_file", "resource_id": "/secret.txt"},
            )
            assert resp.status_code == 403

    def test_nas_file_success(self, tmp_path):
        """NAS 檔案類型建立成功 -> 201"""
        test_file = tmp_path / "ok.txt"
        test_file.write_text("hi")

        app = _create_test_app(_mock_session())

        with (
            patch(
                "ching_tech_os.api.share.validate_nas_file_path",
                return_value=test_file,
            ),
            patch(
                "ching_tech_os.api.share.create_share_link",
                new_callable=AsyncMock,
                return_value=_link_response(resource_type="nas_file", resource_id="/ok.txt"),
            ),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "nas_file", "resource_id": "/ok.txt"},
            )
            assert resp.status_code == 201

    def test_create_resource_not_found(self):
        """service 層回報資源不存在 -> 404"""
        from ching_tech_os.services.share import ResourceNotFoundError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.create_share_link",
            new_callable=AsyncMock,
            side_effect=ResourceNotFoundError("資源不存在"),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "content", "content": "x"},
            )
            assert resp.status_code == 404

    def test_create_share_error(self):
        """service 層一般錯誤 -> 500"""
        from ching_tech_os.services.share import ShareError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.create_share_link",
            new_callable=AsyncMock,
            side_effect=ShareError("爆炸"),
        ):
            client = TestClient(app)
            resp = client.post(
                "/api/share",
                json={"resource_type": "content", "content": "x"},
            )
            assert resp.status_code == 500


# ============================================
# 列出分享連結 API 測試
# ============================================


class TestListLinks:
    def test_mine_as_user(self):
        """一般使用者列出自己的連結"""
        app = _create_test_app(_mock_session(role="user"))

        with patch(
            "ching_tech_os.api.share.list_my_links",
            new_callable=AsyncMock,
            return_value=ShareLinkListResponse(links=[_link_response()]),
        ) as mock_mine:
            client = TestClient(app)
            resp = client.get("/api/share")
            assert resp.status_code == 200
            body = resp.json()
            assert body["is_admin"] is False
            assert len(body["links"]) == 1
            mock_mine.assert_awaited_once_with("testuser")

    def test_all_as_admin(self):
        """管理員以 view=all 列出全部連結"""
        app = _create_test_app(_mock_session(role="admin", username="boss"))

        with patch(
            "ching_tech_os.api.share.list_all_links",
            new_callable=AsyncMock,
            return_value=ShareLinkListResponse(links=[]),
        ) as mock_all:
            client = TestClient(app)
            resp = client.get("/api/share?view=all")
            assert resp.status_code == 200
            assert resp.json()["is_admin"] is True
            mock_all.assert_awaited_once()

    def test_all_as_user_falls_back_to_mine(self):
        """非管理員帶 view=all 仍只看到自己的連結"""
        app = _create_test_app(_mock_session(role="user"))

        with patch(
            "ching_tech_os.api.share.list_my_links",
            new_callable=AsyncMock,
            return_value=ShareLinkListResponse(links=[]),
        ) as mock_mine:
            client = TestClient(app)
            resp = client.get("/api/share?view=all")
            assert resp.status_code == 200
            mock_mine.assert_awaited_once_with("testuser")

    def test_share_error(self):
        """service 層錯誤 -> 500"""
        from ching_tech_os.services.share import ShareError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.list_my_links",
            new_callable=AsyncMock,
            side_effect=ShareError("查詢失敗"),
        ):
            client = TestClient(app)
            resp = client.get("/api/share")
            assert resp.status_code == 500


# ============================================
# 撤銷分享連結 API 測試
# ============================================


class TestDeleteLink:
    def test_success(self):
        """撤銷成功 -> 204"""
        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.revoke_link",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_revoke:
            client = TestClient(app)
            resp = client.delete("/api/share/abc123")
            assert resp.status_code == 204
            mock_revoke.assert_awaited_once_with("abc123", "testuser", False)

    def test_not_found(self):
        """連結不存在 -> 404"""
        from ching_tech_os.services.share import ShareLinkNotFoundError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.revoke_link",
            new_callable=AsyncMock,
            side_effect=ShareLinkNotFoundError(),
        ):
            client = TestClient(app)
            resp = client.delete("/api/share/missing")
            assert resp.status_code == 404

    def test_no_permission(self):
        """撤銷他人連結被拒 -> 403"""
        from ching_tech_os.services.share import ShareError

        app = _create_test_app(_mock_session())

        with patch(
            "ching_tech_os.api.share.revoke_link",
            new_callable=AsyncMock,
            side_effect=ShareError("您沒有權限撤銷此連結"),
        ):
            client = TestClient(app)
            resp = client.delete("/api/share/other-token")
            assert resp.status_code == 403


# ============================================
# 公開附件 API 成功／權限分支測試
# ============================================


def _patch_knowledge_link(kb_id="kb1"):
    """回傳 get_link_info 的 patch（knowledge 類型）"""
    return patch(
        "ching_tech_os.api.share.get_link_info",
        new_callable=AsyncMock,
        return_value={"resource_type": "knowledge", "resource_id": kb_id},
    )


class TestGetPublicAttachmentBranches:
    def _make_local_asset(self, tmp_path, monkeypatch, filename="kb1-a.png"):
        """建立本機 assets 圖片並指向 tmp_path"""
        monkeypatch.setattr(settings, "knowledge_data_path", str(tmp_path))
        asset = tmp_path / "assets" / "images" / filename
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"png-data")
        return asset

    def test_local_asset_new_format(self, tmp_path, monkeypatch):
        """local://knowledge/assets/images/ 新格式讀取本機附件"""
        self._make_local_asset(tmp_path, monkeypatch)
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/local://knowledge/assets/images/kb1-a.png"
            )
            assert resp.status_code == 200
            assert resp.content == b"png-data"
            assert resp.headers["content-type"].startswith("image/png")

    def test_local_asset_new_format_nginx_merged(self, tmp_path, monkeypatch):
        """local:/knowledge/assets/images/（nginx 合併 //）格式"""
        self._make_local_asset(tmp_path, monkeypatch)
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/local:/knowledge/assets/images/kb1-a.png"
            )
            assert resp.status_code == 200

    def test_local_asset_old_format(self, tmp_path, monkeypatch):
        """local://knowledge/images/ 舊格式"""
        self._make_local_asset(tmp_path, monkeypatch)
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/local://knowledge/images/kb1-a.png"
            )
            assert resp.status_code == 200

    def test_local_asset_old_format_nginx_merged(self, tmp_path, monkeypatch):
        """local:/knowledge/images/（nginx 合併 //）舊格式"""
        self._make_local_asset(tmp_path, monkeypatch)
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/local:/knowledge/images/kb1-a.png"
            )
            assert resp.status_code == 200

    def test_local_asset_normalized_format(self, tmp_path, monkeypatch):
        """local/images/ 正規化格式"""
        self._make_local_asset(tmp_path, monkeypatch)
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get("/api/public/tok/attachments/local/images/kb1-a.png")
            assert resp.status_code == 200

    def test_local_asset_wrong_kb_id(self, tmp_path, monkeypatch):
        """本機附件檔名不含 kb_id -> 403"""
        self._make_local_asset(tmp_path, monkeypatch, filename="other-a.png")
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get("/api/public/tok/attachments/local/images/other-a.png")
            assert resp.status_code == 403

    def test_local_asset_missing_file(self, tmp_path, monkeypatch):
        """本機附件檔案不存在 -> 404"""
        monkeypatch.setattr(settings, "knowledge_data_path", str(tmp_path))
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get("/api/public/tok/attachments/local/images/kb1-none.png")
            assert resp.status_code == 404

    def test_path_traversal_blocked(self):
        """路徑含 ..（URL 編碼繞過 client 正規化）-> 400"""
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            # 用 %2E%2E 編碼避免 httpx 先把 ../ 正規化掉
            resp = client.get("/api/public/tok/attachments/local/images/%2E%2E/kb1-a.png")
            assert resp.status_code == 400

    def test_nas_attachment_ctos_format(self):
        """ctos://knowledge/attachments/ 新格式讀取 NAS 附件"""
        app = _create_test_app()

        with (
            _patch_knowledge_link(),
            patch(
                "ching_tech_os.api.share.get_nas_attachment",
                return_value=b"nas-data",
            ) as mock_nas,
        ):
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/ctos://knowledge/attachments/kb1/f.jpg"
            )
            assert resp.status_code == 200
            assert resp.content == b"nas-data"
            mock_nas.assert_called_once_with("kb1/f.jpg")

    def test_nas_attachment_ctos_format_nginx_merged(self):
        """ctos:/knowledge/attachments/（nginx 合併 //）格式"""
        app = _create_test_app()

        with (
            _patch_knowledge_link(),
            patch(
                "ching_tech_os.api.share.get_nas_attachment",
                return_value=b"nas-data",
            ),
        ):
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/ctos:/knowledge/attachments/kb1/f.jpg"
            )
            assert resp.status_code == 200

    def test_nas_attachment_nas_old_format(self):
        """nas://knowledge/ 舊格式"""
        app = _create_test_app()

        with (
            _patch_knowledge_link(),
            patch(
                "ching_tech_os.api.share.get_nas_attachment",
                return_value=b"nas-data",
            ),
        ):
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/nas://knowledge/attachments/kb1/f.jpg"
            )
            assert resp.status_code == 200

    def test_nas_attachment_nas_old_format_nginx_merged(self):
        """nas:/knowledge/（nginx 合併 //）舊格式"""
        app = _create_test_app()

        with (
            _patch_knowledge_link(),
            patch(
                "ching_tech_os.api.share.get_nas_attachment",
                return_value=b"nas-data",
            ),
        ):
            client = TestClient(app)
            resp = client.get(
                "/api/public/tok/attachments/nas:/knowledge/attachments/kb1/f.jpg"
            )
            assert resp.status_code == 200

    def test_nas_attachment_wrong_kb(self):
        """NAS 附件不屬於該知識庫 -> 403"""
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get("/api/public/tok/attachments/attachments/other/f.jpg")
            assert resp.status_code == 403

    def test_nas_attachment_knowledge_error(self):
        """NAS 讀取失敗（KnowledgeError）-> 404"""
        from ching_tech_os.services.knowledge import KnowledgeError

        app = _create_test_app()

        with (
            _patch_knowledge_link(),
            patch(
                "ching_tech_os.api.share.get_nas_attachment",
                side_effect=KnowledgeError("讀取失敗"),
            ),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/tok/attachments/attachments/kb1/f.jpg")
            assert resp.status_code == 404

    def test_unknown_extension_octet_stream(self, tmp_path, monkeypatch):
        """未知副檔名回傳 application/octet-stream"""
        self._make_local_asset(tmp_path, monkeypatch, filename="kb1-x.zzz")
        app = _create_test_app()

        with _patch_knowledge_link():
            client = TestClient(app)
            resp = client.get("/api/public/tok/attachments/local/images/kb1-x.zzz")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/octet-stream"


# ============================================
# 下載 API 補充測試
# ============================================


class TestDownloadSharedFileMore:
    def test_resource_not_found(self):
        """ResourceNotFoundError -> 404"""
        from ching_tech_os.services.share import ResourceNotFoundError

        app = _create_test_app()

        with patch(
            "ching_tech_os.api.share.get_link_info",
            new_callable=AsyncMock,
            side_effect=ResourceNotFoundError("資源不存在"),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/tok/download")
            assert resp.status_code == 404

    def test_image_inline_disposition(self, tmp_path):
        """圖片檔案使用 inline Content-Disposition"""
        img = tmp_path / "照片.png"
        img.write_bytes(b"fake-png")

        app = _create_test_app()

        with (
            patch(
                "ching_tech_os.api.share.get_link_info",
                new_callable=AsyncMock,
                return_value={"resource_type": "nas_file", "resource_id": "/照片.png"},
            ),
            patch(
                "ching_tech_os.api.share.validate_nas_file_path",
                return_value=img,
            ),
        ):
            client = TestClient(app)
            resp = client.get("/api/public/tok/download")
            assert resp.status_code == 200
            assert resp.headers["content-disposition"].startswith("inline")
