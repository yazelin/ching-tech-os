"""modules.py 基礎行為測試。"""

from __future__ import annotations

from ching_tech_os import modules


def test_is_module_enabled_with_whitelist(monkeypatch) -> None:
    monkeypatch.setattr(modules.settings, "enabled_modules", "core,knowledge-base")
    assert modules.is_module_enabled("core") is True
    assert modules.is_module_enabled("knowledge-base") is True
    assert modules.is_module_enabled("line-bot") is False


def test_get_enabled_app_manifests_filters_disabled(monkeypatch) -> None:
    fake_registry = {
        "core": {"app_manifest": [{"id": "settings", "name": "系統設定", "icon": "mdi-cog"}]},
        "module-a": {"app_manifest": [{"id": "a", "name": "A", "icon": "mdi-a"}]},
        "module-b": {"app_manifest": [{"id": "b", "name": "B", "icon": "mdi-b"}]},
    }
    monkeypatch.setattr(modules, "get_module_registry", lambda: fake_registry)
    monkeypatch.setattr(modules, "is_module_enabled", lambda module_id: module_id != "module-b")

    apps = modules.get_enabled_app_manifests()
    assert [app["id"] for app in apps] == ["settings", "a"]


def test_get_module_registry_uses_public_skill_manager_api(monkeypatch) -> None:
    called = {"value": False}

    class _FakeSkillManager:
        def get_loaded_skills(self):
            called["value"] = True
            return []

    import ching_tech_os.skills as skills_module

    monkeypatch.setattr(skills_module, "get_skill_manager", lambda: _FakeSkillManager())
    registry = modules.get_module_registry()
    assert called["value"] is True
    assert "core" in registry
