"""採購服務（purchase_orders / purchase_order_lines）

單號 `PO-YYYYMM-NNN` 在同一交易內產生：先 `pg_advisory_xact_lock` 鎖住當月序號，
再查當月最大值 +1，所以兩個 agent 同時開單不會撞號（撞了也還有 unique 擋著）。
收貨走 `erp_inventory.apply_movement`（reason=receipt，ref 指回採購單），
同一交易更新 `received_qty` 與單頭狀態。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..database import get_connection
from .erp import (
    AmbiguousError,
    InvalidOperationError,
    audit,
    build_diff,
    pick_fields,
    update_assignments,
)
from .erp_inventory import apply_movement

logger = logging.getLogger(__name__)

# 可更新的單頭欄位（行項不在這裡改）
_PO_UPDATE_FIELDS = (
    "supplier_id",
    "project_id",
    "status",
    "order_date",
    "expected_date",
    "notes",
)

# 已結案的單不給改狀態以外的東西
_CLOSED_STATUSES = ("received", "cancelled")


async def next_po_no(conn, on_date: date | None = None) -> str:
    """產生當月單號 PO-YYYYMM-NNN（呼叫端要在交易裡）"""
    day = on_date or date.today()
    prefix = f"PO-{day:%Y%m}-"
    # 同月同一把鎖；交易結束自動釋放
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", prefix)
    max_seq = await conn.fetchval(
        """
        SELECT COALESCE(MAX(NULLIF(substring(po_no from 11), '')::int), 0)
        FROM purchase_orders
        WHERE po_no LIKE $1 || '%'
        """,
        prefix,
    )
    return f"{prefix}{int(max_seq or 0) + 1:03d}"


# ============================================================
# 清單與明細
# ============================================================


async def list_purchase_orders(
    supplier_id: UUID | None = None,
    status: str | None = None,
    project_id: UUID | None = None,
    since: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """採購單清單（可依供應商、狀態、專案、起始日期篩選）"""
    offset = (max(page, 1) - 1) * page_size
    where = """
        WHERE ($1::uuid IS NULL OR po.supplier_id = $1)
          AND ($2::text IS NULL OR po.status = $2)
          AND ($3::uuid IS NULL OR po.project_id = $3)
          AND ($4::date IS NULL OR COALESCE(po.order_date, po.created_at::date) >= $4)
    """
    async with get_connection() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM purchase_orders po {where}",
            supplier_id,
            status,
            project_id,
            since,
        )
        rows = await conn.fetch(
            f"""
            SELECT po.id, po.po_no, po.supplier_id, s.name AS supplier_name,
                   po.project_id, pr.name AS project_name, po.status,
                   po.order_date, po.expected_date, po.created_at, po.updated_at,
                   COALESCE((
                       SELECT count(*) FROM purchase_order_lines l
                       WHERE l.po_id = po.id
                   ), 0)::int AS line_count,
                   COALESCE((
                       SELECT SUM(l.qty * COALESCE(l.unit_price, 0))
                       FROM purchase_order_lines l WHERE l.po_id = po.id
                   ), 0) AS total_amount
            FROM purchase_orders po
            LEFT JOIN parties s ON s.id = po.supplier_id
            LEFT JOIN projects pr ON pr.id = po.project_id
            {where}
            ORDER BY po.created_at DESC
            LIMIT $5 OFFSET $6
            """,
            supplier_id,
            status,
            project_id,
            since,
            page_size,
            offset,
        )
    return {"items": [dict(r) for r in rows], "total": int(total or 0)}


async def get_purchase_order(
    po_id: UUID | None = None, po_no: str | None = None
) -> dict[str, Any] | None:
    """採購單明細（用 id 或單號查）

    Raises:
        ValueError: `po_id` 與 `po_no` 都沒給（不然 SQL 會把整張表的第一筆撈回來）
    """
    if po_id is None and po_no is None:
        raise ValueError("get_purchase_order 需要 po_id 或 po_no")
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT po.id, po.po_no, po.supplier_id, s.name AS supplier_name,
                   po.project_id, pr.name AS project_name, po.status,
                   po.order_date, po.expected_date, po.notes, po.created_by,
                   po.created_at, po.updated_at
            FROM purchase_orders po
            LEFT JOIN parties s ON s.id = po.supplier_id
            LEFT JOIN projects pr ON pr.id = po.project_id
            WHERE ($1::uuid IS NULL OR po.id = $1)
              AND ($2::text IS NULL OR po.po_no = $2)
            """,
            po_id,
            po_no,
        )
        if row is None:
            return None
        lines = await conn.fetch(
            """
            SELECT l.id, l.po_id, l.item_id, i.code AS item_code,
                   i.name AS item_name, l.description, l.qty, l.unit_price,
                   l.received_qty, l.sort_order
            FROM purchase_order_lines l
            LEFT JOIN items i ON i.id = l.item_id
            WHERE l.po_id = $1
            ORDER BY l.sort_order, l.id
            """,
            row["id"],
        )

    detail = dict(row)
    detail["lines"] = [dict(r) for r in lines]
    detail["total_amount"] = sum(
        (Decimal(line["qty"]) * Decimal(line["unit_price"] or 0) for line in lines),
        Decimal(0),
    )
    return detail


