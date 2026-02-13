"""MCP presentation tools 測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services.mcp import presentation_tools


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
async def test_generate_presentation_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = await presentation_tools.generate_presentation(topic="", outline_json=None)
    assert "請提供 topic" in missing

    invalid_theme = await presentation_tools.generate_presentation(topic="T", theme="bad")
    assert "無效的主題" in invalid_theme

    invalid_format = await presentation_tools.generate_presentation(topic="T", output_format="docx")
    assert "無效的輸出格式" in invalid_format

    invalid_source = await presentation_tools.generate_presentation(topic="T", image_source="bad")
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
    )
    assert "簡報生成完成" in ok
    assert "ctos://linebot/files/demo.html" in ok
    assert captured["num_slides"] == 99
    assert isinstance(captured["outline_json"], str)

    async def _raise_generate(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ching_tech_os.services.presentation.generate_html_presentation", _raise_generate)
    failed = await presentation_tools.generate_presentation(topic="工廠自動化")
    assert "發生錯誤" in failed


@pytest.mark.asyncio
async def test_generate_md2ppt_and_md2doc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(presentation_tools, "ensure_db_connection", AsyncMock())
    from ching_tech_os.config import settings

    monkeypatch.setattr(settings, "ctos_mount_path", str(tmp_path))
    monkeypatch.setattr(settings, "md2ppt_url", "https://md2ppt.example.com")
    monkeypatch.setattr(settings, "md2doc_url", "https://md2doc.example.com")

    bad_ppt = await presentation_tools.generate_md2ppt("# bad")
    assert "必須是已格式化的 MD2PPT" in bad_ppt
    bad_doc = await presentation_tools.generate_md2doc("# bad")
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
"""
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
"""
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
"""
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
