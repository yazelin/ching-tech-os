"""project service 高覆蓋 smoke 測試。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ching_tech_os.services import project


class _DummyModel(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, item):
        return self.get(item)


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


class _Row(dict):
    def __getitem__(self, key):  # noqa: D401
        return self.get(key)


class _Conn:
    def __init__(self, row: _Row):
        self.row = row

    async def fetch(self, *_args, **_kwargs):
        return [self.row]

    async def fetchrow(self, *_args, **_kwargs):
        return self.row

    async def fetchval(self, *_args, **_kwargs):
        return 1

    async def execute(self, *_args, **_kwargs):
        return "DELETE 1"


def _patch_response_models(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "ProjectResponse",
        "ProjectDetailResponse",
        "ProjectListItem",
        "ProjectListResponse",
        "ProjectMemberResponse",
        "ProjectMeetingResponse",
        "ProjectMeetingListItem",
        "ProjectAttachmentResponse",
        "ProjectLinkResponse",
        "ProjectMilestoneResponse",
        "DeliveryScheduleResponse",
    ]:
        monkeypatch.setattr(project, name, _DummyModel)


@pytest.mark.asyncio
async def test_project_service_happy_path_smoke(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _patch_response_models(monkeypatch)
    pid = uuid4()
    aid = uuid4()
    now = datetime.now()
    row = _Row(
        id=pid,
        project_id=pid,
        member_id=uuid4(),
        meeting_id=uuid4(),
        attachment_id=aid,
        link_id=uuid4(),
        milestone_id=uuid4(),
        delivery_id=uuid4(),
        user_id=1,
        username="user1",
        display_name="User One",
        user_username="user1",
        user_display_name="User One",
        name="Demo Project",
        title="Title",
        description="Desc",
        status="active",
        start_date=None,
        end_date=None,
        created_at=now,
        updated_at=now,
        meeting_date=now,
        location="Room",
        attendees=[],
        content="notes",
        created_by="admin",
        filename="file.txt",
        file_type="document",
        file_size=10,
        storage_path=f"{pid}/file.txt",
        uploaded_at=now,
        uploaded_by="admin",
        url="https://example.com",
        milestone_type="custom",
        planned_date=None,
        actual_date=None,
        notes="n",
        sort_order=1,
        vendor="Vendor",
        vendor_id=uuid4(),
        vendor_name="Vendor",
        vendor_erp_code="V001",
        item="Item",
        item_id=uuid4(),
        item_name="Item",
        quantity="1",
        order_date=None,
        expected_delivery_date=None,
        actual_delivery_date=None,
        member_count=1,
        meeting_count=1,
        attachment_count=1,
    )
    conn = _Conn(row)
    monkeypatch.setattr(project, "get_connection", lambda: _CM(conn))

    monkeypatch.setattr(project.settings, "project_attachments_path", str(tmp_path))

    class _DummyFileService:
        def __init__(self):
            self.calls = []

        def write_file(self, path: str, data: bytes) -> None:
            self.calls.append((path, data))

    fs = _DummyFileService()
    monkeypatch.setattr(project, "create_project_file_service", lambda: fs)
    monkeypatch.setattr(project, "_delete_attachment_file", lambda _p: None)

    # 專案 CRUD
    projects = await project.list_projects(status="active", query="Demo")
    assert projects["total"] == 1
    detail = await project.get_project(pid)
    assert detail["id"] == pid
    created = await project.create_project(SimpleNamespace(name="N", description="D", status="active", start_date=None, end_date=None), "u1")
    assert created["name"] == "Demo Project"
    updated = await project.update_project(pid, SimpleNamespace(name="N2", description=None, status=None, start_date=None, end_date=None))
    assert updated["name"] == "Demo Project"
    await project.delete_project(pid)

    # 成員
    assert len(await project.list_members(pid)) == 1
    member = await project.create_member(
        pid,
        SimpleNamespace(name="M", role=None, company=None, email=None, phone=None, notes=None, is_internal=True, user_id=1),
    )
    assert member["name"] == "Demo Project"
    await project.update_member(pid, uuid4(), SimpleNamespace(name="M2", role=None, company=None, email=None, phone=None, notes=None, is_internal=None, user_id=None))
    await project.delete_member(pid, uuid4())

    # 會議
    assert len(await project.list_meetings(pid)) == 1
    await project.get_meeting(pid, uuid4())
    await project.create_meeting(pid, SimpleNamespace(title="T", meeting_date=now, location=None, attendees=[], content=None), "u1")
    await project.update_meeting(pid, uuid4(), SimpleNamespace(title="U", meeting_date=now, location=None, attendees=None, content=None))
    await project.delete_meeting(pid, uuid4())

    # 附件
    assert project._get_file_type("x.pdf") == "pdf"
    assert project._get_file_type("x.jpg") == "image"
    assert project._get_file_type("x.dwg") == "cad"
    assert project._get_file_type("x.docx") == "document"
    assert project._get_file_type("x.bin") == "other"

    await project.list_attachments(pid)
    small = await project.upload_attachment(pid, "small.txt", b"hello", "d", "u1")
    assert small["filename"] == "file.txt"
    large = await project.upload_attachment(pid, "big.bin", b"x" * (1024 * 1024 + 1), "d", "u1")
    assert large["filename"] == "file.txt"
    assert fs.calls  # NAS 分支有被呼叫

    # get_attachment_content：走 LOCAL 分支
    from ching_tech_os.services import path_manager as pm

    local_file = tmp_path / f"{pid}" / "file.txt"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"abc")

    monkeypatch.setattr(pm.path_manager, "parse", lambda _p: SimpleNamespace(zone=pm.StorageZone.LOCAL, path=f"{pid}/file.txt"))
    content, filename = await project.get_attachment_content(pid, aid)
    assert content == b"abc"
    assert filename == "file.txt"

    await project.update_attachment(pid, aid, SimpleNamespace(description="new"))
    await project.delete_attachment(pid, aid)

    # 連結
    assert len(await project.list_links(pid)) == 1
    await project.create_link(pid, SimpleNamespace(title="L", url="https://x", description=None))
    await project.update_link(pid, uuid4(), SimpleNamespace(title="T", url=None, description=None))
    await project.delete_link(pid, uuid4())

    # 里程碑
    assert len(await project.list_milestones(pid)) == 1
    await project.create_milestone(pid, SimpleNamespace(name="M", milestone_type="custom", planned_date=None, actual_date=None, status="pending", notes=None, sort_order=0))
    await project.update_milestone(pid, uuid4(), SimpleNamespace(name="X", milestone_type=None, planned_date=None, actual_date=None, status=None, notes=None, sort_order=None))
    await project.delete_milestone(pid, uuid4())

    # 發包/交貨
    assert len(await project.list_deliveries(pid)) == 1
    await project.create_delivery(
        pid,
        SimpleNamespace(
            vendor=None,
            vendor_id=uuid4(),
            item=None,
            item_id=uuid4(),
            quantity="1",
            order_date=None,
            expected_delivery_date=None,
            status="pending",
            notes=None,
        ),
        "u1",
    )
    await project.update_delivery(
        pid,
        uuid4(),
        SimpleNamespace(
            vendor="V2",
            vendor_id=None,
            item="I2",
            item_id=None,
            quantity="2",
            order_date=None,
            expected_delivery_date=None,
            actual_delivery_date=None,
            status="ordered",
            notes="ok",
        ),
    )
    await project.delete_delivery(pid, uuid4())


@pytest.mark.asyncio
async def test_project_service_not_found_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_response_models(monkeypatch)

    class _ConnNotFound(_Conn):
        async def fetchrow(self, *_args, **_kwargs):
            return None

        async def fetchval(self, *_args, **_kwargs):
            return 0

        async def execute(self, *_args, **_kwargs):
            return "DELETE 0"

    conn = _ConnNotFound(_Row())
    monkeypatch.setattr(project, "get_connection", lambda: _CM(conn))

    with pytest.raises(project.ProjectNotFoundError):
        await project.get_project(uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.update_project(uuid4(), SimpleNamespace(name="x", description=None, status=None, start_date=None, end_date=None))
    with pytest.raises(project.ProjectNotFoundError):
        await project.delete_project(uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.delete_member(uuid4(), uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.get_meeting(uuid4(), uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.delete_meeting(uuid4(), uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.delete_link(uuid4(), uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.delete_milestone(uuid4(), uuid4())
    with pytest.raises(project.ProjectNotFoundError):
        await project.delete_delivery(uuid4(), uuid4())
