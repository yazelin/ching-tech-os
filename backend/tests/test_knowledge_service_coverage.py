"""knowledge service 補充覆蓋率測試。

針對 test_knowledge_service.py 未觸及的分支：
錯誤處理、搜尋過濾、scope 權限、附件處理、版本歷史等。
所有測試皆為 hermetic：檔案操作走 tmp_path、subprocess 與 NAS 服務全部 mock。
"""

from __future__ import annotations

import builtins
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ching_tech_os.models.knowledge import (
    IndexEntry,
    KnowledgeCreate,
    KnowledgeIndex,
    KnowledgeSource,
    KnowledgeTags,
    KnowledgeUpdate,
)
from ching_tech_os.services import knowledge
from ching_tech_os.services.local_file import LocalFileError


def _setup_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """把知識庫路徑導向 tmp_path，避免碰到真實資料。"""
    base = tmp_path / "knowledge"
    entries = base / "entries"
    assets = base / "assets"
    index = base / "index.json"
    entries.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(knowledge, "_get_paths", lambda: (base, entries, assets, index))
    return base, entries, assets, index


def _write_entry(entries: Path, filename: str, front_matter: str, body: str = "body") -> Path:
    """直接寫入一個知識 markdown 檔。"""
    f = entries / filename
    f.write_text(f"---\n{front_matter}---\n\n{body}", encoding="utf-8")
    return f


class _Result:
    """模擬 subprocess.run 的回傳物件。"""

    def __init__(self, code: int, out: str):
        self.returncode = code
        self.stdout = out


# ---------------------------------------------------------------------------
# 基礎工具函式
# ---------------------------------------------------------------------------


def test_get_paths_from_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """_get_paths 應從 settings.knowledge_data_path 組出四個路徑。"""
    monkeypatch.setattr(knowledge.settings, "knowledge_data_path", str(tmp_path / "kbdata"))
    base, entries, assets, index = knowledge._get_paths()
    assert base == tmp_path / "kbdata"
    assert entries == base / "entries"
    assert assets == base / "assets"
    assert index == base / "index.json"


def test_save_index_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """index.json 是目錄時，儲存索引應拋出 KnowledgeError。"""
    _base, _entries, _assets, index_path = _setup_paths(monkeypatch, tmp_path)
    index_path.mkdir()  # 讓 open(..., "w") 失敗
    with pytest.raises(knowledge.KnowledgeError):
        knowledge._save_index(KnowledgeIndex())


def test_parse_front_matter_without_closing() -> None:
    """front matter 沒有結尾 --- 時，應原樣回傳內容。"""
    raw = "---\ntitle: 未閉合"
    meta, content = knowledge._parse_front_matter(raw)
    assert meta == {}
    assert content == raw


# ---------------------------------------------------------------------------
# get_knowledge
# ---------------------------------------------------------------------------


def test_get_knowledge_with_attachments_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """讀取含附件與字串日期的知識，應正確轉成回應物件。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(
        entries,
        "kb-050-att.md",
        (
            "id: kb-050\n"
            "title: 附件知識\n"
            "attachments:\n"
            "  - type: image\n"
            "    path: local://knowledge/assets/images/kb-050-a.png\n"
            "    size: 1.0KB\n"
            "    description: 圖片\n"
            "created_at: '2024-01-02'\n"
            "updated_at: '2024-01-03'\n"
        ),
    )
    kb = knowledge.get_knowledge("kb-050")
    assert len(kb.attachments) == 1
    assert kb.attachments[0].type == "image"
    assert kb.created_at.isoformat() == "2024-01-02"


def test_get_knowledge_not_found_reraise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """讀取過程中拋出的 KnowledgeNotFoundError 應原樣傳遞，不被包裝。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(entries, "kb-052-r.md", "id: kb-052\ntitle: R\n")
    monkeypatch.setattr(
        knowledge,
        "_parse_front_matter",
        lambda _c: (_ for _ in ()).throw(knowledge.KnowledgeNotFoundError("不見了")),
    )
    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.get_knowledge("kb-052")


