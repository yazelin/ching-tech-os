"""登入記錄 API"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

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


@router.get(
    "",
    response_model=LoginRecordListResponse,
    summary="搜尋登入記錄",
)
async def list_login_records(
    user_id: int | None = Query(None, description="使用者 ID 過濾"),
    username: str | None = Query(None, description="使用者名稱過濾"),
    success: bool | None = Query(None, description="成功/失敗過濾"),
    ip_address: str | None = Query(None, description="IP 位址過濾"),
    start_date: datetime | None = Query(None, description="開始日期"),
    end_date: datetime | None = Query(None, description="結束日期"),
    device_fingerprint: str | None = Query(None, description="裝置指紋過濾"),
    page: int = Query(1, ge=1, description="頁碼"),
    limit: int = Query(20, ge=1, le=100, description="每頁筆數"),
) -> LoginRecordListResponse:
    """搜尋登入記錄

    支援多維度過濾與分頁。
    """
    filter = LoginRecordFilter(
        user_id=user_id,
        username=username,
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
) -> RecentLoginsResponse:
    """取得最近登入記錄

    若指定 user_id 或 username，只返回該使用者的記錄。
    """
    return await get_recent_logins(
        user_id=user_id,
        username=username,
        limit=limit,
    )


@router.get(
    "/stats",
    summary="取得登入統計",
)
async def get_login_statistics(
    user_id: int | None = Query(None, description="使用者 ID"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
) -> dict:
    """取得登入統計資訊

    包含總登入次數、成功/失敗次數、不同 IP/裝置數等。
    """
    return await get_login_stats(user_id=user_id, days=days)


@router.get(
    "/{record_id}",
    response_model=LoginRecordResponse,
    summary="取得單一登入記錄",
)
async def get_single_login_record(record_id: int) -> LoginRecordResponse:
    """取得單一登入記錄的完整資訊

    Args:
        record_id: 記錄 ID
    """
    record = await get_login_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"登入記錄 {record_id} 不存在",
        )
    return record
