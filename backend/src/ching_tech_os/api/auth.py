"""認證 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import settings
from ..models.auth import LoginRequest, LoginResponse, LogoutResponse, ErrorResponse, TenantBriefInfo
from ..models.login_record import DeviceInfo as LoginRecordDeviceInfo, DeviceType, GeoLocation
from ..models.message import MessageSeverity, MessageSource
from ..services.session import session_manager, SessionData
from ..services.smb import create_smb_service, SMBAuthError, SMBConnectionError
from ..services.user import upsert_user, get_user_by_username, get_user_for_auth, update_last_login
from ..services.password import verify_password
from ..services.login_record import record_login
from ..services.message import log_message
from ..services.geoip import resolve_ip_location, parse_device_info
from ..services.tenant import (
    resolve_tenant_id,
    get_tenant_by_id,
    get_tenant_admin_role,
    get_tenant_settings,
    TenantNotFoundError,
    TenantSuspendedError,
)
from ..api.message_events import emit_new_message, emit_unread_count

logger = logging.getLogger(__name__)

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


# ============================================================
# 統一權限檢查函數
# ============================================================

# 角色權限階層（數字越大權限越高）
ROLE_HIERARCHY = {
    "user": 1,
    "tenant_admin": 2,
    "platform_admin": 3,
}


def get_role_level(role: str | None) -> int:
    """取得角色的權限等級"""
    return ROLE_HIERARCHY.get(role or "user", 1)


def can_manage_user(operator_role: str | None, target_role: str | None) -> bool:
    """檢查操作者是否可以管理目標使用者

    規則：
    - platform_admin 可管理所有人（包括其他 platform_admin）
    - tenant_admin 只能管理 user
    - user 不能管理任何人
    """
    operator_level = get_role_level(operator_role)
    target_level = get_role_level(target_role)

    # platform_admin 可管理所有人
    if operator_role == "platform_admin":
        return True

    # 其他角色只能管理比自己低的角色
    return operator_level > target_level


async def require_platform_admin(
    session: SessionData = Depends(get_current_session),
) -> SessionData:
    """要求平台管理員權限

    Raises:
        HTTPException: 若不是平台管理員
    """
    if session.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要平台管理員權限",
        )
    return session


async def require_tenant_admin_or_above(
    session: SessionData = Depends(get_current_session),
) -> SessionData:
    """要求租戶管理員或更高權限

    Raises:
        HTTPException: 若不是租戶管理員或平台管理員
    """
    if session.role not in ("tenant_admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要租戶管理員或更高權限",
        )
    return session


async def require_can_manage_target(
    session: SessionData, target_role: str | None, target_tenant_id: str | None = None
) -> None:
    """檢查是否可以管理目標使用者

    Args:
        session: 操作者的 session
        target_role: 目標使用者的角色
        target_tenant_id: 目標使用者的租戶 ID（可選）

    Raises:
        HTTPException: 若無權限
    """
    # 檢查角色階層
    if not can_manage_user(session.role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無權限操作此使用者",
        )

    # 非平台管理員需要檢查租戶隔離
    if session.role != "platform_admin" and target_tenant_id is not None:
        if str(session.tenant_id) != str(target_tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權限操作其他租戶的使用者",
            )


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

    支援兩種認證方式：
    1. 密碼認證：使用者已設定密碼（password_hash 不為 NULL）
    2. SMB 認證：使用者尚未設定密碼，fallback 到 NAS SMB 驗證（過渡期）

    多租戶模式下需要提供 tenant_code 參數。
    """
    # 取得客戶端資訊
    ip_address = get_client_ip(req)
    user_agent = req.headers.get("user-agent", "")

    # 解析租戶 ID
    try:
        tenant_id = await resolve_tenant_id(request.tenant_code)
    except TenantNotFoundError:
        return LoginResponse(success=False, error="租戶代碼不存在")
    except TenantSuspendedError:
        return LoginResponse(success=False, error="此租戶帳號已被停用")

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

    # 先嘗試從資料庫查找使用者
    user_data = await get_user_for_auth(request.username, tenant_id)

    auth_success = False
    use_password_auth = False
    must_change_password = False

    # 認證邏輯
    if user_data and user_data.get("password_hash"):
        # 使用密碼認證
        use_password_auth = True

        # 檢查帳號是否停用
        if not user_data.get("is_active", True):
            return LoginResponse(success=False, error="此帳號已被停用")

        # 驗證密碼
        if verify_password(request.password, user_data["password_hash"]):
            auth_success = True
            must_change_password = user_data.get("must_change_password", False)
        else:
            auth_success = False
    else:
        # 使用者沒有密碼，檢查租戶是否啟用 NAS 驗證
        try:
            tenant_settings = await get_tenant_settings(tenant_id)
        except TenantNotFoundError:
            return LoginResponse(success=False, error="租戶不存在")

        if tenant_settings.enable_nas_auth:
            # 租戶啟用 NAS 驗證，使用租戶設定的 NAS 主機
            smb = create_smb_service(
                request.username,
                request.password,
                host=tenant_settings.nas_auth_host,  # None 表示使用系統預設
                port=tenant_settings.nas_auth_port,
                share=tenant_settings.nas_auth_share,
            )
            try:
                smb.test_auth()
                auth_success = True
            except SMBAuthError:
                auth_success = False
            except SMBConnectionError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="無法連線至檔案伺服器",
                )
        else:
            # 租戶未啟用 NAS 驗證，且使用者不存在或無密碼
            if user_data is None:
                return LoginResponse(success=False, error="帳號不存在")
            else:
                # 使用者存在但沒有密碼，無法登入
                return LoginResponse(success=False, error="帳號或密碼錯誤")

    if not auth_success:
        # 登入失敗：記錄失敗的登入嘗試
        try:
            await record_login(
                username=request.username,
                success=False,
                ip_address=ip_address,
                user_id=user_data["id"] if user_data else None,
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

    # 認證成功
    user_id = None
    user_role = "user"

    if user_data:
        # 使用者已存在
        user_id = user_data["id"]
        # 更新最後登入時間
        await update_last_login(user_id)
    else:
        # 使用者不存在（SMB 認證但尚未建立用戶記錄）
        try:
            user_id = await upsert_user(request.username, tenant_id=tenant_id)
        except Exception as e:
            logger.error(f"Failed to upsert user '{request.username}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="無法建立使用者記錄，請稍後再試。",
            )

    # 從 tenant_admins 表判斷角色（而非 users.role 欄位）
    from ..services.user import get_user_role
    user_role = await get_user_role(user_id, tenant_id)

    # 取得使用者的 App 權限（供 session 快取使用）
    from ..services.permissions import get_user_app_permissions_sync
    app_permissions = get_user_app_permissions_sync(user_role, user_data)

    # 建立 session
    # 注意：密碼認證時，session 不儲存密碼（password 欄位為空字串）
    # SMB 認證時仍需保留密碼（過渡期，供檔案操作使用）
    session_password = "" if use_password_auth else request.password

    token = session_manager.create_session(
        request.username,
        session_password,
        user_id=user_id,
        tenant_id=tenant_id,
        role=user_role,
        app_permissions=app_permissions,
    )

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

        auth_method = "密碼" if use_password_auth else "SMB"
        msg_id = await log_message(
            severity=MessageSeverity.INFO,
            source=MessageSource.SECURITY,
            title=f"登入成功：{request.username}",
            content=f"使用者 {request.username} 從 {ip_address} {location_str}登入（{auth_method}認證）",
            category="auth",
            user_id=user_id,
            session_id=token,
            metadata={
                "ip": ip_address,
                "username": request.username,
                "geo": {"country": geo.country, "city": geo.city} if geo else None,
                "device_type": device_info.device_type.value if device_info else None,
                "auth_method": auth_method,
            },
        )
        # 推送未讀數量更新
        if user_id:
            await emit_unread_count(user_id)
    except Exception:
        pass

    # 取得租戶資訊（用於回應）
    tenant_brief = None
    try:
        tenant_data = await get_tenant_by_id(tenant_id)
        if tenant_data:
            tenant_brief = TenantBriefInfo(
                id=tenant_data["id"],
                code=tenant_data["code"],
                name=tenant_data["name"],
                plan=tenant_data["plan"],
            )
    except Exception:
        pass

    return LoginResponse(
        success=True,
        token=token,
        username=request.username,
        tenant=tenant_brief,
        role=user_role,
        must_change_password=must_change_password,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(token: str = Depends(get_token)) -> LogoutResponse:
    """登出並清除 session"""
    session_manager.delete_session(token)
    return LogoutResponse(success=True)


# 密碼變更相關 models
from pydantic import BaseModel


class ChangePasswordRequest(BaseModel):
    """變更密碼請求"""
    current_password: str | None = None  # 首次設定密碼時可為空
    new_password: str


class ChangePasswordResponse(BaseModel):
    """變更密碼回應"""
    success: bool
    error: str | None = None


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    session: SessionData = Depends(get_current_session),
) -> ChangePasswordResponse:
    """變更密碼

    使用者必須已登入。
    - 若已有密碼：需提供目前密碼
    - 若尚未設定密碼（NAS 認證使用者）：可直接設定新密碼
    變更成功後會清除 must_change_password 標記。
    """
    from ..services.password import verify_password, hash_password, validate_password_strength
    from ..services.user import get_user_for_auth, set_user_password, upsert_user

    # 確保使用者存在於資料庫（NAS 使用者可能尚未建立記錄）
    user_id = session.user_id
    if user_id is None:
        # 嘗試建立使用者記錄
        try:
            user_id = await upsert_user(session.username, session.tenant_id)
        except Exception:
            return ChangePasswordResponse(success=False, error="無法建立使用者記錄")

    # 取得使用者資料
    user_data = await get_user_for_auth(session.username, session.tenant_id)

    # 判斷是否為首次設定密碼
    has_password = user_data and user_data.get("password_hash")

    if has_password:
        # 已有密碼，需驗證目前密碼
        if not request.current_password:
            return ChangePasswordResponse(success=False, error="請輸入目前密碼")
        if not verify_password(request.current_password, user_data["password_hash"]):
            return ChangePasswordResponse(success=False, error="目前密碼錯誤")
    # 若沒有密碼，允許直接設定（首次設定）

    # 驗證新密碼強度
    is_valid, error_msg = validate_password_strength(request.new_password)
    if not is_valid:
        return ChangePasswordResponse(success=False, error=error_msg)

    # 更新密碼
    new_hash = hash_password(request.new_password)
    success = await set_user_password(user_id, new_hash, must_change=False)

    if not success:
        return ChangePasswordResponse(success=False, error="密碼更新失敗")

    return ChangePasswordResponse(success=True)
