"""往來與物料模組 Service 層測試。

DB 一律用假的 connection（記下每一句 SQL 與參數），驗 SQL 內容、呼叫序與交易。
不碰真資料庫。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ching_tech_os.services import erp as erp_core
from ching_tech_os.services import erp_inventory as inventory_service
from ching_tech_os.services import erp_parties as party_service
from ching_tech_os.services import erp_purchasing as purchasing_service


class _DictRecord(dict):
    """模擬 asyncpg Record（同時支援 dict() 與 key 存取）"""


class _Tx:
    """模擬 conn.transaction() 的 async context manager"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _FakeConn:
    """記錄每一次呼叫的假 connection

    fetchrow／fetchval／fetch 各自吃一個佇列，用完之後回 None／空清單。
    """

    def __init__(self, fetchrow=None, fetchval=None, fetch=None) -> None:
        self._fetchrow = list(fetchrow or [])
        self._fetchval = list(fetchval or [])
        self._fetch = list(fetch or [])
        self.calls: list[tuple[str, str, tuple]] = []

    def transaction(self):
        self.in_transaction = True
        return _Tx()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self._fetchrow.pop(0) if self._fetchrow else None

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return self._fetchval.pop(0) if self._fetchval else None

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self._fetch.pop(0) if self._fetch else []

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "UPDATE 1"

    # ── 斷言用的小工具 ────────────────────────────────────────
    def sqls(self) -> list[str]:
        return [sql for _method, sql, _args in self.calls]

    def find(self, fragment: str) -> list[tuple[str, str, tuple]]:
        return [c for c in self.calls if fragment in c[1]]

    def index_of(self, fragment: str) -> int:
        for i, (_m, sql, _a) in enumerate(self.calls):
            if fragment in sql:
                return i
        raise AssertionError(f"找不到 SQL 片段：{fragment}")


class _CM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _patch(monkeypatch: pytest.MonkeyPatch, module, conn) -> None:
    monkeypatch.setattr(module, "get_connection", lambda: _CM(conn))


NOW = datetime.now(timezone.utc)


def _party_row(**overrides) -> _DictRecord:
    base = {
        "id": uuid4(),
        "name": "鴻佰科技",
        "short_name": "鴻佰",
        "aliases": ["鴻佰工業"],
        "is_supplier": True,
        "is_customer": False,
        "tax_id": "12345678",
        "industry": None,
        "payment_terms": None,
        "notes": None,
        "source_ref": None,
        "created_by": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return _DictRecord(base)


def _item_row(**overrides) -> _DictRecord:
    base = {
        "id": uuid4(),
        "code": "CTOS-A1",
        "name": "不鏽鋼螺絲",
        "spec": None,
        "unit": "支",
        "item_group": None,
        "default_supplier_id": None,
        "purchase_price": Decimal("5"),
        "lead_days": None,
        "aliases": [],
        "notes": None,
        "source_ref": None,
        "created_by": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return _DictRecord(base)


# ============================================================
# 純函式
# ============================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("50%", r"%50\%%"),
        ("a_b", r"%a\_b%"),
        ("c\\d", r"%c\\d%"),
        ("鴻佰", "%鴻佰%"),
    ],
)
def test_like_pattern_escapes(raw, expected) -> None:
    assert erp_core.like_pattern(raw) == expected


def test_pick_fields_drops_unknown_keys() -> None:
    assert erp_core.pick_fields({"a": 1, "b": 2}, ("a",)) == {"a": 1}


def test_update_assignments_builds_numbered_clause() -> None:
    clause, values = erp_core.update_assignments({"name": "A", "notes": "B"})
    assert clause == "name = $2, notes = $3"
    assert values == ["A", "B"]


def test_build_diff_only_records_changes() -> None:
    diff = erp_core.build_diff(
        {"name": "A", "notes": None, "qty": Decimal("1")},
        {"name": "B", "notes": None, "qty": Decimal("1")},
    )
    assert diff == {"name": {"before": "A", "after": "B"}}


def test_build_diff_jsonable_for_uuid_and_decimal() -> None:
    pid = uuid4()
    diff = erp_core.build_diff(None, {"id": pid, "price": Decimal("1.5")})
    assert diff["id"]["after"] == str(pid)
    assert diff["price"]["after"] == "1.5"
    assert diff["id"]["before"] is None


def test_jsonable_handles_nested_containers() -> None:
    value = erp_core._jsonable({"a": [uuid4()], "b": {"c": Decimal("2")}})
    assert isinstance(value["a"][0], str)
    assert value["b"]["c"] == "2"


def test_negative_stock_error_message() -> None:
    err = erp_core.NegativeStockError(uuid4(), uuid4(), Decimal("3"), Decimal("-5"))
    assert "庫存不足" in str(err)
    assert err.current == Decimal("3")


# ============================================================
# 稽核
# ============================================================


@pytest.mark.asyncio
async def test_audit_writes_row_in_caller_transaction() -> None:
    audit_id = uuid4()
    conn = _FakeConn(fetchval=[audit_id])

    result = await erp_core.audit(
        conn, "party", None, "create", {"name": "A"}, 7, "mcp", "linebot"
    )

    assert result == audit_id
    method, sql, args = conn.calls[0]
    assert "INSERT INTO erp_audit" in sql
    assert args[0] == "party"
    assert args[2] == "create"
    assert '"name"' in args[3]  # diff 以 JSON 字串傳入
    assert args[4] == 7 and args[5] == "mcp" and args[6] == "linebot"


@pytest.mark.asyncio
async def test_list_audit_parses_jsonb_string(monkeypatch) -> None:
    conn = _FakeConn(
        fetch=[
            [
                _DictRecord(
                    {
                        "id": uuid4(),
                        "entity_type": "party",
                        "entity_id": uuid4(),
                        "action": "create",
                        "diff": '{"name": {"before": null, "after": "A"}}',
                        "actor_user_id": None,
                        "via": "mcp",
                        "agent_name": None,
                        "created_at": NOW,
                    }
                )
            ]
        ]
    )
    _patch(monkeypatch, erp_core, conn)

    rows = await erp_core.list_audit(entity_type="party")
    assert rows[0]["diff"]["name"]["after"] == "A"


@pytest.mark.asyncio
async def test_list_audit_tolerates_broken_json(monkeypatch) -> None:
    conn = _FakeConn(
        fetch=[[_DictRecord({"id": uuid4(), "diff": "not json"})]],
    )
    _patch(monkeypatch, erp_core, conn)

    rows = await erp_core.list_audit()
    assert rows[0]["diff"] is None


# ============================================================
# 模糊解析：三種結果
# ============================================================


@pytest.mark.asyncio
async def test_resolve_party_single_candidate(monkeypatch) -> None:
    row = _DictRecord({"id": uuid4(), "name": "鴻佰科技", "exact_hit": False})
    conn = _FakeConn(fetch=[[row]])
    _patch(monkeypatch, erp_core, conn)

    hit = await erp_core.resolve_party("鴻佰")
    assert hit["name"] == "鴻佰科技"
    # 軟刪除的不進解析
    assert "deleted_at IS NULL" in conn.calls[0][1]


