"""測試 modules.py 中未覆蓋的函數"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ching_tech_os.modules import (
    _normalize_frontend_asset,
    _resolve_skill_file,
    _build_skill_module,
)


# ============================================
# _normalize_frontend_asset
# ============================================


class TestNormalizeFrontendAsset:
    def test_normal_path(self):
        result = _normalize_frontend_asset("my-skill", "app.js")
        assert result == "/api/skills/my-skill/frontend/app.js"

    def test_dot_slash_prefix(self):
        result = _normalize_frontend_asset("my-skill", "./css/style.css")
        assert result == "/api/skills/my-skill/frontend/css/style.css"

    def test_frontend_prefix(self):
        result = _normalize_frontend_asset("my-skill", "frontend/app.js")
        assert result == "/api/skills/my-skill/frontend/app.js"

    def test_both_prefixes(self):
        result = _normalize_frontend_asset("my-skill", "./frontend/main.js")
        assert result == "/api/skills/my-skill/frontend/main.js"

    def test_empty_string(self):
        result = _normalize_frontend_asset("my-skill", "")
        assert result is None

    def test_slash_prefix(self):
        result = _normalize_frontend_asset("my-skill", "/absolute/path.js")
        assert result is None

    def test_dotdot_traversal(self):
        result = _normalize_frontend_asset("my-skill", "../secret/file.js")
        assert result is None

    def test_backslash(self):
        result = _normalize_frontend_asset("my-skill", "css\\style.css")
        assert result == "/api/skills/my-skill/frontend/css/style.css"

    def test_whitespace_stripped(self):
        result = _normalize_frontend_asset("my-skill", "  app.js  ")
        assert result == "/api/skills/my-skill/frontend/app.js"


# ============================================
# _resolve_skill_file
# ============================================


class TestResolveSkillFile:
    def test_path_traversal(self, tmp_path):
        """路徑穿越防護"""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        # 建立一個在 skill_dir 外的檔案
        outer_file = tmp_path / "secret.txt"
        outer_file.write_text("secret")
        result = _resolve_skill_file(skill_dir, "../secret.txt")
        assert result is None

    def test_file_not_exist(self, tmp_path):
        """檔案不存在"""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        result = _resolve_skill_file(skill_dir, "nonexistent.py")
        assert result is None

    def test_success(self, tmp_path):
        """正常回傳路徑"""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        mcp_file = skill_dir / "mcp_tools.py"
        mcp_file.write_text("# tools")
        result = _resolve_skill_file(skill_dir, "mcp_tools.py")
        assert result == str(mcp_file.resolve())


# ============================================
# _build_skill_module
# ============================================


class TestBuildSkillModule:
    def _make_skill(self, name="test-skill", metadata=None, skill_dir=None):
        skill = MagicMock()
        skill.name = name
        skill.metadata = metadata or {}
        skill.skill_dir = skill_dir
        return skill

    def test_no_contributes(self):
        """無 contributes 回傳 None"""
        skill = self._make_skill(metadata={})
        assert _build_skill_module(skill) is None

    def test_contributes_not_dict(self):
        """contributes 非 dict 回傳 None"""
        skill = self._make_skill(metadata={"contributes": "bad"})
        assert _build_skill_module(skill) is None

    def test_minimal_contributes(self):
        """最小 contributes"""
        skill = self._make_skill(
            metadata={"contributes": {"permissions": {"my-app": True}}},
        )
        result = _build_skill_module(skill)
        assert result is not None
        assert result["id"] == "test-skill"
        assert result["permission_defaults"] == {"my-app": True}

    def test_with_app_data(self):
        """有 app manifest"""
        skill = self._make_skill(
            metadata={
                "contributes": {
                    "app": {
                        "id": "my-app",
                        "name": "我的應用",
                        "icon": "star",
                    },
                }
            },
        )
        result = _build_skill_module(skill)
        assert result is not None
        assert result["id"] == "my-app"
        assert len(result["app_manifest"]) == 1
        assert result["app_manifest"][0]["name"] == "我的應用"

    def test_with_app_loader(self, tmp_path):
        """有 app loader"""
        skill = self._make_skill(
            metadata={
                "contributes": {
                    "app": {
                        "id": "loader-app",
                        "name": "Loader App",
                        "icon": "play",
                        "loader": {
                            "src": "app.js",
                            "globalName": "MyApp",
                        },
                    },
                }
            },
        )
        result = _build_skill_module(skill)
        assert result is not None
        app = result["app_manifest"][0]
        assert "loader" in app
        assert app["loader"]["globalName"] == "MyApp"

    def test_with_app_css(self):
        """有 app CSS"""
        skill = self._make_skill(
            metadata={
                "contributes": {
                    "app": {
                        "id": "css-app",
                        "name": "CSS App",
                        "icon": "palette",
                        "css": "style.css",
                    },
                }
            },
        )
        result = _build_skill_module(skill)
        assert result is not None
        app = result["app_manifest"][0]
        assert "css" in app

    def test_with_permissions_dict_config(self):
        """permissions 使用 dict config 格式"""
        skill = self._make_skill(
            metadata={
                "contributes": {
                    "permissions": {
                        "feature-a": {"default": False, "display_name": "功能A"},
                        "feature-b": True,
                    }
                }
            },
        )
        result = _build_skill_module(skill)
        assert result["permission_defaults"]["feature-a"] is False
        assert result["permission_defaults"]["feature-b"] is True
        assert result["permission_display_names"]["feature-a"] == "功能A"

    def test_with_mcp_tools(self, tmp_path):
        """有 mcp_tools 設定"""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        mcp_file = skill_dir / "mcp_tools.py"
        mcp_file.write_text("# tools")

        skill = self._make_skill(
            metadata={
                "contributes": {
                    "mcp_tools": "mcp_tools.py",
                    "permissions": {"app": True},
                }
            },
            skill_dir=skill_dir,
        )
        result = _build_skill_module(skill)
        assert result is not None
        assert "mcp_tools_file" in result

    def test_with_invalid_mcp_tools_path(self, tmp_path):
        """mcp_tools 路徑無效"""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        skill = self._make_skill(
            metadata={
                "contributes": {
                    "mcp_tools": "nonexistent.py",
                    "permissions": {"app": True},
                }
            },
            skill_dir=skill_dir,
        )
        result = _build_skill_module(skill)
        assert result is not None
        assert "mcp_tools_file" not in result

    def test_with_scheduler(self):
        """有 scheduler 設定"""
        skill = self._make_skill(
            metadata={
                "contributes": {
                    "permissions": {"app": True},
                    "scheduler": [
                        {"id": "job1", "trigger": "cron", "hour": "8"},
                    ],
                }
            },
        )
        result = _build_skill_module(skill)
        assert result is not None
        assert "scheduler_jobs" in result
        assert len(result["scheduler_jobs"]) == 1
