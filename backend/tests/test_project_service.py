"""專案模組 Service 層測試。

DB 一律用 AsyncMock 假的 connection，驗 SQL 內容與呼叫序。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ching_tech_os.services import project as project_service


class _DictRecord(dict):
    """模擬 asyncpg Record（同時支援 dict() 和 key 存取）"""


class _CM:
    """Mock connection context manager"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


class _Tx:
    """模擬 conn.transaction() 的 async context manager"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def _patch_conn(monkeypatch: pytest.MonkeyPatch, conn) -> None:
    conn.transaction = MagicMock(return_value=_Tx())
    monkeypatch.setattr(project_service, "get_connection", lambda: _CM(conn))


def _project_row(**overrides) -> _DictRecord:
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "name": "A 案",
        "customer": "甲客戶",
        "status": "active",
        "owner_id": 1,
        "owner_name": "小明",
        "start_date": None,
        "end_date": None,
        "description": None,
        "created_by": 1,
        "created_at": now,
        "updated_at": now,
        "task_count": 4,
        "done_count": 1,
        "member_count": 2,
        "overdue_milestones": 1,
    }
    base.update(overrides)
    return _DictRecord(base)


# ============================================================
# 純函式：進度與逾期
# ============================================================


@pytest.mark.parametrize(
    "done, total, expected",
    [
        (0, 0, 0),          # 沒有任務時為 0
        (None, None, 0),
        (0, 4, 0),
        (1, 4, 25),
        (1, 3, 33),         # 四捨五入
        (2, 3, 67),
        (4, 4, 100),
    ],
)
def test_calc_progress(done, total, expected) -> None:
    assert project_service.calc_progress(done, total) == expected


def test_is_milestone_overdue() -> None:
    today = date(2026, 9, 11)
    overdue = project_service.is_milestone_overdue

    # 到期日已過、未完成、專案還在進行中 → 逾期
    assert overdue(date(2026, 9, 10), "pending", "active", today)
    assert overdue(date(2026, 9, 10), "in_progress", "active", today)
    # 已完成不算逾期
    assert not overdue(date(2026, 9, 10), "completed", "active", today)
    # 今天到期不算逾期
    assert not overdue(today, "pending", "active", today)
    # 未來
    assert not overdue(date(2026, 9, 12), "pending", "active", today)
    # 沒有到期日
    assert not overdue(None, "pending", "active", today)


@pytest.mark.parametrize(
    "project_status", ["planning", "on_hold", "completed", "cancelled", None]
)
def test_is_milestone_overdue_only_for_active_projects(project_status) -> None:
    """規格第一節：逾期還要所屬專案 status = 'active'，結案／取消的不該一直紅著"""
    today = date(2026, 9, 11)
    assert not project_service.is_milestone_overdue(
        date(2026, 9, 10), "pending", project_status, today
    )


# ============================================================
# 清單
# ============================================================


@pytest.mark.asyncio
async def test_list_projects_computes_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[_project_row(task_count=4, done_count=1)])
    _patch_conn(monkeypatch, conn)

    result = await project_service.list_projects()

    assert result["total"] == 1
    item = result["items"][0]
    assert item["progress"] == 25
    assert item["member_count"] == 2
    assert item["overdue_milestones"] == 1
    # 進度靠 SQL 的 count(*) filter，不在 Python 迴圈裡數
    sql = conn.fetch.call_args[0][0]
    assert "count(*) FILTER (WHERE t.status = 'done')" in sql
    # 逾期定義：到期日已過、未完成，且所屬專案還在進行中
    assert "m.due_date < CURRENT_DATE" in sql
    assert "m.status <> 'completed'" in sql
    assert "p.status = 'active'" in sql


@pytest.mark.asyncio
async def test_list_projects_filters_and_paging(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])
    _patch_conn(monkeypatch, conn)

    await project_service.list_projects(status="active", q="甲", page=3, page_size=20)

    args = conn.fetch.call_args[0]
    assert args[1] == "active"
    assert args[2] == "%甲%"
    assert args[3] == 20      # limit
    assert args[4] == 40      # offset =（3-1）× 20


@pytest.mark.parametrize(
    "q, expected",
    [
        ("50%", "%50\\%%"),
        ("a_b", "%a\\_b%"),
        ("c\\d", "%c\\\\d%"),
        ("甲", "%甲%"),
    ],
)
def test_like_pattern_escapes_wildcards(q, expected) -> None:
    """ILIKE 的 % 與 _ 要跳脫，否則搜尋「50%」等於搜尋全部"""
    assert project_service.like_pattern(q) == expected


@pytest.mark.asyncio
async def test_list_projects_escapes_q(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])
    _patch_conn(monkeypatch, conn)

    await project_service.list_projects(q="50%")

    # q="50%" 的樣式必須是 %50\%%（中間那個 % 被跳脫）
    assert conn.fetch.call_args[0][2] == "%50\\%%"
    assert "ESCAPE '\\'" in conn.fetch.call_args[0][0]


# ============================================================
# 明細
# ============================================================


@pytest.mark.asyncio
async def test_get_project_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    mid = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_project_row(id=pid, task_count=2, done_count=1))
    conn.fetch = AsyncMock(
        side_effect=[
            [_DictRecord({"user_id": 1, "username": "ming", "display_name": "小明", "role": "owner"})],
            [
                _DictRecord(
                    {
                        "id": mid,
                        "project_id": pid,
                        "name": "出圖",
                        "due_date": date(2000, 1, 1),
                        "completed_at": None,
                        "status": "pending",
                        "sort_order": 0,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            ],
            [],
            [_DictRecord({"id": uuid4(), "platform_type": "line", "group_name": "工地群"})],
        ]
    )
    _patch_conn(monkeypatch, conn)
    monkeypatch.setattr(project_service, "count_project_knowledge", lambda _pid: 7)

    detail = await project_service.get_project_detail(pid)

    assert detail["progress"] == 50
    # 算出來的統計要留在明細裡（前端表頭要用），不能算了又丟掉
    assert detail["member_count"] == 2
    assert detail["overdue_milestones"] == 1
    assert detail["members"][0]["role"] == "owner"
    assert detail["milestones"][0]["is_overdue"] is True
    assert detail["bot_groups"][0]["group_name"] == "工地群"
    assert detail["knowledge_count"] == 7
    # bot_groups 的群組名稱來自 bot_groups.name，取別名 group_name
    assert "name AS group_name" in conn.fetch.call_args_list[3][0][0]


@pytest.mark.asyncio
async def test_get_project_detail_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    _patch_conn(monkeypatch, conn)

    assert await project_service.get_project_detail(uuid4()) is None


@pytest.mark.asyncio
async def test_project_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    _patch_conn(monkeypatch, conn)
    assert await project_service.project_exists(uuid4()) is True

    conn.fetchval = AsyncMock(return_value=None)
    assert await project_service.project_exists(uuid4()) is False


def test_count_project_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    """知識條目數走既有的 search_knowledge（讀檔案索引），不另開 index"""
    from ching_tech_os.services import knowledge as knowledge_service

    captured: dict = {}

    def _fake_search(**kwargs):
        captured.update(kwargs)
        return type("R", (), {"total": 3})()

    monkeypatch.setattr(knowledge_service, "search_knowledge", _fake_search)
    assert project_service.count_project_knowledge("pid-1") == 3
    assert captured == {"scope": "project", "project_id": "pid-1"}


def test_count_project_knowledge_survives_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.services import knowledge as knowledge_service

    def _boom(**_kwargs):
        raise RuntimeError("索引壞了")

    monkeypatch.setattr(knowledge_service, "search_knowledge", _boom)
    assert project_service.count_project_knowledge("pid-1") == 0


# ============================================================
# CRUD 與負責人／成員同步
# ============================================================


@pytest.mark.asyncio
async def test_create_project_syncs_owner_member(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_project_row(id=pid, owner_id=9))
    _patch_conn(monkeypatch, conn)

    await project_service.create_project({"name": "新案", "owner_id": 9}, created_by=1)

    assert "INSERT INTO projects" in conn.fetchrow.call_args[0][0]
    # 設 owner 會自動 upsert 成員 role='owner'，原 owner 降成 member
    executes = [c[0][0] for c in conn.execute.call_args_list]
    assert any("SET role = 'member'" in sql for sql in executes)
    assert any("DO UPDATE SET role = 'owner'" in sql for sql in executes)
    demote_idx = next(i for i, sql in enumerate(executes) if "SET role = 'member'" in sql)
    promote_idx = next(i for i, sql in enumerate(executes) if "DO UPDATE SET role = 'owner'" in sql)
    assert demote_idx < promote_idx


@pytest.mark.asyncio
async def test_create_project_without_owner_skips_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_project_row(owner_id=None))
    _patch_conn(monkeypatch, conn)

    await project_service.create_project({"name": "新案"})

    executes = [c[0][0] for c in conn.execute.call_args_list]
    assert not any("DO UPDATE SET role = 'owner'" in sql for sql in executes)


@pytest.mark.asyncio
async def test_update_project_owner_change_syncs_member(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_project_row(id=pid, owner_id=5))
    _patch_conn(monkeypatch, conn)

    await project_service.update_project(pid, {"owner_id": 5, "name": "改名"})

    sql = conn.fetchrow.call_args[0][0]
    assert "UPDATE projects" in sql
    assert "updated_at = NOW()" in sql
    executes = [c[0][0] for c in conn.execute.call_args_list]
    assert any("DO UPDATE SET role = 'owner'" in s for s in executes)


@pytest.mark.asyncio
async def test_update_project_no_fields_reads_back(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_project_row())
    _patch_conn(monkeypatch, conn)

    await project_service.update_project(uuid4(), {})

    assert "SELECT * FROM projects" in conn.fetchrow.call_args[0][0]
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_project_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    _patch_conn(monkeypatch, conn)

    assert await project_service.update_project(uuid4(), {"name": "x"}) is None


@pytest.mark.asyncio
async def test_delete_project_clears_bot_group_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 2", "DELETE 1"])
    _patch_conn(monkeypatch, conn)

    assert await project_service.delete_project(uuid4()) is True

    first_sql = conn.execute.call_args_list[0][0][0]
    second_sql = conn.execute.call_args_list[1][0][0]
    assert "UPDATE bot_groups SET project_id = NULL" in first_sql
    assert "DELETE FROM projects" in second_sql


@pytest.mark.asyncio
async def test_delete_project_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 0", "DELETE 0"])
    _patch_conn(monkeypatch, conn)

    assert await project_service.delete_project(uuid4()) is False


# ============================================================
# 成員
# ============================================================


@pytest.mark.asyncio
async def test_add_member(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)  # 使用者存在
    conn.fetchrow = AsyncMock(
        return_value=_DictRecord(
            {"user_id": 3, "username": "abc", "display_name": "阿貓", "role": "member"}
        )
    )
    _patch_conn(monkeypatch, conn)

    member = await project_service.add_member(uuid4(), 3)

    assert member["role"] == "member"
    assert "SELECT 1 FROM users WHERE id = $1" in conn.fetchval.call_args[0][0]
    assert "ON CONFLICT (project_id, user_id) DO NOTHING" in conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_add_member_unknown_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """使用者不存在時先擋下來，不要讓 FK 例外變成 500"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)  # users 查不到
    _patch_conn(monkeypatch, conn)

    assert await project_service.add_member(uuid4(), 999) is None
    # 沒有真的去 INSERT
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_member_owner_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="owner")
    _patch_conn(monkeypatch, conn)

    assert await project_service.remove_member(uuid4(), 1) == "owner"
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_member_ok_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="member")
    _patch_conn(monkeypatch, conn)
    assert await project_service.remove_member(uuid4(), 2) == "removed"

    conn.fetchval = AsyncMock(return_value=None)
    assert await project_service.remove_member(uuid4(), 2) == "not_found"