@pytest.mark.asyncio
async def test_resolve_party_ambiguous(monkeypatch) -> None:
    rows = [
        _DictRecord({"id": uuid4(), "name": "鴻佰科技", "exact_hit": False}),
        _DictRecord({"id": uuid4(), "name": "鴻佰工業", "exact_hit": False}),
    ]
    conn = _FakeConn(fetch=[rows])
    _patch(monkeypatch, erp_core, conn)

    with pytest.raises(erp_core.AmbiguousError) as exc:
        await erp_core.resolve_party("鴻佰")
    assert len(exc.value.candidates) == 2
    assert exc.value.entity == "往來對象"


@pytest.mark.asyncio
async def test_resolve_party_exact_hit_wins_over_fuzzy(monkeypatch) -> None:
    """一筆精確命中（統編／電話／同名／別名）時不算模糊"""
    exact = _DictRecord({"id": uuid4(), "name": "鴻佰科技", "exact_hit": True})
    fuzzy = _DictRecord({"id": uuid4(), "name": "鴻佰工業", "exact_hit": False})
    conn = _FakeConn(fetch=[[exact, fuzzy]])
    _patch(monkeypatch, erp_core, conn)

    assert (await erp_core.resolve_party("鴻佰"))["name"] == "鴻佰科技"


@pytest.mark.asyncio
async def test_resolve_party_two_exact_hits_still_ambiguous(monkeypatch) -> None:
    rows = [
        _DictRecord({"id": uuid4(), "name": "同名公司", "exact_hit": True}),
        _DictRecord({"id": uuid4(), "name": "同名公司", "exact_hit": True}),
    ]
    conn = _FakeConn(fetch=[rows])
    _patch(monkeypatch, erp_core, conn)

    with pytest.raises(erp_core.AmbiguousError):
        await erp_core.resolve_party("同名公司")


@pytest.mark.asyncio
async def test_resolve_party_not_found(monkeypatch) -> None:
    conn = _FakeConn(fetch=[[]])
    _patch(monkeypatch, erp_core, conn)

    with pytest.raises(erp_core.NotFoundError):
        await erp_core.resolve_party("查無此公司")


@pytest.mark.asyncio
async def test_find_parties_empty_query_short_circuits(monkeypatch) -> None:
    conn = _FakeConn()
    _patch(monkeypatch, erp_core, conn)

    assert await erp_core.find_parties("   ") == []
    assert conn.calls == []


@pytest.mark.asyncio
async def test_find_parties_passes_role_threshold_and_limit(monkeypatch) -> None:
    conn = _FakeConn(fetch=[[]])
    _patch(monkeypatch, erp_core, conn)

    await erp_core.find_parties("鴻佰", role="supplier")
    _method, sql, args = conn.calls[0]
    assert "similarity" in sql
    assert args[0] == "鴻佰"
    assert args[2] == "supplier"
    assert args[3] == erp_core.SIMILARITY_THRESHOLD
    assert args[4] == erp_core.CANDIDATE_LIMIT


@pytest.mark.asyncio
async def test_find_parties_reuses_given_connection(monkeypatch) -> None:
    """呼叫端已經在交易裡時，解析要走同一條連線"""
    conn = _FakeConn(fetch=[[]])
    _patch(monkeypatch, erp_core, AsyncMock())

    await erp_core.find_parties("鴻佰", conn=conn)
    assert conn.calls  # 用的是傳進去的 conn


@pytest.mark.asyncio
async def test_resolve_item_by_alias(monkeypatch) -> None:
    conn = _FakeConn(
        fetch=[[_DictRecord({"id": uuid4(), "code": "CTOS-A1", "exact_hit": True})]]
    )
    _patch(monkeypatch, erp_core, conn)

    assert (await erp_core.resolve_item("白鐵螺絲"))["code"] == "CTOS-A1"


@pytest.mark.asyncio
async def test_find_items_empty_query(monkeypatch) -> None:
    conn = _FakeConn()
    _patch(monkeypatch, erp_core, conn)
    assert await erp_core.find_items("") == []


@pytest.mark.asyncio
async def test_find_items_uses_given_connection() -> None:
    conn = _FakeConn(fetch=[[]])
    assert await erp_core.find_items("螺絲", conn=conn) == []
    assert conn.calls


@pytest.mark.asyncio
async def test_resolve_warehouse(monkeypatch) -> None:
    conn = _FakeConn(
        fetch=[[_DictRecord({"id": uuid4(), "code": "MAIN", "exact_hit": True})]]
    )
    _patch(monkeypatch, erp_core, conn)

    assert (await erp_core.resolve_warehouse("主倉"))["code"] == "MAIN"


@pytest.mark.asyncio
async def test_resolve_warehouse_blank_query() -> None:
    with pytest.raises(erp_core.NotFoundError):
        await erp_core.resolve_warehouse("")


@pytest.mark.asyncio
async def test_resolve_warehouse_with_connection() -> None:
    conn = _FakeConn(fetch=[[_DictRecord({"id": uuid4(), "code": "MAIN"})]])
    assert (await erp_core.resolve_warehouse("MAIN", conn=conn))["code"] == "MAIN"


# ============================================================
# 往來對象
# ============================================================


@pytest.mark.asyncio
async def test_list_parties_filters_soft_deleted(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[2], fetch=[[_party_row()]])
    _patch(monkeypatch, party_service, conn)

    result = await party_service.list_parties(q="鴻佰", role="supplier")

    assert result["total"] == 2
    count_sql = conn.calls[0][1]
    assert "p.deleted_at IS NULL" in count_sql
    assert conn.calls[0][2] == ("supplier", "%鴻佰%")


@pytest.mark.asyncio
async def test_get_party_detail_aggregates(monkeypatch) -> None:
    row = _party_row()
    conn = _FakeConn(
        fetchrow=[row],
        fetch=[
            [_DictRecord({"id": uuid4(), "name": "陳先生"})],
            [_DictRecord({"id": uuid4(), "address": "桃園"})],
            [_DictRecord({"po_no": "PO-202609-001"})],
            [_DictRecord({"id": uuid4(), "name": "A 案", "status": "active"})],
        ],
    )
    _patch(monkeypatch, party_service, conn)
    monkeypatch.setattr(party_service, "count_party_knowledge", lambda name: 3)

    detail = await party_service.get_party_detail(row["id"])

    assert detail["knowledge_count"] == 3
    assert len(detail["contacts"]) == 1
    assert detail["purchase_orders"][0]["po_no"] == "PO-202609-001"
    assert detail["projects"][0]["name"] == "A 案"


@pytest.mark.asyncio
async def test_get_party_detail_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, party_service, conn)
    assert await party_service.get_party_detail(uuid4()) is None


def test_count_party_knowledge_swallows_errors(monkeypatch) -> None:
    import ching_tech_os.services.knowledge as knowledge_module

    def _boom(**_kwargs):
        raise RuntimeError("index 壞了")

    monkeypatch.setattr(knowledge_module, "search_knowledge", _boom)
    assert party_service.count_party_knowledge("鴻佰") == 0


