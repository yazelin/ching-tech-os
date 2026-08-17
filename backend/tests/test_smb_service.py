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


def _make_authed_service() -> smb_module.SMBService:
    """建立一個已帶假 session 的 SMBService（不經過真實連線）。"""
    svc = smb_module.SMBService("h", "u", "p")
    svc._connection = _FakeConnection()
    svc._session = _FakeSession(svc._connection, "u", "p")
    return svc


def test_smb_connect_generic_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """連線時發生非逾時的例外，應轉為 SMBConnectionError。"""

    class _BrokenConnection(_FakeConnection):
        def connect(self, timeout=None):
            raise RuntimeError("socket error")

    monkeypatch.setattr(smb_module, "Connection", _BrokenConnection)
    with pytest.raises(smb_module.SMBConnectionError):
        smb_module.SMBService("h", "u", "p")._connect()


def test_smb_authenticate_without_connection() -> None:
    """尚未建立連線就認證，應拋出 SMBConnectionError。"""
    svc = smb_module.SMBService("h", "u", "p")
    with pytest.raises(smb_module.SMBConnectionError):
        svc._authenticate()


def test_smb_authenticate_generic_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """認證失敗但訊息與帳密無關時，應拋出一般 SMBError。"""

    class _WeirdSession(_FakeSession):
        def connect(self):
            raise RuntimeError("unexpected boom")

    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _WeirdSession)

    svc = smb_module.SMBService("h", "u", "p")
    svc._connect()
    with pytest.raises(smb_module.SMBError) as exc_info:
        svc._authenticate()
    # 不應被歸類為認證錯誤（401）
    assert not isinstance(exc_info.value, smb_module.SMBAuthError)


def test_smb_disconnect_swallows_errors() -> None:
    """session / connection 關閉失敗時應吞掉例外並清空狀態。"""

    class _BadClose:
        def disconnect(self):
            raise RuntimeError("close failed")

    svc = smb_module.SMBService("h", "u", "p")
    svc._session = _BadClose()
    svc._connection = _BadClose()
    svc._disconnect()  # 不應拋出例外
    assert svc._session is None
    assert svc._connection is None


def test_smb_context_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """with 語法應自動連線、認證並在離開時斷線。"""
    _patch_core(monkeypatch)
    with smb_module.SMBService("h", "u", "p") as svc:
        assert svc._session is not None
    assert svc._session is None
    assert svc._connection is None


def test_smb_test_auth_share_other_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """auth_share 連線失敗且非權限問題（如共享不存在），也視為認證失敗。"""
    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _FakeSession)

    class _MissingShareTree(_FakeTree):
        def connect(self):
            raise RuntimeError("share not available")

    monkeypatch.setattr(smb_module, "TreeConnect", _MissingShareTree)
    with pytest.raises(smb_module.SMBAuthError):
        smb_module.SMBService("h", "u", "p", auth_share="ghost").test_auth()


def test_smb_test_auth_tree_disconnect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """tree 斷線失敗時應吞掉例外，不影響 test_auth 結果。"""
    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _FakeSession)

    class _BadDisconnectTree(_FakeTree):
        def disconnect(self):
            raise RuntimeError("disconnect failed")

    monkeypatch.setattr(smb_module, "TreeConnect", _BadDisconnectTree)
    assert smb_module.SMBService("h", "u", "p", auth_share="ok").test_auth() is True


