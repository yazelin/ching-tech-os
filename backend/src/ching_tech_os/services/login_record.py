"""登入記錄服務"""

import math
from datetime import datetime
from decimal import Decimal

from ..database import get_connection
from ..models.login_record import (
    DeviceInfo,
    GeoLocation,
    LoginRecordCreate,
    LoginRecordFilter,
    LoginRecordListItem,
    LoginRecordListResponse,
    LoginRecordResponse,
    RecentLoginsResponse,
)


async def record_login(
    username: str,
    success: bool,
    ip_address: str,
    user_id: int | None = None,
    failure_reason: str | None = None,
    user_agent: str | None = None,
    geo: GeoLocation | None = None,
    device: DeviceInfo | None = None,
    session_id: str | None = None,
) -> int:
    """記錄登入嘗試

    Args:
        username: 使用者帳號
        success: 是否成功
        ip_address: IP 位址
        user_id: 使用者 ID
        failure_reason: 失敗原因
        user_agent: User-Agent
        geo: 地理位置資訊
        device: 裝置資訊
        session_id: Session ID

    Returns:
        新建記錄的 ID
    """
    async with get_connection() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO login_records (
                user_id, username, success, failure_reason,
                ip_address, user_agent,
                geo_country, geo_city, geo_latitude, geo_longitude,
                device_fingerprint, device_type, browser, os,
                session_id, partition_date
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, CURRENT_DATE
            )
            RETURNING id
            """,
            user_id,
            username,
            success,
            failure_reason,
            ip_address,
            user_agent,
            geo.country if geo else None,
            geo.city if geo else None,
            geo.latitude if geo else None,
            geo.longitude if geo else None,
            device.fingerprint if device else None,
            device.device_type.value if device else None,
            device.browser if device else None,
            device.os if device else None,
            session_id,
        )
        return result["id"]


async def get_login_record(record_id: int) -> LoginRecordResponse | None:
    """取得單一登入記錄詳情

    Args:
        record_id: 記錄 ID

    Returns:
        登入記錄或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, created_at, user_id, username, success, failure_reason,
                   ip_address, user_agent,
                   geo_country, geo_city, geo_latitude, geo_longitude,
                   device_fingerprint, device_type, browser, os, session_id
            FROM login_records
            WHERE id = $1
            """,
            record_id,
        )
        if row:
            return LoginRecordResponse(
                id=row["id"],
                created_at=row["created_at"],
                user_id=row["user_id"],
                username=row["username"],
                success=row["success"],
                failure_reason=row["failure_reason"],
                ip_address=str(row["ip_address"]),
                user_agent=row["user_agent"],
                geo_country=row["geo_country"],
                geo_city=row["geo_city"],
                geo_latitude=row["geo_latitude"],
                geo_longitude=row["geo_longitude"],
                device_fingerprint=row["device_fingerprint"],
                device_type=row["device_type"],
                browser=row["browser"],
                os=row["os"],
                session_id=row["session_id"],
            )
        return None


async def search_login_records(filter: LoginRecordFilter) -> LoginRecordListResponse:
    """搜尋登入記錄

    Args:
        filter: 查詢條件

    Returns:
        登入記錄列表（含分頁資訊）
    """
    conditions = []
    params = []
    param_idx = 1

    # 使用者 ID 過濾
    if filter.user_id:
        conditions.append(f"user_id = ${param_idx}")
        params.append(filter.user_id)
        param_idx += 1

    # 使用者名稱過濾
    if filter.username:
        conditions.append(f"username = ${param_idx}")
        params.append(filter.username)
        param_idx += 1

    # 成功/失敗過濾
    if filter.success is not None:
        conditions.append(f"success = ${param_idx}")
        params.append(filter.success)
        param_idx += 1

    # IP 過濾
    if filter.ip_address:
        conditions.append(f"ip_address = ${param_idx}::inet")
        params.append(filter.ip_address)
        param_idx += 1

    # 日期範圍過濾
    if filter.start_date:
        conditions.append(f"created_at >= ${param_idx}")
        params.append(filter.start_date)
        param_idx += 1

    if filter.end_date:
        conditions.append(f"created_at <= ${param_idx}")
        params.append(filter.end_date)
        param_idx += 1

    # 裝置指紋過濾
    if filter.device_fingerprint:
        conditions.append(f"device_fingerprint = ${param_idx}")
        params.append(filter.device_fingerprint)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    async with get_connection() as conn:
        # 計算總數
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM login_records WHERE {where_clause}",
            *params,
        )
        total = count_row["total"]

        # 計算分頁
        offset = (filter.page - 1) * filter.limit
        total_pages = math.ceil(total / filter.limit) if total > 0 else 1

        # 查詢資料
        rows = await conn.fetch(
            f"""
            SELECT id, created_at, username, success, failure_reason,
                   ip_address, geo_country, geo_city, device_type, browser
            FROM login_records
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
            filter.limit,
            offset,
        )

        items = [
            LoginRecordListItem(
                id=row["id"],
                created_at=row["created_at"],
                username=row["username"],
                success=row["success"],
                failure_reason=row["failure_reason"],
                ip_address=str(row["ip_address"]),
                geo_country=row["geo_country"],
                geo_city=row["geo_city"],
                device_type=row["device_type"],
                browser=row["browser"],
            )
            for row in rows
        ]

        return LoginRecordListResponse(
            items=items,
            total=total,
            page=filter.page,
            limit=filter.limit,
            total_pages=total_pages,
        )


