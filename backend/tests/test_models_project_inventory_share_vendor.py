"""專案/物料/分享/廠商模型測試。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ching_tech_os.models.inventory import (
    InventoryItemCreate,
    InventoryItemListItem,
    InventoryItemListResponse,
    InventoryOrderCreate,
    InventoryOrderListItem,
    InventoryOrderListResponse,
    InventoryOrderResponse,
    InventoryStockSummary,
    InventoryTransactionCreate,
    InventoryTransactionListItem,
    InventoryTransactionListResponse,
    InventoryTransactionResponse,
    OrderStatus,
    TransactionType,
    calculate_is_low_stock,
)
from ching_tech_os.models.project import (
    DeliveryScheduleCreate,
    DeliveryScheduleResponse,
    ProjectAttachmentCreate,
    ProjectAttachmentResponse,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectLinkResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectMeetingCreate,
    ProjectMeetingListItem,
    ProjectMeetingResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMilestoneCreate,
    ProjectMilestoneResponse,
    ProjectResponse,
)
from ching_tech_os.models.share import (
    PasswordRequiredResponse,
    PublicResourceResponse,
    ShareLinkCreate,
    ShareLinkListResponse,
    ShareLinkResponse,
)
from ching_tech_os.models.vendor import VendorCreate, VendorListItem, VendorListResponse, VendorResponse


def test_project_models_and_link_type_property() -> None:
    now = datetime.now()
    project_id = uuid4()

    project = ProjectResponse(
        id=project_id,
        name="專案 A",
        description="desc",
        status="active",
        start_date=date.today(),
        end_date=None,
        created_at=now,
        updated_at=now,
        created_by="admin",
    )
    assert project.name == "專案 A"

    member = ProjectMemberResponse(
        id=uuid4(),
        project_id=project_id,
        name="王小明",
        role="PM",
        company=None,
        email=None,
        phone=None,
        notes=None,
        is_internal=True,
        user_id=1,
        created_at=now,
    )
    meeting = ProjectMeetingListItem(
        id=uuid4(),
        title="週會",
        meeting_date=now,
        location="會議室",
        attendees=["A", "B"],
    )
    attachment = ProjectAttachmentResponse(
        id=uuid4(),
        project_id=project_id,
        filename="spec.pdf",
        file_type="pdf",
        file_size=123,
        storage_path="ctos://projects/spec.pdf",
        description=None,
        uploaded_at=now,
        uploaded_by="admin",
    )
    link_external = ProjectLinkResponse(
        id=uuid4(),
        project_id=project_id,
        title="網站",
        url="https://example.com",
        description=None,
        created_at=now,
    )
    link_nas = ProjectLinkResponse(
        id=uuid4(),
        project_id=project_id,
        title="NAS",
        url="nas://project/file.pdf",
        description=None,
        created_at=now,
    )
    assert link_external.link_type == "external"
    assert link_nas.link_type == "nas"

    milestone = ProjectMilestoneResponse(
        id=uuid4(),
        project_id=project_id,
        name="設計完成",
        milestone_type="design",
        planned_date=date.today(),
        actual_date=None,
        status="pending",
        notes=None,
        sort_order=1,
        created_at=now,
        updated_at=now,
    )
    delivery = DeliveryScheduleResponse(
        id=uuid4(),
        project_id=project_id,
        vendor="廠商 A",
        vendor_id=None,
        item="料件 A",
        item_id=None,
        quantity="2 台",
        order_date=date.today(),
        expected_delivery_date=None,
        actual_delivery_date=None,
        status="pending",
        notes=None,
        created_at=now,
        updated_at=now,
    )

    detail = ProjectDetailResponse(
        **project.model_dump(),
        members=[member],
        meetings=[meeting],
        attachments=[attachment],
        links=[link_external],
        milestones=[milestone],
        deliveries=[delivery],
    )
    assert detail.members[0].name == "王小明"

    plist = ProjectListResponse(
        items=[
            ProjectListItem(
                id=project_id,
                name="專案 A",
                status="active",
                start_date=None,
                end_date=None,
                updated_at=now,
            )
        ],
        total=1,
    )
    assert plist.total == 1

    # 建立/更新請求模型可正常建構
    assert ProjectCreate(name="P").name == "P"
    assert ProjectMemberCreate(name="M").name == "M"
    assert ProjectMeetingCreate(title="T", meeting_date=now).title == "T"
    assert ProjectAttachmentCreate(filename="a", storage_path="x").filename == "a"
    assert DeliveryScheduleCreate(vendor="v", item="i").vendor == "v"
    assert ProjectMilestoneCreate(name="m").status == "pending"


def test_inventory_models_and_helpers() -> None:
    now = datetime.now()
    item_id = uuid4()

    assert calculate_is_low_stock(Decimal("1"), Decimal("2")) is True
    assert calculate_is_low_stock(Decimal("2"), Decimal("1")) is False
    assert calculate_is_low_stock(None, Decimal("1")) is False

    item = InventoryItemListItem(
        id=item_id,
        name="馬達",
        model="X1",
        specification=None,
        unit="個",
        category="機械",
        storage_location=None,
        default_vendor=None,
        current_stock=Decimal("5"),
        min_stock=Decimal("1"),
        is_low_stock=False,
        updated_at=now,
    )
    items = InventoryItemListResponse(items=[item], total=1)
    assert items.total == 1

    tx = InventoryTransactionResponse(
        id=uuid4(),
        item_id=item_id,
        type=TransactionType.IN,
        quantity=Decimal("2"),
        transaction_date=date.today(),
        vendor="v",
        project_id=None,
        notes=None,
        created_at=now,
        created_by="admin",
        project_name=None,
    )
    tx_list = InventoryTransactionListResponse(
        items=[
            InventoryTransactionListItem(
                id=tx.id,
                item_id=item_id,
                type=TransactionType.OUT,
                quantity=Decimal("1"),
                transaction_date=date.today(),
                created_at=now,
            )
        ],
        total=1,
    )
    assert tx.type == TransactionType.IN
    assert tx_list.total == 1

    order = InventoryOrderResponse(
        id=uuid4(),
        item_id=item_id,
        order_quantity=Decimal("3"),
        order_date=date.today(),
        expected_delivery_date=None,
        actual_delivery_date=None,
        status=OrderStatus.PENDING,
        vendor=None,
        project_id=None,
        notes=None,
        created_at=now,
        updated_at=now,
        created_by=None,
    )
    orders = InventoryOrderListResponse(
        items=[
            InventoryOrderListItem(
                id=order.id,
                item_id=item_id,
                order_quantity=Decimal("3"),
                status=OrderStatus.ORDERED,
                created_at=now,
                updated_at=now,
            )
        ],
        total=1,
    )
    assert orders.items[0].status == OrderStatus.ORDERED

    summary = InventoryStockSummary(
        item_id=item_id,
        item_name="馬達",
        current_stock=Decimal("5"),
        min_stock=Decimal("1"),
        is_low_stock=False,
    )
    assert summary.recent_in == Decimal("0")

    assert InventoryItemCreate(name="料件").name == "料件"
    assert InventoryTransactionCreate(type=TransactionType.IN, quantity=Decimal("1")).type == TransactionType.IN
    assert InventoryOrderCreate(order_quantity=Decimal("1")).order_quantity == Decimal("1")


def test_share_and_vendor_models() -> None:
    now = datetime.now(timezone.utc)
    link = ShareLinkResponse(
        token="abc123",
        url="/s/abc123",
        full_url="https://example.com/s/abc123",
        resource_type="content",
        resource_id="",
        resource_title="內容",
        expires_at=None,
        created_at=now,
    )
    links = ShareLinkListResponse(links=[link], is_admin=True)
    assert links.is_admin is True

    public = PublicResourceResponse(
        type="content",
        data={"content": "hello"},
        shared_by="admin",
        shared_at=now,
        expires_at=None,
    )
    assert public.data["content"] == "hello"

    pwd = PasswordRequiredResponse()
    assert pwd.requires_password is True

    create = ShareLinkCreate(resource_type="content", content="c", filename="f.txt")
    assert create.filename == "f.txt"

    vendor = VendorResponse(
        id=uuid4(),
        name="廠商",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    vendor_list = VendorListResponse(items=[VendorListItem(id=vendor.id, name=vendor.name)], total=1)
    assert vendor_list.total == 1
    assert VendorCreate(name="V").name == "V"