# ============================================================
# 里程碑與任務
# ============================================================


def _milestone_row(**overrides) -> _DictRecord:
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "project_id": uuid4(),
        "name": "交機",
        "due_date": date(2000, 1, 1),
        "completed_at": None,
        "status": "pending",
        "sort_order": 0,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return _DictRecord(base)


@pytest.mark.asyncio
async def test_create_milestone(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_milestone_row())
    conn.fetchval = AsyncMock(return_value="active")
    _patch_conn(monkeypatch, conn)

    row = await project_service.create_milestone(
        uuid4(), {"name": "交機", "due_date": date(2000, 1, 1)}
    )
    assert row["is_overdue"] is True
    assert "INSERT INTO milestones" in conn.fetchrow.call_args[0][0]
    conn.transaction.assert_called_once()


@pytest.mark.asyncio
async def test_create_milestone_on_cancelled_project_is_not_overdue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """專案取消後，過期的里程碑不再算逾期"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_milestone_row())
    conn.fetchval = AsyncMock(return_value="cancelled")
    _patch_conn(monkeypatch, conn)

    row = await project_service.create_milestone(
        uuid4(), {"name": "交機", "due_date": date(2000, 1, 1)}
    )
    assert row["is_overdue"] is False


@pytest.mark.asyncio
async def test_update_milestone(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_milestone_row(status="completed"))
    conn.fetchval = AsyncMock(return_value="active")
    _patch_conn(monkeypatch, conn)

    row = await project_service.update_milestone(uuid4(), uuid4(), {"status": "completed"})
    assert row["is_overdue"] is False
    assert "UPDATE milestones" in conn.fetchrow.call_args[0][0]

    # 沒有可更新欄位時退回讀取
    conn.fetchrow = AsyncMock(return_value=_milestone_row())
    await project_service.update_milestone(uuid4(), uuid4(), {})
    assert "SELECT * FROM milestones" in conn.fetchrow.call_args[0][0]

    conn.fetchrow = AsyncMock(return_value=None)
    assert await project_service.update_milestone(uuid4(), uuid4(), {"name": "x"}) is None


@pytest.mark.asyncio
async def test_delete_milestone(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 1")
    _patch_conn(monkeypatch, conn)
    assert await project_service.delete_milestone(uuid4(), uuid4()) is True

    conn.execute = AsyncMock(return_value="DELETE 0")
    assert await project_service.delete_milestone(uuid4(), uuid4()) is False


def _task_row(**overrides) -> _DictRecord:
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "project_id": uuid4(),
        "milestone_id": None,
        "title": "拉線",
        "description": None,
        "assignee_id": None,
        "status": "todo",
        "due_date": None,
        "sort_order": 0,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return _DictRecord(base)


@pytest.mark.asyncio
async def test_create_task(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_task_row())
    _patch_conn(monkeypatch, conn)

    row = await project_service.create_task(uuid4(), {"title": "拉線"})
    assert row["title"] == "拉線"
    assert "INSERT INTO tasks" in conn.fetchrow.call_args[0][0]


@pytest.mark.asyncio
async def test_update_task(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_task_row(status="done"))
    _patch_conn(monkeypatch, conn)

    row = await project_service.update_task(uuid4(), uuid4(), {"status": "done"})
    assert row["status"] == "done"
    assert "UPDATE tasks" in conn.fetchrow.call_args[0][0]

    conn.fetchrow = AsyncMock(return_value=_task_row())
    await project_service.update_task(uuid4(), uuid4(), {})
    assert "SELECT * FROM tasks" in conn.fetchrow.call_args[0][0]

    conn.fetchrow = AsyncMock(return_value=None)
    assert await project_service.update_task(uuid4(), uuid4(), {"title": "x"}) is None


@pytest.mark.asyncio
async def test_delete_task(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 1")
    _patch_conn(monkeypatch, conn)
    assert await project_service.delete_task(uuid4(), uuid4()) is True

    conn.execute = AsyncMock(return_value="DELETE 0")
    assert await project_service.delete_task(uuid4(), uuid4()) is False


# ============================================================
# Dashboard 摘要
# ============================================================


@pytest.mark.asyncio
async def test_get_summary_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=3)
    conn.fetch = AsyncMock(
        return_value=[
            _DictRecord(
                {
                    "project_id": uuid4(),
                    "project_name": "A 案",
                    "milestone_id": uuid4(),
                    "name": "交機",
                    "due_date": date(2026, 9, 1),
                    "days_overdue": 10,
                }
            )
        ]
    )
    _patch_conn(monkeypatch, conn)

    result = await project_service.get_summary()

    assert result["active_count"] == 3
    assert result["overdue_milestones"][0]["days_overdue"] == 10

    count_sql = conn.fetchval.call_args[0][0]
    assert "WHERE status = 'active'" in count_sql

    sql = conn.fetch.call_args[0][0]
    # 逾期定義：到期日已過、未完成，summary 另加專案 status = 'active'
    assert "m.due_date < CURRENT_DATE" in sql
    assert "m.status <> 'completed'" in sql
    assert "p.status = 'active'" in sql
    # 依到期日升冪、最多 20 筆
    assert "ORDER BY m.due_date ASC" in sql
    assert conn.fetch.call_args[0][1] == 20
    assert project_service.SUMMARY_OVERDUE_LIMIT == 20


# ============================================================
# 外鍵驗證（F2）與交易（F4）
# ============================================================


@pytest.mark.asyncio
async def test_create_project_rejects_unknown_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)  # users 查不到
    _patch_conn(monkeypatch, conn)

    with pytest.raises(project_service.UserNotFoundError):
        await project_service.create_project({"name": "新案", "owner_id": 999})

    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_project_rejects_unknown_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    _patch_conn(monkeypatch, conn)

    with pytest.raises(project_service.UserNotFoundError):
        await project_service.update_project(uuid4(), {"owner_id": 999})


@pytest.mark.asyncio
async def test_update_project_allows_clearing_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """owner_id 送 None 是清空負責人，不用驗使用者"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_project_row(owner_id=None))
    _patch_conn(monkeypatch, conn)

    await project_service.update_project(uuid4(), {"owner_id": None})

    assert not any(
        "FROM users" in c[0][0] for c in conn.fetchval.call_args_list
    )