async def get_recent_logins(
    user_id: int | None = None,
    username: str | None = None,
    limit: int = 10,
) -> RecentLoginsResponse:
    """取得最近登入記錄

    Args:
        user_id: 使用者 ID
        username: 使用者名稱
        limit: 最大筆數

    Returns:
        最近登入記錄
    """
    async with get_connection() as conn:
        if user_id:
            rows = await conn.fetch(
                """
                SELECT id, created_at, username, success, failure_reason,
                       ip_address, geo_country, geo_city, device_type, browser
                FROM login_records
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
        elif username:
            rows = await conn.fetch(
                """
                SELECT id, created_at, username, success, failure_reason,
                       ip_address, geo_country, geo_city, device_type, browser
                FROM login_records
                WHERE username = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                username,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, created_at, username, success, failure_reason,
                       ip_address, geo_country, geo_city, device_type, browser
                FROM login_records
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )

        items = [
            LoginRecordListItem(
                id=row["id"],
                created_at=row["created_at"],
                username=row["username"],
                success=row["success"],
                failure_reason=row["failure_reason"],
                ip_address=str(row["ip_address"]),
                geo_country=row["geo_country"],
                geo_city=row["geo_city"],
                device_type=row["device_type"],
                browser=row["browser"],
            )
            for row in rows
        ]

        return RecentLoginsResponse(items=items)


async def get_login_stats(user_id: int | None = None, days: int = 30) -> dict:
    """取得登入統計資訊

    Args:
        user_id: 使用者 ID
        days: 統計天數

    Returns:
        統計資訊
    """
    async with get_connection() as conn:
        if user_id:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failure_count,
                    COUNT(DISTINCT ip_address) as unique_ips,
                    COUNT(DISTINCT device_fingerprint) as unique_devices
                FROM login_records
                WHERE user_id = $1
                AND created_at >= NOW() - ($2 || ' days')::INTERVAL
                """,
                user_id,
                days,
            )
        else:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failure_count,
                    COUNT(DISTINCT ip_address) as unique_ips,
                    COUNT(DISTINCT device_fingerprint) as unique_devices
                FROM login_records
                WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL
                """,
                days,
            )

        return {
            "total": stats["total"],
            "success_count": stats["success_count"],
            "failure_count": stats["failure_count"],
            "unique_ips": stats["unique_ips"],
            "unique_devices": stats["unique_devices"],
            "days": days,
        }
