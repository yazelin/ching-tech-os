"""geoip 服務測試。"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

import ching_tech_os.services.geoip as geoip


@pytest.fixture(autouse=True)
def _reset_geoip_reader_state():
    geoip._geoip_reader = None
    yield
    geoip._geoip_reader = None


def test_get_geoip_reader_db_not_found(tmp_path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "missing.mmdb"
    monkeypatch.setattr(geoip, "GEOIP_DB_PATH", db_path)

    assert geoip._get_geoip_reader() is None
    assert geoip._geoip_reader is False


def test_get_geoip_reader_success(tmp_path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "GeoLite2-City.mmdb"
    db_path.write_bytes(b"fake")
    monkeypatch.setattr(geoip, "GEOIP_DB_PATH", db_path)

    fake_reader = object()
    geoip2_module = ModuleType("geoip2")
    database_module = ModuleType("geoip2.database")
    database_module.Reader = lambda _path: fake_reader
    geoip2_module.database = database_module
    monkeypatch.setitem(sys.modules, "geoip2", geoip2_module)
    monkeypatch.setitem(sys.modules, "geoip2.database", database_module)

    assert geoip._get_geoip_reader() is fake_reader
    # 第二次應命中快取
    assert geoip._get_geoip_reader() is fake_reader


def test_get_geoip_reader_load_failed(tmp_path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "GeoLite2-City.mmdb"
    db_path.write_bytes(b"fake")
    monkeypatch.setattr(geoip, "GEOIP_DB_PATH", db_path)

    def _raise(_path: str):
        raise RuntimeError("boom")

    geoip2_module = ModuleType("geoip2")
    database_module = ModuleType("geoip2.database")
    database_module.Reader = _raise
    geoip2_module.database = database_module
    monkeypatch.setitem(sys.modules, "geoip2", geoip2_module)
    monkeypatch.setitem(sys.modules, "geoip2.database", database_module)

    assert geoip._get_geoip_reader() is None
    assert geoip._geoip_reader is False


def test_is_private_ip_and_invalid():
    assert geoip.is_private_ip("127.0.0.1") is True
    assert geoip.is_private_ip("10.0.0.1") is True
    assert geoip.is_private_ip("8.8.8.8") is False
    assert geoip.is_private_ip("bad-ip") is False


def test_resolve_ip_location_success(monkeypatch: pytest.MonkeyPatch):
    response = SimpleNamespace(
        country=SimpleNamespace(names={"zh-CN": "台灣"}, name="Taiwan"),
        city=SimpleNamespace(names={"zh-CN": "台北"}, name="Taipei"),
        location=SimpleNamespace(latitude=25.033, longitude=121.5654),
    )
    reader = SimpleNamespace(city=lambda _ip: response)
    monkeypatch.setattr(geoip, "_get_geoip_reader", lambda: reader)

    result = geoip.resolve_ip_location("8.8.8.8")
    assert result is not None
    assert result.country == "台灣"
    assert result.city == "台北"
    assert str(result.latitude) == "25.033"
    assert str(result.longitude) == "121.5654"


def test_resolve_ip_location_fallback_and_errors(monkeypatch: pytest.MonkeyPatch):
    # 內網 IP 不解析
    assert geoip.resolve_ip_location("192.168.1.2") is None

    # 無 reader
    monkeypatch.setattr(geoip, "_get_geoip_reader", lambda: None)
    assert geoip.resolve_ip_location("1.1.1.1") is None

    # 查詢例外
    class _BadReader:
        def city(self, _ip):
            raise RuntimeError("not found")

    monkeypatch.setattr(geoip, "_get_geoip_reader", lambda: _BadReader())
    assert geoip.resolve_ip_location("8.8.4.4") is None


def test_parse_device_info(monkeypatch: pytest.MonkeyPatch):
    mobile_ua = SimpleNamespace(
        is_mobile=True,
        is_tablet=False,
        is_pc=False,
        browser=SimpleNamespace(family="Chrome", version_string="120"),
        os=SimpleNamespace(family="Android", version_string="14"),
    )
    monkeypatch.setattr(geoip, "parse_user_agent", lambda _ua: mobile_ua)
    mobile_info = geoip.parse_device_info("ua")
    assert mobile_info.device_type.value == "mobile"
    assert mobile_info.browser == "Chrome 120"
    assert mobile_info.os == "Android 14"

    unknown_ua = SimpleNamespace(
        is_mobile=False,
        is_tablet=False,
        is_pc=False,
        browser=SimpleNamespace(family="UnknownBrowser", version_string=""),
        os=SimpleNamespace(family="UnknownOS", version_string=""),
    )
    monkeypatch.setattr(geoip, "parse_user_agent", lambda _ua: unknown_ua)
    unknown_info = geoip.parse_device_info("ua")
    assert unknown_info.device_type.value == "unknown"
    assert unknown_info.browser == "UnknownBrowser"
    assert unknown_info.os == "UnknownOS"


def test_close_geoip_reader():
    reader = Mock()
    geoip._geoip_reader = reader
    geoip.close_geoip_reader()
    reader.close.assert_called_once()
    assert geoip._geoip_reader is None

    geoip._geoip_reader = False
    geoip.close_geoip_reader()
    assert geoip._geoip_reader is False