def test_get_knowledge_read_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """日期格式錯誤導致解析失敗時，應包成 KnowledgeError。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(entries, "kb-051-bad.md", "id: kb-051\ntitle: 壞日期\ncreated_at: 'not-a-date'\n")
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.get_knowledge("kb-051")


# ---------------------------------------------------------------------------
# search_knowledge 過濾分支
# ---------------------------------------------------------------------------


def _build_search_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """建立含各種 scope / 標籤組合的索引供搜尋測試用。"""
    _setup_paths(monkeypatch, tmp_path)
    index = KnowledgeIndex(next_id=200)
    index.entries = [
        IndexEntry(
            id="kb-101",
            title="全域公開",
            filename="kb-101-a.md",
            type="knowledge",
            category="technical",
            scope="global",
            is_public=True,
            tags=KnowledgeTags(projects=["p1"], roles=["dev"], topics=["t1"], level="L1"),
            author="x",
            created_at="2024-01-01",
            updated_at="2024-01-04",
        ),
        IndexEntry(
            id="kb-102",
            title="alice 個人",
            filename="kb-102-b.md",
            type="knowledge",
            category="technical",
            scope="personal",
            owner="alice",
            tags=KnowledgeTags(topics=["t1"]),
            author="alice",
            created_at="2024-01-01",
            updated_at="2024-01-03",
        ),
        IndexEntry(
            id="kb-103",
            title="bob 個人",
            filename="kb-103-c.md",
            type="knowledge",
            category="technical",
            scope="personal",
            owner="bob",
            tags=KnowledgeTags(topics=["t1"]),
            author="bob",
            created_at="2024-01-01",
            updated_at="2024-01-02",
        ),
        IndexEntry(
            id="kb-104",
            title="全域非公開",
            filename="kb-104-d.md",
            type="context",
            category="ops",
            scope="global",
            is_public=False,
            tags=KnowledgeTags(projects=["p2"], roles=["qa"], topics=["t2"], level="L2"),
            author="x",
            created_at="2024-01-01",
            updated_at="2024-01-01",
        ),
    ]
    knowledge._save_index(index)


def test_search_scope_and_public_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """scope / public_only / 預設可見範圍的過濾邏輯。"""
    _build_search_index(monkeypatch, tmp_path)

    # scope=global：個人知識全部排除
    res = knowledge.search_knowledge(scope="global", current_username="alice")
    assert {i.id for i in res.items} == {"kb-101", "kb-104"}

    # scope=personal：只看到自己的個人知識
    res = knowledge.search_knowledge(scope="personal", current_username="alice")
    assert {i.id for i in res.items} == {"kb-102"}

    # 預設：全域 + 自己的個人知識（bob 的被排除）
    res = knowledge.search_knowledge(current_username="alice")
    assert {i.id for i in res.items} == {"kb-101", "kb-102", "kb-104"}

    # public_only：僅 global 且 is_public
    res = knowledge.search_knowledge(public_only=True)
    assert {i.id for i in res.items} == {"kb-101"}


def test_search_tag_filters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """project / type / category / role / level / topics 過濾。"""
    _build_search_index(monkeypatch, tmp_path)

    assert {i.id for i in knowledge.search_knowledge(project="p1").items} == {"kb-101"}
    res = knowledge.search_knowledge(kb_type="context")
    assert {i.id for i in res.items} == {"kb-104"}
    res = knowledge.search_knowledge(category="ops")
    assert {i.id for i in res.items} == {"kb-104"}
    res = knowledge.search_knowledge(role="qa")
    assert {i.id for i in res.items} == {"kb-104"}
    res = knowledge.search_knowledge(level="L2")
    assert {i.id for i in res.items} == {"kb-104"}
    res = knowledge.search_knowledge(topics=["t2"], current_username="alice")
    assert {i.id for i in res.items} == {"kb-104"}


def test_search_multi_term_intersection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """多詞查詢應取交集，且附上匹配片段。"""
    _build_search_index(monkeypatch, tmp_path)

    def _rg_run(args, **_kwargs):
        if "-l" in args:
            term = args[-2]
            if term == "alpha":
                return _Result(0, "/x/kb-101-a.md\n/x/kb-104-d.md")
            return _Result(0, "/x/kb-101-a.md")  # beta 只匹配 kb-101
        # 取得片段（-C 模式）
        return _Result(0, "/x/kb-101-a.md:內容片段 alpha")

    monkeypatch.setattr("subprocess.run", _rg_run)
    res = knowledge.search_knowledge(query="alpha beta", current_username="alice")
    assert {i.id for i in res.items} == {"kb-101"}
    assert res.items[0].snippet is not None


def test_search_ripgrep_errors_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ripgrep 逾時或未安裝時，應回退為列出全部可見知識。"""
    _build_search_index(monkeypatch, tmp_path)

    def _timeout(args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="rg", timeout=10)

    monkeypatch.setattr("subprocess.run", _timeout)
    res = knowledge.search_knowledge(query="alpha", current_username="alice")
    assert res.total == 3  # 回退為預設可見範圍

    def _missing(args, **_kwargs):
        raise FileNotFoundError("rg not found")

    monkeypatch.setattr("subprocess.run", _missing)
    res = knowledge.search_knowledge(query="alpha", current_username="alice")
    assert res.total == 3


