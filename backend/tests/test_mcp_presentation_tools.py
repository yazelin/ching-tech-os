"""MCP presentation tools 測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import presentation_tools


@pytest.fixture
def _allow_tool_permission(monkeypatch: pytest.MonkeyPatch):
    """文件生成三支現在會先過 app 權限（issue #210）。

    這份檔案測的是產生邏輯，權限本身由 test_generation_tools_require_bound_user
    與 tests/test_mcp_unbound_guard.py 負責。
    """
    monkeypatch.setattr(
        presentation_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(True, "")),
    )


def test_fix_md2ppt_and_md2doc_format() -> None:
    md2ppt = """```markdown
---
theme: bad-theme
layout: wrong
---
# T
===
:: right ::
:::
::: chart-bar {'labels':['A'], 'values':[1]}
content
```"""
    fixed = presentation_tools.fix_md2ppt_format(md2ppt)
    assert "theme: midnight" in fixed
    assert "layout: default" in fixed
    assert '::: chart-bar {"labels":["A"], "values":[1]}' in fixed
    assert "\n===\n" in fixed

    md2doc = """# 文件
#### 太深標題
> [!INFO]
內容"""
    fixed_doc = presentation_tools.fix_md2doc_format(md2doc)
    assert fixed_doc.startswith("---")
    assert "**太深標題**" in fixed_doc
    assert "> [!NOTE]" in fixed_doc


@pytest.mark.asyncio
async def test_generate_presentation_paths(
    monkeypatch: pytest.MonkeyPatch, _allow_tool_permission
) -> None:
    missing = await presentation_tools.generate_presentation(
        topic="", outline_json=None, ctos_user_id=1
    )
    assert "請提供 topic" in missing

    invalid_theme = await presentation_tools.generate_presentation(topic="T", theme="bad", ctos_user_id=1)
    assert "無效的主題" in invalid_theme

    invalid_format = await presentation_tools.generate_presentation(
        topic="T", output_format="docx", ctos_user_id=1
    )
    assert "無效的輸出格式" in invalid_format

    invalid_source = await presentation_tools.generate_presentation(
        topic="T", image_source="bad", ctos_user_id=1
    )
    assert "無效的圖片來源" in invalid_source

    captured = {}

    async def _fake_generate(**kwargs):
        captured.update(kwargs)
        return {"title": "Demo", "slides_count": 5, "nas_path": "linebot/files/demo.html"}

    monkeypatch.setattr("ching_tech_os.services.presentation.generate_html_presentation", _fake_generate)
    ok = await presentation_tools.generate_presentation(
        topic="工廠自動化",
        num_slides=99,
        theme="gaia",
        include_images=False,
        image_source="pexels",
        outline_json={"title": "x", "slides": []},
        output_format="html",
        ctos_user_id=1,
    )
    assert "簡報生成完成" in ok
    assert "ctos://linebot/files/demo.html" in ok
    assert captured["num_slides"] == 99
    assert isinstance(captured["outline_json"], str)

    async def _raise_generate(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ching_tech_os.services.presentation.generate_html_presentation", _raise_generate)
    failed = await presentation_tools.generate_presentation(
        topic="工廠自動化", ctos_user_id=1
    )
    assert "發生錯誤" in failed


@pytest.mark.asyncio
async def test_generate_md2ppt_and_md2doc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _allow_tool_permission
) -> None:
    monkeypatch.setattr(presentation_tools, "ensure_db_connection", AsyncMock())
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(settings, "md2ppt_url", "https://md2ppt.example.com")
    monkeypatch.setattr(settings, "md2doc_url", "https://md2doc.example.com")

    bad_ppt = await presentation_tools.generate_md2ppt("# bad", ctos_user_id=1)
    assert "必須是已格式化的 MD2PPT" in bad_ppt
    bad_doc = await presentation_tools.generate_md2doc("# bad", ctos_user_id=1)
    assert "必須是已格式化的 MD2DOC" in bad_doc

    monkeypatch.setattr(
        "ching_tech_os.services.share.create_share_link",
        AsyncMock(return_value=SimpleNamespace(token="token-1", password="pass-1")),
    )
    ok_ppt = await presentation_tools.generate_md2ppt(
        """---
theme: midnight
---
# 投影片
""",
        ctos_user_id=1,
    )
    assert "簡報產生成功" in ok_ppt
    assert "token-1" in ok_ppt
    assert "pass-1" in ok_ppt

    ppt_files = list((tmp_path / "linebot" / "files" / "ai-generated").glob("*.md2ppt"))
    assert len(ppt_files) == 1

    monkeypatch.setattr(
        "ching_tech_os.services.share.create_share_link",
        AsyncMock(return_value=SimpleNamespace(token="token-2", password="pass-2")),
    )
    ok_doc = await presentation_tools.generate_md2doc(
        """---
title: "文件"
---
# 文件
""",
        ctos_user_id=1,
    )
    assert "文件產生成功" in ok_doc
    assert "token-2" in ok_doc
    assert "pass-2" in ok_doc

    doc_files = list((tmp_path / "linebot" / "files" / "ai-generated").glob("*.md2doc"))
    assert len(doc_files) == 1

    monkeypatch.setattr(
        "ching_tech_os.services.share.create_share_link",
        AsyncMock(side_effect=RuntimeError("share failed")),
    )
    failed = await presentation_tools.generate_md2ppt(
        """---
