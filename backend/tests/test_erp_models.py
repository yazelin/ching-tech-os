"""往來與物料模組 Pydantic 模型測試。

重點：Update 模型對資料表 NOT NULL 的欄位明確送 null 要 422（ValidationError），
沒送的欄位不動，狀態值用 Literal 鎖住。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ching_tech_os.models import erp as models

NOW = datetime.now(timezone.utc)


# ============================================================
# NOT NULL 欄位送 null → 422
# ============================================================


@pytest.mark.parametrize(
    "model, field",
    [
        (models.PartyUpdate, "name"),
        (models.PartyUpdate, "aliases"),
        (models.PartyUpdate, "is_supplier"),
        (models.PartyUpdate, "is_customer"),
        (models.ItemUpdate, "code"),
        (models.ItemUpdate, "name"),
        (models.ItemUpdate, "aliases"),
        (models.WarehouseUpdate, "code"),
        (models.WarehouseUpdate, "name"),
        (models.PurchaseOrderUpdate, "supplier_id"),
        (models.PurchaseOrderUpdate, "status"),
        (models.PartyContactUpdate, "name"),
        (models.PartyContactUpdate, "is_primary"),
        (models.PartyAddressUpdate, "address"),
        (models.PartyAddressUpdate, "is_primary"),
    ],
)
def test_update_rejects_explicit_null(model, field) -> None:
    with pytest.raises(ValidationError) as exc:
        model(**{field: None})
    assert "不可為 null" in str(exc.value)


@pytest.mark.parametrize(
    "model, field",
    [
        (models.PartyUpdate, "tax_id"),
        (models.PartyUpdate, "notes"),
        (models.ItemUpdate, "spec"),
        (models.ItemUpdate, "default_supplier_id"),
        (models.PurchaseOrderUpdate, "project_id"),
        (models.PurchaseOrderUpdate, "expected_date"),
        (models.PartyContactUpdate, "phone"),
        (models.PartyContactUpdate, "notes"),
        (models.PartyAddressUpdate, "city"),
        (models.PartyAddressUpdate, "label"),
    ],
)
def test_update_allows_null_for_nullable_fields(model, field) -> None:
    body = model(**{field: None})
    assert field in body.model_dump(exclude_unset=True)


def test_update_unset_fields_are_excluded() -> None:
    body = models.PartyUpdate(payment_terms="月結 60 天")
    assert body.model_dump(exclude_unset=True) == {"payment_terms": "月結 60 天"}


# ============================================================
# Literal 鎖住的值
# ============================================================


def test_purchase_order_status_literal() -> None:
    with pytest.raises(ValidationError):
        models.PurchaseOrderUpdate(status="open")
    assert models.PurchaseOrderUpdate(status="draft").status == "draft"
    assert models.PurchaseOrderUpdate(status="ordered").status == "ordered"


@pytest.mark.parametrize("status", ["partial", "received", "cancelled"])
def test_purchase_order_update_rejects_computed_status(status) -> None:
    """F10：partial／received 由收貨算出來，cancelled 只能走 cancel 端點"""
    with pytest.raises(ValidationError):
        models.PurchaseOrderUpdate(status=status)
    # 建立時仍可指定 draft／ordered 以外的值由 service 決定，這裡只鎖更新
    assert models.PurchaseOrderCreate(
        supplier_id=uuid4(), lines=[{"item_id": uuid4(), "qty": 1}], status="draft"
    ).status == "draft"


def test_stock_reason_literal() -> None:
    with pytest.raises(ValidationError):
        models.StockAdjustRequest(
            item_id=uuid4(), warehouse_id=uuid4(), qty_delta=1, reason="unknown"
        )
    body = models.StockAdjustRequest(
        item_id=uuid4(), warehouse_id=uuid4(), qty_delta=Decimal("-2"), reason="issue"
    )
    assert body.qty_delta == Decimal("-2")


# ============================================================
# 建立請求
# ============================================================


def test_party_create_defaults() -> None:
    body = models.PartyCreate(name="丙丁科技")
    assert body.aliases == []
    assert body.is_supplier is False
    assert body.contacts == [] and body.addresses == []


def test_party_create_with_children() -> None:
    body = models.PartyCreate(
        name="丙丁科技",
        contacts=[{"name": "陳先生", "phone": "03-1234567", "is_primary": True}],
        addresses=[{"address": "桃園市中壢區"}],
    )
    assert body.contacts[0].is_primary is True
    assert body.addresses[0].is_primary is False


def test_purchase_order_create_requires_at_least_one_line() -> None:
    with pytest.raises(ValidationError):
        models.PurchaseOrderCreate(supplier_id=uuid4(), lines=[])


def test_purchase_order_create_default_status_is_ordered() -> None:
    body = models.PurchaseOrderCreate(
        supplier_id=uuid4(), lines=[{"item_id": uuid4(), "qty": 10}]
    )
    assert body.status == "ordered"
    assert body.lines[0].unit_price is None


def test_receive_request_defaults() -> None:
    body = models.PurchaseOrderReceiveRequest()
    assert body.all is False and body.lines == []


def test_receive_line_accepts_line_id_or_item_id() -> None:
    """F1：行項的 key 是 line_id，item_id 只在該物料單獨一行時夠用"""
    line_id = uuid4()
    assert models.ReceiveLine(line_id=line_id, qty=1).line_id == line_id
    assert models.ReceiveLine(item_id=uuid4(), qty=1).line_id is None


def test_receive_line_requires_one_of_them() -> None:
    with pytest.raises(ValidationError) as exc:
        models.ReceiveLine(qty=1)
    assert "line_id 或 item_id" in str(exc.value)


def test_party_merge_request() -> None:
    keep, drop = uuid4(), uuid4()
    body = models.PartyMergeRequest(keep_id=keep, drop_id=drop)
    assert (body.keep_id, body.drop_id) == (keep, drop)


# ============================================================
# 回應模型
# ============================================================


def test_party_detail_response_defaults() -> None:
    detail = models.PartyDetailResponse(
        id=uuid4(), name="丙丁科技", created_at=NOW, updated_at=NOW
    )
    assert detail.contacts == []
    assert detail.knowledge_count == 0
    assert detail.audit_id is None


@pytest.mark.parametrize(
    "model, extra",
    [
        (models.PartyDetailResponse, {"name": "丙丁科技"}),
        (models.ItemDetailResponse, {"code": "A1", "name": "螺絲"}),
        (models.WarehouseResponse, {"code": "MAIN", "name": "主倉"}),
        (
            models.PurchaseOrderDetailResponse,
            {"po_no": "PO-202609-001", "supplier_id": uuid4(), "status": "ordered"},
        ),
    ],
)
def test_write_responses_carry_audit_id(model, extra) -> None:
    """F2：建立／更新的回應要帶得動 audit_id"""
    audit_id = uuid4()
    obj = model(
        id=uuid4(), created_at=NOW, updated_at=NOW, audit_id=audit_id, **extra
    )
    assert obj.audit_id == audit_id


def test_contact_and_address_update_responses_carry_audit_id() -> None:
    """PR 4b：PUT contacts／addresses 回傳更新後的物件＋audit_id"""
    audit_id = uuid4()
    contact = models.PartyContactUpdateResponse(
        id=uuid4(),
        party_id=uuid4(),
        name="陳先生",
        created_at=NOW,
        updated_at=NOW,
        audit_id=audit_id,
    )
    assert contact.audit_id == audit_id

    address = models.PartyAddressUpdateResponse(
        id=uuid4(),
        party_id=uuid4(),
        address="桃園",
        created_at=NOW,
        updated_at=NOW,
        audit_id=audit_id,
    )
    assert address.audit_id == audit_id


def test_stock_movement_item_has_no_item_code() -> None:
    """nit：沒人填的 item_code 已經拿掉，不要再宣告假欄位"""
    assert "item_code" not in models.StockMovementItem.model_fields


def test_item_detail_response_accepts_balances() -> None:
    detail = models.ItemDetailResponse(
        id=uuid4(),
        code="CTOS-A1",
        name="不鏽鋼螺絲",
        created_at=NOW,
        updated_at=NOW,
        balances=[
            {"warehouse_id": uuid4(), "warehouse_name": "主倉", "qty": Decimal("70")}
        ],
        total_qty=Decimal("70"),
    )
    assert detail.balances[0].qty == Decimal("70")


def test_audit_response_holds_diff() -> None:
    audit = models.AuditResponse(
        id=uuid4(),
        entity_type="party",
        action="update",
        diff={"name": {"before": "A", "after": "B"}},
        created_at=NOW,
    )
    assert audit.via == "mcp"
    assert audit.diff["name"]["after"] == "B"


def test_stock_mutation_response_defaults() -> None:
    assert models.StockMutationResponse().movements == []
