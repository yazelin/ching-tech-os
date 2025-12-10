"""認證 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.auth import LoginRequest, LoginResponse, LogoutResponse, ErrorResponse
from ..services.session import session_manager, SessionData
from ..services.smb import create_smb_service, SMBAuthError, SMBConnectionError
from ..services.user import upsert_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

security = HTTPBearer(auto_error=False)


def get_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """取得並驗證 token

    Returns:
        token 字串

    Raises:
        HTTPException: 若未提供 token
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權，請重新登入",
        )
    return credentials.credentials


async def get_current_session(token: str = Depends(get_token)) -> SessionData:
    """驗證 token 並取得目前 session

    Returns:
        SessionData

    Raises:
        HTTPException: 若 token 無效或過期
    """
    session = session_manager.get_session(token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權，請重新登入",
        )

    return session


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "認證失敗"},
        503: {"model": ErrorResponse, "description": "無法連線至檔案伺服器"},
    },
)
async def login(request: LoginRequest) -> LoginResponse:
    """登入並建立 session

    使用 NAS SMB 認證驗證使用者身份。
    """
    smb = create_smb_service(request.username, request.password)

    try:
        # 測試 SMB 認證
        smb.test_auth()
    except SMBAuthError:
        return LoginResponse(success=False, error="帳號或密碼錯誤")
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )

    # 認證成功，建立 session
    token = session_manager.create_session(request.username, request.password)

    # 記錄使用者（非同步，不阻塞回應）
    try:
        await upsert_user(request.username)
    except Exception:
        # 資料庫錯誤不影響登入
        pass

    return LoginResponse(
        success=True,
        token=token,
        username=request.username,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(token: str = Depends(get_token)) -> LogoutResponse:
    """登出並清除 session"""
    session_manager.delete_session(token)
    return LogoutResponse(success=True)