# ---------------------------------------------------------------------------
# create / update / delete
# ---------------------------------------------------------------------------


def test_create_knowledge_slug_fallback_and_collision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """標題無法 slug 化時用預設 slug；slug 重複時自動加序號。"""
    _setup_paths(monkeypatch, tmp_path)

    # 標題只有符號，slugify 後為空字串 → 走 fallback
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="!!!", content="c", scope="global"), owner=None
    )
    assert "knowledge-" in knowledge._find_knowledge_file(kb.id).name

    # 相同 slug 建立兩次 → 第二次自動加 -2
    kb1 = knowledge.create_knowledge(
        KnowledgeCreate(title="A", slug="dup", content="c", scope="global"), owner=None
    )
    kb2 = knowledge.create_knowledge(
        KnowledgeCreate(title="B", slug="dup", content="c", scope="global"), owner=None
    )
    assert knowledge._find_knowledge_file(kb1.id).name.endswith("-dup.md")
    assert knowledge._find_knowledge_file(kb2.id).name.endswith("-dup-2.md")


def test_create_knowledge_write_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """entries 路徑被檔案佔用導致無法建目錄時，應拋 KnowledgeError。"""
    base = tmp_path / "knowledge"
    base.mkdir()
    entries = base / "entries"
    entries.write_text("我是檔案不是目錄", encoding="utf-8")
    monkeypatch.setattr(
        knowledge,
        "_get_paths",
        lambda: (base, entries, base / "assets", base / "index.json"),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.create_knowledge(
            KnowledgeCreate(title="X", content="c", scope="global"), owner=None
        )


def test_update_knowledge_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """更新不存在的知識應拋 KnowledgeNotFoundError。"""
    _setup_paths(monkeypatch, tmp_path)
    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.update_knowledge("kb-404", KnowledgeUpdate(title="x"))


def test_update_knowledge_all_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """更新 type / category / source / related / is_public 等欄位。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="原始", content="c", scope="global"), owner=None
    )
    updated = knowledge.update_knowledge(
        kb.id,
        KnowledgeUpdate(
            type="reference",
            category="ops",
            source=KnowledgeSource(project="proj", path="a/b.py", commit="abc123"),
            related=["kb-001"],
            is_public=True,
        ),
    )
    assert updated.type == "reference"
    assert updated.category == "ops"
    assert updated.source.project == "proj"
    assert updated.related == ["kb-001"]
    assert updated.is_public is True


def test_update_knowledge_read_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """讀取知識內容失敗時，應包成 KnowledgeError。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="讀失敗", content="c", scope="global"), owner=None
    )
    monkeypatch.setattr(
        knowledge,
        "_parse_front_matter",
        lambda _c: (_ for _ in ()).throw(RuntimeError("parse fail")),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.update_knowledge(kb.id, KnowledgeUpdate(title="x"))


def test_update_knowledge_write_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """寫回知識檔失敗時，應包成 KnowledgeError。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="寫失敗", content="c", scope="global"), owner=None
    )

    real_open = builtins.open

    def _fake_open(file, mode="r", *args, **kwargs):
        # 只擋 .md 檔的寫入，讀取與 index.json 照常
        if "w" in mode and str(file).endswith(".md"):
            raise OSError("磁碟已滿")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _fake_open)
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.update_knowledge(kb.id, KnowledgeUpdate(title="x"))


def test_delete_knowledge_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """刪除不存在的知識應拋 KnowledgeNotFoundError。"""
    _setup_paths(monkeypatch, tmp_path)
    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.delete_knowledge("kb-404")


def test_delete_knowledge_ignores_attachment_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """附件與目錄刪除失敗不應阻止知識刪除。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(
        entries,
        "kb-060-x.md",
        (
            "id: kb-060\n"
            "title: 待刪\n"
            "attachments:\n"
            "  - type: file\n"
            "    path: ctos://knowledge/attachments/kb-060/f.bin\n"
            "    size: 2.0MB\n"
        ),
    )
    index = KnowledgeIndex(next_id=61)
    index.entries = [
        IndexEntry(
            id="kb-060",
            title="待刪",
            filename="kb-060-x.md",
            type="knowledge",
            category="technical",
            tags=KnowledgeTags(),
            author="x",
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )
    ]
    knowledge._save_index(index)

    def _raise(*_a, **_k):
        raise LocalFileError("NAS 掛了")

    monkeypatch.setattr(
        knowledge,
        "create_knowledge_file_service",
        lambda: SimpleNamespace(delete_file=_raise, delete_directory=_raise),
    )
    knowledge.delete_knowledge("kb-060")  # 不應拋出例外
    assert knowledge._find_knowledge_file("kb-060") is None


def test_delete_knowledge_unlink_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """知識檔本體刪除失敗時，應拋 KnowledgeError。"""
    _setup_paths(monkeypatch, tmp_path)
    ghost = tmp_path / "knowledge" / "entries" / "kb-070-ghost.md"
    # 檔案不存在：讀附件失敗（走空附件分支）、unlink 也會失敗
    monkeypatch.setattr(knowledge, "_find_knowledge_file", lambda _id: ghost)
    monkeypatch.setattr(
        knowledge,
        "create_knowledge_file_service",
        lambda: SimpleNamespace(delete_file=lambda _p: None, delete_directory=lambda _p: None),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.delete_knowledge("kb-070")


# ---------------------------------------------------------------------------
# rebuild_index / get_history / get_version
# ---------------------------------------------------------------------------


def test_rebuild_index_records_parse_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """欄位驗證失敗的檔案應記入 errors，不中斷重建。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(entries, "kb-001-ok.md", "id: kb-001\ntitle: 正常\n")
    # tags.projects 型別錯誤 → pydantic 驗證失敗
    _write_entry(entries, "kb-002-broken.md", "id: kb-002\ntitle: 壞\ntags:\n  projects: 5\n")

    result = knowledge.rebuild_index()
    assert result["total"] == 1
    assert any("kb-002-broken.md" in e for e in result["errors"])


def test_get_history_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """get_history：不存在、空行/壞行、逾時、一般例外。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)

    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.get_history("kb-404")

    _write_entry(entries, "kb-080-h.md", "id: kb-080\ntitle: H\n")

    # 輸出含空行與欄位不足的行，應被略過
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: _Result(0, "c1|alice|2024-01-01T00:00:00+00:00|init\n\n壞行"),
    )
    hist = knowledge.get_history("kb-080")
    assert len(hist.entries) == 1

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr("subprocess.run", _timeout)
    assert knowledge.get_history("kb-080").entries == []

    def _boom(*_a, **_k):
        raise OSError("git 壞了")

    monkeypatch.setattr("subprocess.run", _boom)
    assert knowledge.get_history("kb-080").entries == []


