"""CORS_EXTRA_ORIGINS 解析。"""

import importlib


def test_cors_extra_origins_appended(monkeypatch):
    monkeypatch.setenv("CORS_EXTRA_ORIGINS", "https://os.ching-tech.com, http://localhost:5173 ,")
    import ching_tech_os.config as config
    importlib.reload(config)
    origins = config.settings.cors_origins
    assert "https://os.ching-tech.com" in origins
    assert "http://localhost:5173" in origins
    assert "" not in origins
    assert "http://localhost:8080" in origins  # 原本的沒被蓋掉
    monkeypatch.delenv("CORS_EXTRA_ORIGINS")
    importlib.reload(config)
