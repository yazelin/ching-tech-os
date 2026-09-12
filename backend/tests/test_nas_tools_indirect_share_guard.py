"""issue #217（review 追加）：`send_nas_file`／`prepare_file_message` 間接建立分享連結
前也要 `share-manager` 權限。

背景：這兩支工具只掛 `file-manager`（`TOOL_APP_MAPPING`），但內部會直接呼叫
`share_service.create_share_link()` 產生公開連結——這是繞過 `create_share_link`
工具本身 `share-manager` 權限檢查的後門：一個只有 `file-manager` 沒有
`share-manager` 的使用者，原本仍能透過這兩支工具把 NAS 檔案或知識庫附件變成
公開連結。修法是在真的建立連結那一步之前（`_require_share_manager_for_link()`），
額外檢查一次 `share-manager`，不影響這兩支工具其餘不建立連結的路徑（檔案不存在、
路徑解析失敗等既有的驗證錯誤，發生在這道檢查之前）。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import nas_tools
from ching_tech_os.services.mcp import server as mcp_server


class _ConnCtx:
    """最小 async context manager，包一個假的 connection。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _bound_user_conn(share_manager: bool) -> SimpleNamespace:
    """已綁定一般使用者，`file-manager` 用預設值（開放），`share-manager` 由參數決定。"""
    prefs = {"permissions": {"apps": {"share-manager": share_manager}}}
    return SimpleNamespace(
        fetchrow=AsyncMock(return_value={"role": "user", "preferences": prefs})
    )


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    """不碰真的資料庫；用真正的 `check_mcp_tool_permission()`（不整支蓋掉），
    這樣才驗得到 file-manager 與 share-manager 是兩道獨立的權限判斷。
    """
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setattr(nas_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    # 與 `_get_user_shared_mounts()` 有關的來源權限查詢不是本檔要驗的東西，
    # 固定回一組允許的來源，跟 tests/test_mcp_nas_tools.py 的 `_allow()` 同做法。
    monkeypatch.setattr(
        nas_tools,
        "_get_user_shared_mounts",
        AsyncMock(return_value={"projects": "/mnt/nas/projects"}),
    )


def _wire_db(monkeypatch: pytest.MonkeyPatch, share_manager: bool) -> None:
    conn = _bound_user_conn(share_manager)
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))


# ============================================================
# send_nas_file
# ============================================================


@pytest.mark.asyncio
async def test_send_nas_file_denies_without_share_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """有 file-manager（預設開放）沒有 share-manager（預設關閉）→ 拒絕，
    且 `create_share_link` 完全沒被 await（不是「查了但濾掉結果」）。
    """
    import ching_tech_os.services.share as share_module

    _wire_db(monkeypatch, share_manager=False)

    img = tmp_path / "a.jpg"
    img.write_bytes(b"x" * 100)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: img)
    boom = AsyncMock(side_effect=AssertionError("不該建立分享連結"))
    monkeypatch.setattr(share_module, "create_share_link", boom)

    out = await nas_tools.send_nas_file(
        "shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1
    )

    assert out == "❌ 需要「分享管理」功能權限才能產生分享連結"
    boom.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_nas_file_allows_with_share_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """兩道權限都有 → 照常建立連結並發送。"""
    import ching_tech_os.services.share as share_module
    import ching_tech_os.services.bot_telegram.adapter as tg_adapter
    from ching_tech_os.config import settings

    _wire_db(monkeypatch, share_manager=True)
    monkeypatch.setattr(settings, "telegram_bot_token", "tok")

    img = tmp_path / "a.jpg"
    img.write_bytes(b"x" * 100)
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: img)
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/abc", token="abc")),
    )

    class _TG:
        def __init__(self, token):
            self.token = token

        async def send_image(self, *_a):
            return None

        async def send_file(self, *_a):
            return None

        async def send_text(self, *_a):
            return None

    monkeypatch.setattr(tg_adapter, "TelegramBotAdapter", _TG)

    out = await nas_tools.send_nas_file(
        "shared://projects/a.jpg", telegram_chat_id="1", ctos_user_id=1
    )

    assert "已發送圖片" in out


# ============================================================
# prepare_file_message：知識庫附件分支與 NAS 檔案分支都要擋
# ============================================================


@pytest.mark.asyncio
async def test_prepare_file_message_denies_without_share_manager_knowledge_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import ching_tech_os.services.share as share_module
    import ching_tech_os.services.path_manager as pm

    _wire_db(monkeypatch, share_manager=False)

    kf = tmp_path / "kb-001-a.png"
    kf.write_bytes(b"img")
    monkeypatch.setattr(
        pm.path_manager,
        "parse",
        lambda p: SimpleNamespace(
            zone=pm.StorageZone.LOCAL, path="knowledge/assets/images/kb-001-a.png"
        ),
    )
    monkeypatch.setattr(pm.path_manager, "to_filesystem", lambda _p: str(kf))
    boom = AsyncMock(side_effect=AssertionError("不該建立分享連結"))
    monkeypatch.setattr(share_module, "create_share_link", boom)

    out = await nas_tools.prepare_file_message(
        "local://knowledge/assets/images/kb-001-a.png", ctos_user_id=1
    )

    assert out == "❌ 需要「分享管理」功能權限才能產生分享連結"
    boom.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_file_message_denies_without_share_manager_nas_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import ching_tech_os.services.share as share_module

    _wire_db(monkeypatch, share_manager=False)

    nf = tmp_path / "abc.txt"
    nf.write_text("x", encoding="utf-8")
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: nf)
    boom = AsyncMock(side_effect=AssertionError("不該建立分享連結"))
    monkeypatch.setattr(share_module, "create_share_link", boom)

    out = await nas_tools.prepare_file_message("shared://projects/abc.txt", ctos_user_id=1)

    assert out == "❌ 需要「分享管理」功能權限才能產生分享連結"
    boom.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_file_message_allows_with_share_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """對照組：兩道權限都有 → 照常建立連結，NAS 檔案分支。"""
    import ching_tech_os.services.share as share_module

    _wire_db(monkeypatch, share_manager=True)

    nf = tmp_path / "abc.txt"
    nf.write_text("x", encoding="utf-8")
    monkeypatch.setattr(share_module, "validate_nas_file_path", lambda _p, **_k: nf)
    monkeypatch.setattr(
        share_module,
        "create_share_link",
        AsyncMock(return_value=SimpleNamespace(full_url="https://x/s/t", token="t")),
    )

    msg = await nas_tools.prepare_file_message("shared://projects/abc.txt", ctos_user_id=1)

    assert "[FILE_MESSAGE:" in msg


# ============================================================
# 不影響「不建立連結」的既有路徑（檔案不存在等驗證錯誤先發生）
# ============================================================


@pytest.mark.asyncio
async def test_send_nas_file_missing_file_error_unaffected_by_share_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """檔案不存在的驗證錯誤發生在 share-manager 檢查之前，訊息不變、
    也不會被誤判成權限問題。"""
    import ching_tech_os.services.share as share_module

    _wire_db(monkeypatch, share_manager=False)
    monkeypatch.setattr(
        share_module,
        "validate_nas_file_path",
        lambda _p, **_k: (_ for _ in ()).throw(
            share_module.NasFileNotFoundError("找不到檔案")
        ),
    )

    out = await nas_tools.send_nas_file(
        "shared://projects/missing.jpg", telegram_chat_id="1", ctos_user_id=1
    )

    assert "找不到檔案" in out
    assert "分享管理" not in out
