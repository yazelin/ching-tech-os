"""extends/nvr 的兩支 REST 端點必須掛 nvr-viewer App 權限（issue #261）。

修之前 `GET /api/nvr/recording-status` 與 `GET /api/nvr/snapshot/{channel}`
的函式簽名裡沒有任何 `Depends`，不帶憑證就打得到。

這裡走真正的依賴鏈（`get_token` → `_resolve_session` → `require_app_permission`），
只把「token 換 session」那一步換成 stub，所以拿掉 `Depends` 之後
401／403 這幾條一定會紅（負控制）。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import ching_tech_os.api.auth as auth_api
from ching_tech_os.models.auth import SessionData

REPO_ROOT = Path(__file__).resolve().parents[2]
NVR_API_DIR = REPO_ROOT / "extends" / "nvr" / "api"

VALID_TOKEN = "nvr-test-token"


def _load(module_name: str, filename: str) -> ModuleType:
    """以檔案路徑載入 extends/nvr 的 API 模組。

    正式流程是把 `extends/nvr` 塞進 sys.path 後 `import api.nvr_snapshot`；
    測試裡用唯一模組名載入，避免和別的 extends 模組搶頂層 `api` 這個名字。
    """
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = NVR_API_DIR / filename
    if not path.is_file():
        pytest.skip(f"extends/nvr 未安裝：{path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


nvr_status = _load("_nvr_test_status", "nvr_status.py")
nvr_snapshot = _load("_nvr_test_snapshot", "nvr_snapshot.py")


def _session(role: str = "user", nvr_viewer: bool | None = None) -> SessionData:
    now = datetime.now(timezone.utc)
    app_permissions: dict[str, bool] = {}
    if nvr_viewer is not None:
        app_permissions["nvr-viewer"] = nvr_viewer
    return SessionData(
        username="tester",
        password="xxx",
        nas_host="localhost",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
        app_permissions=app_permissions,
    )


@pytest.fixture
def app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.include_router(nvr_status.router, prefix="/api/nvr")
    fastapi_app.include_router(nvr_snapshot.router, prefix="/api/nvr")
    return fastapi_app


@pytest.fixture
def stub_session(monkeypatch: pytest.MonkeyPatch):
    """只有 VALID_TOKEN 解得出 session，其餘一律無效。"""

    def _install(session: SessionData | None) -> None:
        async def _resolve(token: str) -> SessionData | None:
            if token == VALID_TOKEN:
                return session
            return None

        monkeypatch.setattr(auth_api, "_resolve_session", _resolve)

    return _install


async def _get(app: FastAPI, url: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(url, headers=headers)


@pytest.fixture
def mock_nvr(monkeypatch: pytest.MonkeyPatch):
    """把 NVR 換成回 200 JPEG 的假 client，確認請求真的走到 handler。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b"\xff\xd8\xff\xd9"
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    monkeypatch.setattr(nvr_snapshot, "_get_client", lambda: client)
    return client


# ============================================================
# 無 token → 401
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["/api/nvr/recording-status", "/api/nvr/snapshot/1"],
)
async def test_no_token_unauthorized(app: FastAPI, stub_session, url: str) -> None:
    stub_session(_session(role="admin"))
    resp = await _get(app, url)
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["/api/nvr/recording-status", "/api/nvr/snapshot/1"],
)
async def test_invalid_token_unauthorized(app: FastAPI, stub_session, url: str) -> None:
    stub_session(_session(role="admin"))
    resp = await _get(app, url, token="not-a-real-token")
    assert resp.status_code == 401


# ============================================================
# 有 token、nvr-viewer 權限 False → 403
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["/api/nvr/recording-status", "/api/nvr/snapshot/1"],
)
async def test_permission_denied_forbidden(app: FastAPI, stub_session, url: str) -> None:
    stub_session(_session(role="user", nvr_viewer=False))
    resp = await _get(app, url, token=VALID_TOKEN)
    assert resp.status_code == 403


# ============================================================
# 有權限 → 通到 handler
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("session_kwargs", [{"role": "admin"}, {"role": "user", "nvr_viewer": True}])
async def test_recording_status_allowed(app: FastAPI, stub_session, session_kwargs) -> None:
    stub_session(_session(**session_kwargs))
    resp = await _get(app, "/api/nvr/recording-status", token=VALID_TOKEN)
    assert resp.status_code == 200
    assert "channels" in resp.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("session_kwargs", [{"role": "admin"}, {"role": "user", "nvr_viewer": True}])
async def test_snapshot_allowed(app: FastAPI, stub_session, mock_nvr, session_kwargs) -> None:
    stub_session(_session(**session_kwargs))
    resp = await _get(app, "/api/nvr/snapshot/1", token=VALID_TOKEN)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert mock_nvr.get.await_count == 1


# ============================================================
# snapshot 專屬：<img src> 走 ?token=
# ============================================================


@pytest.mark.asyncio
async def test_snapshot_accepts_query_token(app: FastAPI, stub_session, mock_nvr) -> None:
    """舊桌面的 <img src> 帶不了 header，token 放 query 也要過。"""
    stub_session(_session(role="admin"))
    resp = await _get(app, f"/api/nvr/snapshot/1?token={VALID_TOKEN}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_snapshot_query_token_still_checks_permission(
    app: FastAPI, stub_session, mock_nvr
) -> None:
    """query token 不是後門：權限 False 一樣 403。"""
    stub_session(_session(role="user", nvr_viewer=False))
    resp = await _get(app, f"/api/nvr/snapshot/1?token={VALID_TOKEN}")
    assert resp.status_code == 403
    assert mock_nvr.get.await_count == 0


@pytest.mark.asyncio
async def test_snapshot_bad_query_token_unauthorized(app: FastAPI, stub_session) -> None:
    stub_session(_session(role="admin"))
    resp = await _get(app, "/api/nvr/snapshot/1?token=wrong")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recording_status_rejects_query_token(app: FastAPI, stub_session) -> None:
    """recording-status 是 fetch() 呼叫的，只吃 header，不開 query token。"""
    stub_session(_session(role="admin"))
    resp = await _get(app, f"/api/nvr/recording-status?token={VALID_TOKEN}")
    assert resp.status_code == 401


# ============================================================
# 權限閘本身存在（簽名層級）
# ============================================================


def _closure_app_ids(dependant) -> list[str]:
    """從 require_app_permission 回傳的 checker 取出閉包裡的 app_id。"""
    closure = getattr(dependant, "__closure__", None) or ()
    return [c.cell_contents for c in closure if isinstance(c.cell_contents, str)]


@pytest.mark.parametrize(
    "module_name, path",
    [
        ("_nvr_test_status", "/recording-status"),
        ("_nvr_test_snapshot", "/snapshot/{channel}"),
    ],
)
def test_endpoints_declare_nvr_viewer_dependency(module_name: str, path: str) -> None:
    module = sys.modules[module_name]
    route = next(r for r in module.router.routes if r.path == path)
    app_ids = [
        app_id
        for d in route.dependant.dependencies
        for app_id in _closure_app_ids(d.call)
        if getattr(d.call, "__qualname__", "").startswith("require_app_permission")
    ]
    assert "nvr-viewer" in app_ids
