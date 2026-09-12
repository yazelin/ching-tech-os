"""往來與物料模組 API 路由測試。

httpx AsyncClient + ASGI transport，service 層全部 mock。
重點在權限矩陣（每個端點都掃過，數量與 router.routes 對齊）與錯誤碼轉換。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import erp as erp_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services import erp as erp_core

PARTY_ID = uuid4()
CONTACT_ID = uuid4()
ADDRESS_ID = uuid4()
ITEM_ID = uuid4()
WAREHOUSE_ID = uuid4()
PO_ID = uuid4()
AUDIT_ID = uuid4()
NOW = datetime.now(timezone.utc)


def _session(role: str = "user", user_id: int = 2) -> SessionData:
    return SessionData(
        username="admin" if role == "admin" else "user",
        password="xxx",
        nas_host="localhost",
        user_id=user_id,
        created_at=NOW,
        expires_at=NOW,
        role=role,
    )


def _party_detail(**overrides) -> dict:
    base = {
        "id": PARTY_ID,
        "name": "丙丁科技",
        "short_name": "丙丁",
        "aliases": [],
        "is_supplier": True,
        "is_customer": False,
        "tax_id": "12345678",
        "industry": None,
        "payment_terms": None,
        "notes": None,
        "source_ref": None,
        "created_by": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "contacts": [],
        "addresses": [],
        "purchase_orders": [],
        "projects": [],
        "knowledge_count": 0,
    }
    base.update(overrides)
    return base


def _item_detail(**overrides) -> dict:
    base = {
        "id": ITEM_ID,
        "code": "CTOS-A1",
        "name": "不鏽鋼螺絲",
        "spec": None,
        "unit": "支",
        "item_group": None,
        "default_supplier_id": None,
        "default_supplier_name": None,
        "purchase_price": None,
        "lead_days": None,
        "aliases": [],
        "notes": None,
        "source_ref": None,
        "created_by": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "balances": [],
        "total_qty": Decimal("0"),
        "movements": [],
    }
    base.update(overrides)
    return base


def _po_detail(**overrides) -> dict:
    base = {
        "id": PO_ID,
        "po_no": "PO-202609-001",
        "supplier_id": PARTY_ID,
        "supplier_name": "丙丁科技",
        "project_id": None,
        "project_name": None,
        "status": "ordered",
        "order_date": None,
        "expected_date": None,
        "notes": None,
        "created_by": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "lines": [],
        "total_amount": Decimal("0"),
    }
    base.update(overrides)
    return base


def _warehouse(**overrides) -> dict:
    base = {
        "id": WAREHOUSE_ID,
        "code": "MAIN",
        "name": "主倉",
        "created_by": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "audit_id": None,
    }
    base.update(overrides)
    return base


def _make_app(
    *, vendor: bool = True, inventory: bool = True, role: str = "user"
) -> FastAPI:
    """只覆寫兩個 app 權限 dependency，其餘走真的路由邏輯"""
    app = FastAPI()
    app.include_router(erp_api.router)

    def _grant():
        return _session(role)

    def _denied(app_name: str):
        async def _reject():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"無「{app_name}」功能權限",
            )

        return _reject

    app.dependency_overrides[erp_api.require_vendor_access] = (
        _grant if vendor else _denied("廠商管理")
    )
    app.dependency_overrides[erp_api.require_inventory_access] = (
        _grant if inventory else _denied("物料管理")
    )
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# 每個端點一筆：(方法, 路徑, payload, 需要的 app)
_ENDPOINTS = [
    ("get", "/api/parties", None, "vendor"),
    ("post", "/api/parties", {"name": "新廠商"}, "vendor"),
    (
        "post",
        "/api/parties/merge",
        {"keep_id": str(PARTY_ID), "drop_id": str(uuid4())},
        "vendor",
    ),
    ("get", f"/api/parties/{PARTY_ID}", None, "vendor"),
    ("put", f"/api/parties/{PARTY_ID}", {"notes": "x"}, "vendor"),
    ("delete", f"/api/parties/{PARTY_ID}", None, "vendor"),
    ("post", f"/api/parties/{PARTY_ID}/contacts", {"name": "陳先生"}, "vendor"),
    ("post", f"/api/parties/{PARTY_ID}/addresses", {"address": "桃園"}, "vendor"),
    (
        "put",
        f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}",
        {"notes": "x"},
        "vendor",
    ),
    (
        "delete",
        f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}",
        None,
        "vendor",
    ),
    (
        "put",
        f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}",
        {"city": "台北"},
        "vendor",
    ),
    (
        "delete",
        f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}",
        None,
        "vendor",
    ),
    ("get", "/api/items", None, "inventory"),
    ("post", "/api/items", {"code": "A1", "name": "螺絲"}, "inventory"),
    ("get", f"/api/items/{ITEM_ID}", None, "inventory"),
    ("put", f"/api/items/{ITEM_ID}", {"name": "螺絲"}, "inventory"),
    ("delete", f"/api/items/{ITEM_ID}", None, "inventory"),
    ("get", "/api/warehouses", None, "inventory"),
    ("post", "/api/warehouses", {"code": "MAIN", "name": "主倉"}, "inventory"),
    ("put", f"/api/warehouses/{WAREHOUSE_ID}", {"name": "總倉"}, "inventory"),
    ("delete", f"/api/warehouses/{WAREHOUSE_ID}", None, "inventory"),
    ("get", "/api/stock", None, "inventory"),
    (
        "post",
        "/api/stock/adjust",
        {"item_id": str(ITEM_ID), "warehouse_id": str(WAREHOUSE_ID), "qty_delta": 1},
        "inventory",
    ),
    (
        "post",
        "/api/stock/transfer",
        {
            "item_id": str(ITEM_ID),
            "from_warehouse_id": str(WAREHOUSE_ID),
            "to_warehouse_id": str(uuid4()),
            "qty": 1,
        },
        "inventory",
    ),
    ("get", "/api/purchase-orders", None, "inventory"),
    (
        "post",
        "/api/purchase-orders",
        {"supplier_id": str(PARTY_ID), "lines": [{"item_id": str(ITEM_ID), "qty": 1}]},
        "inventory",
    ),
    ("get", f"/api/purchase-orders/{PO_ID}", None, "inventory"),
    ("put", f"/api/purchase-orders/{PO_ID}", {"notes": "x"}, "inventory"),
    ("post", f"/api/purchase-orders/{PO_ID}/receive", {"all": True}, "inventory"),
    ("post", f"/api/purchase-orders/{PO_ID}/cancel", {"reason": "x"}, "inventory"),
]


# ============================================================
# 權限矩陣
# ============================================================


@pytest.mark.asyncio
async def test_endpoint_list_covers_every_route() -> None:
    """加了端點忘了補這份清單會直接紅"""
    assert len(_ENDPOINTS) == len(erp_api.router.routes)


@pytest.mark.asyncio
async def test_no_app_permission_is_rejected() -> None:
    """沒有對應 app 權限的使用者：每個端點都 403，訊息指到正確的 app"""
    app = _make_app(vendor=False, inventory=False)
    async with _client(app) as client:
        for method, url, payload, required in _ENDPOINTS:
            resp = await getattr(client, method)(
                url, **({"json": payload} if payload is not None else {})
            )
            assert resp.status_code == 403, f"{method.upper()} {url}"
            expected = "廠商管理" if required == "vendor" else "物料管理"
            assert expected in resp.json()["detail"], f"{method.upper()} {url}"


@pytest.mark.asyncio
async def test_vendor_permission_does_not_open_inventory() -> None:
    """兩個 app 權限各管各的：只有廠商管理時碰不到物料端點"""
    app = _make_app(vendor=True, inventory=False)
    async with _client(app) as client:
        resp = await client.get("/api/items")
    assert resp.status_code == 403
    assert "物料管理" in resp.json()["detail"]


# ============================================================
# 往來對象
# ============================================================


@pytest.mark.asyncio
async def test_list_parties(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "list_parties",
        AsyncMock(
            return_value={
                "items": [
                    {
                        "id": PARTY_ID,
                        "name": "丙丁科技",
                        "is_supplier": True,
                        "is_customer": False,
                        "created_at": NOW,
                        "updated_at": NOW,
                    }
                ],
                "total": 1,
            }
        ),
    )
    async with _client(_make_app()) as client:
        resp = await client.get("/api/parties?q=丙丁&role=supplier")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_parties_role_both(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "list_parties",
        AsyncMock(return_value={"items": [], "total": 0}),
    )
    async with _client(_make_app()) as client:
        resp = await client.get("/api/parties?role=both")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_parties_invalid_role_is_422(monkeypatch) -> None:
    """role 不再靜默回空清單，無效值直接 422"""
    list_parties = AsyncMock()
    monkeypatch.setattr(erp_api.party_service, "list_parties", list_parties)
    async with _client(_make_app()) as client:
        resp = await client.get("/api/parties?role=vendor")
    assert resp.status_code == 422
    list_parties.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_party(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "create_party",
        AsyncMock(return_value={"id": PARTY_ID, "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.party_service,
        "get_party_detail",
        AsyncMock(return_value=_party_detail()),
    )
    async with _client(_make_app()) as client:
        resp = await client.post("/api/parties", json={"name": "丙丁科技"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "丙丁科技"
    # F2：寫入端點要把稽核 id 回給呼叫端
    assert resp.json()["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_create_party_service_error(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "create_party",
        AsyncMock(side_effect=erp_core.InvalidOperationError("壞了")),
    )
    async with _client(_make_app()) as client:
        resp = await client.post("/api/parties", json={"name": "丙丁"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "壞了"


@pytest.mark.asyncio
async def test_get_party_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "get_party_detail", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.get(f"/api/parties/{PARTY_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_party_detail_has_no_audit_id(monkeypatch) -> None:
    """F2：只有寫入才有 audit_id，GET 明細是 null"""
    monkeypatch.setattr(
        erp_api.party_service,
        "get_party_detail",
        AsyncMock(return_value=_party_detail()),
    )
    async with _client(_make_app()) as client:
        resp = await client.get(f"/api/parties/{PARTY_ID}")
    assert resp.status_code == 200
    assert resp.json()["audit_id"] is None


@pytest.mark.asyncio
async def test_update_party_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "update_party", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.put(f"/api/parties/{PARTY_ID}", json={"notes": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_party(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "update_party",
        AsyncMock(return_value={"id": PARTY_ID, "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.party_service,
        "get_party_detail",
        AsyncMock(return_value=_party_detail(notes="改過")),
    )
    async with _client(_make_app()) as client:
        resp = await client.put(f"/api/parties/{PARTY_ID}", json={"notes": "改過"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "改過"
    assert resp.json()["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_update_party_rejects_null_on_not_null_field() -> None:
    async with _client(_make_app()) as client:
        resp = await client.put(f"/api/parties/{PARTY_ID}", json={"name": None})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_party_is_soft(monkeypatch) -> None:
    delete = AsyncMock(return_value=AUDIT_ID)
    monkeypatch.setattr(erp_api.party_service, "delete_party", delete)
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/parties/{PARTY_ID}")
    assert resp.status_code == 200
    assert resp.json()["audit_id"] == str(AUDIT_ID)
    assert delete.await_args.kwargs["via"] == "rest"


@pytest.mark.asyncio
async def test_delete_party_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "delete_party", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/parties/{PARTY_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_contact_and_address(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "add_contact",
        AsyncMock(return_value={"id": uuid4(), "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.party_service,
        "add_address",
        AsyncMock(return_value={"id": uuid4(), "audit_id": AUDIT_ID}),
    )
    async with _client(_make_app()) as client:
        contact = await client.post(
            f"/api/parties/{PARTY_ID}/contacts", json={"name": "陳先生"}
        )
        address = await client.post(
            f"/api/parties/{PARTY_ID}/addresses", json={"address": "桃園"}
        )
    assert contact.status_code == 201 and address.status_code == 201


@pytest.mark.asyncio
async def test_add_contact_and_address_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "add_contact", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        erp_api.party_service, "add_address", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        contact = await client.post(
            f"/api/parties/{PARTY_ID}/contacts", json={"name": "陳先生"}
        )
        address = await client.post(
            f"/api/parties/{PARTY_ID}/addresses", json={"address": "桃園"}
        )
    assert contact.status_code == 404 and address.status_code == 404


def _contact_row(**overrides) -> dict:
    base = {
        "id": CONTACT_ID,
        "party_id": PARTY_ID,
        "name": "陳先生",
        "title": None,
        "phone": None,
        "mobile": None,
        "email": None,
        "is_primary": False,
        "notes": None,
        "created_at": NOW,
        "updated_at": NOW,
        "audit_id": AUDIT_ID,
    }
    base.update(overrides)
    return base


def _address_row(**overrides) -> dict:
    base = {
        "id": ADDRESS_ID,
        "party_id": PARTY_ID,
        "label": "公司",
        "address": "桃園",
        "city": None,
        "is_primary": False,
        "created_at": NOW,
        "updated_at": NOW,
        "audit_id": AUDIT_ID,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_update_party_contact(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "update_contact",
        AsyncMock(return_value=_contact_row(notes="改過")),
    )
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}", json={"notes": "改過"}
        )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "改過"
    assert resp.json()["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_update_party_contact_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "update_contact", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}", json={"notes": "x"}
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_party_contact_rejects_null_on_not_null_field() -> None:
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}", json={"name": None}
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_party_contact(monkeypatch) -> None:
    delete = AsyncMock(return_value=AUDIT_ID)
    monkeypatch.setattr(erp_api.party_service, "delete_contact", delete)
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}")
    assert resp.status_code == 200
    assert resp.json()["audit_id"] == str(AUDIT_ID)
    assert delete.await_args.kwargs["via"] == "rest"


@pytest.mark.asyncio
async def test_delete_party_contact_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "delete_contact", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/parties/{PARTY_ID}/contacts/{CONTACT_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_party_address(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "update_address",
        AsyncMock(return_value=_address_row(city="台北")),
    )
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}", json={"city": "台北"}
        )
    assert resp.status_code == 200
    assert resp.json()["city"] == "台北"
    assert resp.json()["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_update_party_address_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "update_address", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}", json={"city": "台北"}
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_party_address_rejects_null_on_not_null_field() -> None:
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}",
            json={"address": None},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_party_address(monkeypatch) -> None:
    delete = AsyncMock(return_value=AUDIT_ID)
    monkeypatch.setattr(erp_api.party_service, "delete_address", delete)
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}")
    assert resp.status_code == 200
    assert resp.json()["audit_id"] == str(AUDIT_ID)
    assert delete.await_args.kwargs["via"] == "rest"


@pytest.mark.asyncio
async def test_delete_party_address_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service, "delete_address", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/parties/{PARTY_ID}/addresses/{ADDRESS_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_merge_route_not_swallowed_by_party_id(monkeypatch) -> None:
    """/merge 宣告在 /{party_id} 之前，不能被當成 id"""
    merge = AsyncMock(return_value={"id": PARTY_ID, "audit_id": AUDIT_ID})
    detail = AsyncMock(return_value=_party_detail())
    monkeypatch.setattr(erp_api.party_service, "merge_parties", merge)
    monkeypatch.setattr(erp_api.party_service, "get_party_detail", detail)

    async with _client(_make_app()) as client:
        resp = await client.post(
            "/api/parties/merge",
            json={"keep_id": str(PARTY_ID), "drop_id": str(uuid4())},
        )
    assert resp.status_code == 200
    merge.assert_awaited()
    assert resp.json()["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_merge_conflict_is_400(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.party_service,
        "merge_parties",
        AsyncMock(side_effect=erp_core.InvalidOperationError("不能合併自己")),
    )
    async with _client(_make_app()) as client:
        resp = await client.post(
            "/api/parties/merge",
            json={"keep_id": str(PARTY_ID), "drop_id": str(PARTY_ID)},
        )
    assert resp.status_code == 400


# ============================================================
# 物料、倉庫、庫存
# ============================================================


@pytest.mark.asyncio
async def test_item_crud(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "list_items",
        AsyncMock(return_value={"items": [], "total": 0}),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "create_item",
        AsyncMock(return_value={"id": ITEM_ID, "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "get_item_detail",
        AsyncMock(return_value=_item_detail()),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "update_item",
        AsyncMock(return_value={"id": ITEM_ID, "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.inventory_service, "delete_item", AsyncMock(return_value=AUDIT_ID)
    )

    async with _client(_make_app()) as client:
        assert (await client.get("/api/items")).status_code == 200
        created = await client.post(
            "/api/items", json={"code": "CTOS-A1", "name": "不鏽鋼螺絲"}
        )
        assert created.status_code == 201
        assert created.json()["audit_id"] == str(AUDIT_ID)
        assert (await client.get(f"/api/items/{ITEM_ID}")).status_code == 200
        assert (
            await client.put(f"/api/items/{ITEM_ID}", json={"name": "螺絲"})
        ).status_code == 200
        assert (await client.delete(f"/api/items/{ITEM_ID}")).status_code == 200


@pytest.mark.asyncio
async def test_item_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "create_item",
        AsyncMock(side_effect=erp_core.InvalidOperationError("料號已存在：A1")),
    )
    monkeypatch.setattr(
        erp_api.inventory_service, "update_item", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        erp_api.inventory_service, "delete_item", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        erp_api.inventory_service, "get_item_detail", AsyncMock(return_value=None)
    )

    async with _client(_make_app()) as client:
        assert (
            await client.post("/api/items", json={"code": "A1", "name": "x"})
        ).status_code == 400
        assert (
            await client.put(f"/api/items/{ITEM_ID}", json={"name": "x"})
        ).status_code == 404
        assert (await client.delete(f"/api/items/{ITEM_ID}")).status_code == 404
        assert (await client.get(f"/api/items/{ITEM_ID}")).status_code == 404


@pytest.mark.asyncio
async def test_warehouse_crud(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "list_warehouses",
        AsyncMock(return_value={"items": [_warehouse()], "total": 1}),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "create_warehouse",
        AsyncMock(return_value=_warehouse(audit_id=AUDIT_ID)),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "update_warehouse",
        AsyncMock(return_value=_warehouse(name="總倉", audit_id=AUDIT_ID)),
    )
    monkeypatch.setattr(
        erp_api.inventory_service, "delete_warehouse", AsyncMock(return_value=AUDIT_ID)
    )

    async with _client(_make_app()) as client:
        assert (await client.get("/api/warehouses")).json()["total"] == 1
        created = await client.post(
            "/api/warehouses", json={"code": "MAIN", "name": "主倉"}
        )
        assert created.status_code == 201
        assert created.json()["audit_id"] == str(AUDIT_ID)
        updated = await client.put(
            f"/api/warehouses/{WAREHOUSE_ID}", json={"name": "總倉"}
        )
        assert updated.json()["name"] == "總倉"
        assert updated.json()["audit_id"] == str(AUDIT_ID)
        assert (
            await client.delete(f"/api/warehouses/{WAREHOUSE_ID}")
        ).status_code == 200


@pytest.mark.asyncio
async def test_warehouse_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "create_warehouse",
        AsyncMock(side_effect=erp_core.InvalidOperationError("倉庫代碼已存在：MAIN")),
    )
    monkeypatch.setattr(
        erp_api.inventory_service, "update_warehouse", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "delete_warehouse",
        AsyncMock(side_effect=erp_core.InvalidOperationError("倉庫還有庫存餘額，不能刪除")),
    )

    async with _client(_make_app()) as client:
        assert (
            await client.post("/api/warehouses", json={"code": "MAIN", "name": "主倉"})
        ).status_code == 400
        assert (
            await client.put(f"/api/warehouses/{WAREHOUSE_ID}", json={"name": "x"})
        ).status_code == 404
        assert (
            await client.delete(f"/api/warehouses/{WAREHOUSE_ID}")
        ).status_code == 400


@pytest.mark.asyncio
async def test_update_warehouse_duplicate_code_is_400(monkeypatch) -> None:
    """F3"""
    monkeypatch.setattr(
        erp_api.inventory_service,
        "update_warehouse",
        AsyncMock(side_effect=erp_core.InvalidOperationError("倉庫代碼已存在：SUB")),
    )
    async with _client(_make_app()) as client:
        resp = await client.put(f"/api/warehouses/{WAREHOUSE_ID}", json={"code": "SUB"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_warehouse_404(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service, "delete_warehouse", AsyncMock(return_value=None)
    )
    async with _client(_make_app()) as client:
        resp = await client.delete(f"/api/warehouses/{WAREHOUSE_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stock_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "get_stock",
        AsyncMock(return_value={"items": [], "total": 0}),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "adjust_stock",
        AsyncMock(
            return_value={"audit_id": AUDIT_ID, "balances": [{"qty": Decimal("10")}]}
        ),
    )
    monkeypatch.setattr(
        erp_api.inventory_service,
        "transfer_stock",
        AsyncMock(
            return_value={
                "audit_id": AUDIT_ID,
                "balances": [
                    {"warehouse_id": WAREHOUSE_ID, "qty": Decimal("70")},
                    {"warehouse_id": uuid4(), "qty": Decimal("30")},
                ],
            }
        ),
    )

    async with _client(_make_app()) as client:
        assert (await client.get("/api/stock")).status_code == 200
        adjusted = await client.post(
            "/api/stock/adjust",
            json={
                "item_id": str(ITEM_ID),
                "warehouse_id": str(WAREHOUSE_ID),
                "qty_delta": 10,
                "reason": "receipt",
            },
        )
        assert adjusted.json()["qty_after"] == "10"
        transferred = await client.post(
            "/api/stock/transfer",
            json={
                "item_id": str(ITEM_ID),
                "from_warehouse_id": str(WAREHOUSE_ID),
                "to_warehouse_id": str(uuid4()),
                "qty": 30,
            },
        )
        assert len(transferred.json()["balances"]) == 2


@pytest.mark.asyncio
async def test_stock_adjust_negative_is_400(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "adjust_stock",
        AsyncMock(
            side_effect=erp_core.NegativeStockError(
                ITEM_ID, WAREHOUSE_ID, Decimal("3"), Decimal("-5")
            )
        ),
    )
    async with _client(_make_app()) as client:
        resp = await client.post(
            "/api/stock/adjust",
            json={
                "item_id": str(ITEM_ID),
                "warehouse_id": str(WAREHOUSE_ID),
                "qty_delta": -5,
            },
        )
    assert resp.status_code == 400
    assert "庫存不足" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_stock_transfer_error_is_400(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.inventory_service,
        "transfer_stock",
        AsyncMock(side_effect=erp_core.InvalidOperationError("來源倉與目的倉不能相同")),
    )
    async with _client(_make_app()) as client:
        resp = await client.post(
            "/api/stock/transfer",
            json={
                "item_id": str(ITEM_ID),
                "from_warehouse_id": str(WAREHOUSE_ID),
                "to_warehouse_id": str(WAREHOUSE_ID),
                "qty": 1,
            },
        )
    assert resp.status_code == 400


# ============================================================
# 採購單
# ============================================================


@pytest.mark.asyncio
async def test_purchase_order_flow(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "list_purchase_orders",
        AsyncMock(return_value={"items": [], "total": 0}),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "create_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value=_po_detail()),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "update_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "receive_purchase_order",
        AsyncMock(return_value={"status": "received", "audit_id": AUDIT_ID}),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "cancel_purchase_order",
        AsyncMock(return_value={"status": "cancelled", "audit_id": AUDIT_ID}),
    )

    async with _client(_make_app()) as client:
        assert (await client.get("/api/purchase-orders")).status_code == 200
        created = await client.post(
            "/api/purchase-orders",
            json={
                "supplier_id": str(PARTY_ID),
                "lines": [{"item_id": str(ITEM_ID), "qty": 10, "unit_price": 5}],
            },
        )
        assert created.status_code == 201
        assert created.json()["po_no"] == "PO-202609-001"
        assert created.json()["audit_id"] == str(AUDIT_ID)
        assert (await client.get(f"/api/purchase-orders/{PO_ID}")).status_code == 200
        assert (
            await client.put(f"/api/purchase-orders/{PO_ID}", json={"notes": "急件"})
        ).status_code == 200
        received = await client.post(
            f"/api/purchase-orders/{PO_ID}/receive", json={"all": True}
        )
        assert received.json()["status"] == "received"
        cancelled = await client.post(
            f"/api/purchase-orders/{PO_ID}/cancel", json={"reason": "改採別家"}
        )
        assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_create_purchase_order_rejects_import_only_fields(monkeypatch) -> None:
    """`po_no` 與行項 `received_qty` 只給匯入腳本用，REST 送進來要 422

    不擋的話 pydantic 預設會靜默丟掉，呼叫端會以為自己指定得了單號。
    """
    created = AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-001"})
    monkeypatch.setattr(
        erp_api.purchasing_service, "create_purchase_order", created
    )

    async with _client(_make_app()) as client:
        with_po_no = await client.post(
            "/api/purchase-orders",
            json={
                "supplier_id": str(PARTY_ID),
                "po_no": "PUR-ORD-TEST-00001",
                "lines": [{"item_id": str(ITEM_ID), "qty": 10}],
            },
        )
        with_received = await client.post(
            "/api/purchase-orders",
            json={
                "supplier_id": str(PARTY_ID),
                "lines": [{"item_id": str(ITEM_ID), "qty": 10, "received_qty": 3}],
            },
        )

    assert with_po_no.status_code == 422
    assert with_received.status_code == 422
    created.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_purchase_orders_passes_since(monkeypatch) -> None:
    """F11"""
    from datetime import date

    listed = AsyncMock(return_value={"items": [], "total": 0})
    monkeypatch.setattr(erp_api.purchasing_service, "list_purchase_orders", listed)

    async with _client(_make_app()) as client:
        resp = await client.get("/api/purchase-orders?since=2026-09-01&status=ordered")

    assert resp.status_code == 200
    assert listed.await_args.kwargs["since"] == date(2026, 9, 1)
    assert listed.await_args.kwargs["status"] == "ordered"


@pytest.mark.asyncio
async def test_receive_passes_line_id(monkeypatch) -> None:
    """F1：REST 也要把 line_id 傳到 service"""
    line_id = uuid4()
    receive = AsyncMock(return_value={"status": "partial", "audit_id": AUDIT_ID})
    monkeypatch.setattr(erp_api.purchasing_service, "receive_purchase_order", receive)

    async with _client(_make_app()) as client:
        resp = await client.post(
            f"/api/purchase-orders/{PO_ID}/receive",
            json={"lines": [{"line_id": str(line_id), "qty": 4}]},
        )

    assert resp.status_code == 200
    assert receive.await_args.kwargs["lines"][0]["line_id"] == line_id


@pytest.mark.asyncio
async def test_receive_line_requires_line_or_item() -> None:
    async with _client(_make_app()) as client:
        resp = await client.post(
            f"/api/purchase-orders/{PO_ID}/receive", json={"lines": [{"qty": 4}]}
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_receive_ambiguous_line_is_409(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "receive_purchase_order",
        AsyncMock(
            side_effect=erp_core.AmbiguousError(
                "採購單行項", str(ITEM_ID), [{"line_id": str(uuid4())}]
            )
        ),
    )
    async with _client(_make_app()) as client:
        resp = await client.post(
            f"/api/purchase-orders/{PO_ID}/receive",
            json={"lines": [{"item_id": str(ITEM_ID), "qty": 1}]},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_purchase_order_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "create_purchase_order",
        AsyncMock(side_effect=erp_core.InvalidOperationError("供應商不存在或已刪除")),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "update_purchase_order",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "receive_purchase_order",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "cancel_purchase_order",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service, "get_purchase_order", AsyncMock(return_value=None)
    )

    async with _client(_make_app()) as client:
        assert (
            await client.post(
                "/api/purchase-orders",
                json={
                    "supplier_id": str(PARTY_ID),
                    "lines": [{"item_id": str(ITEM_ID), "qty": 1}],
                },
            )
        ).status_code == 400
        assert (
            await client.put(f"/api/purchase-orders/{PO_ID}", json={"notes": "x"})
        ).status_code == 404
        assert (
            await client.post(f"/api/purchase-orders/{PO_ID}/receive", json={"all": True})
        ).status_code == 404
        assert (
            await client.post(f"/api/purchase-orders/{PO_ID}/cancel", json={})
        ).status_code == 404
        assert (await client.get(f"/api/purchase-orders/{PO_ID}")).status_code == 404


@pytest.mark.asyncio
async def test_receive_and_cancel_invalid_state(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "receive_purchase_order",
        AsyncMock(side_effect=erp_core.InvalidOperationError("採購單狀態為 cancelled，不能收貨")),
    )
    monkeypatch.setattr(
        erp_api.purchasing_service,
        "cancel_purchase_order",
        AsyncMock(side_effect=erp_core.InvalidOperationError("已收過貨的採購單不能取消，請先做庫存調整")),
    )
    async with _client(_make_app()) as client:
        received = await client.post(
            f"/api/purchase-orders/{PO_ID}/receive", json={"all": True}
        )
        cancelled = await client.post(
            f"/api/purchase-orders/{PO_ID}/cancel", json={"reason": "x"}
        )
    assert received.status_code == 400
    assert cancelled.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ["received", "cancelled", "partial"])
async def test_put_purchase_order_rejects_computed_status(bad_status) -> None:
    """F10：收貨與取消不能用 PUT status 走後門"""
    async with _client(_make_app()) as client:
        resp = await client.put(
            f"/api/purchase-orders/{PO_ID}", json={"status": bad_status}
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_purchase_order_create_requires_lines() -> None:
    async with _client(_make_app()) as client:
        resp = await client.post(
            "/api/purchase-orders", json={"supplier_id": str(PARTY_ID), "lines": []}
        )
    assert resp.status_code == 422


def test_http_error_maps_not_found_and_ambiguous() -> None:
    assert (
        erp_api._http_error(erp_core.NotFoundError("物料", "x")).status_code == 404
    )
    assert (
        erp_api._http_error(
            erp_core.AmbiguousError("物料", "x", [{"id": ITEM_ID}])
        ).status_code
        == 409
    )
