"""SMB service 測試。"""

from __future__ import annotations

import stat as stat_module
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ching_tech_os.services import smb as smb_module


class _V:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value


class _FakeConnection:
    def __init__(self, *_args, **_kwargs):
        self.connected = False

    def connect(self, timeout=None):
        if timeout == -1:
            raise TimeoutError()
        self.connected = True

    def disconnect(self):
        self.connected = False


class _FakeSession:
    def __init__(self, _conn, username, password):
        self.username = username
        self.password = password
        self.connected = False

    def connect(self):
        if self.password == "bad":
            raise RuntimeError("logon failed")
        self.connected = True

    def disconnect(self):
        self.connected = False


class _FakeTree:
    def __init__(self, _session, unc: str):
        self.unc = unc
        self.connected = False

    def connect(self):
        if "deny" in self.unc:
            raise RuntimeError("access denied")
        self.connected = True

    def disconnect(self):
        self.connected = False


def _patch_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _FakeSession)
    monkeypatch.setattr(smb_module, "TreeConnect", _FakeTree)


def test_smb_connect_auth_and_test_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_core(monkeypatch)

    svc = smb_module.SMBService("host", "u", "p", connect_timeout=2, auth_share="ok")
    assert svc.test_auth() is True

    with pytest.raises(smb_module.SMBAuthError):
        smb_module.SMBService("host", "u", "bad").test_auth()

    with pytest.raises(smb_module.SMBConnectionError):
        smb_module.SMBService("host", "u", "p", connect_timeout=-1).test_auth()

    with pytest.raises(smb_module.SMBAuthError):
        smb_module.SMBService("host", "u", "p", auth_share="deny-share").test_auth()


def test_smb_list_shares(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        def __init__(self, code, out="", err=""):
            self.returncode = code
            self.stdout = out
            self.stderr = err

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_a, **_k: _Result(0, "Disk|docs|x\nDisk|IPC$|x\nPrinter|p|x\n"),
    )
    svc = smb_module.SMBService("h", "u", "p")
    assert svc.list_shares() == [{"name": "docs", "type": "disk"}]

    monkeypatch.setattr("subprocess.run", lambda *_a, **_k: _Result(1, err="err"))
    with pytest.raises(smb_module.SMBError):
        svc.list_shares()


def test_smb_browse_read_write(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_core(monkeypatch)

    class _Open:
        def __init__(self, _tree, path):
            self.path = path
            self.end_of_file = 7
            self._writes = []

        def create(self, *_args, **_kwargs):
            return None

        def query_directory(self, *_args, **_kwargs):
            return [
                {
                    "file_name": _V("a.txt"),
                    "file_attributes": _V(0),
                    "end_of_file": _V(3),
                    "last_write_time": _V(datetime(2024, 1, 1)),
                },
                {
                    "file_name": _V("dir".encode("utf-16-le")),
                    "file_attributes": _V(smb_module.FileAttributes.FILE_ATTRIBUTE_DIRECTORY),
                    "end_of_file": _V(0),
                    "last_write_time": _V(116444736000000000 + 2 * 10_000_000),
                },
            ]

        def read(self, offset, size):
            content = b"abcdefg"
            return content[offset:offset + size]

        def write(self, chunk, offset):
            self._writes.append((offset, chunk))

        def close(self):
            return None

    monkeypatch.setattr(smb_module, "Open", _Open)

    svc = smb_module.SMBService("h", "u", "p")
    svc._connection = _FakeConnection()
    svc._session = _FakeSession(svc._connection, "u", "p")

    items = svc.browse_directory("share", "/")
    assert items[0]["name"] == "a.txt"
    assert items[1]["type"] == "directory"

    data = svc.read_file("share", "/a.txt")
    assert data == b"abcdefg"

    svc.write_file("share", "/b.bin", b"123456")

    with pytest.raises(smb_module.SMBPermissionError):
        class _OpenDenied(_Open):
            def read(self, *_a):
                raise RuntimeError("access denied")

        monkeypatch.setattr(smb_module, "Open", _OpenDenied)
        svc.read_file("share", "/a.txt")

    with pytest.raises(smb_module.SMBFileNotFoundError):
        class _OpenMissing(_Open):
            def read(self, *_a):
                raise RuntimeError("status_object_name_not_found")

        monkeypatch.setattr(smb_module, "Open", _OpenMissing)
        svc.read_file("share", "/a.txt")


def test_smb_delete_rename_mkdir_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_core(monkeypatch)
    svc = smb_module.SMBService("h", "u", "p")
    svc._connection = _FakeConnection()
    svc._session = _FakeSession(svc._connection, "u", "p")

    monkeypatch.setattr(smb_module, "register_session", lambda *_a, **_k: None)
    monkeypatch.setattr(
        smb_module,
        "smb_stat",
        lambda path: SimpleNamespace(st_mode=stat_module.S_IFDIR if path.endswith("dir") else stat_module.S_IFREG),
    )
    monkeypatch.setattr(smb_module, "smb_remove", Mock())
    monkeypatch.setattr(smb_module, "smb_rmdir", Mock())
    monkeypatch.setattr(smb_module, "smb_listdir", lambda _p: [".", "..", "child.txt"])
    monkeypatch.setattr(smb_module, "smb_rename", Mock())
    monkeypatch.setattr(
        smb_module,
        "smb_walk",
        lambda _p: iter([("\\\\h\\share", ["sub"], ["a.txt"]), ("\\\\h\\share\\sub", [], ["b.txt"])]),
    )

    svc.delete_item("share", "/a.txt", recursive=False)
    svc.delete_item("share", "/dir", recursive=True)
    svc.rename_item("share", "/a.txt", "b.txt")
    results = svc.search_files("share", "/", "txt", max_depth=3, max_results=10)
    assert any(r["type"] == "file" for r in results)

    class _OpenDir:
        def __init__(self, *_args):
            pass

        def create(self, *_args, **_kwargs):
            return None

        def close(self):
            return None

    monkeypatch.setattr(smb_module, "Open", _OpenDir)
    svc.create_directory("share", "/new")

    monkeypatch.setattr(smb_module, "smb_rename", lambda *_a, **_k: (_ for _ in ()).throw(FileExistsError()))
    with pytest.raises(smb_module.SMBError):
        svc.rename_item("share", "/a.txt", "b.txt")

    monkeypatch.setattr(smb_module, "smb_walk", lambda _p: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(smb_module.SMBError):
        svc.search_files("share", "/", "txt")


def test_create_smb_service_factory() -> None:
    svc = smb_module.create_smb_service("u", "p", host="h", port=445, share="docs")
    assert isinstance(svc, smb_module.SMBService)
    assert svc.host == "h"
    assert svc.auth_share == "docs"
