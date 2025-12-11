"""認證 API"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.auth import LoginRequest, LoginResponse, LogoutResponse, ErrorResponse
from ..models.login_record import DeviceInfo as LoginRecordDeviceInfo, DeviceType, GeoLocation
from ..models.message import MessageSeverity, MessageSource
from ..services.session import session_manager, SessionData
from ..services.smb import create_smb_service, SMBAuthError, SMBConnectionError
from ..services.user import upsert_user, get_user_by_username
from ..services.login_record import record_login
from ..services.message import log_message
from ..services.geoip import resolve_ip_location, parse_device_info
from ..api.message_events import emit_new_message, emit_unread_count

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


def get_session_from_token_or_query(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    token: str | None = None,  # Query parameter
) -> SessionData:
    """從 header 或 query parameter 取得 session

    優先使用 Authorization header，若無則使用 query parameter token。
    這允許 <img src> 等無法設定 header 的請求使用 token。

    Returns:
        SessionData

    Raises:
        HTTPException: 若 token 無效或過期
    """
    # 優先使用 header
    actual_token = None
    if credentials is not None:
        actual_token = credentials.credentials
    elif token is not None:
        actual_token = token

    if actual_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權，請重新登入",
        )

    session = session_manager.get_session(actual_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授權，請重新登入",
        )

    return session


def get_client_ip(req: Request) -> str:
    """取得客戶端真實 IP"""
    # 檢查 X-Forwarded-For 標頭
    forwarded = req.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # 檢查 X-Real-IP 標頭
    real_ip = req.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    # 使用直接連線 IP
    return req.client.host if req.client else "127.0.0.1"


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "認證失敗"},
        503: {"model": ErrorResponse, "description": "無法連線至檔案伺服器"},
    },
)
async def login(request: LoginRequest, req: Request) -> LoginResponse:
    """登入並建立 session

    使用 NAS SMB 認證驗證使用者身份。
    """
    # 取得客戶端資訊
    ip_address = get_client_ip(req)
    user_agent = req.headers.get("user-agent", "")

    # 解析地理位置
    geo = resolve_ip_location(ip_address)

    # 解析裝置資訊（從 User-Agent）
    ua_device = parse_device_info(user_agent) if user_agent else None

    # 合併前端提供的裝置資訊
    device_info = LoginRecordDeviceInfo(
        fingerprint=request.device.fingerprint if request.device else None,
        device_type=DeviceType(request.device.device_type) if request.device and request.device.device_type else (ua_device.device_type if ua_device else DeviceType.UNKNOWN),
        browser=request.device.browser if request.device and request.device.browser else (ua_device.browser if ua_device else None),
        os=request.device.os if request.device and request.device.os else (ua_device.os if ua_device else None),
    )

    smb = create_smb_service(request.username, request.password)

    try:
        # 測試 SMB 認證
        smb.test_auth()
    except SMBAuthError:
        # 登入失敗：記錄失敗的登入嘗試
        try:
            await record_login(
                username=request.username,
                success=False,
                ip_address=ip_address,
                user_id=None,
                failure_reason="帳號或密碼錯誤",
                user_agent=user_agent,
                geo=geo,
                device=device_info,
            )
            # 產生安全訊息
            msg_id = await log_message(
                severity=MessageSeverity.WARNING,
                source=MessageSource.SECURITY,
                title=f"登入失敗：{request.username}",
                content=f"來自 {ip_address} 的登入嘗試失敗（帳號或密碼錯誤）",
                category="auth",
                metadata={
                    "ip": ip_address,
                    "username": request.username,
                    "geo": {"country": geo.country, "city": geo.city} if geo else None,
                },
            )
            # 推送訊息通知
            from datetime import datetime
            await emit_new_message(
                message_id=msg_id,
                severity=MessageSeverity.WARNING,
                source=MessageSource.SECURITY,
                title=f"登入失敗：{request.username}",
                created_at=datetime.now().isoformat(),
                category="auth",
            )
        except Exception:
            pass  # 記錄失敗不影響回應

        return LoginResponse(success=False, error="帳號或密碼錯誤")
    except SMBConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="無法連線至檔案伺服器",
        )

    # 記錄使用者並取得 user_id
    user_id = None
    try:
        user_id = await upsert_user(request.username)
    except Exception:
        pass

    # 認證成功，建立 session（包含 user_id）
    token = session_manager.create_session(request.username, request.password, user_id=user_id)

    # 記錄成功登入
    try:
        await record_login(
            username=request.username,
            success=True,
            ip_address=ip_address,
            user_id=user_id,
            user_agent=user_agent,
            geo=geo,
            device=device_info,
            session_id=token,
        )
        # 產生安全訊息
        location_str = ""
        if geo and geo.city:
            location_str = f"（{geo.city}, {geo.country}）"
        elif geo and geo.country:
            location_str = f"（{geo.country}）"

        msg_id = await log_message(
            severity=MessageSeverity.INFO,
            source=MessageSource.SECURITY,
            title=f"登入成功：{request.username}",
            content=f"使用者 {request.username} 從 {ip_address} {location_str}登入",
            category="auth",
            user_id=user_id,
            session_id=token,
            metadata={
                "ip": ip_address,
                "username": request.username,
                "geo": {"country": geo.country, "city": geo.city} if geo else None,
                "device_type": device_info.device_type.value if device_info else None,
            },
        )
        # 推送未讀數量更新
        if user_id:
            await emit_unread_count(user_id)
    except Exception:
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
