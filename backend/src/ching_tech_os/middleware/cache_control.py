"""Cache-Control Middleware

根據請求路徑設定適當的 Cache-Control 標頭，
解決 no-store 阻止瀏覽器 BFCache 的問題。
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# 認證端點：必須阻止快取（安全需求）
_AUTH_PREFIXES = ("/api/auth/", "/api/login/")

# 靜態資源：長期快取
_STATIC_PREFIXES = ("/css/", "/js/", "/assets/", "/data/")

# 公開分享頁面：短期快取
_PUBLIC_PREFIXES = ("/share/", "/public", "/s/", "/api/config/public")

# SPA 入口頁面：允許 BFCache，但每次驗證
_SPA_PATHS = ("/", "/login.html", "/index.html", "/public.html")


class CacheControlMiddleware(BaseHTTPMiddleware):
    """根據路徑類型自動設定 Cache-Control 標頭"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 若回應已有 cache-control 標頭，不覆蓋
        if "cache-control" in response.headers:
            return response

        path = request.url.path
        cache_value = self._get_cache_value(path)

        if cache_value:
            response.headers["cache-control"] = cache_value

        return response

    @staticmethod
    def _get_cache_value(path: str) -> str | None:
        """根據路徑決定 Cache-Control 值"""

        # 認證端點：嚴格禁止快取
        if any(path.startswith(p) for p in _AUTH_PREFIXES):
            return "private, no-store"

        # SPA 入口頁面：允許 BFCache，每次驗證新鮮度（須在公開前綴之前檢查）
        if path in _SPA_PATHS:
            return "no-cache"

        # 靜態資源：長期不可變快取
        if any(path.startswith(p) for p in _STATIC_PREFIXES):
            return "public, max-age=31536000, immutable"

        # 公開分享頁面：短期快取（5 分鐘）
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return "public, max-age=300"

        # 一般 API 端點：私有、每次驗證
        if path.startswith("/api/"):
            return "private, no-cache"

        return None