theme: midnight
---
# 投影片
""",
        ctos_user_id=1,
    )
    assert "發生錯誤" in failed


class _FakeProc:
    def __init__(self, returncode: int, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stderr = stderr

    async def communicate(self):
        return b"", self._stderr


@pytest.mark.asyncio
async def test_prepare_print_file_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(presentation_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(presentation_tools, "ALLOWED_PRINT_PATHS", (f"{tmp_path}/", "/tmp/ctos/"))
    monkeypatch.setattr(
        presentation_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(False, "DENY")),
    )

    denied = await presentation_tools.prepare_print_file("/tmp/ctos/a.pdf", ctos_user_id=1)
    assert denied.startswith("❌")

    monkeypatch.setattr(
        presentation_tools,
        "check_mcp_tool_permission",
        AsyncMock(return_value=(True, "")),
    )

    import ching_tech_os.services.path_manager as path_manager_module

    monkeypatch.setattr(path_manager_module.path_manager, "to_filesystem", lambda _p: (_ for _ in ()).throw(ValueError("bad path")))
    parsed_fail = await presentation_tools.prepare_print_file("ctos://knowledge/a.pdf", ctos_user_id=1)
    assert "路徑解析失敗" in parsed_fail

    traversal = await presentation_tools.prepare_print_file("../etc/passwd")
    assert "禁止路徑穿越" in traversal

    outside_file = Path("/tmp/outside.pdf")
    outside_file.write_text("x", encoding="utf-8")
    denied_path = await presentation_tools.prepare_print_file(str(outside_file))
    assert "不允許存取" in denied_path

    missing = await presentation_tools.prepare_print_file(str(tmp_path / "missing.pdf"))
    assert "檔案不存在" in missing

    not_file_dir = tmp_path / "folder"
    not_file_dir.mkdir(parents=True, exist_ok=True)
    not_file = await presentation_tools.prepare_print_file(str(not_file_dir))
    assert "路徑不是檔案" in not_file

    printable = tmp_path / "a.pdf"
    printable.write_text("pdf", encoding="utf-8")
    printable_ok = await presentation_tools.prepare_print_file(str(printable))
    assert "檔案已準備好" in printable_ok
    assert str(printable) in printable_ok

    office = tmp_path / "b.docx"
    office.write_text("docx", encoding="utf-8")
    tmp_pdf_dir = Path("/tmp/ctos/print")
    tmp_pdf_dir.mkdir(parents=True, exist_ok=True)
    (tmp_pdf_dir / "b.pdf").write_text("pdf", encoding="utf-8")

    async def _ok_subprocess(*_args, **_kwargs):
        return _FakeProc(returncode=0)

    monkeypatch.setattr(presentation_tools._asyncio, "create_subprocess_exec", _ok_subprocess)
    office_ok = await presentation_tools.prepare_print_file(str(office))
    assert "已轉換為 PDF" in office_ok

    async def _fail_subprocess(*_args, **_kwargs):
        return _FakeProc(returncode=1, stderr=b"convert failed")

    monkeypatch.setattr(presentation_tools._asyncio, "create_subprocess_exec", _fail_subprocess)
    office_fail = await presentation_tools.prepare_print_file(str(office))
    assert "轉換 PDF 失敗" in office_fail

    async def _missing_binary(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(presentation_tools._asyncio, "create_subprocess_exec", _missing_binary)
    no_libreoffice = await presentation_tools.prepare_print_file(str(office))
    assert "找不到 libreoffice" in no_libreoffice

    unknown = tmp_path / "c.xyz"
    unknown.write_text("x", encoding="utf-8")
    unsupported = await presentation_tools.prepare_print_file(str(unknown))
    assert "不支援的檔案格式" in unsupported


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    ["generate_presentation", "generate_md2ppt", "generate_md2doc"],
)
async def test_generation_tools_require_bound_user(
    tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未綁定叫文件生成三支要被擋，而且底層 service 完全沒被 await（issue #210）。

    這三支都會把檔案寫進 NAS 的 ai-generated 目錄，`generate_md2ppt`／
    `generate_md2doc` 還會建立不需帳號就打得開的分享連結。
    """
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setattr(presentation_tools, "ensure_db_connection", AsyncMock())

    generate_html = AsyncMock()
    create_share = AsyncMock()
    monkeypatch.setattr(
        "ching_tech_os.services.presentation.generate_html_presentation", generate_html
    )
    monkeypatch.setattr("ching_tech_os.services.share.create_share_link", create_share)

    tool = getattr(presentation_tools, tool_name)
    if tool_name == "generate_presentation":
        result = await tool(topic="任何主題", ctos_user_id=None)
    else:
        result = await tool("---\ntheme: midnight\n---\n# T\n", ctos_user_id=None)

    assert result.startswith("❌")
    assert permissions_module.BOUND_USER_REQUIRED_MESSAGE in result
    generate_html.assert_not_awaited()
    create_share.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_print_file_denies_unbound(monkeypatch: pytest.MonkeyPatch) -> None:
    """未綁定不得把檔案推進印表機佇列（issue #210）。

    原本的寫法是 `if ctos_user_id:` 才檢查——未綁定反而整個跳過。
    """
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setattr(presentation_tools, "ensure_db_connection", AsyncMock())

    result = await presentation_tools.prepare_print_file("/tmp/ctos/a.pdf")
    assert result.startswith("❌")
    assert permissions_module.BOUND_USER_REQUIRED_MESSAGE in result
    assert "printer" in permissions_module.APPS_REQUIRE_BOUND_USER
