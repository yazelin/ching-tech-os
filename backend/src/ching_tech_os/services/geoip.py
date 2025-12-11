"""GeoIP 地理位置解析服務"""

import ipaddress
import os
from decimal import Decimal
from pathlib import Path

from user_agents import parse as parse_user_agent

from ..models.login_record import DeviceInfo, DeviceType, GeoLocation

# GeoIP 資料庫路徑
GEOIP_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "GeoLite2-City.mmdb"

# GeoIP reader（延遲載入）
_geoip_reader = None


def _get_geoip_reader():
    """取得 GeoIP reader（延遲載入）"""
    global _geoip_reader
    if _geoip_reader is None:
        if GEOIP_DB_PATH.exists():
            try:
                import geoip2.database

                _geoip_reader = geoip2.database.Reader(str(GEOIP_DB_PATH))
            except Exception as e:
                print(f"Warning: Failed to load GeoIP database: {e}")
                _geoip_reader = False  # 標記為載入失敗
        else:
            print(f"Warning: GeoIP database not found at {GEOIP_DB_PATH}")
            _geoip_reader = False

    return _geoip_reader if _geoip_reader else None


def is_private_ip(ip_str: str) -> bool:
    """檢查是否為內網 IP

    Args:
        ip_str: IP 位址字串

    Returns:
        是否為內網 IP
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def resolve_ip_location(ip_address: str) -> GeoLocation | None:
    """解析 IP 地理位置

    Args:
        ip_address: IP 位址

    Returns:
        地理位置資訊或 None
    """
    # 內網 IP 無法解析
    if is_private_ip(ip_address):
        return None

    reader = _get_geoip_reader()
    if reader is None:
        return None

    try:
        response = reader.city(ip_address)
        return GeoLocation(
            country=response.country.names.get("zh-CN") or response.country.name,
            city=response.city.names.get("zh-CN") or response.city.name,
            latitude=Decimal(str(response.location.latitude)) if response.location.latitude else None,
            longitude=Decimal(str(response.location.longitude)) if response.location.longitude else None,
        )
    except Exception as e:
        # IP 不在資料庫中或其他錯誤
        print(f"GeoIP lookup failed for {ip_address}: {e}")
        return None


def parse_device_info(user_agent: str) -> DeviceInfo:
    """解析 User-Agent 取得裝置資訊

    Args:
        user_agent: User-Agent 字串

    Returns:
        裝置資訊
    """
    ua = parse_user_agent(user_agent)

    # 判斷裝置類型
    if ua.is_mobile:
        device_type = DeviceType.MOBILE
    elif ua.is_tablet:
        device_type = DeviceType.TABLET
    elif ua.is_pc:
        device_type = DeviceType.DESKTOP
    else:
        device_type = DeviceType.UNKNOWN

    # 組合瀏覽器資訊
    browser = ua.browser.family
    if ua.browser.version_string:
        browser = f"{browser} {ua.browser.version_string}"

    # 組合 OS 資訊
    os_info = ua.os.family
    if ua.os.version_string:
        os_info = f"{os_info} {ua.os.version_string}"

    return DeviceInfo(
        fingerprint=None,  # 由前端提供
        device_type=device_type,
        browser=browser,
        os=os_info,
    )


def close_geoip_reader():
    """關閉 GeoIP reader"""
    global _geoip_reader
    if _geoip_reader and _geoip_reader is not False:
        _geoip_reader.close()
        _geoip_reader = None
