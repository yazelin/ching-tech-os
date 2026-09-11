"""往來與物料模組：共用層（稽核、模糊解析、例外）

資料表見 migration 030。這一層放三塊給 parties／inventory／purchasing 共用的東西：

1. **稽核**：`audit()` 吃呼叫端的 conn，跟寫入在同一個交易裡，寫失敗就一起回滾。
2. **模糊解析**：`resolve_party()`／`resolve_item()` 讓工具的輸入容忍自然語言
   （規格第一節原則 2）。精確命中（統編、電話、料號、完全同名、別名）優先，
   其餘走 pg_trgm similarity 與 ILIKE 子字串。唯一命中才回，多個候選拋
   `AmbiguousError`，零命中拋 `NotFoundError`——呼叫端不准自己猜。
3. **軟刪除**：`deleted_at` 非空的主檔不進清單也不進解析。

子模組：`erp_parties.py`（往來對象）、`erp_inventory.py`（物料與庫存）、
`erp_purchasing.py`（採購）。
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..database import get_connection

logger = logging.getLogger(__name__)

# pg_trgm similarity 的門檻；低於這個值不算候選
SIMILARITY_THRESHOLD = 0.3

# 回給 agent 的候選上限（規格第二節：回前三個候選讓 agent 挑或問人）
CANDIDATE_LIMIT = 3


# ============================================================
# 例外
# ============================================================


class ErpError(Exception):
    """往來與物料模組的基底例外"""


class NotFoundError(ErpError):
    """解析不到任何候選"""

    def __init__(self, entity: str, query: str) -> None:
        self.entity = entity
        self.query = query
        super().__init__(f"找不到{entity}：{query}")


class AmbiguousError(ErpError):
    """解析到多個候選，要人或 agent 挑一個"""

    def __init__(self, entity: str, query: str, candidates: list[dict[str, Any]]) -> None:
        self.entity = entity
        self.query = query
        self.candidates = candidates
        super().__init__(f"{entity}「{query}」有 {len(candidates)} 個候選，請確認")


class NegativeStockError(ErpError):
    """異動後餘額會變成負數"""

    def __init__(
        self,
        item_id: UUID,
        warehouse_id: UUID,
        current: Decimal,
        delta: Decimal,
    ) -> None:
        self.item_id = item_id
        self.warehouse_id = warehouse_id
        self.current = current
        self.delta = delta
        super().__init__(
            f"庫存不足：目前 {current}，要異動 {delta}（不允許負庫存）"
        )


class InvalidOperationError(ErpError):
    """狀態不允許的操作（取消已收貨的採購單、收貨數超過未收量等）"""


# ============================================================
# 共用小工具
# ============================================================


def like_pattern(q: str) -> str:
    """把使用者輸入包成 ILIKE 樣式，並跳脫 %、_ 與跳脫字元本身

    沒跳脫的話 q="50%" 會變成「任何東西」，q="a_b" 的底線會對到任一字元。
    """
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def pick_fields(data: dict, fields: tuple[str, ...]) -> dict[str, Any]:
    """只留白名單內的欄位（擋掉呼叫端亂送的 key，也擋掉 SQL 注入用的欄位名）"""
    return {k: v for k, v in data.items() if k in fields}


def update_assignments(fields: dict, start: int = 2) -> tuple[str, list[Any]]:
    """把 {欄位: 值} 組成 UPDATE 的 SET 片段與對應的參數串

    欄位名一律來自 `pick_fields` 的白名單，不會是使用者輸入。
    `start` 是第一個值的參數編號（$1 通常留給主鍵）。
    """
    names = list(fields.keys())
    clause = ", ".join(f"{name} = ${i + start}" for i, name in enumerate(names))
    return clause, [fields[name] for name in names]


def build_diff(before: dict | None, after: dict | None) -> dict[str, Any]:
    """稽核用的差異：只記真的變了的欄位（before/after 成對）"""
    diff: dict[str, Any] = {}
    before = before or {}
    after = after or {}
    for key in set(before) | set(after):
        old = before.get(key)
        new = after.get(key)
        if old != new:
            diff[key] = {"before": _jsonable(old), "after": _jsonable(new)}
    return diff


def _jsonable(value: Any) -> Any:
    """把 asyncpg 回來的值轉成可以塞進 jsonb 的型別"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


# ============================================================
# 稽核
# ============================================================


