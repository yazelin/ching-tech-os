"""物料與庫存服務（items / warehouses / stock_balances / stock_movements）

庫存是簡化分類帳：每次異動寫一筆 `stock_movements`，同一交易用
`INSERT ... ON CONFLICT (item_id, warehouse_id) DO UPDATE SET qty = qty + delta`
累計 `stock_balances`。餘額不可為負（`allow_negative=False` 時拋
`NegativeStockError`，整個交易回滾）。不做成本、不做批號。
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..database import get_connection
from .erp import (
    InvalidOperationError,
    NegativeStockError,
    audit,
    build_diff,
    like_pattern,
)

logger = logging.getLogger(__name__)

_ITEM_FIELDS = (
    "code",
    "name",
    "spec",
    "unit",
    "item_group",
    "default_supplier_id",
    "purchase_price",
    "lead_days",
    "aliases",
    "notes",
    "source_ref",
)

_WAREHOUSE_FIELDS = ("code", "name")


def _pick(data: dict, fields: tuple[str, ...]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in fields}


# ============================================================
# 物料清單與明細
# ============================================================


async def list_items(
    q: str | None = None,
    item_group: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """物料清單（含各倉合計數量與預設供應商名稱）"""
    offset = (max(page, 1) - 1) * page_size
    pattern = like_pattern(q) if q else None
    where = r"""
        WHERE i.deleted_at IS NULL
          AND ($1::text IS NULL OR i.item_group = $1)
          AND (
            $2::text IS NULL
            OR i.code ILIKE $2 ESCAPE '\'
            OR i.name ILIKE $2 ESCAPE '\'
            OR COALESCE(i.spec, '') ILIKE $2 ESCAPE '\'
            OR EXISTS (
                SELECT 1 FROM unnest(i.aliases) AS a WHERE a ILIKE $2 ESCAPE '\'
            )
          )
    """
    async with get_connection() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM items i {where}", item_group, pattern
        )
        rows = await conn.fetch(
            f"""
            SELECT
                i.id, i.code, i.name, i.spec, i.unit, i.item_group,
                i.default_supplier_id, p.name AS default_supplier_name,
                i.purchase_price, i.created_at, i.updated_at,
                COALESCE((
                    SELECT SUM(b.qty) FROM stock_balances b WHERE b.item_id = i.id
                ), 0) AS total_qty
            FROM items i
            LEFT JOIN parties p ON p.id = i.default_supplier_id
            {where}
            ORDER BY i.updated_at DESC
            LIMIT $3 OFFSET $4
            """,
            item_group,
            pattern,
            page_size,
            offset,
        )
    return {"items": [dict(r) for r in rows], "total": int(total or 0)}


async def get_item_detail(
    item_id: UUID, movement_limit: int = 20
) -> dict[str, Any] | None:
    """物料明細：主檔＋各倉餘額＋最近異動＋預設供應商"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT i.id, i.code, i.name, i.spec, i.unit, i.item_group,
                   i.default_supplier_id, p.name AS default_supplier_name,
                   i.purchase_price, i.lead_days, i.aliases, i.notes,
                   i.source_ref, i.created_by, i.created_at, i.updated_at
            FROM items i
            LEFT JOIN parties p ON p.id = i.default_supplier_id
            WHERE i.id = $1 AND i.deleted_at IS NULL
            """,
            item_id,
        )
        if row is None:
            return None
        balances = await conn.fetch(
            """
            SELECT b.warehouse_id, w.code AS warehouse_code,
                   w.name AS warehouse_name, b.qty
            FROM stock_balances b
            JOIN warehouses w ON w.id = b.warehouse_id
            WHERE b.item_id = $1
            ORDER BY w.code
            """,
            item_id,
        )
        movements = await conn.fetch(
            """
            SELECT m.id, m.item_id, m.warehouse_id, w.name AS warehouse_name,
                   m.qty_delta, m.reason, m.ref_type, m.ref_id, m.note,
                   m.actor_user_id, m.created_at
            FROM stock_movements m
            LEFT JOIN warehouses w ON w.id = m.warehouse_id
            WHERE m.item_id = $1
            ORDER BY m.created_at DESC
            LIMIT $2
            """,
            item_id,
            movement_limit,
        )

    detail = dict(row)
    detail["balances"] = [dict(r) for r in balances]
    detail["total_qty"] = sum((b["qty"] for b in balances), Decimal(0))
    detail["movements"] = [dict(r) for r in movements]
    return detail


# ============================================================
# 物料 CRUD
# ============================================================


async def create_item(
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """建立物料；料號重複時拋 InvalidOperationError（不吃 FK 例外變 500）"""
    async with get_connection() as conn, conn.transaction():
        exists = await conn.fetchval(
            "SELECT 1 FROM items WHERE lower(code) = lower($1)", data["code"]
        )
        if exists:
            raise InvalidOperationError(f"料號已存在：{data['code']}")
        row = await conn.fetchrow(
            """
            INSERT INTO items
                (code, name, spec, unit, item_group, default_supplier_id,
                 purchase_price, lead_days, aliases, notes, source_ref, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            data["code"],
            data["name"],
            data.get("spec"),
            data.get("unit"),
            data.get("item_group"),
            data.get("default_supplier_id"),
            data.get("purchase_price"),
            data.get("lead_days"),
            list(data.get("aliases") or []),
            data.get("notes"),
            data.get("source_ref"),
            actor_user_id,
        )
        audit_id = await audit(
            conn,
            "item",
            row["id"],
            "create",
            build_diff(None, _pick(dict(row), _ITEM_FIELDS)),
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def update_item(
    item_id: UUID,
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """更新物料主檔；找不到回 None"""
    fields = _pick(data, _ITEM_FIELDS)
    async with get_connection() as conn, conn.transaction():
        before = await conn.fetchrow(
            "SELECT * FROM items WHERE id = $1 AND deleted_at IS NULL", item_id
        )
        if before is None:
            return None
        if "code" in fields:
            clash = await conn.fetchval(
                "SELECT 1 FROM items WHERE lower(code) = lower($1) AND id <> $2",
                fields["code"],
                item_id,
            )
            if clash:
                raise InvalidOperationError(f"料號已存在：{fields['code']}")
        if fields:
            names = list(fields.keys())
            assignments = ", ".join(f"{n} = ${i + 2}" for i, n in enumerate(names))
            row = await conn.fetchrow(
                f"""
                UPDATE items
                SET {assignments}, updated_at = NOW()
                WHERE id = $1 AND deleted_at IS NULL
                RETURNING *
                """,
                item_id,
                *[fields[n] for n in names],
            )
        else:
            row = before
        audit_id = await audit(
            conn,
            "item",
            item_id,
            "update",
            build_diff(_pick(dict(before), _ITEM_FIELDS), _pick(dict(row), _ITEM_FIELDS)),
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def delete_item(
    item_id: UUID,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> UUID | None:
    """軟刪除物料；不存在或已刪回 None"""
    async with get_connection() as conn, conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE items
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id, code
            """,
            item_id,
        )
        if row is None:
            return None
        return await audit(
            conn,
            "item",
            item_id,
            "delete",
            {"code": row["code"]},
            actor_user_id,
            via,
            agent_name,
        )


# ============================================================
# 倉庫
# ============================================================


async def list_warehouses(page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """倉庫清單（只有五個，不做搜尋）"""
    offset = (max(page, 1) - 1) * page_size
    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM warehouses WHERE deleted_at IS NULL"
        )
        rows = await conn.fetch(
            """
            SELECT id, code, name, created_by, created_at, updated_at
            FROM warehouses
            WHERE deleted_at IS NULL
            ORDER BY code
            LIMIT $1 OFFSET $2
            """,
            page_size,
            offset,
        )
    return {"items": [dict(r) for r in rows], "total": int(total or 0)}


async def create_warehouse(
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """建立倉庫；代碼重複拋 InvalidOperationError"""
    async with get_connection() as conn, conn.transaction():
        exists = await conn.fetchval(
            "SELECT 1 FROM warehouses WHERE lower(code) = lower($1)", data["code"]
        )
        if exists:
            raise InvalidOperationError(f"倉庫代碼已存在：{data['code']}")
        row = await conn.fetchrow(
            """
            INSERT INTO warehouses (code, name, created_by)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            data["code"],
            data["name"],
            actor_user_id,
        )
        audit_id = await audit(
            conn,
            "warehouse",
            row["id"],
            "create",
            build_diff(None, _pick(dict(row), _WAREHOUSE_FIELDS)),
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def update_warehouse(
    warehouse_id: UUID,
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """更新倉庫；找不到回 None"""
    fields = _pick(data, _WAREHOUSE_FIELDS)
    async with get_connection() as conn, conn.transaction():
        before = await conn.fetchrow(
            "SELECT * FROM warehouses WHERE id = $1 AND deleted_at IS NULL",
            warehouse_id,
        )
        if before is None:
            return None
        if fields:
            names = list(fields.keys())
            assignments = ", ".join(f"{n} = ${i + 2}" for i, n in enumerate(names))
            row = await conn.fetchrow(
                f"""
                UPDATE warehouses
                SET {assignments}, updated_at = NOW()
                WHERE id = $1 AND deleted_at IS NULL
                RETURNING *
                """,
                warehouse_id,
                *[fields[n] for n in names],
            )
        else:
            row = before
        audit_id = await audit(
            conn,
            "warehouse",
            warehouse_id,
            "update",
            build_diff(
                _pick(dict(before), _WAREHOUSE_FIELDS),
                _pick(dict(row), _WAREHOUSE_FIELDS),
            ),
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def delete_warehouse(
    warehouse_id: UUID,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> UUID | None:
    """軟刪除倉庫；還有餘額的不給刪"""
    async with get_connection() as conn, conn.transaction():
        qty = await conn.fetchval(
            """
            SELECT COALESCE(SUM(qty), 0) FROM stock_balances WHERE warehouse_id = $1
            """,
            warehouse_id,
        )
        if qty and Decimal(qty) != 0:
            raise InvalidOperationError("倉庫還有庫存餘額，不能刪除")
        row = await conn.fetchrow(
            """
            UPDATE warehouses
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id, code
            """,
            warehouse_id,
        )
        if row is None:
            return None
        return await audit(
            conn,
            "warehouse",
            warehouse_id,
            "delete",
            {"code": row["code"]},
            actor_user_id,
            via,
            agent_name,
        )


# ============================================================
# 庫存查詢
# ============================================================


async def get_stock(
    item_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """庫存查詢（item × warehouse 一列）；軟刪除的物料不列"""
    offset = (max(page, 1) - 1) * page_size
    where = """
        WHERE i.deleted_at IS NULL
          AND ($1::uuid IS NULL OR b.item_id = $1)
          AND ($2::uuid IS NULL OR b.warehouse_id = $2)
    """
    async with get_connection() as conn:
        total = await conn.fetchval(
            f"""
            SELECT count(*)
            FROM stock_balances b
            JOIN items i ON i.id = b.item_id
            {where}
            """,
            item_id,
            warehouse_id,
        )
        rows = await conn.fetch(
            f"""
            SELECT b.item_id, i.code AS item_code, i.name AS item_name,
                   b.warehouse_id, w.code AS warehouse_code,
                   w.name AS warehouse_name, b.qty
            FROM stock_balances b
            JOIN items i ON i.id = b.item_id
            JOIN warehouses w ON w.id = b.warehouse_id
            {where}
            ORDER BY i.code, w.code
            LIMIT $3 OFFSET $4
            """,
            item_id,
            warehouse_id,
            page_size,
            offset,
        )
    return {"items": [dict(r) for r in rows], "total": int(total or 0)}


# ============================================================
# 庫存異動（核心）
# ============================================================


async def apply_movement(
    conn,
    item_id: UUID,
    warehouse_id: UUID,
    qty_delta,
    reason: str,
    ref_type: str | None = None,
    ref_id: UUID | None = None,
    note: str | None = None,
    actor_user_id: int | None = None,
    allow_negative: bool = False,
) -> dict[str, Any]:
    """寫一筆異動並累計餘額（呼叫端負責交易）

    順序固定：先 `stock_movements`，再 `stock_balances` 的 upsert。
    upsert 後的餘額為負且 `allow_negative=False` 時拋 `NegativeStockError`，
    由呼叫端的交易回滾（movement 也一起不見）。
    """
    movement = await conn.fetchrow(
        """
        INSERT INTO stock_movements
            (item_id, warehouse_id, qty_delta, reason, ref_type, ref_id, note,
             actor_user_id, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
        RETURNING *
        """,
        item_id,
        warehouse_id,
        qty_delta,
        reason,
        ref_type,
        ref_id,
        note,
        actor_user_id,
    )
    balance = await conn.fetchrow(
        """
        INSERT INTO stock_balances (item_id, warehouse_id, qty, created_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (item_id, warehouse_id)
        DO UPDATE SET qty = stock_balances.qty + EXCLUDED.qty, updated_at = NOW()
        RETURNING *
        """,
        item_id,
        warehouse_id,
        qty_delta,
        actor_user_id,
    )
    new_qty = Decimal(balance["qty"])
    if not allow_negative and new_qty < 0:
        raise NegativeStockError(
            item_id, warehouse_id, new_qty - Decimal(qty_delta), qty_delta
        )
    return {"movement": dict(movement), "balance": dict(balance)}


async def adjust_stock(
    item_id: UUID,
    warehouse_id: UUID,
    qty_delta,
    reason: str = "adjust",
    note: str | None = None,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
    allow_negative: bool = False,
) -> dict[str, Any]:
    """調整庫存（qty_delta 可正可負）"""
    if Decimal(qty_delta) == 0:
        raise InvalidOperationError("異動數量不可為 0")
    async with get_connection() as conn, conn.transaction():
        applied = await apply_movement(
            conn,
            item_id,
            warehouse_id,
            qty_delta,
            reason,
            note=note,
            actor_user_id=actor_user_id,
            allow_negative=allow_negative,
        )
        audit_id = await audit(
            conn,
            "stock",
            item_id,
            "adjust",
            {
                "warehouse_id": str(warehouse_id),
                "qty_delta": str(qty_delta),
                "reason": reason,
                "qty_after": str(applied["balance"]["qty"]),
            },
            actor_user_id,
            via,
            agent_name,
        )
    return {
        "audit_id": audit_id,
        "movements": [applied["movement"]],
        "balances": [applied["balance"]],
    }


async def transfer_stock(
    item_id: UUID,
    from_warehouse_id: UUID,
    to_warehouse_id: UUID,
    qty,
    note: str | None = None,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """倉別調撥：同一交易寫 transfer_out 與 transfer_in 兩筆異動"""
    if Decimal(qty) <= 0:
        raise InvalidOperationError("調撥數量必須大於 0")
    if from_warehouse_id == to_warehouse_id:
        raise InvalidOperationError("來源倉與目的倉不能相同")

    async with get_connection() as conn, conn.transaction():
        out = await apply_movement(
            conn,
            item_id,
            from_warehouse_id,
            -Decimal(qty),
            "transfer_out",
            note=note,
            actor_user_id=actor_user_id,
        )
        into = await apply_movement(
            conn,
            item_id,
            to_warehouse_id,
            Decimal(qty),
            "transfer_in",
            note=note,
            actor_user_id=actor_user_id,
        )
        audit_id = await audit(
            conn,
            "stock",
            item_id,
            "transfer",
            {
                "from_warehouse_id": str(from_warehouse_id),
                "to_warehouse_id": str(to_warehouse_id),
                "qty": str(qty),
            },
            actor_user_id,
            via,
            agent_name,
        )
    return {
        "audit_id": audit_id,
        "movements": [out["movement"], into["movement"]],
        "balances": [out["balance"], into["balance"]],
    }


# ============================================================
# 摘要
# ============================================================


async def summarize_item(item_id: UUID) -> dict[str, Any] | None:
    """把物料的關聯資料組成一段給 agent 的上下文"""
    detail = await get_item_detail(item_id, movement_limit=5)
    if detail is None:
        return None

    lines = [f"【{detail['code']}】{detail['name']}"]
    if detail.get("spec"):
        lines.append(f"規格：{detail['spec']}")
    unit = detail.get("unit") or ""
    lines.append(f"總庫存：{detail['total_qty']}{unit}")
    if detail["balances"]:
        lines.append(
            "各倉："
            + "、".join(
                f"{b['warehouse_name']} {b['qty']}{unit}" for b in detail["balances"]
            )
        )
    if detail.get("default_supplier_name"):
        lines.append(f"預設供應商：{detail['default_supplier_name']}")
    if detail.get("purchase_price") is not None:
        lines.append(f"採購價：{detail['purchase_price']}")
    if detail["movements"]:
        lines.append(
            "最近異動："
            + "、".join(
                f"{m['reason']} {m['qty_delta']}{unit}" for m in detail["movements"]
            )
        )
    else:
        lines.append("最近異動：無")

    return {
        "item_id": detail["id"],
        "code": detail["code"],
        "name": detail["name"],
        "summary": "\n".join(lines),
        "total_qty": detail["total_qty"],
        "warehouse_count": len(detail["balances"]),
    }
