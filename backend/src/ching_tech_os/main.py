"""FastAPI 應用程式入口"""

import importlib
import inspect
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import socketio

from .config import settings
from .database import init_db_pool, close_db_pool
from .services.session import session_manager
from .services.terminal import terminal_service
from .services.scheduler import start_scheduler, stop_scheduler
from .modules import get_module_registry, is_module_enabled

try:  # 向下相容：保留可 monkeypatch 的符號
    from .services.linebot_agents import ensure_default_linebot_agents  # noqa: F401
except Exception:  # pragma: no cover - 僅在依賴缺失時啟用
    async def ensure_default_linebot_agents():
        return None

# 建立 Socket.IO 伺服器
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')


def ensure_directories():
    """確保必要的目錄存在"""
    from pathlib import Path
    import logging

    logger = logging.getLogger(__name__)

    # 需要建立的目錄
    directories = [
        Path(settings.knowledge_local_path),  # 知識庫
        Path(settings.project_local_path),    # 專案
        Path(settings.linebot_local_path) / "ai-images",  # AI 生成圖片
    ]

    for dir_path in directories:
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"建立目錄: {dir_path}")
            except Exception as e:
                logger.warning(f"無法建立目錄 {dir_path}: {e}")


def _resolve_callable(dotted_path: str):
    """解析 dotted path 為可呼叫函數。"""
    module_path, attr = dotted_path.rsplit(".", 1)
    if module_path.startswith("."):
        mod = importlib.import_module(module_path, package=__package__)
    else:
        mod = importlib.import_module(module_path)
    return getattr(mod, attr)


