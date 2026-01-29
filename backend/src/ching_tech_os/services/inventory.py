"""物料管理服務"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from ..config import settings
from ..database import get_connection
from ..models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListItem,
    InventoryItemListResponse,
    InventoryTransactionCreate,
    InventoryTransactionUpdate,
    InventoryTransactionResponse,
    InventoryTransactionListItem,
    InventoryTransactionListResponse,
    InventoryOrderCreate,
    InventoryOrderUpdate,
    InventoryOrderResponse,
    InventoryOrderListItem,
    InventoryOrderListResponse,
    OrderStatus,
    TransactionType,
    calculate_is_low_stock,
)


class InventoryError(Exception):
    """物料操作錯誤"""
    pass


class InventoryItemNotFoundError(InventoryError):
    """物料不存在"""
    pass


class InventoryTransactionNotFoundError(InventoryError):
    """進出貨記錄不存在"""
    pass


class InventoryOrderNotFoundError(InventoryError):
    """訂購記錄不存在"""
    pass


def _get_tenant_id(tenant_id: UUID | str | None) -> UUID:
    """處理 tenant_id 參數"""
    if tenant_id is None:
        return UUID(settings.default_tenant_id)
    if isinstance(tenant_id, str):
        return UUID(tenant_id)
    return tenant_id


# ============================================
# 物料主檔 CRUD
# ============================================


async def list_inventory_items(
    query: str | None = None,
    category: str | None = None,
    vendor: str | None = None,
    low_stock: bool = False,
    tenant_id: UUID | str | None = None,
) -> InventoryItemListResponse:
    """列出物料"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        sql = """
            SELECT
                id, name, model, specification, unit, category,
                storage_location, default_vendor, current_stock, min_stock, updated_at
            FROM inventory_items
            WHERE tenant_id = $1
        """
        params = [tid]
        param_idx = 2

        if query:
            # 正規化搜尋：移除連字符和空格後再比較
            # 讓 "kv7500" 可以匹配到 "PLC KV-7500"
            normalized_query = query.replace('-', '').replace(' ', '').lower()
            sql += f""" AND (
                REPLACE(REPLACE(LOWER(name), '-', ''), ' ', '') LIKE ${param_idx}
                OR REPLACE(REPLACE(LOWER(COALESCE(specification, '')), '-', ''), ' ', '') LIKE ${param_idx}
                OR REPLACE(REPLACE(LOWER(COALESCE(model, '')), '-', ''), ' ', '') LIKE ${param_idx}
                OR REPLACE(REPLACE(LOWER(COALESCE(category, '')), '-', ''), ' ', '') LIKE ${param_idx}
                OR REPLACE(REPLACE(LOWER(COALESCE(default_vendor, '')), '-', ''), ' ', '') LIKE ${param_idx}
            )"""
            params.append(f"%{normalized_query}%")
            param_idx += 1

        if category:
            sql += f" AND category = ${param_idx}"
            params.append(category)
            param_idx += 1

        if vendor:
            # 廠商名稱模糊搜尋
            sql += f" AND default_vendor ILIKE ${param_idx}"
            params.append(f"%{vendor}%")
            param_idx += 1

        if low_stock:
            sql += " AND current_stock < COALESCE(min_stock, 0)"

        sql += " ORDER BY name ASC"

        rows = await conn.fetch(sql, *params)

        items = [
            InventoryItemListItem(
                id=row["id"],
                name=row["name"],
                model=row["model"],
                specification=row["specification"],
                unit=row["unit"],
                category=row["category"],
                storage_location=row["storage_location"],
                default_vendor=row["default_vendor"],
                current_stock=row["current_stock"] or Decimal("0"),
                min_stock=row["min_stock"],
                is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

        return InventoryItemListResponse(items=items, total=len(items))


async def get_inventory_item(
    item_id: UUID,
    tenant_id: UUID | str | None = None,
) -> InventoryItemResponse:
    """取得物料詳情"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )
        if not row:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            model=row["model"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            storage_location=row["storage_location"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
        )


async def get_inventory_item_by_name(
    name: str,
    tenant_id: UUID | str | None = None,
) -> InventoryItemResponse | None:
    """依名稱取得物料"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE name = $1 AND tenant_id = $2",
            name,
            tid,
        )
        if not row:
            return None

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            model=row["model"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            storage_location=row["storage_location"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
        )


async def search_inventory_items(
    keyword: str,
    limit: int = 10,
    tenant_id: UUID | str | None = None,
) -> list[InventoryItemListItem]:
    """搜尋物料（模糊匹配）"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, model, specification, unit, category, storage_location,
                   current_stock, min_stock, updated_at
            FROM inventory_items
            WHERE tenant_id = $1 AND (name ILIKE $2 OR specification ILIKE $2 OR model ILIKE $2)
            ORDER BY
                CASE WHEN name ILIKE $3 THEN 0 ELSE 1 END,
                name ASC
            LIMIT $4
            """,
            tid,
            f"%{keyword}%",
            f"{keyword}%",
            limit,
        )

        return [
            InventoryItemListItem(
                id=row["id"],
                name=row["name"],
                model=row["model"],
                specification=row["specification"],
                unit=row["unit"],
                category=row["category"],
                storage_location=row["storage_location"],
                current_stock=row["current_stock"] or Decimal("0"),
                min_stock=row["min_stock"],
                is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]


async def create_inventory_item(
    data: InventoryItemCreate,
    created_by: str | None = None,
    tenant_id: UUID | str | None = None,
) -> InventoryItemResponse:
    """建立物料"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 檢查名稱是否重複（在同一租戶內）
        existing = await conn.fetchrow(
            "SELECT id FROM inventory_items WHERE name = $1 AND tenant_id = $2",
            data.name,
            tid,
        )
        if existing:
            raise InventoryError(f"物料名稱 '{data.name}' 已存在")

        row = await conn.fetchrow(
            """
            INSERT INTO inventory_items (
                name, model, specification, unit, category, default_vendor,
                storage_location, min_stock, notes, created_by, tenant_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            data.name,
            data.model,
            data.specification,
            data.unit,
            data.category,
            data.default_vendor,
            data.storage_location,
            data.min_stock,
            data.notes,
            created_by,
            tid,
        )

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            model=row["model"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            storage_location=row["storage_location"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=False,
        )


async def update_inventory_item(
    item_id: UUID,
    data: InventoryItemUpdate,
    tenant_id: UUID | str | None = None,
) -> InventoryItemResponse:
    """更新物料"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 檢查物料是否存在（在同一租戶內）
        existing = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )
        if not existing:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        # 如果要更新名稱，檢查是否重複（在同一租戶內）
        if data.name and data.name != existing["name"]:
            duplicate = await conn.fetchrow(
                "SELECT id FROM inventory_items WHERE name = $1 AND id != $2 AND tenant_id = $3",
                data.name,
                item_id,
                tid,
            )
            if duplicate:
                raise InventoryError(f"物料名稱 '{data.name}' 已存在")

        # 建立動態更新 SQL
        update_fields = []
        params = []
        param_idx = 1

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                update_fields.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not update_fields:
            return await get_inventory_item(item_id, tenant_id=tid)

        params.append(item_id)
        params.append(tid)
        sql = f"""
            UPDATE inventory_items
            SET {', '.join(update_fields)}
            WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
            RETURNING *
        """

        row = await conn.fetchrow(sql, *params)

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            model=row["model"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            storage_location=row["storage_location"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
        )


async def delete_inventory_item(
    item_id: UUID,
    tenant_id: UUID | str | None = None,
) -> None:
    """刪除物料"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM inventory_items WHERE id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )
        if result == "DELETE 0":
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")


# ============================================
# 進出貨記錄 CRUD
# ============================================


async def list_inventory_transactions(
    item_id: UUID,
    limit: int = 50,
    tenant_id: UUID | str | None = None,
) -> InventoryTransactionListResponse:
    """列出物料的進出貨記錄"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id, t.item_id, t.type, t.quantity, t.transaction_date,
                t.vendor, t.project_id, t.notes, t.created_at, t.created_by,
                p.name as project_name
            FROM inventory_transactions t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.item_id = $1 AND t.tenant_id = $2
            ORDER BY t.transaction_date DESC, t.created_at DESC
            LIMIT $3
            """,
            item_id,
            tid,
            limit,
        )

        items = [
            InventoryTransactionListItem(
                id=row["id"],
                item_id=row["item_id"],
                type=row["type"],
                quantity=row["quantity"],
                transaction_date=row["transaction_date"],
                vendor=row["vendor"],
                project_id=row["project_id"],
                project_name=row["project_name"],
                notes=row["notes"],
                created_at=row["created_at"],
                created_by=row["created_by"],
            )
            for row in rows
        ]

        # 取得總數
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM inventory_transactions WHERE item_id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )

        return InventoryTransactionListResponse(items=items, total=total)


async def get_inventory_transaction(
    transaction_id: UUID,
    tenant_id: UUID | str | None = None,
) -> InventoryTransactionResponse:
    """取得進出貨記錄詳情"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                t.*, p.name as project_name
            FROM inventory_transactions t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.id = $1 AND t.tenant_id = $2
            """,
            transaction_id,
            tid,
        )
        if not row:
            raise InventoryTransactionNotFoundError(f"進出貨記錄 {transaction_id} 不存在")

        return InventoryTransactionResponse(
            id=row["id"],
            item_id=row["item_id"],
            type=row["type"],
            quantity=row["quantity"],
            transaction_date=row["transaction_date"],
            vendor=row["vendor"],
            project_id=row["project_id"],
            notes=row["notes"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            project_name=row["project_name"],
        )


async def create_inventory_transaction(
    item_id: UUID,
    data: InventoryTransactionCreate,
    created_by: str | None = None,
    tenant_id: UUID | str | None = None,
) -> InventoryTransactionResponse:
    """建立進出貨記錄"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 檢查物料是否存在（在同一租戶內）
        item = await conn.fetchrow(
            "SELECT id, current_stock FROM inventory_items WHERE id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )
        if not item:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        # 類型已由 Pydantic 的 TransactionType Enum 驗證

        # 驗證專案是否存在（如果有指定，在同一租戶內）
        if data.project_id:
            project = await conn.fetchrow(
                "SELECT id FROM projects WHERE id = $1 AND tenant_id = $2",
                data.project_id,
                tid,
            )
            if not project:
                raise InventoryError(f"專案 {data.project_id} 不存在")

        row = await conn.fetchrow(
            """
            INSERT INTO inventory_transactions (
                item_id, type, quantity, transaction_date, vendor, project_id, notes, created_by, tenant_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            item_id,
            data.type.value,  # 使用 Enum 的值
            data.quantity,
            data.transaction_date or date.today(),
            data.vendor,
            data.project_id,
            data.notes,
            created_by,
            tid,
        )

        # 取得專案名稱
        project_name = None
        if data.project_id:
            project_row = await conn.fetchrow(
                "SELECT name FROM projects WHERE id = $1", data.project_id
            )
            if project_row:
                project_name = project_row["name"]

        return InventoryTransactionResponse(
            id=row["id"],
            item_id=row["item_id"],
            type=row["type"],
            quantity=row["quantity"],
            transaction_date=row["transaction_date"],
            vendor=row["vendor"],
            project_id=row["project_id"],
            notes=row["notes"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            project_name=project_name,
        )


async def delete_inventory_transaction(
    transaction_id: UUID,
    tenant_id: UUID | str | None = None,
) -> None:
    """刪除進出貨記錄"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM inventory_transactions WHERE id = $1 AND tenant_id = $2",
            transaction_id,
            tid,
        )
        if result == "DELETE 0":
            raise InventoryTransactionNotFoundError(f"進出貨記錄 {transaction_id} 不存在")


# ============================================
# 庫存統計
# ============================================


async def get_categories(tenant_id: UUID | str | None = None) -> list[str]:
    """取得所有類別"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT category FROM inventory_items
            WHERE tenant_id = $1 AND category IS NOT NULL AND category != ''
            ORDER BY category
            """,
            tid,
        )
        return [row["category"] for row in rows]


async def get_low_stock_count(tenant_id: UUID | str | None = None) -> int:
    """取得庫存不足的物料數量"""
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM inventory_items
            WHERE tenant_id = $1 AND min_stock IS NOT NULL AND current_stock < min_stock
            """,
            tid,
        )
        return count or 0


# ============================================
# MCP 工具輔助函數
# ============================================


class ItemLookupResult:
    """物料查詢結果"""
    def __init__(
        self,
        item: dict | None = None,
        error: str | None = None,
        candidates: list[dict] | None = None,
    ):
        self.item = item
        self.error = error
        self.candidates = candidates

    @property
    def found(self) -> bool:
        return self.item is not None

    @property
    def has_multiple(self) -> bool:
        return self.candidates is not None and len(self.candidates) > 1


class ProjectLookupResult:
    """專案查詢結果"""
    def __init__(
        self,
        project: dict | None = None,
        error: str | None = None,
        candidates: list[dict] | None = None,
    ):
        self.project = project
        self.error = error
        self.candidates = candidates

    @property
    def found(self) -> bool:
        return self.project is not None

    @property
    def has_multiple(self) -> bool:
        return self.candidates is not None and len(self.candidates) > 1


async def find_item_by_id_or_name(
    item_id: str | None = None,
    item_name: str | None = None,
    include_stock: bool = False,
    tenant_id: UUID | str | None = None,
) -> ItemLookupResult:
    """
    依 ID 或名稱查詢物料（模糊匹配）

    Args:
        item_id: 物料 ID
        item_name: 物料名稱（會模糊匹配）
        include_stock: 是否包含庫存欄位
        tenant_id: 租戶 ID

    Returns:
        ItemLookupResult 包含查詢結果、錯誤訊息或候選列表
    """
    if not item_id and not item_name:
        return ItemLookupResult(error="請提供物料 ID 或物料名稱")

    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        if item_id:
            try:
                columns = "id, name, unit, current_stock" if include_stock else "id, name, unit"
                row = await conn.fetchrow(
                    f"SELECT {columns} FROM inventory_items WHERE id = $1 AND tenant_id = $2",
                    UUID(item_id),
                    tid,
                )
                if not row:
                    return ItemLookupResult(error=f"找不到物料 ID: {item_id}")
                return ItemLookupResult(item=dict(row))
            except ValueError:
                return ItemLookupResult(error=f"無效的物料 ID 格式: {item_id}")
        else:
            columns = "id, name, unit, current_stock" if include_stock else "id, name, unit"
            rows = await conn.fetch(
                f"""
                SELECT {columns} FROM inventory_items
                WHERE tenant_id = $1 AND name ILIKE $2
                ORDER BY CASE WHEN name = $3 THEN 0 ELSE 1 END, name
                LIMIT 5
                """,
                tid,
                f"%{item_name}%",
                item_name,
            )
            if not rows:
                return ItemLookupResult(error=f"找不到物料「{item_name}」")

            # 精確匹配或只有一個結果
            if len(rows) == 1 or rows[0]["name"].lower() == item_name.lower():
                return ItemLookupResult(item=dict(rows[0]))

            # 多個候選
            return ItemLookupResult(
                candidates=[dict(r) for r in rows],
                error="找到多個匹配的物料",
            )


async def find_project_by_id_or_name(
    project_id: str | None = None,
    project_name: str | None = None,
    tenant_id: UUID | str | None = None,
) -> ProjectLookupResult:
    """
    依 ID 或名稱查詢專案（模糊匹配）

    Args:
        project_id: 專案 ID
        project_name: 專案名稱（會模糊匹配）
        tenant_id: 租戶 ID

    Returns:
        ProjectLookupResult 包含查詢結果、錯誤訊息或候選列表
    """
    if not project_id and not project_name:
        return ProjectLookupResult()  # 無專案，不是錯誤

    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        if project_id:
            try:
                row = await conn.fetchrow(
                    "SELECT id, name FROM projects WHERE id = $1 AND tenant_id = $2",
                    UUID(project_id),
                    tid,
                )
                if not row:
                    return ProjectLookupResult(error=f"找不到專案 ID: {project_id}")
                return ProjectLookupResult(project=dict(row))
            except ValueError:
                return ProjectLookupResult(error=f"無效的專案 ID 格式: {project_id}")
        else:
            rows = await conn.fetch(
                "SELECT id, name FROM projects WHERE tenant_id = $1 AND name ILIKE $2 LIMIT 3",
                tid,
                f"%{project_name}%",
            )
            if not rows:
                return ProjectLookupResult()  # 找不到專案，不算錯誤

            if len(rows) == 1:
                return ProjectLookupResult(project=dict(rows[0]))

            # 多個候選
            return ProjectLookupResult(
                candidates=[dict(r) for r in rows],
                error="找到多個匹配的專案",
            )


async def get_item_with_transactions(
    item_id: UUID,
    limit: int = 5,
    tenant_id: UUID | str | None = None,
) -> dict:
    """
    取得物料詳情及近期交易記錄

    Args:
        item_id: 物料 ID
        limit: 交易記錄數量限制
        tenant_id: 租戶 ID

    Returns:
        包含物料資訊和交易記錄的字典
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )
        if not row:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        transactions = await conn.fetch(
            """
            SELECT t.*, p.name as project_name
            FROM inventory_transactions t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.item_id = $1 AND t.tenant_id = $2
            ORDER BY t.transaction_date DESC, t.created_at DESC
            LIMIT $3
            """,
            item_id,
            tid,
            limit,
        )

        return {
            "item": dict(row),
            "transactions": [dict(t) for t in transactions],
        }


async def create_inventory_transaction_mcp(
    item_id: UUID,
    transaction_type: str,
    quantity: Decimal,
    transaction_date: date | None = None,
    vendor: str | None = None,
    project_id: UUID | None = None,
    notes: str | None = None,
    created_by: str = "linebot",
    tenant_id: UUID | str | None = None,
) -> Decimal:
    """
    建立進出貨記錄（MCP 專用，返回更新後的庫存）

    Args:
        item_id: 物料 ID
        transaction_type: 交易類型（'in' 或 'out'）
        quantity: 數量
        transaction_date: 交易日期
        vendor: 廠商
        project_id: 專案 ID
        notes: 備註
        created_by: 建立者
        tenant_id: 租戶 ID

    Returns:
        更新後的庫存數量
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO inventory_transactions (
                item_id, type, quantity, transaction_date, vendor, project_id, notes, created_by, tenant_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            item_id,
            transaction_type,
            quantity,
            transaction_date or date.today(),
            vendor,
            project_id,
            notes,
            created_by,
            tid,
        )

        new_stock = await conn.fetchval(
            "SELECT current_stock FROM inventory_items WHERE id = $1 AND tenant_id = $2",
            item_id,
            tid,
        )
        return new_stock or Decimal("0")


# ============================================
# 訂購記錄 CRUD
# ============================================


async def list_inventory_orders(
    item_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> InventoryOrderListResponse:
    """列出訂購記錄"""
    async with get_connection() as conn:
        sql = """
            SELECT
                o.id, o.item_id, o.order_quantity, o.order_date,
                o.expected_delivery_date, o.actual_delivery_date, o.status,
                o.vendor, o.project_id, o.notes, o.created_at, o.updated_at, o.created_by,
                i.name as item_name, p.name as project_name
            FROM inventory_orders o
            LEFT JOIN inventory_items i ON o.item_id = i.id
            LEFT JOIN projects p ON o.project_id = p.id
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if item_id:
            sql += f" AND o.item_id = ${param_idx}"
            params.append(item_id)
            param_idx += 1

        if status:
            sql += f" AND o.status = ${param_idx}"
            params.append(status)
            param_idx += 1

        sql += " ORDER BY o.order_date DESC NULLS LAST, o.created_at DESC"
        sql += f" LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)

        items = [
            InventoryOrderListItem(
                id=row["id"],
                item_id=row["item_id"],
                item_name=row["item_name"],
                order_quantity=row["order_quantity"],
                order_date=row["order_date"],
                expected_delivery_date=row["expected_delivery_date"],
                actual_delivery_date=row["actual_delivery_date"],
                status=row["status"],
                vendor=row["vendor"],
                project_id=row["project_id"],
                project_name=row["project_name"],
                notes=row["notes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                created_by=row["created_by"],
            )
            for row in rows
        ]

        # 取得總數
        count_sql = "SELECT COUNT(*) FROM inventory_orders WHERE 1=1"
        count_params = []
        param_idx = 1

        if item_id:
            count_sql += f" AND item_id = ${param_idx}"
            count_params.append(item_id)
            param_idx += 1

        if status:
            count_sql += f" AND status = ${param_idx}"
            count_params.append(status)

        total = await conn.fetchval(count_sql, *count_params)

        return InventoryOrderListResponse(items=items, total=total or 0)


async def get_inventory_order(order_id: UUID) -> InventoryOrderResponse:
    """取得訂購記錄詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                o.*, i.name as item_name, p.name as project_name
            FROM inventory_orders o
            LEFT JOIN inventory_items i ON o.item_id = i.id
            LEFT JOIN projects p ON o.project_id = p.id
            WHERE o.id = $1
            """,
            order_id,
        )
        if not row:
            raise InventoryOrderNotFoundError(f"訂購記錄 {order_id} 不存在")

        return InventoryOrderResponse(
            id=row["id"],
            item_id=row["item_id"],
            order_quantity=row["order_quantity"],
            order_date=row["order_date"],
            expected_delivery_date=row["expected_delivery_date"],
            actual_delivery_date=row["actual_delivery_date"],
            status=row["status"],
            vendor=row["vendor"],
            project_id=row["project_id"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            item_name=row["item_name"],
            project_name=row["project_name"],
        )


async def create_inventory_order(
    item_id: UUID,
    data: InventoryOrderCreate,
    created_by: str | None = None,
) -> InventoryOrderResponse:
    """建立訂購記錄"""
    async with get_connection() as conn:
        # 檢查物料是否存在
        item = await conn.fetchrow(
            "SELECT id, name FROM inventory_items WHERE id = $1", item_id
        )
        if not item:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        # 驗證專案是否存在（如果有指定）
        project_name = None
        if data.project_id:
            project = await conn.fetchrow(
                "SELECT id, name FROM projects WHERE id = $1", data.project_id
            )
            if not project:
                raise InventoryError(f"專案 {data.project_id} 不存在")
            project_name = project["name"]

        row = await conn.fetchrow(
            """
            INSERT INTO inventory_orders (
                item_id, order_quantity, order_date, expected_delivery_date,
                vendor, project_id, notes, created_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            item_id,
            data.order_quantity,
            data.order_date,
            data.expected_delivery_date,
            data.vendor,
            data.project_id,
            data.notes,
            created_by,
        )

        return InventoryOrderResponse(
            id=row["id"],
            item_id=row["item_id"],
            order_quantity=row["order_quantity"],
            order_date=row["order_date"],
            expected_delivery_date=row["expected_delivery_date"],
            actual_delivery_date=row["actual_delivery_date"],
            status=row["status"],
            vendor=row["vendor"],
            project_id=row["project_id"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            item_name=item["name"],
            project_name=project_name,
        )


async def update_inventory_order(
    order_id: UUID,
    data: InventoryOrderUpdate,
) -> InventoryOrderResponse:
    """更新訂購記錄"""
    async with get_connection() as conn:
        # 檢查訂購記錄是否存在
        existing = await conn.fetchrow(
            "SELECT * FROM inventory_orders WHERE id = $1", order_id
        )
        if not existing:
            raise InventoryOrderNotFoundError(f"訂購記錄 {order_id} 不存在")

        # 驗證專案是否存在（如果有指定）
        if data.project_id:
            project = await conn.fetchrow(
                "SELECT id FROM projects WHERE id = $1", data.project_id
            )
            if not project:
                raise InventoryError(f"專案 {data.project_id} 不存在")

        # 建立動態更新 SQL
        update_fields = []
        params = []
        param_idx = 1

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                # 處理 Enum 類型
                if isinstance(value, OrderStatus):
                    value = value.value
                update_fields.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not update_fields:
            return await get_inventory_order(order_id)

        params.append(order_id)
        sql = f"""
            UPDATE inventory_orders
            SET {', '.join(update_fields)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(sql, *params)

        # 取得關聯資訊
        item = await conn.fetchrow(
            "SELECT name FROM inventory_items WHERE id = $1", row["item_id"]
        )
        project_name = None
        if row["project_id"]:
            project = await conn.fetchrow(
                "SELECT name FROM projects WHERE id = $1", row["project_id"]
            )
            if project:
                project_name = project["name"]

        return InventoryOrderResponse(
            id=row["id"],
            item_id=row["item_id"],
            order_quantity=row["order_quantity"],
            order_date=row["order_date"],
            expected_delivery_date=row["expected_delivery_date"],
            actual_delivery_date=row["actual_delivery_date"],
            status=row["status"],
            vendor=row["vendor"],
            project_id=row["project_id"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            item_name=item["name"] if item else None,
            project_name=project_name,
        )


async def get_project_inventory_status(
    project_id: UUID,
    tenant_id: UUID | str | None = None,
) -> dict:
    """
    查詢指定專案的物料進出貨狀態

    Args:
        project_id: 專案 ID
        tenant_id: 租戶 ID

    Returns:
        包含專案名稱和各物料進出貨彙總的字典
    """
    tid = _get_tenant_id(tenant_id)
    async with get_connection() as conn:
        # 取得專案名稱
        project = await conn.fetchrow(
            "SELECT name FROM projects WHERE id = $1 AND tenant_id = $2",
            project_id,
            tid,
        )
        if not project:
            raise InventoryError(f"專案 {project_id} 不存在")

        # 查詢該專案所有進出貨記錄，按物料分組彙總
        rows = await conn.fetch(
            """
            SELECT
                i.id AS item_id,
                i.name AS item_name,
                i.unit,
                COALESCE(SUM(CASE WHEN t.type = 'in' THEN t.quantity ELSE 0 END), 0) AS total_in,
                COALESCE(SUM(CASE WHEN t.type = 'out' THEN t.quantity ELSE 0 END), 0) AS total_out
            FROM inventory_transactions t
            JOIN inventory_items i ON t.item_id = i.id
            WHERE t.project_id = $1 AND t.tenant_id = $2
            GROUP BY i.id, i.name, i.unit
            ORDER BY i.name
            """,
            project_id,
            tid,
        )

        items = [
            {
                "item_id": str(row["item_id"]),
                "item_name": row["item_name"],
                "unit": row["unit"],
                "total_in": row["total_in"],
                "total_out": row["total_out"],
            }
            for row in rows
        ]

        return {
            "project_name": project["name"],
            "items": items,
        }


async def delete_inventory_order(order_id: UUID) -> None:
    """刪除訂購記錄"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM inventory_orders WHERE id = $1", order_id
        )
        if result == "DELETE 0":
            raise InventoryOrderNotFoundError(f"訂購記錄 {order_id} 不存在")