def test_count_party_knowledge_returns_total(monkeypatch) -> None:
    import ching_tech_os.services.knowledge as knowledge_module

    monkeypatch.setattr(
        knowledge_module,
        "search_knowledge",
        lambda **_kwargs: MagicMock(total=5),
    )
    assert party_service.count_party_knowledge("鴻佰") == 5


@pytest.mark.asyncio
async def test_create_party_writes_children_and_audit(monkeypatch) -> None:
    row = _party_row()
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[row, _DictRecord({"id": uuid4()}), _DictRecord({"id": uuid4()})],
        fetchval=[audit_id],
    )
    _patch(monkeypatch, party_service, conn)

    result = await party_service.create_party(
        {
            "name": "鴻佰科技",
            "contacts": [{"name": "陳先生", "is_primary": True}],
            "addresses": [{"address": "桃園", "is_primary": True}],
        },
        actor_user_id=9,
        via="mcp",
        agent_name="linebot",
    )

    assert result["audit_id"] == audit_id
    assert conn.in_transaction is True
    # 順序：主檔 → 聯絡人 → 地址 → 稽核
    assert conn.index_of("INSERT INTO parties") < conn.index_of(
        "INSERT INTO party_contacts"
    )
    assert conn.index_of("INSERT INTO party_addresses") < conn.index_of(
        "INSERT INTO erp_audit"
    )
    # is_primary 的聯絡人會先把其他的取消
    assert conn.find("UPDATE party_contacts SET is_primary = false")
    assert conn.find("INSERT INTO erp_audit")[0][2][5] == "mcp"


@pytest.mark.asyncio
async def test_update_party_computes_diff(monkeypatch) -> None:
    before = _party_row(payment_terms="月結 30 天")
    after = _party_row(id=before["id"], payment_terms="月結 60 天")
    audit_id = uuid4()
    conn = _FakeConn(fetchrow=[before, after], fetchval=[audit_id])
    _patch(monkeypatch, party_service, conn)

    result = await party_service.update_party(
        before["id"], {"payment_terms": "月結 60 天", "ignored": 1}
    )

    assert result["audit_id"] == audit_id
    update_sql = conn.calls[1][1]
    assert "payment_terms = $2" in update_sql
    assert "ignored" not in update_sql
    diff_json = conn.find("INSERT INTO erp_audit")[0][2][3]
    assert "月結 60 天" in diff_json


@pytest.mark.asyncio
async def test_update_party_without_fields_still_audits(monkeypatch) -> None:
    before = _party_row()
    conn = _FakeConn(fetchrow=[before], fetchval=[uuid4()])
    _patch(monkeypatch, party_service, conn)

    result = await party_service.update_party(before["id"], {})
    assert result["id"] == before["id"]
    assert not conn.find("UPDATE parties")


@pytest.mark.asyncio
async def test_update_party_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, party_service, conn)
    assert await party_service.update_party(uuid4(), {"name": "X"}) is None


@pytest.mark.asyncio
async def test_delete_party_is_soft(monkeypatch) -> None:
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "name": "鴻佰"})], fetchval=[audit_id]
    )
    _patch(monkeypatch, party_service, conn)

    assert await party_service.delete_party(uuid4()) == audit_id
    sql = conn.calls[0][1]
    assert "SET deleted_at = NOW()" in sql
    assert "DELETE FROM parties" not in " ".join(conn.sqls())


@pytest.mark.asyncio
async def test_delete_party_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, party_service, conn)
    assert await party_service.delete_party(uuid4()) is None


@pytest.mark.asyncio
async def test_add_contact_requires_live_party(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[None])
    _patch(monkeypatch, party_service, conn)

    assert await party_service.add_contact(uuid4(), {"name": "陳先生"}) is None
    assert not conn.find("INSERT INTO party_contacts")


@pytest.mark.asyncio
async def test_add_contact_writes_audit(monkeypatch) -> None:
    audit_id = uuid4()
    contact = _DictRecord(
        {
            "id": uuid4(),
            "party_id": uuid4(),
            "name": "陳先生",
            "title": None,
            "phone": None,
            "mobile": None,
            "email": None,
            "is_primary": False,
            "notes": None,
        }
    )
    conn = _FakeConn(fetchrow=[contact], fetchval=[1, audit_id])
    _patch(monkeypatch, party_service, conn)

    result = await party_service.add_contact(contact["party_id"], {"name": "陳先生"})
    assert result["audit_id"] == audit_id


@pytest.mark.asyncio
async def test_add_address_requires_live_party(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[None])
    _patch(monkeypatch, party_service, conn)
    assert await party_service.add_address(uuid4(), {"address": "桃園"}) is None


@pytest.mark.asyncio
async def test_add_address_writes_audit(monkeypatch) -> None:
    audit_id = uuid4()
    address = _DictRecord(
        {
            "id": uuid4(),
            "party_id": uuid4(),
            "label": "公司",
            "address": "桃園",
            "city": None,
            "is_primary": True,
        }
    )
    conn = _FakeConn(fetchrow=[address], fetchval=[1, audit_id])
    _patch(monkeypatch, party_service, conn)

    result = await party_service.add_address(
        address["party_id"], {"address": "桃園", "is_primary": True}
    )
    assert result["audit_id"] == audit_id
    assert conn.find("UPDATE party_addresses SET is_primary = false")


@pytest.mark.asyncio
async def test_merge_parties_moves_children_and_soft_deletes(monkeypatch) -> None:
    keep = _party_row(name="鴻佰科技", aliases=["鴻佰"])
    drop = _party_row(name="鴻佰工業", short_name=None, aliases=["鴻佰工"], is_customer=True)
    merged = _party_row(id=keep["id"], aliases=["鴻佰", "鴻佰工業", "鴻佰工"])
    audit_id = uuid4()
    # 前兩個 fetchval 是「keep 這邊有沒有主要聯絡人／地址」
    conn = _FakeConn(fetchrow=[keep, drop, merged], fetchval=[None, None, audit_id])
    _patch(monkeypatch, party_service, conn)

    result = await party_service.merge_parties(keep["id"], drop["id"])

    assert result["audit_id"] == audit_id
    assert conn.find("UPDATE party_contacts")
    assert conn.find("UPDATE purchase_orders SET supplier_id")
    assert conn.find("UPDATE items SET default_supplier_id")
    # drop 被軟刪除
    assert any(
        "SET deleted_at = NOW()" in sql for sql in conn.sqls()
    )


@pytest.mark.asyncio
async def test_merge_parties_demotes_drop_primary_when_keep_has_one(
    monkeypatch,
) -> None:
    """F9：keep 已經有主要聯絡人／地址時，drop 搬過來的要降級"""
    keep = _party_row()
    drop = _party_row()
    conn = _FakeConn(
        fetchrow=[keep, drop, _party_row(id=keep["id"])],
        fetchval=[1, 1, uuid4()],  # keep 兩邊都已經有 primary
    )
    _patch(monkeypatch, party_service, conn)

    await party_service.merge_parties(keep["id"], drop["id"])

    contacts = conn.find("UPDATE party_contacts")[0]
    addresses = conn.find("UPDATE party_addresses")[0]
    assert "is_primary = CASE WHEN $3 THEN false ELSE is_primary END" in contacts[1]
    assert contacts[2][2] is True
    assert addresses[2][2] is True


