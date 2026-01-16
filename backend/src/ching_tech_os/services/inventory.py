"""物料管理服務"""

from datetime import date
from decimal import Decimal
from uuid import UUID

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


# ============================================
# 物料主檔 CRUD
# ============================================


async def list_inventory_items(
    query: str | None = None,
    category: str | None = None,
    low_stock: bool = False,
) -> InventoryItemListResponse:
    """列出物料"""
    async with get_connection() as conn:
        sql = """
            SELECT
                id, name, specification, unit, category,
                current_stock, min_stock, updated_at
            FROM inventory_items
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if query:
            sql += f" AND (name ILIKE ${param_idx} OR specification ILIKE ${param_idx})"
            params.append(f"%{query}%")
            param_idx += 1

        if category:
            sql += f" AND category = ${param_idx}"
            params.append(category)
            param_idx += 1

        if low_stock:
            sql += " AND current_stock < COALESCE(min_stock, 0)"

        sql += " ORDER BY name ASC"

        rows = await conn.fetch(sql, *params)

        items = [
            InventoryItemListItem(
                id=row["id"],
                name=row["name"],
                specification=row["specification"],
                unit=row["unit"],
                category=row["category"],
                current_stock=row["current_stock"] or Decimal("0"),
                min_stock=row["min_stock"],
                is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

        return InventoryItemListResponse(items=items, total=len(items))


async def get_inventory_item(item_id: UUID) -> InventoryItemResponse:
    """取得物料詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE id = $1", item_id
        )
        if not row:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
        )


async def get_inventory_item_by_name(name: str) -> InventoryItemResponse | None:
    """依名稱取得物料"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE name = $1", name
        )
        if not row:
            return None

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
        )


async def search_inventory_items(keyword: str, limit: int = 10) -> list[InventoryItemListItem]:
    """搜尋物料（模糊匹配）"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, specification, unit, category, current_stock, min_stock, updated_at
            FROM inventory_items
            WHERE name ILIKE $1 OR specification ILIKE $1
            ORDER BY
                CASE WHEN name ILIKE $2 THEN 0 ELSE 1 END,
                name ASC
            LIMIT $3
            """,
            f"%{keyword}%",
            f"{keyword}%",
            limit,
        )

        return [
            InventoryItemListItem(
                id=row["id"],
                name=row["name"],
                specification=row["specification"],
                unit=row["unit"],
                category=row["category"],
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
) -> InventoryItemResponse:
    """建立物料"""
    async with get_connection() as conn:
        # 檢查名稱是否重複
        existing = await conn.fetchrow(
            "SELECT id FROM inventory_items WHERE name = $1", data.name
        )
        if existing:
            raise InventoryError(f"物料名稱 '{data.name}' 已存在")

        row = await conn.fetchrow(
            """
            INSERT INTO inventory_items (
                name, specification, unit, category, default_vendor,
                min_stock, notes, created_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            data.name,
            data.specification,
            data.unit,
            data.category,
            data.default_vendor,
            data.min_stock,
            data.notes,
            created_by,
        )

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
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
) -> InventoryItemResponse:
    """更新物料"""
    async with get_connection() as conn:
        # 檢查物料是否存在
        existing = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE id = $1", item_id
        )
        if not existing:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        # 如果要更新名稱，檢查是否重複
        if data.name and data.name != existing["name"]:
            duplicate = await conn.fetchrow(
                "SELECT id FROM inventory_items WHERE name = $1 AND id != $2",
                data.name,
                item_id,
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
            return await get_inventory_item(item_id)

        params.append(item_id)
        sql = f"""
            UPDATE inventory_items
            SET {', '.join(update_fields)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(sql, *params)

        return InventoryItemResponse(
            id=row["id"],
            name=row["name"],
            specification=row["specification"],
            unit=row["unit"],
            category=row["category"],
            default_vendor=row["default_vendor"],
            min_stock=row["min_stock"],
            current_stock=row["current_stock"] or Decimal("0"),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            is_low_stock=calculate_is_low_stock(row["current_stock"], row["min_stock"]),
        )


async def delete_inventory_item(item_id: UUID) -> None:
    """刪除物料"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM inventory_items WHERE id = $1", item_id
        )
        if result == "DELETE 0":
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")


# ============================================
# 進出貨記錄 CRUD
# ============================================


async def list_inventory_transactions(
    item_id: UUID,
    limit: int = 50,
) -> InventoryTransactionListResponse:
    """列出物料的進出貨記錄"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id, t.item_id, t.type, t.quantity, t.transaction_date,
                t.vendor, t.project_id, t.notes, t.created_at, t.created_by,
                p.name as project_name
            FROM inventory_transactions t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.item_id = $1
            ORDER BY t.transaction_date DESC, t.created_at DESC
            LIMIT $2
            """,
            item_id,
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
            "SELECT COUNT(*) FROM inventory_transactions WHERE item_id = $1",
            item_id,
        )

        return InventoryTransactionListResponse(items=items, total=total)