def test_get_version_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """get_version：不存在、git 失敗、逾時、一般例外。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)

    with pytest.raises(knowledge.KnowledgeNotFoundError):
        knowledge.get_version("kb-404", "c1")

    _write_entry(entries, "kb-081-v.md", "id: kb-081\ntitle: V\n")

    # git show 回傳非 0 → 無法取得版本
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Result(1, ""))
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.get_version("kb-081", "c1")

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr("subprocess.run", _timeout)
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.get_version("kb-081", "c1")

    def _boom(*_a, **_k):
        raise OSError("git 壞了")

    monkeypatch.setattr("subprocess.run", _boom)
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.get_version("kb-081", "c1")


# ---------------------------------------------------------------------------
# 附件處理
# ---------------------------------------------------------------------------


def test_upload_attachment_file_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """影片與文件副檔名應對應 video / document 類型。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="類型", content="c", scope="global"), owner=None
    )
    assert knowledge.upload_attachment(kb.id, "clip.mp4", b"v").type == "video"
    assert knowledge.upload_attachment(kb.id, "doc.pdf", b"d").type == "document"


def test_upload_attachment_nas_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """大檔上傳 NAS 失敗時，應拋 KnowledgeError。"""
    _setup_paths(monkeypatch, tmp_path)

    def _raise(*_a, **_k):
        raise LocalFileError("寫入失敗")

    monkeypatch.setattr(
        knowledge,
        "create_knowledge_file_service",
        lambda: SimpleNamespace(write_file=_raise),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.upload_attachment("kb-001", "big.bin", b"x" * (1024 * 1024))


def test_upload_attachment_creates_attachments_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """front matter 沒有 attachments 欄位時，上傳後應自動建立。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(entries, "kb-090-noatt.md", "id: kb-090\ntitle: 無附件欄\n")

    att = knowledge.upload_attachment("kb-090", "a.png", b"123")
    assert att.type == "image"
    kb = knowledge.get_knowledge("kb-090")
    assert len(kb.attachments) == 1


def test_upload_attachment_metadata_update_failure_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """更新知識元資料失敗不應影響附件上傳結果。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="忽略錯誤", content="c", scope="global"), owner=None
    )
    monkeypatch.setattr(
        knowledge,
        "_generate_front_matter",
        lambda _m: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    att = knowledge.upload_attachment(kb.id, "a.png", b"123")
    assert att.path.startswith("local://")


def test_copy_linebot_uri_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ctos://linebot/files/ 前綴應被移除後再讀取。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="Line 附件", content="c", scope="global"), owner=None
    )
    seen: list[str] = []

    def _read(path: str) -> bytes:
        seen.append(path)
        return b"img"

    monkeypatch.setattr(
        knowledge, "create_linebot_file_service", lambda: SimpleNamespace(read_file=_read)
    )
    att = knowledge.copy_linebot_attachment_to_knowledge(
        kb.id, "ctos://linebot/files/groups/g1/images/a.jpg"
    )
    assert seen == ["groups/g1/images/a.jpg"]
    assert att.path


