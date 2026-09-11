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
    assert models.PurchaseOrderUpdate(status="partial").status == "partial"


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
    body = models.PartyCreate(name="鴻佰科技")
    assert body.aliases == []
    assert body.is_supplier is False
    assert body.contacts == [] and body.addresses == []


def test_party_create_with_children() -> None:
    body = models.PartyCreate(
        name="鴻佰科技",
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


# ============================================================
# 回應模型
# ============================================================


def test_party_detail_response_defaults() -> None:
    detail = models.PartyDetailResponse(
        id=uuid4(), name="鴻佰科技", created_at=NOW, updated_at=NOW
    )
    assert detail.contacts == []
    assert detail.knowledge_count == 0


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
