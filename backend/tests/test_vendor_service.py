"""vendor service 測試。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.models.vendor import VendorCreate, VendorUpdate
from ching_tech_os.services import vendor


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _row(**kwargs):
    now = datetime.now()
    base = {
        "id": uuid4(),
        "erp_code": "V001",
        "name": "Vendor A",
        "short_name": "VA",
        "contact_person": "Tom",
        "phone": "123",
        "fax": None,
        "email": None,
        "address": None,
        "tax_id": None,
        "payment_terms": None,
        "notes": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": "admin",
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_vendor_crud_happy_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_row()])
    conn.fetchval = AsyncMock(side_effect=[1, 0, 1, 0])
    conn.fetchrow = AsyncMock(return_value=_row())
    conn.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(vendor, "get_connection", lambda: _CM(conn))

    result = await vendor.list_vendors(query="V", active_only=True, limit=10)
    assert result.total >= 0

    got = await vendor.get_vendor(uuid4())
    assert got.name == "Vendor A"

    by_code = await vendor.get_vendor_by_erp_code("V001")
    assert by_code is not None

    created = await vendor.create_vendor(VendorCreate(name="New", erp_code="V100"), created_by="u1")
    assert created.erp_code == "V001"

    updated = await vendor.update_vendor(uuid4(), VendorUpdate(name="Updated"))
    assert updated.name == "Vendor A"

    deactivated = await vendor.deactivate_vendor(uuid4())
    assert deactivated.is_active is True
    activated = await vendor.activate_vendor(uuid4())
    assert activated.is_active is True


@pytest.mark.asyncio
async def test_vendor_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(vendor, "get_connection", lambda: _CM(conn))

    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(vendor.VendorNotFoundError):
        await vendor.get_vendor(uuid4())
    assert await vendor.get_vendor_by_erp_code("NA") is None

    conn.fetchval = AsyncMock(return_value=1)
    with pytest.raises(vendor.VendorDuplicateError):
        await vendor.create_vendor(VendorCreate(name="Dup", erp_code="DUP"))

    conn.fetchval = AsyncMock(return_value=0)
    with pytest.raises(vendor.VendorNotFoundError):
        await vendor.update_vendor(uuid4(), VendorUpdate(name="x"))

    conn.fetchval = AsyncMock(side_effect=[1, 1])
    with pytest.raises(vendor.VendorDuplicateError):
        await vendor.update_vendor(uuid4(), VendorUpdate(erp_code="DUP"))

    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(vendor.VendorNotFoundError):
        await vendor.deactivate_vendor(uuid4())
    with pytest.raises(vendor.VendorNotFoundError):
        await vendor.activate_vendor(uuid4())