@pytest.mark.asyncio
async def test_merge_parties_keeps_drop_primary_when_keep_has_none(
    monkeypatch,
) -> None:
    keep = _party_row()
    drop = _party_row()
    conn = _FakeConn(
        fetchrow=[keep, drop, _party_row(id=keep["id"])],
        fetchval=[None, None, uuid4()],
    )
    _patch(monkeypatch, party_service, conn)

    await party_service.merge_parties(keep["id"], drop["id"])

    assert conn.find("UPDATE party_contacts")[0][2][2] is False


@pytest.mark.asyncio
async def test_merge_parties_rejects_same_id() -> None:
    same = uuid4()
    with pytest.raises(erp_core.InvalidOperationError):
        await party_service.merge_parties(same, same)


@pytest.mark.asyncio
async def test_merge_parties_rejects_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[_party_row(), None])
    _patch(monkeypatch, party_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await party_service.merge_parties(uuid4(), uuid4())


def test_merge_aliases_dedupes_and_skips_keep_name() -> None:
    keep = {"name": "鴻佰科技", "aliases": ["鴻佰"], "short_name": "鴻佰"}
    drop = {"name": "鴻佰科技", "short_name": "鴻佰", "aliases": ["鴻佰工"]}
    assert party_service._merge_aliases(keep, drop) == ["鴻佰", "鴻佰工"]


@pytest.mark.asyncio
async def test_summarize_party(monkeypatch) -> None:
    detail = {
        "id": uuid4(),
        "name": "鴻佰科技",
        "is_supplier": True,
        "is_customer": True,
        "tax_id": "12345678",
        "payment_terms": "月結 60 天",
        "contacts": [{"name": "陳先生", "phone": "03-1234567"}],
        "addresses": [{"address": "桃園市中壢區"}],
        "purchase_orders": [{"po_no": "PO-202609-001", "status": "received"}],
        "projects": [{"name": "A 案"}],
        "knowledge_count": 2,
    }
    monkeypatch.setattr(
        party_service, "get_party_detail", AsyncMock(return_value=detail)
    )

    result = await party_service.summarize_party(detail["id"])
    assert "供應商／客戶" in result["summary"]
    assert "PO-202609-001" in result["summary"]
    assert result["knowledge_count"] == 2


@pytest.mark.asyncio
async def test_summarize_party_without_relations(monkeypatch) -> None:
    detail = {
        "id": uuid4(),
        "name": "小廠",
        "is_supplier": False,
        "is_customer": False,
        "tax_id": None,
        "payment_terms": None,
        "contacts": [],
        "addresses": [],
        "purchase_orders": [],
        "projects": [],
        "knowledge_count": 0,
    }
    monkeypatch.setattr(
        party_service, "get_party_detail", AsyncMock(return_value=detail)
    )
    result = await party_service.summarize_party(detail["id"])
    assert "未標角色" in result["summary"]
    assert "近期採購單：無" in result["summary"]


@pytest.mark.asyncio
async def test_summarize_party_missing(monkeypatch) -> None:
    monkeypatch.setattr(party_service, "get_party_detail", AsyncMock(return_value=None))
    assert await party_service.summarize_party(uuid4()) is None


# ============================================================
# 物料與庫存
# ============================================================


@pytest.mark.asyncio
async def test_list_items(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[1], fetch=[[_DictRecord({"code": "CTOS-A1"})]])
    _patch(monkeypatch, inventory_service, conn)

    result = await inventory_service.list_items(q="螺絲", item_group="零件")
    assert result["total"] == 1
    assert conn.calls[0][2] == ("零件", "%螺絲%")
    assert "i.deleted_at IS NULL" in conn.calls[0][1]


@pytest.mark.asyncio
async def test_get_item_detail_sums_balances(monkeypatch) -> None:
    row = _item_row()
    conn = _FakeConn(
        fetchrow=[row],
        fetch=[
            [
                _DictRecord({"warehouse_id": uuid4(), "qty": Decimal("70")}),
                _DictRecord({"warehouse_id": uuid4(), "qty": Decimal("30")}),
            ],
            [_DictRecord({"id": uuid4(), "reason": "receipt"})],
        ],
    )
    _patch(monkeypatch, inventory_service, conn)

    detail = await inventory_service.get_item_detail(row["id"])
    assert detail["total_qty"] == Decimal("100")
    assert len(detail["movements"]) == 1
    # F8：餘額 join 的倉庫要排除軟刪除
    balance_sql = conn.find("FROM stock_balances b")[0][1]
    assert "JOIN warehouses w ON w.id = b.warehouse_id AND w.deleted_at IS NULL" in balance_sql


@pytest.mark.asyncio
async def test_get_item_detail_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, inventory_service, conn)
    assert await inventory_service.get_item_detail(uuid4()) is None


@pytest.mark.asyncio
async def test_create_item_rejects_duplicate_code(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[1])
    _patch(monkeypatch, inventory_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.create_item({"code": "CTOS-A1", "name": "螺絲"})
    assert not conn.find("INSERT INTO items")


@pytest.mark.asyncio
async def test_create_item_writes_audit(monkeypatch) -> None:
    row = _item_row()
    audit_id = uuid4()
    conn = _FakeConn(fetchrow=[row], fetchval=[None, audit_id])
    _patch(monkeypatch, inventory_service, conn)

    result = await inventory_service.create_item({"code": "CTOS-A1", "name": "螺絲"})
    assert result["audit_id"] == audit_id
    assert conn.in_transaction is True


@pytest.mark.asyncio
async def test_update_item_rejects_duplicate_code(monkeypatch) -> None:
    row = _item_row()
    conn = _FakeConn(fetchrow=[row], fetchval=[1])
    _patch(monkeypatch, inventory_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.update_item(row["id"], {"code": "CTOS-B2"})


@pytest.mark.asyncio
async def test_update_item(monkeypatch) -> None:
    before = _item_row()
    after = _item_row(id=before["id"], purchase_price=Decimal("9"))
    audit_id = uuid4()
    conn = _FakeConn(fetchrow=[before, after], fetchval=[audit_id])
    _patch(monkeypatch, inventory_service, conn)

    result = await inventory_service.update_item(
        before["id"], {"purchase_price": Decimal("9")}
    )
    assert result["audit_id"] == audit_id


@pytest.mark.asyncio
async def test_update_item_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, inventory_service, conn)
    assert await inventory_service.update_item(uuid4(), {"name": "X"}) is None


@pytest.mark.asyncio
async def test_update_item_without_fields(monkeypatch) -> None:
    before = _item_row()
    conn = _FakeConn(fetchrow=[before], fetchval=[uuid4()])
    _patch(monkeypatch, inventory_service, conn)
    result = await inventory_service.update_item(before["id"], {})
    assert result["code"] == before["code"]


@pytest.mark.asyncio
async def test_delete_item_is_soft(monkeypatch) -> None:
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "code": "CTOS-A1"})], fetchval=[audit_id]
    )
    _patch(monkeypatch, inventory_service, conn)

    assert await inventory_service.delete_item(uuid4()) == audit_id
    assert "SET deleted_at = NOW()" in conn.calls[0][1]


