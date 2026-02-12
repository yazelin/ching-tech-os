"""document_reader 測試。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ching_tech_os.services import document_reader as dr


def test_document_reader_basic_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "a.docx"
    f.write_text("x", encoding="utf-8")
    assert ".pdf" in dr.get_supported_extensions()
    assert dr.is_supported(str(f)) is True
    assert dr.is_legacy_format("x.doc") is True

    with pytest.raises(FileNotFoundError):
        dr.extract_text(str(tmp_path / "missing.docx"))

    g = tmp_path / "a.doc"
    g.write_text("x", encoding="utf-8")
    with pytest.raises(dr.UnsupportedFormatError):
        dr.extract_text(str(g))

    h = tmp_path / "a.txt"
    h.write_text("x", encoding="utf-8")
    with pytest.raises(dr.UnsupportedFormatError):
        dr.extract_text(str(h))

    monkeypatch.setattr(dr, "MAX_FILE_SIZE", {".docx": 0})
    with pytest.raises(dr.FileTooLargeError):
        dr.extract_text(str(f))


def test_extract_docx_xlsx_pptx(monkeypatch: pytest.MonkeyPatch) -> None:
    # docx
    fake_docx = SimpleNamespace(
        paragraphs=[SimpleNamespace(text="p1"), SimpleNamespace(text="")],
        tables=[SimpleNamespace(rows=[SimpleNamespace(cells=[SimpleNamespace(text="a"), SimpleNamespace(text="b")])])],
        core_properties=SimpleNamespace(title="T", author="A"),
    )
    monkeypatch.setattr(dr, "Document", lambda _p: fake_docx)
    monkeypatch.setattr(dr, "MAX_OUTPUT_CHARS", 100)
    d = dr._extract_docx("x.docx")
    assert "p1" in d.text and d.metadata["title"] == "T"

    monkeypatch.setattr(dr, "Document", lambda _p: (_ for _ in ()).throw(RuntimeError("password protected")))
    with pytest.raises(dr.PasswordProtectedError):
        dr._extract_docx("x.docx")

    # xlsx
    class _Sheet:
        def __init__(self, rows):
            self._rows = rows

        def iter_rows(self, values_only=True):
            return self._rows

    class _WB:
        sheetnames = ["S1", "S2"]

        def __getitem__(self, name):
            return _Sheet([(1, 2), (None, None)]) if name == "S1" else _Sheet([])

        def close(self):
            return None

    monkeypatch.setattr(dr, "load_workbook", lambda *_a, **_k: _WB())
    x = dr._extract_xlsx("x.xlsx")
    assert "工作表: S1" in x.text and x.page_count == 2

    monkeypatch.setattr(dr, "load_workbook", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("encrypted")))
    with pytest.raises(dr.PasswordProtectedError):
        dr._extract_xlsx("x.xlsx")

    # pptx
    fake_slide = SimpleNamespace(shapes=[SimpleNamespace(text="S1"), SimpleNamespace(text="")])
    monkeypatch.setattr(dr, "Presentation", lambda _p: SimpleNamespace(slides=[fake_slide]))
    p = dr._extract_pptx("x.pptx")
    assert "投影片 1" in p.text

    monkeypatch.setattr(dr, "Presentation", lambda _p: (_ for _ in ()).throw(RuntimeError("encrypted")))
    with pytest.raises(dr.PasswordProtectedError):
        dr._extract_pptx("x.pptx")


def test_extract_pdf_and_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Page:
        def __init__(self, text):
            self._text = text

        def get_text(self):
            return self._text

        def get_pixmap(self, matrix=None):
            class _Pix:
                def save(self, path):
                    Path(path).write_bytes(b"img")

            return _Pix()

    class _Doc:
        def __init__(self, texts, needs_pass=False):
            self.pages = [_Page(t) for t in texts]
            self.needs_pass = needs_pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter(self.pages)

        def __len__(self):
            return len(self.pages)

        def __getitem__(self, idx):
            return self.pages[idx]

    monkeypatch.setattr(dr.fitz, "open", lambda _p: _Doc(["a", "b"]))
    pdf = dr._extract_pdf("x.pdf")
    assert pdf.page_count == 2 and pdf.error is None

    monkeypatch.setattr(dr.fitz, "open", lambda _p: _Doc(["", ""]))
    scanned = dr._extract_pdf("x.pdf")
    assert scanned.metadata["is_scanned"] is True

    monkeypatch.setattr(dr.fitz, "open", lambda _p: _Doc(["a"], needs_pass=True))
    with pytest.raises(dr.PasswordProtectedError):
        dr._extract_pdf("x.pdf")

    monkeypatch.setattr(dr.fitz, "open", lambda _p: (_ for _ in ()).throw(RuntimeError("bad")))
    with pytest.raises(dr.CorruptedFileError):
        dr._extract_pdf("x.pdf")

    # parse pages
    assert dr._parse_pages_param("all", 5) == [0, 1, 2, 3, 4]
    assert dr._parse_pages_param("1,3-4", 5) == [0, 2, 3]
    with pytest.raises(ValueError):
        dr._parse_pages_param("x", 5)

    # convert pdf
    pdf_file = tmp_path / "x.pdf"
    pdf_file.write_bytes(b"%PDF")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(dr.fitz, "open", lambda _p: _Doc(["a", "b", "c"]))
    monkeypatch.setattr(dr.fitz, "Matrix", lambda *_a, **_k: object())
    r0 = dr.convert_pdf_to_images(str(pdf_file), str(out_dir), pages="0")
    assert r0.total_pages == 3 and r0.converted_pages == 0
    r1 = dr.convert_pdf_to_images(str(pdf_file), str(out_dir), pages="1-3", max_pages=2)
    assert r1.converted_pages == 2

    monkeypatch.setattr(dr.fitz, "open", lambda _p: _Doc(["a"], needs_pass=True))
    with pytest.raises(dr.PasswordProtectedError):
        dr.convert_pdf_to_images(str(pdf_file), str(out_dir))

    monkeypatch.setattr(dr.fitz, "open", lambda _p: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(dr.CorruptedFileError):
        dr.convert_pdf_to_images(str(pdf_file), str(out_dir))

    txt_file = tmp_path / "x.txt"
    txt_file.write_text("x", encoding="utf-8")
    with pytest.raises(dr.UnsupportedFormatError):
        dr.convert_pdf_to_images(str(txt_file), str(out_dir))
