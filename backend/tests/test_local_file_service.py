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


def test_io_permission_error_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LocalFileService(str(tmp_path))
    _disable_mount_check(service, monkeypatch)
    original_mkdir = local_file.Path.mkdir

    src = tmp_path / "src.txt"
    src.write_bytes(b"src")
    dst = tmp_path / "dst.txt"

    # read_file PermissionError / IOError
    def _raise_permission(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("builtins.open", _raise_permission)
    with pytest.raises(LocalFileError, match="無權限讀取檔案"):
        service.read_file("src.txt")

    def _raise_io(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", _raise_io)
    with pytest.raises(LocalFileError, match="讀取檔案失敗"):
        service.read_file("src.txt")

    # write_file PermissionError / IOError
    monkeypatch.setattr("builtins.open", _raise_permission)
    with pytest.raises(LocalFileError, match="無權限寫入檔案"):
        service.write_file("write.txt", b"x")

    monkeypatch.setattr("builtins.open", _raise_io)
    with pytest.raises(LocalFileError, match="寫入檔案失敗"):
        service.write_file("write.txt", b"x")

    # delete_file PermissionError / IOError
    monkeypatch.setattr(local_file.Path, "unlink", lambda _p: (_ for _ in ()).throw(PermissionError("nope")))
    with pytest.raises(LocalFileError, match="無權限刪除檔案"):
        service.delete_file("src.txt")

    monkeypatch.setattr(local_file.Path, "unlink", lambda _p: (_ for _ in ()).throw(OSError("fail")))
    with pytest.raises(LocalFileError, match="刪除檔案失敗"):
        service.delete_file("src.txt")

    # delete_directory: 目錄不存在
    with pytest.raises(LocalFileError, match="目錄不存在"):
        service.delete_directory("not-dir")

    # create_directory PermissionError / IOError
    monkeypatch.setattr(local_file.Path, "mkdir", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("deny")))
    with pytest.raises(LocalFileError, match="無權限建立目錄"):
        service.create_directory("x")

    monkeypatch.setattr(local_file.Path, "mkdir", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("io")))
    with pytest.raises(LocalFileError, match="建立目錄失敗"):
        service.create_directory("x")

    # copy/move PermissionError / IOError
    monkeypatch.setattr(local_file.Path, "mkdir", original_mkdir)
    monkeypatch.setattr(local_file.shutil, "copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("deny")))
    with pytest.raises(LocalFileError, match="無權限複製檔案"):
        service.copy_file("src.txt", "copy.txt")

    monkeypatch.setattr(local_file.shutil, "copy2", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("io")))
    with pytest.raises(LocalFileError, match="複製檔案失敗"):
        service.copy_file("src.txt", "copy.txt")

    monkeypatch.setattr(local_file.shutil, "move", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("deny")))
    with pytest.raises(LocalFileError, match="無權限移動檔案"):
        service.move_file("src.txt", str(dst))

    monkeypatch.setattr(local_file.shutil, "move", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("io")))
    with pytest.raises(LocalFileError, match="移動檔案失敗"):
        service.move_file("src.txt", str(dst))
