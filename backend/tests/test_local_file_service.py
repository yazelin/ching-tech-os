"""LocalFileService 單元測試。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ching_tech_os.services import local_file
from ching_tech_os.services.local_file import LocalFileError, LocalFileService


def _disable_mount_check(service: LocalFileService, monkeypatch: pytest.MonkeyPatch) -> None:
    """測試檔案操作時停用掛載檢查，避免依賴真實 NAS 環境。"""
    monkeypatch.setattr(service, "_ensure_mount", lambda: None)


def test_file_roundtrip_and_copy_move_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    _disable_mount_check(service, monkeypatch)

    service.write_file("docs/a.txt", b"hello")
    assert service.read_file("/docs/a.txt") == b"hello"
    assert service.exists("docs/a.txt") is True
    assert service.is_file("docs/a.txt") is True
    assert service.is_directory("docs/a.txt") is False
    assert service.get_full_path("docs/a.txt").endswith("docs/a.txt")

    service.copy_file("docs/a.txt", "docs/b.txt")
    service.move_file("docs/b.txt", "docs/sub/c.txt")
    assert service.read_file("docs/sub/c.txt") == b"hello"

    service.delete_file("docs/sub/c.txt")
    assert service.exists("docs/sub/c.txt") is False


def test_directory_create_list_and_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    _disable_mount_check(service, monkeypatch)

    service.create_directory("folder")
    service.write_file("folder/file.txt", b"abc")

    items = service.list_directory("folder")
    by_name = {item["name"]: item for item in items}
    assert "file.txt" in by_name
    assert by_name["file.txt"]["type"] == "file"
    assert by_name["file.txt"]["size"] == 3
    assert isinstance(by_name["file.txt"]["modified"], str)

    with pytest.raises(LocalFileError, match="目錄不是空的"):
        service.delete_directory("folder")

    service.delete_directory("folder", recursive=True)
    assert service.exists("folder") is False


def test_local_file_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    _disable_mount_check(service, monkeypatch)
    service.create_directory("dir-only")

    with pytest.raises(LocalFileError, match="檔案不存在"):
        service.read_file("missing.txt")
    with pytest.raises(LocalFileError, match="路徑是目錄"):
        service.delete_file("dir-only")
    with pytest.raises(LocalFileError, match="檔案不存在"):
        service.delete_file("missing.txt")
    with pytest.raises(LocalFileError, match="目錄不存在"):
        service.list_directory("missing")
    with pytest.raises(LocalFileError, match="來源檔案不存在"):
        service.copy_file("missing.txt", "x.txt")
    with pytest.raises(LocalFileError, match="來源檔案不存在"):
        service.move_file("missing.txt", "x.txt")


def test_ensure_mount_detects_missing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path / "does-not-exist"))
    monkeypatch.setattr(local_file.Path, "is_mount", lambda _: False)

    with pytest.raises(LocalFileError, match="NAS 路徑不存在"):
        service._ensure_mount()


def test_ensure_mount_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    original_iterdir = local_file.Path.iterdir
    monkeypatch.setattr(local_file.Path, "is_mount", lambda _: False)

    def _iterdir_with_permission_error(path: Path):
        if path == service.base_path:
            raise PermissionError("denied")
        return original_iterdir(path)

    monkeypatch.setattr(local_file.Path, "iterdir", _iterdir_with_permission_error)

    with pytest.raises(LocalFileError, match="無法存取 NAS 路徑"):
        service._ensure_mount()


def test_ensure_mount_accepts_mountpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    monkeypatch.setattr(local_file.Path, "is_mount", lambda path: path == service.base_path)
    service._ensure_mount()


def test_list_directory_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    _disable_mount_check(service, monkeypatch)
    original_iterdir = local_file.Path.iterdir

    def _iterdir_with_permission_error(path: Path):
        if path == service.base_path:
            raise PermissionError("denied")
        return original_iterdir(path)

    monkeypatch.setattr(local_file.Path, "iterdir", _iterdir_with_permission_error)

    with pytest.raises(LocalFileError, match="無權限存取目錄"):
        service.list_directory()


def test_factory_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_file.settings, "ctos_mount_path", "/mnt/nas/ctos-test")
    monkeypatch.setattr(local_file.settings, "knowledge_nas_path", "knowledge-x")
    monkeypatch.setattr(local_file.settings, "project_nas_path", "projects-x")
    monkeypatch.setattr(local_file.settings, "line_files_nas_path", "linebot-x")

    assert str(local_file.create_knowledge_file_service().base_path) == "/mnt/nas/ctos-test/knowledge-x"
    assert str(local_file.create_project_file_service().base_path) == "/mnt/nas/ctos-test/projects-x"
    assert str(local_file.create_linebot_file_service().base_path) == "/mnt/nas/ctos-test/linebot-x"
    assert str(local_file.create_attachments_file_service().base_path) == "/mnt/nas/ctos-test/attachments"
    assert str(local_file.create_ai_generated_file_service().base_path) == "/mnt/nas/ctos-test/ai-generated"
