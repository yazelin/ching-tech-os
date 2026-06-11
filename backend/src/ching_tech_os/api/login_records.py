"""登入記錄 API"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ching_tech_os.models.auth import SessionData
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.login_record import (
    LoginRecordFilter,
    LoginRecordListResponse,
    LoginRecordResponse,
    RecentLoginsResponse,
)
from ching_tech_os.services.login_record import (
    get_login_record,
    get_login_stats,
    get_recent_logins,
    search_login_records,
)

router = APIRouter(prefix="/api/login-records", tags=["login-records"])


def _scoped_user_id(session: SessionData, requested: int | None) -> int | None:
    """非 admin 一律限縮為自己的 user_id；admin 可用傳入值（None=全部）"""
    if session.role == "admin":
        return requested
    return session.user_id


@router.get(
    "",
    response_model=LoginRecordListResponse,
    summary="搜尋登入記錄",
)
async def list_login_records(
    user_id: int | None = Query(None, description="使用者 ID 過濾（非管理員一律限為自己）"),
    username: str | None = Query(None, description="使用者名稱過濾"),
    success: bool | None = Query(None, description="成功/失敗過濾"),
    ip_address: str | None = Query(None, description="IP 位址過濾"),
    start_date: datetime | None = Query(None, description="開始日期"),
    end_date: datetime | None = Query(None, description="結束日期"),
    device_fingerprint: str | None = Query(None, description="裝置指紋過濾"),
    page: int = Query(1, ge=1, description="頁碼"),
    limit: int = Query(20, ge=1, le=100, description="每頁筆數"),
    session: SessionData = Depends(get_current_session),
) -> LoginRecordListResponse:
    """搜尋登入記錄

    一般使用者只能查自己的登入記錄，管理員可查全部。
    """
    filter = LoginRecordFilter(
        user_id=_scoped_user_id(session, user_id),
        username=username if session.role == "admin" else None,
        success=success,
        ip_address=ip_address,
        start_date=start_date,
        end_date=end_date,
        device_fingerprint=device_fingerprint,
        page=page,
        limit=limit,
    )
    return await search_login_records(filter)


@router.get(
    "/recent",
    response_model=RecentLoginsResponse,
    summary="取得最近登入",
)
async def get_recent_login_records(
    user_id: int | None = Query(None, description="使用者 ID"),
    username: str | None = Query(None, description="使用者名稱"),
    limit: int = Query(10, ge=1, le=50, description="最大筆數"),
    session: SessionData = Depends(get_current_session),
) -> RecentLoginsResponse:
    """取得最近登入記錄

    一般使用者只返回自己的記錄，管理員可指定 user_id/username。
    """
    return await get_recent_logins(
        user_id=_scoped_user_id(session, user_id),
        username=username if session.role == "admin" else None,
        limit=limit,
    )


@router.get(
    "/stats",
    summary="取得登入統計",
)
async def get_login_statistics(
    user_id: int | None = Query(None, description="使用者 ID"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    session: SessionData = Depends(get_current_session),
) -> dict:
    """取得登入統計資訊

    一般使用者只統計自己的，管理員可指定 user_id（None=全部）。
    """
    return await get_login_stats(user_id=_scoped_user_id(session, user_id), days=days)


@router.get(
    "/{record_id}",
    response_model=LoginRecordResponse,
    summary="取得單一登入記錄",
)
async def get_single_login_record(
    record_id: int,
    session: SessionData = Depends(get_current_session),
) -> LoginRecordResponse:
    """取得單一登入記錄的完整資訊

    一般使用者只能取自己的記錄，否則回 404（不洩漏存在）。

    Args:
        record_id: 記錄 ID
    """
    record = await get_login_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"登入記錄 {record_id} 不存在",
        )
    if session.role != "admin" and getattr(record, "user_id", None) != session.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"登入記錄 {record_id} 不存在",
        )
    return record