@pytest.mark.asyncio
async def test_delete_item_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, inventory_service, conn)
    assert await inventory_service.delete_item(uuid4()) is None


@pytest.mark.asyncio
async def test_warehouse_crud(monkeypatch) -> None:
    row = _DictRecord({"id": uuid4(), "code": "MAIN", "name": "主倉"})
    conn = _FakeConn(fetchval=[1], fetch=[[row]])
    _patch(monkeypatch, inventory_service, conn)
    listed = await inventory_service.list_warehouses()
    assert listed["total"] == 1

    conn = _FakeConn(fetchrow=[row], fetchval=[None, uuid4()])
    _patch(monkeypatch, inventory_service, conn)
    created = await inventory_service.create_warehouse({"code": "MAIN", "name": "主倉"})
    assert created["code"] == "MAIN"

    conn = _FakeConn(fetchval=[1])
    _patch(monkeypatch, inventory_service, conn)
    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.create_warehouse({"code": "MAIN", "name": "主倉"})


@pytest.mark.asyncio
async def test_update_warehouse(monkeypatch) -> None:
    before = _DictRecord({"id": uuid4(), "code": "MAIN", "name": "主倉"})
    after = _DictRecord({"id": before["id"], "code": "MAIN", "name": "總倉"})
    conn = _FakeConn(fetchrow=[before, after], fetchval=[uuid4()])
    _patch(monkeypatch, inventory_service, conn)

    result = await inventory_service.update_warehouse(before["id"], {"name": "總倉"})
    assert result["name"] == "總倉"


@pytest.mark.asyncio
async def test_update_warehouse_rejects_duplicate_code(monkeypatch) -> None:
    """F3：改代碼撞到別的倉要擋下來，不要讓 unique 例外變成 500"""
    before = _DictRecord({"id": uuid4(), "code": "MAIN", "name": "主倉"})
    conn = _FakeConn(fetchrow=[before], fetchval=[1])
    _patch(monkeypatch, inventory_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.update_warehouse(before["id"], {"code": "SUB"})
    assert not conn.find("UPDATE warehouses\n                SET")


@pytest.mark.asyncio
async def test_update_warehouse_missing_and_noop(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, inventory_service, conn)
    assert await inventory_service.update_warehouse(uuid4(), {"name": "X"}) is None

    before = _DictRecord({"id": uuid4(), "code": "MAIN", "name": "主倉"})
    conn = _FakeConn(fetchrow=[before], fetchval=[uuid4()])
    _patch(monkeypatch, inventory_service, conn)
    assert (await inventory_service.update_warehouse(before["id"], {}))["code"] == "MAIN"


@pytest.mark.asyncio
async def test_delete_warehouse_rejects_when_stock_left(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[Decimal("5")])
    _patch(monkeypatch, inventory_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.delete_warehouse(uuid4())


@pytest.mark.asyncio
async def test_delete_warehouse(monkeypatch) -> None:
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "code": "MAIN"})],
        fetchval=[Decimal("0"), audit_id],
    )
    _patch(monkeypatch, inventory_service, conn)
    assert await inventory_service.delete_warehouse(uuid4()) == audit_id


@pytest.mark.asyncio
async def test_delete_warehouse_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None], fetchval=[Decimal("0")])
    _patch(monkeypatch, inventory_service, conn)
    assert await inventory_service.delete_warehouse(uuid4()) is None


@pytest.mark.asyncio
async def test_get_stock_filters(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[1], fetch=[[_DictRecord({"qty": Decimal("10")})]])
    _patch(monkeypatch, inventory_service, conn)

    item_id, warehouse_id = uuid4(), uuid4()
    result = await inventory_service.get_stock(item_id, warehouse_id)
    assert result["total"] == 1
    assert conn.calls[0][2] == (item_id, warehouse_id)
    assert "i.deleted_at IS NULL" in conn.calls[0][1]
    # F8：軟刪除的倉庫不列
    assert "w.deleted_at IS NULL" in conn.calls[0][1]
    assert "JOIN warehouses w" in conn.calls[0][1]


@pytest.mark.asyncio
async def test_apply_movement_writes_movement_then_upserts_balance() -> None:
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4(), "qty_delta": Decimal("10")}),
            _DictRecord({"id": uuid4(), "qty": Decimal("110")}),
        ]
    )
    item_id, warehouse_id = uuid4(), uuid4()

    result = await inventory_service.apply_movement(
        conn, item_id, warehouse_id, Decimal("10"), "receipt"
    )

    assert result["balance"]["qty"] == Decimal("110")
    assert conn.index_of("INSERT INTO stock_movements") < conn.index_of(
        "INSERT INTO stock_balances"
    )
    upsert_sql = conn.calls[1][1]
    assert "ON CONFLICT (item_id, warehouse_id)" in upsert_sql
    assert "qty = stock_balances.qty + EXCLUDED.qty" in upsert_sql


@pytest.mark.asyncio
async def test_apply_movement_rejects_negative_balance() -> None:
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4()}),
            _DictRecord({"id": uuid4(), "qty": Decimal("-5")}),
        ]
    )
    with pytest.raises(erp_core.NegativeStockError):
        await inventory_service.apply_movement(
            conn, uuid4(), uuid4(), Decimal("-15"), "issue"
        )


@pytest.mark.asyncio
async def test_apply_movement_allows_negative_when_opted_in() -> None:
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4()}),
            _DictRecord({"id": uuid4(), "qty": Decimal("-5")}),
        ]
    )
    result = await inventory_service.apply_movement(
        conn, uuid4(), uuid4(), Decimal("-15"), "issue", allow_negative=True
    )
    assert result["balance"]["qty"] == Decimal("-5")


@pytest.mark.asyncio
async def test_adjust_stock_rejects_zero() -> None:
    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.adjust_stock(uuid4(), uuid4(), Decimal("0"))


@pytest.mark.asyncio
async def test_adjust_stock_writes_audit(monkeypatch) -> None:
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4()}),
            _DictRecord({"id": uuid4(), "qty": Decimal("110")}),
        ],
        fetchval=[audit_id],
    )
    _patch(monkeypatch, inventory_service, conn)

    result = await inventory_service.adjust_stock(
        uuid4(), uuid4(), Decimal("10"), reason="receipt", via="mcp"
    )
    assert result["audit_id"] == audit_id
    assert conn.in_transaction is True


@pytest.mark.asyncio
async def test_transfer_stock_rejects_bad_input() -> None:
    same = uuid4()
    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.transfer_stock(uuid4(), same, same, Decimal("1"))
    with pytest.raises(erp_core.InvalidOperationError):
        await inventory_service.transfer_stock(
            uuid4(), uuid4(), uuid4(), Decimal("-1")
        )


@pytest.mark.asyncio
async def test_transfer_stock_writes_two_movements(monkeypatch) -> None:
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4(), "reason": "transfer_out"}),
            _DictRecord({"id": uuid4(), "qty": Decimal("70")}),
            _DictRecord({"id": uuid4(), "reason": "transfer_in"}),
            _DictRecord({"id": uuid4(), "qty": Decimal("30")}),
        ],
        fetchval=[audit_id],
    )
    _patch(monkeypatch, inventory_service, conn)

    result = await inventory_service.transfer_stock(
        uuid4(), uuid4(), uuid4(), Decimal("30")
    )
    assert len(result["movements"]) == 2
    reasons = [c[2][3] for c in conn.find("INSERT INTO stock_movements")]
    assert reasons == ["transfer_out", "transfer_in"]