async def audit(
    conn,
    entity_type: str,
    entity_id: UUID | None,
    action: str,
    diff: dict | None = None,
    actor_user_id: int | None = None,
    via: str = "mcp",
    agent_name: str | None = None,
) -> UUID:
    """寫一筆稽核；conn 由呼叫端給，確保與寫入同一個交易

    Returns:
        erp_audit.id，工具與 REST 都會把它回給呼叫者（規格第三節）
    """
    return await conn.fetchval(
        """
        INSERT INTO erp_audit
            (entity_type, entity_id, action, diff, actor_user_id, via,
             agent_name, created_by)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $5)
        RETURNING id
        """,
        entity_type,
        entity_id,
        action,
        json.dumps(_jsonable(diff or {}), ensure_ascii=False),
        actor_user_id,
        via,
        agent_name,
    )


async def list_audit(
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """查稽核紀錄（明細頁與 agent 回報用）"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, entity_type, entity_id, action, diff, actor_user_id,
                   via, agent_name, created_at
            FROM erp_audit
            WHERE ($1::text IS NULL OR entity_type = $1)
              AND ($2::uuid IS NULL OR entity_id = $2)
            ORDER BY created_at DESC
            LIMIT $3
            """,
            entity_type,
            entity_id,
            limit,
        )
    return [_audit_row(r) for r in rows]


def _audit_row(row) -> dict[str, Any]:
    """asyncpg 的 jsonb 回來是字串，轉成 dict"""
    data = dict(row)
    raw = data.get("diff")
    if isinstance(raw, str):
        try:
            data["diff"] = json.loads(raw)
        except ValueError:
            data["diff"] = None
    return data


# ============================================================
# 模糊解析：往來對象
# ============================================================

# 候選查詢：精確命中（統編／電話／同名／別名）優先，其次 trgm 相似度與子字串
_PARTY_CANDIDATE_SQL = """
    WITH scored AS (
        SELECT
            p.id, p.name, p.short_name, p.is_supplier, p.is_customer, p.tax_id,
            (
                SELECT c.name FROM party_contacts c
                WHERE c.party_id = p.id
                ORDER BY c.is_primary DESC, c.created_at
                LIMIT 1
            ) AS primary_contact,
            (
                SELECT COALESCE(c.phone, c.mobile) FROM party_contacts c
                WHERE c.party_id = p.id
                ORDER BY c.is_primary DESC, c.created_at
                LIMIT 1
            ) AS primary_phone,
            GREATEST(
                similarity(p.name, $1),
                similarity(COALESCE(p.short_name, ''), $1),
                COALESCE(
                    (SELECT MAX(similarity(a, $1)) FROM unnest(p.aliases) AS a), 0
                ),
                COALESCE(
                    (SELECT MAX(similarity(c.name, $1)) FROM party_contacts c
                     WHERE c.party_id = p.id), 0
                )
            ) AS score,
            (
                (p.tax_id IS NOT NULL AND p.tax_id = $1)
                OR lower(p.name) = lower($1)
                OR lower(COALESCE(p.short_name, '')) = lower($1)
                OR EXISTS (
                    SELECT 1 FROM unnest(p.aliases) AS a WHERE lower(a) = lower($1)
                )
                OR EXISTS (
                    SELECT 1 FROM party_contacts c
                    WHERE c.party_id = p.id AND $1 IN (c.phone, c.mobile)
                )
            ) AS exact_hit,
            (
                p.name ILIKE $2 ESCAPE '\\'
                OR COALESCE(p.short_name, '') ILIKE $2 ESCAPE '\\'
                OR EXISTS (
                    SELECT 1 FROM unnest(p.aliases) AS a WHERE a ILIKE $2 ESCAPE '\\'
                )
            ) AS contains_hit
        FROM parties p
        WHERE p.deleted_at IS NULL
          AND (
            $3::text IS NULL
            OR ($3 = 'supplier' AND p.is_supplier)
            OR ($3 = 'customer' AND p.is_customer)
          )
    )
    SELECT id, name, short_name, is_supplier, is_customer, tax_id,
           primary_contact, primary_phone, score, exact_hit
    FROM scored
    WHERE exact_hit OR contains_hit OR score >= $4
    ORDER BY exact_hit DESC, contains_hit DESC, score DESC, name
    LIMIT $5
"""


async def find_parties(
    query: str,
    role: str | None = None,
    limit: int = CANDIDATE_LIMIT,
    conn=None,
) -> list[dict[str, Any]]:
    """模糊找往來對象，回候選清單（已排序，最像的在前）"""
    if not (query or "").strip():
        return []

    async def _run(c) -> list[dict[str, Any]]:
        rows = await c.fetch(
            _PARTY_CANDIDATE_SQL,
            query.strip(),
            like_pattern(query.strip()),
            role,
            SIMILARITY_THRESHOLD,
            limit,
        )
        return [dict(r) for r in rows]

    if conn is not None:
        return await _run(conn)
    async with get_connection() as c:
        return await _run(c)


