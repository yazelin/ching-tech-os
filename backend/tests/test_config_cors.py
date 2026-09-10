"""CORS_EXTRA_ORIGINS 解析。"""

from ching_tech_os import config


def test_parse_extra_origins_strips_and_drops_empty():
    parsed = config._parse_extra_origins("https://os.ching-tech.com, http://localhost:5173 ,")
    assert parsed == ["https://os.ching-tech.com", "http://localhost:5173"]
    assert config._parse_extra_origins("") == []


def test_default_origins_preserved():
    assert "http://localhost:8080" in config.settings.cors_origins
    assert "https://md-2-ppt-evolution.vercel.app" in config.settings.cors_origins