@pytest.mark.asyncio
async def test_summarize_item(monkeypatch) -> None:
    detail = {
        "id": uuid4(),
        "code": "CTOS-A1",
        "name": "不鏽鋼螺絲",
        "spec": "M6",
        "unit": "支",
        "total_qty": Decimal("100"),
        "balances": [{"warehouse_name": "主倉", "qty": Decimal("100")}],
        "default_supplier_name": "鴻佰科技",
        "purchase_price": Decimal("5"),
        "movements": [{"reason": "receipt", "qty_delta": Decimal("10")}],
    }
    monkeypatch.setattr(
        inventory_service, "get_item_detail", AsyncMock(return_value=detail)
    )

    result = await inventory_service.summarize_item(detail["id"])
    assert "主倉" in result["summary"]
    assert result["warehouse_count"] == 1


@pytest.mark.asyncio
async def test_summarize_item_without_movements(monkeypatch) -> None:
    detail = {
        "id": uuid4(),
        "code": "CTOS-A1",
        "name": "螺絲",
        "spec": None,
        "unit": None,
        "total_qty": Decimal("0"),
        "balances": [],
        "default_supplier_name": None,
        "purchase_price": None,
        "movements": [],
    }
    monkeypatch.setattr(
        inventory_service, "get_item_detail", AsyncMock(return_value=detail)
    )
    result = await inventory_service.summarize_item(detail["id"])
    assert "最近異動：無" in result["summary"]


@pytest.mark.asyncio
async def test_summarize_item_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        inventory_service, "get_item_detail", AsyncMock(return_value=None)
    )
    assert await inventory_service.summarize_item(uuid4()) is None


# ============================================================
# 採購
# ============================================================


@pytest.mark.asyncio
async def test_next_po_no_locks_and_increments() -> None:
    conn = _FakeConn(fetchval=[7])
    po_no = await purchasing_service.next_po_no(conn, date(2026, 9, 12))

    assert po_no == "PO-202609-008"
    assert "pg_advisory_xact_lock" in conn.calls[0][1]
    assert conn.calls[0][2] == ("PO-202609-",)


@pytest.mark.asyncio
async def test_next_po_no_starts_at_001() -> None:
    conn = _FakeConn(fetchval=[None])
    assert await purchasing_service.next_po_no(conn, date(2026, 1, 5)) == "PO-202601-001"


@pytest.mark.asyncio
async def test_create_purchase_order_requires_lines() -> None:
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.create_purchase_order(
            {"supplier_id": uuid4(), "lines": []}
        )


@pytest.mark.asyncio
async def test_create_purchase_order_rejects_unknown_supplier(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, purchasing_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.create_purchase_order(
            {"supplier_id": uuid4(), "lines": [{"item_id": uuid4(), "qty": 1}]}
        )


@pytest.mark.asyncio
async def test_create_purchase_order_rejects_unknown_project(monkeypatch) -> None:
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "name": "鴻佰"})], fetchval=[None]
    )
    _patch(monkeypatch, purchasing_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.create_purchase_order(
            {
                "supplier_id": uuid4(),
                "project_id": uuid4(),
                "lines": [{"item_id": uuid4(), "qty": 1}],
            }
        )


@pytest.mark.asyncio
async def test_create_purchase_order_rejects_unknown_item(monkeypatch) -> None:
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4(), "name": "鴻佰"}),
            _DictRecord({"id": uuid4(), "po_no": "PO-202609-001"}),
            None,
        ],
        fetchval=[0],
    )
    _patch(monkeypatch, purchasing_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.create_purchase_order(
            {"supplier_id": uuid4(), "lines": [{"item_id": uuid4(), "qty": 1}]}
        )


@pytest.mark.asyncio
async def test_create_purchase_order_rejects_zero_qty(monkeypatch) -> None:
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4(), "name": "鴻佰"}),
            _DictRecord({"id": uuid4(), "po_no": "PO-202609-001"}),
            _DictRecord({"id": uuid4(), "code": "CTOS-A1"}),
        ],
        fetchval=[0],
    )
    _patch(monkeypatch, purchasing_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.create_purchase_order(
            {"supplier_id": uuid4(), "lines": [{"item_id": uuid4(), "qty": 0}]}
        )


@pytest.mark.asyncio
async def test_create_purchase_order_generates_po_no(monkeypatch) -> None:
    audit_id = uuid4()
    po_row = _DictRecord(
        {"id": uuid4(), "po_no": "PO-202609-001", "status": "ordered"}
    )
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": uuid4(), "name": "鴻佰"}),
            po_row,
            _DictRecord({"id": uuid4(), "code": "CTOS-A1"}),
        ],
        fetchval=[0, audit_id],
    )
    _patch(monkeypatch, purchasing_service, conn)

    result = await purchasing_service.create_purchase_order(
        {
            "supplier_id": uuid4(),
            "order_date": date(2026, 9, 12),
            "lines": [{"item_id": uuid4(), "qty": Decimal("10"), "unit_price": 5}],
        }
    )

    assert result["po_no"] == "PO-202609-001"
    assert result["audit_id"] == audit_id
    assert conn.find("INSERT INTO purchase_order_lines")
    assert conn.in_transaction is True


@pytest.mark.asyncio
async def test_list_purchase_orders_filters(monkeypatch) -> None:
    conn = _FakeConn(fetchval=[1], fetch=[[_DictRecord({"po_no": "PO-202609-001"})]])
    _patch(monkeypatch, purchasing_service, conn)

    supplier_id, project_id = uuid4(), uuid4()
    result = await purchasing_service.list_purchase_orders(
        supplier_id=supplier_id,
        status="ordered",
        project_id=project_id,
        since=date(2026, 9, 1),
    )
    assert result["total"] == 1
    assert conn.calls[0][2] == (supplier_id, "ordered", project_id, date(2026, 9, 1))


@pytest.mark.asyncio
async def test_get_purchase_order_sums_amount(monkeypatch) -> None:
    po_id = uuid4()
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": po_id, "po_no": "PO-202609-001"})],
        fetch=[
            [
                _DictRecord({"qty": Decimal("10"), "unit_price": Decimal("5")}),
                _DictRecord({"qty": Decimal("2"), "unit_price": None}),
            ]
        ],
    )
    _patch(monkeypatch, purchasing_service, conn)

    detail = await purchasing_service.get_purchase_order(po_id=po_id)
    assert detail["total_amount"] == Decimal("50")


@pytest.mark.asyncio
async def test_get_purchase_order_requires_a_key() -> None:
    """F5：兩個參數都沒給是程式錯誤，不能讓 SQL 撈回第一筆"""
    with pytest.raises(ValueError):
        await purchasing_service.get_purchase_order()


@pytest.mark.asyncio
async def test_get_purchase_order_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, purchasing_service, conn)
    assert await purchasing_service.get_purchase_order(po_no="PO-x") is None


