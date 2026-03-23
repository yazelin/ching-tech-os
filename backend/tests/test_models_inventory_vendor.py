"""測試 inventory 和 vendor 資料模型"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from ching_tech_os.models.inventory import (
    InventoryItemBase,
    InventoryItemCreate,
    InventoryItemListItem,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryOrderBase,
    InventoryOrderCreate,
    InventoryOrderListItem,
    InventoryOrderListResponse,
    InventoryOrderResponse,
    InventoryOrderUpdate,
    InventoryStockSummary,
    InventoryTransactionBase,
    InventoryTransactionCreate,
    InventoryTransactionListItem,
    InventoryTransactionListResponse,
    InventoryTransactionResponse,
    InventoryTransactionUpdate,
    OrderStatus,
    TransactionType,
    calculate_is_low_stock,
)
from ching_tech_os.models.vendor import (
    VendorBase,
    VendorCreate,
    VendorListItem,
    VendorListResponse,
    VendorResponse,
    VendorUpdate,
)


# ============================================
# Enum 測試
# ============================================


class TestTransactionType:
    def test_values(self):
        assert TransactionType.IN == "in"
        assert TransactionType.OUT == "out"

    def test_from_value(self):
        assert TransactionType("in") is TransactionType.IN
        assert TransactionType("out") is TransactionType.OUT


class TestOrderStatus:
    def test_values(self):
        assert OrderStatus.PENDING == "pending"
        assert OrderStatus.ORDERED == "ordered"
        assert OrderStatus.DELIVERED == "delivered"
        assert OrderStatus.CANCELLED == "cancelled"

    def test_from_value(self):
        assert OrderStatus("pending") is OrderStatus.PENDING


# ============================================
# calculate_is_low_stock 測試
# ============================================


class TestCalculateIsLowStock:
    def test_both_none(self):
        assert calculate_is_low_stock(None, None) is False

    def test_current_none(self):
        assert calculate_is_low_stock(None, Decimal("10")) is False

    def test_min_none(self):
        assert calculate_is_low_stock(Decimal("5"), None) is False

    def test_low_stock(self):
        assert calculate_is_low_stock(Decimal("3"), Decimal("10")) is True

    def test_not_low_stock(self):
        assert calculate_is_low_stock(Decimal("15"), Decimal("10")) is False

    def test_equal_not_low(self):
        assert calculate_is_low_stock(Decimal("10"), Decimal("10")) is False


# ============================================
# 物料主檔 Model 測試
# ============================================


class TestInventoryItemBase:
    def test_required_fields(self):
        item = InventoryItemBase(name="螺絲")
        assert item.name == "螺絲"
        assert item.model is None
        assert item.unit is None
        assert item.min_stock == Decimal("0")

    def test_all_fields(self):
        item = InventoryItemBase(
            name="螺絲",
            model="M8x20",
            specification="不鏽鋼",
            unit="個",
            category="五金",
            default_vendor="ABC",
            storage_location="A-01",
            min_stock=Decimal("100"),
            notes="常用",
        )
        assert item.specification == "不鏽鋼"
        assert item.storage_location == "A-01"


class TestInventoryItemCreate:
    def test_inherits_base(self):
        item = InventoryItemCreate(name="電阻")
        assert item.name == "電阻"


class TestInventoryItemUpdate:
    def test_all_optional(self):
        update = InventoryItemUpdate()
        assert update.name is None
        assert update.min_stock is None

    def test_partial(self):
        update = InventoryItemUpdate(name="新名稱", unit="台")
        assert update.name == "新名稱"


class TestInventoryItemResponse:
    def test_full(self):
        now = datetime.now()
        uid = uuid4()
        resp = InventoryItemResponse(
            id=uid,
            name="測試物料",
            current_stock=Decimal("50"),
            created_at=now,
            updated_at=now,
            is_low_stock=True,
        )
        assert resp.id == uid
        assert resp.current_stock == Decimal("50")
        assert resp.is_low_stock is True


class TestInventoryItemListItem:
    def test_defaults(self):
        now = datetime.now()
        item = InventoryItemListItem(
            id=uuid4(), name="物料A", updated_at=now,
        )
        assert item.current_stock == Decimal("0")
        assert item.is_low_stock is False
        assert item.model is None


class TestInventoryItemListResponse:
    def test_structure(self):
        resp = InventoryItemListResponse(items=[], total=0)
        assert resp.total == 0
        assert resp.items == []


# ============================================
# 進出貨記錄 Model 測試
# ============================================


class TestInventoryTransactionBase:
    def test_required(self):
        tx = InventoryTransactionBase(
            type=TransactionType.IN,
            quantity=Decimal("10"),
        )
        assert tx.type == TransactionType.IN
        assert tx.transaction_date == date.today()
        assert tx.vendor is None

    def test_all_fields(self):
        pid = uuid4()
        tx = InventoryTransactionBase(
            type=TransactionType.OUT,
            quantity=Decimal("5"),
            transaction_date=date(2025, 1, 1),
            vendor="廠商A",
            project_id=pid,
            notes="出貨備註",
        )
        assert tx.vendor == "廠商A"
        assert tx.project_id == pid


class TestInventoryTransactionCreate:
    def test_inherits(self):
        tx = InventoryTransactionCreate(
            type=TransactionType.IN, quantity=Decimal("1"),
        )
        assert tx.quantity == Decimal("1")


class TestInventoryTransactionUpdate:
    def test_all_optional(self):
        update = InventoryTransactionUpdate()
        assert update.type is None
        assert update.quantity is None

    def test_partial(self):
        update = InventoryTransactionUpdate(quantity=Decimal("20"))
        assert update.quantity == Decimal("20")


class TestInventoryTransactionResponse:
    def test_full(self):
        now = datetime.now()
        uid = uuid4()
        item_id = uuid4()
        resp = InventoryTransactionResponse(
            id=uid,
            item_id=item_id,
            type=TransactionType.OUT,
            quantity=Decimal("3"),
            created_at=now,
            project_name="專案A",
        )
        assert resp.item_id == item_id
        assert resp.project_name == "專案A"


class TestInventoryTransactionListItem:
    def test_full(self):
        now = datetime.now()
        item = InventoryTransactionListItem(
            id=uuid4(),
            item_id=uuid4(),
            type=TransactionType.IN,
            quantity=Decimal("100"),
            transaction_date=date.today(),
            created_at=now,
        )
        assert item.vendor is None
        assert item.created_by is None


class TestInventoryTransactionListResponse:
    def test_structure(self):
        resp = InventoryTransactionListResponse(items=[], total=5)
        assert resp.total == 5


# ============================================
# 訂購記錄 Model 測試
# ============================================


class TestInventoryOrderBase:
    def test_required(self):
        order = InventoryOrderBase(order_quantity=Decimal("50"))
        assert order.order_quantity == Decimal("50")
        assert order.order_date is None
        assert order.vendor is None

    def test_all_fields(self):
        pid = uuid4()
        order = InventoryOrderBase(
            order_quantity=Decimal("100"),
            order_date=date(2025, 6, 1),
            expected_delivery_date=date(2025, 6, 15),
            vendor="供應商B",
            project_id=pid,
            notes="急件",
        )
        assert order.expected_delivery_date == date(2025, 6, 15)


class TestInventoryOrderCreate:
    def test_inherits(self):
        order = InventoryOrderCreate(order_quantity=Decimal("10"))
        assert order.order_quantity == Decimal("10")


class TestInventoryOrderUpdate:
    def test_all_optional(self):
        update = InventoryOrderUpdate()
        assert update.order_quantity is None
        assert update.status is None

    def test_partial(self):
        update = InventoryOrderUpdate(
            status=OrderStatus.ORDERED,
            actual_delivery_date=date(2025, 7, 1),
        )
        assert update.status == OrderStatus.ORDERED


class TestInventoryOrderResponse:
    def test_full(self):
        now = datetime.now()
        uid = uuid4()
        item_id = uuid4()
        resp = InventoryOrderResponse(
            id=uid,
            item_id=item_id,
            order_quantity=Decimal("25"),
            created_at=now,
            updated_at=now,
            status=OrderStatus.DELIVERED,
            item_name="物料X",
        )
        assert resp.status == OrderStatus.DELIVERED
        assert resp.item_name == "物料X"

    def test_defaults(self):
        now = datetime.now()
        resp = InventoryOrderResponse(
            id=uuid4(),
            item_id=uuid4(),
            order_quantity=Decimal("5"),
            created_at=now,
            updated_at=now,
        )
        assert resp.status == OrderStatus.PENDING
        assert resp.actual_delivery_date is None


class TestInventoryOrderListItem:
    def test_full(self):
        now = datetime.now()
        item = InventoryOrderListItem(
            id=uuid4(),
            item_id=uuid4(),
            order_quantity=Decimal("30"),
            status=OrderStatus.CANCELLED,
            created_at=now,
            updated_at=now,
        )
        assert item.status == OrderStatus.CANCELLED
        assert item.item_name is None
        assert item.project_name is None


class TestInventoryOrderListResponse:
    def test_structure(self):
        resp = InventoryOrderListResponse(items=[], total=2)
        assert resp.total == 2


# ============================================
# 庫存摘要 Model 測試
# ============================================


class TestInventoryStockSummary:
    def test_full(self):
        summary = InventoryStockSummary(
            item_id=uuid4(),
            item_name="物料Z",
            current_stock=Decimal("80"),
            min_stock=Decimal("20"),
            is_low_stock=False,
            recent_in=Decimal("50"),
            recent_out=Decimal("30"),
        )
        assert summary.recent_in == Decimal("50")

    def test_defaults(self):
        summary = InventoryStockSummary(
            item_id=uuid4(),
            item_name="物料Y",
            current_stock=Decimal("0"),
            min_stock=None,
            is_low_stock=False,
        )
        assert summary.recent_in == Decimal("0")
        assert summary.recent_out == Decimal("0")


# ============================================
# Vendor Model 測試
# ============================================


class TestVendorBase:
    def test_required(self):
        vendor = VendorBase(name="廠商A")
        assert vendor.name == "廠商A"
        assert vendor.erp_code is None
        assert vendor.phone is None

    def test_all_fields(self):
        vendor = VendorBase(
            erp_code="V001",
            name="廠商A",
            short_name="A",
            contact_person="張三",
            phone="02-1234-5678",
            fax="02-8765-4321",
            email="a@example.com",
            address="台北市",
            tax_id="12345678",
            payment_terms="月結30天",
            notes="VIP 廠商",
        )
        assert vendor.tax_id == "12345678"


class TestVendorCreate:
    def test_inherits(self):
        vendor = VendorCreate(name="新廠商")
        assert vendor.name == "新廠商"


class TestVendorUpdate:
    def test_all_optional(self):
        update = VendorUpdate()
        assert update.name is None
        assert update.is_active is None

    def test_partial(self):
        update = VendorUpdate(name="改名", is_active=False)
        assert update.is_active is False


class TestVendorResponse:
    def test_full(self):
        now = datetime.now()
        uid = uuid4()
        resp = VendorResponse(
            id=uid,
            name="廠商B",
            created_at=now,
            updated_at=now,
        )
        assert resp.is_active is True
        assert resp.created_by is None


class TestVendorListItem:
    def test_defaults(self):
        item = VendorListItem(id=uuid4(), name="廠商C")
        assert item.is_active is True
        assert item.erp_code is None
        assert item.contact_person is None


class TestVendorListResponse:
    def test_structure(self):
        resp = VendorListResponse(items=[], total=0)
        assert resp.total == 0
        assert resp.items == []
