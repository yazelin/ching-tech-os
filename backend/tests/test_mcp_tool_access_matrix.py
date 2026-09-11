"""MCP 工具存取矩陣：文件必須等於程式內省的結果（issue #201／#204／#205／#207）。

矩陣是「未綁定者到底能碰到什麼」的單一事實來源。手寫的表格三個月後就是假的，
所以 `backend/scripts/gen_tool_access_matrix.py` 從 `TOOL_APP_MAPPING`、
`APPS_REQUIRE_BOUND_USER`、`DEFAULT_APP_PERMISSIONS`、`TOOLS_REQUIRE_BOUND_USER`、
`WRITE_TOOLS` 和 MCP 工具清單產生，這裡重跑一次比對逐字相同。

另外兩條是 registry 漂移的負控制：
- 名字是寫入動詞開頭的工具沒進 `WRITE_TOOLS` → 紅
- `TOOLS_REQUIRE_BOUND_USER` 裡的工具實際上沒擋未綁定 → 紅
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services.mcp import server as mcp_server

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
GENERATOR = BACKEND_DIR / "scripts" / "gen_tool_access_matrix.py"
MATRIX_DOC = REPO_ROOT / "docs" / "mcp-tool-access-matrix.md"


def _generate(enabled_modules: str = "knowledge") -> str:
    """以乾淨的直譯器重跑產生器。

    - 用 subprocess：其他測試會往真的 MCP registry 註冊假工具，in-process 產生會被汙染。
    - 明確給一份最小 env：不繼承這個 pytest 行程的環境，矩陣才不會隨開發機飄。
    - `ENABLED_MODULES` 預設故意傳一個「只開一個模組」的值：產生器要自己硬設成 `*`，
      否則 `get_effective_app_permissions()` 會少掉被停用模組的 app，整欄「未綁定可呼叫」就變了。
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONIOENCODING": "utf-8",
        "ENABLED_MODULES": enabled_modules,
    }
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--stdout"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        cwd=str(BACKEND_DIR),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_matrix_doc_matches_generator() -> None:
    """重新產生要與 repo 內的檔案逐字相同（漂移就紅）。"""
    assert MATRIX_DOC.exists(), "docs/mcp-tool-access-matrix.md 不存在"
    assert MATRIX_DOC.read_text(encoding="utf-8") == _generate()


@pytest.mark.parametrize("enabled_modules", ["*", "knowledge", ""])
def test_matrix_is_independent_of_enabled_modules(enabled_modules: str) -> None:
    """產生器硬設 `ENABLED_MODULES=*`：呼叫端的設定不該改變矩陣內容。"""
    assert _generate(enabled_modules) == MATRIX_DOC.read_text(encoding="utf-8")


def test_matrix_doc_explains_root_cause() -> None:
    """矩陣頂端要寫共同根因與四個 issue 的關聯。"""
    content = MATRIX_DOC.read_text(encoding="utf-8")
    assert "這套權限設計假設呼叫者是已綁定的自己人" in content
    for issue in ("#201", "#204", "#205", "#207"):
        assert issue in content


def test_matrix_doc_lists_generated_gaps() -> None:
    """已知缺口要由表格資料產生，不是手寫的一句話。"""
    content = MATRIX_DOC.read_text(encoding="utf-8")
    gaps = content.split("## 已知缺口")[-1]

    unchecked = [
        line.split("`")[1]
        for line in content.splitlines()
        if line.startswith("| `") and "是（未檢查）" in line
    ]
    assert unchecked, "矩陣裡應該有沒做權限檢查的工具"
    for name in unchecked:
        assert f"`{name}`" in gaps, f"{name} 沒有出現在已知缺口"

    # 未綁定可呼叫又會送印的代表案例，以及網頁聊天沒注入身分那條
    assert "`prepare_print_file`" in gaps
    assert "api/ai.py" in gaps


def test_write_tools_registry_covers_write_verbs() -> None:
    """負控制：名字是寫入動詞開頭的工具一定要在 WRITE_TOOLS 裡。"""
    content = MATRIX_DOC.read_text(encoding="utf-8")
    tool_names = [
        line.split("`")[1]
        for line in content.splitlines()
        if line.startswith("| `")
    ]
    assert tool_names, "矩陣沒有任何工具列"

    missing = [
        name
        for name in tool_names
        if name.startswith(permissions_module.WRITE_TOOL_NAME_PREFIXES)
        and name not in permissions_module.WRITE_TOOLS
    ]
    assert missing == [], f"這些工具看起來會寫入卻沒分類：{missing}"


def test_write_tools_registry_has_no_unknown_names() -> None:
    """WRITE_TOOLS 裡不該有已經不存在的工具（刪工具忘了清 registry）。"""
    content = MATRIX_DOC.read_text(encoding="utf-8")
    tool_names = {
        line.split("`")[1] for line in content.splitlines() if line.startswith("| `")
    }
    assert permissions_module.WRITE_TOOLS <= tool_names


@pytest.mark.parametrize("tool_name", sorted(permissions_module.TOOLS_REQUIRE_BOUND_USER))
def test_tools_require_bound_user_actually_block(
    tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """負控制：registry 說要擋，`require_bound_user` 就真的要擋。"""
    monkeypatch.delenv("CTOS_USER_ID", raising=False)

    assert (
        mcp_server.require_bound_user(tool_name, None)
        == permissions_module.BOUND_USER_REQUIRED_MESSAGE
    )
    assert mcp_server.require_bound_user(tool_name, 1) is None


def test_require_bound_user_ignores_unlisted_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    assert mcp_server.require_bound_user("search_knowledge", None) is None