@pytest.mark.asyncio
async def test_update_purchase_order_rejects_closed(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[_DictRecord({"id": uuid4(), "status": "received"})])
    _patch(monkeypatch, purchasing_service, conn)

    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.update_purchase_order(uuid4(), {"notes": "x"})


@pytest.mark.asyncio
async def test_update_purchase_order(monkeypatch) -> None:
    before = _DictRecord({"id": uuid4(), "status": "ordered", "notes": None})
    after = _DictRecord({"id": before["id"], "status": "ordered", "notes": "急件"})
    conn = _FakeConn(fetchrow=[before, after], fetchval=[uuid4()])
    _patch(monkeypatch, purchasing_service, conn)

    result = await purchasing_service.update_purchase_order(
        before["id"], {"notes": "急件"}
    )
    assert result["notes"] == "急件"


@pytest.mark.asyncio
async def test_update_purchase_order_missing_and_noop(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, purchasing_service, conn)
    assert await purchasing_service.update_purchase_order(uuid4(), {}) is None

    before = _DictRecord({"id": uuid4(), "status": "ordered", "notes": None})
    conn = _FakeConn(fetchrow=[before], fetchval=[uuid4()])
    _patch(monkeypatch, purchasing_service, conn)
    assert (await purchasing_service.update_purchase_order(before["id"], {}))[
        "status"
    ] == "ordered"


# ── 收貨計畫（純函式）────────────────────────────────────────


def _po_line(item_id, qty, received="0"):
    return _DictRecord(
        {
            "id": uuid4(),
            "item_id": item_id,
            "qty": Decimal(qty),
            "received_qty": Decimal(received),
            "item_code": "CTOS-A1",
        }
    )


def test_receive_plan_all_takes_outstanding_only() -> None:
    a, b = uuid4(), uuid4()
    lines = [_po_line(a, "10", "10"), _po_line(b, "5", "2")]
    plan = purchasing_service._receive_plan(lines, None, True)
    assert [(item, qty) for _lid, item, qty in plan] == [(b, Decimal("3"))]


def test_receive_plan_all_covers_two_lines_of_same_item() -> None:
    """F1：同一物料兩行時，receive_all 要兩行都收（舊版會漏掉一行）"""
    item = uuid4()
    first, second = _po_line(item, "10"), _po_line(item, "4")
    plan = purchasing_service._receive_plan([first, second], None, True)

    assert [line_id for line_id, _item, _qty in plan] == [first["id"], second["id"]]
    assert [qty for _lid, _item, qty in plan] == [Decimal("10"), Decimal("4")]


def test_receive_plan_by_line_id() -> None:
    item = uuid4()
    first, second = _po_line(item, "10"), _po_line(item, "4")
    plan = purchasing_service._receive_plan(
        [first, second], [{"line_id": second["id"], "qty": 4}], False
    )
    assert plan == [(second["id"], item, Decimal("4"))]


def test_receive_plan_by_item_is_ambiguous_when_two_lines() -> None:
    """F1 裁定：只給 item 而該物料有兩行 → 回候選，不准猜"""
    item = uuid4()
    lines = [_po_line(item, "10"), _po_line(item, "4")]
    with pytest.raises(erp_core.AmbiguousError) as exc:
        purchasing_service._receive_plan(lines, [{"item_id": item, "qty": 1}], False)

    assert len(exc.value.candidates) == 2
    assert exc.value.candidates[0]["line_id"] == str(lines[0]["id"])
    assert exc.value.candidates[0]["item_code"] == "CTOS-A1"


def test_receive_plan_by_item_ok_when_single_line() -> None:
    item = uuid4()
    line = _po_line(item, "10")
    plan = purchasing_service._receive_plan(
        [line], [{"item_id": item, "qty": 4}], False
    )
    assert plan == [(line["id"], item, Decimal("4"))]


def test_receive_plan_rejects_unknown_line_id() -> None:
    with pytest.raises(erp_core.InvalidOperationError):
        purchasing_service._receive_plan(
            [_po_line(uuid4(), "10")], [{"line_id": uuid4(), "qty": 1}], False
        )


def test_receive_plan_requires_line_or_item() -> None:
    with pytest.raises(erp_core.InvalidOperationError):
        purchasing_service._receive_plan(
            [_po_line(uuid4(), "10")], [{"qty": 1}], False
        )


def test_receive_plan_rejects_over_receive() -> None:
    a = uuid4()
    lines = [_po_line(a, "10", "8")]
    with pytest.raises(erp_core.InvalidOperationError):
        purchasing_service._receive_plan(lines, [{"item_id": a, "qty": 5}], False)


def test_receive_plan_rejects_unknown_item() -> None:
    lines = [_po_line(uuid4(), "10")]
    with pytest.raises(erp_core.InvalidOperationError):
        purchasing_service._receive_plan(lines, [{"item_id": uuid4(), "qty": 1}], False)


def test_receive_plan_rejects_zero_qty() -> None:
    a = uuid4()
    with pytest.raises(erp_core.InvalidOperationError):
        purchasing_service._receive_plan(
            [_po_line(a, "10")], [{"item_id": a, "qty": 0}], False
        )


def test_receive_plan_partial() -> None:
    a = uuid4()
    plan = purchasing_service._receive_plan(
        [_po_line(a, "10")], [{"item_id": a, "qty": 4}], False
    )
    assert plan[0][2] == Decimal("4")


@pytest.mark.asyncio
async def test_refresh_po_status() -> None:
    for total, received, expected in [
        ("10", "10", "received"),
        ("10", "4", "partial"),
        ("10", "0", "ordered"),
    ]:
        conn = _FakeConn(
            fetchrow=[
                _DictRecord(
                    {"total_qty": Decimal(total), "received_qty": Decimal(received)}
                )
            ]
        )
        assert await purchasing_service._refresh_po_status(conn, uuid4()) == expected


@pytest.mark.asyncio
async def test_resolve_receive_warehouse_single_warehouse() -> None:
    wid = uuid4()
    conn = _FakeConn(fetch=[[_DictRecord({"id": wid})]])
    assert await purchasing_service._resolve_receive_warehouse(conn, None) == wid


@pytest.mark.asyncio
async def test_resolve_receive_warehouse_requires_choice_when_many() -> None:
    conn = _FakeConn(fetch=[[_DictRecord({"id": uuid4()}), _DictRecord({"id": uuid4()})]])
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service._resolve_receive_warehouse(conn, None)


@pytest.mark.asyncio
async def test_resolve_receive_warehouse_validates_given_id() -> None:
    conn = _FakeConn(fetchval=[None])
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service._resolve_receive_warehouse(conn, uuid4())


