"""往來與物料模組 MCP 工具測試。

重點：
- 權限被拒時回錯誤 dict，不進 service
- `AmbiguousError` 回 `{"need_confirmation": true, "candidates": [...]}` 而不是丟例外
- 寫入類工具回 `audit_id`
- 文件擷取兩支只做草稿與重複比對，不呼叫模型
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.services import erp as erp_core
from ching_tech_os.services.mcp import erp_tools

NOW = datetime.now(timezone.utc)
PARTY_ID = uuid4()
ITEM_ID = uuid4()
PO_ID = uuid4()
AUDIT_ID = uuid4()


@pytest.fixture(autouse=True)
def _allow(monkeypatch: pytest.MonkeyPatch):
    """預設放行權限並跳過真的連線"""
    monkeypatch.setattr(erp_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        erp_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(True, "")),
    )


def _deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        erp_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(False, "您沒有「廠商管理」功能權限，無法使用此工具")),
    )


# ============================================================
# 共用輔助
# ============================================================


def test_clean_serializes_uuid_decimal_and_datetime() -> None:
    value = erp_tools._clean(
        {"id": PARTY_ID, "qty": Decimal("1.5"), "at": NOW, "rows": [{"x": ITEM_ID}]}
    )
    assert value["id"] == str(PARTY_ID)
    assert value["qty"] == "1.5"
    assert value["at"] == NOW.isoformat()
    assert value["rows"][0]["x"] == str(ITEM_ID)


def test_fail_maps_ambiguous_to_need_confirmation() -> None:
    err = erp_core.AmbiguousError(
        "往來對象", "鴻佰", [{"id": PARTY_ID, "name": "鴻佰科技"}]
    )
    result = erp_tools._fail(err)
    assert result["need_confirmation"] is True
    assert result["candidates"][0]["id"] == str(PARTY_ID)
    assert result["ok"] is False


def test_fail_maps_not_found_and_generic() -> None:
    assert erp_tools._fail(erp_core.NotFoundError("物料", "x"))["not_found"] is True
    assert erp_tools._fail(erp_core.InvalidOperationError("不行"))["error"] == "不行"
    assert "執行失敗" in erp_tools._fail(RuntimeError("boom"))["error"]


@pytest.mark.asyncio
async def test_party_id_from_requires_id_or_name() -> None:
    with pytest.raises(erp_core.NotFoundError):
        await erp_tools._party_id_from(None, None)
    assert await erp_tools._party_id_from(str(PARTY_ID), None) == PARTY_ID


@pytest.mark.asyncio
async def test_item_id_from_requires_id_or_query() -> None:
    with pytest.raises(erp_core.NotFoundError):
        await erp_tools._item_id_from(None, None)


@pytest.mark.asyncio
async def test_warehouse_id_from_accepts_uuid_or_name(monkeypatch) -> None:
    wid = uuid4()
    assert await erp_tools._warehouse_id_from(None) is None
    assert await erp_tools._warehouse_id_from(str(wid)) == wid
    monkeypatch.setattr(
        erp_core, "resolve_warehouse", AsyncMock(return_value={"id": wid})
    )
    assert await erp_tools._warehouse_id_from("主倉") == wid


# ============================================================
# 權限
# ============================================================


@pytest.mark.asyncio
async def test_tool_denied_without_app_permission(monkeypatch) -> None:
    _deny(monkeypatch)
    find = AsyncMock()
    monkeypatch.setattr(erp_core, "find_parties", find)

    result = await erp_tools.find_party("鴻佰", ctos_user_id=3)

    assert result["ok"] is False
    assert "廠商管理" in result["error"]
    find.assert_not_awaited()


# ============================================================
# 往來對象
# ============================================================


@pytest.mark.asyncio
async def test_find_party_returns_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core,
        "find_parties",
        AsyncMock(return_value=[{"id": PARTY_ID, "name": "鴻佰科技"}]),
    )
    result = await erp_tools.find_party("鴻佰", role="supplier")
    assert result["count"] == 1
    assert result["candidates"][0]["id"] == str(PARTY_ID)


@pytest.mark.asyncio
async def test_find_party_wraps_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "find_parties", AsyncMock(side_effect=RuntimeError("db 壞了"))
    )
    assert (await erp_tools.find_party("鴻佰"))["ok"] is False


@pytest.mark.asyncio
async def test_get_party_by_name_ambiguous_returns_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core,
        "resolve_party",
        AsyncMock(
            side_effect=erp_core.AmbiguousError(
                "往來對象", "鴻佰", [{"id": PARTY_ID, "name": "鴻佰科技"}]
            )
        ),
    )
    result = await erp_tools.get_party(name="鴻佰")
    assert result["need_confirmation"] is True
    assert result["query"] == "鴻佰"


@pytest.mark.asyncio
async def test_get_party_returns_detail(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "get_party_detail",
        AsyncMock(return_value={"id": PARTY_ID, "name": "鴻佰科技"}),
    )
    result = await erp_tools.get_party(party_id=str(PARTY_ID))
    assert result["party"]["name"] == "鴻佰科技"


@pytest.mark.asyncio
async def test_get_party_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service, "get_party_detail", AsyncMock(return_value=None)
    )
    assert (await erp_tools.get_party(party_id=str(PARTY_ID)))["not_found"] is True


@pytest.mark.asyncio
async def test_create_party_returns_audit_id(monkeypatch) -> None:
    create = AsyncMock(
        return_value={"id": PARTY_ID, "name": "鴻佰科技", "audit_id": AUDIT_ID}
    )
    monkeypatch.setattr(erp_tools.party_service, "create_party", create)

    result = await erp_tools.create_party(
        "鴻佰科技",
        is_supplier=True,
        contacts=[{"name": "陳先生"}],
        ctos_user_id=5,
    )

    assert result["audit_id"] == str(AUDIT_ID)
    payload, kwargs = create.await_args
    assert payload[0]["contacts"] == [{"name": "陳先生"}]
    assert kwargs["actor_user_id"] == 5
    assert kwargs["via"] == "mcp"


@pytest.mark.asyncio
async def test_create_party_reports_service_error(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "create_party",
        AsyncMock(side_effect=erp_core.InvalidOperationError("壞了")),
    )
    assert (await erp_tools.create_party("鴻佰"))["error"] == "壞了"


@pytest.mark.asyncio
async def test_update_party_requires_fields() -> None:
    assert (await erp_tools.update_party(party_id=str(PARTY_ID)))["ok"] is False


@pytest.mark.asyncio
async def test_update_party(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "update_party",
        AsyncMock(return_value={"id": PARTY_ID, "name": "鴻佰", "audit_id": AUDIT_ID}),
    )
    result = await erp_tools.update_party(
        party_id=str(PARTY_ID), fields={"payment_terms": "月結 60 天"}
    )
    assert result["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_update_party_validates_fields(monkeypatch) -> None:
    """F4：null 進 NOT NULL 欄位要回錯誤 dict，不能等資料庫爆"""
    update = AsyncMock()
    monkeypatch.setattr(erp_tools.party_service, "update_party", update)

    result = await erp_tools.update_party(
        party_id=str(PARTY_ID), fields={"name": None}
    )

    assert result["ok"] is False
    assert "欄位不合法" in result["error"]
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_party_drops_unknown_fields(monkeypatch) -> None:
    update = AsyncMock(
        return_value={"id": PARTY_ID, "name": "鴻佰", "audit_id": AUDIT_ID}
    )
    monkeypatch.setattr(erp_tools.party_service, "update_party", update)

    await erp_tools.update_party(
        party_id=str(PARTY_ID), fields={"notes": "x", "不存在的欄位": 1}
    )

    assert update.await_args[0][1] == {"notes": "x"}


@pytest.mark.asyncio
async def test_update_item_validates_fields(monkeypatch) -> None:
    update = AsyncMock()
    monkeypatch.setattr(erp_tools.inventory_service, "update_item", update)

    result = await erp_tools.update_item(item_id=str(ITEM_ID), fields={"code": None})

    assert result["ok"] is False
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_party_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service, "update_party", AsyncMock(return_value=None)
    )
    result = await erp_tools.update_party(party_id=str(PARTY_ID), fields={"notes": "x"})
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_add_party_contact(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "add_contact",
        AsyncMock(
            return_value={"id": uuid4(), "party_id": PARTY_ID, "audit_id": AUDIT_ID}
        ),
    )
    result = await erp_tools.add_party_contact(
        party_id=str(PARTY_ID), name="陳先生", phone="03-1234567"
    )
    assert result["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_add_party_contact_validations(monkeypatch) -> None:
    assert (await erp_tools.add_party_contact(party_id=str(PARTY_ID)))["ok"] is False
    monkeypatch.setattr(
        erp_tools.party_service, "add_contact", AsyncMock(return_value=None)
    )
    result = await erp_tools.add_party_contact(party_id=str(PARTY_ID), name="陳先生")
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_add_party_address(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "add_address",
        AsyncMock(
            return_value={"id": uuid4(), "party_id": PARTY_ID, "audit_id": AUDIT_ID}
        ),
    )
    result = await erp_tools.add_party_address(
        party_id=str(PARTY_ID), address="桃園市中壢區"
    )
    assert result["audit_id"] == str(AUDIT_ID)


@pytest.mark.asyncio
async def test_add_party_address_validations(monkeypatch) -> None:
    assert (await erp_tools.add_party_address(party_id=str(PARTY_ID)))["ok"] is False
    monkeypatch.setattr(
        erp_tools.party_service, "add_address", AsyncMock(return_value=None)
    )
    result = await erp_tools.add_party_address(
        party_id=str(PARTY_ID), address="桃園"
    )
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_merge_parties(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "merge_parties",
        AsyncMock(
            return_value={
                "id": PARTY_ID,
                "name": "鴻佰科技",
                "aliases": ["鴻佰工業"],
                "audit_id": AUDIT_ID,
            }
        ),
    )
    result = await erp_tools.merge_parties(str(PARTY_ID), str(uuid4()))
    assert result["aliases"] == ["鴻佰工業"]


@pytest.mark.asyncio
async def test_merge_parties_error(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "merge_parties",
        AsyncMock(side_effect=erp_core.InvalidOperationError("不能合併自己")),
    )
    assert (await erp_tools.merge_parties(str(PARTY_ID), str(PARTY_ID)))["ok"] is False


@pytest.mark.asyncio
async def test_summarize_party(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service,
        "summarize_party",
        AsyncMock(return_value={"party_id": PARTY_ID, "summary": "【鴻佰】供應商"}),
    )
    result = await erp_tools.summarize_party(party_id=str(PARTY_ID))
    assert result["summary"].startswith("【鴻佰】")


@pytest.mark.asyncio
async def test_summarize_party_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.party_service, "summarize_party", AsyncMock(return_value=None)
    )
    assert (await erp_tools.summarize_party(party_id=str(PARTY_ID)))["not_found"] is True


# ============================================================
# 物料與庫存
# ============================================================


@pytest.mark.asyncio
async def test_find_item(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "find_items", AsyncMock(return_value=[{"id": ITEM_ID, "code": "A1"}])
    )
    assert (await erp_tools.find_item("螺絲"))["count"] == 1


@pytest.mark.asyncio
async def test_find_item_error(monkeypatch) -> None:
    monkeypatch.setattr(erp_core, "find_items", AsyncMock(side_effect=RuntimeError()))
    assert (await erp_tools.find_item("螺絲"))["ok"] is False


@pytest.mark.asyncio
async def test_get_item(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "get_item_detail",
        AsyncMock(return_value={"id": ITEM_ID, "code": "A1", "total_qty": Decimal("3")}),
    )
    result = await erp_tools.get_item(item_id=str(ITEM_ID))
    assert result["item"]["total_qty"] == "3"


@pytest.mark.asyncio
async def test_get_item_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.inventory_service, "get_item_detail", AsyncMock(return_value=None)
    )
    assert (await erp_tools.get_item(item_id=str(ITEM_ID)))["not_found"] is True


@pytest.mark.asyncio
async def test_create_item_resolves_default_supplier(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_party", AsyncMock(return_value={"id": PARTY_ID})
    )
    create = AsyncMock(return_value={"id": ITEM_ID, "code": "A1", "audit_id": AUDIT_ID})
    monkeypatch.setattr(erp_tools.inventory_service, "create_item", create)

    result = await erp_tools.create_item(
        "A1", "螺絲", default_supplier="鴻佰", purchase_price=5.5
    )

    assert result["audit_id"] == str(AUDIT_ID)
    payload = create.await_args[0][0]
    assert payload["default_supplier_id"] == PARTY_ID
    assert payload["purchase_price"] == Decimal("5.5")


@pytest.mark.asyncio
async def test_create_item_duplicate(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "create_item",
        AsyncMock(side_effect=erp_core.InvalidOperationError("料號已存在：A1")),
    )
    assert "已存在" in (await erp_tools.create_item("A1", "螺絲"))["error"]


@pytest.mark.asyncio
async def test_update_item(monkeypatch) -> None:
    update = AsyncMock(return_value={"id": ITEM_ID, "code": "A1", "audit_id": AUDIT_ID})
    monkeypatch.setattr(erp_tools.inventory_service, "update_item", update)

    result = await erp_tools.update_item(
        item_id=str(ITEM_ID), fields={"purchase_price": 9}
    )
    assert result["audit_id"] == str(AUDIT_ID)
    # 模型把它轉成 Decimal（F4：驗證與轉型都在 Pydantic）
    assert update.await_args[0][1]["purchase_price"] == Decimal("9")


@pytest.mark.asyncio
async def test_update_item_validations(monkeypatch) -> None:
    assert (await erp_tools.update_item(item_id=str(ITEM_ID)))["ok"] is False
    monkeypatch.setattr(
        erp_tools.inventory_service, "update_item", AsyncMock(return_value=None)
    )
    result = await erp_tools.update_item(item_id=str(ITEM_ID), fields={"name": "x"})
    assert result["not_found"] is True


@pytest.mark.asyncio
async def test_get_stock(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "get_stock",
        AsyncMock(return_value={"total": 1, "items": [{"qty": Decimal("10")}]}),
    )
    result = await erp_tools.get_stock(item="螺絲")
    assert result["rows"][0]["qty"] == "10"


@pytest.mark.asyncio
async def test_get_stock_item_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core,
        "resolve_item",
        AsyncMock(side_effect=erp_core.NotFoundError("物料", "xyz")),
    )
    assert (await erp_tools.get_stock(item="xyz"))["not_found"] is True


@pytest.mark.asyncio
async def test_adjust_stock(monkeypatch) -> None:
    wid = uuid4()
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    monkeypatch.setattr(
        erp_core, "resolve_warehouse", AsyncMock(return_value={"id": wid})
    )
    adjust = AsyncMock(
        return_value={"audit_id": AUDIT_ID, "balances": [{"qty": Decimal("110")}]}
    )
    monkeypatch.setattr(erp_tools.inventory_service, "adjust_stock", adjust)

    result = await erp_tools.adjust_stock("螺絲", "主倉", 10, reason="receipt")

    assert result["qty_after"] == "110"
    assert adjust.await_args[0][2] == Decimal("10")


@pytest.mark.asyncio
async def test_adjust_stock_requires_warehouse(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    assert (await erp_tools.adjust_stock("螺絲", "", 10))["ok"] is False


@pytest.mark.asyncio
async def test_adjust_stock_negative_balance(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    monkeypatch.setattr(
        erp_core, "resolve_warehouse", AsyncMock(return_value={"id": uuid4()})
    )
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "adjust_stock",
        AsyncMock(
            side_effect=erp_core.NegativeStockError(
                ITEM_ID, uuid4(), Decimal("3"), Decimal("-5")
            )
        ),
    )
    assert "庫存不足" in (await erp_tools.adjust_stock("螺絲", "主倉", -5))["error"]


@pytest.mark.asyncio
async def test_transfer_stock(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    monkeypatch.setattr(
        erp_core, "resolve_warehouse", AsyncMock(return_value={"id": uuid4()})
    )
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "transfer_stock",
        AsyncMock(
            return_value={
                "audit_id": AUDIT_ID,
                "balances": [{"qty": Decimal("70")}, {"qty": Decimal("30")}],
            }
        ),
    )
    result = await erp_tools.transfer_stock("螺絲", "主倉", "副倉", 30)
    assert len(result["balances"]) == 2


@pytest.mark.asyncio
async def test_transfer_stock_requires_both_warehouses(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    assert (await erp_tools.transfer_stock("螺絲", "", "", 1))["ok"] is False


@pytest.mark.asyncio
async def test_summarize_item(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.inventory_service,
        "summarize_item",
        AsyncMock(return_value={"item_id": ITEM_ID, "summary": "【A1】螺絲"}),
    )
    assert (await erp_tools.summarize_item(item_id=str(ITEM_ID)))["ok"] is True


@pytest.mark.asyncio
async def test_summarize_item_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.inventory_service, "summarize_item", AsyncMock(return_value=None)
    )
    assert (await erp_tools.summarize_item(item_id=str(ITEM_ID)))["not_found"] is True


# ============================================================
# 採購
# ============================================================


@pytest.mark.asyncio
async def test_create_purchase_order_resolves_names(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_party", AsyncMock(return_value={"id": PARTY_ID})
    )
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    create = AsyncMock(
        return_value={
            "id": PO_ID,
            "po_no": "PO-202609-001",
            "status": "ordered",
            "audit_id": AUDIT_ID,
        }
    )
    monkeypatch.setattr(erp_tools.purchasing_service, "create_purchase_order", create)

    result = await erp_tools.create_purchase_order(
        "鴻佰", [{"item": "螺絲", "qty": 10, "unit_price": 5}]
    )

    assert result["po_no"] == "PO-202609-001"
    payload = create.await_args[0][0]
    assert payload["lines"][0]["item_id"] == ITEM_ID
    assert payload["lines"][0]["unit_price"] == Decimal("5")


@pytest.mark.asyncio
async def test_create_purchase_order_requires_lines() -> None:
    assert (await erp_tools.create_purchase_order("鴻佰", []))["ok"] is False


@pytest.mark.asyncio
async def test_create_purchase_order_ambiguous_item(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_party", AsyncMock(return_value={"id": PARTY_ID})
    )
    monkeypatch.setattr(
        erp_core,
        "resolve_item",
        AsyncMock(
            side_effect=erp_core.AmbiguousError(
                "物料", "螺絲", [{"id": ITEM_ID, "code": "A1"}]
            )
        ),
    )
    result = await erp_tools.create_purchase_order("鴻佰", [{"item": "螺絲", "qty": 1}])
    assert result["need_confirmation"] is True
    assert result["entity"] == "物料"


@pytest.mark.asyncio
async def test_resolve_project_id_variants(monkeypatch) -> None:
    pid = uuid4()
    assert await erp_tools._resolve_project_id(None) is None
    assert await erp_tools._resolve_project_id(str(pid)) == pid

    class _Conn:
        def __init__(self, rows):
            self.rows = rows
            self.sql = ""
            self.args: tuple = ()

        async def fetch(self, sql, *args):
            self.sql = sql
            self.args = args
            return self.rows

    class _CM:
        def __init__(self, conn):
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, *_args):
            return None

    import ching_tech_os.database as database

    conn = _Conn([{"id": pid, "name": "A 案"}])
    monkeypatch.setattr(database, "get_connection", lambda: _CM(conn))
    assert await erp_tools._resolve_project_id("A 案") == pid
    # F7：% 與 _ 要跳脫，ILIKE 要帶 ESCAPE
    assert conn.args[0] == "%A 案%"
    assert "ESCAPE" in conn.sql

    monkeypatch.setattr(database, "get_connection", lambda: _CM(_Conn([])))
    with pytest.raises(erp_core.NotFoundError):
        await erp_tools._resolve_project_id("查無")

    escaped = _Conn([{"id": pid, "name": "折扣 50%"}])
    monkeypatch.setattr(database, "get_connection", lambda: _CM(escaped))
    await erp_tools._resolve_project_id("50%")
    assert escaped.args[0] == r"%50\%%"

    monkeypatch.setattr(
        database,
        "get_connection",
        lambda: _CM(_Conn([{"id": pid, "name": "A"}, {"id": uuid4(), "name": "A2"}])),
    )
    with pytest.raises(erp_core.AmbiguousError):
        await erp_tools._resolve_project_id("A")


@pytest.mark.asyncio
async def test_get_purchase_order_by_po_no(monkeypatch) -> None:
    get = AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-001"})
    monkeypatch.setattr(erp_tools.purchasing_service, "get_purchase_order", get)

    result = await erp_tools.get_purchase_order("PO-202609-001")
    assert result["purchase_order"]["po_no"] == "PO-202609-001"
    assert get.await_args.kwargs == {"po_no": "PO-202609-001"}


@pytest.mark.asyncio
async def test_load_po_by_uuid(monkeypatch) -> None:
    get = AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-001"})
    monkeypatch.setattr(erp_tools.purchasing_service, "get_purchase_order", get)

    await erp_tools.get_purchase_order(str(PO_ID))
    assert get.await_args.kwargs == {"po_id": PO_ID}


@pytest.mark.asyncio
async def test_load_po_does_not_swallow_service_value_error(monkeypatch) -> None:
    """F6：try 只包 UUID 解析；service 自己丟的 ValueError 不能被當成「這是單號」"""
    get = AsyncMock(side_effect=ValueError("service 壞了"))
    monkeypatch.setattr(erp_tools.purchasing_service, "get_purchase_order", get)

    result = await erp_tools.get_purchase_order(str(PO_ID))

    assert result["ok"] is False
    assert get.await_count == 1


@pytest.mark.asyncio
async def test_get_purchase_order_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service, "get_purchase_order", AsyncMock(return_value=None)
    )
    assert (await erp_tools.get_purchase_order("PO-x"))["not_found"] is True


@pytest.mark.asyncio
async def test_list_purchase_orders(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_party", AsyncMock(return_value={"id": PARTY_ID})
    )
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "list_purchase_orders",
        AsyncMock(return_value={"total": 1, "items": [{"po_no": "PO-202609-001"}]}),
    )
    result = await erp_tools.list_purchase_orders(supplier="鴻佰", status="ordered")
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_list_purchase_orders_supplier_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core,
        "resolve_party",
        AsyncMock(side_effect=erp_core.NotFoundError("往來對象", "x")),
    )
    assert (await erp_tools.list_purchase_orders(supplier="x"))["not_found"] is True


@pytest.mark.asyncio
async def test_receive_purchase_order(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-001"}),
    )
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    receive = AsyncMock(
        return_value={"audit_id": AUDIT_ID, "status": "received", "movements": [{}]}
    )
    monkeypatch.setattr(erp_tools.purchasing_service, "receive_purchase_order", receive)

    result = await erp_tools.receive_purchase_order(
        "PO-202609-001", lines=[{"item": "螺絲", "qty": 4}]
    )

    assert result["status"] == "received"
    assert result["received_lines"] == 1
    assert receive.await_args.kwargs["lines"][0]["qty"] == Decimal("4")
    assert receive.await_args.kwargs["lines"][0]["item_id"] == ITEM_ID


@pytest.mark.asyncio
async def test_receive_purchase_order_passes_line_id(monkeypatch) -> None:
    """F1：給了 line_id 就直接用，不要再去解析物料"""
    line_id = uuid4()
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-001"}),
    )
    resolve_item = AsyncMock()
    monkeypatch.setattr(erp_core, "resolve_item", resolve_item)
    receive = AsyncMock(
        return_value={"audit_id": AUDIT_ID, "status": "partial", "movements": [{}]}
    )
    monkeypatch.setattr(erp_tools.purchasing_service, "receive_purchase_order", receive)

    await erp_tools.receive_purchase_order(
        "PO-202609-001", lines=[{"line_id": str(line_id), "qty": 4}]
    )

    assert receive.await_args.kwargs["lines"][0]["line_id"] == line_id
    assert "item_id" not in receive.await_args.kwargs["lines"][0]
    resolve_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_receive_purchase_order_ambiguous_line(monkeypatch) -> None:
    """同物料兩行、只給 item 時，工具回 need_confirmation ＋ 行候選"""
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-001"}),
    )
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "receive_purchase_order",
        AsyncMock(
            side_effect=erp_core.AmbiguousError(
                "採購單行項",
                str(ITEM_ID),
                [{"line_id": str(uuid4())}, {"line_id": str(uuid4())}],
            )
        ),
    )

    result = await erp_tools.receive_purchase_order(
        "PO-202609-001", lines=[{"item": "螺絲", "qty": 1}]
    )

    assert result["need_confirmation"] is True
    assert len(result["candidates"]) == 2


@pytest.mark.asyncio
async def test_receive_purchase_order_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service, "get_purchase_order", AsyncMock(return_value=None)
    )
    assert (await erp_tools.receive_purchase_order("PO-x"))["not_found"] is True


@pytest.mark.asyncio
async def test_receive_purchase_order_service_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "po_no": "PO-1"}),
    )
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "receive_purchase_order",
        AsyncMock(return_value=None),
    )
    assert (await erp_tools.receive_purchase_order("PO-1", all=True))["not_found"] is True


@pytest.mark.asyncio
async def test_cancel_purchase_order(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "po_no": "PO-202609-002"}),
    )
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "cancel_purchase_order",
        AsyncMock(
            return_value={
                "po_no": "PO-202609-002",
                "status": "cancelled",
                "audit_id": AUDIT_ID,
            }
        ),
    )
    result = await erp_tools.cancel_purchase_order("PO-202609-002", reason="改採別家")
    assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_purchase_order_missing_and_none(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service, "get_purchase_order", AsyncMock(return_value=None)
    )
    assert (await erp_tools.cancel_purchase_order("PO-x"))["not_found"] is True

    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "get_purchase_order",
        AsyncMock(return_value={"id": PO_ID, "po_no": "PO-1"}),
    )
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "cancel_purchase_order",
        AsyncMock(return_value=None),
    )
    assert (await erp_tools.cancel_purchase_order("PO-1"))["not_found"] is True


# ============================================================
# 文件擷取（不呼叫模型）
# ============================================================


@pytest.mark.asyncio
async def test_extract_party_from_document_builds_draft(monkeypatch) -> None:
    match = AsyncMock(return_value=[{"id": PARTY_ID, "name": "鴻佰科技"}])
    monkeypatch.setattr(erp_tools.purchasing_service, "match_duplicate_parties", match)

    result = await erp_tools.extract_party_from_document(
        "/tmp/card.jpg",
        name="鴻佰科技",
        tax_id="12345678",
        contact_name="陳先生",
        phone="03-1234567",
        address="桃園市中壢區",
    )

    assert result["draft"]["contacts"][0]["is_primary"] is True
    assert result["draft"]["addresses"][0]["address"] == "桃園市中壢區"
    assert result["duplicates"][0]["id"] == str(PARTY_ID)
    assert result["source_file"] == "/tmp/card.jpg"


@pytest.mark.asyncio
async def test_extract_party_without_contact_or_address(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service, "match_duplicate_parties", AsyncMock(return_value=[])
    )
    result = await erp_tools.extract_party_from_document("/tmp/x.pdf", name="小廠")
    assert result["draft"]["contacts"] == []
    assert result["draft"]["addresses"] == []


@pytest.mark.asyncio
async def test_extract_party_reports_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_tools.purchasing_service,
        "match_duplicate_parties",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    assert (await erp_tools.extract_party_from_document("/tmp/x", name="A"))["ok"] is False


@pytest.mark.asyncio
async def test_extract_purchase_order_marks_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_party", AsyncMock(return_value={"id": PARTY_ID})
    )
    monkeypatch.setattr(
        erp_core, "resolve_item", AsyncMock(return_value={"id": ITEM_ID})
    )

    result = await erp_tools.extract_purchase_order_from_document(
        "/tmp/quote.pdf", "鴻佰", [{"item": "螺絲", "qty": 10}]
    )

    assert result["ready_to_create"] is True
    assert result["supplier"]["resolved"]["id"] == str(PARTY_ID)


@pytest.mark.asyncio
async def test_extract_purchase_order_reports_unresolved(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core,
        "resolve_party",
        AsyncMock(
            side_effect=erp_core.AmbiguousError("往來對象", "鴻佰", [{"id": PARTY_ID}])
        ),
    )
    monkeypatch.setattr(
        erp_core,
        "resolve_item",
        AsyncMock(side_effect=erp_core.NotFoundError("物料", "螺絲")),
    )

    result = await erp_tools.extract_purchase_order_from_document(
        "/tmp/quote.pdf", "鴻佰", [{"item": "螺絲", "qty": 10}]
    )

    assert result["ready_to_create"] is False
    assert result["supplier"]["candidates"]
    assert result["lines"][0]["not_found"] is True


@pytest.mark.asyncio
async def test_extract_purchase_order_supplier_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core,
        "resolve_party",
        AsyncMock(side_effect=erp_core.NotFoundError("往來對象", "鴻佰")),
    )
    result = await erp_tools.extract_purchase_order_from_document(
        "/tmp/q.pdf", "鴻佰", []
    )
    assert result["supplier"]["not_found"] is True
    assert result["ready_to_create"] is False


@pytest.mark.asyncio
async def test_extract_purchase_order_unexpected_error(monkeypatch) -> None:
    monkeypatch.setattr(
        erp_core, "resolve_party", AsyncMock(side_effect=RuntimeError("boom"))
    )
    result = await erp_tools.extract_purchase_order_from_document("/tmp/q.pdf", "x", [])
    assert result["ok"] is False


# ============================================================
# 工具與權限對照表
# ============================================================


def test_every_erp_tool_is_in_tool_app_mapping() -> None:
    from ching_tech_os.services.permissions import TOOL_APP_MAPPING

    vendor_tools = {
        "find_party",
        "get_party",
        "create_party",
        "update_party",
        "add_party_contact",
        "add_party_address",
        "merge_parties",
        "summarize_party",
        "extract_party_from_document",
    }
    inventory_tools = {
        "find_item",
        "get_item",
        "create_item",
        "update_item",
        "get_stock",
        "adjust_stock",
        "transfer_stock",
        "create_purchase_order",
        "get_purchase_order",
        "list_purchase_orders",
        "receive_purchase_order",
        "cancel_purchase_order",
        "summarize_item",
        "extract_purchase_order_from_document",
    }
    # 規格第三節的 23 支工具全部有對應 app
    assert len(vendor_tools | inventory_tools) == 23
    for name in vendor_tools:
        assert TOOL_APP_MAPPING[name] == "vendor-management", name
    for name in inventory_tools:
        assert TOOL_APP_MAPPING[name] == "inventory-management", name
    # 工具本身都存在於模組上
    for name in vendor_tools | inventory_tools:
        assert callable(getattr(erp_tools, name)), name


# 每支工具的最小呼叫參數（權限掃描用）
_MINIMAL_CALLS: list[tuple[str, tuple, dict]] = [
    ("find_party", ("鴻佰",), {}),
    ("get_party", (), {"party_id": str(PARTY_ID)}),
    ("create_party", ("鴻佰",), {}),
    ("update_party", (), {"party_id": str(PARTY_ID), "fields": {"notes": "x"}}),
    ("add_party_contact", (), {"party_id": str(PARTY_ID), "name": "陳先生"}),
    ("add_party_address", (), {"party_id": str(PARTY_ID), "address": "桃園"}),
    ("merge_parties", (str(PARTY_ID), str(uuid4())), {}),
    ("summarize_party", (), {"party_id": str(PARTY_ID)}),
    ("extract_party_from_document", ("/tmp/a.jpg", "鴻佰"), {}),
    ("find_item", ("螺絲",), {}),
    ("get_item", (), {"item_id": str(ITEM_ID)}),
    ("create_item", ("A1", "螺絲"), {}),
    ("update_item", (), {"item_id": str(ITEM_ID), "fields": {"name": "x"}}),
    ("get_stock", (), {}),
    ("adjust_stock", ("螺絲", "主倉", 1), {}),
    ("transfer_stock", ("螺絲", "主倉", "副倉", 1), {}),
    ("create_purchase_order", ("鴻佰", [{"item": "螺絲", "qty": 1}]), {}),
    ("get_purchase_order", ("PO-202609-001",), {}),
    ("list_purchase_orders", (), {}),
    ("receive_purchase_order", ("PO-202609-001",), {}),
    ("cancel_purchase_order", ("PO-202609-001",), {}),
    ("extract_purchase_order_from_document", ("/tmp/q.pdf", "鴻佰", []), {}),
    ("summarize_item", (), {"item_id": str(ITEM_ID)}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name, args, kwargs", _MINIMAL_CALLS)
async def test_all_tools_check_permission(
    monkeypatch: pytest.MonkeyPatch, tool_name, args, kwargs
) -> None:
    """23 支工具每一支都要先過 check_mcp_tool_permission，被拒就不進 service"""
    checker = AsyncMock(return_value=(False, "無權限"))
    monkeypatch.setattr(erp_tools, "check_mcp_tool_permission", checker)
    # service 一律炸掉：真的被呼叫到就會紅
    for module in (
        erp_tools.party_service,
        erp_tools.inventory_service,
        erp_tools.purchasing_service,
    ):
        for attr in dir(module):
            value = getattr(module, attr)
            if attr.startswith("_") or not callable(value):
                continue
            if getattr(value, "__module__", "") == module.__name__:
                monkeypatch.setattr(
                    module, attr, AsyncMock(side_effect=AssertionError(attr))
                )

    result = await getattr(erp_tools, tool_name)(*args, **kwargs)

    assert result == {"ok": False, "error": "無權限"}
    assert checker.await_args[0][0] == tool_name


def test_minimal_calls_cover_every_tool() -> None:
    """新增工具忘了補權限掃描會直接紅"""
    assert len(_MINIMAL_CALLS) == 23