@pytest.mark.asyncio
async def test_create_task_rejects_unknown_assignee(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    _patch_conn(monkeypatch, conn)

    with pytest.raises(project_service.UserNotFoundError):
        await project_service.create_task(uuid4(), {"title": "A", "assignee_id": 999})


@pytest.mark.asyncio
async def test_create_task_rejects_foreign_milestone(monkeypatch: pytest.MonkeyPatch) -> None:
    """里程碑不屬於這個專案就不准掛上去"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=False)  # EXISTS 回 false
    _patch_conn(monkeypatch, conn)

    with pytest.raises(project_service.MilestoneNotInProjectError):
        await project_service.create_task(
            uuid4(), {"title": "A", "milestone_id": uuid4()}
        )

    sql = conn.fetchval.call_args[0][0]
    assert "SELECT EXISTS" in sql
    assert "FROM milestones WHERE id = $1 AND project_id = $2" in sql
    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_rejects_foreign_milestone(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=False)
    _patch_conn(monkeypatch, conn)

    with pytest.raises(project_service.MilestoneNotInProjectError):
        await project_service.update_task(
            uuid4(), uuid4(), {"milestone_id": uuid4()}
        )


@pytest.mark.asyncio
async def test_update_task_rejects_unknown_assignee(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    _patch_conn(monkeypatch, conn)

    with pytest.raises(project_service.UserNotFoundError):
        await project_service.update_task(uuid4(), uuid4(), {"assignee_id": 999})


@pytest.mark.asyncio
async def test_task_allows_clearing_milestone_and_assignee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """送 None 是清空關聯，不用驗"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_task_row())
    _patch_conn(monkeypatch, conn)

    await project_service.update_task(
        uuid4(), uuid4(), {"milestone_id": None, "assignee_id": None}
    )

    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_mutations_run_in_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """多語句的寫入要包在交易裡，中途失敗不能留半套"""
    pid = uuid4()

    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=_project_row(id=pid, owner_id=1))
    _patch_conn(monkeypatch, conn)
    await project_service.create_project({"name": "x", "owner_id": 1})
    conn.transaction.assert_called_once()

    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=_project_row(id=pid, owner_id=1))
    _patch_conn(monkeypatch, conn)
    await project_service.update_project(pid, {"owner_id": 1})
    conn.transaction.assert_called_once()

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 0", "DELETE 1"])
    _patch_conn(monkeypatch, conn)
    await project_service.delete_project(pid)
    conn.transaction.assert_called_once()
