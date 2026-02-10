"""CacheControlMiddleware 測試

驗證不同路徑類型的 Cache-Control 標頭行為。
"""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from httpx import ASGITransport, AsyncClient

from ching_tech_os.middleware.cache_control import CacheControlMiddleware


def _create_app(*, preset_cache_control: str | None = None) -> FastAPI:
    """建立測試用 FastAPI 應用"""
    test_app = FastAPI()
    test_app.add_middleware(CacheControlMiddleware)

    @test_app.get("/api/auth/login")
    async def auth_login():
        return JSONResponse({"ok": True})

    @test_app.get("/api/auth/token")
    async def auth_token():
        return JSONResponse({"token": "abc"})

    @test_app.get("/api/login/check")
    async def login_check():
        return JSONResponse({"ok": True})

    @test_app.get("/api/knowledge/list")
    async def api_knowledge():
        return JSONResponse({"items": []})

    @test_app.get("/api/config/public")
    async def config_public():
        return JSONResponse({"config": {}})

    @test_app.get("/share/abc123")
    async def share_page():
        return PlainTextResponse("shared content")

    @test_app.get("/s/token123")
    async def short_url():
        return PlainTextResponse("short url")

    @test_app.get("/public")
    async def public_page():
        return PlainTextResponse("public")

    @test_app.get("/")
    async def index():
        return PlainTextResponse("index")

    @test_app.get("/login.html")
    async def login():
        return PlainTextResponse("login")

    @test_app.get("/index.html")
    async def desktop():
        return PlainTextResponse("desktop")

    @test_app.get("/public.html")
    async def public_html():
        return PlainTextResponse("public html")

    @test_app.get("/api/health")
    async def health():
        return JSONResponse({"status": "healthy"})

    @test_app.get("/api/preset")
    async def preset():
        """模擬已設定 cache-control 的端點"""
        resp = JSONResponse({"ok": True})
        if preset_cache_control:
            resp.headers["cache-control"] = preset_cache_control
        return resp

    return test_app


async def _get(path: str, *, app: FastAPI | None = None) -> "httpx.Response":
    """輔助函式：對測試 app 發送 GET 請求"""
    transport = ASGITransport(app=app or _create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get(path)


# === 認證端點：private, no-store ===

@pytest.mark.asyncio
async def test_auth_login_no_store():
    """認證端點應回傳 private, no-store"""
    resp = await _get("/api/auth/login")
    assert resp.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_auth_token_no_store():
    """認證 token 端點應回傳 private, no-store"""
    resp = await _get("/api/auth/token")
    assert resp.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_login_check_no_store():
    """/api/login/ 前綴也應回傳 no-store"""
    resp = await _get("/api/login/check")
    assert resp.headers["cache-control"] == "private, no-store"


# === 公開分享頁面：public, max-age=300 ===

@pytest.mark.asyncio
async def test_share_page_public_cache():
    """/share/ 頁面應有短期快取"""
    resp = await _get("/share/abc123")
    assert resp.headers["cache-control"] == "public, max-age=300"


@pytest.mark.asyncio
async def test_short_url_public_cache():
    """/s/ 短網址應有短期快取"""
    resp = await _get("/s/token123")
    assert resp.headers["cache-control"] == "public, max-age=300"


@pytest.mark.asyncio
async def test_public_page_cache():
    """/public 頁面應有短期快取"""
    resp = await _get("/public")
    assert resp.headers["cache-control"] == "public, max-age=300"


@pytest.mark.asyncio
async def test_config_public_cache():
    """/api/config/public 應有短期快取"""
    resp = await _get("/api/config/public")
    assert resp.headers["cache-control"] == "public, max-age=300"


# === API 端點：private, no-cache ===

@pytest.mark.asyncio
async def test_api_endpoint_private_no_cache():
    """一般 API 端點應回傳 private, no-cache"""
    resp = await _get("/api/knowledge/list")
    assert resp.headers["cache-control"] == "private, no-cache"


@pytest.mark.asyncio
async def test_api_health_private_no_cache():
    """健康檢查端點也是 API，應回傳 private, no-cache"""
    resp = await _get("/api/health")
    assert resp.headers["cache-control"] == "private, no-cache"


# === SPA 入口頁面：no-cache ===

@pytest.mark.asyncio
async def test_spa_index_no_cache():
    """首頁應回傳 no-cache（允許 BFCache）"""
    resp = await _get("/")
    assert resp.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_spa_login_no_cache():
    """登入頁應回傳 no-cache"""
    resp = await _get("/login.html")
    assert resp.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_spa_desktop_no_cache():
    """桌面頁應回傳 no-cache"""
    resp = await _get("/index.html")
    assert resp.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_spa_public_html_no_cache():
    """公開頁面 HTML 應回傳 no-cache"""
    resp = await _get("/public.html")
    assert resp.headers["cache-control"] == "no-cache"


# === 已有 cache-control 的回應不被覆蓋 ===

@pytest.mark.asyncio
async def test_existing_cache_control_not_overridden():
    """已設定 cache-control 的回應不應被 middleware 覆蓋"""
    test_app = _create_app(preset_cache_control="public, max-age=3600")
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/preset")
        assert resp.headers["cache-control"] == "public, max-age=3600"