async def get_inventory_transaction(transaction_id: UUID) -> InventoryTransactionResponse:
    """取得進出貨記錄詳情"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                t.*, p.name as project_name
            FROM inventory_transactions t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.id = $1
            """,
            transaction_id,
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
) -> InventoryTransactionResponse:
    """建立進出貨記錄"""
    async with get_connection() as conn:
        # 檢查物料是否存在
        item = await conn.fetchrow(
            "SELECT id, current_stock FROM inventory_items WHERE id = $1", item_id
        )
        if not item:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        # 類型已由 Pydantic 的 TransactionType Enum 驗證

        # 驗證專案是否存在（如果有指定）
        if data.project_id:
            project = await conn.fetchrow(
                "SELECT id FROM projects WHERE id = $1", data.project_id
            )
            if not project:
                raise InventoryError(f"專案 {data.project_id} 不存在")

        row = await conn.fetchrow(
            """
            INSERT INTO inventory_transactions (
                item_id, type, quantity, transaction_date, vendor, project_id, notes, created_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
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


async def delete_inventory_transaction(transaction_id: UUID) -> None:
    """刪除進出貨記錄"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM inventory_transactions WHERE id = $1", transaction_id
        )
        if result == "DELETE 0":
            raise InventoryTransactionNotFoundError(f"進出貨記錄 {transaction_id} 不存在")


# ============================================
# 庫存統計
# ============================================


async def get_categories() -> list[str]:
    """取得所有類別"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT category FROM inventory_items
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
            """
        )
        return [row["category"] for row in rows]


async def get_low_stock_count() -> int:
    """取得庫存不足的物料數量"""
    async with get_connection() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM inventory_items
            WHERE min_stock IS NOT NULL AND current_stock < min_stock
            """
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
) -> ItemLookupResult:
    """
    依 ID 或名稱查詢物料（模糊匹配）

    Args:
        item_id: 物料 ID
        item_name: 物料名稱（會模糊匹配）
        include_stock: 是否包含庫存欄位

    Returns:
        ItemLookupResult 包含查詢結果、錯誤訊息或候選列表
    """
    if not item_id and not item_name:
        return ItemLookupResult(error="請提供物料 ID 或物料名稱")

    async with get_connection() as conn:
        if item_id:
            try:
                columns = "id, name, unit, current_stock" if include_stock else "id, name, unit"
                row = await conn.fetchrow(
                    f"SELECT {columns} FROM inventory_items WHERE id = $1",
                    UUID(item_id),
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
                WHERE name ILIKE $1
                ORDER BY CASE WHEN name = $2 THEN 0 ELSE 1 END, name
                LIMIT 5
                """,
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
) -> ProjectLookupResult:
    """
    依 ID 或名稱查詢專案（模糊匹配）

    Args:
        project_id: 專案 ID
        project_name: 專案名稱（會模糊匹配）

    Returns:
        ProjectLookupResult 包含查詢結果、錯誤訊息或候選列表
    """
    if not project_id and not project_name:
        return ProjectLookupResult()  # 無專案，不是錯誤

    async with get_connection() as conn:
        if project_id:
            try:
                row = await conn.fetchrow(
                    "SELECT id, name FROM projects WHERE id = $1",
                    UUID(project_id),
                )
                if not row:
                    return ProjectLookupResult(error=f"找不到專案 ID: {project_id}")
                return ProjectLookupResult(project=dict(row))
            except ValueError:
                return ProjectLookupResult(error=f"無效的專案 ID 格式: {project_id}")
        else:
            rows = await conn.fetch(
                "SELECT id, name FROM projects WHERE name ILIKE $1 LIMIT 3",
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


async def get_item_with_transactions(item_id: UUID, limit: int = 5) -> dict:
    """
    取得物料詳情及近期交易記錄

    Args:
        item_id: 物料 ID
        limit: 交易記錄數量限制

    Returns:
        包含物料資訊和交易記錄的字典
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM inventory_items WHERE id = $1",
            item_id,
        )
        if not row:
            raise InventoryItemNotFoundError(f"物料 {item_id} 不存在")

        transactions = await conn.fetch(
            """
            SELECT t.*, p.name as project_name
            FROM inventory_transactions t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.item_id = $1
            ORDER BY t.transaction_date DESC, t.created_at DESC
            LIMIT $2
            """,
            item_id,
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

    Returns:
        更新後的庫存數量
    """
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO inventory_transactions (
                item_id, type, quantity, transaction_date, vendor, project_id, notes, created_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            item_id,
            transaction_type,
            quantity,
            transaction_date or date.today(),
            vendor,
            project_id,
            notes,
            created_by,
        )

        new_stock = await conn.fetchval(
            "SELECT current_stock FROM inventory_items WHERE id = $1",
            item_id,
        )
        return new_stock or Decimal("0")