def test_copy_linebot_presentation_read_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ai-presentations 檔案不存在時，應改走 linebot 服務讀取。"""
    _setup_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(knowledge.settings, "ctos_mount_path", str(tmp_path / "mount"))
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="簡報", content="c", scope="global"), owner=None
    )
    monkeypatch.setattr(
        knowledge,
        "create_linebot_file_service",
        lambda: SimpleNamespace(read_file=lambda _p: b"html"),
    )
    att = knowledge.copy_linebot_attachment_to_knowledge(
        kb.id, "ctos://ai-presentations/missing.html"
    )
    assert att.path


def test_copy_linebot_ai_images_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """linebot 服務讀不到 ai-images 時，應 fallback 到舊共用路徑。"""
    _setup_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(knowledge.settings, "ctos_mount_path", str(tmp_path / "mount"))
    monkeypatch.setattr(knowledge.settings, "line_files_nas_path", "linebot/files")
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="AI 圖", content="c", scope="global"), owner=None
    )

    def _raise(_p):
        raise LocalFileError("讀取失敗")

    monkeypatch.setattr(
        knowledge, "create_linebot_file_service", lambda: SimpleNamespace(read_file=_raise)
    )

    # fallback 檔案存在 → 成功
    fallback = tmp_path / "mount" / "linebot" / "files" / "ai-images" / "x.jpg"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    fallback.write_bytes(b"jpg")
    att = knowledge.copy_linebot_attachment_to_knowledge(kb.id, "ai-images/x.jpg")
    assert att.path

    # fallback 檔案不存在 → KnowledgeError
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.copy_linebot_attachment_to_knowledge(kb.id, "ai-images/missing.jpg")


def test_update_attachment_error_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """附件索引超出範圍與一般例外的錯誤處理。"""
    _setup_paths(monkeypatch, tmp_path)
    kb = knowledge.create_knowledge(
        KnowledgeCreate(title="附件更新", content="c", scope="global"), owner=None
    )
    knowledge.upload_attachment(kb.id, "a.png", b"1")

    with pytest.raises(knowledge.KnowledgeError):
        knowledge.update_attachment(kb.id, 5, description="超出範圍")

    monkeypatch.setattr(
        knowledge,
        "_generate_front_matter",
        lambda _m: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.update_attachment(kb.id, 0, description="一般例外")


def test_delete_attachment_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """刪除附件：索引超出範圍、NAS 刪除失敗、路徑解析失敗、一般例外。"""
    _base, entries, _assets, _index = _setup_paths(monkeypatch, tmp_path)
    _write_entry(
        entries,
        "kb-095-d.md",
        (
            "id: kb-095\n"
            "title: 刪附件\n"
            "attachments:\n"
            "  - type: file\n"
            "    path: ctos://knowledge/attachments/kb-095/f.bin\n"
            "    size: 2.0MB\n"
            "  - type: file\n"
            "    path: ''\n"
            "    size: 1.0KB\n"
        ),
    )

    with pytest.raises(knowledge.KnowledgeError):
        knowledge.delete_attachment("kb-095", 9)

    # NAS 刪除失敗應被忽略，附件參考仍被移除
    def _raise(_p):
        raise LocalFileError("刪除失敗")

    monkeypatch.setattr(
        knowledge,
        "create_knowledge_file_service",
        lambda: SimpleNamespace(delete_file=_raise),
    )
    knowledge.delete_attachment("kb-095", 0)
    assert len(knowledge.get_knowledge("kb-095").attachments) == 1

    # 空路徑：path_manager.parse 失敗應被忽略，仍可刪除參考
    knowledge.delete_attachment("kb-095", 0)
    assert knowledge.get_knowledge("kb-095").attachments == []

    # 一般例外 → 包成 KnowledgeError
    _write_entry(
        entries,
        "kb-096-e.md",
        (
            "id: kb-096\n"
            "title: 例外\n"
            "attachments:\n"
            "  - type: file\n"
            "    path: ''\n"
        ),
    )
    monkeypatch.setattr(
        knowledge,
        "_generate_front_matter",
        lambda _m: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.delete_attachment("kb-096", 0)