# ============================================================
# 建立／更新
# ============================================================


async def create_purchase_order(
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any]:
    """建立採購單（單號同交易產生），回傳明細＋audit_id

    `data["po_no"]` 有給就沿用（ERPNext 匯入要保留原單號），沒給才自動產生。
    行項的 `received_qty` 同理：匯入歷史單據時直接把已收量帶進來，不另外產生
    庫存異動（那些庫存已經在 Bin 的初始餘額裡了）。

    Raises:
        InvalidOperationError: 沒有行項、供應商不存在、行項的物料不存在、
            指定的單號已存在、已收量超過訂購量
    """
    lines = data.get("lines") or []
    if not lines:
        raise InvalidOperationError("採購單至少要一個行項")

    async with get_connection() as conn, conn.transaction():
        supplier = await conn.fetchrow(
            "SELECT id, name FROM parties WHERE id = $1 AND deleted_at IS NULL",
            data["supplier_id"],
        )
        if supplier is None:
            raise InvalidOperationError("供應商不存在或已刪除")
        if data.get("project_id") is not None:
            project = await conn.fetchval(
                "SELECT 1 FROM projects WHERE id = $1", data["project_id"]
            )
            if not project:
                raise InvalidOperationError("專案不存在")

        order_date = data.get("order_date") or date.today()
        po_no = (data.get("po_no") or "").strip() or None
        if po_no is None:
            po_no = await next_po_no(conn, order_date)
        elif await conn.fetchval(
            "SELECT 1 FROM purchase_orders WHERE po_no = $1", po_no
        ):
            raise InvalidOperationError(f"採購單號已存在：{po_no}")
        row = await conn.fetchrow(
            """
            INSERT INTO purchase_orders
                (po_no, supplier_id, project_id, status, order_date,
                 expected_date, notes, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            po_no,
            data["supplier_id"],
            data.get("project_id"),
            data.get("status") or "ordered",
            order_date,
            data.get("expected_date"),
            data.get("notes"),
            actor_user_id,
        )

        for index, line in enumerate(lines):
            item = await conn.fetchrow(
                "SELECT id, code FROM items WHERE id = $1 AND deleted_at IS NULL",
                line["item_id"],
            )
            if item is None:
                raise InvalidOperationError(f"物料不存在或已刪除：{line['item_id']}")
            qty = Decimal(str(line["qty"]))
            if qty <= 0:
                raise InvalidOperationError("行項數量必須大於 0")
            received_qty = Decimal(str(line.get("received_qty") or 0))
            if received_qty < 0 or received_qty > qty:
                raise InvalidOperationError(
                    f"已收量 {received_qty} 不能小於 0 或超過訂購量 {qty}"
                )
            await conn.execute(
                """
                INSERT INTO purchase_order_lines
                    (po_id, item_id, description, qty, unit_price, received_qty,
                     sort_order, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                row["id"],
                line["item_id"],
                line.get("description"),
                line["qty"],
                line.get("unit_price"),
                received_qty,
                index,
                actor_user_id,
            )

        audit_id = await audit(
            conn,
            "purchase_order",
            row["id"],
            "create",
            {
                "po_no": po_no,
                "supplier": supplier["name"],
                "line_count": len(lines),
            },
            actor_user_id,
            via,
            agent_name,
        )

    result = dict(row)
    result["audit_id"] = audit_id
    return result


async def update_purchase_order(
    po_id: UUID,
    data: dict,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """更新單頭；找不到回 None，已收貨／已取消的單不給改"""
    fields = pick_fields(data, _PO_UPDATE_FIELDS)
    async with get_connection() as conn, conn.transaction():
        before = await conn.fetchrow(
            "SELECT * FROM purchase_orders WHERE id = $1", po_id
        )
        if before is None:
            return None
        if before["status"] in _CLOSED_STATUSES:
            raise InvalidOperationError(
                f"採購單狀態為 {before['status']}，不能修改"
            )
        if fields:
            assignments, values = update_assignments(fields)
            row = await conn.fetchrow(
                f"""
                UPDATE purchase_orders
                SET {assignments}, updated_at = NOW()
                WHERE id = $1
                RETURNING *
                """,
                po_id,
                *values,
            )
        else:
            row = before
        audit_id = await audit(
            conn,
            "purchase_order",
            po_id,
            "update",
            build_diff(
                pick_fields(dict(before), _PO_UPDATE_FIELDS),
                pick_fields(dict(row), _PO_UPDATE_FIELDS),
            ),
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


# ============================================================
# 收貨
# ============================================================


async def receive_purchase_order(
    po_id: UUID,
    lines: list[dict] | None = None,
    receive_all: bool = False,
    warehouse_id: UUID | None = None,
    note: str | None = None,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """收貨入庫：更新 received_qty、產生 receipt 異動、更新單頭狀態

    Args:
        lines: `[{"line_id": ..., "qty": ...}]`（只給 `item_id` 也可以，
            但該物料在單上有兩行以上時會拋 `AmbiguousError`）；
            `receive_all=True` 時忽略，收下所有行項的未收數量。
        warehouse_id: 入庫倉；沒給且系統只有一個倉時自動採用該倉。

    Returns:
        `{"audit_id", "status", "movements"}`；採購單不存在回 None
    """
    async with get_connection() as conn, conn.transaction():
        po = await conn.fetchrow("SELECT * FROM purchase_orders WHERE id = $1", po_id)
        if po is None:
            return None
        if po["status"] in _CLOSED_STATUSES:
            raise InvalidOperationError(
                f"採購單狀態為 {po['status']}，不能收貨"
            )

        po_lines = await conn.fetch(
            """
            SELECT l.id, l.item_id, l.qty, l.received_qty, i.code AS item_code
            FROM purchase_order_lines l
            LEFT JOIN items i ON i.id = l.item_id
            WHERE l.po_id = $1
            ORDER BY l.sort_order, l.id
            """,
            po_id,
        )
        if not po_lines:
            raise InvalidOperationError("採購單沒有行項")

        target = _receive_plan(po_lines, lines, receive_all)
        if not target:
            raise InvalidOperationError("沒有可收貨的行項")

        warehouse_id = await _resolve_receive_warehouse(conn, warehouse_id)

        movements = []
        for line_id, item_id, qty in target:
            await conn.execute(
                """
                UPDATE purchase_order_lines
                SET received_qty = received_qty + $2, updated_at = NOW()
                WHERE id = $1
                """,
                line_id,
                qty,
            )
            applied = await apply_movement(
                conn,
                item_id,
                warehouse_id,
                qty,
                "receipt",
                ref_type="purchase_order",
                ref_id=po_id,
                note=note,
                actor_user_id=actor_user_id,
            )
            movements.append(applied["movement"])

        status = await _refresh_po_status(conn, po_id)
        audit_id = await audit(
            conn,
            "purchase_order",
            po_id,
            "receive",
            {
                "po_no": po["po_no"],
                "warehouse_id": str(warehouse_id),
                "status": status,
                "lines": [
                    {
                        "line_id": str(line_id),
                        "item_id": str(item_id),
                        "qty": str(qty),
                    }
                    for line_id, item_id, qty in target
                ],
            },
            actor_user_id,
            via,
            agent_name,
        )

    return {"audit_id": audit_id, "status": status, "movements": movements}


def _line_candidates(po_lines) -> list[dict[str, Any]]:
    """把行項整理成回給 agent 的候選（同一物料多行時要人挑哪一行）"""
    return [
        {
            "line_id": str(row["id"]),
            "item_id": str(row["item_id"]),
            "item_code": row["item_code"],
            "qty": str(row["qty"]),
            "received_qty": str(row["received_qty"]),
        }
        for row in po_lines
    ]


def _receive_plan(
    po_lines, requested: list[dict] | None, receive_all: bool
) -> list[tuple[UUID, UUID, Decimal]]:
    """算出這次每一行要收多少；超收、未知行項、同物料多行都擋下來

    行項以 `line_id` 為 key（同一張單可以有兩行同物料）。呼叫端也可以只給
    `item_id`：該物料只出現在一行時視為指定那一行，出現多行就拋
    `AmbiguousError(candidates=行清單)`，要人或 agent 指定 `line_id`。

    同一行在同一個請求裡出現多次是允許的，剩餘量會逐筆遞減，合計超過未收量才擋。

    Raises:
        InvalidOperationError: 數量 ≤ 0、超收（含同一行多筆合計超收）、行項不屬於這張單
        AmbiguousError: 只給 item_id 但該物料有多行
    """
    by_line = {
        row["id"]: (row["item_id"], Decimal(row["qty"]) - Decimal(row["received_qty"]))
        for row in po_lines
    }
    if receive_all:
        return [
            (line_id, item_id, remain)
            for line_id, (item_id, remain) in by_line.items()
            if remain > 0
        ]

    plan: list[tuple[UUID, UUID, Decimal]] = []
    for entry in requested or []:
        line_id = _pick_line_id(po_lines, entry)
        item_id, remain = by_line[line_id]
        qty = Decimal(entry["qty"])
        if qty <= 0:
            raise InvalidOperationError("收貨數量必須大於 0")
        if qty > remain:
            raise InvalidOperationError(
                f"收貨數量超過未收量（未收 {remain}，要收 {qty}）"
            )
        # 同一行在同一個請求裡出現兩次時，剩餘量要跟著遞減；
        # 不然 {qty:3} 兩筆對剩 4 的行會各自過檢查、合起來收 6
        by_line[line_id] = (item_id, remain - qty)
        plan.append((line_id, item_id, qty))
    return plan


def _pick_line_id(po_lines, entry: dict) -> UUID:
    """從收貨請求的一筆找出對應的行項 id"""
    line_id = entry.get("line_id")
    if line_id is not None:
        if not any(row["id"] == line_id for row in po_lines):
            raise InvalidOperationError(f"採購單沒有這個行項：{line_id}")
        return line_id

    item_id = entry.get("item_id")
    if item_id is None:
        raise InvalidOperationError("收貨行項要給 line_id 或 item_id")
    matched = [row for row in po_lines if row["item_id"] == item_id]
    if not matched:
        raise InvalidOperationError(f"採購單沒有這個物料的行項：{item_id}")
    if len(matched) > 1:
        raise AmbiguousError(
            "採購單行項", str(item_id), _line_candidates(matched)
        )
    return matched[0]["id"]


async def _resolve_receive_warehouse(conn, warehouse_id: UUID | None) -> UUID:
    """沒指定入庫倉時：只有一個倉就用它，多個倉要呼叫端講清楚"""
    if warehouse_id is not None:
        found = await conn.fetchval(
            "SELECT 1 FROM warehouses WHERE id = $1 AND deleted_at IS NULL",
            warehouse_id,
        )
        if not found:
            raise InvalidOperationError("倉庫不存在或已刪除")
        return warehouse_id

    rows = await conn.fetch(
        "SELECT id FROM warehouses WHERE deleted_at IS NULL LIMIT 2"
    )
    if len(rows) == 1:
        return rows[0]["id"]
    raise InvalidOperationError("請指定入庫倉別")


async def _refresh_po_status(conn, po_id: UUID) -> str:
    """全收改 received、部分收改 partial，其餘維持原狀態"""
    stats = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(qty), 0) AS total_qty,
            COALESCE(SUM(received_qty), 0) AS received_qty
        FROM purchase_order_lines
        WHERE po_id = $1
        """,
        po_id,
    )
    total = Decimal(stats["total_qty"])
    received = Decimal(stats["received_qty"])
    if received >= total:
        status = "received"
    elif received > 0:
        status = "partial"
    else:
        status = "ordered"
    await conn.execute(
        "UPDATE purchase_orders SET status = $2, updated_at = NOW() WHERE id = $1",
        po_id,
        status,
    )
    return status


# ============================================================
# 取消
# ============================================================


async def cancel_purchase_order(
    po_id: UUID,
    reason: str | None = None,
    actor_user_id: int | None = None,
    via: str = "rest",
    agent_name: str | None = None,
) -> dict[str, Any] | None:
    """取消採購單（不是刪除）；已收過貨的不給取消"""
    async with get_connection() as conn, conn.transaction():
        po = await conn.fetchrow("SELECT * FROM purchase_orders WHERE id = $1", po_id)
        if po is None:
            return None
        if po["status"] == "cancelled":
            raise InvalidOperationError("採購單已經取消")
        received = await conn.fetchval(
            """
            SELECT COALESCE(SUM(received_qty), 0)
            FROM purchase_order_lines WHERE po_id = $1
            """,
            po_id,
        )
        if received and Decimal(received) > 0:
            raise InvalidOperationError("已收過貨的採購單不能取消，請先做庫存調整")

        row = await conn.fetchrow(
            """
            UPDATE purchase_orders
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            po_id,
        )
        audit_id = await audit(
            conn,
            "purchase_order",
            po_id,
            "cancel",
            {"po_no": po["po_no"], "reason": reason},
            actor_user_id,
            via,
            agent_name,
        )
    result = dict(row)
    result["audit_id"] = audit_id
    return result


# ============================================================
# 文件擷取草稿（工具本身不呼叫模型）
# ============================================================


async def match_duplicate_parties(name: str, tax_id: str | None = None) -> list[dict]:
    """名片／報價單擷取出來的公司，回可能重複的既有主檔"""
    from .erp import find_parties

    candidates = await find_parties(name) if name else []
    if tax_id:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, short_name, is_supplier, is_customer, tax_id
                FROM parties
                WHERE deleted_at IS NULL AND tax_id = $1
                """,
                tax_id,
            )
        known = {c["id"] for c in candidates}
        for row in rows:
            if row["id"] not in known:
                candidates.insert(0, {**dict(row), "score": 1.0, "exact_hit": True})
    return candidates


def normalize_extracted_date(value: Any) -> date | None:
    """擷取結果的日期字串轉 date；轉不動回 None（草稿不因為日期壞掉整個失敗）"""
    if value is None or isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    text = str(value).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
