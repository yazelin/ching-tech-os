"""bot_line.file_handler 測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.services.bot_line import file_handler


class _ConnCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


class _FakeFileService:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.raise_write = False
        self.raise_read = False
        self.raise_delete = False

    def write_file(self, path: str, content: bytes):
        if self.raise_write:
            raise file_handler.LocalFileError("write fail")
        self.store[path] = content

    def read_file(self, path: str) -> bytes:
        if self.raise_read:
            raise file_handler.LocalFileError("read fail")
        return self.store[path]

    def delete_file(self, path: str):
        if self.raise_delete:
            raise file_handler.LocalFileError("delete fail")
        self.store.pop(path, None)


@pytest.mark.asyncio
async def test_save_record_download_and_guess(monkeypatch: pytest.MonkeyPatch) -> None:
    message_uuid = uuid4()
    file_uuid = uuid4()
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={"id": file_uuid}), execute=AsyncMock())
    monkeypatch.setattr(file_handler, "get_connection", lambda: _ConnCtx(conn))

    returned = await file_handler.save_file_record(
        message_uuid=message_uuid,
        file_type="image",
        file_name="a.jpg",
        file_size=100,
        mime_type="image/jpeg",
        nas_path="groups/g1/images/a.jpg",
        duration=None,
    )
    assert returned == file_uuid
    conn.execute.assert_awaited_once()

    monkeypatch.setattr(file_handler, "download_line_content", AsyncMock(return_value=b"abc"))
    original_generate_nas_path = file_handler.generate_nas_path
    monkeypatch.setattr(file_handler, "generate_nas_path", lambda **_kwargs: "groups/g1/files/a.txt")
    monkeypatch.setattr(file_handler, "save_to_nas", AsyncMock(return_value=True))
    saved = await file_handler.download_and_save_file("m1", message_uuid, "file", line_group_id="g1", file_name="a.txt")
    assert saved == "groups/g1/files/a.txt"

    monkeypatch.setattr(file_handler, "save_to_nas", AsyncMock(return_value=False))
    assert await file_handler.download_and_save_file("m1", message_uuid, "file", line_group_id="g1", file_name="a.txt") is None

    monkeypatch.setattr(file_handler, "download_line_content", AsyncMock(return_value=None))
    assert await file_handler.download_and_save_file("m1", message_uuid, "file", line_group_id="g1", file_name="a.txt") is None

    monkeypatch.setattr(file_handler, "download_line_content", AsyncMock(side_effect=RuntimeError("boom")))
    assert await file_handler.download_and_save_file("m1", message_uuid, "file") is None

    monkeypatch.setattr(file_handler, "generate_nas_path", original_generate_nas_path)
    path1 = file_handler.generate_nas_path("image", "m1", line_group_id="g1", file_name=None, content=b"\xff\xd8\xffx")
    path2 = file_handler.generate_nas_path("file", "m2", line_user_id="u1", file_name="../x.txt")
    path3 = file_handler.generate_nas_path("audio", "m3")
    assert "groups/g1/images/" in path1
    assert "m2_.._x.txt" in path2
    assert path3.startswith("unknown/audios/")

    assert file_handler.guess_mime_type(b"\xff\xd8\xffa") == "image/jpeg"
    assert file_handler.guess_mime_type(b"\x89PNG\r\n\x1a\nabc") == "image/png"
    assert file_handler.guess_mime_type(b"GIF89aabc") == "image/gif"
    assert file_handler.guess_mime_type(b"RIFFxxxxWEBP") == "image/webp"
    assert file_handler.guess_mime_type(b"xxxxftypisom") == "audio/m4a"
    assert file_handler.guess_mime_type(b"unknown") == "application/octet-stream"


@pytest.mark.asyncio
async def test_line_content_and_nas_operations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Resp:
        def __init__(self, status_code: int, content: bytes, text: str = "") -> None:
            self.status_code = status_code
            self.content = content
            self.text = text

    class _Client:
        def __init__(self, status_code: int):
            self.status_code = status_code

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url, headers=None):
            return _Resp(self.status_code, b"ok", text="bad")

    monkeypatch.setattr(file_handler.settings, "line_channel_access_token", "token")
    monkeypatch.setattr(file_handler.httpx, "AsyncClient", lambda timeout=300.0: _Client(200))
    assert await file_handler.download_line_content("m1") == b"ok"

    monkeypatch.setattr(file_handler.httpx, "AsyncClient", lambda timeout=300.0: _Client(500))
    assert await file_handler.download_line_content("m1") is None

    class _ErrClient(_Client):
        async def get(self, _url, headers=None):
            raise RuntimeError("http fail")

    monkeypatch.setattr(file_handler.httpx, "AsyncClient", lambda timeout=300.0: _ErrClient(200))
    assert await file_handler.download_line_content("m1") is None

    fake_service = _FakeFileService()
    monkeypatch.setattr(file_handler, "create_linebot_file_service", lambda: fake_service)
    assert await file_handler.save_to_nas("a/b.txt", b"123") is True
    assert await file_handler.read_file_from_nas("a/b.txt") == b"123"

    fake_service.raise_write = True
    assert await file_handler.save_to_nas("a/c.txt", b"123") is False

    fake_service.raise_read = True
    assert await file_handler.read_file_from_nas("a/b.txt") is None

    # delete_file / list_files / get_file_by_id / get_image_info / get_file_info
    file_id = uuid4()
    message_id = uuid4()
    conn = SimpleNamespace(
        execute=AsyncMock(),
        fetchval=AsyncMock(return_value=2),
        fetch=AsyncMock(return_value=[{"id": file_id, "file_type": "image"}]),
        fetchrow=AsyncMock(
            side_effect=[
                {"id": file_id, "file_type": "image", "message_id": message_id, "nas_path": "a/b.txt"},
                {"id": file_id, "file_type": "image"},
            ]
        ),
    )
    monkeypatch.setattr(file_handler, "get_connection", lambda: _ConnCtx(conn))
    fake_service.raise_delete = False
    deleted = await file_handler.delete_file(file_id)
    assert deleted is True

    fake_service.raise_delete = True
    deleted_with_nas_error = await file_handler.delete_file(file_id)
    assert deleted_with_nas_error is True

    original_get_file_by_id = file_handler.get_file_by_id
    monkeypatch.setattr(file_handler, "get_file_by_id", AsyncMock(return_value=None))
    assert await file_handler.delete_file(file_id) is False

    monkeypatch.setattr(file_handler, "get_file_by_id", original_get_file_by_id)
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": file_id, "file_type": "image"},
            None,
            {"nas_path": "a.jpg", "file_type": "image", "message_uuid": message_id},
            {"nas_path": "a.txt", "file_type": "file", "file_name": "a.txt", "file_size": 1, "message_uuid": message_id},
            None,
        ]
    )
    files, total = await file_handler.list_files(line_group_id=uuid4(), file_type="image", platform_type="line", limit=10, offset=0)
    assert total == 2
    assert files[0]["file_type"] == "image"

    one = await file_handler.get_file_by_id(file_id)
    missing = await file_handler.get_file_by_id(file_id)
    assert one is not None
    assert missing is None

    img_info = await file_handler.get_image_info_by_line_message_id("mid-1")
    file_info = await file_handler.get_file_info_by_line_message_id("mid-1")
    file_missing = await file_handler.get_file_info_by_line_message_id("mid-2")
    assert img_info is not None
    assert file_info is not None
    assert file_missing is None


@pytest.mark.asyncio
async def test_temp_image_and_temp_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(file_handler, "TEMP_IMAGE_DIR", str(tmp_path / "img"))
    monkeypatch.setattr(file_handler, "TEMP_FILE_DIR", str(tmp_path / "file"))
    monkeypatch.setattr(file_handler, "MAX_READABLE_FILE_SIZE", 10)

    # get_temp helper
    assert file_handler.get_temp_image_path("m1").endswith("/m1.jpg")
    assert file_handler.get_temp_file_path("m1", "../a.txt").endswith("m1_.._a.txt")

    # ensure_temp_image: 已存在
    existing = Path(file_handler.get_temp_image_path("m2"))
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"abc")
    assert await file_handler.ensure_temp_image("m2", "a.jpg") == str(existing)

    # ensure_temp_image: NAS 讀取失敗 / 成功 / 寫入失敗
    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=None))
    assert await file_handler.ensure_temp_image("m3", "a.jpg") is None

    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=b"xyz"))
    ok_temp = await file_handler.ensure_temp_image("m4", "a.jpg")
    assert ok_temp is not None and Path(ok_temp).exists()

    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=b"xyz"))
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("write fail")))
    assert await file_handler.ensure_temp_image("m5", "a.jpg") is None


@pytest.mark.asyncio
async def test_ensure_temp_file_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(file_handler, "TEMP_FILE_DIR", str(tmp_path / "file"))
    monkeypatch.setattr(file_handler, "MAX_READABLE_FILE_SIZE", 8)

    # 不可讀
    monkeypatch.setattr(file_handler, "is_readable_file", lambda _name: False)
    assert await file_handler.ensure_temp_file("m1", "a", "a.bin") is None

    # 可讀但太大（非 document）
    monkeypatch.setattr(file_handler, "is_readable_file", lambda _name: True)
    monkeypatch.setattr(file_handler, "is_document_file", lambda _name: False)
    assert await file_handler.ensure_temp_file("m2", "a", "a.txt", file_size=99) is None

    # 既有檔案
    existing = Path(file_handler.get_temp_file_path("m3", "a.txt"))
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"ok")
    assert await file_handler.ensure_temp_file("m3", "a", "a.txt", file_size=1) == str(existing)

    # NAS 讀取失敗
    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=None))
    assert await file_handler.ensure_temp_file("m4", "a", "a.txt", file_size=1) is None

    # 純文字實際內容過大 / 成功
    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=b"0123456789"))
    assert await file_handler.ensure_temp_file("m5", "a", "a.txt", file_size=1) is None

    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=b"1234"))
    ok_txt = await file_handler.ensure_temp_file("m6", "a", "a.txt", file_size=1)
    assert ok_txt is not None and Path(ok_txt).exists()

    # 文件解析成功（含 PDF 路徑）
    monkeypatch.setattr(file_handler, "is_document_file", lambda _name: True)
    monkeypatch.setattr(file_handler, "read_file_from_nas", AsyncMock(return_value=b"%PDF-1.4"))
    import ching_tech_os.services.workers as workers_module

    async def _run_in_doc_pool(_func, _path):
        return SimpleNamespace(text="doc text", error=None)

    monkeypatch.setattr(workers_module, "run_in_doc_pool", _run_in_doc_pool)
    pdf_result = await file_handler.ensure_temp_file("m7", "a", "report.pdf", file_size=1)
    assert pdf_result is not None and "PDF:" in pdf_result and "|TXT:" in pdf_result

    # 文件過大 / 密碼保護 / 解析失敗 / 一般例外
    async def _raise_too_large(_func, _path):
        raise file_handler.document_reader.FileTooLargeError("too large")

    monkeypatch.setattr(workers_module, "run_in_doc_pool", _raise_too_large)
    assert await file_handler.ensure_temp_file("m8", "a", "report.docx", file_size=1) is None

    async def _raise_password(_func, _path):
        raise file_handler.document_reader.PasswordProtectedError("locked")

    monkeypatch.setattr(workers_module, "run_in_doc_pool", _raise_password)
    pwd_path = await file_handler.ensure_temp_file("m9", "a", "report.docx", file_size=1)
    assert pwd_path is not None and Path(pwd_path).exists()

    async def _raise_doc_error(_func, _path):
        raise file_handler.document_reader.DocumentReadError("broken")

    monkeypatch.setattr(workers_module, "run_in_doc_pool", _raise_doc_error)
    assert await file_handler.ensure_temp_file("m10", "a", "report.docx", file_size=1) is None
    pdf_doc_error = await file_handler.ensure_temp_file("m11", "a", "report.pdf", file_size=1)
    assert pdf_doc_error is not None and pdf_doc_error.startswith("PDF:")

    async def _raise_runtime(_func, _path):
        raise RuntimeError("boom")

    monkeypatch.setattr(workers_module, "run_in_doc_pool", _raise_runtime)
    assert await file_handler.ensure_temp_file("m12", "a", "report.docx", file_size=1) is None
