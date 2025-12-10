"""FastAPI 應用程式入口"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .database import init_db_pool, close_db_pool
from .services.session import session_manager
from .api import auth, nas


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時
    await init_db_pool()
    await session_manager.start_cleanup_task()
    yield
    # 關閉時
    await session_manager.stop_cleanup_task()
    await close_db_pool()


app = FastAPI(
    title="Ching Tech OS API",
    version="0.1.0",
    lifespan=lifespan,
)

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
app.include_router(nas.router)


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