def test_smb_list_shares_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """list_shares 的逾時、缺少 smbclient、一般例外與空行解析分支。"""
    import subprocess

    svc = smb_module.SMBService("h", "u", "p")

    # 輸出中間夾空行，應被跳過
    class _Result:
        def __init__(self, code, out="", err=""):
            self.returncode = code
            self.stdout = out
            self.stderr = err

    monkeypatch.setattr(
        "subprocess.run",
        lambda *_a, **_k: _Result(0, "Disk|docs|x\n\nDisk|media|x\n"),
    )
    assert svc.list_shares() == [
        {"name": "docs", "type": "disk"},
        {"name": "media", "type": "disk"},
    ]

    # 逾時
    def _raise_timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="smbclient", timeout=10)

    monkeypatch.setattr("subprocess.run", _raise_timeout)
    with pytest.raises(smb_module.SMBError, match="逾時"):
        svc.list_shares()

    # 系統未安裝 smbclient
    def _raise_not_found(*_a, **_k):
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", _raise_not_found)
    with pytest.raises(smb_module.SMBError, match="smbclient"):
        svc.list_shares()

    # 其他未預期例外
    def _raise_generic(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("subprocess.run", _raise_generic)
    with pytest.raises(smb_module.SMBError, match="失敗"):
        svc.list_shares()


def test_smb_operations_require_session() -> None:
    """所有需要認證的操作在沒有 session 時應直接拋出 SMBError。"""
    svc = smb_module.SMBService("h", "u", "p")
    with pytest.raises(smb_module.SMBError):
        svc.browse_directory("share")
    with pytest.raises(smb_module.SMBError):
        svc.read_file("share", "/a.txt")
    with pytest.raises(smb_module.SMBError):
        svc.write_file("share", "/a.txt", b"x")
    with pytest.raises(smb_module.SMBError):
        svc.delete_item("share", "/a.txt")
    with pytest.raises(smb_module.SMBError):
        svc.rename_item("share", "/a.txt", "b.txt")
    with pytest.raises(smb_module.SMBError):
        svc.create_directory("share", "/new")
    with pytest.raises(smb_module.SMBError):
        svc.search_files("share", "/", "txt")


def test_smb_browse_directory_edge_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """browse_directory 應跳過 . / ..，並容忍缺欄位與異常時間值。"""
    _patch_core(monkeypatch)

    class _OpenEdge:
        def __init__(self, _tree, path):
            self.path = path

        def create(self, *_args, **_kwargs):
            return None

        def query_directory(self, *_args, **_kwargs):
            return [
                # 應被跳過的目錄項目
                {"file_name": _V("."), "file_attributes": _V(0)},
                {"file_name": _V(".."), "file_attributes": _V(0)},
                # 缺 end_of_file 與 last_write_time → size=0、modified=None
                {"file_name": _V("no-meta.txt"), "file_attributes": _V(0)},
                # last_write_time 為 0（非正整數）→ modified=None
                {
                    "file_name": _V("zero-time.txt"),
                    "file_attributes": _V(0),
                    "end_of_file": _V(5),
                    "last_write_time": _V(0),
                },
            ]

        def close(self):
            return None

    monkeypatch.setattr(smb_module, "Open", _OpenEdge)
    svc = _make_authed_service()
    items = svc.browse_directory("share", "")
    assert [i["name"] for i in items] == ["no-meta.txt", "zero-time.txt"]
    assert items[0]["size"] == 0
    assert items[0]["modified"] is None
    assert items[1]["modified"] is None


def test_smb_browse_directory_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """browse_directory 權限錯誤與一般錯誤分支，以及 tree 斷線失敗吞例外。"""
    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _FakeSession)

    class _BadDisconnectTree(_FakeTree):
        def disconnect(self):
            raise RuntimeError("disconnect failed")

    monkeypatch.setattr(smb_module, "TreeConnect", _BadDisconnectTree)

    class _OpenDenied:
        def __init__(self, *_args):
            pass

        def create(self, *_args, **_kwargs):
            raise RuntimeError("access denied")

    monkeypatch.setattr(smb_module, "Open", _OpenDenied)
    svc = _make_authed_service()
    with pytest.raises(smb_module.SMBError, match="無權限"):
        svc.browse_directory("share", "/sub")

    class _OpenBroken:
        def __init__(self, *_args):
            pass

        def create(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(smb_module, "Open", _OpenBroken)
    with pytest.raises(smb_module.SMBError, match="瀏覽資料夾失敗"):
        svc.browse_directory("share", "/sub")


def test_smb_read_write_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """read_file 一般錯誤、write_file 權限/一般錯誤與 tree 斷線失敗分支。"""
    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _FakeSession)

    class _BadDisconnectTree(_FakeTree):
        def disconnect(self):
            raise RuntimeError("disconnect failed")

    monkeypatch.setattr(smb_module, "TreeConnect", _BadDisconnectTree)
    svc = _make_authed_service()

    class _OpenBroken:
        def __init__(self, *_args):
            pass

        def create(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(smb_module, "Open", _OpenBroken)
    with pytest.raises(smb_module.SMBError, match="讀取檔案失敗"):
        svc.read_file("share", "/a.txt")
    with pytest.raises(smb_module.SMBError, match="寫入檔案失敗"):
        svc.write_file("share", "/a.txt", b"x")

    class _OpenWriteDenied:
        def __init__(self, *_args):
            pass

        def create(self, *_args, **_kwargs):
            raise RuntimeError("access denied")

    monkeypatch.setattr(smb_module, "Open", _OpenWriteDenied)
    with pytest.raises(smb_module.SMBError, match="無權限寫入"):
        svc.write_file("share", "/a.txt", b"x")


def test_smb_delete_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """delete_item 的不存在、權限、非空資料夾與一般錯誤分支。"""
    svc = _make_authed_service()
    monkeypatch.setattr(smb_module, "register_session", lambda *_a, **_k: None)

    # 檔案或資料夾不存在
    monkeypatch.setattr(
        smb_module, "smb_stat", lambda _p: (_ for _ in ()).throw(FileNotFoundError())
    )
    with pytest.raises(smb_module.SMBError, match="不存在"):
        svc.delete_item("share", "/gone.txt")

    # OSError：權限被拒
    monkeypatch.setattr(
        smb_module, "smb_stat", lambda _p: (_ for _ in ()).throw(OSError("access denied"))
    )
    with pytest.raises(smb_module.SMBError, match="無權限"):
        svc.delete_item("share", "/locked.txt")

    # OSError：資料夾非空
    monkeypatch.setattr(
        smb_module,
        "smb_stat",
        lambda _p: SimpleNamespace(st_mode=stat_module.S_IFDIR),
    )
    monkeypatch.setattr(
        smb_module, "smb_rmdir", lambda _p: (_ for _ in ()).throw(OSError("directory not empty"))
    )
    with pytest.raises(smb_module.SMBError, match="遞迴刪除"):
        svc.delete_item("share", "/dir", recursive=False)

    # OSError：其他錯誤
    monkeypatch.setattr(
        smb_module, "smb_rmdir", lambda _p: (_ for _ in ()).throw(OSError("disk failure"))
    )
    with pytest.raises(smb_module.SMBError, match="刪除失敗"):
        svc.delete_item("share", "/dir", recursive=False)

    # 非 OSError 的未預期例外
    monkeypatch.setattr(
        smb_module, "smb_rmdir", lambda _p: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(smb_module.SMBError, match="刪除失敗"):
        svc.delete_item("share", "/dir", recursive=False)


def test_smb_delete_recursive_with_subdir(monkeypatch: pytest.MonkeyPatch) -> None:
    """遞迴刪除含子資料夾的目錄，應先深入子層再刪除自身。"""
    svc = _make_authed_service()
    monkeypatch.setattr(smb_module, "register_session", lambda *_a, **_k: None)

    # dir 底下有子資料夾 sub 與檔案 a.txt；sub 底下只有 b.txt
    def _listdir(path):
        if path.endswith("\\sub"):
            return ["b.txt"]
        return [".", "..", "sub", "a.txt"]

    def _stat(path):
        is_dir = path.endswith("\\dir") or path.endswith("\\sub")
        return SimpleNamespace(
            st_mode=stat_module.S_IFDIR if is_dir else stat_module.S_IFREG
        )

    removed: list[str] = []
    rmdirs: list[str] = []
    monkeypatch.setattr(smb_module, "smb_listdir", _listdir)
    monkeypatch.setattr(smb_module, "smb_stat", _stat)
    monkeypatch.setattr(smb_module, "smb_remove", removed.append)
    monkeypatch.setattr(smb_module, "smb_rmdir", rmdirs.append)

    svc.delete_item("share", "/dir", recursive=True)
    assert any(p.endswith("b.txt") for p in removed)
    assert any(p.endswith("a.txt") for p in removed)
    # 子資料夾與根資料夾都應被 rmdir
    assert any(p.endswith("\\sub") for p in rmdirs)
    assert any(p.endswith("\\dir") for p in rmdirs)


def test_smb_rename_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """rename_item 的子資料夾路徑計算與各錯誤分支。"""
    svc = _make_authed_service()
    monkeypatch.setattr(smb_module, "register_session", lambda *_a, **_k: None)

    # 子資料夾內重命名：新路徑應保留父層目錄
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(smb_module, "smb_rename", lambda old, new: calls.append((old, new)))
    svc.rename_item("share", "/folder/a.txt", "b.txt")
    assert calls[0][1].endswith("\\folder\\b.txt")

    # 檔案不存在
    monkeypatch.setattr(
        smb_module, "smb_rename", lambda *_a: (_ for _ in ()).throw(FileNotFoundError())
    )
    with pytest.raises(smb_module.SMBError, match="不存在"):
        svc.rename_item("share", "/a.txt", "b.txt")

    # OSError：權限被拒
    monkeypatch.setattr(
        smb_module, "smb_rename", lambda *_a: (_ for _ in ()).throw(OSError("access denied"))
    )
    with pytest.raises(smb_module.SMBError, match="無權限"):
        svc.rename_item("share", "/a.txt", "b.txt")

    # OSError：目標已存在
    monkeypatch.setattr(
        smb_module, "smb_rename", lambda *_a: (_ for _ in ()).throw(OSError("target exists"))
    )
    with pytest.raises(smb_module.SMBError, match="已存在"):
        svc.rename_item("share", "/a.txt", "b.txt")

    # OSError：其他錯誤
    monkeypatch.setattr(
        smb_module, "smb_rename", lambda *_a: (_ for _ in ()).throw(OSError("io failure"))
    )
    with pytest.raises(smb_module.SMBError, match="重命名失敗"):
        svc.rename_item("share", "/a.txt", "b.txt")

    # 非 OSError 的未預期例外
    monkeypatch.setattr(
        smb_module, "smb_rename", lambda *_a: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(smb_module.SMBError, match="重命名失敗"):
        svc.rename_item("share", "/a.txt", "b.txt")


def test_smb_create_directory_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_directory 的權限、已存在與一般錯誤分支，含 tree 斷線失敗。"""
    monkeypatch.setattr(smb_module, "Connection", _FakeConnection)
    monkeypatch.setattr(smb_module, "Session", _FakeSession)

    class _BadDisconnectTree(_FakeTree):
        def disconnect(self):
            raise RuntimeError("disconnect failed")

    monkeypatch.setattr(smb_module, "TreeConnect", _BadDisconnectTree)
    svc = _make_authed_service()

    def _make_open(message: str):
        class _OpenFail:
            def __init__(self, *_args):
                pass

            def create(self, *_args, **_kwargs):
                raise RuntimeError(message)

        return _OpenFail

    monkeypatch.setattr(smb_module, "Open", _make_open("access denied"))
    with pytest.raises(smb_module.SMBError, match="無權限"):
        svc.create_directory("share", "/new")

    monkeypatch.setattr(smb_module, "Open", _make_open("object name exists"))
    with pytest.raises(smb_module.SMBError, match="已存在"):
        svc.create_directory("share", "/new")

    monkeypatch.setattr(smb_module, "Open", _make_open("boom"))
    with pytest.raises(smb_module.SMBError, match="建立資料夾失敗"):
        svc.create_directory("share", "/new")


def test_smb_search_files_depth_prefix_and_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """search_files 的深度限制、子路徑前綴、目錄命中與 max_results 分支。"""
    svc = _make_authed_service()
    monkeypatch.setattr(smb_module, "register_session", lambda *_a, **_k: None)

    root = "\\\\h\\share\\start"

    def _walk(_p):
        # 第一層含符合的資料夾與檔案，第二層超過深度應被跳過
        yield root, ["match-dir", "other"], ["match-a.txt"]
        yield rf"{root}\match-dir\deep1\deep2", [], ["match-deep.txt"]

    monkeypatch.setattr(smb_module, "smb_walk", _walk)

    # 指定起始子路徑（base_path 非空），深度 1 應排除第三層結果
    results = svc.search_files("share", "/start", "match", max_depth=1, max_results=10)
    names = [r["name"] for r in results]
    assert "match-dir" in names
    assert "match-a.txt" in names
    assert "match-deep.txt" not in names
    # 路徑前綴應包含起始子路徑
    assert all(r["path"].startswith("/start/") for r in results)

    # max_results=1：第一個目錄命中後即回傳
    results = svc.search_files("share", "/start", "match", max_depth=1, max_results=1)
    assert len(results) == 1
    assert results[0]["type"] == "directory"

    # 只有檔案命中時，max_results 應在檔案迴圈中觸發
    monkeypatch.setattr(
        smb_module,
        "smb_walk",
        lambda _p: iter([(root, [], ["match-1.txt", "match-2.txt"])]),
    )
    results = svc.search_files("share", "/start", "match", max_results=1)
    assert len(results) == 1
    assert results[0]["type"] == "file"

    # 子層有命中時，rel_dir 與 base_path 前綴應同時保留
    monkeypatch.setattr(
        smb_module,
        "smb_walk",
        lambda _p: iter([(rf"{root}\sub", [], ["match-sub.txt"])]),
    )
    results = svc.search_files("share", "/start", "match", max_depth=2)
    assert results[0]["path"] == "/start/sub/match-sub.txt"

    # 未預期例外應轉為 SMBError
    monkeypatch.setattr(
        smb_module, "smb_walk", lambda _p: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(smb_module.SMBError, match="搜尋失敗"):
        svc.search_files("share", "/start", "match")
