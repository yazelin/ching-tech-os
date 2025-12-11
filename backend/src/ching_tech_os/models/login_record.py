"""登入記錄相關資料模型"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    """裝置類型"""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    UNKNOWN = "unknown"


class GeoLocation(BaseModel):
    """地理位置資訊"""

    country: str | None = None
    city: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class DeviceInfo(BaseModel):
    """裝置資訊"""

    fingerprint: str | None = None
    device_type: DeviceType = DeviceType.UNKNOWN
    browser: str | None = None
    os: str | None = None


class LoginRecordCreate(BaseModel):
    """建立登入記錄請求（內部使用）"""

    user_id: int | None = None
    username: str = Field(..., max_length=100)
    success: bool
    failure_reason: str | None = Field(None, max_length=200)
    ip_address: str
    user_agent: str | None = None
    geo: GeoLocation | None = None
    device: DeviceInfo | None = None
    session_id: str | None = Field(None, max_length=100)


class LoginRecordResponse(BaseModel):
    """登入記錄回應"""

    id: int
    created_at: datetime
    user_id: int | None
    username: str
    success: bool
    failure_reason: str | None
    ip_address: str
    user_agent: str | None
    geo_country: str | None
    geo_city: str | None
    geo_latitude: Decimal | None
    geo_longitude: Decimal | None
    device_fingerprint: str | None
    device_type: str | None
    browser: str | None
    os: str | None
    session_id: str | None


class LoginRecordListItem(BaseModel):
    """登入記錄列表項目（簡化版）"""

    id: int
    created_at: datetime
    username: str
    success: bool
    failure_reason: str | None
    ip_address: str
    geo_country: str | None
    geo_city: str | None
    device_type: str | None
    browser: str | None


class LoginRecordListResponse(BaseModel):
    """登入記錄列表回應（含分頁）"""

    items: list[LoginRecordListItem]
    total: int
    page: int
    limit: int
    total_pages: int


class LoginRecordFilter(BaseModel):
    """登入記錄查詢條件"""

    user_id: int | None = None
    username: str | None = None
    success: bool | None = None
    ip_address: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    device_fingerprint: str | None = None
    page: int = 1
    limit: int = 20


class RecentLoginsResponse(BaseModel):
    """最近登入回應"""

    items: list[LoginRecordListItem]


# 前端傳送的裝置資訊（登入時）
class LoginDeviceInfo(BaseModel):
    """登入時前端傳送的裝置資訊"""

    fingerprint: str | None = None
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    screen_resolution: str | None = None
    timezone: str | None = None
    language: str | None = None
