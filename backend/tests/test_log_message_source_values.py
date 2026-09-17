"""log_message 的 source 必須是 MessageSource 的合法值。

DB 上有 chk_messages_source 檢查約束（只收 system／security／app／user），
而 log_message 的呼叫端全都用 try/except 把例外吞掉只 print，違規時線上
不會噴錯、只是訊息中心少了一筆，靠人工檢查抓不到。這裡用靜態掃描把所有
呼叫端的 source 字面值逐一比對，違規就讓測試紅掉。
"""

from __future__ import annotations

import ast
from pathlib import Path

from ching_tech_os.models.message import MessageSource

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "ching_tech_os"
VALID = {m.value for m in MessageSource}


def _log_message_source_literals() -> list[tuple[str, int, str]]:
    """掃出所有 log_message(source="...") 的字面值與位置。"""
    found: list[tuple[str, int, str]] = []
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != "log_message":
                continue
            for kw in node.keywords:
                if kw.arg == "source" and isinstance(kw.value, ast.Constant):
                    if isinstance(kw.value.value, str):
                        rel = path.relative_to(SRC_ROOT.parents[1])
                        found.append((str(rel), node.lineno, kw.value.value))
    return found


def test_found_some_call_sites() -> None:
    """掃描本身要有效：掃不到任何呼叫端就是掃描器壞了，不是程式碼乾淨。"""
    assert _log_message_source_literals(), "掃不到任何 log_message(source=...) 呼叫端"


def test_all_log_message_sources_are_valid() -> None:
    bad = [item for item in _log_message_source_literals() if item[2] not in VALID]
    assert not bad, "log_message 的 source 不在 MessageSource 之內（會被 DB 的 " \
        f"chk_messages_source 擋下）：{bad}；合法值：{sorted(VALID)}"
