"""FastAPI 應用程式入口"""

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
from .services.linebot_agents import ensure_default_linebot_agents
from .api import auth, knowledge, login_records, messages, nas, user, ai_router, ai_management, linebot_router, telegram_router, share, files, presentation, config_public, bot_settings

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時
    if not settings.bot_secret_key:
        import logging
        logging.getLogger(__name__).warning(
            "BOT_SECRET_KEY 未設定，Bot 憑證加密將使用預設金鑰（不安全）。"
            "請在 .env 中設定 BOT_SECRET_KEY。"
        )
    ensure_directories()  # 確保必要目錄存在
    # 預載入 Skills
    try:
        from .skills import get_skill_manager
        await get_skill_manager().load_skills()
    except Exception as e:
        logging.getLogger(__name__).warning(f"Skills 預載入失敗: {e}")
    await init_db_pool()
    await ensure_default_linebot_agents()  # 確保 Line Bot Agent 存在
    await session_manager.start_cleanup_task()
    await terminal_service.start_cleanup_task()
    start_scheduler()
    # 啟動 Telegram Polling（取代 webhook 模式）
    import asyncio
    from .services.bot_telegram.polling import run_telegram_polling
    telegram_polling_task = asyncio.create_task(run_telegram_polling())
    yield
    # 關閉時
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
    version="0.3.0",
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

# 註冊路由
app.include_router(auth.router)
app.include_router(knowledge.router)
app.include_router(messages.router)
app.include_router(login_records.router)
app.include_router(nas.router)
app.include_router(user.router)
app.include_router(user.admin_router)  # 管理員 API
app.include_router(ai_router.router)
app.include_router(ai_management.router)
app.include_router(linebot_router.router, prefix="/api/bot")
app.include_router(linebot_router.line_router, prefix="/api/bot/line")
app.include_router(telegram_router.router, prefix="/api/bot/telegram")
app.include_router(share.router)
app.include_router(share.public_router)
app.include_router(files.router)
app.include_router(presentation.router)
app.include_router(config_public.router)  # 公開配置 API
app.include_router(bot_settings.router)  # Bot 設定管理 API


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
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

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
from .api import ai
ai.register_events(sio)

# 註冊終端機事件
from .api import terminal
terminal.register_events(sio)

# 註冊訊息中心事件
from .api import message_events
message_events.register_events(sio)
