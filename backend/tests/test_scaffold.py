"""scaffold.py 產生器測試

以 subprocess 執行 scripts/scaffold.py，驗證骨架產生、拒絕覆蓋與
extends contributes.yaml 驗證。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"


def run_scaffold(*args: str) -> subprocess.CompletedProcess:
    """以目前 Python 直譯器執行 scaffold.py"""
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


# ============================================================
# app 子命令
# ============================================================


def test_app_generates_five_files(tmp_path: Path) -> None:
    """app 子命令產生 5 個檔案且內容含關鍵字"""
    result = run_scaffold("app", "demo-widget", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr

    api_file = tmp_path / "backend/src/ching_tech_os/api/demo_widget.py"
    service_file = tmp_path / "backend/src/ching_tech_os/services/demo_widget.py"
    model_file = tmp_path / "backend/src/ching_tech_os/models/demo_widget.py"
    js_file = tmp_path / "frontend/js/demo-widget.js"
    css_file = tmp_path / "frontend/css/demo-widget.css"
    for path in (api_file, service_file, model_file, js_file, css_file):
        assert path.is_file(), f"未產生 {path}"

    # API：掛 require_app_permission 且 prefix 正確
    api_text = api_file.read_text(encoding="utf-8")
    assert 'require_app_permission("demo-widget")' in api_text
    assert 'prefix="/api/demo-widget"' in api_text

    # 服務層 / 模型
    assert "list_items" in service_file.read_text(encoding="utf-8")
    assert "BaseModel" in model_file.read_text(encoding="utf-8")

    # 前端：IIFE 模組 + 掛載到 window
    js_text = js_file.read_text(encoding="utf-8")
    assert "const DemoWidgetApp = (function()" in js_text
    assert "window.DemoWidgetApp = DemoWidgetApp" in js_text

    # CSS：使用 CSS 變數
    assert "var(--text-primary)" in css_file.read_text(encoding="utf-8")

    # 手動步驟清單
    assert "BUILTIN_MODULES" in result.stdout
    assert "desktop.js" in result.stdout
    assert "module-index.md" in result.stdout


def test_app_refuses_overwrite(tmp_path: Path) -> None:
    """重複執行同一 app-id 被拒絕（exit 1，不覆蓋既有檔案）"""
    first = run_scaffold("app", "demo-widget", "--root", str(tmp_path))
    assert first.returncode == 0, first.stderr
    js_file = tmp_path / "frontend/js/demo-widget.js"
    original = js_file.read_text(encoding="utf-8")

    second = run_scaffold("app", "demo-widget", "--root", str(tmp_path))
    assert second.returncode == 1
    assert "拒絕覆蓋" in second.stderr
    assert js_file.read_text(encoding="utf-8") == original


# ============================================================
# extends / skill 子命令
# ============================================================


def test_extends_generates_skeleton(tmp_path: Path) -> None:
    """extends 子命令產生 contributes.yaml / core / README"""
    result = run_scaffold("extends", "my-module", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr

    module_dir = tmp_path / "extends/my-module"
    contributes = (module_dir / "contributes.yaml").read_text(encoding="utf-8")
    assert "module_id: my-module" in contributes
    # 四種貢獻皆有註解說明
    for keyword in ("mcp_tools", "mcp_servers", "lifespan", "routers"):
        assert keyword in contributes, f"contributes.yaml 缺少 {keyword} 說明"

    assert (module_dir / "core/__init__.py").is_file()
    mcp_tools = (module_dir / "core/mcp_tools.py").read_text(encoding="utf-8")
    assert "ching_tech_os.services.mcp.server" in mcp_tools
    assert "ensure_db_connection" in mcp_tools
    assert (module_dir / "README.md").is_file()


def test_skill_generates_skeleton(tmp_path: Path) -> None:
    """skill 子命令產生 SKILL.md + scripts；--extends 改放 extends 下"""
    result = run_scaffold("skill", "my-skill", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr

    skill_dir = tmp_path / "backend/src/ching_tech_os/skills/my-skill"
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "name: my-skill" in skill_md
    assert "allowed-tools:" in skill_md
    assert "requires_app" in skill_md

    script = (skill_dir / "scripts/example.py").read_text(encoding="utf-8")
    assert "sys.stdin.read" in script  # 讀 stdin JSON
    assert "json.dumps" in script  # 輸出 stdout

    # --extends 放到 extends/<module>/skills/ 下
    result2 = run_scaffold(
        "skill", "ext-skill", "--extends", "my-module", "--root", str(tmp_path)
    )
    assert result2.returncode == 0, result2.stderr
    assert (tmp_path / "extends/my-module/skills/ext-skill/SKILL.md").is_file()
    assert (tmp_path / "extends/my-module/skills/ext-skill/scripts/example.py").is_file()


# ============================================================
# validate 子命令
# ============================================================


def test_validate_passes_on_real_repo() -> None:
    """validate 對現有 repo 的 extends 應通過（exit 0）"""
    result = run_scaffold("validate")
    assert result.returncode == 0, (
        "validate 在現有 repo 失敗，請檢查 extends/*/contributes.yaml：\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "驗證通過" in result.stdout


def test_validate_reports_problems(tmp_path: Path) -> None:
    """validate 對有問題的宣告逐項回報並 exit 1"""
    bad_dir = tmp_path / "extends/bad-module"
    bad_dir.mkdir(parents=True)
    (bad_dir / "contributes.yaml").write_text(
        "module_id: dup-id\n"
        "mcp_tools: core/mcp_tools.py\n"  # 檔案不存在
        "mcp_servers:\n"
        "  bad:\n"
        "    args: [x]\n",  # 缺 command 欄位
        encoding="utf-8",
    )
    # 第二個模組重複 module_id
    dup_dir = tmp_path / "extends/dup-module"
    dup_dir.mkdir(parents=True)
    (dup_dir / "contributes.yaml").write_text("module_id: dup-id\n", encoding="utf-8")

    result = run_scaffold("validate", "--root", str(tmp_path))
    assert result.returncode == 1
    assert "mcp_tools 檔案不存在" in result.stdout
    assert "缺少 command 欄位" in result.stdout
    assert "module_id 重複" in result.stdout
