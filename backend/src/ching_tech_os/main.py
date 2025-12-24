"""FastAPI 應用程式入口"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio

from .config import settings
from .database import init_db_pool, close_db_pool
from .services.session import session_manager
from .services.terminal import terminal_service
from .services.scheduler import start_scheduler, stop_scheduler
from .api import auth, knowledge, login_records, messages, nas, user, ai_router, ai_management, project, linebot_router

# 建立 Socket.IO 伺服器
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時
    await init_db_pool()
    await session_manager.start_cleanup_task()
    await terminal_service.start_cleanup_task()
    start_scheduler()
    yield
    # 關閉時
    stop_scheduler()
    await terminal_service.stop_cleanup_task()
    terminal_service.close_all()
    await session_manager.stop_cleanup_task()
    await close_db_pool()


app = FastAPI(
    title="Ching Tech OS API",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(project.router)
app.include_router(linebot_router.router)


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


# 掛載靜態檔案（放在最後，避免覆蓋 API 路由）
app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

# 知識庫本機附件目錄
KNOWLEDGE_ASSETS = Path("/home/ct/SDD/ching-tech-os/data/knowledge/assets")
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
