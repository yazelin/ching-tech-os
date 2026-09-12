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


def _matrix_rows() -> list[str]:
    return [
        line
        for line in MATRIX_DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `")
    ]


def test_matrix_doc_lists_generated_gaps() -> None:
    """已知缺口要由表格資料產生，不是手寫的一句話。"""
    content = MATRIX_DOC.read_text(encoding="utf-8")
    gaps = content.split("## 已知缺口")[-1]

    unchecked = [
        line.split("`")[1]
        for line in content.splitlines()
        if line.startswith("| `") and "是（未檢查）" in line
    ]
    for name in unchecked:
        assert f"`{name}`" in gaps, f"{name} 沒有出現在已知缺口"

    # 還沒收掉的兩條：Telegram chat id 不在注入範圍、網頁聊天沒注入身分
    assert "telegram_chat_id" in gaps
    assert "api/ai.py" in gaps


def test_no_tool_is_unchecked_and_unregistered() -> None:
    """issue #210：不呼叫 `check_mcp_tool_permission` 的工具一定要登記理由。

    「忘了決定」和「決定要開放」必須分得出來——矩陣裡不該再有「是（未檢查）」。
    """
    unchecked = [line.split("`")[1] for line in _matrix_rows() if "是（未檢查）" in line]
    assert unchecked == [], f"這些工具既沒權限檢查也沒登記理由：{unchecked}"


def test_intentionally_open_registry_is_pinned() -> None:
    """釘住「有意開放」的名單：改了 registry 這條就紅，逼人重新拿決定。"""
    assert set(permissions_module.TOOLS_INTENTIONALLY_OPEN) == {
        # 記憶四支：範圍由注入身分決定（issue #204）
        "add_memory",
        "get_memories",
        "update_memory",
        "delete_memory",
        # 讀對話／附件兩支：注入身分限自己的群組（issue #209）
        "summarize_chat",
        "get_message_attachments",
        # 純產出型三支
        "download_web_image",
        "text_to_speech",
        "browse_webpage",
    }
    for name, reason in permissions_module.TOOLS_INTENTIONALLY_OPEN.items():
        assert reason.strip(), f"{name} 沒有寫理由"


def test_intentionally_open_tools_exist_and_show_reasons() -> None:
    """registry 裡的名字要真的是工具，理由要逐字出現在矩陣裡。"""
    tool_names = {line.split("`")[1] for line in _matrix_rows()}
    content = MATRIX_DOC.read_text(encoding="utf-8")

    for name, reason in permissions_module.TOOLS_INTENTIONALLY_OPEN.items():
        assert name in tool_names, f"{name} 不是現存的工具"
        assert reason in content, f"{name} 的理由沒有出現在矩陣裡"


def test_intentionally_open_tools_do_not_call_permission_check() -> None:
    """負控制：登記開放的工具不能同時呼叫 `check_mcp_tool_permission`。

    「登記開放」與「有做 app 權限檢查」是兩個相反的決定。兩者並存時矩陣會謊報
    （標成「是（登記開放）」，但實際上權限那一關會擋），所以產生器的 `_classify()`
    直接丟 ValueError，這裡確認現況沒有這種矛盾。
    """
    import inspect
    import os
    import sys

    os.environ["ENABLED_MODULES"] = "*"
    sys.path.insert(0, str(BACKEND_DIR / "src"))
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))
    import gen_tool_access_matrix as generator

    tools = generator._load_tools()
    offenders = []
    for name in permissions_module.TOOLS_INTENTIONALLY_OPEN:
        tool = tools.get(name)
        if tool is None:
            continue
        source = inspect.getsource(inspect.unwrap(tool.fn))
        if any(marker in source for marker in generator._PERMISSION_CALL_MARKERS):
            offenders.append(name)

    assert offenders == [], f"這些工具同時登記開放又做了權限檢查：{offenders}"


def test_classify_rejects_contradictory_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """產生器遇到矛盾要爆掉，不是靜靜標成開放。"""
    import sys

    sys.path.insert(0, str(BACKEND_DIR / "src"))
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))
    import gen_tool_access_matrix as generator

    tools = generator._load_tools()
    # search_knowledge 有呼叫 check_mcp_tool_permission，硬把它登記成開放
    monkeypatch.setitem(
        permissions_module.TOOLS_INTENTIONALLY_OPEN, "search_knowledge", "亂寫的理由"
    )
    with pytest.raises(ValueError, match="同時登記在 TOOLS_INTENTIONALLY_OPEN"):
        generator._classify("search_knowledge", tools["search_knowledge"])


def test_intentionally_open_tools_do_not_also_require_bound_user() -> None:
    """同一支不能又「登記開放」又「要求綁定」——那是兩個相反的決定。"""
    overlap = set(permissions_module.TOOLS_INTENTIONALLY_OPEN) & (
        permissions_module.TOOLS_REQUIRE_BOUND_USER
    )
    assert overlap == set(), f"這些工具的決定自相矛盾：{sorted(overlap)}"


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