async def resolve_party(
    query: str, role: str | None = None, conn=None
) -> dict[str, Any]:
    """把名稱／別名／電話／統編解析成唯一一筆往來對象

    Raises:
        NotFoundError: 零候選
        AmbiguousError: 多個候選（呼叫端要回去問人，不准自己挑）
    """
    candidates = await find_parties(query, role=role, conn=conn)
    return _pick_single("往來對象", query, candidates)


# ============================================================
# 模糊解析：物料
# ============================================================

_ITEM_CANDIDATE_SQL = """
    WITH scored AS (
        SELECT
            i.id, i.code, i.name, i.spec, i.unit, i.item_group,
            GREATEST(
                similarity(i.name, $1),
                similarity(i.code, $1),
                COALESCE(
                    (SELECT MAX(similarity(a, $1)) FROM unnest(i.aliases) AS a), 0
                ),
                similarity(COALESCE(i.spec, ''), $1)
            ) AS score,
            (
                lower(i.code) = lower($1)
                OR lower(i.name) = lower($1)
                OR EXISTS (
                    SELECT 1 FROM unnest(i.aliases) AS a WHERE lower(a) = lower($1)
                )
            ) AS exact_hit,
            (
                i.code ILIKE $2 ESCAPE '\\'
                OR i.name ILIKE $2 ESCAPE '\\'
                OR COALESCE(i.spec, '') ILIKE $2 ESCAPE '\\'
                OR EXISTS (
                    SELECT 1 FROM unnest(i.aliases) AS a WHERE a ILIKE $2 ESCAPE '\\'
                )
            ) AS contains_hit
        FROM items i
        WHERE i.deleted_at IS NULL
    )
    SELECT id, code, name, spec, unit, item_group, score, exact_hit
    FROM scored
    WHERE exact_hit OR contains_hit OR score >= $3
    ORDER BY exact_hit DESC, contains_hit DESC, score DESC, code
    LIMIT $4
"""


async def find_items(
    query: str, limit: int = CANDIDATE_LIMIT, conn=None
) -> list[dict[str, Any]]:
    """模糊找物料（料號、品名、別名、規格），回候選清單"""
    if not (query or "").strip():
        return []

    async def _run(c) -> list[dict[str, Any]]:
        rows = await c.fetch(
            _ITEM_CANDIDATE_SQL,
            query.strip(),
            like_pattern(query.strip()),
            SIMILARITY_THRESHOLD,
            limit,
        )
        return [dict(r) for r in rows]

    if conn is not None:
        return await _run(conn)
    async with get_connection() as c:
        return await _run(c)


async def resolve_item(query: str, conn=None) -> dict[str, Any]:
    """把料號／品名／別名解析成唯一一筆物料

    Raises:
        NotFoundError / AmbiguousError（語意同 resolve_party）
    """
    candidates = await find_items(query, conn=conn)
    return _pick_single("物料", query, candidates)


async def resolve_warehouse(query: str, conn=None) -> dict[str, Any]:
    """倉庫用代碼或名稱解析（倉庫只有五個，不做 trgm）"""
    if not (query or "").strip():
        raise NotFoundError("倉庫", query or "")

    async def _run(c) -> list[dict[str, Any]]:
        rows = await c.fetch(
            r"""
            SELECT id, code, name,
                   (lower(code) = lower($1) OR lower(name) = lower($1)) AS exact_hit
            FROM warehouses
            WHERE deleted_at IS NULL
              AND (
                lower(code) = lower($1)
                OR lower(name) = lower($1)
                OR code ILIKE $2 ESCAPE '\'
                OR name ILIKE $2 ESCAPE '\'
              )
            ORDER BY exact_hit DESC, code
            LIMIT $3
            """,
            query.strip(),
            like_pattern(query.strip()),
            CANDIDATE_LIMIT,
        )
        return [dict(r) for r in rows]

    if conn is not None:
        candidates = await _run(conn)
    else:
        async with get_connection() as c:
            candidates = await _run(c)
    return _pick_single("倉庫", query, candidates)


def _pick_single(
    entity: str, query: str, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """唯一命中才回；精確命中只有一筆時也算唯一（同名不同家除外）"""
    if not candidates:
        raise NotFoundError(entity, query)
    if len(candidates) == 1:
        return candidates[0]
    exact = [c for c in candidates if c.get("exact_hit")]
    if len(exact) == 1:
        return exact[0]
    raise AmbiguousError(entity, query, candidates)
