"""inventory service 高覆蓋 smoke 測試。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ching_tech_os.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryOrderCreate,
    InventoryOrderUpdate,
    InventoryTransactionCreate,
    TransactionType,
)
from ching_tech_os.services import inventory


class _DummyModel(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, item):
        return self.get(item)


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


class _Row(dict):
    def __getitem__(self, key):
        return self.get(key)


class _Conn:
    def __init__(self, row: _Row):
        self.row = row

    async def fetch(self, sql: str, *_args):
        if "LIMIT 5" in sql:  # find_item_by_id_or_name name 查詢
            return [self.row]
        return [self.row]

    async def fetchrow(self, sql: str, *_args):
        # 建立/更新物料重複檢查走無重複
        if "SELECT id FROM inventory_items WHERE name = $1" in sql:
            return None
        if "SELECT id FROM inventory_items WHERE name = $1 AND id != $2" in sql:
            return None
        return self.row

    async def fetchval(self, *_args):
        return 1

    async def execute(self, *_args):
        return "DELETE 1"


def _patch_models(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "InventoryItemResponse",
        "InventoryItemListItem",
        "InventoryItemListResponse",
        "InventoryTransactionResponse",
        "InventoryTransactionListItem",
        "InventoryTransactionListResponse",
        "InventoryOrderResponse",
        "InventoryOrderListItem",
        "InventoryOrderListResponse",
    ]:
        monkeypatch.setattr(inventory, name, _DummyModel)


@pytest.mark.asyncio
async def test_inventory_service_happy_path_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch)

    item_id = uuid4()
    project_id = uuid4()
    now = datetime.now()
    row = _Row(
        id=item_id,
        item_id=item_id,
        project_id=project_id,
        name="Motor",
        model="M1",
        specification="spec",
        unit="pcs",
        category="cat",
        default_vendor="Vendor",
        storage_location="A1",
        min_stock=Decimal("1"),
        current_stock=Decimal("10"),
        notes="note",
        type="in",
        quantity=Decimal("2"),
        transaction_date=date.today(),
        vendor="Vendor",
        created_at=now,
        updated_at=now,
        created_by="admin",
        project_name="ProjectX",
        order_quantity=Decimal("3"),
        order_date=date.today(),
        expected_delivery_date=None,
        actual_delivery_date=None,
        status="pending",
        item_name="Motor",
        total_in=Decimal("5"),
        total_out=Decimal("2"),
    )
    conn = _Conn(row)
    monkeypatch.setattr(inventory, "get_connection", lambda: _CM(conn))

    items = await inventory.list_inventory_items(query="motor", category="cat", vendor="Vendor", low_stock=True)
    assert items["total"] == 1
    assert (await inventory.get_inventory_item(item_id))["name"] == "Motor"
    assert (await inventory.get_inventory_item_by_name("Motor"))["name"] == "Motor"
    assert len(await inventory.search_inventory_items("M")) == 1

    created = await inventory.create_inventory_item(
        InventoryItemCreate(
            name="I1",
            model="M",
            specification="S",
            unit="pcs",
            category="cat",
            default_vendor="V",
            storage_location="L",
            min_stock=Decimal("1"),
            notes="N",
        ),
        created_by="u1",
    )
    assert created["name"] == "Motor"

    updated = await inventory.update_inventory_item(item_id, InventoryItemUpdate(name="I2"))
    assert updated["name"] == "Motor"
    await inventory.delete_inventory_item(item_id)

    txs = await inventory.list_inventory_transactions(item_id, limit=10)
    assert txs["total"] == 1
    tx = await inventory.get_inventory_transaction(uuid4())
    assert tx["item_id"] == item_id

    new_tx = await inventory.create_inventory_transaction(
        item_id,
        InventoryTransactionCreate(type=TransactionType.IN, quantity=Decimal("1"), project_id=project_id),
        created_by="u1",
    )
    assert new_tx["project_name"] == "Motor"
    await inventory.delete_inventory_transaction(uuid4())

    assert await inventory.get_categories() == ["cat"]
    assert await inventory.get_low_stock_count() == 1

    assert (await inventory.find_item_by_id_or_name(item_id=str(item_id))).found is True
    assert (await inventory.find_item_by_id_or_name(item_name="Motor")).found is True
    assert (await inventory.find_project_by_id_or_name(project_id=str(project_id))).found is True
    assert (await inventory.find_project_by_id_or_name(project_name="P")).found is True

    item_with_txs = await inventory.get_item_with_transactions(item_id, limit=5)
    assert item_with_txs["item"]["name"] == "Motor"

    stock = await inventory.create_inventory_transaction_mcp(
        item_id=item_id,
        transaction_type="in",
        quantity=Decimal("1"),
        created_by="linebot",
    )
    assert stock == 1

    order_list = await inventory.list_inventory_orders(item_id=item_id, status="pending", limit=5)
    assert order_list["total"] == 1
    order = await inventory.get_inventory_order(uuid4())
    assert order["item_name"] == "Motor"

    created_order = await inventory.create_inventory_order(
        item_id,
        InventoryOrderCreate(
            order_quantity=Decimal("3"),
            order_date=date.today(),
            expected_delivery_date=None,
            vendor="Vendor",
            project_id=project_id,
            notes="N",
        ),
        created_by="u1",
    )
    assert created_order["item_name"] == "Motor"

    updated_order = await inventory.update_inventory_order(
        uuid4(),
        InventoryOrderUpdate(status="ordered", vendor="V2"),
    )
    assert updated_order["status"] == "pending"

    project_status = await inventory.get_project_inventory_status(project_id)
    assert project_status["project_name"] == "Motor"
    await inventory.delete_inventory_order(uuid4())


@pytest.mark.asyncio
async def test_inventory_service_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_models(monkeypatch)

    class _ConnNotFound(_Conn):
        async def fetchrow(self, *_args, **_kwargs):
            return None

        async def fetch(self, *_args, **_kwargs):
            return []

        async def fetchval(self, *_args, **_kwargs):
            return 0

        async def execute(self, *_args, **_kwargs):
            return "DELETE 0"

    conn = _ConnNotFound(_Row())
    monkeypatch.setattr(inventory, "get_connection", lambda: _CM(conn))

    with pytest.raises(inventory.InventoryItemNotFoundError):
        await inventory.get_inventory_item(uuid4())
    assert await inventory.get_inventory_item_by_name("none") is None
    with pytest.raises(inventory.InventoryItemNotFoundError):
        await inventory.update_inventory_item(uuid4(), InventoryItemUpdate(name="x"))
    with pytest.raises(inventory.InventoryItemNotFoundError):
        await inventory.delete_inventory_item(uuid4())
    with pytest.raises(inventory.InventoryTransactionNotFoundError):
        await inventory.get_inventory_transaction(uuid4())
    with pytest.raises(inventory.InventoryTransactionNotFoundError):
        await inventory.delete_inventory_transaction(uuid4())
    with pytest.raises(inventory.InventoryOrderNotFoundError):
        await inventory.get_inventory_order(uuid4())
    with pytest.raises(inventory.InventoryOrderNotFoundError):
        await inventory.update_inventory_order(uuid4(), InventoryOrderUpdate(vendor="x"))
    with pytest.raises(inventory.InventoryOrderNotFoundError):
        await inventory.delete_inventory_order(uuid4())

    item_lookup = await inventory.find_item_by_id_or_name(item_id="bad-uuid")
    assert item_lookup.error is not None
    assert (await inventory.find_item_by_id_or_name(item_name="none")).error is not None

    project_lookup = await inventory.find_project_by_id_or_name(project_id="bad-uuid")
    assert project_lookup.error is not None
    assert (await inventory.find_project_by_id_or_name(project_name="none")).found is False

    with pytest.raises(inventory.InventoryItemNotFoundError):
        await inventory.get_item_with_transactions(uuid4())
    with pytest.raises(inventory.InventoryError):
        await inventory.get_project_inventory_status(uuid4())
