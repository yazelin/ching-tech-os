"""Files API 目錄列表端點測試"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from ching_tech_os.api.files import list_directory
from ching_tech_os.models.auth import SessionData


def _session() -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="",
        nas_host="h",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_list_directory_success(tmp_path) -> None:
    (tmp_path / "技術文件").mkdir()
    (tmp_path / "產品資料").mkdir()
    (tmp_path / "規格書.pdf").write_bytes(b"pdf-content")
    (tmp_path / ".hidden").write_text("x")  # 隱藏檔應排除

    with patch(
        "ching_tech_os.api.files._get_file_path", return_value=tmp_path
    ):
        resp = await list_directory("shared", "library", session=_session())

    assert resp.success is True
    assert resp.dirs == ["技術文件", "產品資料"] or sorted(resp.dirs) == [
        "技術文件",
        "產品資料",
    ]
    assert [f.name for f in resp.files] == ["規格書.pdf"]
    assert resp.files[0].size == len(b"pdf-content")


@pytest.mark.asyncio
async def test_list_directory_errors(tmp_path) -> None:
    # NAS zone 不支援
    with pytest.raises(HTTPException) as e:
        await list_directory("nas", "share/folder", session=_session())
    assert e.value.status_code == 400

    # 空路徑
    with pytest.raises(HTTPException) as e:
        await list_directory("shared", "", session=_session())
    assert e.value.status_code == 400

    # 路徑穿越
    with pytest.raises(HTTPException) as e:
        await list_directory("shared", "library/../etc", session=_session())
    assert e.value.status_code == 400

    # 目錄不存在
    with patch(
        "ching_tech_os.api.files._get_file_path",
        return_value=tmp_path / "nope",
    ):
        with pytest.raises(HTTPException) as e:
            await list_directory("shared", "library/nope", session=_session())
    assert e.value.status_code == 404

    # 路徑解析失敗（無效的 shared 來源）
    with patch(
        "ching_tech_os.api.files._get_file_path",
        side_effect=ValueError("無效的共享來源"),
    ):
        with pytest.raises(HTTPException) as e:
            await list_directory("shared", "bogus", session=_session())
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_list_directory_path_is_file(tmp_path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    with patch("ching_tech_os.api.files._get_file_path", return_value=f):
        with pytest.raises(HTTPException) as e:
            await list_directory("shared", "library/file.txt", session=_session())
    assert e.value.status_code == 404
