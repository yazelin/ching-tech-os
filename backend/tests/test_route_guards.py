"""路由守衛回歸測試：每條 /api 路由都要掛身分依賴，例外要列名附理由。

作法是 FastAPI 的 route 內省，不是靜態 AST：
把 `app.routes` 裡每條 `APIRoute` 的 `route.dependant` 依賴樹整棵走過，
看裡面有沒有出現「身分依賴」（見 `IDENTITY_DEPENDENCIES`）。
沒有任何身分依賴的路由，一定要出現在 `ALLOWED_PUBLIC`（附理由）
或 `KNOWN_UNGUARDED`（已開 issue、用 strict xfail 盯著）裡，否則測試紅。

為什麼不用 AST：AST 只看得到原始碼字面上的 `Depends(...)`，
看不到 router-level `dependencies=`、`include_router(dependencies=...)`、
以及 `require_app_permission()` 這種閉包底下真正掛了什麼。
route 內省看的是 FastAPI 實際會執行的東西。
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

# 必須在 import main 之前設定：extends 與各模組路由都看這個開關
os.environ.setdefault("ENABLED_MODULES", "*")

from fastapi import FastAPI  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402


# ============================================================
# 身分依賴認定清單
# ============================================================
# 比對依據是依賴 callable 的 `__qualname__`（閉包會帶 `<locals>`）或 `__name__`。
# 只要路由的依賴樹裡出現其中任何一個，就算「有掛身分」。
#
# 注意：`HTTPBearer(auto_error=False)`（`security`）刻意不列入——
# 它在沒帶 token 時回 None 而不擋，單獨掛它等於沒有身分檢查。
IDENTITY_DEPENDENCIES = frozenset({
    # api/auth.py：核心 session 驗證
    "get_token",                       # 取 Bearer token，沒帶就 401
    "get_current_session",             # token → SessionData，無效就 401
    "get_session_from_token_or_query", # 同上，額外允許 query string 帶 token
    "require_admin",                   # api/auth.py、api/user.py、api/bot_settings.py 各有一份
    # services/permissions.py：require_app_permission(app_id) 產生的閉包
    # （api/project.py 的 require_project_access、api/erp.py 的
    #   require_vendor_access / require_inventory_access 都是它的別名）
    "require_app_permission.<locals>.checker",
    # 取 user_id 的薄包裝（底層都掛 get_current_session）
    "get_current_user_id",             # api/ai_router.py
    "_get_user_id",                    # api/voice_router.py
    # 專案／NAS 的複合依賴（底層都掛 require_app_permission）
    "require_project_editor",          # api/project.py
    "get_nas_connection",              # api/nas.py
    "get_nas_connection_with_query",   # api/nas.py
})


# ============================================================
# 允許清單：沒有身分依賴，但確定是設計上公開或有自己的驗證
# ============================================================
ALLOWED_PUBLIC: dict[tuple[str, str], str] = {
    ("POST", "/api/auth/login"): "登入本身，尚未有 session 可驗",
    ("GET", "/api/health"): "健康檢查，只回 status，不含任何資料",
    ("GET", "/api/config/health"): "前端開機前探測後端是否活著，只回布林與版本",
    ("POST", "/api/bot/line/webhook"): "LINE 平台回呼，用 X-Line-Signature HMAC 簽章驗證來源",
    ("POST", "/api/bot/telegram/webhook"): "Telegram 平台回呼，用 secret token 驗證來源",
    ("POST", "/api/internal/proactive-push"): "內部排程觸發，handler 內限制來源必須是 127.0.0.1",
    ("GET", "/api/public/{token}"): "公開分享頁，權限由不可猜測的分享 token 本身承擔",
    ("GET", "/api/public/{token}/download"): "公開分享檔案下載，同上由分享 token 授權",
    ("GET", "/api/public/{token}/attachments/{path:path}"): "公開分享頁附件，同上由分享 token 授權",
    ("GET", "/api/voice/tts/{file_id}.m4a"): "LINE 伺服器要抓 TTS 音檔，無法帶 header；#265 判定刻意公開，檔名是 UUID4",
    ("GET", "/api/voice/tts/{file_id}.mp3"): "同上（.mp3 為向後相容的副檔名）",
}


# ============================================================
# 已知沒閘、已開 issue 待修：strict xfail 盯著
# ============================================================
# 這些「不」放進 ALLOWED_PUBLIC。修好之後 xfail 會變成 XPASS，
# strict=True 讓 XPASS 也算失敗，逼人回來把這裡的條目刪掉。
KNOWN_UNGUARDED: dict[tuple[str, str], str] = {
    ("GET", "/api/voice/voices"): "#256",
    ("GET", "/api/nvr/snapshot/{channel}"): "#261",
    ("GET", "/api/nvr/recording-status"): "#261",
}


# ============================================================
# 蒐集路由（含 extends）
# ============================================================
def _register_extends_routers(target_app: FastAPI) -> None:
    """把 extends/*/contributes.yaml 宣告的 router 掛到 target_app。

    這裡刻意只做 main._start_extends_modules() 的「註冊 router」那一段，
    不跑 lifespan startup（那會去連 DBF／載 Whisper 模型）。
    """
    import yaml

    from ching_tech_os.config import settings

    extends_root = Path(settings.extends_dir)
    if not extends_root.is_dir():
        return

    for contrib_path in sorted(extends_root.glob("*/contributes.yaml")):
        module_dir = contrib_path.parent
        try:
            config = yaml.safe_load(contrib_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - yaml 壞掉時不該讓守衛測試炸掉
            continue
        if not isinstance(config, dict):
            continue

        module_dir_str = str(module_dir)
        if module_dir_str not in sys.path:
            sys.path.insert(0, module_dir_str)

        for router_spec in config.get("routers") or []:
            if not isinstance(router_spec, dict):
                continue
            router_module = router_spec.get("module")
            if not isinstance(router_module, str):
                continue
            try:
                mod = importlib.import_module(router_module)
                router = getattr(mod, router_spec.get("attr", "router"))
            except Exception:  # pragma: no cover - 缺依賴時跳過該模組
                continue
            target_app.include_router(router, **(router_spec.get("kwargs") or {}))


def _dependency_names(route: APIRoute) -> set[str]:
    """走完整棵 dependant 樹，收集每個依賴 callable 的名字。"""
    names: set[str] = set()
    stack = [route.dependant]
    while stack:
        dependant = stack.pop()
        call = getattr(dependant, "call", None)
        if call is not None:
            names.add(getattr(call, "__qualname__", "") or "")
            names.add(getattr(call, "__name__", "") or "")
        stack.extend(dependant.dependencies)
    names.discard("")
    return names


def _collect_api_routes() -> dict[tuple[str, str], set[str]]:
    """回傳 {(METHOD, path): 依賴名字集合}，只含 /api 開頭的路由。"""
    from ching_tech_os.main import app

    # 不動全域 app：extends router 掛到另一個臨時 app 上再合併路由清單
    extends_app = FastAPI()
    _register_extends_routers(extends_app)

    table: dict[tuple[str, str], set[str]] = {}
    for route in list(app.routes) + list(extends_app.routes):
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api"):
            continue
        names = _dependency_names(route)
        for method in route.methods - {"HEAD", "OPTIONS"}:
            table[(method, route.path)] = names
    return table


@pytest.fixture(scope="module")
def api_routes() -> dict[tuple[str, str], set[str]]:
    routes = _collect_api_routes()
    assert routes, "沒有蒐集到任何 /api 路由，內省方式可能壞了"
    return routes


def _is_guarded(dep_names: set[str]) -> bool:
    return bool(dep_names & IDENTITY_DEPENDENCIES)


def _fmt(entry: tuple[str, str]) -> str:
    return f"{entry[0]:6} {entry[1]}"


# ============================================================
# 測試
# ============================================================
def test_every_api_route_has_identity_dependency(api_routes) -> None:
    """每條 /api 路由都要有身分依賴，否則必須列在允許清單或已知待修清單裡。"""
    unguarded = {
        entry for entry, names in api_routes.items() if not _is_guarded(names)
    }
    missing = sorted(unguarded - set(ALLOWED_PUBLIC) - set(KNOWN_UNGUARDED))
    assert not missing, (
        "以下 /api 路由沒有任何身分依賴，也不在允許清單裡：\n"
        + "\n".join(f"  {_fmt(e)}" for e in missing)
        + "\n\n要嘛補上登入／權限依賴，要嘛加進 tests/test_route_guards.py 的 "
        "ALLOWED_PUBLIC 並寫一句理由。"
    )


def test_allowlist_entries_all_exist(api_routes) -> None:
    """允許清單與待修清單裡的每一條都要真的存在，避免路由改名後留下死條目。"""
    listed = set(ALLOWED_PUBLIC) | set(KNOWN_UNGUARDED)
    stale = sorted(listed - set(api_routes))
    assert not stale, (
        "以下條目列在 ALLOWED_PUBLIC / KNOWN_UNGUARDED，但 app.routes 裡找不到"
        "（路由被改名或刪掉了？）：\n"
        + "\n".join(f"  {_fmt(e)}" for e in stale)
    )


def test_allowlist_entries_are_actually_unguarded(api_routes) -> None:
    """允許清單裡的路由若後來補上了身分依賴，就該從清單移除（清單不留贅條目）。"""
    now_guarded = sorted(
        entry for entry in ALLOWED_PUBLIC if _is_guarded(api_routes.get(entry, set()))
    )
    assert not now_guarded, (
        "以下路由已經掛上身分依賴，請從 ALLOWED_PUBLIC 移除：\n"
        + "\n".join(f"  {_fmt(e)}" for e in now_guarded)
    )


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param(
            entry,
            id=f"{entry[0]} {entry[1]}",
            marks=pytest.mark.xfail(strict=True, reason=reason),
        )
        for entry, reason in sorted(KNOWN_UNGUARDED.items())
    ],
)
def test_known_unguarded_routes_are_still_unguarded(api_routes, entry) -> None:
    """已知沒閘的路由：修好後這裡會 XPASS（strict）而紅，提醒刪掉 KNOWN_UNGUARDED 條目。"""
    assert _is_guarded(api_routes.get(entry, set())), (
        f"{_fmt(entry)} 尚未掛上身分依賴（{KNOWN_UNGUARDED[entry]}）"
    )