def _register_module_routers(fastapi_app: FastAPI) -> None:
    """依啟用模組動態註冊 API 路由。"""
    imported_modules: dict[str, object] = {}
    for module_id, info in get_module_registry().items():
        if not is_module_enabled(module_id):
            continue
        for router_spec in info.get("routers", []):
            module_path = router_spec.get("module")
            router_attr = router_spec.get("attr", "router")
            kwargs = router_spec.get("kwargs") or {}
            if not isinstance(module_path, str):
                continue
            try:
                mod = imported_modules.get(module_path)
                if mod is None:
                    mod = importlib.import_module(module_path, package=__package__)
                    imported_modules[module_path] = mod
                router = getattr(mod, router_attr)
                fastapi_app.include_router(router, **kwargs)
            except ImportError as e:
                logging.getLogger(__name__).warning("模組 %s 路由載入失敗: %s", module_id, e)
            except AttributeError:
                logging.getLogger(__name__).warning(
                    "模組 %s 缺少路由屬性: %s.%s",
                    module_id,
                    module_path,
                    router_attr,
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    import logging as _logging  # 避免與模組層級 logging 衝突
    # 啟動時
    if not settings.bot_secret_key:
        _logging.getLogger(__name__).warning(
            "BOT_SECRET_KEY 未設定，Bot 憑證加密將使用預設金鑰（不安全）。"
            "請在 .env 中設定 BOT_SECRET_KEY。"
        )
    ensure_directories()  # 確保必要目錄存在
    # 預載入 Skills
    try:
        from .skills import get_skill_manager
        await get_skill_manager().load_skills()
    except Exception as e:
        _logging.getLogger(__name__).warning("Skills 預載入失敗: %s", e)
    # 初始化 ClawHub client（存入 app.state 供依賴注入）
    from .services.clawhub_client import ClawHubClient
    app.state.clawhub_client = ClawHubClient()
    # 初始化 SkillHub client（依 feature flag）
    from .services.skillhub_client import SkillHubClient, skillhub_enabled
    if skillhub_enabled():
        app.state.skillhub_client = SkillHubClient()
    await init_db_pool()

    # 啟動模組初始化（依啟停狀態）
    for module_id, info in get_module_registry().items():
        if not is_module_enabled(module_id):
            continue
        startup_path = info.get("lifespan_startup")
        if not isinstance(startup_path, str) or not startup_path:
            continue
        try:
            startup_fn = _resolve_callable(startup_path)
            result = startup_fn()
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            _logging.getLogger(__name__).warning("模組 %s 啟動函式執行失敗: %s", module_id, e)

    await session_manager.start_cleanup_task()
    await terminal_service.start_cleanup_task()
    start_scheduler()

    # 啟動 Telegram Polling（取代 webhook 模式）
    import asyncio
    telegram_polling_task = None
    if is_module_enabled("telegram-bot"):
        from .services.bot_telegram.polling import run_telegram_polling
        telegram_polling_task = asyncio.create_task(run_telegram_polling())
    yield
    # 關閉時
    if telegram_polling_task is not None:
        telegram_polling_task.cancel()
        try:
            await telegram_polling_task
        except asyncio.CancelledError:
            pass
    stop_scheduler()
    await terminal_service.stop_cleanup_task()
    terminal_service.close_all()
    await session_manager.stop_cleanup_task()
    from .services.workers import shutdown_pools
    shutdown_pools()
    # 關閉 Hub clients
    async def _shutdown_client(attr_name: str) -> None:
        try:
            client = getattr(app.state, attr_name, None)
            if client is not None:
                await client.close()
                delattr(app.state, attr_name)
        except Exception as e:
            _logging.getLogger(__name__).warning(f"關閉 {attr_name} 失敗: {e}")

    await _shutdown_client("clawhub_client")
    await _shutdown_client("skillhub_client")
    # 關閉 Line Bot 共用客戶端
    from .services.bot_line.client import close_line_client
    await close_line_client()
    # 清理 Claude agent 工作目錄基底
    try:
        from .services.claude_agent import _WORKING_DIR_BASE
        import shutil
        shutil.rmtree(_WORKING_DIR_BASE, ignore_errors=True)
    except Exception as e:
        logging.getLogger(__name__).warning(f"清理 Claude agent 工作目錄失敗: {e}")
    await close_db_pool()


app = FastAPI(
    title="Ching Tech OS API",
    version="0.4.0",
    lifespan=lifespan,
)

# --- 全域 ServiceError handler ---
from .services.errors import ServiceError  # noqa: E402

_error_logger = logging.getLogger("error_handler")


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    _error_logger.warning(
        "ServiceError %s %s: [%s] %s",
        request.method,
        request.url.path,
        exc.code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
    )


# 包裝成 ASGI 應用（Socket.IO + FastAPI）
socket_app = socketio.ASGIApp(sio, app)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache-Control 設定（BFCache 優化）
from .middleware.cache_control import CacheControlMiddleware  # noqa: E402
app.add_middleware(CacheControlMiddleware)

# 註冊路由
_register_module_routers(app)


@app.get("/api/health")
async def health():
    """API 健康檢查"""
    return {"status": "healthy"}


# 前端路由
FRONTEND = Path(settings.frontend_dir)


@app.get("/")
async def index():
    """首頁重導向到登入頁"""
    return FileResponse(FRONTEND / "login.html")


@app.get("/login.html")
async def login_page():
    """登入頁面"""
    return FileResponse(FRONTEND / "login.html")


@app.get("/index.html")
async def desktop_page():
    """桌面頁面"""
    return FileResponse(FRONTEND / "index.html")


@app.get("/public.html")
async def public_page():
    """公開分享頁面"""
    return FileResponse(FRONTEND / "public.html")


@app.get("/s/{token}")
async def short_share_url(token: str):
    """短網址 - 產生帶有動態 OG 標籤的 HTML（供 Line 預覽）"""
    from .services.share import get_link_info, ShareLinkNotFoundError, ShareLinkExpiredError

    # 預設 OG 資訊
    og_title = "擎添工業 - 分享內容"
    og_description = "此為擎添工業內部分享的文件或專案資訊"
    og_type = "article"

    try:
        link_info = await get_link_info(token)
        resource_type = link_info["resource_type"]
        resource_id = link_info["resource_id"]

        if resource_type == "knowledge":
            from .services.knowledge import get_knowledge
            try:
                kb = get_knowledge(resource_id)
                og_title = f"{kb.title} - 擎添工業"
                # 截取前 100 字作為描述
                content_preview = (kb.content or "")[:100].replace("\n", " ").strip()
                if content_preview:
                    og_description = content_preview + ("..." if len(kb.content or "") > 100 else "")
            except Exception:
                pass

        elif resource_type == "project":
            from .services import project_service
            try:
                project = await project_service.get_project(resource_id)
                if project:
                    og_title = f"{project['name']} - 擎添工業專案"
                    if project.get("description"):
                        og_description = project["description"][:100]
            except Exception:
                pass

        elif resource_type == "nas_file":
            # 從路徑取得檔名
            file_name = resource_id.split("/")[-1] if "/" in resource_id else resource_id
            og_title = f"{file_name} - 擎添工業"
            og_description = f"點擊下載檔案：{file_name}"

    except (ShareLinkNotFoundError, ShareLinkExpiredError):
        # 連結無效或過期，使用預設值（讓前端 JS 處理錯誤顯示）
        pass
    except Exception:
        pass

    # 讀取 public.html 模板
    html_template = (FRONTEND / "public.html").read_text(encoding="utf-8")

    # 將靜態 OG 標籤替換為動態內容
    import html
    og_title_escaped = html.escape(og_title)
    og_description_escaped = html.escape(og_description)

    html_content = html_template.replace(
        '<meta property="og:title" content="擎添工業 - 分享內容">',
        f'<meta property="og:title" content="{og_title_escaped}">'
    ).replace(
        '<meta property="og:description" content="此為擎添工業內部分享的文件或專案資訊">',
        f'<meta property="og:description" content="{og_description_escaped}">'
    ).replace(
        '<title>擎添工業 - 分享內容</title>',
        f'<title>{og_title_escaped}</title>'
    )

    return HTMLResponse(content=html_content)


# 掛載靜態檔案（放在最後，避免覆蓋 API 路由）
app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
app.mount("/fonts", StaticFiles(directory=FRONTEND / "fonts"), name="fonts")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")
app.mount("/src", StaticFiles(directory=FRONTEND / "src"), name="src")
if (FRONTEND / "fonts").is_dir():
    app.mount("/fonts", StaticFiles(directory=FRONTEND / "fonts"), name="fonts")

# 知識庫本機附件目錄
KNOWLEDGE_ASSETS = Path(settings.knowledge_data_path) / "assets"
if KNOWLEDGE_ASSETS.exists():
    app.mount("/data/knowledge/assets", StaticFiles(directory=KNOWLEDGE_ASSETS), name="knowledge-assets")

# 專案附件本機目錄
PROJECT_ATTACHMENTS = Path(settings.project_attachments_path)
PROJECT_ATTACHMENTS.mkdir(parents=True, exist_ok=True)
app.mount("/data/projects/attachments", StaticFiles(directory=PROJECT_ATTACHMENTS), name="project-attachments")


# === Socket.IO 事件 ===

@sio.event
async def connect(sid, environ):
    """客戶端連線"""
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    """客戶端斷線"""
    print(f"Client disconnected: {sid}")


# 註冊 AI 事件（在 api/ai.py 中定義）
if is_module_enabled("ai-agent"):
    from .api import ai

    ai.register_events(sio)

# 註冊終端機事件
if is_module_enabled("terminal"):
    from .api import terminal

    terminal.register_events(sio)

# 註冊訊息中心事件
from .api import message_events
message_events.register_events(sio)
