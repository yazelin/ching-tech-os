"""knowledge service 測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ching_tech_os.models.knowledge import KnowledgeCreate, KnowledgeTags, KnowledgeUpdate
from ching_tech_os.services import knowledge
from ching_tech_os.services.local_file import LocalFileError


def _setup_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    base = tmp_path / "knowledge"
    entries = base / "entries"
    assets = base / "assets"
    index = base / "index.json"
    entries.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(knowledge, "_get_paths", lambda: (base, entries, assets, index))
    return base, entries, assets, index


def test_knowledge_utils(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _base, entries, _assets, index_path = _setup_paths(monkeypatch, tmp_path)
    assert knowledge._slugify("Hello 世界 -- test") == "hello-世界-test"

    meta, content = knowledge._parse_front_matter("---\ntitle: T\n---\n\nbody")
    assert meta["title"] == "T"
    assert content == "body"
    assert knowledge._parse_front_matter("no fm")[0] == {}
    assert knowledge._parse_front_matter("---\n[\n---\n\nx")[0] == {}

    fm = knowledge._generate_front_matter({"id": "kb-001"})
    assert fm.startswith("---\n")

    idx = knowledge._load_index()
    assert idx.next_id == 1
    idx.next_id = 3
    knowledge._save_index(idx)
    assert index_path.exists()

    index_path.write_text("{bad json}", encoding="utf-8")
    with pytest.raises(knowledge.KnowledgeError):
        knowledge._load_index()

    # _find_knowledge_file
    f = entries / "kb-001-demo.md"
    f.write_text("x", encoding="utf-8")
    assert knowledge._find_knowledge_file("kb-001") == f


def test_knowledge_crud_and_search(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)

    kb = knowledge.create_knowledge(
        KnowledgeCreate(
            title="測試知識",
            content="這是內容 alpha",
            scope="personal",
            tags=KnowledgeTags(projects=["common"], topics=["t1"]),
        ),
        owner="alice",
    )
    assert kb.id.startswith("kb-")
    assert kb.owner == "alice"

    got = knowledge.get_knowledge(kb.id)
    assert got.title == "測試知識"

    class _Result:
        def __init__(self, code: int, out: str):
            self.returncode = code
            self.stdout = out

    def _rg_run(args, **_kwargs):
        target = next(entries.glob(f"{kb.id}-*.md"))
        if "-l" in args:
            return _Result(0, str(target))
        return _Result(0, f"{target}:這是內容 alpha")

    monkeypatch.setattr("subprocess.run", _rg_run)
    res = knowledge.search_knowledge(query="alpha", current_username="alice")
    assert res.total >= 1

    updated = knowledge.update_knowledge(
        kb.id,
        KnowledgeUpdate(
            title="新標題",
            scope="global",
            owner="",
            tags=KnowledgeTags(projects=["common"], topics=["t2"]),
            content="new body",
        ),
    )
    assert updated.title == "新標題"
    assert updated.scope == "global"
    assert updated.owner is None

    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.get_knowledge("kb-999")


@pytest.mark.asyncio
async def test_knowledge_tags_rebuild_history_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)

    (entries / "kb-001-a.md").write_text(
        "---\nid: kb-001\ntitle: A\ntags:\n  topics: [x]\n---\n\nbody",
        encoding="utf-8",
    )
    (entries / "kb-002-bad.md").write_text("---\ntitle: no-id\n---\n\nbody", encoding="utf-8")

    rebuilt = knowledge.rebuild_index()
    assert rebuilt["total"] == 1
    assert rebuilt["next_id"] >= 2
    assert rebuilt["errors"]

    class _Result:
        def __init__(self, code: int, out: str):
            self.returncode = code
            self.stdout = out

    monkeypatch.setattr(
        "subprocess.run",
        lambda args, **_kwargs: _Result(
            0,
            "c1|alice|2024-01-01T00:00:00+00:00|init"
            if "log" in args
            else "---\nid: kb-001\n---\n\nv1",
        ),
    )

    hist = knowledge.get_history("kb-001")
    assert len(hist.entries) == 1
    ver = knowledge.get_version("kb-001", "c1")
    assert ver.content == "v1"

    tags = await knowledge.get_all_tags()
    assert "common" in tags.projects


def test_knowledge_attachments_and_delete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base, entries, assets, _index = _setup_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(knowledge.settings, "ctos_mount_path", str(base))
    monkeypatch.setattr(knowledge.settings, "line_files_nas_path", "linebot/files")

    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="附件測試", content="body", scope="global"),
        owner=None,
    )

    # local attachment
    att_local = knowledge.upload_attachment(kb.id, "a.png", b"1234", "img")
    assert att_local.path.startswith("local://")
    assert (assets / "images").exists()

    # NAS attachment
    fake_knowledge_fs = SimpleNamespace(
        write_file=lambda _p, _d: None,
        read_file=lambda _p: b"nas",
        delete_file=lambda _p: None,
        delete_directory=lambda _p: None,
    )
    monkeypatch.setattr(knowledge, "create_knowledge_file_service", lambda: fake_knowledge_fs)
    att_nas = knowledge.upload_attachment(kb.id, "b.bin", b"x" * (1024 * 1024), "bin")
    assert att_nas.path.startswith("ctos://knowledge/")
    assert knowledge.get_nas_attachment("x.bin") == b"nas"

    monkeypatch.setattr(
        knowledge,
        "create_linebot_file_service",
        lambda: SimpleNamespace(read_file=lambda _p: b"linebot"),
    )
    copied = knowledge.copy_linebot_attachment_to_knowledge(kb.id, "groups/g1/images/a.jpg")
    assert copied.path

    # fallback ai-presentations
    ai_p = base / "ai-presentations" / "a.html"
    ai_p.parent.mkdir(parents=True, exist_ok=True)
    ai_p.write_bytes(b"<html/>")
    copied2 = knowledge.copy_linebot_attachment_to_knowledge(kb.id, "ctos://ai-presentations/a.html")
    assert copied2.path

    # update/delete attachment metadata
    updated_att = knowledge.update_attachment(kb.id, 0, description="new", attachment_type="document")
    assert updated_att.description == "new"
    knowledge.delete_attachment(kb.id, 0)

    # delete knowledge with attachments cleanup
    knowledge.delete_knowledge(kb.id)
    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.get_knowledge(kb.id)


def test_knowledge_error_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _base, _entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.update_attachment("kb-404", 0)
    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.delete_attachment("kb-404", 0)

    monkeypatch.setattr(
        knowledge,
        "create_knowledge_file_service",
        lambda: SimpleNamespace(read_file=lambda _p: (_ for _ in ()).throw(LocalFileError("x"))),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.get_nas_attachment("x")

    monkeypatch.setattr(
        knowledge,
        "create_linebot_file_service",
        lambda: SimpleNamespace(read_file=lambda _p: (_ for _ in ()).throw(LocalFileError("x"))),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.copy_linebot_attachment_to_knowledge("kb-001", "groups/x.jpg")