@pytest.mark.asyncio
async def test_receive_purchase_order_updates_lines_and_status(monkeypatch) -> None:
    po_id, item_id, wh_id = uuid4(), uuid4(), uuid4()
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": po_id, "po_no": "PO-202609-001", "status": "ordered"}),
            # apply_movement 的 movement 與 balance
            _DictRecord({"id": uuid4()}),
            _DictRecord({"id": uuid4(), "qty": Decimal("10")}),
            # _refresh_po_status
            _DictRecord({"total_qty": Decimal("10"), "received_qty": Decimal("10")}),
        ],
        fetchval=[1, audit_id],
        fetch=[[_po_line(item_id, "10")]],
    )
    _patch(monkeypatch, purchasing_service, conn)

    result = await purchasing_service.receive_purchase_order(
        po_id, lines=[{"item_id": item_id, "qty": Decimal("10")}], warehouse_id=wh_id
    )

    assert result["status"] == "received"
    assert result["audit_id"] == audit_id
    assert conn.find("SET received_qty = received_qty + $2")
    assert conn.find("INSERT INTO stock_movements")[0][2][3] == "receipt"
    # 稽核 diff 記 line_id（F1）
    assert '"line_id"' in conn.find("INSERT INTO erp_audit")[0][2][3]


@pytest.mark.asyncio
async def test_receive_all_two_lines_of_same_item(monkeypatch) -> None:
    """F1 回歸：同一物料兩行的 PO，receive_all 兩行都收、狀態到 received"""
    po_id, item_id, wh_id = uuid4(), uuid4(), uuid4()
    first, second = _po_line(item_id, "10"), _po_line(item_id, "4")
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": po_id, "po_no": "PO-202609-001", "status": "ordered"}),
            _DictRecord({"id": uuid4()}),                       # 第一行 movement
            _DictRecord({"id": uuid4(), "qty": Decimal("10")}),  # 第一行 balance
            _DictRecord({"id": uuid4()}),                       # 第二行 movement
            _DictRecord({"id": uuid4(), "qty": Decimal("14")}),  # 第二行 balance
            _DictRecord({"total_qty": Decimal("14"), "received_qty": Decimal("14")}),
        ],
        fetchval=[1, uuid4()],
        fetch=[[first, second]],
    )
    _patch(monkeypatch, purchasing_service, conn)

    result = await purchasing_service.receive_purchase_order(
        po_id, receive_all=True, warehouse_id=wh_id
    )

    assert result["status"] == "received"
    assert len(result["movements"]) == 2
    updated_lines = [c[2][0] for c in conn.find("SET received_qty = received_qty + $2")]
    assert updated_lines == [first["id"], second["id"]]


@pytest.mark.asyncio
async def test_receive_by_item_with_two_lines_raises_ambiguous(monkeypatch) -> None:
    po_id, item_id = uuid4(), uuid4()
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": po_id, "po_no": "PO-1", "status": "ordered"})],
        fetch=[[_po_line(item_id, "10"), _po_line(item_id, "4")]],
    )
    _patch(monkeypatch, purchasing_service, conn)

    with pytest.raises(erp_core.AmbiguousError):
        await purchasing_service.receive_purchase_order(
            po_id, lines=[{"item_id": item_id, "qty": 1}], warehouse_id=uuid4()
        )


@pytest.mark.asyncio
async def test_receive_purchase_order_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, purchasing_service, conn)
    assert await purchasing_service.receive_purchase_order(uuid4()) is None


@pytest.mark.asyncio
async def test_receive_purchase_order_rejects_closed(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[_DictRecord({"id": uuid4(), "status": "cancelled"})])
    _patch(monkeypatch, purchasing_service, conn)
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.receive_purchase_order(uuid4(), receive_all=True)


@pytest.mark.asyncio
async def test_receive_purchase_order_without_lines(monkeypatch) -> None:
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "status": "ordered"})], fetch=[[]]
    )
    _patch(monkeypatch, purchasing_service, conn)
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.receive_purchase_order(uuid4(), receive_all=True)


@pytest.mark.asyncio
async def test_receive_purchase_order_nothing_outstanding(monkeypatch) -> None:
    item_id = uuid4()
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "status": "partial"})],
        fetch=[[_po_line(item_id, "10", "10")]],
    )
    _patch(monkeypatch, purchasing_service, conn)
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.receive_purchase_order(uuid4(), receive_all=True)


@pytest.mark.asyncio
async def test_cancel_purchase_order(monkeypatch) -> None:
    po_id = uuid4()
    audit_id = uuid4()
    conn = _FakeConn(
        fetchrow=[
            _DictRecord({"id": po_id, "po_no": "PO-202609-002", "status": "ordered"}),
            _DictRecord({"id": po_id, "po_no": "PO-202609-002", "status": "cancelled"}),
        ],
        fetchval=[Decimal("0"), audit_id],
    )
    _patch(monkeypatch, purchasing_service, conn)

    result = await purchasing_service.cancel_purchase_order(po_id, reason="改採別家")
    assert result["status"] == "cancelled"
    assert result["audit_id"] == audit_id


@pytest.mark.asyncio
async def test_cancel_purchase_order_missing(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[None])
    _patch(monkeypatch, purchasing_service, conn)
    assert await purchasing_service.cancel_purchase_order(uuid4()) is None


@pytest.mark.asyncio
async def test_cancel_purchase_order_already_cancelled(monkeypatch) -> None:
    conn = _FakeConn(fetchrow=[_DictRecord({"id": uuid4(), "status": "cancelled"})])
    _patch(monkeypatch, purchasing_service, conn)
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.cancel_purchase_order(uuid4())


@pytest.mark.asyncio
async def test_cancel_purchase_order_rejects_received_lines(monkeypatch) -> None:
    conn = _FakeConn(
        fetchrow=[_DictRecord({"id": uuid4(), "status": "partial"})],
        fetchval=[Decimal("4")],
    )
    _patch(monkeypatch, purchasing_service, conn)
    with pytest.raises(erp_core.InvalidOperationError):
        await purchasing_service.cancel_purchase_order(uuid4())


# ============================================================
# 文件擷取輔助
# ============================================================


@pytest.mark.asyncio
async def test_match_duplicate_parties_puts_tax_id_hit_first(monkeypatch) -> None:
    fuzzy_id, tax_id_hit = uuid4(), uuid4()
    monkeypatch.setattr(
        erp_core,
        "find_parties",
        AsyncMock(return_value=[{"id": fuzzy_id, "name": "鴻佰工業"}]),
    )
    conn = _FakeConn(
        fetch=[[_DictRecord({"id": tax_id_hit, "name": "鴻佰科技", "tax_id": "12345678"})]]
    )
    _patch(monkeypatch, purchasing_service, conn)

    result = await purchasing_service.match_duplicate_parties("鴻佰", "12345678")
    assert result[0]["id"] == tax_id_hit
    assert result[0]["exact_hit"] is True


@pytest.mark.asyncio
async def test_match_duplicate_parties_without_tax_id(monkeypatch) -> None:
    monkeypatch.setattr(erp_core, "find_parties", AsyncMock(return_value=[]))
    assert await purchasing_service.match_duplicate_parties("鴻佰") == []


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026-09-12", date(2026, 9, 12)),
        ("2026/09/12", date(2026, 9, 12)),
        ("20260912", date(2026, 9, 12)),
        ("民國 115 年", None),
        (None, None),
        (date(2026, 9, 12), date(2026, 9, 12)),
        (datetime(2026, 9, 12, 8, 0), date(2026, 9, 12)),
    ],
)
def test_normalize_extracted_date(raw, expected) -> None:
    assert purchasing_service.normalize_extracted_date(raw) == expected
