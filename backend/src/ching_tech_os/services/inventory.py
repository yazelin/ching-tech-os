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
                is_low_stock=(
                    row["current_stock"] is not None
                    and row["min_stock"] is not None
                    and row["current_stock"] < row["min_stock"]
                ),
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
            is_low_stock=(
                row["current_stock"] is not None
                and row["min_stock"] is not None
                and row["current_stock"] < row["min_stock"]
            ),
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
            is_low_stock=(
                row["current_stock"] is not None
                and row["min_stock"] is not None
                and row["current_stock"] < row["min_stock"]
            ),
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
                is_low_stock=(
                    row["current_stock"] is not None
                    and row["min_stock"] is not None
                    and row["current_stock"] < row["min_stock"]
                ),
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
            is_low_stock=(
                row["current_stock"] is not None
                and row["min_stock"] is not None
                and row["current_stock"] < row["min_stock"]
            ),
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

        # 驗證類型
        if data.type not in ("in", "out"):
            raise InventoryError("類型必須是 'in'（進貨）或 'out'（出貨）")

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
            data.type,
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
